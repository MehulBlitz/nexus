"""Agent contracts reject invalid output and cannot cite non-existent evidence."""

import pytest
from pydantic import ValidationError

from app.agents.schemas import (
    EvidenceRef,
    Hypothesis,
    InvestigationResult,
    MapperResult,
    PlanItem,
    RiskFindingRef,
)


def test_hypothesis_requires_evidence():
    with pytest.raises(ValidationError):
        Hypothesis(title="Maybe this", confidence=0.4, reasoning="Because", evidence=[])


def test_confidence_must_be_between_zero_and_one():
    for value in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            Hypothesis(
                title="Maybe this",
                confidence=value,
                reasoning="Because",
                evidence=[EvidenceRef(file="a.py")],
            )


def test_evidence_end_line_must_follow_start_line():
    with pytest.raises(ValidationError):
        EvidenceRef(file="a.py", start_line=10, end_line=5)


def test_evidence_file_is_required():
    with pytest.raises(ValidationError):
        EvidenceRef(file="")


def test_investigation_output_rejects_wrong_types():
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(
            {
                "summary": "x",
                "hypotheses": [
                    {
                        "title": "bad",
                        "confidence": "high",
                        "reasoning": "y",
                        "evidence": [{"file": "a.py"}],
                    }
                ],
            }
        )


def test_mapper_output_cannot_contain_unknown_fields():
    with pytest.raises(ValidationError):
        MapperResult.model_validate(
            {"overview": "x", "architecture_summary": "y", "unexpected": True}
        )


def test_plan_items_require_human_approval_default():
    item = PlanItem(
        priority="P1",
        problem="Change auth",
        suggested_fix="Do it",
    )
    assert item.requires_human_approval is True
    assert item.complexity == "medium"


def test_risk_finding_score_is_bounded():
    with pytest.raises(ValidationError):
        RiskFindingRef(
            finding_id="1",
            title="x",
            severity="high",
            score=120,
            confidence=0.5,
            why_it_matters="y",
        )
