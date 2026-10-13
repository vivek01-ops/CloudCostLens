"""Error classification tests."""

from __future__ import annotations

from botocore.exceptions import EndpointConnectionError, NoCredentialsError
from core.aws.errors import (
    AwsAccessDenied,
    AwsAuthError,
    AwsNotFoundError,
    AwsRegionUnavailable,
    AwsThrottlingError,
    AwsTransientError,
    AwsValidationError,
    classify_exception,
)
from tests.unit.aws.helpers import client_error


def test_throttling_is_retryable() -> None:
    error = classify_exception(client_error("Throttling"), region="us-east-1")
    assert isinstance(error, AwsThrottlingError)
    assert error.retryable is True
    assert error.code == "Throttling"


def test_http_429_is_throttling() -> None:
    error = classify_exception(client_error("SomethingNew", status=429))
    assert isinstance(error, AwsThrottlingError)
    assert error.retryable is True


def test_access_denied_is_not_retryable() -> None:
    error = classify_exception(client_error("UnauthorizedOperation"))
    assert isinstance(error, AwsAccessDenied)
    assert error.retryable is False


def test_auth_failure_is_not_retryable() -> None:
    error = classify_exception(client_error("ExpiredToken"))
    assert isinstance(error, AwsAuthError)


def test_region_unavailable_is_distinct() -> None:
    error = classify_exception(client_error("OptInRequired"))
    assert isinstance(error, AwsRegionUnavailable)


def test_not_found_is_non_retryable() -> None:
    error = classify_exception(client_error("InvalidInstanceID.NotFound"))
    assert isinstance(error, AwsNotFoundError)


def test_validation_is_non_retryable() -> None:
    error = classify_exception(client_error("ValidationError"))
    assert isinstance(error, AwsValidationError)


def test_server_error_is_transient() -> None:
    error = classify_exception(client_error("InternalError", status=503))
    assert isinstance(error, AwsTransientError)
    assert error.retryable is True


def test_network_error_is_transient() -> None:
    exc = EndpointConnectionError(endpoint_url="https://ec2.us-east-1.amazonaws.com")
    error = classify_exception(exc)
    assert isinstance(error, AwsTransientError)
    assert error.retryable is True


def test_missing_credentials_is_auth_error() -> None:
    error = classify_exception(NoCredentialsError())
    assert isinstance(error, AwsAuthError)
    assert error.retryable is False
