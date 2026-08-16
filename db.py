import json
import os
from datetime import UTC, datetime

import libsql_client

# Defaults to a local file — no credentials needed for local dev or tests.
# Production sets DB_URL to a libsql://... Turso URL and DB_AUTH_TOKEN to a
# real token, which gives the exact same API but with storage that survives
# a redeploy instead of living on Render's ephemeral container disk.
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


def _client(db_url: str | None = None, auth_token: str | None = None) -> libsql_client.Client:
    url = db_url or DB_URL
    token = auth_token if auth_token is not None else DB_AUTH_TOKEN
    kwargs = {"auth_token": token} if token else {}
    return libsql_client.create_client_sync(url, **kwargs)


def save_score_run(
    repo: str,
    overall_score: float,
    blast_radius_score: float,
    recovery_score: float,
    redundancy_score: float,
    degradation_score: float,
    findings: list[dict],
    db_url: str | None = None,
    auth_token: str | None = None,
) -> int | None:
    """
    `findings` is plain dicts, already including any remediation text — this
    module deliberately knows nothing about ScoreResult or the LLM layer, it
    just persists whatever finished JSON it's handed.
    """
    with _client(db_url, auth_token) as client:
        client.execute(_SCHEMA)
        result = client.execute(
            """
            INSERT INTO score_runs
                (repo, overall_score, blast_radius_score, recovery_score,
                 redundancy_score, degradation_score, findings_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                repo,
                overall_score,
                blast_radius_score,
                recovery_score,
                redundancy_score,
                degradation_score,
                json.dumps(findings),
                datetime.now(UTC).isoformat(),
            ],
        )
        return result.last_insert_rowid


def get_score_history(
    repo: str, limit: int = 20, db_url: str | None = None, auth_token: str | None = None
) -> list[dict]:
    with _client(db_url, auth_token) as client:
        client.execute(_SCHEMA)
        result = client.execute(
            "SELECT * FROM score_runs WHERE repo = ? ORDER BY created_at DESC LIMIT ?",
            [repo, limit],
        )
        return [row.asdict() for row in result.rows]
