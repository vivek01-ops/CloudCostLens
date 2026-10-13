"""Worker database session access.

A thin seam over the core session factory so worker tests can substitute a session scope.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from core.db.session import get_session
from sqlalchemy.orm import Session


@contextmanager
def worker_session() -> Iterator[Session]:
    """Provide a transactional session for a worker pass."""
    with get_session() as session:
        yield session
