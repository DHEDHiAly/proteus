"""Regression tests: conversational messages must not start a full MCMC cycle."""

import pytest

from app.schemas.agent import PatientInfo
from app.services.agent import ProteinDesignAgent, _is_design_request, _is_question


@pytest.fixture
def egfr_patient() -> PatientInfo:
    return PatientInfo(
        full_name="Demo",
        age=55,
        cancer_type="EGFRvIII",
        cancer_stage="IV",
        tumor_markers="EGFRvIII",
        previous_treatments="",
        brain_metastasis=False,
        notes="",
        modality="",
    )


def _has_mcmc_rounds(messages):
    return any(
        getattr(m, "data", None)
        and m.data.get("status") in ("round_complete", "complete", "running")
        for m in messages
    )


class TestAgentConversationVsMcmc:
    @pytest.mark.parametrize(
        "msg",
        [
            "how does this treatment work?",
            "how does this treatment work",
            "How does treatment work？",
            "what is the treatment",
            "how does it work",
        ],
    )
    def test_clinical_questions_do_not_run_mcmc(self, egfr_patient, msg: str):
        agent = ProteinDesignAgent()
        out = agent.run(egfr_patient, msg)
        assert not _has_mcmc_rounds(out.messages), f"MCMC leaked for message: {msg!r}"
        assert any(m.role == "agent" and m.content for m in out.messages)

    def test_explicit_design_still_runs_mcmc(self, egfr_patient):
        agent = ProteinDesignAgent()
        out = agent.run(egfr_patient, "design a peptide")
        assert _has_mcmc_rounds(out.messages)

    def test_how_do_i_design_prefers_mcmc(self, egfr_patient):
        """Design intent must override interrogative wording."""
        assert _is_design_request("how do I design a peptide for EGFR?")
        agent = ProteinDesignAgent()
        out = agent.run(egfr_patient, "how do I design a peptide for EGFR?")
        assert _has_mcmc_rounds(out.messages)


class TestQuestionHeuristics:
    def test_unicode_question_mark(self):
        assert _is_question("does binding improve？？")  # fullwidth at end

    def test_how_without_trailing_mark(self):
        assert _is_question("how does binding change over rounds")
