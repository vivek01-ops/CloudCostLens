"""Credential provider / AssumeRole cache tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from botocore.stub import Stubber
from core.aws.credentials import AssumeRoleCredentialCache, assume_role
from tests.unit.aws.helpers import make_client


def _creds_response(expiration: datetime | None = None) -> dict:
    return {
        "Credentials": {
            "AccessKeyId": "ASIAEXAMPLEACCESSKEY",
            "SecretAccessKey": "examplesecretaccesskeyvalue",
            "SessionToken": "examplesessiontokenvalue",
            "Expiration": expiration or (datetime.now(UTC) + timedelta(hours=1)),
        }
    }


def test_assume_role_returns_credentials() -> None:
    client = make_client("sts")
    stubber = Stubber(client)
    stubber.add_response("assume_role", _creds_response())
    with stubber:
        creds = assume_role(
            role_arn="arn:aws:iam::111:role/r", external_id="abc", sts_client=client
        )
    assert creds.access_key_id == "ASIAEXAMPLEACCESSKEY"
    assert creds.as_session_kwargs()["aws_session_token"] == "examplesessiontokenvalue"
    assert creds.is_valid() is True


def test_expired_credentials_are_invalid() -> None:
    client = make_client("sts")
    stubber = Stubber(client)
    stubber.add_response("assume_role", _creds_response(datetime.now(UTC) - timedelta(minutes=1)))
    with stubber:
        creds = assume_role(
            role_arn="arn:aws:iam::111:role/r", external_id="abc", sts_client=client
        )
    assert creds.is_valid() is False


def test_cache_reuses_valid_credentials() -> None:
    client = make_client("sts")
    stubber = Stubber(client)
    # Only one response is queued: a second STS call would raise, proving the cache is used.
    stubber.add_response("assume_role", _creds_response())
    cache = AssumeRoleCredentialCache()
    with stubber:
        first = cache.get(role_arn="arn:aws:iam::111:role/r", external_id="abc", sts_client=client)
        second = cache.get(role_arn="arn:aws:iam::111:role/r", external_id="abc", sts_client=client)
    assert first == second
