"""EC2 adapter: region enumeration and instance discovery.

Only business-relevant metadata is extracted. Public/private IP addresses and DNS names
are deliberately **not** collected and are filtered out during normalization.
"""

from __future__ import annotations

from typing import Any

from core.aws.models import DiscoveredResource, RegionInfo
from core.aws.retry import RetryPolicy, retry_call
from core.models.enums import ResourceType

# Tag keys (lowercased) used to derive environment and owner.
_ENVIRONMENT_TAGS = ("environment", "env", "stage")
_OWNER_TAGS = ("owner", "owneremail", "team", "owneremailaddress")

# Fields that must never be persisted (business-plane network identifiers).
_EXCLUDED_FIELDS = frozenset(
    {
        "PrivateIpAddress",
        "PublicIpAddress",
        "PublicDnsName",
        "PrivateDnsName",
        "NetworkInterfaces",
    }
)

_MAX_RESULTS = 1000


def _tags_to_dict(tags: list[dict[str, str]] | None) -> dict[str, str]:
    if not tags:
        return {}
    return {t["Key"]: t["Value"] for t in tags if "Key" in t}


def _lookup_tag(tags: dict[str, str], names: tuple[str, ...]) -> str | None:
    lowered = {k.lower(): v for k, v in tags.items()}
    for name in names:
        if lowered.get(name):
            return lowered[name]
    return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:  # pragma: no cover - defensive
        return str(value)


def normalize_instance(
    instance: dict[str, Any],
    *,
    region: str,
    account_id: str | None = None,
) -> DiscoveredResource:
    """Map a raw EC2 instance dict into a :class:`DiscoveredResource`."""
    instance_id = instance.get("InstanceId", "")
    tags = _tags_to_dict(instance.get("Tags"))
    attributes: dict[str, object] = {
        "instance_type": instance.get("InstanceType"),
        "availability_zone": (instance.get("Placement") or {}).get("AvailabilityZone"),
        "vpc_id": instance.get("VpcId"),
        "subnet_id": instance.get("SubnetId"),
        "architecture": instance.get("Architecture"),
        "platform_details": instance.get("PlatformDetails"),
        "launch_time": _iso(instance.get("LaunchTime")),
        "tenancy": instance.get("Tenancy"),
    }
    attributes = {k: v for k, v in attributes.items() if v is not None}
    # Defensive: drop any excluded field even if a future AWS field slips in.
    for excluded in _EXCLUDED_FIELDS:
        attributes.pop(excluded, None)

    arn = None
    if account_id and instance_id:
        arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"

    return DiscoveredResource(
        resource_type=ResourceType.EC2_INSTANCE,
        resource_id=instance_id,
        region=region,
        arn=arn,
        name=_lookup_tag(tags, ("name",)) or None,
        state=(instance.get("State") or {}).get("Name"),
        environment=_lookup_tag(tags, _ENVIRONMENT_TAGS),
        owner=_lookup_tag(tags, _OWNER_TAGS),
        tags=tags,
        attributes=attributes,
    )


class EC2Adapter:
    """Retrying, paginated wrapper over the EC2 API."""

    def __init__(
        self,
        client: Any,
        region: str,
        *,
        account_id: str | None = None,
        policy: RetryPolicy | None = None,
    ) -> None:
        self._client = client
        self._region = region
        self._account_id = account_id
        self._policy = policy or RetryPolicy()

    def describe_regions(self) -> list[RegionInfo]:
        response = retry_call(
            lambda: self._client.describe_regions(AllRegions=True),
            policy=self._policy,
            operation="DescribeRegions",
            region=self._region,
        )
        regions = []
        for entry in response.get("Regions", []):
            name = entry.get("RegionName")
            if not name:
                continue
            regions.append(
                RegionInfo(name=name, opt_in_status=entry.get("OptInStatus", "opt-in-not-required"))
            )
        return sorted(regions, key=lambda r: r.name)

    def describe_instances(self) -> list[DiscoveredResource]:
        """Enumerate every instance in the region, following pagination."""
        discovered: list[DiscoveredResource] = []
        next_token: str | None = None
        while True:
            params: dict[str, Any] = {"MaxResults": _MAX_RESULTS}
            if next_token:
                params["NextToken"] = next_token
            response = retry_call(
                lambda p=params: self._client.describe_instances(**p),
                policy=self._policy,
                operation="DescribeInstances",
                region=self._region,
            )
            for reservation in response.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    if not instance.get("InstanceId"):
                        continue
                    discovered.append(
                        normalize_instance(
                            instance,
                            region=self._region,
                            account_id=self._account_id,
                        )
                    )
            next_token = response.get("NextToken")
            if not next_token:
                break
        return discovered
