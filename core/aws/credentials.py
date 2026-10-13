"""Temporary AWS credentials via STS role assumption.

Customer accounts are accessed exclusively through ``sts:AssumeRole`` with a required
external ID. No long-lived customer keys are stored. Assumed credentials are cached in
memory until shortly before they expire to avoid an STS call per API request.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from core.aws.errors import AwsError
from core.logging import get_logger

if TYPE_CHECKING:
    from core.models.cloud import CloudAccount

log = get_logger("core.aws.credentials")

_DEFAULT_SESSION_NAME = "cloudcostlens-discovery"
_EXPIRY_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class AssumedCredentials:
    """Temporary credentials returned by STS."""

    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: datetime | None

    def is_valid(self, *, now: datetime | None = None, skew: timedelta = _EXPIRY_SKEW) -> bool:
        if self.expiration is None:
            return True
        current = now or datetime.now(UTC)
        return self.expiration - skew > current

    def as_session_kwargs(self) -> dict[str, str]:
        return {
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "aws_session_token": self.session_token,
        }


def _parse_expiration(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return None


def assume_role(
    *,
    role_arn: str,
    external_id: str,
    sts_client: Any,
    session_name: str = _DEFAULT_SESSION_NAME,
    duration_seconds: int = 3600,
) -> AssumedCredentials:
    """Call ``sts:AssumeRole`` and return the temporary credentials.

    ``sts_client`` is injected so tests can supply a Stubber-wrapped client.
    """
    response = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
        ExternalId=external_id,
        DurationSeconds=duration_seconds,
    )
    creds = response.get("Credentials") or {}
    missing = [k for k in ("AccessKeyId", "SecretAccessKey", "SessionToken") if not creds.get(k)]
    if missing:
        raise AwsError(
            "STS AssumeRole response was missing credential fields",
            code="MalformedAssumeRoleResponse",
        )
    return AssumedCredentials(
        access_key_id=creds["AccessKeyId"],
        secret_access_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
        expiration=_parse_expiration(creds.get("Expiration")),
    )


class AssumeRoleCredentialCache:
    """Thread-safe in-memory cache of assumed credentials keyed by role + external ID."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str], AssumedCredentials] = {}

    def get(
        self,
        *,
        role_arn: str,
        external_id: str,
        sts_client: Any,
        session_name: str = _DEFAULT_SESSION_NAME,
        duration_seconds: int = 3600,
        now: datetime | None = None,
    ) -> AssumedCredentials:
        key = (role_arn, external_id)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached.is_valid(now=now):
                return cached
        # Assume outside the lock: STS calls are network-bound and slow.
        credentials = assume_role(
            role_arn=role_arn,
            external_id=external_id,
            sts_client=sts_client,
            session_name=session_name,
            duration_seconds=duration_seconds,
        )
        with self._lock:
            self._cache[key] = credentials
        return credentials

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


def get_credential_cache() -> AssumeRoleCredentialCache:
    """Return the process-wide credential cache."""
    return _CACHE


_CACHE = AssumeRoleCredentialCache()


def cache_key_for_account(account: CloudAccount, external_id: str) -> tuple[str, str]:
    """Return a stable cache key for an account (never logs the external ID)."""
    return (account.role_arn or "", external_id)
