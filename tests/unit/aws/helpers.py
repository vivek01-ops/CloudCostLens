"""Shared helpers for AWS adapter tests (Botocore Stubber)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

TEST_REGION = "us-east-1"


def make_client(service: str, region: str = TEST_REGION) -> Any:
    """Create a real boto3 client (no network until a Stubber intercepts calls)."""
    return boto3.client(
        service,
        region_name=region,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        aws_session_token="testing",
    )


def client_error(
    code: str, *, status: int = 400, operation: str = "DescribeInstances"
) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": f"{code} occurred"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation,
    )


def instance(
    instance_id: str = "i-0123456789abcdef0",
    *,
    name: str | None = "web-01",
    state: str = "running",
    environment: str | None = "production",
    owner: str | None = "platform",
    instance_type: str = "m5.large",
    include_network: bool = True,
) -> dict[str, Any]:
    tags = []
    if name is not None:
        tags.append({"Key": "Name", "Value": name})
    if environment is not None:
        tags.append({"Key": "Environment", "Value": environment})
    if owner is not None:
        tags.append({"Key": "Owner", "Value": owner})
    item: dict[str, Any] = {
        "InstanceId": instance_id,
        "InstanceType": instance_type,
        "State": {"Name": state},
        "Placement": {"AvailabilityZone": f"{TEST_REGION}a"},
        "Tags": tags,
        "LaunchTime": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "VpcId": "vpc-0abc",
        "SubnetId": "subnet-0abc",
        "Architecture": "x86_64",
        "PlatformDetails": "Linux/UNIX",
    }
    if include_network:
        item.update(
            {
                "PrivateIpAddress": "10.0.0.10",
                "PublicIpAddress": "203.0.113.10",
                "PublicDnsName": "ec2-203-0-113-10.compute.amazonaws.com",
                "PrivateDnsName": "ip-10-0-0-10.ec2.internal",
            }
        )
    return item


def reservations(*instances: dict[str, Any], next_token: str | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "Reservations": [{"ReservationId": "r-1", "Instances": list(instances)}]
    }
    if next_token:
        response["NextToken"] = next_token
    return response
