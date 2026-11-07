"""Turn analyzer output into persisted graph nodes and evidence-backed edges.

Edge confidence and origin are explicit:
- parsed imports with a resolved repository target: origin "parsed", confidence 0.95-1.0
- imports of packages outside the repository: module node, origin "inferred", confidence 0.4
- CALLS edges resolved by unique symbol name: origin "inferred", confidence 0.45
- TESTS edges from a test file to the files it imports: origin "inferred", confidence 0.6
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field

from app.analyzers.base import ParsedFile
from app.ingestion.file_filter import is_test_path
from app.models.code import CodeNode, DependencyEdge


@dataclass
class NodeSpec:
    key: str
    node_type: str
    name: str
    qualified_name: str | None = None
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    language: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EdgeSpec:
    source_key: str
    target_key: str
    relationship_type: str
    confidence: float
    origin: str
    source_line: int | None = None
    detail: str | None = None
    evidence: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


JS_EXTENSIONS = (
    "",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    "/index.ts",
    "/index.tsx",
    "/index.js",
    "/index.jsx",
)
JAVA_ROOTS = ("src/main/java/", "src/test/java/", "src/")


def _directory_chain(path: str) -> list[str]:
    parts = path.split("/")[:-1]
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def build_graph(
    parsed_files: list[ParsedFile], *, max_edges: int = 20000
) -> tuple[list[NodeSpec], list[EdgeSpec]]:
    """Build the deterministic software graph for one snapshot."""
    nodes: list[NodeSpec] = []
    edges: list[EdgeSpec] = []
    module_index: dict[str, str] = {}
    file_keys: dict[str, str] = {}
    directory_keys: set[str] = set()
    python_symbols: dict[str, list[tuple[str, str]]] = {}
    all_symbol_keys: dict[str, list[tuple[str, str]]] = {}

    def add_directory(path: str) -> str:
        key = f"dir:{path}"
        if key not in directory_keys:
            directory_keys.add(key)
            nodes.append(
                NodeSpec(
                    key=key,
                    node_type="directory",
                    name=posixpath.basename(path),
                    file_path=path,
                )
            )
        return key

    for parsed in parsed_files:
        file_key = f"file:{parsed.path}"
        file_keys[parsed.path] = file_key
        node_type = "test" if is_test_path(parsed.path) else "file"
        nodes.append(
            NodeSpec(
                key=file_key,
                node_type=node_type,
                name=posixpath.basename(parsed.path),
                qualified_name=parsed.path,
                file_path=parsed.path,
                language=parsed.language,
                metadata={
                    "line_count": parsed.line_count,
                    "parse_mode": parsed.parse_mode,
                    "complexity": parsed.complexity,
                    "import_count": len(parsed.imports),
                    "symbol_count": len(parsed.symbols),
                    "warnings": parsed.warnings[:10],
                },
            )
        )
        for directory in _directory_chain(parsed.path):
            add_directory(directory)
            directory_key = f"dir:{directory}"
            parent = directory.rsplit("/", 1)[0] if "/" in directory else None
            edges.append(
                EdgeSpec(
                    source_key=f"dir:{parent}" if parent else "repository",
                    target_key=directory_key,
                    relationship_type="CONTAINS",
                    confidence=1.0,
                    origin="parsed",
                    detail="directory containment",
                )
            )
        file_parent = posixpath.dirname(parsed.path)
        edges.append(
            EdgeSpec(
                source_key=f"dir:{file_parent}" if file_parent else "repository",
                target_key=file_key,
                relationship_type="CONTAINS",
                confidence=1.0,
                origin="parsed",
                detail="file containment",
            )
        )
        if parsed.symbols:
            for symbol in parsed.symbols:
                symbol_key = f"symbol:{parsed.path}::{symbol.qualified_name or symbol.name}"
                nodes.append(
                    NodeSpec(
                        key=symbol_key,
                        node_type="class" if symbol.kind == "class" else "function",
                        name=symbol.name,
                        qualified_name=symbol.qualified_name,
                        file_path=parsed.path,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        language=parsed.language,
                        metadata={"complexity": symbol.complexity, "kind": symbol.kind},
                    )
                )
                edges.append(
                    EdgeSpec(
                        source_key=file_key,
                        target_key=symbol_key,
                        relationship_type="CONTAINS",
                        confidence=1.0,
                        origin="parsed",
                        source_line=symbol.start_line,
                        detail="symbol declared in file",
                    )
                )
                all_symbol_keys.setdefault(symbol.name, []).append((symbol_key, parsed.path))
                if parsed.language == "Python":
                    python_symbols.setdefault(symbol.name, []).append(
                        (symbol_key, parsed.path)
                    )
        # Python module aliases for import resolution.
        if parsed.language == "Python":
            dotted = parsed.path[:-3].replace("/", ".")
            if dotted.endswith(".__init__"):
                dotted = dotted[: -len(".__init__")]
            module_index.setdefault(dotted, file_key)
            module_index.setdefault(dotted.split(".")[-1], file_key)
        elif parsed.language in {"JavaScript", "TypeScript"}:
            module_index.setdefault(parsed.path.rsplit(".", 1)[0], file_key)

    # Repository root connects top-level directories.
    nodes.insert(0, NodeSpec(key="repository", node_type="repository", name="repository"))

    unresolved_modules: dict[str, str] = {}

    def resolve_import(parsed: ParsedFile, module: str) -> tuple[str | None, float, str]:
        if parsed.language == "Python":
            if module.startswith("."):
                base = posixpath.dirname(parsed.path)
                ups = len(module) - len(module.lstrip("."))
                for _ in range(max(0, ups - 1)):
                    base = posixpath.dirname(base)
                remainder = module.lstrip(".").replace(".", "/")
                candidate = posixpath.join(base, remainder) if remainder else base
                for suffix in (".py", "/__init__.py"):
                    if f"{candidate}{suffix}" in file_keys:
                        return file_keys[f"{candidate}{suffix}"], 1.0, "relative import resolved"
                return None, 0.4, "relative import target not found"
            parts = module.split(".")
            for size in range(len(parts), 0, -1):
                dotted = ".".join(parts[:size])
                if dotted in module_index:
                    return module_index[dotted], 0.95, "absolute import resolved"
            return None, 0.4, "external or unresolved module"
        if parsed.language in {"JavaScript", "TypeScript"}:
            if module.startswith("."):
                base = posixpath.dirname(parsed.path)
                target = posixpath.normpath(posixpath.join(base, module))
                if target.startswith("../"):
                    return None, 0.3, "relative import escapes the repository"
                for extension in JS_EXTENSIONS:
                    candidate = f"{target}{extension}"
                    if candidate in file_keys:
                        return file_keys[candidate], 0.95, "relative import resolved"
                return None, 0.35, "relative import target not found"
            return None, 0.35, "external package"
        if parsed.language == "Java":
            dotted = module.replace(".", "/")
            for root in JAVA_ROOTS:
                candidate = f"{root}{dotted}.java"
                if candidate in file_keys:
                    return file_keys[candidate], 0.9, "java import resolved by path"
            # Static imports may reference a member of a resolved class.
            parent = "/".join(dotted.split("/")[:-1])
            for root in JAVA_ROOTS:
                candidate = f"{root}{parent}.java"
                if candidate in file_keys:
                    return file_keys[candidate], 0.8, "java static import resolved to class"
            return None, 0.35, "external package"
        return None, 0.3, "unsupported language"

    for parsed in parsed_files:
        source_key = file_keys[parsed.path]
        for imp in parsed.imports:
            target_key, confidence, detail = resolve_import(parsed, imp.module)
            if target_key:
                relationship = "TESTS" if is_test_path(parsed.path) else "IMPORTS"
                edges.append(
                    EdgeSpec(
                        source_key=source_key,
                        target_key=target_key,
                        relationship_type=relationship,
                        confidence=confidence,
                        origin="parsed" if confidence >= 0.9 else "inferred",
                        source_line=imp.line,
                        detail=detail,
                        evidence={"module": imp.module, "line": imp.line, "resolution": detail},
                    )
                )
            else:
                module_key = f"module:{imp.module}"
                if module_key not in unresolved_modules:
                    unresolved_modules[module_key] = imp.module
                    nodes.append(
                        NodeSpec(
                            key=module_key,
                            node_type="module",
                            name=imp.module,
                            qualified_name=imp.module,
                            metadata={"external": True},
                        )
                    )
                edges.append(
                    EdgeSpec(
                        source_key=source_key,
                        target_key=module_key,
                        relationship_type="IMPORTS",
                        confidence=imp.confidence * 0.5,
                        origin="inferred",
                        source_line=imp.line,
                        detail=detail,
                        evidence={"module": imp.module, "line": imp.line, "resolution": detail},
                    )
                )

    # CALLS: only when a call name matches exactly one declared symbol in another file.
    symbol_lookup = {name: refs for name, refs in all_symbol_keys.items()}
    for parsed in parsed_files:
        for call in parsed.calls:
            refs = symbol_lookup.get(call.callee.split(".")[-1], [])
            if len(refs) != 1:
                continue
            target_key, target_path = refs[0]
            source_key = (
                f"symbol:{parsed.path}::{call.caller}"
                if call.caller
                else file_keys[parsed.path]
            )
            edges.append(
                EdgeSpec(
                    source_key=source_key,
                    target_key=target_key,
                    relationship_type="CALLS",
                    confidence=call.confidence,
                    origin="inferred",
                    source_line=call.line,
                    detail="call target matched by unique symbol name",
                    evidence={"callee": call.callee, "line": call.line, "file": parsed.path},
                )
            )
            if len(edges) > max_edges:
                break

    # Deduplicate identical edges (same source, target, type, line).
    seen: set[tuple[str, str, str, int | None]] = set()
    unique_edges: list[EdgeSpec] = []
    for edge in edges:
        signature = (edge.source_key, edge.target_key, edge.relationship_type, edge.source_line)
        if signature in seen:
            continue
        seen.add(signature)
        unique_edges.append(edge)
    return nodes, unique_edges[:max_edges]


def persist_graph(
    session, snapshot_id: str, nodes: list[NodeSpec], edges: list[EdgeSpec]
) -> tuple[int, int]:
    """Insert nodes then edges, resolving keys to database ids."""
    from app.repositories import code as code_repo

    code_repo.clear_snapshot_graph(session, snapshot_id)
    node_records = [
        CodeNode(
            snapshot_id=snapshot_id,
            key=spec.key,
            node_type=spec.node_type,
            name=spec.name[:300],
            qualified_name=(spec.qualified_name or None),
            file_path=spec.file_path,
            start_line=spec.start_line,
            end_line=spec.end_line,
            language=spec.language,
            metadata_json=spec.metadata or None,
        )
        for spec in nodes
    ]
    code_repo.add_nodes(session, node_records)
    by_key = {spec.key: record for spec, record in zip(nodes, node_records, strict=True)}
    edge_records = []
    for spec in edges:
        source = by_key.get(spec.source_key)
        target = by_key.get(spec.target_key)
        if source is None or target is None or source.id == target.id:
            continue
        edge_records.append(
            DependencyEdge(
                snapshot_id=snapshot_id,
                source_node_id=source.id,
                target_node_id=target.id,
                relationship_type=spec.relationship_type,
                confidence=spec.confidence,
                origin=spec.origin,
                source_line=spec.source_line,
                detail=spec.detail,
                evidence_json=spec.evidence or None,
                metadata_json=spec.metadata or None,
            )
        )
    code_repo.add_edges(session, edge_records)
    return len(node_records), len(edge_records)
