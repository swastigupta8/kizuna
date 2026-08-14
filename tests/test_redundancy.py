from pathlib import Path

from models import ArchitectureGraph, Edge, Node, NodeConfig, NodeType
from parser import parse_compose
from redundancy import find_articulation_points, redundancy_score

FIXTURE = Path(__file__).parent.parent / "testdata" / "booking-platform" / "docker-compose.yml"


def _node(node_id: str, critical: bool = False) -> Node:
    return Node(id=node_id, type=NodeType.SERVICE, config=NodeConfig(critical=critical))


def test_middle_of_a_chain_is_a_spof():
    # api -> gateway -> db : gateway is the only path between api and db
    graph = ArchitectureGraph(
        nodes=[_node("api", critical=True), _node("gateway"), _node("db", critical=True)],
        edges=[Edge(source="api", target="gateway"), Edge(source="gateway", target="db")],
    )
    assert find_articulation_points(graph) == {"gateway"}


def test_a_hub_with_three_independent_paths_has_no_spof():
    # api reaches db through three separate services — no single node,
    # if removed, disconnects api from db, so structurally this is redundant
    # even though db only has one instance.
    graph = parse_compose(FIXTURE)
    assert find_articulation_points(graph) == set()


def test_redundancy_score_is_100_when_no_spofs_exist():
    graph = parse_compose(FIXTURE)
    score, findings = redundancy_score(graph)
    assert score == 100.0
    assert findings == []


def test_redundancy_score_drops_and_reports_a_finding_when_a_spof_exists():
    graph = ArchitectureGraph(
        nodes=[_node("api", critical=True), _node("gateway", critical=True), _node("db", critical=True)],
        edges=[Edge(source="api", target="gateway"), Edge(source="gateway", target="db")],
    )
    score, findings = redundancy_score(graph)
    assert score < 100.0
    assert len(findings) == 1
    assert findings[0].node_id == "gateway"
    assert "single point of failure" in findings[0].message
