import pytest
import numpy as np
from app.core.mcmc import MCMCParallelSampler, MCMCRunResult, ChainResult
from app.core.energy import EnergyOracle
from app.core.proposal import ProposalDistribution


class TestMCMCConvergence:
    @pytest.fixture
    def energy_oracle(self):
        return EnergyOracle()

    @pytest.fixture
    def proposal_dist(self):
        return ProposalDistribution()

    @pytest.fixture
    def sampler(self, energy_oracle, proposal_dist):
        return MCMCParallelSampler(
            energy_oracle=energy_oracle,
            proposal_dist=proposal_dist,
            num_chains=2,
            temperatures=[0.5, 1.0],
            steps_per_chain=20,
            swap_interval=10,
            convergence_check_interval=5,
            patience=5,
            min_effective_samples=5,
            gelman_rubin_threshold=1.5,
        )

    def test_sampler_initialization(self, sampler):
        assert sampler.num_chains == 2
        assert sampler.temperatures == [0.5, 1.0]
        assert sampler.steps_per_chain == 20
        assert sampler.swap_interval == 10

    def test_run_returns_mcmc_result(self, sampler):
        result = sampler.run("MVLDGEQG", "test_target")
        assert isinstance(result, MCMCRunResult)
        assert result.run_id is not None
        assert len(result.chains) == 2

    def test_chain_result_structure(self, sampler):
        result = sampler.run("MVLDGEQG", "test_target")
        for chain in result.chains:
            assert isinstance(chain, ChainResult)
            assert isinstance(chain.energy_trace, list)
            assert len(chain.energy_trace) > 0
            assert chain.acceptance_rate >= 0.0
            assert chain.acceptance_rate <= 1.0

    def test_best_energy_is_minimal(self, sampler):
        result = sampler.run("MVLDGEQG", "test_target")
        for chain in result.chains:
            assert chain.best_energy <= chain.initial_energy
            assert chain.best_energy <= chain.final_energy

    def test_rhat_computation(self, sampler):
        result = sampler.run("MVLDGEQG", "test_target")
        assert result.rhat is not None

    def test_ess_positive(self, sampler):
        result = sampler.run("MVLDGEQG", "test_target")
        if result.ess is not None:
            assert result.ess > 0

    def test_candidates_ranked(self, sampler):
        result = sampler.run("MVLDGEQG", "test_target")
        assert len(result.candidates) > 0
        for i, candidate in enumerate(result.candidates):
            assert candidate["rank"] == i + 1

    def test_different_seeds_produce_different_results(self, sampler):
        result1 = sampler.run("MVLDGEQG", "test_target")
        result2 = sampler.run("MVAQWKEQ", "test_target")
        assert result1.best_overall_sequence != result2.best_overall_sequence or \
               abs(result1.best_overall_energy - result2.best_overall_energy) > 0.01

    def test_small_sequence_works(self, sampler):
        result = sampler.run("MVL", "test_target")
        assert result.best_overall_sequence is not None
        assert len(result.best_overall_sequence) >= 3

    def test_to_dict_serializable(self, sampler):
        result = sampler.run("MVLDGEQG", "test_target")
        d = sampler.to_dict(result)
        assert isinstance(d, dict)
        assert "run_id" in d
        assert "chains" in d
        assert "candidates" in d
        assert len(d["chains"]) == 2


class TestEnergyOracle:
    @pytest.fixture
    def oracle(self):
        return EnergyOracle()

    def test_energy_lower_for_known_binder(self, oracle):
        binder = "MVLDGEQG"
        random_seq = "MVLDXXXX"
        binder_energy = oracle.compute_energy(binder)
        random_energy = oracle.compute_energy(random_seq)
        assert binder_energy < random_energy

    def test_energy_finite(self, oracle):
        for seq in ["MVLDGEQG", "MVAQWKEQ", "CYCLIC_GE11"]:
            energy = oracle.compute_energy(seq)
            assert np.isfinite(energy)
            assert energy >= 0.0

    def test_energy_decomposition(self, oracle):
        seq = "MVLDGEQG"
        decomposition = oracle.compute_energy_decomposition(seq)
        assert "total" in decomposition
        assert "binding" in decomposition
        assert "stability" in decomposition
        assert abs(decomposition["total"] - oracle.compute_energy(seq)) < 1e-6

    def test_pocket_increases_binding(self, oracle):
        seq = "MVLDGEQG"
        energy_no_pocket = oracle.compute_energy(seq)
        oracle.set_target_pocket([0, 2, 4])
        energy_with_pocket = oracle.compute_energy(seq)
        assert energy_no_pocket != energy_with_pocket

    def test_gravy_computation(self, oracle):
        hydrophobic = "IIIIII"
        hydrophilic = "DDDDDD"
        assert oracle._compute_gravy(hydrophobic) > oracle._compute_gravy(hydrophilic)

    def test_charge_computation(self, oracle):
        positive = "KKKKKK"
        negative = "DDDDDD"
        neutral = "GGGGGG"
        assert oracle._compute_net_charge(positive) > 0
        assert oracle._compute_net_charge(negative) < 0
        assert abs(oracle._compute_net_charge(neutral)) < 0.1

    def test_empty_sequence(self, oracle):
        assert oracle.compute_energy("") == 1000.0

    def test_blosum_similarity(self, oracle):
        sim_identical = oracle.compute_blosum_similarity("A", "A")
        sim_conserved = oracle.compute_blosum_similarity("D", "E")
        sim_dissimilar = oracle.compute_blosum_similarity("A", "W")
        assert sim_identical >= sim_conserved
        assert sim_conserved >= sim_dissimilar


class TestProposalDistribution:
    @pytest.fixture
    def proposal(self):
        return ProposalDistribution()

    def test_point_substitution_changes_one_aa(self, proposal):
        seq = "MVLDGEQG"
        new_seq, pos, from_aa, to_aa = proposal.point_substitution(seq)
        assert len(new_seq) == len(seq)
        assert from_aa != to_aa
        assert new_seq[pos] == to_aa
        assert seq[pos] == from_aa
        mutations = sum(1 for a, b in zip(seq, new_seq) if a != b)
        assert mutations == 1

    def test_block_replacement_changes_block(self, proposal):
        seq = "MVLDGEQG"
        new_seq, start, old_block, new_block = proposal.block_replacement(seq, block_size=3)
        assert len(new_seq) == len(seq)
        assert len(old_block) == len(new_block)
        assert old_block != new_block

    def test_propose_returns_valid(self, proposal):
        seq = "MVLDGEQG"
        new_seq, pos, from_aa, to_aa, operation = proposal.propose(seq)
        assert len(new_seq) == len(seq)
        assert isinstance(operation, str)
        assert operation in ["point_substitution", "esm_guided_substitution",
                             "block_replacement", "llm_jump"]

    def test_llm_jump_changes_multiple(self, proposal):
        seq = "MVLDGEQG"
        new_seq, positions, old_chars, new_chars = proposal.llm_jump(seq)
        assert len(new_seq) == len(seq)
        assert len(positions) >= 2
        assert old_chars != new_chars
