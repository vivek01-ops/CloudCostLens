# CloudCostLens — Implementation Plan

Living document. Updated at the end of every milestone with completed work, changed files,
tests executed, results, remaining issues, and the next milestone.

## Milestones

### Milestone 1 — Foundation ✅
Deliverables: repository structure; configuration; design system; navigation; PostgreSQL
schema; migrations; Docker Compose environment; logging; test setup; API skeleton; web shell
on clearly labeled demonstration data.

Exit gate: `ruff` + `tsc` clean; `pytest`/Vitest green; migration applies; api + web boot;
UI inspected. ✅

### Milestone 2 — AWS read-only connection ✅
Credential provider, STS role assumption, region enumeration, EC2 discovery, retries/
pagination/error handling. Gate: Stubber tests; `scan_runs` persisted; partial scans recorded.
✅

### Milestone 3 — Billing and metrics
Cost Explorer, CloudWatch, EBS, RDS, ELB adapters; normalized persistence; data freshness
exposed. Gate: Stubber tests; no duplicate rows; freshness surfaced in UI.

### Milestone 4 — Recommendation engine
Idle EC2, rightsizing, unattached EBS, idle EIP, cost anomalies; structured evidence and
savings with `PricingProvider`. Gate: determinism/currency/missing-telemetry tests.

### Milestone 5 — Enterprise dashboard
Complete Overview, Resources, Cost Explorer, Recommendations, Resource Details, Approval
Center, Activity & Audit, Settings; remove generic AI patterns. Gate: UI inspected against
design constraints; every metric's calculation defined.

### Milestone 6 — Approval workflow
Auth/RBAC, approval records, action validation, restricted execution, EC2 stop/start,
audit logging. Termination stays disabled. Gate: approval/expiry/tamper/state-change/
idempotency/authz tests.

### Milestone 7 — Production hardening
Tenant isolation (+RLS), security testing, backups, health checks, deployment docs, E2E.
Gate: cross-tenant denial tests; compose valid; docs match system.

## Progress log

### Milestone 1 — 2026-10-12
Implemented:
- Documentation set (`docs/`): PRODUCT_REQUIREMENTS, ARCHITECTURE, DATABASE_SCHEMA,
  AWS_PERMISSIONS, UI_DESIGN_SYSTEM, SECURITY, TESTING, IMPLEMENTATION_PLAN, API.
- Python project scaffold (`pyproject.toml`), pinned dependencies, ruff + pytest config.
- `core/config.py` (Pydantic Settings), `core/logging.py`, DB engine/session/base.
- SQLAlchemy 2.x models for all entities (identity, cloud, optimization, workflow).
- Alembic configuration + initial migration `2563fa8c7d9d_initial_schema`.
- FastAPI skeleton: `/health`, `/version`, OpenAPI, middleware, error handlers.
- Next.js (App Router) shell: design tokens, `AppShell`, sidebar, all 8 pages on
  clearly labeled demonstration data (ECharts + dense tables).
- Docker Compose (db, api, worker, scheduler, web, proxy), non-root Dockerfiles,
  `.env.example`, ignores.
- Scripts: `bootstrap_owner.py`, `seed_demo.py`.
- Test suite (unit + api) and CI-style commands.

Changed files: see repository tree.

Tests executed: `ruff check`, `pytest`, `tsc --noEmit`, `alembic upgrade head`,
app boot. Results recorded in the milestone checkpoint summary.

Remaining/incomplete: AWS adapters are Milestone 2+; external-ID encryption wiring and
auth/RBAC are Milestone 6 (a no-op `DemoPrincipal` is used for the M1 shell).

Next recommended milestone: Milestone 2 — AWS read-only connection.

### Milestone 2 — 2026-10-12
Implemented:
- AWS read-only adapters (`core/aws/`): error classification with retryable flags
  (`errors.py`); exponential backoff + jitter (`retry.py`, PEP 695 generics); discovered
  resource/region DTOs (`models.py`); `assume_role` + thread-safe `AssumeRoleCredentialCache`
  (`credentials.py`); `AwsClientFactory`/`build_client_factory` (`session.py`); `STSAdapter`
  (`sts.py`); `EC2Adapter` with manual `NextToken` pagination, `describe_regions`, and
  `normalize_instance` that strips IP/DNS fields (`ec2.py`).
- Append-only audit writer (`core/audit.py`) and PostgreSQL session advisory locks
  (`core/db/locks.py`).
- Ingestion + orchestration: idempotent `upsert_resources` keyed by `uq_resource_identity`
  preserving `first_seen` (`core/services/ingestion.py`); `run_discovery` scan lifecycle
  SUCCEEDED/PARTIAL/FAILED with per-region isolation, advisory-lock guard, audit events, and
  no-delete-on-failure (`core/services/discovery.py`).
- Worker entrypoint: `workers/discovery.py`, `workers/db.py` session seam, `workers/cli.py`
  dispatches `discovery`.

Changed files: `core/aws/*`, `core/audit.py`, `core/db/locks.py`,
`core/services/{__init__,ingestion,discovery}.py`, `workers/{discovery,cli,db}.py`,
`tests/unit/aws/*`, `tests/integration/test_discovery.py`.

Tests executed: `ruff check .` clean; `pytest` 50 passed (17 M1 + 27 AWS unit incl. Stubber
pagination/throttling/access-denied/region-filter + 6 discovery integration against live
PostgreSQL). Results: all green.

Verification notes: AWS paths are exercised only via Botocore `Stubber` (no live credentials
available); discovery integration tests run against the `ccl-pg` container and assert scan
lifecycle, partial-scan recording, idempotency (`first_seen` preserved), no-delete-on-failure,
and advisory-lock rejection.

Remaining/incomplete: billing/metrics, recommendation engine, approvals, auth (M3–M6).

Next recommended milestone: Milestone 3 — Billing and metrics.
