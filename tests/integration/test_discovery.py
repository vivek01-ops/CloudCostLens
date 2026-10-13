"""Discovery integration tests against a live PostgreSQL database.

AWS is stubbed with Botocore Stubber so the real adapter + orchestration + persistence code
paths are exercised without live credentials. Skipped automatically when no database is
reachable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from botocore.stub import Stubber
from core.aws.retry import RetryPolicy
from core.db.locks import advisory_unlock, try_advisory_lock
from core.db.session import get_session, get_sessionmaker
from core.models.cloud import CloudAccount, Resource, ScanRun
from core.models.enums import ConnectionStatus, ResourceType, ScanStatus, ScanType
from core.models.identity import Organization
from core.models.workflow import AuditEvent
from core.services.discovery import ScanInProgress, run_discovery
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from tests.unit.aws.helpers import instance, make_client, reservations

pytestmark = pytest.mark.integration

FAST = RetryPolicy(max_attempts=3, base_delay=0.0)


def _db_available() -> bool:
    try:
        with get_session() as session:
            session.execute(select(1))
        return True
    except OperationalError:
        return False


@pytest.fixture(scope="module", autouse=True)
def _require_db() -> None:
    if not _db_available():
        pytest.skip("PostgreSQL is not reachable; skipping discovery integration tests")


def _make_account(regions: list[str] | None = None) -> uuid.UUID:
    with get_session() as session:
        org = Organization(name="Discovery Test", slug=f"disc-{uuid.uuid4().hex[:10]}")
        session.add(org)
        session.flush()
        account = CloudAccount(
            organization_id=org.id,
            aws_account_id=f"{uuid.uuid4().int % 10**12:012d}",
            alias="test-account",
            connection_status=ConnectionStatus.PENDING,
            default_region="us-east-1",
            enabled_regions=regions or ["us-east-1", "us-west-2"],
        )
        session.add(account)
        session.flush()
        return account.id


def _identity(account_number: str) -> dict[str, Any]:
    return {
        "UserId": "AIDAEXAMPLEUSER",
        "Account": account_number,
        "Arn": f"arn:aws:sts::{account_number}:assumed-role/CloudCostLensReadOnly/session",
    }


class StubFactory:
    """Builds Stubber-wrapped clients keyed by (service, region)."""

    def __init__(self, account_number: str) -> None:
        self.account_number = account_number
        self._clients: dict[tuple[str, str], Any] = {}
        self._stubbers: list[Stubber] = []

    def _new(self, service: str, region: str) -> tuple[Any, Stubber]:
        client = make_client(service, region)
        stubber = Stubber(client)
        stubber.activate()
        self._stubbers.append(stubber)
        self._clients[(service, region)] = client
        return client, stubber

    def sts_ok(self, region: str = "us-east-1") -> None:
        _, stubber = self._new("sts", region)
        stubber.add_response("get_caller_identity", _identity(self.account_number))

    def sts_denied(self, region: str = "us-east-1") -> None:
        _, stubber = self._new("sts", region)
        stubber.add_client_error("get_caller_identity", service_error_code="UnauthorizedOperation")

    def ec2_ok(self, region: str, *instances: dict[str, Any]) -> None:
        _, stubber = self._new("ec2", region)
        stubber.add_response("describe_instances", reservations(*instances))

    def ec2_denied(self, region: str) -> None:
        _, stubber = self._new("ec2", region)
        stubber.add_client_error("describe_instances", service_error_code="UnauthorizedOperation")

    def __call__(self, service: str, region: str) -> Any:
        key = (service, region)
        if key not in self._clients:
            client, _ = self._new(service, region)
            return client
        return self._clients[key]


def _run(account_id: uuid.UUID, factory: StubFactory, *, now: datetime | None = None):
    with get_session() as session:
        account = session.get(CloudAccount, account_id)
        assert account is not None
        return run_discovery(session, account, client_factory=factory, retry=FAST, now=now)


def test_successful_discovery_persists_inventory() -> None:
    account_id = _make_account(["us-east-1", "us-west-2"])
    with get_session() as session:
        number = session.get(CloudAccount, account_id).aws_account_id

    factory = StubFactory(number)
    factory.sts_ok()
    factory.ec2_ok("us-east-1", instance("i-1"), instance("i-2"))
    factory.ec2_ok("us-west-2", instance("i-3"))

    outcome = _run(account_id, factory)

    assert outcome.status is ScanStatus.SUCCEEDED
    assert outcome.resources_seen == 3
    assert outcome.regions_ok == 2
    assert outcome.created == 3

    with get_session() as session:
        resources = session.execute(
            select(Resource).where(Resource.cloud_account_id == account_id)
        ).scalars().all()
        assert {r.resource_id for r in resources} == {"i-1", "i-2", "i-3"}
        assert all(r.resource_type is ResourceType.EC2_INSTANCE for r in resources)
        scan = session.get(ScanRun, outcome.scan_run_id)
        assert scan.status is ScanStatus.SUCCEEDED
        assert scan.resources_seen == 3
        account = session.get(CloudAccount, account_id)
        assert account.connection_status is ConnectionStatus.CONNECTED
        assert account.last_verified_at is not None
        event_types = {
            e.event_type
            for e in session.execute(
                select(AuditEvent).where(AuditEvent.organization_id == account.organization_id)
            ).scalars()
        }
        assert {"account.connected", "scan.started", "scan.completed"} <= event_types


def test_discovery_is_idempotent() -> None:
    account_id = _make_account(["us-east-1"])
    with get_session() as session:
        number = session.get(CloudAccount, account_id).aws_account_id

    first = StubFactory(number)
    first.sts_ok()
    first.ec2_ok("us-east-1", instance("i-1"), instance("i-2"))
    now1 = datetime(2026, 3, 1, tzinfo=UTC)
    outcome1 = _run(account_id, first, now=now1)
    assert outcome1.created == 2
    assert outcome1.updated == 0

    with get_session() as session:
        first_seens = {
            r.resource_id: r.first_seen
            for r in session.execute(
                select(Resource).where(Resource.cloud_account_id == account_id)
            ).scalars()
        }

    second = StubFactory(number)
    second.sts_ok()
    second.ec2_ok("us-east-1", instance("i-1", state="stopped"), instance("i-2"))
    now2 = now1 + timedelta(hours=6)
    outcome2 = _run(account_id, second, now=now2)
    assert outcome2.created == 0
    assert outcome2.updated == 2

    with get_session() as session:
        resources = session.execute(
            select(Resource).where(Resource.cloud_account_id == account_id)
        ).scalars().all()
        assert len(resources) == 2
        for resource in resources:
            assert resource.first_seen == first_seens[resource.resource_id]
        by_id = {r.resource_id: r for r in resources}
        assert by_id["i-1"].state == "stopped"


def test_partial_scan_records_error_and_keeps_good_region() -> None:
    account_id = _make_account(["us-east-1", "us-west-2"])
    with get_session() as session:
        number = session.get(CloudAccount, account_id).aws_account_id

    factory = StubFactory(number)
    factory.sts_ok()
    factory.ec2_ok("us-east-1", instance("i-1"), instance("i-2"))
    factory.ec2_denied("us-west-2")

    outcome = _run(account_id, factory)

    assert outcome.status is ScanStatus.PARTIAL
    assert outcome.resources_seen == 2
    assert outcome.regions_ok == 1
    assert len(outcome.errors) == 1
    assert outcome.errors[0].region == "us-west-2"

    with get_session() as session:
        scan = session.get(ScanRun, outcome.scan_run_id)
        assert scan.status is ScanStatus.PARTIAL
        assert "us-west-2" in (scan.error_summary or "")
        count = len(
            session.execute(
                select(Resource).where(Resource.cloud_account_id == account_id)
            ).scalars().all()
        )
        assert count == 2


def test_failed_verification_marks_account_error() -> None:
    account_id = _make_account(["us-east-1"])
    with get_session() as session:
        number = session.get(CloudAccount, account_id).aws_account_id

    factory = StubFactory(number)
    factory.sts_denied()

    outcome = _run(account_id, factory)

    assert outcome.status is ScanStatus.FAILED
    assert outcome.resources_seen == 0

    with get_session() as session:
        account = session.get(CloudAccount, account_id)
        assert account.connection_status is ConnectionStatus.ERROR
        assert account.last_error is not None
        scan = session.get(ScanRun, outcome.scan_run_id)
        assert scan.status is ScanStatus.FAILED


def test_failed_scan_does_not_delete_inventory() -> None:
    account_id = _make_account(["us-east-1"])
    with get_session() as session:
        number = session.get(CloudAccount, account_id).aws_account_id

    good = StubFactory(number)
    good.sts_ok()
    good.ec2_ok("us-east-1", instance("i-1"), instance("i-2"))
    assert _run(account_id, good).status is ScanStatus.SUCCEEDED

    bad = StubFactory(number)
    bad.sts_ok()
    bad.ec2_denied("us-east-1")
    assert _run(account_id, bad).status is ScanStatus.FAILED

    with get_session() as session:
        resources = session.execute(
            select(Resource).where(Resource.cloud_account_id == account_id)
        ).scalars().all()
        assert {r.resource_id for r in resources} == {"i-1", "i-2"}


def test_concurrent_scan_rejected_by_advisory_lock() -> None:
    account_id = _make_account(["us-east-1"])
    holder = get_sessionmaker()()
    try:
        account = holder.get(CloudAccount, account_id)
        assert account is not None
        # A different connection holds the account's scan lock.
        assert try_advisory_lock(holder, account.id, ScanType.DISCOVERY.value)
        with get_session() as session:
            other = session.get(CloudAccount, account_id)
            assert other is not None
            with pytest.raises(ScanInProgress):
                run_discovery(session, other, client_factory=_noop_factory(), retry=FAST)
    finally:
        advisory_unlock(holder, account.id, ScanType.DISCOVERY.value)
        holder.close()


def _noop_factory() -> Any:
    def factory(service: str, region: str) -> Any:  # pragma: no cover - never called
        raise AssertionError("no AWS calls expected")

    return factory
