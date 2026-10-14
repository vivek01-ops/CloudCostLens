"""Small SQLite persistence layer for CloudCostLens.

Keeps state that must survive a process restart (and, later, be shared across
gunicorn workers) without adding a database dependency: the stdlib ``sqlite3``
module is enough. Today it backs auth rate limiting; session persistence and any
future cached snapshots live here too.

The database lives in ``DATA_DIR`` (default ``./data``) so it can be bind-mounted
as a Docker volume. Connections are opened per operation — SQLite handles the
serialization, and WAL keeps concurrent readers from blocking writers.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import threading
import time

_LOCK = threading.Lock()
_DB_PATH: str | None = None


def init(data_dir: str) -> None:
    """Create the data directory, database file and schema. Safe to call twice."""
    global _DB_PATH
    os.makedirs(data_dir, exist_ok=True)
    _DB_PATH = os.path.join(data_dir, "cloudcostlens.db")
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rate_events (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                key  TEXT    NOT NULL,
                at   REAL    NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_key_at ON rate_events(key, at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                sid               TEXT PRIMARY KEY,
                provider          TEXT    NOT NULL,
                identity_json     TEXT,
                subscription_json TEXT,
                created_at        REAL    NOT NULL
            )
            """
        )


@contextlib.contextmanager
def _db():
    if _DB_PATH is None:
        raise RuntimeError("store.init() must be called before using the database")
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_session(sid: str, state: dict) -> None:
    """Upsert the lightweight login state for a session so it survives restarts."""
    with _LOCK, _db() as conn:
        conn.execute(
            """
            INSERT INTO sessions (sid, provider, identity_json, subscription_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sid) DO UPDATE SET
                provider = excluded.provider,
                identity_json = excluded.identity_json,
                subscription_json = excluded.subscription_json,
                created_at = excluded.created_at
            """,
            (
                sid,
                state.get("provider") or "",
                json.dumps(state.get("identity") or None),
                json.dumps(state.get("subscription") or None),
                time.time(),
            ),
        )


def load_session(sid: str) -> dict | None:
    """Return the persisted login state for a session id, or None."""
    with _LOCK, _db() as conn:
        row = conn.execute(
            "SELECT provider, identity_json, subscription_json FROM sessions WHERE sid = ?",
            (sid,),
        ).fetchone()
    if row is None:
        return None
    provider, identity_json, subscription_json = row
    state: dict = {"provider": provider}
    for key, raw in (("identity", identity_json), ("subscription", subscription_json)):
        if raw:
            try:
                state[key] = json.loads(raw)
            except ValueError:
                pass
    return state


def delete_session(sid: str) -> None:
    with _LOCK, _db() as conn:
        conn.execute("DELETE FROM sessions WHERE sid = ?", (sid,))


def prune_sessions(max_age_seconds: int) -> int:
    """Delete sessions older than max_age. Returns the number removed."""
    cutoff = time.time() - max_age_seconds
    with _LOCK, _db() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
        return cur.rowcount


def ping() -> bool:
    """Return True if the database file is reachable and queryable."""
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


def rate_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Sliding-window limiter. Returns (allowed, retry_after_seconds).

    Records one hit for ``key`` when allowed. When the limit is exceeded the hit
    is not recorded and ``retry_after`` (seconds until the oldest hit ages out)
    is returned so the caller can populate ``Retry-After``.
    """
    now = time.time()
    cutoff = now - window_seconds
    with _LOCK, _db() as conn:
        conn.execute("DELETE FROM rate_events WHERE at < ?", (cutoff,))
        count = conn.execute(
            "SELECT COUNT(*) FROM rate_events WHERE key = ? AND at >= ?", (key, cutoff)
        ).fetchone()[0]
        if count >= limit:
            oldest = conn.execute(
                "SELECT MIN(at) FROM rate_events WHERE key = ?", (key,)
            ).fetchone()[0]
            retry = max(1, int(window_seconds - (now - (oldest or now))) + 1)
            return False, retry
        conn.execute("INSERT INTO rate_events (key, at) VALUES (?, ?)", (key, now))
        return True, 0
