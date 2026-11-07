# Knowledge graph spec

Status: IMPLEMENTED · TESTED, including Hypothesis graph properties.

## Requirements

1. Build a directed graph of files, modules, classes, functions, tests and workflows.
2. Only create edges with evidence; mark inferred edges with confidence and origin.
3. Support direct/reverse lookup, bounded traversal, cycles, components and centrality.
4. Provide impact analysis with related tests and evidence.
5. Expose graph filters, search and metrics through the API.
6. Render actual indexed data in an interactive React Flow explorer.
7. Bound traversal depth and view size to protect the API.

## Acceptance criteria

- [x] Edges reference existing nodes only.
- [x] Traversal terminates within `max_depth` (property test).
- [x] Reverse traversal returns incoming relationships.
- [x] Cycle detection returns real cycles.
- [x] Impact analysis returns affected nodes, depths, paths, related tests and evidence.
- [x] Graph view caps nodes and reports `truncated`/totals.
- [x] UI supports zoom, pan, search, type filter, node details, both traversal directions, impact,
      minimap and reset view.
- [x] Missing evidence edges are counted in metrics.

## Design

`app/graph/builder.py` persists nodes/edges; `app/graph/engine.py` wraps NetworkX with explicit
bounds (`MAX_DEPTH`, view limits, cycle cap). `app/api/v1/graph.py` exposes view, metrics, node,
dependencies and impact. UI: `features/graph/GraphPage.tsx` with `@xyflow/react`.

## Data model

`code_nodes`, `dependency_edges` (`relationship_type`, `confidence`, `origin`, `evidence_json`).

## API

`GET /repositories/{id}/graph`, `/graph/metrics`, `/graph/nodes/{node_id}`,
`/graph/dependencies/{node_id}?direction=&max_depth=`, `POST /graph/impact`.

## Tasks

- [x] Graph schemas.
- [x] Node/edge building.
- [x] Traversal and reverse traversal.
- [x] Cycles and components.
- [x] Centrality.
- [x] Impact analysis.
- [x] Graph API.
- [x] React Flow explorer.
- [x] Property-based tests.
- [ ] Layout tuning for very large repositories (current view is capped at 250 nodes).

## Tests

Hypothesis: no self-dependency unless in a cycle, valid edge endpoints, traversal termination,
reverse validity, unrelated node isolation, edge removal safety. Integration: chain and impact on the
mocked repository.
