"""Security helpers (encryption at rest for sensitive connector values)."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.fernet_key or Fernet.generate_key()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    """Encrypt a sensitive value (e.g. an AWS external ID) at rest."""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a value previously encrypted with :func:`encrypt`."""
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")