from dataclasses import dataclass, field

from models import ArchitectureGraph, Finding, Node, Severity

SECONDS_PER_HOP = 2.0
PROPAGATION_FLOOR = 0.05
DEFAULT_SLA_TARGET_SECONDS = 60.0


@dataclass
class CascadeEvent:
    node_id: str
    severity: float
    time_offset: float


@dataclass
class CascadeResult:
    target_node: str
    severities: dict[str, float]
    timeline: list[CascadeEvent] = field(default_factory=list)


def run_cascade(graph: ArchitectureGraph, target_node: str, magnitude: float = 1.0) -> CascadeResult:
    """
    Breadth-first walk from a failed node to whatever depends on it. Each hop's
    severity is dampened by the *receiving* node's resilience config — a circuit
    breaker absorbs 60% of it, a bare retry absorbs 20%, nothing absorbs none of
    it. Propagation stops once severity drops below a noise floor.
    """
    severities: dict[str, float] = {target_node: magnitude}
    timeline: list[CascadeEvent] = [CascadeEvent(target_node, magnitude, 0.0)]
    visited: set[str] = set()
    queue: list[str] = [target_node]
    t = 0.0

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        t += SECONDS_PER_HOP

        for downstream in graph.dependents(current):
            resilience = _resilience_factor(graph.node(downstream))
            propagated = severities[current] * (1 - resilience)
            if propagated > PROPAGATION_FLOOR:
                severities[downstream] = propagated
                timeline.append(CascadeEvent(downstream, propagated, t))
                queue.append(downstream)

    return CascadeResult(target_node=target_node, severities=severities, timeline=timeline)


def _resilience_factor(node: Node) -> float:
    if node.config.has_circuit_breaker:
        return 0.6
    if node.config.has_retry:
        return 0.2
    return 0.0


def simulate_critical_failures(graph: ArchitectureGraph, magnitude: float = 1.0) -> list[CascadeResult]:
    """Run the cascade once per critical node — falls back to every node if none are marked critical."""
    targets = [n.id for n in graph.nodes if n.config.critical] or [n.id for n in graph.nodes]
    return [run_cascade(graph, target, magnitude) for target in targets]


def blast_radius_score(results: list[CascadeResult], total_nodes: int) -> tuple[float, list[Finding]]:
    if not results or total_nodes == 0:
        return 100.0, []

    total_pct = 0.0
    findings: list[Finding] = []
    for result in results:
        affected = sum(1 for severity in result.severities.values() if severity > 0.1)
        pct = affected / total_nodes
        total_pct += pct
        if pct > 0.5:
            findings.append(
                Finding(
                    severity=Severity.HIGH,
                    node_id=result.target_node,
                    message=f"failure at {result.target_node} would degrade {pct * 100:.0f}% of the system",
                )
            )

    average_pct = total_pct / len(results)
    return max(100.0 * (1 - average_pct), 0.0), findings


def recovery_score(recovery_seconds: float, sla_target_seconds: float = DEFAULT_SLA_TARGET_SECONDS) -> float:
    if recovery_seconds <= 0:
        return 100.0
    ratio = sla_target_seconds / recovery_seconds
    return min(100.0, 100.0 * ratio)


def average_recovery_score(
    results: list[CascadeResult], sla_target_seconds: float = DEFAULT_SLA_TARGET_SECONDS
) -> float:
    if not results:
        return 100.0
    scores = [recovery_score(_stabilization_time(r), sla_target_seconds) for r in results]
    return sum(scores) / len(scores)


def _stabilization_time(result: CascadeResult) -> float:
    return result.timeline[-1].time_offset if result.timeline else 0.0
