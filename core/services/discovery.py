"""Discovery orchestration.

Runs a read-only inventory scan for a single account and records its lifecycle in
``scan_runs``. Supports region enumeration, per-region isolation (one region failing does
not abort the scan), idempotent upserts, and an advisory lock that prevents overlapping
scans for the same account. A failed scan never deletes inventory.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.audit import (
    EVENT_ACCOUNT_CONNECTED,
    EVENT_ACCOUNT_VERIFICATION_FAILED,
    EVENT_SCAN_COMPLETED,
    EVENT_SCAN_FAILED,
    EVENT_SCAN_PARTIAL,
    EVENT_SCAN_STARTED,
    record_event,
)
from core.aws.ec2 import EC2Adapter
from core.aws.errors import AwsError, AwsRegionUnavailable
from core.aws.retry import RetryPolicy
from core.aws.session import build_client_factory
from core.aws.sts import STSAdapter
from core.db.locks import advisory_unlock, try_advisory_lock
from core.logging import get_logger
from core.models.cloud import CloudAccount, ScanRun
from core.models.enums import (
    ActorType,
    ConnectionStatus,
    EventSeverity,
    ScanStatus,
    ScanType,
)
from core.security import decrypt
from core.services.ingestion import upsert_resources

log = get_logger("core.services.discovery")

ClientFactory = Callable[[str, str], Any]

_DEFAULT_REGION = "us-east-1"


class ScanInProgress(Exception):
    """Raised when a discovery scan is already running for the account."""


@dataclass(frozen=True)
class RegionError:
    region: str
    code: str | None
    message: str


@dataclass
class ScanOutcome:
    scan_run_id: uuid.UUID
    status: ScanStatus
    resources_seen: int = 0
    created: int = 0
    updated: int = 0
    regions_scanned: int = 0
    regions_ok: int = 0
    errors: list[RegionError] = field(default_factory=list)

    @property
    def error_summary(self) -> str | None:
        if not self.errors:
            return None
        return json.dumps(
            [{"region": e.region, "code": e.code, "message": e.message} for e in self.errors]
        )


def _resolve_external_id(account: CloudAccount) -> str | None:
    if not account.external_id_encrypted:
        return None
    return decrypt(account.external_id_encrypted)


def _select_regions(
    account: CloudAccount,
    factory: ClientFactory,
    policy: RetryPolicy,
    *,
    default_region: str,
) -> list[str]:
    if account.enabled_regions:
        return list(account.enabled_regions)
    adapter = EC2Adapter(factory("ec2", default_region), default_region, policy=policy)
    return [region.name for region in adapter.describe_regions() if region.is_available]


def run_discovery(
    session: Session,
    account: CloudAccount,
    *,
    client_factory: ClientFactory | None = None,
    retry: RetryPolicy | None = None,
    now: datetime | None = None,
    external_id: str | None = None,
) -> ScanOutcome:
    """Run a read-only discovery scan for ``account`` and persist the outcome.

    The caller owns the transaction (commit/rollback). Raises :class:`ScanInProgress` if
    another scan for this account is already running.
    """
    timestamp = now or datetime.now(UTC)
    policy = retry or RetryPolicy()
    default_region = account.default_region or _DEFAULT_REGION

    if not try_advisory_lock(session, account.id, ScanType.DISCOVERY.value):
        raise ScanInProgress(f"A discovery scan is already running for account {account.id}")

    scan = ScanRun(
        cloud_account_id=account.id,
        scan_type=ScanType.DISCOVERY,
        status=ScanStatus.RUNNING,
        started_at=timestamp,
    )
    session.add(scan)
    session.flush()

    record_event(
        session,
        event_type=EVENT_SCAN_STARTED,
        summary=f"Discovery scan started for account {account.aws_account_id}",
        organization_id=account.organization_id,
        actor_type=ActorType.WORKER,
        entity_type="cloud_account",
        entity_id=str(account.id),
        data={"scan_run_id": str(scan.id), "scan_type": ScanType.DISCOVERY.value},
    )

    try:
        factory = client_factory or build_client_factory(
            account, external_id=external_id or _resolve_external_id(account)
        )
        outcome = _execute_scan(
            session,
            account=account,
            scan=scan,
            factory=factory,
            policy=policy,
            timestamp=timestamp,
            default_region=default_region,
        )
    finally:
        advisory_unlock(session, account.id, ScanType.DISCOVERY.value)

    return outcome


def _execute_scan(
    session: Session,
    *,
    account: CloudAccount,
    scan: ScanRun,
    factory: ClientFactory,
    policy: RetryPolicy,
    timestamp: datetime,
    default_region: str,
) -> ScanOutcome:
    # 1) Verify the connection via STS GetCallerIdentity.
    try:
        sts = STSAdapter(factory("sts", default_region), policy, region=default_region)
        identity = sts.get_caller_identity()
    except AwsError as exc:
        return _finish_failed(
            session,
            account=account,
            scan=scan,
            timestamp=timestamp,
            exc=exc,
            reason="connection verification failed",
        )

    account.connection_status = ConnectionStatus.CONNECTED
    account.last_verified_at = timestamp
    account.last_error = None
    record_event(
        session,
        event_type=EVENT_ACCOUNT_CONNECTED,
        summary=f"Verified connection to AWS account {identity.account}",
        organization_id=account.organization_id,
        actor_type=ActorType.WORKER,
        entity_type="cloud_account",
        entity_id=str(account.id),
        data={"caller_arn": identity.arn, "verified_account": identity.account},
    )

    # 2) Determine the regions to scan.
    try:
        regions = _select_regions(account, factory, policy, default_region=default_region)
    except AwsError as exc:
        return _finish_failed(
            session,
            account=account,
            scan=scan,
            timestamp=timestamp,
            exc=exc,
            reason="region enumeration failed",
        )

    outcome = ScanOutcome(
        scan_run_id=scan.id,
        status=ScanStatus.RUNNING,
        regions_scanned=len(regions),
    )

    # 3) Scan each region in isolation.
    for region in regions:
        try:
            adapter = EC2Adapter(
                factory("ec2", region),
                region,
                account_id=account.aws_account_id,
                policy=policy,
            )
            resources = adapter.describe_instances()
            stats = upsert_resources(
                session,
                organization_id=account.organization_id,
                cloud_account_id=account.id,
                resources=resources,
                seen_at=timestamp,
            )
            outcome.resources_seen += len(resources)
            outcome.created += stats.created
            outcome.updated += stats.updated
            outcome.regions_ok += 1
        except AwsRegionUnavailable as exc:
            log.info("region_skipped", account=str(account.id), region=region, code=exc.code)
        except AwsError as exc:
            outcome.errors.append(
                RegionError(region=region, code=exc.code, message=exc.message)
            )
            log.warning(
                "region_failed", account=str(account.id), region=region, code=exc.code
            )

    if outcome.regions_ok == 0 and outcome.errors:
        status = ScanStatus.FAILED
    elif outcome.errors:
        status = ScanStatus.PARTIAL
    else:
        status = ScanStatus.SUCCEEDED

    scan.status = status
    scan.finished_at = timestamp
    scan.resources_seen = outcome.resources_seen
    scan.error_summary = outcome.error_summary
    outcome.status = status

    if status == ScanStatus.SUCCEEDED:
        event_type = EVENT_SCAN_COMPLETED
        severity = EventSeverity.INFO
    elif status == ScanStatus.PARTIAL:
        event_type = EVENT_SCAN_PARTIAL
        severity = EventSeverity.WARNING
    else:
        event_type = EVENT_SCAN_FAILED
        severity = EventSeverity.CRITICAL

    record_event(
        session,
        event_type=event_type,
        summary=(
            f"Discovery scan {status.value}: {outcome.resources_seen} resources "
            f"across {outcome.regions_ok}/{outcome.regions_scanned} regions"
        ),
        organization_id=account.organization_id,
        actor_type=ActorType.WORKER,
        severity=severity,
        entity_type="scan_run",
        entity_id=str(scan.id),
        data={
            "scan_run_id": str(scan.id),
            "resources_seen": outcome.resources_seen,
            "created": outcome.created,
            "updated": outcome.updated,
            "errors": [{"region": e.region, "code": e.code} for e in outcome.errors],
        },
    )
    session.flush()
    return outcome


def _finish_failed(
    session: Session,
    *,
    account: CloudAccount,
    scan: ScanRun,
    timestamp: datetime,
    exc: AwsError,
    reason: str,
) -> ScanOutcome:
    account.connection_status = ConnectionStatus.ERROR
    account.last_error = f"{reason}: {exc}"
    scan.status = ScanStatus.FAILED
    scan.finished_at = timestamp
    scan.error_summary = str(exc)
    record_event(
        session,
        event_type=EVENT_SCAN_FAILED,
        summary=f"Discovery scan failed: {reason}",
        organization_id=account.organization_id,
        actor_type=ActorType.WORKER,
        severity=EventSeverity.CRITICAL,
        entity_type="scan_run",
        entity_id=str(scan.id),
        data={"code": exc.code, "operation": exc.operation},
    )
    if reason.startswith("connection verification"):
        record_event(
            session,
            event_type=EVENT_ACCOUNT_VERIFICATION_FAILED,
            summary=f"Connection verification failed for account {account.aws_account_id}",
            organization_id=account.organization_id,
            actor_type=ActorType.WORKER,
            severity=EventSeverity.CRITICAL,
            entity_type="cloud_account",
            entity_id=str(account.id),
            data={"code": exc.code},
        )
    session.flush()
    return ScanOutcome(scan_run_id=scan.id, status=ScanStatus.FAILED)
