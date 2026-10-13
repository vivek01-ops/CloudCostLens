"""SQLAlchemy engine factory."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Return a process-wide SQLAlchemy engine.

    ``pool_pre_ping`` guards against stale connections; ``future`` semantics are the
    default in SQLAlchemy 2.x.
    """
    settings = get_settings()
    kwargs: dict[str, object] = {"pool_pre_ping": True, "future": True}
    if settings.database_url.startswith("postgresql"):
        kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_recycle": 1800})
    return create_engine(settings.database_url, **kwargs)
