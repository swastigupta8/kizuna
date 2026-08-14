from models import ArchitectureGraph, Finding, Severity


def find_articulation_points(graph: ArchitectureGraph) -> set[str]:
    """
    Tarjan's articulation point algorithm, run on the dependency graph treated
    as undirected. A node is an articulation point if removing it splits the
    graph into pieces that can no longer reach each other at all — a genuine
    structural single point of failure, independent of which way calls flow.
    """
    adjacency = _undirected_adjacency(graph)
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    articulation_points: set[str] = set()
    timer = 0

    def dfs(u: str) -> None:
        nonlocal timer
        discovery[u] = low[u] = timer
        timer += 1
        children = 0

        for v in adjacency[u]:
            if v not in discovery:
                children += 1
                parent[v] = u
                dfs(v)
                low[u] = min(low[u], low[v])

                is_root = parent[u] is None
                if is_root and children > 1:
                    articulation_points.add(u)
                if not is_root and low[v] >= discovery[u]:
                    articulation_points.add(u)
            elif v != parent[u]:
                low[u] = min(low[u], discovery[v])

    for node in graph.nodes:
        if node.id not in discovery:
            parent[node.id] = None
            dfs(node.id)

    return articulation_points


def redundancy_score(graph: ArchitectureGraph) -> tuple[float, list[Finding]]:
    spofs = find_articulation_points(graph)
    critical_node_count = len([n for n in graph.nodes if n.config.critical])
    denominator = critical_node_count or len(graph.nodes) or 1

    findings = [
        Finding(
            severity=Severity.HIGH,
            node_id=node_id,
            message=f"{node_id} is a single point of failure — no redundant path exists",
        )
        for node_id in sorted(spofs)
    ]

    score = 100.0 * (1.0 - len(spofs) / denominator)
    return max(score, 0.0), findings


def _undirected_adjacency(graph: ArchitectureGraph) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {node.id: set() for node in graph.nodes}
    for edge in graph.edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)
    return adjacency
