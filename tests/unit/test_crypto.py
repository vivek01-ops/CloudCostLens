"""Encryption-at-rest tests for connector secrets."""

from __future__ import annotations

from core.config import get_settings
from core.security import decrypt, encrypt
from cryptography.fernet import Fernet


def test_round_trip() -> None:
    secret = "external-id-abc-123"
    token = encrypt(secret)
    assert token != secret
    assert decrypt(token) == secret


def test_ciphertext_differs_each_time() -> None:
    assert encrypt("same") != encrypt("same")


def test_uses_configured_key() -> None:
    settings = get_settings()
    settings.fernet_key = Fernet.generate_key().decode()
    # Clear the cached Fernet so the new key is used, then verify decrypt still works.
    from core.security import crypto

    crypto._fernet.cache_clear()
    token = encrypt("value")
    assert decrypt(token) == "value"
    settings.fernet_key = None
    crypto._fernet.cache_clear()
