from pathlib import Path

from models import NodeType
from parser import parse_compose

FIXTURE = Path(__file__).parent.parent / "testdata" / "booking-platform" / "docker-compose.yml"


def test_parses_every_service_as_a_node():
    graph = parse_compose(FIXTURE)
    node_ids = {n.id for n in graph.nodes}
    assert node_ids == {
        "booking-api",
        "payment-service",
        "inventory-service",
        "notification-service",
        "inventory-db",
    }


def test_infers_database_type_from_image_name():
    graph = parse_compose(FIXTURE)
    assert graph.node("inventory-db").type == NodeType.DATABASE
    assert graph.node("booking-api").type == NodeType.SERVICE


def test_depends_on_becomes_edges():
    graph = parse_compose(FIXTURE)
    assert graph.neighbors("payment-service") == ["inventory-db"]
    assert set(graph.neighbors("booking-api")) == {
        "payment-service",
        "inventory-service",
        "notification-service",
    }


def test_dependents_is_the_reverse_of_neighbors():
    graph = parse_compose(FIXTURE)
    # every service that calls inventory-db shows up as its dependent
    assert set(graph.dependents("inventory-db")) == {
        "payment-service",
        "inventory-service",
        "notification-service",
    }


def test_reads_kizuna_labels_into_config():
    graph = parse_compose(FIXTURE)

    payment = graph.node("payment-service")
    assert payment.config.has_circuit_breaker is True
    assert payment.config.critical is True

    notifications = graph.node("notification-service")
    assert notifications.config.has_circuit_breaker is False
    assert notifications.config.critical is False


def test_reads_replica_count_from_deploy_block():
    graph = parse_compose(FIXTURE)
    assert graph.node("inventory-service").config.replicas == 2
    assert graph.node("inventory-db").config.replicas == 1
