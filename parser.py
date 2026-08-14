from pathlib import Path

import yaml

from models import ArchitectureGraph, Edge, Node, NodeConfig, NodeType

_DB_HINTS = ("postgres", "mysql", "mariadb", "mongo", "cassandra")
_CACHE_HINTS = ("redis", "memcached")
_QUEUE_HINTS = ("kafka", "rabbitmq", "sqs")


def parse_compose(path: str | Path) -> ArchitectureGraph:
    raw = yaml.safe_load(Path(path).read_text())
    services = raw.get("services") or {}

    nodes: list[Node] = []
    edges: list[Edge] = []

    for name, spec in services.items():
        spec = spec or {}
        image = spec.get("image")
        labels = _normalize_labels(spec.get("labels"))
        replicas = (spec.get("deploy") or {}).get("replicas", 1)

        config = NodeConfig(
            has_circuit_breaker=_flag(labels, "kizuna.circuit_breaker"),
            has_retry=_flag(labels, "kizuna.retry"),
            has_backoff=_flag(labels, "kizuna.backoff"),
            timeout_ms=int(labels.get("kizuna.timeout_ms", 0)),
            replicas=int(replicas),
            critical=_flag(labels, "kizuna.critical"),
        )

        nodes.append(Node(id=name, type=_infer_type(image), image=image, config=config))

        for dep_name in _depends_on_names(spec.get("depends_on")):
            edges.append(Edge(source=name, target=dep_name))

    return ArchitectureGraph(nodes=nodes, edges=edges)


def _infer_type(image: str | None) -> NodeType:
    """Guess node type from the image name — directionally correct, not perfect."""
    if not image:
        return NodeType.SERVICE
    lowered = image.lower()
    if any(hint in lowered for hint in _DB_HINTS):
        return NodeType.DATABASE
    if any(hint in lowered for hint in _CACHE_HINTS):
        return NodeType.CACHE
    if any(hint in lowered for hint in _QUEUE_HINTS):
        return NodeType.QUEUE
    return NodeType.SERVICE


def _depends_on_names(depends_on) -> list[str]:
    """depends_on can be a YAML list (short syntax) or a dict (long syntax w/ health conditions)."""
    if not depends_on:
        return []
    if isinstance(depends_on, dict):
        return list(depends_on.keys())
    return list(depends_on)


def _normalize_labels(labels) -> dict:
    """labels can be a YAML dict, or a list of "key=value" strings — compose allows both."""
    if not labels:
        return {}
    if isinstance(labels, dict):
        return {str(k): str(v) for k, v in labels.items()}
    out: dict[str, str] = {}
    for item in labels:
        if "=" in item:
            key, value = item.split("=", 1)
            out[key] = value
    return out


def _flag(labels: dict, key: str) -> bool:
    return str(labels.get(key, "")).lower() in ("1", "true", "yes")
