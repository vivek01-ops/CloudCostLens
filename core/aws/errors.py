"""AWS error classification.

Adapters never let raw ``botocore`` exceptions escape: they classify failures into a small
set of domain errors with an explicit ``retryable`` flag so callers can decide whether to
back off or fail fast. This keeps retry logic and user-facing error handling uniform across
every AWS service.
"""

from __future__ import annotations

from typing import Any

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
    ReadTimeoutError,
)

# Error codes that indicate transient/throttling conditions: retry with backoff.
_THROTTLING_CODES = frozenset(
    {
        "Throttling",
        "ThrottlingException",
        "ThrottledException",
        "RequestThrottled",
        "RequestThrottledException",
        "RequestLimitExceeded",
        "TooManyRequestsException",
        "SlowDown",
        "LimitExceededException",
        "ProvisionedThroughputExceededException",
        "TransactionInProgressException",
    }
)

# Authentication/authorization failures: never retry, surface clearly.
_AUTH_CODES = frozenset(
    {
        "AuthFailure",
        "InvalidClientTokenId",
        "SignatureDoesNotMatch",
        "UnrecognizedClientException",
        "InvalidAccessKeyId",
        "ExpiredToken",
        "ExpiredTokenException",
        "TokenRefreshRequired",
        "InvalidSignatureException",
        "InvalidClientToken",
    }
)

_ACCESS_DENIED_CODES = frozenset(
    {
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
        "AuthorizationError",
        "AccessDeniedError",
        "MissingAction",
        "Forbidden",
    }
)

# A region that is not opted-in / disabled. The scan should skip it, not fail.
_REGION_UNAVAILABLE_CODES = frozenset(
    {
        "OptInRequired",
        "UnavailableRegion",
        "RegionDisabledException",
        "InvalidRegion",
        "InvalidParameterValue",
    }
)

# AssumeRole / validation problems that will not succeed on retry.
_VALIDATION_CODES = frozenset(
    {
        "MalformedPolicyDocument",
        "ValidationError",
        "InvalidParameterCombination",
        "MissingParameter",
        "ParameterNotFound",
    }
)

_NOT_FOUND_CODES = frozenset(
    {
        "NoSuchEntity",
        "NotFoundException",
        "ResourceNotFoundException",
        "InvalidInstanceID.NotFound",
        "InvalidVpcID.NotFound",
    }
)

# HTTP status codes that imply a transient server-side condition.
_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})

_NETWORK_EXCEPTIONS = (
    EndpointConnectionError,
    ConnectTimeoutError,
    ReadTimeoutError,
    ConnectionClosedError,
)


class AwsError(Exception):
    """Base class for classified AWS errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        operation: str | None = None,
        region: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.operation = operation
        self.region = region
        self.retryable = retryable

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        parts = [self.message]
        if self.operation:
            parts.append(f"operation={self.operation}")
        if self.code:
            parts.append(f"code={self.code}")
        if self.region:
            parts.append(f"region={self.region}")
        return " ".join(parts)


class AwsAuthError(AwsError):
    """Credentials are missing, invalid, or expired (non-retryable)."""


class AwsAccessDenied(AwsError):
    """The identity lacks the required permission (non-retryable)."""


class AwsThrottlingError(AwsError):
    """The request was throttled (retryable)."""


class AwsTransientError(AwsError):
    """A transient network/server error (retryable)."""


class AwsRegionUnavailable(AwsError):
    """The region is not opted-in or otherwise unavailable (skip)."""


class AwsNotFoundError(AwsError):
    """The requested resource does not exist (non-retryable)."""


class AwsValidationError(AwsError):
    """The request was rejected as invalid (non-retryable)."""


class AwsNonRetryableError(AwsError):
    """Any other evaluated non-retryable AWS error."""


def _client_error_parts(exc: ClientError) -> tuple[str | None, str, int | None, str | None]:
    response: dict[str, Any] = exc.response or {}
    error = response.get("Error", {}) or {}
    code = error.get("Code")
    message = error.get("Message") or code or "AWS request failed"
    meta = response.get("ResponseMetadata", {}) or {}
    status = meta.get("HTTPStatusCode")
    operation = getattr(exc, "operation_name", None)
    return code, message, status, operation


def classify_exception(
    exc: BaseException,
    *,
    operation: str | None = None,
    region: str | None = None,
) -> AwsError:
    """Translate any exception raised by botocore into a classified :class:`AwsError`."""
    if isinstance(exc, AwsError):
        return exc

    if isinstance(exc, ClientError):
        code, message, status, op = _client_error_parts(exc)
        op = op or operation
        return _classify_code(code, message, status, op, region)

    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return AwsAuthError(
            "AWS credentials are not configured for this environment",
            code=type(exc).__name__,
            operation=operation,
            region=region,
        )

    if isinstance(exc, _NETWORK_EXCEPTIONS):
        return AwsTransientError(
            f"Network error contacting AWS: {exc}",
            code=type(exc).__name__,
            operation=operation,
            region=region,
            retryable=True,
        )

    if isinstance(exc, BotoCoreError):
        return AwsTransientError(
            f"AWS client error: {exc}",
            code=type(exc).__name__,
            operation=operation,
            region=region,
            retryable=True,
        )

    return AwsNonRetryableError(
        str(exc) or "AWS request failed",
        code=type(exc).__name__,
        operation=operation,
        region=region,
    )


def _classify_code(
    code: str | None,
    message: str,
    status: int | None,
    operation: str | None,
    region: str | None,
) -> AwsError:
    kwargs = {"code": code, "operation": operation, "region": region}

    if code in _THROTTLING_CODES or status == 429:
        return AwsThrottlingError(message, retryable=True, **kwargs)
    if code in _AUTH_CODES:
        return AwsAuthError(message, **kwargs)
    if code in _ACCESS_DENIED_CODES:
        return AwsAccessDenied(message, **kwargs)
    if code in _REGION_UNAVAILABLE_CODES:
        return AwsRegionUnavailable(message, **kwargs)
    if code in _NOT_FOUND_CODES:
        return AwsNotFoundError(message, **kwargs)
    if code in _VALIDATION_CODES:
        return AwsValidationError(message, **kwargs)

    if status in _RETRYABLE_HTTP:
        return AwsTransientError(message, retryable=True, **kwargs)

    return AwsNonRetryableError(message, **kwargs)
