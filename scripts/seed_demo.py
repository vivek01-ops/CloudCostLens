"""Seed demonstration data (clearly labeled, never presented as live AWS data).

This data is for development and UI review only. Everything it creates carries
``is_estimate``/``source`` markers and the UI renders a "Sample data" banner for it.
Requires ``--confirm`` to run because it inserts synthetic records.

Usage:
    python -m scripts.seed_demo --confirm
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime, timedelta

from core.db.session import get_session
from core.logging import configure_logging, get_logger
from core.models import (
    CloudAccount,
    CostRecord,
    Organization,
    Recommendation,
    Resource,
    ResourceMetricSummary,
)
from core.models.enums import (
    Attribution,
    Confidence,
    ConnectionStatus,
    FindingType,
    Granularity,
    OperationalRisk,
    OptimizationStatus,
    RecommendationStatus,
    ResourceType,
    Reversibility,
)

log = get_logger("scripts.seed_demo")

DEMO_ORG_SLUG = "demo-org"
DEMO_ACCOUNT_ID = "111122223333"
CURRENCY = "USD"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed clearly labeled demonstration data.")
    parser.add_argument("--confirm", action="store_true", help="Acknowledge synthetic data.")
    args = parser.parse_args(argv)

    if not args.confirm:
        raise SystemExit(
            "Refusing to seed synthetic data. Re-run with --confirm. "
            "This data is never presented as live AWS data."
        )

    configure_logging(level="INFO")
    now = _utcnow()

    with get_session() as db:
        org = db.query(Organization).filter(Organization.slug == DEMO_ORG_SLUG).first()
        if org is None:
            org = Organization(name="Demo Organization", slug=DEMO_ORG_SLUG)
            db.add(org)
            db.flush()

        account = (
            db.query(CloudAccount)
            .filter(
                CloudAccount.organization_id == org.id,
                CloudAccount.aws_account_id == DEMO_ACCOUNT_ID,
            )
            .first()
        )
        if account is None:
            account = CloudAccount(
                organization_id=org.id,
                aws_account_id=DEMO_ACCOUNT_ID,
                alias="demo-account",
                connection_status=ConnectionStatus.CONNECTED,
                default_region="eu-west-1",
                enabled_regions=["eu-west-1", "us-east-1"],
                last_verified_at=now,
            )
            db.add(account)
            db.flush()

        resources = {
            "dev-app-03": Resource(
                organization_id=org.id,
                cloud_account_id=account.id,
                resource_type=ResourceType.EC2_INSTANCE,
                resource_id="i-09a8b7c6d5e4f3a21",
                arn="arn:aws:ec2:eu-west-1:111122223333:instance/i-09a8b7c6d5e4f3a21",
                name="dev-app-03",
                region="eu-west-1",
                state="running",
                environment="development",
                owner="platform",
                tags={"Name": "dev-app-03", "env": "dev", "business-owner": "platform"},
                attributes={"instance_type": "t3.medium", "vpc_id": "vpc-1234"},
                monthly_cost_estimate=None,
                currency=CURRENCY,
                optimization_status=OptimizationStatus.IDLE,
                first_seen=now - timedelta(days=60),
                last_seen=now,
            ),
            "prod-web-01": Resource(
                organization_id=org.id,
                cloud_account_id=account.id,
                resource_type=ResourceType.EC2_INSTANCE,
                resource_id="i-0b1c2d3e4f5a6b7c8",
                arn="arn:aws:ec2:eu-west-1:111122223333:instance/i-0b1c2d3e4f5a6b7c8",
                name="prod-web-01",
                region="eu-west-1",
                state="running",
                environment="production",
                owner="web",
                tags={"Name": "prod-web-01", "env": "prod", "business-owner": "web"},
                attributes={"instance_type": "m5.large"},
                monthly_cost_estimate=None,
                currency=CURRENCY,
                optimization_status=OptimizationStatus.OPTIMIZED,
                first_seen=now - timedelta(days=200),
                last_seen=now,
            ),
            "vol-unattached-01": Resource(
                organization_id=org.id,
                cloud_account_id=account.id,
                resource_type=ResourceType.EBS_VOLUME,
                resource_id="vol-0aa11bb22cc33dd44",
                arn="arn:aws:ec2:eu-west-1:111122223333:volume/vol-0aa11bb22cc33dd44",
                name="vol-unattached-01",
                region="eu-west-1",
                state="available",
                environment="development",
                owner=None,
                tags={"Name": "vol-unattached-01"},
                attributes={"volume_type": "gp3", "size_gb": 100},
                monthly_cost_estimate=None,
                currency=CURRENCY,
                optimization_status=OptimizationStatus.UNDERUTILIZED,
                first_seen=now - timedelta(days=90),
                last_seen=now,
            ),
            "eip-unassociated-01": Resource(
                organization_id=org.id,
                cloud_account_id=account.id,
                resource_type=ResourceType.ELASTIC_IP,
                resource_id="eipalloc-0fee22ddee44ff550",
                arn="arn:aws:ec2:eu-west-1:111122223333:elastic-ip/eipalloc-0fee22ddee44ff550",
                name="eip-unassociated-01",
                region="eu-west-1",
                state="unassociated",
                environment=None,
                owner=None,
                tags={},
                attributes={"public_ipv4": "54.1.2.3"},
                monthly_cost_estimate=None,
                currency=CURRENCY,
                optimization_status=OptimizationStatus.UNKNOWN,
                first_seen=now - timedelta(days=40),
                last_seen=now,
            ),
        }
        for resource in resources.values():
            existing = (
                db.query(Resource)
                .filter(
                    Resource.cloud_account_id == account.id,
                    Resource.resource_type == resource.resource_type,
                    Resource.resource_id == resource.resource_id,
                    Resource.region == resource.region,
                )
                .first()
            )
            if existing is None:
                db.add(resource)

        db.flush()

        # Metric summaries for dev-app-03 (laboratory fixtures, not production telemetry).
        dev_app = db.query(Resource).filter(Resource.name == "dev-app-03").one()
        period_start = now - timedelta(days=14)
        for metric_name, value, unit in [
            ("CPUUtilization", "3.2", "Percent"),
            ("NetworkIn", "1800.0", "Bytes"),
            ("NetworkOut", "2400.0", "Bytes"),
        ]:
            summary = ResourceMetricSummary(
                resource_id=dev_app.id,
                metric_name=metric_name,
                statistic="average",
                value=value,
                unit=unit,
                period_start=period_start,
                period_end=now,
                window_seconds=14 * 86400,
                coverage_pct="92.0",
                source="fixture",
                collected_at=now,
            )
            db.add(summary)
        db.add(
            ResourceMetricSummary(
                resource_id=dev_app.id,
                metric_name="CPUUtilization",
                statistic="max",
                value="11.4",
                unit="Percent",
                period_start=period_start,
                period_end=now,
                window_seconds=14 * 86400,
                coverage_pct="92.0",
                source="fixture",
                collected_at=now,
            )
        )

        # Cost records: daily, service-level, last 35 days.
        services = {
            "Amazon Elastic Compute Cloud - Compute": 86.4,
            "Amazon Elastic Block Store": 12.8,
            "Amazon Relational Database Service": 24.5,
        }
        for day_offset in range(35, 0, -1):
            day = now - timedelta(days=day_offset)
            for service, base in services.items():
                db.add(
                    CostRecord(
                        organization_id=org.id,
                        cloud_account_id=account.id,
                        service=service,
                        region="eu-west-1",
                        granularity=Granularity.DAILY,
                        period_start=day.replace(hour=0, minute=0, second=0, microsecond=0),
                        period_end=(day + timedelta(days=1)),
                        amount=base,
                        currency=CURRENCY,
                        attribution=Attribution.SERVICE,
                        source="fixture",
                        is_estimated=True,
                        collection_lag_days=0,
                        collected_at=now,
                    )
                )

        # One deterministic recommendation derived from the fixture evidence above.
        existing_reco = (
            db.query(Recommendation)
            .filter(
                Recommendation.organization_id == org.id,
                Recommendation.resource_id == dev_app.id,
                Recommendation.finding_type == FindingType.IDLE_EC2,
            )
            .first()
        )
        if existing_reco is None:
            db.add(
                Recommendation(
                    organization_id=org.id,
                    cloud_account_id=account.id,
                    resource_id=dev_app.id,
                    finding_type=FindingType.IDLE_EC2,
                    rule_id="ec2.idle",
                    rule_version="1.0",
                    config_version="default-v1",
                    observation_fingerprint=uuid.uuid4().hex[:16],
                    severity="medium",
                    confidence=Confidence.MEDIUM,
                    operational_risk=OperationalRisk.LOW,
                    reversibility=Reversibility.REVERSIBLE,
                    evidence={
                        "cpu_average_pct": "3.2",
                        "cpu_max_pct": "11.4",
                        "network_in_bytes_avg": "1800",
                        "network_out_bytes_avg": "2400",
                        "state": "running",
                        "environment": "development",
                        "source": "fixture",
                    },
                    observation_window_days=14,
                    metric_coverage_pct="92.0",
                    current_monthly_cost="41.60",
                    projected_monthly_cost="8.32",
                    estimated_monthly_savings="33.28",
                    estimated_annual_savings="399.36",
                    currency=CURRENCY,
                    is_estimate=True,
                    assumptions={
                        "instance_type": "t3.medium",
                        "savings_apply_while_stopped": False,
                        "storage_charges_remain": True,
                    },
                    recommended_action=(
                        "Review this instance for stopping. Observed utilization has "
                        "remained low over the selected period. Confirm workload "
                        "dependencies, scheduled jobs, and availability requirements "
                        "before approving."
                    ),
                    status=RecommendationStatus.OPEN,
                )
            )

    log.info("demo_data_seeded", organization=DEMO_ORG_SLUG)
    print(f"Demo data seeded into organization '{DEMO_ORG_SLUG}' (clearly labeled fixtures).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())