"""Dashboard aggregate schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.repository import RepositoryOut


class AuditEventOut(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None
    created_at: datetime


class AgentActivityOut(BaseModel):
    id: str
    agent_name: str
    status: str
    execution_time: float | None
    started_at: datetime | None
    investigation_id: str


class DashboardStats(BaseModel):
    repository_count: int
    indexed_file_count: int
    symbol_count: int
    active_job_count: int
    open_investigation_count: int
    completed_investigation_count: int
    report_count: int
    risk_distribution: dict[str, int]
    repositories: list[RepositoryOut]
    recent_activity: list[AuditEventOut]
    agent_activity: list[AgentActivityOut]
    ai_configured: bool
    ai_provider: str
