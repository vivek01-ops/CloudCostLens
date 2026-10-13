"""EC2 adapter tests using Botocore Stubber."""

from __future__ import annotations

import pytest
from botocore.stub import Stubber
from core.aws.ec2 import EC2Adapter, normalize_instance
from core.aws.errors import AwsAccessDenied, AwsRegionUnavailable
from core.aws.retry import RetryPolicy
from core.models.enums import ResourceType
from tests.unit.aws.helpers import instance, make_client, reservations

FAST = RetryPolicy(max_attempts=5, base_delay=0.0)


def test_normalize_instance_extracts_metadata() -> None:
    resource = normalize_instance(
        instance("i-1", name="api-01", environment="prod", owner="sre"),
        region="us-east-1",
        account_id="111122223333",
    )
    assert resource.resource_type is ResourceType.EC2_INSTANCE
    assert resource.resource_id == "i-1"
    assert resource.name == "api-01"
    assert resource.environment == "prod"
    assert resource.owner == "sre"
    assert resource.state == "running"
    assert resource.arn == "arn:aws:ec2:us-east-1:111122223333:instance/i-1"
    assert resource.attributes["instance_type"] == "m5.large"


def test_normalize_instance_excludes_network_identifiers() -> None:
    resource = normalize_instance(instance(), region="us-east-1", account_id="111")
    for forbidden in ("PrivateIpAddress", "PublicIpAddress", "PublicDnsName", "PrivateDnsName"):
        assert forbidden not in resource.attributes
    assert "10.0.0.10" not in str(resource.attributes)
    assert "203.0.113.10" not in str(resource.attributes)


def test_describe_instances_single_page() -> None:
    client = make_client("ec2")
    stubber = Stubber(client)
    stubber.add_response("describe_instances", reservations(instance("i-1"), instance("i-2")))
    with stubber:
        adapter = EC2Adapter(client, "us-east-1", account_id="111", policy=FAST)
        resources = adapter.describe_instances()
    assert {r.resource_id for r in resources} == {"i-1", "i-2"}


def test_describe_instances_follows_pagination() -> None:
    client = make_client("ec2")
    stubber = Stubber(client)
    stubber.add_response(
        "describe_instances", reservations(instance("i-1"), next_token="page-2")
    )
    stubber.add_response("describe_instances", reservations(instance("i-2")))
    with stubber:
        adapter = EC2Adapter(client, "us-east-1", account_id="111", policy=FAST)
        resources = adapter.describe_instances()
    assert {r.resource_id for r in resources} == {"i-1", "i-2"}


def test_describe_instances_retries_throttling() -> None:
    client = make_client("ec2")
    stubber = Stubber(client)
    stubber.add_client_error(
        "describe_instances", service_error_code="Throttling", http_status_code=400
    )
    stubber.add_response("describe_instances", reservations(instance("i-1")))
    with stubber:
        adapter = EC2Adapter(client, "us-east-1", account_id="111", policy=FAST)
        resources = adapter.describe_instances()
    assert [r.resource_id for r in resources] == ["i-1"]


def test_describe_instances_access_denied_raises() -> None:
    client = make_client("ec2")
    stubber = Stubber(client)
    stubber.add_client_error("describe_instances", service_error_code="UnauthorizedOperation")
    with stubber:
        adapter = EC2Adapter(client, "us-east-1", account_id="111", policy=FAST)
        with pytest.raises(AwsAccessDenied):
            adapter.describe_instances()


def test_describe_instances_region_unavailable_raises() -> None:
    client = make_client("ec2")
    stubber = Stubber(client)
    stubber.add_client_error("describe_instances", service_error_code="OptInRequired")
    with stubber:
        adapter = EC2Adapter(client, "ap-east-1", account_id="111", policy=FAST)
        with pytest.raises(AwsRegionUnavailable):
            adapter.describe_instances()


def test_describe_regions_reports_opt_in_status() -> None:
    client = make_client("ec2")
    stubber = Stubber(client)
    stubber.add_response(
        "describe_regions",
        {
            "Regions": [
                {
                    "RegionName": "us-east-1",
                    "OptInStatus": "opt-in-not-required",
                    "Endpoint": "ec2.us-east-1.amazonaws.com",
                },
                {
                    "RegionName": "ap-east-1",
                    "OptInStatus": "not-opted-in",
                    "Endpoint": "ec2.ap-east-1.amazonaws.com",
                },
            ]
        },
    )
    with stubber:
        adapter = EC2Adapter(client, "us-east-1", policy=FAST)
        regions = adapter.describe_regions()
    by_name = {r.name: r for r in regions}
    assert by_name["us-east-1"].is_available is True
    assert by_name["ap-east-1"].is_available is False
