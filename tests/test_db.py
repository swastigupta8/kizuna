import db
from score import ScoreResult


def test_save_and_read_back_a_score_run(tmp_path):
    db_path = tmp_path / "test.db"
    result = ScoreResult(overall=72.5, blast_radius=65.0, recovery=88.0, redundancy=60.0, degradation=82.0)

    db.save_score_run("swastigupta8/kizuna-demo", result, db_path=db_path)
    history = db.get_score_history("swastigupta8/kizuna-demo", db_path=db_path)

    assert len(history) == 1
    assert history[0]["overall_score"] == 72.5
    assert history[0]["repo"] == "swastigupta8/kizuna-demo"


def test_history_is_scoped_to_the_requested_repo(tmp_path):
    db_path = tmp_path / "test.db"
    result = ScoreResult(overall=90.0, blast_radius=90.0, recovery=90.0, redundancy=90.0, degradation=90.0)

    db.save_score_run("repo-a", result, db_path=db_path)
    db.save_score_run("repo-b", result, db_path=db_path)

    assert len(db.get_score_history("repo-a", db_path=db_path)) == 1
    assert len(db.get_score_history("repo-b", db_path=db_path)) == 1
    assert len(db.get_score_history("repo-c", db_path=db_path)) == 0


def test_history_is_ordered_most_recent_first(tmp_path):
    db_path = tmp_path / "test.db"
    low = ScoreResult(overall=40.0, blast_radius=40.0, recovery=40.0, redundancy=40.0, degradation=40.0)
    high = ScoreResult(overall=95.0, blast_radius=95.0, recovery=95.0, redundancy=95.0, degradation=95.0)

    db.save_score_run("repo-a", low, db_path=db_path)
    db.save_score_run("repo-a", high, db_path=db_path)

    history = db.get_score_history("repo-a", db_path=db_path)
    assert history[0]["overall_score"] == 95.0
    assert history[1]["overall_score"] == 40.0
