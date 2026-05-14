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
