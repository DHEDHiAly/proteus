import asyncio
import json
import logging
import uuid
import numpy as np
from typing import Optional, Callable, Dict, Any
from datetime import datetime
from sqlalchemy import select

from app.config import settings
from app.core.mcmc import MCMCParallelSampler, MCMCRunResult
from app.core.energy import EnergyOracle
from app.core.proposal import ProposalDistribution
from app.core.esm2 import ESM2EmbeddingCache
from app.models.run import RunStatus, MCMCRun, ChainState, MutationStep, DesignedCandidate
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class MCMCJobRunner:
    def __init__(self):
        self.esm_cache = ESM2EmbeddingCache(settings.ESM_CACHE_DIR)
        self.active_jobs: Dict[str, asyncio.Task] = {}
        self.progress_callbacks: Dict[str, list] = {}

    def create_sampler(self, config: dict, run_id: str,
                       progress_callback: Optional[Callable] = None) -> MCMCParallelSampler:
        mcmc_config = config.get("mcmc", {})
        scoring_config = config.get("scoring", {})

        energy_oracle = EnergyOracle({"scoring": scoring_config})
        proposal_dist = ProposalDistribution(self.esm_cache._cache)

        num_chains = mcmc_config.get("num_chains", 5)
        temperatures = mcmc_config.get("temperatures", [0.5, 1.0, 2.0, 5.0, 10.0])
        steps_per_chain = mcmc_config.get("steps_per_chain", 1000)

        convergence = config.get("convergence", {})

        def wrapped_callback(msg):
            msg["run_id"] = run_id
            if progress_callback:
                progress_callback(msg)

        return MCMCParallelSampler(
            energy_oracle=energy_oracle,
            proposal_dist=proposal_dist,
            num_chains=num_chains,
            temperatures=temperatures,
            steps_per_chain=steps_per_chain,
            swap_interval=mcmc_config.get("swap_interval", 50),
            convergence_check_interval=convergence.get("check_interval", 50),
            patience=convergence.get("patience", 100),
            min_effective_samples=convergence.get("min_effective_samples", 100),
            gelman_rubin_threshold=convergence.get("gelman_rubin_threshold", 1.05),
            progress_callback=wrapped_callback,
        )

    def get_target_pdb_id(self, target_name: str, targets_meta: list) -> str:
        for t in targets_meta:
            if t["name"] == target_name:
                return t.get("pdb_id", "")
        return ""

    def get_target_pocket(self, target_name: str, targets_meta: list) -> list:
        for t in targets_meta:
            if t["name"] == target_name:
                return t.get("binding_site_residues", [])
        return []

    def register_progress_callback(self, run_id: str, callback: Callable):
        if run_id not in self.progress_callbacks:
            self.progress_callbacks[run_id] = []
        self.progress_callbacks[run_id].append(callback)

    def unregister_progress_callback(self, run_id: str, callback: Callable):
        if run_id in self.progress_callbacks:
            self.progress_callbacks[run_id] = [cb for cb in self.progress_callbacks[run_id]
                                               if cb is not callback]

    async def broadcast_progress(self, run_id: str, message: dict):
        if run_id in self.progress_callbacks:
            for callback in self.progress_callbacks[run_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")

    async def run_job(
        self,
        run_id: uuid.UUID,
        seed_sequence: str,
        target_name: str,
        config: dict,
        targets_meta: list,
        db_session_factory,
        audit_service_factory,
    ):
        run_id_str = str(run_id)
        logger.info(f"Starting MCMC job {run_id_str} for target {target_name}")

        # Capture the running event loop at async entry; _run_chain_epoch runs in
        # ThreadPoolExecutor threads where get_running_loop() would fail.
        loop = asyncio.get_running_loop()

        try:
            async with db_session_factory() as db:
                result = await db.execute(
                    select(MCMCRun).where(MCMCRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if not run:
                    logger.error(f"Run {run_id_str} not found in database")
                    return
                run.status = RunStatus.RUNNING
                run.started_at = datetime.utcnow()
                await db.commit()

            sampler = self.create_sampler(
                config, run_id_str,
                progress_callback=lambda msg: asyncio.run_coroutine_threadsafe(
                    self.broadcast_progress(run_id_str, msg), loop
                ),
            )

            energy_oracle = sampler.energy_oracle
            pocket = self.get_target_pocket(target_name, targets_meta)
            if pocket:
                energy_oracle.set_target_pocket(pocket)

            mcmc_result = sampler.run(seed_sequence, target_name)

            async with db_session_factory() as db:
                result = await db.execute(
                    select(MCMCRun).where(MCMCRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if not run:
                    return

                run.status = RunStatus.COMPLETED
                run.completed_at = datetime.utcnow()
                run.total_steps_completed = (
                    mcmc_result.chains[0].steps * len(mcmc_result.chains)
                    if mcmc_result.chains else 0
                )
                run.best_score = mcmc_result.best_overall_energy
                run.best_sequence = mcmc_result.best_overall_sequence
                run.convergence_rhat = mcmc_result.rhat
                run.convergence_ess = mcmc_result.ess
                run.results_hash = AuditService.compute_hash(
                    sampler.to_dict(mcmc_result)
                )

                for chain in mcmc_result.chains:
                    best_idx = int(np.argmin(chain.energy_trace)) if chain.energy_trace else 0
                    best_seq = chain.mutation_log[best_idx]["to_aa"] if chain.mutation_log and best_idx < len(chain.mutation_log) else chain.best_sequence

                    cs = ChainState(
                        run_id=run_id,
                        chain_index=chain.chain_index,
                        step=chain.steps,
                        temperature=chain.temperature,
                        current_sequence=chain.final_sequence,
                        current_energy=chain.final_energy,
                        acceptance_rate=chain.acceptance_rate,
                        best_energy=chain.best_energy,
                        best_sequence=chain.best_sequence,
                    )
                    db.add(cs)

                    for mut in chain.mutation_log:
                        ms = MutationStep(
                            run_id=run_id,
                            chain_index=chain.chain_index,
                            step=mut["step"],
                            position=mut["position"] if isinstance(mut.get("position"), int) else 0,
                            from_aa=str(mut["from_aa"])[:1] if mut["from_aa"] else "X",
                            to_aa=str(mut["to_aa"])[:1] if mut["to_aa"] else "X",
                            mutation_type=mut.get("mutation_type", "unknown"),
                            energy_before=mut["energy_before"],
                            energy_after=mut["energy_after"],
                            delta_energy=mut["delta_energy"],
                            acceptance_probability=mut["acceptance_probability"],
                            accepted=mut["accepted"],
                            temperature=mut["temperature"],
                        )
                        db.add(ms)

                for cand in mcmc_result.candidates:
                    dc = DesignedCandidate(
                        run_id=run_id,
                        rank=cand.get("rank", 0),
                        sequence=cand.get("sequence", ""),
                        binding_score=cand.get("binding_score", 0.0),
                        stability_score=cand.get("stability_score", 0.0),
                        solubility_score=cand.get("solubility_score", 0.0),
                        hydrophobicity=cand.get("hydrophobicity"),
                        net_charge=cand.get("net_charge"),
                        aggregation_risk=cand.get("aggregation_risk"),
                        num_mutations_from_seed=sum(
                            1 for a, b in zip(
                                mcmc_result.seed_sequence,
                                cand.get("sequence", "")
                            ) if a != b
                        ) if mcmc_result.seed_sequence and cand.get("sequence") else 0,
                    )
                    db.add(dc)

                audit = AuditService(db)
                await audit.log(
                    user_id=run.user_id,
                    user_email=None,
                    action="mcmc_run_completed",
                    resource_type="mcmc_run",
                    resource_id=run_id_str,
                    parameters={"target_name": target_name, "config": config},
                    results_hash=run.results_hash,
                )

                await db.commit()

            await self.broadcast_progress(run_id_str, {
                "type": "complete",
                "run_id": run_id_str,
                "best_sequence": mcmc_result.best_overall_sequence,
                "best_energy": mcmc_result.best_overall_energy,
                "converged": mcmc_result.converged,
                "rhat": mcmc_result.rhat,
                "ess": mcmc_result.ess,
            })

        except Exception as e:
            logger.error(f"MCMC job {run_id_str} failed: {e}", exc_info=True)
            async with db_session_factory() as db:
                result = await db.execute(
                    select(MCMCRun).where(MCMCRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if run:
                    run.status = RunStatus.FAILED
                    run.error_message = str(e)
                    run.completed_at = datetime.utcnow()
                    await db.commit()

            await self.broadcast_progress(run_id_str, {
                "type": "error",
                "run_id": run_id_str,
                "message": str(e),
            })
        finally:
            if run_id_str in self.active_jobs:
                del self.active_jobs[run_id_str]
            if run_id_str in self.progress_callbacks:
                del self.progress_callbacks[run_id_str]


job_runner = MCMCJobRunner()
