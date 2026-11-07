"""Structured, validated contracts for every agent.

An agent output that does not validate is rejected; it is never displayed or stored as if it
were a real result. Unknown fields are rejected so a model cannot smuggle in uninspected data.
Evidence references always name a repository file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Origin = Literal["measured", "inferred", "ai_suggested"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictModel):
    file: str = Field(min_length=1, max_length=1000)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, max_length=500)
    origin: Origin = "measured"

    @field_validator("end_line")
    @classmethod
    def _end_after_start(cls, value: int | None, info):
        start = info.data.get("start_line")
        if value is not None and start is not None and value < start:
            raise ValueError("end_line must be greater than or equal to start_line")
        return value


class Hypothesis(StrictModel):
    title: str = Field(min_length=3, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=4000)
    evidence: list[EvidenceRef] = Field(min_length=1)
    origin: Origin = "inferred"
    suggested_check: str | None = Field(default=None, max_length=500)


class InvestigationResult(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    ai_used: bool = False


class MapperResult(StrictModel):
    overview: str
    architecture_summary: str
    languages: dict[str, int] = Field(default_factory=dict)
    frameworks_detected: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    important_files: list[EvidenceRef] = Field(default_factory=list)
    dependency_observations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RiskFindingRef(StrictModel):
    finding_id: str
    title: str
    severity: Literal["low", "moderate", "high", "critical"]
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    file: str | None = None
    why_it_matters: str


class RiskAnalystResult(StrictModel):
    summary: str
    overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    findings: list[RiskFindingRef] = Field(default_factory=list)
    signals_available: list[str] = Field(default_factory=list)
    signals_unavailable: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ArchitectureObservation(StrictModel):
    title: str
    detail: str
    severity: Literal["info", "low", "moderate", "high"]
    evidence: list[EvidenceRef] = Field(default_factory=list)
    origin: Origin = "measured"


class ArchitectureReviewResult(StrictModel):
    summary: str
    observations: list[ArchitectureObservation] = Field(default_factory=list)
    cycle_count: int = 0
    high_centrality: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PlanItem(StrictModel):
    priority: Literal["P0", "P1", "P2", "P3"]
    problem: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    suggested_fix: str
    related_files: list[str] = Field(default_factory=list)
    suggested_tests: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    complexity: Literal["small", "medium", "large"] = "medium"
    requires_human_approval: bool = True


class PlannerResult(StrictModel):
    theme: str
    items: list[PlanItem] = Field(default_factory=list)
    deduplicated_recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
