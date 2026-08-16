import db


def _sample_findings() -> list[dict]:
    return [{"severity": "high", "node_id": "api", "message": "no circuit breaker", "remediation": "add one"}]


def _file_url(tmp_path, name: str) -> str:
    return f"file:{tmp_path / name}"


def test_save_and_read_back_a_score_run(tmp_path):
    db_url = _file_url(tmp_path, "test.db")

    db.save_score_run("swastigupta8/kizuna-demo", 72.5, 65.0, 88.0, 60.0, 82.0, _sample_findings(), db_url=db_url)
    history = db.get_score_history("swastigupta8/kizuna-demo", db_url=db_url)

    assert len(history) == 1
    assert history[0]["overall_score"] == 72.5
    assert history[0]["repo"] == "swastigupta8/kizuna-demo"


def test_findings_round_trip_including_remediation_text(tmp_path):
    db_url = _file_url(tmp_path, "test.db")
    db.save_score_run("repo-a", 50.0, 50.0, 50.0, 50.0, 50.0, _sample_findings(), db_url=db_url)

    history = db.get_score_history("repo-a", db_url=db_url)
    import json

    findings = json.loads(history[0]["findings_json"])
    assert findings[0]["remediation"] == "add one"


def test_history_is_scoped_to_the_requested_repo(tmp_path):
    db_url = _file_url(tmp_path, "test.db")

    db.save_score_run("repo-a", 90.0, 90.0, 90.0, 90.0, 90.0, [], db_url=db_url)
    db.save_score_run("repo-b", 90.0, 90.0, 90.0, 90.0, 90.0, [], db_url=db_url)

    assert len(db.get_score_history("repo-a", db_url=db_url)) == 1
    assert len(db.get_score_history("repo-b", db_url=db_url)) == 1
    assert len(db.get_score_history("repo-c", db_url=db_url)) == 0


def test_graph_round_trips_when_provided(tmp_path):
    db_url = _file_url(tmp_path, "test.db")
    graph = {"nodes": [{"id": "api"}, {"id": "db"}], "edges": [{"source": "api", "target": "db"}]}

    db.save_score_run("repo-a", 80.0, 80.0, 80.0, 80.0, 80.0, [], graph=graph, db_url=db_url)
    history = db.get_score_history("repo-a", db_url=db_url)

    import json

    assert json.loads(history[0]["graph_json"]) == graph


def test_graph_is_null_when_not_provided(tmp_path):
    db_url = _file_url(tmp_path, "test.db")
    db.save_score_run("repo-a", 80.0, 80.0, 80.0, 80.0, 80.0, [], db_url=db_url)

    history = db.get_score_history("repo-a", db_url=db_url)
    assert history[0]["graph_json"] is None


def test_history_is_ordered_most_recent_first(tmp_path):
    db_url = _file_url(tmp_path, "test.db")

    db.save_score_run("repo-a", 40.0, 40.0, 40.0, 40.0, 40.0, [], db_url=db_url)
    db.save_score_run("repo-a", 95.0, 95.0, 95.0, 95.0, 95.0, [], db_url=db_url)

    history = db.get_score_history("repo-a", db_url=db_url)
    assert history[0]["overall_score"] == 95.0
    assert history[1]["overall_score"] == 40.0
