# CloudCostLens — Architecture

## 1. Overview

CloudCostLens is a **modular monolith with independently runnable workers**, plus a
separate HTTP API and web frontend. Domain logic lives in exactly one place (`core/`) and
is shared by the API and the workers. No business logic exists in routers or the frontend.

```
┌──────────────┐     OpenAPI/JSON      ┌──────────────┐        ┌────────────────────┐
│  Next.js web │ ────────────────────▶ │  FastAPI     │ ─────▶ │  core/ domain       │
│  (apps/web)  │ ◀──────────────────── │  (apps/api)  │        │  services, rules,   │
└──────────────┘   httpOnly cookies    └──────────────┘        │  repositories, aws  │
                                                               └─────────┬──────────┘
                                                                         │ SQLAlchemy 2.x
┌───────────────────────────────────────────────────────────────────────▼──────────┐
│ PostgreSQL (organizations, resources, costs, recommendations, approvals, audit)   │
└───────────────────────────────────────────────────────────────────────────────────┘
        ▲                     ▲                    ▲                    ▲
   discovery            billing               metrics              analysis          executor
   worker               worker                worker               worker            worker
                                    ▲
                                 scheduler  (DB-backed job records)
```

## 2. Layers

| Layer | Path | Responsibility |
|---|---|---|
| Web UI | `apps/web` | Rendering, navigation, interactions. Never touches AWS or the DB. |
| API | `apps/api` | HTTP transport, validation, auth, RBAC enforcement, tenant scoping, OpenAPI. |
| Domain | `core/` | Models, repositories, services, rules engine, savings, AWS adapters, audit. |
| Workers | `workers/` | Scheduled/queued jobs: discovery, billing, metrics, analysis, execution. |
| Data | PostgreSQL | System of record. Org-scoped, append-only audit. |

### Dependency rule
`apps/web` → `apps/api` → `core` → (DB, AWS). Workers → `core` → (DB, AWS).
`core` never imports FastAPI or Streamlit/Next concerns.

## 3. Web stack

- **Next.js (App Router) + TypeScript**, Tailwind CSS, shadcn/ui (Radix) primitives,
  TanStack Query for interactive data, Apache ECharts for charts.
- Consumes a **TypeScript client generated from the FastAPI OpenAPI schema**.
- Authentication: short-lived JWT in httpOnly/Secure/SameSite cookies issued by FastAPI.
  Route guards in Next are UX only; authorization is enforced server-side.
- Server components fetch via an internal API base URL; interactive views use TanStack Query.

## 4. API stack

- **FastAPI + Pydantic v2**; uvicorn (dev) / gunicorn+uvicorn workers (prod).
- Routers are thin: parse → authorize → call a `core` service → serialize.
- Every request resolves a `Principal` (user, org, roles) from the session cookie.
- All repository calls are org-scoped; tenant id is never trusted from the client payload.

## 5. Domain concepts

- **AWS Adapters** (`core/aws/`): `sts`, `ec2`, `ebs`, `rds`, `elb`, `cloudwatch`,
  `cost_explorer`, `pricing`. Shared session/credentials, pagination, bounded retries with
  backoff/jitter, API timeouts, and structured error classification.
- **Ingestion** (`core/services/`): idempotent upserts keyed by
  `(cloud_account_id, resource_type, resource_id, region)`, tracking `first_seen`/
  `last_seen`. A failed scan records a `scan_run` error and never deletes inventory.
- **Rules engine** (`core/rules/`): deterministic rules, versioned config, structured
  `evidence` JSON. Rule output is a pure function of stored inputs + config version.
- **Savings** (`core/savings.py`): `Decimal` math, explicit currency, measured vs estimated
  cost, de-duplication across overlapping findings, and an explicit confidence/assumptions
  record.
- **Audit** (`core/audit.py`): append-only event writer; no update/delete API.

## 6. Background processing

- A lightweight `scheduler` enqueues DB-backed `scheduled_jobs`; worker entry points claim
  jobs with a state machine (`queued → running → succeeded|failed`).
- Overlapping scans for the same `(account, job_type)` are prevented via a unique
  constraint / advisory lock.
- Bounded retries with error summaries and `last_success_at` per job type.
- The dashboard never blocks on background work; it reads persisted state.

## 7. Data flow

1. **Connect** account (assume role verified) → `cloud_accounts` + audit event.
2. **Discovery** enumerates regions/resources → upsert `resources`, update scan status.
3. **Billing** pulls Cost Explorer → `cost_records` (service/region/account granularity).
4. **Metrics** pulls CloudWatch → `resource_metric_summaries`.
5. **Analysis** runs rules over stored data → `recommendations` (+ evidence JSON).
6. **Approval** creates `approval_requests` (payload hash) → human decision.
7. **Execution** validates + performs allowlisted action → `action_runs` + audit;
   verifies resulting AWS state before marking success.

## 8. Configuration & secrets

- `core/config.py` (Pydantic Settings) reads environment; `.env` for local dev only.
- Secrets (DB URL, JWT signing key, Fernet key) come from the environment / secret store.
- AWS access to customer accounts uses STS temporary credentials; **external IDs are stored
  encrypted** (Fernet) and never logged.
- `.env.example` contains no real secrets.

## 9. Deployment topology

Docker Compose on a Linux VM: `db` (private), `api`, `web`, `worker`, `scheduler`,
`proxy` (TLS). Non-root containers, health checks, restart policies, persistent volume,
migration step on deploy, documented backup/restore.

## 10. Explicit deviations from the original brief

Per product direction, the frontend is **Next.js (TypeScript)** rather than Streamlit,
which makes a dedicated **FastAPI** service necessary; charts use **Apache ECharts** rather
than Plotly. Python remains the backend/domain language. All other architectural principles
(evidence-first, deterministic money math, human-approved actions, least privilege, tenant
isolation, append-only audit, no termination) are unchanged.
