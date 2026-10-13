"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from core.db.session import get_sessionmaker
from fastapi import Depends
from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    """Yields a transactional SQLAlchemy session per request."""
    db = get_sessionmaker()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Placeholder principal for Milestone 1. Authentication and RBAC land in Milestone 6;
# until then the web shell and health/meta endpoints operate without an identity.
DemoSession = Depends(get_db)