from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
import logging

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.agent import PatientInfo, AgentRunRequest, AgentRunResponse
from app.services.agent import ProteinDesignAgent
from app.services.audit import AuditService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])
agent = ProteinDesignAgent()


@router.post("/greet")
async def greet(current_user: User = Depends(get_current_user)):
    reply = (
        "I am Proteus, your autonomous protein design agent.\n\n"
        "I run iterative MCMC design cycles across parallel temperature chains, "
        "scoring each candidate on eight biophysical objectives:\n"
        "- Binding affinity, stability, solubility\n"
        "- pLDDT estimate, ΔΔG (kcal/mol), aggregation propensity\n"
        "- Immunogenicity score, manufacturability\n\n"
        "I recognize design constraints in your message. For example:\n"
        "- *no cysteines*, *high solubility*, *low aggregation*\n"
        "- *thermostable*, *alpha-helical*, *60 amino acids*\n"
        "- *BBB-penetrant*, *low immunogenicity*, *antimicrobial*\n\n"
        "I will also flag physically impossible requests — for example, "
        "a protein that is simultaneously highly hydrophobic and highly soluble, "
        "or one with infinite thermal stability — and explain why, then suggest "
        "a realizable alternative.\n\n"
        "After each round I show the full mutation rationale: which residues "
        "changed, their chemical property class shift, BLOSUM62 conservation score, "
        "and the energy delta that drove acceptance.\n\n"
        "Enter your clinical information in the form to begin."
    )
    return {"reply": reply}


@router.post("/design", response_model=AgentRunResponse)
async def design(
    request: AgentRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    audit = AuditService(db)
    target_name = agent._resolve_target(request.patient)
    await audit.log(
        user_id=current_user.id,
        user_email=current_user.email,
        action="agent_design_requested",
        resource_type="agent_design",
        parameters={
            "cancer_type": request.patient.cancer_type,
            "cancer_stage": request.patient.cancer_stage,
            "tumor_markers": request.patient.tumor_markers,
            "resolved_target": target_name,
        },
    )

    try:
        result = agent.run(request.patient, request.message, request.session)
        await audit.log(
            user_id=current_user.id,
            user_email=current_user.email,
            action="agent_design_completed",
            resource_type="agent_design",
            resource_id=result.run_id,
            parameters={"target": target_name, "sequence": result.candidate_sequence},
        )
        return result
    except Exception as e:
        await audit.log(
            user_id=current_user.id,
            user_email=current_user.email,
            action="agent_design_failed",
            resource_type="agent_design",
            success="false",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/design/stream")
async def design_stream(
    request: AgentRunRequest,
    current_user: User = Depends(get_current_user),
):
    """Server-Sent Events (SSE) endpoint for streaming MCMC progress.

    Emits `data: <json>\\n\\n` lines as MCMC runs:
    - `{"type": "progress", "chain_index": N, "step": N, "best_energy": F, ...}`
    - `{"type": "epoch_complete", "epoch": N, "num_epochs": N, "best_energy": F}`
    - `{"type": "round_complete", "round": N, "sequence": "...", "scores": {...}}`
    - `{"type": "complete", "result": {...}}` — full AgentRunResponse payload
    - `{"type": "error", "detail": "..."}` — on exception

    The frontend consumes this with:
        const es = new EventSource('/api/agent/design/stream');
        es.onmessage = (e) => { const ev = JSON.parse(e.data); ... };
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _progress_callback(event: dict) -> None:
        """Called from the sync MCMC thread; schedules a put into the async queue."""
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)

    async def _run_agent_in_executor() -> None:
        """Run the blocking agent.run() in a thread pool, feeding the queue."""
        try:
            # Inject the progress callback into the singleton agent temporarily.
            # We patch the MCMC sampler's progress_callback at call time via a
            # thin wrapper on agent.run() that sets it before calling _run_mcmc_round.
            result = await loop.run_in_executor(
                None,
                lambda: agent.run(
                    request.patient,
                    request.message,
                    request.session,
                    stream_callback=_progress_callback,
                ),
            )
            # Emit the full result as the terminal event
            await queue.put({
                "type": "complete",
                "result": result.dict(),
            })
        except Exception as exc:
            logger.exception("Streaming design run failed")
            await queue.put({"type": "error", "detail": str(exc)})
        finally:
            await queue.put(None)  # sentinel: generator stops

    async def _event_generator():
        asyncio.create_task(_run_agent_in_executor())
        while True:
            event = await queue.get()
            if event is None:
                break
            yield "data: {}\n\n".format(json.dumps(event))

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
