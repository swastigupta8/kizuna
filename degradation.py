from collections.abc import Callable
from dataclasses import dataclass

from models import ArchitectureGraph, Finding, Node, Severity


@dataclass(frozen=True)
class Rule:
    name: str
    weight: float
    check: Callable[[Node, ArchitectureGraph], Finding | None]


def _missing_timeout(node: Node, graph: ArchitectureGraph) -> Finding | None:
    if graph.neighbors(node.id) and node.config.timeout_ms == 0:
        return Finding(
            severity=Severity.MEDIUM,
            node_id=node.id,
            message=f"{node.id} has no timeout configured on its outbound calls",
        )
    return None


def _no_circuit_breaker_on_dependency(node: Node, graph: ArchitectureGraph) -> Finding | None:
    if graph.neighbors(node.id) and not node.config.has_circuit_breaker:
        return Finding(
            severity=Severity.HIGH,
            node_id=node.id,
            message=f"{node.id} calls a downstream dependency with no circuit breaker",
        )
    return None


def _naive_retry_no_backoff(node: Node, graph: ArchitectureGraph) -> Finding | None:
    if node.config.has_retry and not node.config.has_backoff:
        return Finding(
            severity=Severity.MEDIUM,
            node_id=node.id,
            message=f"{node.id} retries without exponential backoff — risk of retry storms",
        )
    return None


def _single_replica_critical_service(node: Node, graph: ArchitectureGraph) -> Finding | None:
    if node.config.critical and node.config.replicas <= 1:
        return Finding(
            severity=Severity.HIGH,
            node_id=node.id,
            message=f"{node.id} is critical but runs a single replica",
        )
    return None


DEGRADATION_RULES: list[Rule] = [
    Rule("missing_timeout", weight=15, check=_missing_timeout),
    Rule("no_circuit_breaker_on_dependency", weight=20, check=_no_circuit_breaker_on_dependency),
    Rule("naive_retry_no_backoff", weight=10, check=_naive_retry_no_backoff),
    Rule("single_replica_critical_service", weight=15, check=_single_replica_critical_service),
]


def degradation_score(graph: ArchitectureGraph) -> tuple[float, list[Finding]]:
    score = 100.0
    findings: list[Finding] = []
    for node in graph.nodes:
        for rule in DEGRADATION_RULES:
            finding = rule.check(node, graph)
            if finding is not None:
                score -= rule.weight
                findings.append(finding)
    return max(score, 0.0), findings
