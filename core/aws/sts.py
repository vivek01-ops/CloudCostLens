"""STS adapter: identity verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.aws.retry import RetryPolicy, retry_call


@dataclass(frozen=True)
class CallerIdentity:
    account: str
    arn: str
    user_id: str


class STSAdapter:
    """Thin, retrying wrapper over the STS API."""

    def __init__(
        self,
        client: Any,
        policy: RetryPolicy | None = None,
        *,
        region: str | None = None,
    ):
        self._client = client
        self._policy = policy or RetryPolicy()
        self._region = region or getattr(client.meta, "region_name", None)

    def get_caller_identity(self) -> CallerIdentity:
        response = retry_call(
            self._client.get_caller_identity,
            policy=self._policy,
            operation="GetCallerIdentity",
            region=self._region,
        )
        return CallerIdentity(
            account=response.get("Account", ""),
            arn=response.get("Arn", ""),
            user_id=response.get("UserId", ""),
        )
