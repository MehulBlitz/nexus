"""Property-based tests for graph invariants."""

import networkx as nx
from hypothesis import given, settings
from hypothesis import strategies as st

from app.graph.engine import build_view, impact_analysis, traversal
from app.models.code import CodeNode, DependencyEdge

RELATIONSHIPS = ["IMPORTS", "CALLS", "TESTS", "CONTAINS"]


class FakeNode(CodeNode):
    """Detached CodeNode that does not need a session."""

    def __init__(self, node_id: str, path: str):
        self.id = node_id
        self.node_type = "file"
        self.name = path
        self.qualified_name = path
        self.file_path = path
        self.start_line = 1
        self.end_line = 10
        self.language = "Python"
        self.metadata_json = {"line_count": 10}
        self.snapshot_id = "s"


class FakeEdge(DependencyEdge):
    def __init__(self, source: str, target: str, relationship: str):
        self.id = f"{source}->{target}-{relationship}"
        self.source_node_id = source
        self.target_node_id = target
        self.relationship_type = relationship
        self.confidence = 1.0
        self.origin = "parsed"
        self.detail = None
        self.evidence_json = {"verified": True}
        self.snapshot_id = "s"


def graph_payload():
    return st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=5),
            st.integers(min_value=0, max_value=5),
            st.sampled_from(RELATIONSHIPS),
        ),
        max_size=12,
    )


def build(edges_raw):
    nodes = [FakeNode(f"n{i}", f"src/f{i}.py") for i in range(6)]
    edges = [FakeEdge(f"n{a}", f"n{b}", relationship) for a, b, relationship in edges_raw]
    return build_view(nodes, edges)


@settings(max_examples=80, deadline=None)
@given(graph_payload(), st.integers(min_value=1, max_value=8))
def test_traversal_terminates_and_respects_depth(edges_raw, depth):
    view = build(edges_raw)
    steps, _truncated = traversal(view, "n0", direction="out", max_depth=depth)
    assert all(step["depth"] <= depth for step in steps)
    assert len({step["node_id"] for step in steps}) == len(steps)


@settings(max_examples=80, deadline=None)
@given(graph_payload())
def test_every_edge_references_existing_nodes(edges_raw):
    view = build(edges_raw)
    assert all(edge.source_node_id in view.nodes for edge in view.edges)
    assert all(edge.target_node_id in view.nodes for edge in view.edges)


@settings(max_examples=60, deadline=None)
@given(graph_payload())
def test_reverse_traversal_returns_valid_incoming_nodes(edges_raw):
    view = build(edges_raw)
    steps, _ = traversal(view, "n3", direction="in", max_depth=3)
    for step in steps:
        assert step["edge_from"] in view.nodes and step["edge_to"] in view.nodes
        assert view.graph.has_edge(step["edge_from"], step["edge_to"])


def test_adding_unrelated_node_does_not_change_a_chain():
    nodes = [FakeNode("a", "a.py"), FakeNode("b", "b.py")]
    edges = [FakeEdge("a", "b", "IMPORTS")]
    baseline, _ = traversal(build_view(nodes, edges), "a", direction="out", max_depth=3)
    extra = [*nodes, FakeNode("z", "z.py")]
    after, _ = traversal(build_view(extra, edges), "a", direction="out", max_depth=3)
    assert [step["node_id"] for step in baseline] == [step["node_id"] for step in after]


def test_removing_an_edge_does_not_create_a_dependency():
    nodes = [FakeNode("a", "a.py"), FakeNode("b", "b.py"), FakeNode("c", "c.py")]
    edges = [FakeEdge("a", "b", "IMPORTS"), FakeEdge("b", "c", "IMPORTS")]
    trimmed = build_view(nodes, edges[:1])
    steps, _ = traversal(trimmed, "a", direction="out", max_depth=3)
    assert [step["node_id"] for step in steps] == ["b"]
    assert not trimmed.graph.has_edge("b", "c")


def test_cycles_are_detected_without_infinite_traversal():
    nodes = [FakeNode("a", "a.py"), FakeNode("b", "b.py")]
    edges = [FakeEdge("a", "b", "IMPORTS"), FakeEdge("b", "a", "IMPORTS")]
    view = build_view(nodes, edges)
    steps, _ = traversal(view, "a", direction="out", max_depth=8)
    assert [step["node_id"] for step in steps] == ["b"]
    assert nx.is_strongly_connected(view.graph)


def test_impact_analysis_explains_evidence():
    nodes = [FakeNode("a", "a.py"), FakeNode("b", "b.py")]
    edges = [FakeEdge("a", "b", "IMPORTS")]
    result = impact_analysis(build_view(nodes, edges), "b", direction="dependents", max_depth=2)
    assert result["affected"]
    assert result["evidence"]
    assert result["affected"][0]["node"]["file_path"] == "a.py"
