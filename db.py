import json
import os
import sqlite3
from datetime import UTC, datetime

import turso_serverless

# Defaults to a local file — no credentials needed for local dev or tests.
# Production sets DB_URL to a libsql://... Turso URL and DB_AUTH_TOKEN to a
# real token, which gives the exact same effective API but with storage that
# survives a redeploy instead of living on Render's ephemeral container disk.
DB_URL = os.environ.get("DB_URL", "file:kizuna.db")
DB_AUTH_TOKEN = os.environ.get("DB_AUTH_TOKEN")

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


def _is_remote(url: str) -> bool:
    return url.startswith("libsql://") or url.startswith("https://")


def _connect(db_url: str | None = None, auth_token: str | None = None):
    """
    Remote (libsql://...) goes through turso_serverless — Turso's HTTP-based
    driver. Anything else is treated as a local sqlite3 file, so local dev
    and tests never need a Turso account. Both are DB-API-2.0-shaped enough
    that everything downstream (execute/fetchall/description/lastrowid)
    works the same either way.
    """
    url = db_url or DB_URL
    if _is_remote(url):
        token = auth_token if auth_token is not None else DB_AUTH_TOKEN
        conn = turso_serverless.connect(url, auth_token=token)
    else:
        conn = sqlite3.connect(url.removeprefix("file:"))
    conn.execute(_SCHEMA)
    _ensure_graph_column(conn)
    return conn


def _ensure_graph_column(conn) -> None:
    """
    `graph_json` was added after the table already existed in production, so
    CREATE TABLE IF NOT EXISTS alone won't add it to an existing database —
    needs an actual ALTER TABLE. Failing means the column's already there,
    which is the expected, common case after the first run.
    """
    try:
        conn.execute("ALTER TABLE score_runs ADD COLUMN graph_json TEXT")
    except Exception:
        pass


def _fetch_as_dicts(cursor) -> list[dict]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def save_score_run(
    repo: str,
    overall_score: float,
    blast_radius_score: float,
    recovery_score: float,
    redundancy_score: float,
    degradation_score: float,
    findings: list[dict],
    graph: dict | None = None,
    db_url: str | None = None,
    auth_token: str | None = None,
) -> int | None:
    """
    `findings` is plain dicts, already including any remediation text, and
    `graph` is the parsed ArchitectureGraph as a plain dict (nodes + edges) —
    this module deliberately knows nothing about ScoreResult, Finding, or
    ArchitectureGraph as types, it just persists whatever finished JSON it's
    handed.
    """
    conn = _connect(db_url, auth_token)
    try:
        cursor = conn.execute(
            """
            INSERT INTO score_runs
                (repo, overall_score, blast_radius_score, recovery_score,
                 redundancy_score, degradation_score, findings_json, graph_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo,
                overall_score,
                blast_radius_score,
                recovery_score,
                redundancy_score,
                degradation_score,
                json.dumps(findings),
                json.dumps(graph) if graph is not None else None,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_score_history(
    repo: str, limit: int = 20, db_url: str | None = None, auth_token: str | None = None
) -> list[dict]:
    conn = _connect(db_url, auth_token)
    try:
        cursor = conn.execute(
            "SELECT * FROM score_runs WHERE repo = ? ORDER BY created_at DESC LIMIT ?",
            (repo, limit),
        )
        return _fetch_as_dicts(cursor)
    finally:
        conn.close()
