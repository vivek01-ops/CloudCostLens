"""PostgreSQL advisory locks.

Used to prevent overlapping scans for the same ``(account, scan_type)``. On non-PostgreSQL
dialects (e.g. SQLite) locking is a no-op so unit tests can run without a server.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

_NAMESPACE = 0x43434C01  # "CCL\x01"


def _is_postgres(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def _lock_key(account_id: uuid.UUID, scan_type: str) -> int:
    """Derive a stable 63-bit lock key from an account id and scan type."""
    digest = uuid.uuid5(uuid.NAMESPACE_OID, f"{account_id}:{scan_type}")
    return digest.int % (2**63)


def try_advisory_lock(session: Session, account_id: uuid.UUID, scan_type: str) -> bool:
    """Try to acquire a session-level advisory lock. Returns True if acquired."""
    if not _is_postgres(session):
        return True
    acquired = session.execute(
        text("SELECT pg_try_advisory_lock(:ns, :key)"),
        {"ns": _NAMESPACE & 0x7FFFFFFF, "key": _lock_key(account_id, scan_type) % (2**31)},
    ).scalar()
    return bool(acquired)


def advisory_unlock(session: Session, account_id: uuid.UUID, scan_type: str) -> None:
    """Release a previously acquired advisory lock (best effort)."""
    if not _is_postgres(session):
        return
    session.execute(
        text("SELECT pg_advisory_unlock(:ns, :key)"),
        {"ns": _NAMESPACE & 0x7FFFFFFF, "key": _lock_key(account_id, scan_type) % (2**31)},
    )
