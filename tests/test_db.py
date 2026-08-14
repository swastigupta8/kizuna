import db


def _sample_findings() -> list[dict]:
    return [{"severity": "high", "node_id": "api", "message": "no circuit breaker", "remediation": "add one"}]


def test_save_and_read_back_a_score_run(tmp_path):
    db_path = tmp_path / "test.db"

    db.save_score_run(
        "swastigupta8/kizuna-demo", 72.5, 65.0, 88.0, 60.0, 82.0, _sample_findings(), db_path=db_path
    )
    history = db.get_score_history("swastigupta8/kizuna-demo", db_path=db_path)

    assert len(history) == 1
    assert history[0]["overall_score"] == 72.5
    assert history[0]["repo"] == "swastigupta8/kizuna-demo"


def test_findings_round_trip_including_remediation_text(tmp_path):
    db_path = tmp_path / "test.db"
    db.save_score_run("repo-a", 50.0, 50.0, 50.0, 50.0, 50.0, _sample_findings(), db_path=db_path)

    history = db.get_score_history("repo-a", db_path=db_path)
    import json

    findings = json.loads(history[0]["findings_json"])
    assert findings[0]["remediation"] == "add one"


def test_history_is_scoped_to_the_requested_repo(tmp_path):
    db_path = tmp_path / "test.db"

    db.save_score_run("repo-a", 90.0, 90.0, 90.0, 90.0, 90.0, [], db_path=db_path)
    db.save_score_run("repo-b", 90.0, 90.0, 90.0, 90.0, 90.0, [], db_path=db_path)

    assert len(db.get_score_history("repo-a", db_path=db_path)) == 1
    assert len(db.get_score_history("repo-b", db_path=db_path)) == 1
    assert len(db.get_score_history("repo-c", db_path=db_path)) == 0


def test_history_is_ordered_most_recent_first(tmp_path):
    db_path = tmp_path / "test.db"

    db.save_score_run("repo-a", 40.0, 40.0, 40.0, 40.0, 40.0, [], db_path=db_path)
    db.save_score_run("repo-a", 95.0, 95.0, 95.0, 95.0, 95.0, [], db_path=db_path)

    history = db.get_score_history("repo-a", db_path=db_path)
    assert history[0]["overall_score"] == 95.0
    assert history[1]["overall_score"] == 40.0
