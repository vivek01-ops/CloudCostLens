"""Idempotent inventory ingestion.

Resources are keyed by ``(cloud_account_id, resource_type, resource_id, region)``. Re-running
a scan updates mutable fields (state, tags, last_seen) and never creates duplicates, and a
failed scan never deletes existing inventory.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.aws.models import DiscoveredResource
from core.models.cloud import Resource
from core.models.enums import OptimizationStatus

DEFAULT_CURRENCY = "USD"


@dataclass(frozen=True)
class IngestionStats:
    """Outcome counts for a batch upsert."""

    created: int = 0
    updated: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated


def _dedupe(resources: Iterable[DiscoveredResource]) -> dict[tuple, DiscoveredResource]:
    """Collapse duplicate identities within a batch (last occurrence wins)."""
    unique: dict[tuple, DiscoveredResource] = {}
    for resource in resources:
        unique[resource.identity] = resource
    return unique


def upsert_resources(
    session: Session,
    *,
    organization_id: uuid.UUID,
    cloud_account_id: uuid.UUID,
    resources: Iterable[DiscoveredResource],
    seen_at: datetime | None = None,
) -> IngestionStats:
    """Upsert a batch of discovered resources for one account.

    Idempotent: existing rows are updated in place (preserving ``first_seen`` and analysis
    state); new rows are inserted. Returns created/updated counts.
    """
    timestamp = seen_at or datetime.now(UTC)
    unique = _dedupe(resources)
    if not unique:
        return IngestionStats()

    existing_keys = {
        (row.resource_type, row.resource_id, row.region)
        for row in session.execute(
            select(Resource.resource_type, Resource.resource_id, Resource.region).where(
                Resource.cloud_account_id == cloud_account_id
            )
        ).all()
    }

    rows: list[dict] = []
    created = 0
    updated = 0
    for resource in unique.values():
        if resource.identity in existing_keys:
            updated += 1
        else:
            created += 1
        rows.append(
            {
                "id": uuid.uuid4(),
                "organization_id": organization_id,
                "cloud_account_id": cloud_account_id,
                "resource_type": resource.resource_type,
                "resource_id": resource.resource_id,
                "region": resource.region,
                "arn": resource.arn,
                "name": resource.name,
                "state": resource.state,
                "environment": resource.environment,
                "owner": resource.owner,
                "tags": resource.tags,
                "attributes": resource.attributes,
                "currency": DEFAULT_CURRENCY,
                "optimization_status": OptimizationStatus.UNKNOWN,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "updated_at": timestamp,
            }
        )

    statement = pg_insert(Resource).values(rows)
    statement = statement.on_conflict_do_update(
        constraint="uq_resource_identity",
        set_={
            "arn": statement.excluded.arn,
            "name": statement.excluded.name,
            "state": statement.excluded.state,
            "environment": statement.excluded.environment,
            "owner": statement.excluded.owner,
            "tags": statement.excluded.tags,
            "attributes": statement.excluded.attributes,
            "last_seen": statement.excluded.last_seen,
            "updated_at": statement.excluded.updated_at,
        },
    )
    session.execute(statement)
    session.flush()
    return IngestionStats(created=created, updated=updated)


def count_resources(session: Session, *, cloud_account_id: uuid.UUID) -> int:
    """Return the number of resources currently stored for an account."""
    return int(
        session.execute(
            select(func.count()).select_from(Resource).where(
                Resource.cloud_account_id == cloud_account_id
            )
        ).scalar_one()
    )
