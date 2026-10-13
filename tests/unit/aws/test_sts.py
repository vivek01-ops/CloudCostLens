"""STS adapter tests."""

from __future__ import annotations

from botocore.stub import Stubber
from core.aws.retry import RetryPolicy
from core.aws.sts import STSAdapter
from tests.unit.aws.helpers import make_client

FAST = RetryPolicy(max_attempts=3, base_delay=0.0)


def test_get_caller_identity() -> None:
    client = make_client("sts")
    stubber = Stubber(client)
    stubber.add_response(
        "get_caller_identity",
        {
            "UserId": "AIDAEXAMPLE",
            "Account": "111122223333",
            "Arn": "arn:aws:sts::111122223333:assumed-role/CloudCostLensReadOnly/session",
        },
    )
    with stubber:
        identity = STSAdapter(client, FAST, region="us-east-1").get_caller_identity()
    assert identity.account == "111122223333"
    assert "CloudCostLensReadOnly" in identity.arn
