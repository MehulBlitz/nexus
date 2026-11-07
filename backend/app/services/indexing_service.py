"""Repository indexing: fetch, filter, parse, build the graph and persist a snapshot.

Nothing from the repository is executed. Source is parsed as text, and only a snapshot's
derived metadata is stored; file contents are fetched again on demand for evidence search.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.analyzers.base import ParsedFile
from app.analyzers.registry import parse_file
from app.core.config import Settings
from app.core.database import utcnow
from app.core.errors import NotFoundError, UpstreamError
from app.graph.builder import build_graph, persist_graph
from app.ingestion.file_filter import SkippedFile, is_test_path, select_files
from app.integrations.github import GitHubClient, GitHubRepoRef
from app.models.repository import Repository, RepositorySnapshot
from app.repositories import repos as repos_repo
from app.services.github_service import build_client

logger = logging.getLogger("nexus.indexing")

ProgressFn = Callable[[int, str], None]


@dataclass
class IndexOutcome:
    snapshot_id: str
    file_count: int
    symbol_count: int
    edge_count: int
    languages: dict[str, int]
    parse_modes: dict[str, int]
    warnings: list[str] = field(default_factory=list)
    fetch_failures: int = 0
    truncated: bool = False


def _split_full_name(full_name: str) -> GitHubRepoRef:
    parts = full_name.split("/")
    if len(parts) != 2:
        raise UpstreamError("Stored repository name is invalid")
    return GitHubRepoRef(owner=parts[0], repo=parts[1])


def _analysis_summary(parsed: list[ParsedFile], skipped: list[SkippedFile]) -> dict:
    languages = Counter(p.language for p in parsed)
    modes = Counter(p.parse_mode for p in parsed)
    return {
        "languages": dict(sorted(languages.items())),
        "parse_modes": dict(sorted(modes.items())),
        "skipped_reasons": dict(Counter(s.reason for s in skipped)),
    }


def index_repository(
    session: Session,
    repository: Repository,
    *,
    settings: Settings,
    client: GitHubClient | None = None,
    progress: ProgressFn | None = None,
) -> IndexOutcome:
    report = progress or (lambda _p, _m: None)
    ref = _split_full_name(repository.full_name)
    owns_client = client is None
    github = client or build_client(settings)
    repository.status = "indexing"
    session.flush()
    try:
        report(5, "Fetching repository metadata")
        logger.info(
            "indexing %s: resolving branch %s", repository.full_name, repository.default_branch
        )
        branch_info = github.get_branch(ref, repository.default_branch)
        logger.info("indexing %s: branch resolved", repository.full_name)
        commit_sha = (branch_info.get("commit") or {}).get("sha")
        if not commit_sha:
            raise UpstreamError("Could not resolve the latest commit for this branch")
        snapshot = repos_repo.create_snapshot(
            session,
            repository_id=repository.id,
            commit_sha=commit_sha,
            branch=repository.default_branch,
        )
        snapshot.indexing_status = "indexing"
        session.flush()

        report(15, "Listing repository files")
        logger.info("indexing %s: listing tree", repository.full_name)
        tree = github.get_tree(ref, commit_sha)
        logger.info(
            "indexing %s: tree listed (%s entries)", repository.full_name, tree.total_entries
        )
        selected, skipped, truncated = select_files(
            tree.files,
            max_files=settings.max_index_files,
            max_file_bytes=settings.max_file_bytes,
        )
        warnings: list[str] = []
        if tree.truncated:
            warnings.append(
                "GitHub truncated the repository tree; files beyond its limit were not listed."
            )
        if truncated:
            warnings.append(
                f"Indexing stopped at the configured limit of {settings.max_index_files} files."
            )

        report(30, f"Fetching {len(selected)} source files")
        contents: dict[str, str] = {}
        fetch_failures = 0
        total_bytes = 0
        with ThreadPoolExecutor(max_workers=max(1, settings.index_fetch_concurrency)) as pool:
            futures = {
                pool.submit(
                    github.fetch_file, ref, commit_sha, item.path, max_bytes=settings.max_file_bytes
                ): item
                for item in selected
            }
            for index, future in enumerate(as_completed(futures), start=1):
                item = futures[future]
                try:
                    text = future.result()
                except Exception as exc:  # noqa: BLE001 - one file must not fail the index
                    text = None
                    logger.warning("file fetch failed for %s: %s", item.path, type(exc).__name__)
                if text is None:
                    fetch_failures += 1
                    warnings.append(f"Could not fetch or decode: {item.path}")
                    continue
                if total_bytes + len(text.encode("utf-8")) > settings.max_total_bytes:
                    warnings.append("Total repository byte limit reached; remaining files skipped.")
                    break
                total_bytes += len(text.encode("utf-8"))
                contents[item.path] = text
                if index % 25 == 0:
                    report(30 + int(30 * index / max(1, len(selected))), "Fetching source files")

        report(65, "Parsing source files")
        parsed_files: list[ParsedFile] = []
        for path, text in contents.items():
            language = next((s.language for s in selected if s.path == path), "Unknown")
            parsed = parse_file(
                path, text, language, max_symbols=settings.max_symbols_per_file
            )
            parsed_files.append(parsed)
            for warning in parsed.warnings[:3]:
                warnings.append(f"{path}: {warning}")

        report(80, "Building the knowledge graph")
        node_specs, edge_specs = build_graph(parsed_files)
        node_count, edge_count = persist_graph(session, snapshot.id, node_specs, edge_specs)

        summary = _analysis_summary(parsed_files, skipped)
        symbol_count = sum(len(p.symbols) for p in parsed_files)
        test_files = sum(1 for p in parsed_files if is_test_path(p.path))
        snapshot.indexing_status = "completed"
        snapshot.file_count = len(parsed_files)
        snapshot.symbol_count = symbol_count
        snapshot.edge_count = edge_count
        snapshot.languages = summary["languages"]
        snapshot.warnings = warnings[:100]
        snapshot.coverage = {
            "parse_modes": summary["parse_modes"],
            "skipped_reasons": summary["skipped_reasons"],
            "test_files": test_files,
            "fetched_files": len(contents),
            "fetch_failures": fetch_failures,
            "tree_files": tree.total_entries,
            "tree_truncated": tree.truncated,
            "total_bytes": total_bytes,
            "analyzer_note": (
                "Python uses the standard AST. JavaScript, TypeScript and Java use a lexer "
                "that extracts declarations and imports reliably; call edges and end lines are "
                "inferred with lower confidence."
            ),
        }
        snapshot.completed_at = utcnow()
        repository.status = "indexed"
        repository.last_indexed_at = utcnow()
        repository.last_error = None
        if summary["languages"]:
            repository.language = max(summary["languages"].items(), key=lambda kv: kv[1])[0]
        session.flush()
        report(100, "Indexing complete")
        return IndexOutcome(
            snapshot_id=snapshot.id,
            file_count=len(parsed_files),
            symbol_count=symbol_count,
            edge_count=edge_count,
            languages=summary["languages"],
            parse_modes=summary["parse_modes"],
            warnings=warnings[:100],
            fetch_failures=fetch_failures,
            truncated=truncated,
        )
    except (UpstreamError, NotFoundError) as exc:
        repository.status = "failed"
        repository.last_error = exc.message
        session.flush()
        raise
    except Exception as exc:  # noqa: BLE001 - record and re-raise for the job to fail cleanly
        repository.status = "failed"
        repository.last_error = f"Indexing failed: {type(exc).__name__}"
        session.flush()
        logger.exception("indexing failed")
        raise
    finally:
        if owns_client:
            github.close()


def fail_snapshot(session: Session, snapshot: RepositorySnapshot, message: str) -> None:
    snapshot.indexing_status = "failed"
    snapshot.error_message = message[:2000]
    snapshot.completed_at = utcnow()
    session.flush()
