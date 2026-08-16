"""One-off manual smoke test: writes a real row to Turso and reads it back."""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402

print(f"DB_URL: {db.DB_URL}")
print(f"DB_AUTH_TOKEN set: {bool(db.DB_AUTH_TOKEN)}")

try:
    row_id = db.save_score_run(
        "kizuna/turso-smoke-test",
        99.9, 99.9, 99.9, 99.9, 99.9,
        [{"severity": "low", "node_id": "smoke-test", "message": "connectivity check", "remediation": None}],
    )
    print(f"write succeeded, row id: {row_id}")

    history = db.get_score_history("kizuna/turso-smoke-test")
    print(f"read back {len(history)} row(s)")
    print(history[0])
except Exception:
    print("SMOKE TEST FAILED:")
    traceback.print_exc()
    raise
