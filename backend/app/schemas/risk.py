"""Risk analysis schemas. Scores are heuristics, never failure probabilities."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

Severity = Literal["low", "moderate", "high", "critical"]


class RiskSignal(BaseModel):
    name: str
    weight: float
    value: float | None
    normalized: float | None
    available: bool
    explanation: str


class RiskFindingOut(ORMModel):
    id: str
    analysis_run_id: str
    repository_id: str
    snapshot_id: str | None
    finding_type: str
    severity: str
    title: str
    description: str
    risk_score: float
    confidence: float
    origin: str
    file_path: str | None
    evidence_json: dict[str, Any] | None
    recommendations_json: list[str] | None
    created_at: datetime


class RiskSummary(BaseModel):
    repository_id: str
    snapshot_id: str | None
    analysis_run_id: str | None
    overall_score: float | None
    overall_severity: str | None
    analyzed_at: datetime | None
    module_count: int
    severity_counts: dict[str, int]
    signals_available: list[str]
    signals_unavailable: list[str]
    weights: dict[str, float]
    classified_modules: list[dict[str, Any]]
    confidence: float
    limitations: list[str]


class RiskAnalyzeRequest(BaseModel):
    include_github_history: bool = True
    max_findings: int = Field(default=25, ge=1, le=100)


class RiskFindingDetail(RiskFindingOut):
    signals: list[RiskSignal] = Field(default_factory=list)
