"""Repository import, listing, indexing, overview and code intelligence endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_db, owned_repository, require_csrf
from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError
from app.graph.engine import build_view, connected_components, find_cycles, top_central
from app.ingestion.file_filter import is_test_path
from app.models.repository import Repository, RepositorySnapshot
from app.models.user import User
from app.repositories import code as code_repo
from app.repositories import jobs as jobs_repo
from app.repositories import repos as repos_repo
from app.schemas.common import Page
from app.schemas.repository import (
    ActivitySection,
    CodeSearchHit,
    FileEntry,
    JobOut,
    RepositoryActivity,
    RepositoryDetail,
    RepositoryImportRequest,
    RepositoryOut,
    RepositoryOverview,
    RepositoryStatus,
    SnapshotOut,
    SymbolEntry,
)
from app.services import github_service, job_service
from app.services.repository_service import latest_snapshot_or_none
from app.services.search_service import search_code

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _detail(
    session: Session, repository: Repository, settings: Settings | None = None
) -> RepositoryDetail:
    snapshot = latest_snapshot_or_none(session, repository.id)
    active = jobs_repo.active_job_for(session, repository.id)
    data = RepositoryOut.model_validate(repository).model_dump()
    return RepositoryDetail(
        **data,
        latest_snapshot=SnapshotOut.model_validate(snapshot) if snapshot else None,
        active_job=JobOut.model_validate(active) if active else None,
    )


def _require_snapshot(session: Session, repository: Repository) -> RepositorySnapshot:
    snapshot = latest_snapshot_or_none(session, repository.id)
    if snapshot is None:
        raise NotFoundError("This repository has not been indexed yet")
    return snapshot


@router.post("", response_model=RepositoryDetail, status_code=201)
def import_repository(
    body: RepositoryImportRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
    csrf=Depends(require_csrf),
) -> RepositoryDetail:
    client = github_service.build_client(settings)
    try:
        repository, created = github_service.import_repository(
            db,
            owner_id=user.id,
            url=body.url,
            branch=body.branch,
            display_name=body.display_name,
            settings=settings,
            client=client,
        )
    finally:
        client.close()
    db.commit()
    if created:
        job_service.enqueue(
            db,
            job_type="index_repository",
            repository_id=repository.id,
            user_id=user.id,
            dedupe_key=f"index:{repository.id}:{repository.default_branch}",
        )
        jobs_repo.audit(
            db,
            user_id=user.id,
            action="repository.imported",
            resource_type="repository",
            resource_id=repository.id,
            metadata={"full_name": repository.full_name},
        )
        db.commit()
    else:
        response.status_code = 200
    return _detail(db, repository)


@router.get("", response_model=Page[RepositoryOut])
def list_repositories(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Page[RepositoryOut]:
    items, total = repos_repo.list_owned(db, user.id, limit=limit, offset=offset)
    return Page[RepositoryOut](
        items=[RepositoryOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{repository_id}", response_model=RepositoryDetail)
def get_repository(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> RepositoryDetail:
    return _detail(db, repository)


@router.delete("/{repository_id}", status_code=204)
def delete_repository(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    csrf=Depends(require_csrf),
) -> Response:
    jobs_repo.audit(
        db,
        user_id=user.id,
        action="repository.deleted",
        resource_type="repository",
        resource_id=repository.id,
        metadata={"full_name": repository.full_name},
    )
    repos_repo.delete_repository(db, repository)
    db.commit()
    return Response(status_code=204)


@router.post("/{repository_id}/index", response_model=JobOut, status_code=202)
def index_repository(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    csrf=Depends(require_csrf),
) -> JobOut:
    if repository.status == "indexing":
        raise ConflictError("Repository indexing is already running")
    job = job_service.enqueue(
        db,
        job_type="index_repository",
        repository_id=repository.id,
        user_id=user.id,
        dedupe_key=f"index:{repository.id}:{repository.default_branch}",
    )
    jobs_repo.audit(
        db,
        user_id=user.id,
        action="repository.reindex_requested",
        resource_type="repository",
        resource_id=repository.id,
    )
    db.commit()
    return JobOut.model_validate(job)


@router.get("/{repository_id}/status", response_model=RepositoryStatus)
def repository_status(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> RepositoryStatus:
    snapshot = latest_snapshot_or_none(db, repository.id)
    active = jobs_repo.active_job_for(db, repository.id)
    return RepositoryStatus(
        repository_id=repository.id,
        status=repository.status,
        active_job=JobOut.model_validate(active) if active else None,
        latest_snapshot=SnapshotOut.model_validate(snapshot) if snapshot else None,
        last_error=repository.last_error,
    )


@router.get("/{repository_id}/activity", response_model=RepositoryActivity)
def repository_activity(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepositoryActivity:
    sections = github_service.get_activity(db, repository, settings=settings)
    db.commit()
    defaults = {"commits": [], "pull_requests": [], "issues": [], "workflows": []}
    return RepositoryActivity(
        repository_id=repository.id,
        full_name=repository.full_name,
        commits=ActivitySection(**{**defaults, **sections.get("commits", {})}),
        pull_requests=ActivitySection(**{**defaults, **sections.get("pull_requests", {})}),
        issues=ActivitySection(**{**defaults, **sections.get("issues", {})}),
        workflows=ActivitySection(**{**defaults, **sections.get("workflows", {})}),
        summary=github_service.activity_summary(repository.full_name, sections),
    )


@router.get("/{repository_id}/overview", response_model=RepositoryOverview)
def repository_overview(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> RepositoryOverview:
    snapshot = latest_snapshot_or_none(db, repository.id)
    if snapshot is None:
        return RepositoryOverview(
            repository=RepositoryOut.model_validate(repository),
            snapshot=None,
            languages=[],
            file_count=0,
            symbol_count=0,
            module_count=0,
            test_file_count=0,
            top_modules=[],
            directories=[],
            entry_points=[],
            parser_coverage={},
            warnings=[],
        )
    nodes = code_repo.nodes_for_snapshot(db, snapshot.id)
    edges = code_repo.edges_for_snapshot(db, snapshot.id)
    view = build_view(nodes, edges)
    files = [n for n in nodes if n.node_type in {"file", "test"} and n.file_path]
    total_files = len(files) or 1
    languages = snapshot.languages or {}
    language_stats = [
        {
            "language": language,
            "files": count,
            "symbols": sum(
                1
                for node in nodes
                if node.node_type in {"function", "class"} and node.language == language
            ),
            "percent": round(100 * count / total_files, 2),
        }
        for language, count in sorted(languages.items(), key=lambda item: item[1], reverse=True)
    ]
    directories: dict[str, int] = {}
    for node in files:
        top = (node.file_path or "").split("/")[0] if "/" in (node.file_path or "") else "."
        directories[top] = directories.get(top, 0) + 1
    central = top_central(view, limit=8)
    entry_points = sorted(
        node.file_path
        for node in files
        if node.file_path
        and node.file_path.rsplit("/", 1)[-1]
        in {"main.py", "app.py", "index.ts", "index.js", "main.tsx", "App.tsx", "Main.java"}
    )[:10]
    return RepositoryOverview(
        repository=RepositoryOut.model_validate(repository),
        snapshot=SnapshotOut.model_validate(snapshot),
        languages=[
            {"language": item["language"], "files": item["files"], "symbols": item["symbols"],
             "percent": item["percent"]}
            for item in language_stats
        ],
        file_count=snapshot.file_count,
        symbol_count=snapshot.symbol_count,
        module_count=sum(1 for node in nodes if node.node_type == "module"),
        test_file_count=sum(1 for node in files if is_test_path(node.file_path or "")),
        top_modules=[
            {"path": path, "degree_centrality": round(degree, 3)}
            for path, degree, _between in central
        ],
        directories=[
            {"name": name, "files": count}
            for name, count in sorted(directories.items(), key=lambda kv: kv[1], reverse=True)
        ],
        entry_points=entry_points,
        parser_coverage=snapshot.coverage or {},
        warnings=snapshot.warnings or [],
    )


@router.get("/{repository_id}/files", response_model=Page[FileEntry])
def list_files(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[FileEntry]:
    snapshot = _require_snapshot(db, repository)
    nodes = code_repo.nodes_for_snapshot(db, snapshot.id, node_types=["file", "test"])
    symbol_counts: dict[str, int] = {}
    for node in code_repo.nodes_for_snapshot(
        db, snapshot.id, node_types=["function", "class"]
    ):
        if node.file_path:
            symbol_counts[node.file_path] = symbol_counts.get(node.file_path, 0) + 1
    entries = [
        FileEntry(
            path=node.file_path or "",
            language=node.language or "Unknown",
            node_id=node.id,
            line_count=(node.metadata_json or {}).get("line_count"),
            symbols=symbol_counts.get(node.file_path or "", 0),
            imports=int((node.metadata_json or {}).get("import_count") or 0),
        )
        for node in nodes
        if node.file_path
    ]
    total = len(entries)
    return Page[FileEntry](
        items=entries[offset : offset + limit], total=total, limit=limit, offset=offset
    )


@router.get("/{repository_id}/symbols", response_model=Page[SymbolEntry])
def list_symbols(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, max_length=100),
    language: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[SymbolEntry]:
    snapshot = _require_snapshot(db, repository)
    nodes = code_repo.nodes_for_snapshot(db, snapshot.id, node_types=["function", "class"])
    filtered = [
        node
        for node in nodes
        if (not q or q.lower() in (node.qualified_name or node.name).lower())
        and (not language or node.language == language)
    ]
    total = len(filtered)
    items = [
        SymbolEntry(
            id=node.id,
            name=node.name,
            qualified_name=node.qualified_name,
            node_type=node.node_type,
            file_path=node.file_path,
            start_line=node.start_line,
            end_line=node.end_line,
            language=node.language,
        )
        for node in filtered[offset : offset + limit]
    ]
    return Page[SymbolEntry](items=items, total=total, limit=limit, offset=offset)


@router.get("/{repository_id}/search", response_model=list[CodeSearchHit])
def search_repository(
    q: str = Query(min_length=2, max_length=200),
    language: str | None = Query(default=None, max_length=30),
    directory: str | None = Query(default=None, max_length=300),
    limit: int = Query(default=25, ge=1, le=100),
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[CodeSearchHit]:
    snapshot = latest_snapshot_or_none(db, repository.id)
    hits = search_code(
        db,
        repository,
        snapshot,
        q,
        settings=settings,
        language=language,
        directory=directory,
        limit=limit,
    )
    return [CodeSearchHit(**hit) for hit in hits]


@router.get("/{repository_id}/insights")
def repository_insights(
    repository: Repository = Depends(owned_repository),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate counts used by the repository overview page."""
    snapshot = latest_snapshot_or_none(db, repository.id)
    if snapshot is None:
        return {"indexed": False}
    nodes = code_repo.nodes_for_snapshot(db, snapshot.id)
    edges = code_repo.edges_for_snapshot(db, snapshot.id)
    view = build_view(nodes, edges)
    return {
        "indexed": True,
        "cycles": len(find_cycles(view, limit=20)),
        "components": connected_components(view),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "warnings": snapshot.warnings or [],
        "coverage": snapshot.coverage or {},
    }
