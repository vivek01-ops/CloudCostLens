"""Transport-neutral DTOs returned by AWS adapters.

Adapters return these plain dataclasses rather than boto3 response dictionaries so that
ingestion, rules, and tests never depend on the wire format.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.models.enums import ResourceType


@dataclass(frozen=True)
class RegionInfo:
    """A single AWS region and whether it can be scanned."""

    name: str
    opt_in_status: str

    @property
    def is_available(self) -> bool:
        """True when the region is enabled (not ``not-opted-in``)."""
        return self.opt_in_status != "not-opted-in"


@dataclass(frozen=True)
class DiscoveredResource:
    """Normalized inventory record produced by an adapter.

    Note: business-plane identifiers (public/private IP addresses, DNS names) are
    intentionally never populated — see :mod:`core.aws.ec2`.
    """

    resource_type: ResourceType
    resource_id: str
    region: str
    arn: str | None = None
    name: str | None = None
    state: str | None = None
    environment: str | None = None
    owner: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, object] = field(default_factory=dict)

    @property
    def identity(self) -> tuple[ResourceType, str, str]:
        """The idempotency key: ``(resource_type, resource_id, region)``."""
        return (self.resource_type, self.resource_id, self.region)
