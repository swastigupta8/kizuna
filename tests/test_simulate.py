import pytest

from models import ArchitectureGraph, Edge, Node, NodeConfig, NodeType
from simulate import (
    blast_radius_score,
    recovery_score,
    run_cascade,
    simulate_critical_failures,
)


def _node(node_id: str, critical: bool = False, has_circuit_breaker: bool = False) -> Node:
    return Node(
        id=node_id,
        type=NodeType.SERVICE,
        config=NodeConfig(critical=critical, has_circuit_breaker=has_circuit_breaker),
    )


def test_failure_propagates_to_a_direct_dependent():
    # api depends on db — if db fails, api feels it
    graph = ArchitectureGraph(
        nodes=[_node("api"), _node("db")],
        edges=[Edge(source="api", target="db")],
    )
    result = run_cascade(graph, target_node="db", magnitude=1.0)
    assert result.severities == {"db": 1.0, "api": 1.0}
    assert [event.node_id for event in result.timeline] == ["db", "api"]


def test_no_resilience_config_means_full_severity_passes_through():
    graph = ArchitectureGraph(
        nodes=[_node("api"), _node("db")],
        edges=[Edge(source="api", target="db")],
    )
    result = run_cascade(graph, target_node="db", magnitude=1.0)
    assert result.severities["api"] == 1.0


def test_circuit_breaker_dampens_propagated_severity():
    graph = ArchitectureGraph(
        nodes=[_node("api", has_circuit_breaker=True), _node("db")],
        edges=[Edge(source="api", target="db")],
    )
    result = run_cascade(graph, target_node="db", magnitude=1.0)
    assert result.severities["api"] == pytest.approx(0.4)


def test_severity_dampens_progressively_through_a_protected_chain():
    # db -> a -> b -> c, every hop past db has a circuit breaker:
    # 1.0 -> 0.4 -> 0.16 -> 0.064
    graph = ArchitectureGraph(
        nodes=[
            _node("db"),
            _node("a", has_circuit_breaker=True),
            _node("b", has_circuit_breaker=True),
            _node("c", has_circuit_breaker=True),
        ],
        edges=[
            Edge(source="a", target="db"),
            Edge(source="b", target="a"),
            Edge(source="c", target="b"),
        ],
    )
    result = run_cascade(graph, target_node="db", magnitude=1.0)
    assert result.severities["db"] > result.severities["a"] > result.severities["b"] > result.severities["c"]
    assert result.severities["c"] == pytest.approx(0.064)


def test_cascade_stops_once_severity_drops_below_the_floor():
    # one more protected hop past "c": 0.064 * 0.4 = 0.0256, below the 0.05 floor — "d" is spared
    graph = ArchitectureGraph(
        nodes=[
            _node("db"),
            _node("a", has_circuit_breaker=True),
            _node("b", has_circuit_breaker=True),
            _node("c", has_circuit_breaker=True),
            _node("d", has_circuit_breaker=True),
        ],
        edges=[
            Edge(source="a", target="db"),
            Edge(source="b", target="a"),
            Edge(source="c", target="b"),
            Edge(source="d", target="c"),
        ],
    )
    result = run_cascade(graph, target_node="db", magnitude=1.0)
    assert "d" not in result.severities


def test_blast_radius_score_reflects_fraction_of_system_affected():
    # star: three unprotected services all depend on db — if db is critical and fails,
    # the cascade takes out the whole system
    graph = ArchitectureGraph(
        nodes=[_node("db", critical=True), _node("a"), _node("b"), _node("c")],
        edges=[
            Edge(source="a", target="db"),
            Edge(source="b", target="db"),
            Edge(source="c", target="db"),
        ],
    )
    results = simulate_critical_failures(graph)
    score, findings = blast_radius_score(results, total_nodes=len(graph.nodes))
    assert score < 10.0
    assert len(findings) == 1
    assert findings[0].node_id == "db"


def test_blast_radius_score_is_100_when_nothing_is_simulated():
    score, findings = blast_radius_score([], total_nodes=0)
    assert score == 100.0
    assert findings == []


def test_recovery_score_scales_against_the_sla_target():
    assert recovery_score(recovery_seconds=30, sla_target_seconds=60) == 100.0
    assert recovery_score(recovery_seconds=120, sla_target_seconds=60) == 50.0
    assert recovery_score(recovery_seconds=0, sla_target_seconds=60) == 100.0
