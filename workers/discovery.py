"""Discovery worker.

Runs read-only inventory discovery for every connected account, each in its own
transaction so one account's failure never rolls back another's results.
"""

from __future__ import annotations

import uuid

from core.logging import get_logger
from core.models.cloud import CloudAccount
from core.models.enums import ConnectionStatus
from core.services.discovery import ScanInProgress, ScanOutcome, run_discovery
from sqlalchemy import select

from workers.db import worker_session

log = get_logger("workers.discovery")

_SCANNABLE = (
    ConnectionStatus.PENDING,
    ConnectionStatus.CONNECTED,
    ConnectionStatus.ERROR,
)


def _account_ids(account_ids: list[uuid.UUID] | None) -> list[uuid.UUID]:
    if account_ids:
        return list(account_ids)
    with worker_session() as session:
        return list(
            session.execute(
                select(CloudAccount.id).where(CloudAccount.connection_status.in_(_SCANNABLE))
            ).scalars()
        )


def run_once(account_ids: list[uuid.UUID] | None = None) -> list[ScanOutcome]:
    """Discover all (or the given) accounts. Returns one outcome per completed account."""
    outcomes: list[ScanOutcome] = []
    ids = _account_ids(account_ids)
    log.info("discovery_batch_started", accounts=len(ids))
    for account_id in ids:
        with worker_session() as session:
            account = session.get(CloudAccount, account_id)
            if account is None:
                log.warning("account_missing", account_id=str(account_id))
                continue
            try:
                outcome = run_discovery(session, account)
            except ScanInProgress:
                log.info("scan_in_progress", account_id=str(account_id))
                continue
            outcomes.append(outcome)
            log.info(
                "scan_finished",
                account_id=str(account_id),
                status=outcome.status.value,
                resources_seen=outcome.resources_seen,
                regions_ok=outcome.regions_ok,
                regions_scanned=outcome.regions_scanned,
                errors=len(outcome.errors),
            )
    log.info("discovery_batch_finished", completed=len(outcomes))
    return outcomes


def tick() -> None:
    """Single scheduled pass (used by the loop and tests)."""
    run_once()
