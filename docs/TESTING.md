# CloudCostLens — Testing

## 1. Tooling

- **Backend**: `pytest`, `pytest-cov`, `Botocore.Stubber` for AWS, `httpx`/`fastapi.testclient`
  for API tests, ephemeral PostgreSQL for persistence tests.
- **Frontend**: `tsc --noEmit`, ESLint, Vitest (unit), Playwright (smoke).
- **Static**: `ruff` for Python (lint + format). PostgreSQL migration validation via
  `alembic upgrade head` on a clean database. Compose validation via `docker compose config`.

No test is reported as passing unless it was executed successfully.

## 2. Test layers

| Layer | Location | What it covers |
|---|---|---|
| Unit | `tests/unit` | money/currency, savings math, rules, config, missing telemetry, windows |
| AWS adapters | `tests/unit/aws` | pagination, throttling/retry, timeout, error classification (Stubber) |
| API | `tests/api` | routing, auth, RBAC, tenant scoping, validation, health |
| Integration | `tests/integration` | migrations, idempotent ingestion, duplicate scans, approval lifecycle |
| Frontend | `apps/web/**/*.test.tsx` | formatters, table logic, status mapping (Vitest) |
| E2E smoke | `apps/web/e2e` | login + navigate core pages (Playwright) |

## 3. Required cases (mapped to acceptance criteria)

- Cost calculations and currency handling (`Decimal`, ISO-4217, no float drift).
- Savings calculations: measured vs estimated; de-duplication across overlapping findings;
  remaining cost components; assumptions recorded.
- Recommendation rules: each rule deterministic and reproducible from stored evidence +
  `rule_version` + `config_version`.
- Missing telemetry: missing metric is never treated as zero; findings suppressed/flagged.
- Observation windows: 14–30 day windows; insufficient data → no high-confidence finding.
- AWS pagination: multi-page responses fully enumerated.
- Throttling/failures: retryable errors back off and retry; non-retryable fail cleanly.
- Database constraints: uniqueness, FKs, org scoping.
- Duplicate scans: idempotent upserts; no duplicate resources; no data loss on failure.
- Tenant isolation: org A cannot read/write org B rows; cross-tenant access denied.
- Authentication/authorization: login, refresh, revocation; role enforcement server-side.
- Approval expiry: expired approvals cannot execute.
- Payload tampering: modified params fail `payload_hash` verification.
- Resource state change after approval: requires renewed review.
- Execution idempotency: duplicate jobs do not double-apply; ambiguous outcomes reconciled.
- Audit event creation: approvals and actions always recorded; append-only.
- Failed/ambiguous AWS operations: handled safely, never reported as success.

## 4. AWS testing policy

- Adapters are tested with `Botocore.Stubber` using recorded/labelled fixtures.
- A dedicated **sandbox** AWS account is used for any live integration testing; destructive
  behavior is never tested against production, and termination does not exist in the code.
- When no AWS account is available, adapters are validated only against Stubber/fixtures and
  documentation must state that **live AWS verification is pending**.

## 5. Commands

```bash
# Backend
ruff check .            # lint
ruff format --check .   # format
pytest -q               # tests
alembic upgrade head    # migration validation

# Frontend
pnpm --dir apps/web typecheck   # tsc --noEmit
pnpm --dir apps/web lint        # eslint
pnpm --dir apps/web test        # vitest
pnpm --dir apps/web build       # production build

# Deployment
docker compose config   # validate
```

## 6. Milestone gates

Each milestone cannot be marked complete until its relevant tests, `ruff`, type checks,
migration validation, and (where possible) a running app inspection pass. Failures are
fixed, not documented as acceptable. Progress and remaining issues are recorded in
`IMPLEMENTATION_PLAN.md`.

## 7. Demonstration data policy

Fixtures and seed data are clearly labeled in the UI ("Sample data") and in code
(`core/fixtures`). They must never be presented as live AWS data. Tests that depend on
fixtures assert the `is_estimate`/`source` fields so labels cannot be lost.
