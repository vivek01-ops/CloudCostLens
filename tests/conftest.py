"""Shared pytest fixtures and environment setup."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _test_env() -> Iterator[None]:
    """Force a deterministic test environment before settings are cached."""
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("DEMO_MODE", "true")

    from core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
