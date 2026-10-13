# CloudCostLens

An AWS Cloud Cost Intelligence and Optimization platform. CloudCostLens discovers cloud
resources, correlates billing and telemetry evidence, produces explainable cost-saving
recommendations, and — only after explicit human approval — performs a deliberately narrow
set of actions (start/stop). Every recommendation is backed by stored evidence.

> **Status: Milestone 1 — Foundation.** The full data model, API skeleton, worker topology,
> Docker/Compose stack, and an enterprise-style Next.js dashboard on **clearly labeled demo
> data** are in place. Cost math, AWS discovery, and execution are implemented in later
> milestones.

## Principles

- **Evidence before recommendations.** Every finding links to the metrics and config it came from.
- **Deterministic money math.** `Decimal` everywhere with an explicit currency — never floats.
- **Human approval before change.** No action runs without a recorded approval.
- **Least privilege.** Separate read-only discovery and start/stop execution identities.
  **`ec2:TerminateInstances` is denied and never used.**
- **Append-only audit.** The audit trail is immutable.
- **Missing metric ≠ zero.** Absent telemetry is shown as unknown, never as `0`.
- **Tenant isolation & server-enforced RBAC.**

## Architecture

```
Next.js (apps/web) ──HTTP──► FastAPI (apps/api) ──SQLAlchemy──► PostgreSQL
                                    ▲
                    workers (discovery / billing / metrics / analysis
                             / executor / scheduler)
```

See `docs/ARCHITECTURE.md` and `docs/DATABASE_SCHEMA.md` for detail.

## Quick start (Docker)

```bash
cp .env.example .env          # then edit secrets
make up                        # db + migrate + api + workers + web + proxy
# API:      http://localhost:8000/docs
# Web:      http://localhost:3000
# Proxy:    http://localhost:8080
```

Business-plane IPs (EC2 public/private/DNS) are **not** collected. There are no AWS
credentials in this repo; adapters are exercised in tests with Botocore `Stubber` and labeled
fixtures.

## Local development (without Docker)

```bash
make install                   # .venv on Python 3.13 + runtime/dev deps
corepack enable && make install-web
docker compose up -d db        # PostgreSQL for migrations/tests
make migrate
make api                       # http://localhost:8000
make web-dev                   # http://localhost:3000
```

## Common tasks

| Command | Purpose |
| --- | --- |
| `make lint` / `make format` | Ruff lint / format |
| `make test` | Unit tests (integration excluded) |
| `make test-integration` | Migration/DB tests (requires PostgreSQL) |
| `make web-typecheck` / `make web-lint` / `make web-test` | Frontend checks |
| `make revision m="..."` | Autogenerate an Alembic migration |
| `make seed` | Seed demo data (`--confirm` required) |
| `make bootstrap-owner` | Create the first owner (no default admin exists) |

## Repository layout

```
core/        domain: config, logging, db, security, models
workers/     discovery, billing, metrics, analysis, executor, scheduler
apps/api/    FastAPI application and routers
apps/web/    Next.js (App Router, TypeScript, Tailwind, ECharts)
migrations/  Alembic
docs/        product, architecture, schema, security, testing, UI, plan
deploy/      nginx reverse proxy
```

## Security notes

- Secrets live only in the environment/`.env` (git-ignored) and are encrypted at rest with
  Fernet when stored.
- The API issues `httpOnly`, `Secure`, `SameSite` cookies (Milestone 6).
- Never commit real credentials. The bootstrap owner is created explicitly — there is no
  default administrator account.
