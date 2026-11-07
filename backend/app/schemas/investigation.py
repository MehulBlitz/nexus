"""Investigation, agent and report schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class InvestigationCreate(BaseModel):
    question: str = Field(min_length=8, max_length=2000)
    scope_path: str | None = Field(default=None, max_length=500)


class AgentRunOut(ORMModel):
    id: str
    agent_name: str
    status: str
    output_json: dict[str, Any] | None
    execution_time: float | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class InvestigationOut(ORMModel):
    id: str
    repository_id: str
    job_id: str | None = None
    question: str
    scope_path: str | None
    status: str
    progress: int
    summary: str | None
    ai_used: bool
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class InvestigationDetail(InvestigationOut):
    result: dict[str, Any] | None = None
    agent_runs: list[AgentRunOut] = Field(default_factory=list)


class InvestigationEvent(BaseModel):
    sequence: int
    event: str
    at: datetime
    data: dict[str, Any]


class AgentDefinition(BaseModel):
    name: str
    title: str
    responsibility: str
    uses_llm_when_available: bool
    output_schema: str


class AgentRunGlobal(AgentRunOut):
    investigation_id: str
    question: str | None = None
    repository_id: str


class ReportCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    investigation_id: str | None = None


class ReportOut(ORMModel):
    id: str
    repository_id: str
    title: str
    snapshot_id: str | None
    created_at: datetime


class ReportDetail(ReportOut):
    markdown: str
