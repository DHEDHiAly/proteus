import numpy as np
import uuid
import json
import logging
from typing import List, Optional, Callable, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from app.core.energy import EnergyOracle
from app.core.proposal import ProposalDistribution

logger = logging.getLogger(__name__)

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


@dataclass
class ChainResult:
    chain_index: int
    temperature: float
    steps: int
    initial_sequence: str
    final_sequence: str
    initial_energy: float
    final_energy: float
    best_energy: float
    best_sequence: str
    acceptance_rate: float
    energy_trace: List[float] = field(default_factory=list)
    temperature_trace: List[float] = field(default_factory=list)
    mutation_log: List[dict] = field(default_factory=list)
    converged: bool = False


@dataclass
class MCMCRunResult:
    run_id: str
    target_name: str
    seed_sequence: str
    chains: List[ChainResult]
    best_overall_sequence: str
    best_overall_energy: float
    converged: bool
    rhat: Optional[float]
    ess: Optional[int]
    total_best_sequence: str
    total_best_energy: float
    wall_time_seconds: float
    candidates: List[dict] = field(default_factory=list)


class MCMCParallelSampler:
    def __init__(
        self,
        energy_oracle: EnergyOracle,
        proposal_dist: ProposalDistribution,
        num_chains: int = 5,
        temperatures: Optional[List[float]] = None,
        steps_per_chain: int = 1000,
        swap_interval: int = 50,
        convergence_check_interval: int = 50,
        patience: int = 100,
        min_effective_samples: int = 100,
        gelman_rubin_threshold: float = 1.05,
        progress_callback: Optional[Callable] = None,
    ):
        self.energy_oracle = energy_oracle
        self.proposal_dist = proposal_dist
        self.num_chains = num_chains
        self.temperatures = temperatures or [0.5, 1.0, 2.0, 5.0, 10.0]
        self.steps_per_chain = steps_per_chain
        self.swap_interval = swap_interval
        self.convergence_check_interval = convergence_check_interval
        self.patience = patience
        self.min_effective_samples = min_effective_samples
        self.gelman_rubin_threshold = gelman_rubin_threshold
        self.progress_callback = progress_callback

    def _accept_or_reject(self, current_energy: float, proposed_energy: float,
                          temperature: float) -> Tuple[bool, float]:
        if temperature <= 0:
            temperature = 0.01
        delta = current_energy - proposed_energy
        log_accept_prob = delta / temperature
        log_accept_prob = min(log_accept_prob, 0.0)
        accept_prob = np.exp(log_accept_prob)
        accepted = np.random.random() < accept_prob
        return accepted, accept_prob

    def _run_single_chain(self, sequence: str, chain_index: int, temperature: float,
                          target_name: str) -> ChainResult:
        current_sequence = sequence
        current_energy = self.energy_oracle.compute_energy(current_sequence)
        best_sequence = current_sequence
        best_energy = current_energy

        energy_trace = [current_energy]
        mutation_log = []
        accepted_count = 0

        for step in range(1, self.steps_per_chain + 1):
            proposed_seq, pos, from_aa, to_aa, operation = self.proposal_dist.propose(
                current_sequence, target_name
            )
            proposed_energy = self.energy_oracle.compute_energy(proposed_seq)
            accepted, accept_prob = self._accept_or_reject(current_energy, proposed_energy, temperature)

            mutation_log.append({
                "step": step,
                "position": pos,
                "from_aa": str(from_aa) if not isinstance(from_aa, list) else ",".join(from_aa),
                "to_aa": str(to_aa) if not isinstance(to_aa, list) else ",".join(to_aa),
                "mutation_type": operation,
                "energy_before": float(current_energy),
                "energy_after": float(proposed_energy),
                "delta_energy": float(proposed_energy - current_energy),
                "acceptance_probability": float(accept_prob),
                "accepted": bool(accepted),
                "temperature": float(temperature),
            })

            if accepted:
                current_sequence = proposed_seq
                current_energy = proposed_energy
                accepted_count += 1
                if current_energy < best_energy:
                    best_energy = current_energy
                    best_sequence = current_sequence

            energy_trace.append(current_energy)

            # Adaptive temperature: every 50 steps, adjust toward 23–40% acceptance
            if step % 50 == 0 and step >= 50:
                recent = mutation_log[max(0, len(mutation_log) - 50):]
                recent_rate = sum(1 for m in recent if m.get("accepted")) / max(len(recent), 1)
                if recent_rate < 0.23:
                    temperature = min(temperature * 1.1, 50.0)
                elif recent_rate > 0.40:
                    temperature = max(temperature * 0.9, 0.05)

            if self.progress_callback and step % 10 == 0:
                self.progress_callback({
                    "type": "progress",
                    "run_id": "",
                    "chain_index": chain_index,
                    "step": step,
                    "total_steps": self.steps_per_chain,
                    "current_energy": float(current_energy),
                    "best_energy": float(best_energy),
                    "acceptance_rate": float(accepted_count / max(step, 1)),
                    "temperature": float(temperature),
                    "current_sequence": current_sequence,
                    "best_sequence": best_sequence,
                })

        acceptance_rate = accepted_count / self.steps_per_chain

        return ChainResult(
            chain_index=chain_index,
            temperature=temperature,
            steps=self.steps_per_chain,
            initial_sequence=sequence,
            final_sequence=current_sequence,
            initial_energy=energy_trace[0],
            final_energy=current_energy,
            best_energy=best_energy,
            best_sequence=best_sequence,
            acceptance_rate=acceptance_rate,
            energy_trace=energy_trace,
            mutation_log=mutation_log,
        )

    def _swap_chains(self, chain_results: List[ChainResult], current_energies: List[float],
                     sequences: List[str]) -> Tuple[List[str], List[float], bool]:
        swapped = False
        for i in range(len(chain_results) - 1):
            beta_i = 1.0 / max(chain_results[i].temperature, 0.01)
            beta_j = 1.0 / max(chain_results[i + 1].temperature, 0.01)
            log_swap_prob = (current_energies[i] - current_energies[i + 1]) * (beta_i - beta_j)
            if np.random.random() < np.exp(min(log_swap_prob, 0.0)):
                sequences[i], sequences[i + 1] = sequences[i + 1], sequences[i]
                current_energies[i], current_energies[i + 1] = current_energies[i + 1], current_energies[i]
                swapped = True
        return sequences, current_energies, swapped

    def _compute_rhat(self, chain_energies: List[List[float]]) -> float:
        if len(chain_energies) < 2:
            return 1.0
        m = len(chain_energies)
        n = min(len(c) for c in chain_energies)
        if n < 2:
            return 1.0
        truncated = [c[-n:] for c in chain_energies]

        chain_means = np.array([np.mean(c) for c in truncated])
        chain_vars = np.array([np.var(c, ddof=1) for c in truncated])
        overall_mean = np.mean(chain_means)

        between_var = n / (m - 1) * np.sum((chain_means - overall_mean) ** 2)
        within_var = np.mean(chain_vars)
        marginal_var = ((n - 1) / n) * within_var + (1 / n) * between_var
        rhat = np.sqrt(marginal_var / max(within_var, 1e-10))
        return float(rhat)

    def _compute_ess(self, chain_energies: List[List[float]]) -> int:
        all_energies = np.concatenate(chain_energies)
        n = len(all_energies)
        if n < 10:
            return n
        acf = np.correlate(all_energies - np.mean(all_energies),
                           all_energies - np.mean(all_energies), mode="full")
        acf = acf[n - 1:] / acf[n - 1]
        tau = 1.0
        for k in range(1, min(n // 2, 100)):
            if acf[k] > 0.05:
                tau += 2 * acf[k]
            else:
                break
        ess = int(n / max(tau, 1.0))
        return max(ess, 1)

    def run(self, seed_sequence: str, target_name: str = "",
            chain_callbacks: Optional[List[Callable]] = None) -> MCMCRunResult:
        run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        sequences = [seed_sequence] * self.num_chains
        current_energies = [self.energy_oracle.compute_energy(s) for s in sequences]

        chain_results = []
        for i in range(self.num_chains):
            chain_result = self._run_single_chain(
                sequences[i], i, self.temperatures[i], target_name
            )
            chain_results.append(chain_result)
            current_energies[i] = chain_result.final_energy
            sequences[i] = chain_result.final_sequence
            if self.progress_callback:
                self.progress_callback({
                    "type": "chain_complete",
                    "run_id": run_id,
                    "chain_index": i,
                    "best_energy": chain_result.best_energy,
                    "acceptance_rate": chain_result.acceptance_rate,
                })

        best_chain = min(chain_results, key=lambda c: c.best_energy)
        best_overall_sequence = best_chain.best_sequence
        best_overall_energy = best_chain.best_energy

        energy_traces = [c.energy_trace for c in chain_results]
        rhat = self._compute_rhat(energy_traces)
        ess = self._compute_ess(energy_traces)

        converged = (rhat is not None and rhat < self.gelman_rubin_threshold
                     and ess is not None and ess >= self.min_effective_samples)

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        candidates = []
        ranked = sorted(chain_results, key=lambda c: c.best_energy)
        for i, chain in enumerate(ranked):
            candidate_info = self.energy_oracle.score_candidate(
                chain.best_sequence, target_name
            )
            candidate_info["rank"] = i + 1
            candidate_info["chain_index"] = chain.chain_index
            candidate_info["temperature"] = chain.temperature
            candidates.append(candidate_info)

        result = MCMCRunResult(
            run_id=run_id,
            target_name=target_name,
            seed_sequence=seed_sequence,
            chains=chain_results,
            best_overall_sequence=best_overall_sequence,
            best_overall_energy=best_overall_energy,
            converged=converged,
            rhat=rhat,
            ess=ess,
            total_best_sequence=best_overall_sequence,
            total_best_energy=best_overall_energy,
            wall_time_seconds=elapsed,
            candidates=candidates,
        )

        if self.progress_callback:
            self.progress_callback({
                "type": "complete",
                "run_id": run_id,
                "best_sequence": best_overall_sequence,
                "best_energy": float(best_overall_energy),
                "converged": converged,
                "rhat": float(rhat) if rhat else None,
                "ess": ess,
                "wall_time_seconds": elapsed,
            })

        return result

    def to_dict(self, result: MCMCRunResult) -> dict:
        return {
            "run_id": result.run_id,
            "target_name": result.target_name,
            "seed_sequence": result.seed_sequence,
            "best_overall_sequence": result.best_overall_sequence,
            "best_overall_energy": result.best_overall_energy,
            "converged": result.converged,
            "rhat": result.rhat,
            "ess": result.ess,
            "wall_time_seconds": result.wall_time_seconds,
            "chains": [
                {
                    "chain_index": c.chain_index,
                    "temperature": c.temperature,
                    "initial_energy": c.initial_energy,
                    "final_energy": c.final_energy,
                    "best_energy": c.best_energy,
                    "best_sequence": c.best_sequence,
                    "acceptance_rate": c.acceptance_rate,
                    "converged": c.converged,
                    "energy_trace": c.energy_trace,
                    "mutation_log": c.mutation_log,
                }
                for c in result.chains
            ],
            "candidates": result.candidates,
        }



