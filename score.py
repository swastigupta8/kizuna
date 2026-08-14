from dataclasses import dataclass, field

from degradation import degradation_score
from models import ArchitectureGraph, Finding
from redundancy import redundancy_score
from simulate import average_recovery_score, blast_radius_score, simulate_critical_failures

WEIGHTS = {
    "blast_radius": 0.35,
    "recovery": 0.25,
    "redundancy": 0.25,
    "degradation": 0.15,
}


@dataclass
class ScoreResult:
    overall: float
    blast_radius: float
    recovery: float
    redundancy: float
    degradation: float
    findings: list[Finding] = field(default_factory=list)


def compute_score(graph: ArchitectureGraph) -> ScoreResult:
    redundancy_val, redundancy_findings = redundancy_score(graph)
    degradation_val, degradation_findings = degradation_score(graph)

    cascade_results = simulate_critical_failures(graph)
    blast_val, blast_findings = blast_radius_score(cascade_results, total_nodes=len(graph.nodes))
    recovery_val = average_recovery_score(cascade_results)

    overall = (
        blast_val * WEIGHTS["blast_radius"]
        + recovery_val * WEIGHTS["recovery"]
        + redundancy_val * WEIGHTS["redundancy"]
        + degradation_val * WEIGHTS["degradation"]
    )

    return ScoreResult(
        overall=round(overall, 1),
        blast_radius=round(blast_val, 1),
        recovery=round(recovery_val, 1),
        redundancy=round(redundancy_val, 1),
        degradation=round(degradation_val, 1),
        findings=redundancy_findings + degradation_findings + blast_findings,
    )
