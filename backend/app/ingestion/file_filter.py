"""Decide which repository files are safe and useful to index."""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.github import GitHubFile

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
}

SKIP_DIRECTORIES = {
    ".git",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "out",
    ".next",
    "coverage",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".gradle",
    "target",
    "site-packages",
}

# Files whose names clearly mark tests regardless of directory.
TEST_HINTS = ("test_", "_test.", ".test.", ".spec.", "tests/", "test/", "__tests__/")


@dataclass(frozen=True)
class SelectedFile:
    path: str
    sha: str
    language: str
    size: int


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str


def language_for(path: str) -> str | None:
    lower = path.lower()
    for extension, language in LANGUAGE_BY_EXTENSION.items():
        if lower.endswith(extension):
            return language
    return None


def is_test_path(path: str) -> bool:
    lowered = f"/{path.lower()}"
    return any(hint in lowered for hint in TEST_HINTS)


def _skip_reason(path: str, size: int, max_file_bytes: int) -> str | None:
    segments = path.lower().split("/")
    if any(segment in SKIP_DIRECTORIES for segment in segments[:-1]):
        return "excluded directory"
    if language_for(path) is None:
        return "unsupported language"
    if size <= 0:
        return "empty file"
    if size > max_file_bytes:
        return "file exceeds size limit"
    return None


def select_files(
    files: list[GitHubFile], *, max_files: int, max_file_bytes: int
) -> tuple[list[SelectedFile], list[SkippedFile], bool]:
    """Filter tree entries deterministically.

    Returns (selected, skipped, truncated). ``truncated`` is True when the per-repository file
    cap prevented indexing files that would otherwise qualify.
    """
    selected: list[SelectedFile] = []
    skipped: list[SkippedFile] = []
    truncated = False
    for entry in sorted(files, key=lambda f: f.path):
        language = language_for(entry.path)
        reason = _skip_reason(entry.path, entry.size, max_file_bytes)
        if reason:
            # Unsupported-language noise is summarised, not listed one by one.
            if reason != "unsupported language":
                skipped.append(SkippedFile(entry.path, reason))
            continue
        if len(selected) >= max_files:
            truncated = True
            skipped.append(SkippedFile(entry.path, "repository file limit reached"))
            break
        selected.append(
            SelectedFile(
                path=entry.path, sha=entry.sha, language=language or "Unknown", size=entry.size
            )
        )
    return selected, skipped, truncated
