"""boto3 session and client construction.

A single :class:`AwsClientFactory` is the seam between the domain and AWS: it resolves
credentials for an account (default chain for local development, or STS-assumed temporary
credentials for customer accounts) and builds clients with consistent timeouts and retry
configuration. Tests inject a factory that returns Stubber-wrapped clients.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config

from core.aws.credentials import AssumeRoleCredentialCache, get_credential_cache
from core.config import get_settings
from core.logging import get_logger

if TYPE_CHECKING:
    from core.models.cloud import CloudAccount

log = get_logger("core.aws.session")


def _client_config() -> Config:
    settings = get_settings()
    return Config(
        connect_timeout=settings.aws_connect_timeout_seconds,
        read_timeout=settings.aws_read_timeout_seconds,
        retries={"max_attempts": max(1, settings.aws_max_attempts), "mode": "standard"},
    )


class AwsClientFactory:
    """Creates service clients for a single boto3 session."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def __call__(self, service: str, region: str) -> Any:
        return self._session.client(service, region_name=region, config=_client_config())


def build_account_session(
    account: CloudAccount,
    *,
    external_id: str | None = None,
    region: str | None = None,
    base_session: Any | None = None,
    credential_cache: AssumeRoleCredentialCache | None = None,
) -> Any:
    """Return a boto3 Session for ``account``.

    - If the account has no ``role_arn``, the standard credential chain is used
      (local development).
    - Otherwise temporary credentials are obtained via STS AssumeRole using the
      (decrypted) external ID.
    """
    settings = get_settings()
    session_region = region or account.default_region or settings.aws_default_region
    base = base_session or boto3.session.Session(region_name=session_region)

    if not account.role_arn:
        return base

    if not external_id:
        from core.aws.errors import AwsAuthError

        raise AwsAuthError(
            "Account requires a role ARN but no external ID was provided",
            operation="AssumeRole",
            region=session_region,
        )

    cache = credential_cache or get_credential_cache()
    sts_client = base.client("sts", region_name=settings.aws_default_region)
    credentials = cache.get(
        role_arn=account.role_arn,
        external_id=external_id,
        sts_client=sts_client,
    )
    return boto3.session.Session(
        region_name=session_region,
        **credentials.as_session_kwargs(),
    )


def build_client_factory(
    account: CloudAccount,
    *,
    external_id: str | None = None,
    base_session: Any | None = None,
    credential_cache: AssumeRoleCredentialCache | None = None,
) -> AwsClientFactory:
    """Build the default :class:`AwsClientFactory` for an account."""
    session = build_account_session(
        account,
        external_id=external_id,
        base_session=base_session,
        credential_cache=credential_cache,
    )
    return AwsClientFactory(session)
