from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.agent import PatientInfo, AgentRunRequest, AgentRunResponse
from app.services.agent import ProteinDesignAgent
from app.services.audit import AuditService

router = APIRouter(prefix="/agent", tags=["Agent"])
agent = ProteinDesignAgent()


@router.post("/greet")
async def greet(current_user: User = Depends(get_current_user)):
    reply = (
        "I am Proteus, your autonomous protein design agent.\n\n"
        "I work in iterative cycles:\n"
        "1. **Research** — Analyze target protein structure and literature\n"
        "2. **Generate** — Run MCMC to produce candidate sequences\n"
        "3. **Fold** — Predict 3D structure of candidates\n"
        "4. **Evaluate** — Score binding, stability, solubility\n"
        "5. **Iterate** — Use best candidate as seed for next round\n\n"
        "Enter a message to begin."
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
        result = agent.run(request.patient, request.message)
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
