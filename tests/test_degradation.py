from pathlib import Path

from degradation import degradation_score
from models import ArchitectureGraph, Edge, Node, NodeConfig, NodeType
from parser import parse_compose

FIXTURE = Path(__file__).parent.parent / "testdata" / "booking-platform" / "docker-compose.yml"


def _graph_with(config: NodeConfig, has_dependency: bool = True) -> ArchitectureGraph:
    """One node ("svc") with the given config, optionally calling a bare downstream node."""
    nodes = [Node(id="svc", type=NodeType.SERVICE, config=config)]
    edges: list[Edge] = []
    if has_dependency:
        nodes.append(Node(id="downstream", type=NodeType.SERVICE, config=NodeConfig()))
        edges.append(Edge(source="svc", target="downstream"))
    return ArchitectureGraph(nodes=nodes, edges=edges)


def test_missing_timeout_and_missing_circuit_breaker_both_fire():
    graph = _graph_with(NodeConfig(timeout_ms=0))
    score, findings = degradation_score(graph)
    assert score == 100 - 15 - 20
    assert any("timeout" in f.message for f in findings)
    assert any("circuit breaker" in f.message for f in findings)


def test_configured_timeout_and_breaker_avoid_both_findings():
    graph = _graph_with(NodeConfig(timeout_ms=3000, has_circuit_breaker=True))
    score, findings = degradation_score(graph)
    assert score == 100.0
    assert findings == []


def test_no_circuit_breaker_on_a_dependency():
    graph = _graph_with(NodeConfig(timeout_ms=1000))
    score, findings = degradation_score(graph)
    assert score == 80.0
    assert any("circuit breaker" in f.message for f in findings)


def test_naive_retry_without_backoff():
    graph = _graph_with(NodeConfig(has_retry=True, has_backoff=False), has_dependency=False)
    score, findings = degradation_score(graph)
    assert score == 90.0
    assert any("backoff" in f.message for f in findings)


def test_retry_with_backoff_is_fine():
    graph = _graph_with(NodeConfig(has_retry=True, has_backoff=True), has_dependency=False)
    score, findings = degradation_score(graph)
    assert score == 100.0
    assert findings == []


def test_single_replica_on_a_critical_service():
    graph = _graph_with(NodeConfig(critical=True, replicas=1), has_dependency=False)
    score, findings = degradation_score(graph)
    assert score == 85.0
    assert any("single replica" in f.message for f in findings)


def test_multiple_replicas_avoids_the_finding_even_if_critical():
    graph = _graph_with(NodeConfig(critical=True, replicas=3), has_dependency=False)
    score, findings = degradation_score(graph)
    assert score == 100.0
    assert findings == []


def test_demo_fixture_surfaces_at_least_one_real_finding():
    graph = parse_compose(FIXTURE)
    score, findings = degradation_score(graph)
    assert 0.0 <= score <= 100.0
    assert len(findings) > 0
