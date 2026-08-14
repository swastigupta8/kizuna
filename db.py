import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from score import ScoreResult

DB_PATH = Path(__file__).parent / "kizuna.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS score_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    overall_score REAL NOT NULL,
    blast_radius_score REAL NOT NULL,
    recovery_score REAL NOT NULL,
    redundancy_score REAL NOT NULL,
    degradation_score REAL NOT NULL,
    findings_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def save_score_run(repo: str, result: ScoreResult, db_path: Path | None = None) -> int:
    conn = get_connection(db_path)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO score_runs
                (repo, overall_score, blast_radius_score, recovery_score,
                 redundancy_score, degradation_score, findings_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo,
                result.overall,
                result.blast_radius,
                result.recovery,
                result.redundancy,
                result.degradation,
                json.dumps([finding.model_dump() for finding in result.findings]),
                datetime.now(UTC).isoformat(),
            ),
        )
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_score_history(repo: str, limit: int = 20, db_path: Path | None = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM score_runs WHERE repo = ? ORDER BY created_at DESC LIMIT ?",
        (repo, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
