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


def test_dashboard_renders_a_friendly_empty_state_instead_of_a_bare_404(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "dash-test.db")
    resp = client.get("/dashboard/nobody/nothing")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "No scores recorded yet" in resp.text
    assert "nobody/nothing" in resp.text


def test_dashboard_renders_the_latest_score_and_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "dash-test.db")

    client.post("/api/v1/score", json={"repo": "demo/repo", "compose_yaml": COMPOSE})
    resp = client.get("/dashboard/demo/repo")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "demo/repo" in resp.text
    assert "resilience score" in resp.text


def test_dashboard_score_history_feeds_the_chart_data(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "dash-test.db")

    client.post("/api/v1/score", json={"repo": "demo/repo", "compose_yaml": COMPOSE})
    client.post("/api/v1/score", json={"repo": "demo/repo", "compose_yaml": COMPOSE})
    resp = client.get("/dashboard/demo/repo")

    assert resp.status_code == 200
    assert "historyChart" in resp.text
