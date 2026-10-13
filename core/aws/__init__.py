"""AWS adapters.

Public entry points for read-only discovery. Adapters accept injected clients so they can
be exercised with Botocore ``Stubber`` in tests and never require live credentials.
"""

from core.aws.credentials import (
    AssumedCredentials,
    AssumeRoleCredentialCache,
    assume_role,
    get_credential_cache,
)
from core.aws.ec2 import EC2Adapter, normalize_instance
from core.aws.errors import (
    AwsAccessDenied,
    AwsAuthError,
    AwsError,
    AwsNonRetryableError,
    AwsNotFoundError,
    AwsRegionUnavailable,
    AwsThrottlingError,
    AwsTransientError,
    AwsValidationError,
    classify_exception,
)
from core.aws.models import DiscoveredResource, RegionInfo
from core.aws.retry import RetryPolicy, retry_call
from core.aws.session import AwsClientFactory, build_account_session, build_client_factory
from core.aws.sts import CallerIdentity, STSAdapter

__all__ = [
    "AssumeRoleCredentialCache",
    "AssumedCredentials",
    "AwsAccessDenied",
    "AwsAuthError",
    "AwsClientFactory",
    "AwsError",
    "AwsNonRetryableError",
    "AwsNotFoundError",
    "AwsRegionUnavailable",
    "AwsThrottlingError",
    "AwsTransientError",
    "AwsValidationError",
    "CallerIdentity",
    "DiscoveredResource",
    "EC2Adapter",
    "RegionInfo",
    "RetryPolicy",
    "STSAdapter",
    "assume_role",
    "build_account_session",
    "build_client_factory",
    "classify_exception",
    "get_credential_cache",
    "normalize_instance",
    "retry_call",
]
