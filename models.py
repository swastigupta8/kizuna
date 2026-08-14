from enum import Enum

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    EXTERNAL = "external"


class NodeConfig(BaseModel):
    has_circuit_breaker: bool = False
    has_retry: bool = False
    has_backoff: bool = False
    timeout_ms: int = 0
    replicas: int = 1
    critical: bool = False


class Node(BaseModel):
    id: str
    type: NodeType
    image: str | None = None
    config: NodeConfig = Field(default_factory=NodeConfig)


class Edge(BaseModel):
    source: str
    target: str


class ArchitectureGraph(BaseModel):
    nodes: list[Node]
    edges: list[Edge]

    def node(self, node_id: str) -> Node:
        return next(n for n in self.nodes if n.id == node_id)

    def neighbors(self, node_id: str) -> list[str]:
        """Nodes that `node_id` depends on (outgoing edges)."""
        return [e.target for e in self.edges if e.source == node_id]

    def dependents(self, node_id: str) -> list[str]:
        """Nodes that depend on `node_id` (incoming edges) — who breaks if this fails."""
        return [e.source for e in self.edges if e.target == node_id]
