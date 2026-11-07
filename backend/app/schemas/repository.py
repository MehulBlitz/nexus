"""Repository, snapshot and GitHub activity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RepositoryImportRequest(BaseModel):
    url: str = Field(min_length=10, max_length=500, examples=["https://github.com/owner/repository"])
    branch: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=200)


class RepositoryOut(ORMModel):
    id: str
    provider: str
    external_repository_id: str
    name: str
    full_name: str
    html_url: str
    description: str | None
    default_branch: str
    visibility: str
    status: str
    language: str | None
    stars: int
    size_kb: int
    last_indexed_at: datetime | None
    last_error: str | None
    created_at: datetime


class SnapshotOut(ORMModel):
    id: str
    commit_sha: str
    branch: str
    indexing_status: str
    file_count: int
    symbol_count: int
    edge_count: int
    languages: dict[str, Any] | None
    warnings: list[str] | None
    coverage: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None


class RepositoryDetail(RepositoryOut):
    latest_snapshot: SnapshotOut | None = None
    active_job: JobOut | None = None


class RepositoryStatus(BaseModel):
    repository_id: str
    status: str
    active_job: JobOut | None = None
    latest_snapshot: SnapshotOut | None = None
    last_error: str | None = None


class JobOut(ORMModel):
    id: str
    job_type: str
    status: str
    progress: int
    repository_id: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class LanguageStat(BaseModel):
    language: str
    files: int
    symbols: int
    percent: float


class RepositoryOverview(BaseModel):
    repository: RepositoryOut
    snapshot: SnapshotOut | None
    languages: list[LanguageStat]
    file_count: int
    symbol_count: int
    module_count: int
    test_file_count: int
    top_modules: list[dict[str, Any]]
    directories: list[dict[str, Any]]
    entry_points: list[str]
    parser_coverage: dict[str, Any]
    warnings: list[str]


class FileEntry(BaseModel):
    path: str
    language: str
    node_id: str
    line_count: int | None
    symbols: int
    imports: int


class SymbolEntry(BaseModel):
    id: str
    name: str
    qualified_name: str | None
    node_type: str
    file_path: str | None
    start_line: int | None
    end_line: int | None
    language: str | None


class CodeSearchHit(BaseModel):
    path: str
    language: str
    line: int
    match_type: Literal["path", "symbol", "content"]
    snippet: str
    symbol: str | None = None


class CommitItem(BaseModel):
    sha: str
    short_sha: str
    message: str
    author: str | None
    authored_at: datetime | None
    url: str


class PullRequestItem(BaseModel):
    number: int
    title: str
    state: str
    user: str | None
    created_at: datetime | None
    updated_at: datetime | None
    url: str
    draft: bool = False


class IssueItem(BaseModel):
    number: int
    title: str
    state: str
    user: str | None
    labels: list[str]
    created_at: datetime | None
    url: str


class WorkflowRunItem(BaseModel):
    id: int
    name: str | None
    status: str | None
    conclusion: str | None
    branch: str | None
    created_at: datetime | None
    url: str


class ActivitySection(BaseModel):
    available: bool
    reason: str | None = None
    fetched_at: datetime | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)


class RepositoryActivity(BaseModel):
    repository_id: str
    full_name: str
    commits: ActivitySection
    pull_requests: ActivitySection
    issues: ActivitySection
    workflows: ActivitySection
    summary: str


RepositoryDetail.model_rebuild()
RepositoryStatus.model_rebuild()
