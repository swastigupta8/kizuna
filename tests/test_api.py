from fastapi.testclient import TestClient

import db
from main import app

client = TestClient(app)

COMPOSE = """
services:
  api:
    image: myorg/api
    depends_on:
      - db
    labels:
      - "kizuna.critical=true"
  db:
    image: postgres:16
"""


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_score_endpoint_computes_and_returns_all_subscores(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api-test.db")

    resp = client.post("/api/v1/score", json={"repo": "demo/repo", "compose_yaml": COMPOSE})

    assert resp.status_code == 200
    body = resp.json()
    assert body["repo"] == "demo/repo"
    for key in ("overall_score", "blast_radius_score", "recovery_score", "redundancy_score", "degradation_score"):
        assert 0.0 <= body[key] <= 100.0
    assert isinstance(body["findings"], list)


def test_score_endpoint_persists_and_history_reads_it_back(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api-test.db")

    client.post("/api/v1/score", json={"repo": "demo/repo", "compose_yaml": COMPOSE})
    resp = client.get("/api/v1/score/history/demo/repo")

    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 1
    assert history[0]["repo"] == "demo/repo"


def test_invalid_yaml_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api-test.db")

    resp = client.post("/api/v1/score", json={"repo": "demo/repo", "compose_yaml": "not: valid: yaml: at: all:"})
    assert resp.status_code == 400


def test_compose_with_no_services_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api-test.db")

    resp = client.post("/api/v1/score", json={"repo": "demo/repo", "compose_yaml": "services: {}"})
    assert resp.status_code == 400
