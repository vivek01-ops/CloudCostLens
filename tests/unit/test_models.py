"""Model metadata sanity tests (no database required)."""

from __future__ import annotations

import core.models as models
from core.db.base import Base

EXPECTED_TABLES = {
    "organizations",
    "users",
    "memberships",
    "auth_sessions",
    "cloud_accounts",
    "scan_runs",
    "resources",
    "resource_metric_summaries",
    "cost_records",
    "pricing_cache",
    "recommendations",
    "resource_exclusions",
    "rule_configs",
    "approval_requests",
    "action_runs",
    "audit_events",
    "scheduled_jobs",
}


def test_all_tables_registered() -> None:
    assert set(Base.metadata.tables.keys()) >= EXPECTED_TABLES


def test_resource_identity_is_unique() -> None:
    resource = Base.metadata.tables["resources"]
    unique_columns = {
        tuple(sorted(constraint.columns.keys()))
        for constraint in resource.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("cloud_account_id", "region", "resource_id", "resource_type") in unique_columns


def test_audit_events_are_append_only_shape() -> None:
    # The audit table has no updated_at column: nothing to mutate in place.
    columns = set(Base.metadata.tables["audit_events"].columns.keys())
    assert "updated_at" not in columns
    assert {"event_type", "summary", "created_at"} <= columns


def test_money_columns_are_numeric() -> None:
    cost = Base.metadata.tables["cost_records"]
    assert str(cost.columns["amount"].type) == "NUMERIC(18, 6)"
    assert cost.columns["currency"].type.length == 3


def test_models_expose_public_api() -> None:
    for name in ("Organization", "User", "CloudAccount", "Resource", "Recommendation"):
        assert hasattr(models, name)
