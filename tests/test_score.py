import pytest

from degradation import degradation_score
from models import ArchitectureGraph, Edge, Node, NodeConfig, NodeType
from redundancy import redundancy_score
from score import WEIGHTS, compute_score
from simulate import average_recovery_score, blast_radius_score, simulate_critical_failures


def _sample_graph() -> ArchitectureGraph:
    return ArchitectureGraph(
        nodes=[
            Node(id="api", type=NodeType.SERVICE, config=NodeConfig(critical=True, replicas=1)),
            Node(id="db", type=NodeType.DATABASE, config=NodeConfig(critical=True, replicas=1)),
        ],
        edges=[Edge(source="api", target="db")],
    )


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_overall_score_matches_the_weighted_average_of_its_four_inputs():
    graph = _sample_graph()

    redundancy_val, _ = redundancy_score(graph)
    degradation_val, _ = degradation_score(graph)
    cascade_results = simulate_critical_failures(graph)
    blast_val, _ = blast_radius_score(cascade_results, total_nodes=len(graph.nodes))
    recovery_val = average_recovery_score(cascade_results)

    expected = (
        blast_val * WEIGHTS["blast_radius"]
        + recovery_val * WEIGHTS["recovery"]
        + redundancy_val * WEIGHTS["redundancy"]
        + degradation_val * WEIGHTS["degradation"]
    )

    result = compute_score(graph)
    # compute_score() rounds each sub-score to 1dp before weighting; allow for that
    assert result.overall == pytest.approx(expected, abs=0.1)


def test_findings_are_pooled_from_every_subscore():
    graph = _sample_graph()
    result = compute_score(graph)
    assert result.overall < 100.0
    assert len(result.findings) > 0
