"""Migration validation against a live PostgreSQL database.

These tests are marked ``integration`` and are skipped automatically when no database is
reachable, so CI without a database still runs the rest of the suite cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core.config import get_settings
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
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


@pytest.fixture(scope="module")
def engine():  # type: ignore[no-untyped-def]
    url = get_settings().database_url
    try:
        eng = create_engine(url, pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("PostgreSQL is not reachable; skipping migration integration tests")
    return eng


def test_upgrade_head_creates_all_tables(engine) -> None:  # type: ignore[no-untyped-def]
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")

    tables = set(inspect(engine).get_table_names())
    assert tables >= EXPECTED_TABLES
    assert "alembic_version" in tables


def test_downgrade_then_upgrade_is_clean(engine) -> None:  # type: ignore[no-untyped-def]
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
