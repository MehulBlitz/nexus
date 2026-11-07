"""Repository Mapper: structure, entry points, frameworks and dependency shape."""

from __future__ import annotations

import posixpath
from collections import Counter

from app.agents.base import Agent
from app.agents.context import AgentContext
from app.agents.schemas import EvidenceRef, MapperResult

ENTRY_POINT_NAMES = {
    "main.py",
    "__main__.py",
    "app.py",
    "manage.py",
    "index.js",
    "index.ts",
    "main.ts",
    "main.tsx",
    "main.jsx",
    "App.tsx",
    "App.jsx",
    "server.js",
    "server.ts",
    "Main.java",
}

FRAMEWORK_HINTS = {
    "react": "React",
    "next": "Next.js",
    "vue": "Vue",
    "express": "Express",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic",
    "spring": "Spring",
    "junit": "JUnit",
    "jest": "Jest",
    "vitest": "Vitest",
    "pytest": "Pytest",
    "axios": "Axios",
}


class RepositoryMapper(Agent):
    name = "repository_mapper"
    title = "Repository Mapper"
    responsibility = (
        "Summarises repository structure, languages, entry points, frameworks and the shape "
        "of the dependency graph using indexed nodes and edges."
    )
    output_model = MapperResult

    def run(self, context: AgentContext) -> MapperResult:
        files = context.file_nodes()
        snapshot = context.snapshot
        limitations: list[str] = []
        if not snapshot:
            return MapperResult(
                overview="This repository has not been indexed yet.",
                architecture_summary="No snapshot is available.",
                limitations=["No indexed snapshot."],
            )

        languages = Counter(node.language or "Unknown" for node in files)
        directories = Counter(
            posixpath.dirname(node.file_path or "") or "." for node in files
        )
        top_directories = ", ".join(
            f"{name}/ ({count})" for name, count in directories.most_common(6) if name != "."
        )
        entry_points = sorted(
            node.file_path
            for node in files
            if node.file_path and posixpath.basename(node.file_path) in ENTRY_POINT_NAMES
        )[:10]
        if not entry_points:
            limitations.append(
                "No conventional entry point filename was found; entry points may be defined "
                "by project configuration that NEXUS does not parse yet."
            )

        external_modules = [
            node.name
            for node in context.view.nodes.values()
            if node.node_type == "module" and (node.metadata_json or {}).get("external")
        ]
        frameworks = sorted(
            {
                label
                for module in external_modules
                for hint, label in FRAMEWORK_HINTS.items()
                if module.lower().split(".")[0].split("/")[0] == hint
            }
        )
        if not frameworks:
            limitations.append("No frameworks were detected from indexed import statements.")

        degree = dict(context.view.graph.in_degree())
        ranked = sorted(
            (node for node in files if node.file_path),
            key=lambda node: degree.get(node.id, 0),
            reverse=True,
        )
        important_files = [
            EvidenceRef(
                file=node.file_path or "",
                start_line=1,
                end_line=max(1, int((node.metadata_json or {}).get("line_count") or 1)),
                note=f"{degree.get(node.id, 0)} incoming dependency edge(s)",
            )
            for node in ranked[:8]
        ]

        modules = sum(1 for node in context.view.nodes.values() if node.node_type == "module")
        tests = sum(1 for node in files if node.node_type == "test")
        observations = [
            f"{len(files)} indexed source file(s) across {len(directories)} director(ies).",
            f"{modules} module node(s) appear as imports; {len(external_modules)} are external "
            "or unresolved packages.",
            f"{tests} test file(s) detected by path convention.",
        ]
        parse_modes = context.parser_coverage().get("parse_modes", {})
        if parse_modes:
            observations.append(
                "Parser coverage: "
                + ", ".join(f"{mode}={count}" for mode, count in sorted(parse_modes.items()))
                + "."
            )
        overview = (
            f"{context.repository.full_name} at {snapshot.commit_sha[:7]} ({snapshot.branch}) "
            f"contains {len(files)} indexed source file(s). Languages: "
            + (", ".join(f"{language} ({count})" for language, count in languages.most_common()))
            + "."
        )
        layout = top_directories or "the repository root"
        architecture = (
            f"The repository is organised mainly under: {layout}. "
            "Files with the most incoming dependencies are listed as important files; they are "
            "the natural starting points for understanding impact."
        )
        return MapperResult(
            overview=overview,
            architecture_summary=architecture,
            languages=dict(languages),
            frameworks_detected=frameworks,
            entry_points=entry_points,
            important_files=important_files,
            dependency_observations=observations,
            limitations=limitations,
        )
