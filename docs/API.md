# CloudCostLens — HTTP API

FastAPI, JSON over HTTPS. Session auth via httpOnly JWT cookies. OpenAPI schema at
`/openapi.json`, interactive docs at `/docs` (disabled in production unless enabled).

The TypeScript client consumed by `apps/web` is generated from this schema.

## Conventions

- Base path: `/api/v1`.
- Money is serialized as strings to preserve precision, with a sibling `currency` field.
- Timestamps are ISO-8601 UTC.
- List endpoints return `{ items, total, page, page_size }`.
- Errors: `{ error: { code, message, details? } }` with appropriate HTTP status.
- Every request is authorized server-side; the organization is derived from the principal.

## Milestone 1 (implemented)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness/readiness (DB connectivity). |
| GET | `/version` | Build/version metadata. |
| GET | `/api/v1/meta` | Platform metadata: demo-data flag, enabled regions defaults. |

## Planned endpoints (later milestones)

### auth
`POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`,
`GET /api/v1/auth/me`.

### accounts
`GET/POST /api/v1/accounts`, `POST /api/v1/accounts/{id}/verify`,
`PUT /api/v1/accounts/{id}/regions`.

### scans
`POST /api/v1/scans`, `GET /api/v1/scans`, `GET /api/v1/scans/{id}`.

### resources
`GET /api/v1/resources`, `GET /api/v1/resources/{id}`,
`GET /api/v1/resources/{id}/metrics`, `GET /api/v1/resources/{id}/costs`,
`GET /api/v1/resources/export.csv`.

### costs
`GET /api/v1/costs/trend`, `GET /api/v1/costs/by-service`,
`GET /api/v1/costs/by-region`, `GET /api/v1/costs/by-account`,
`GET /api/v1/costs/top-drivers`, `GET /api/v1/costs/forecast`.

### recommendations
`GET /api/v1/recommendations`, `GET /api/v1/recommendations/{id}`,
`POST /api/v1/recommendations/{id}/dismiss`, `POST /api/v1/recommendations/{id}/approval`.

### approvals
`GET /api/v1/approvals`, `GET /api/v1/approvals/{id}`,
`POST /api/v1/approvals/{id}/approve`, `POST /api/v1/approvals/{id}/reject`.

### actions
`GET /api/v1/actions`, `GET /api/v1/actions/{id}`.

### audit
`GET /api/v1/audit` (append-only query, filters: date, user, account, event type, resource,
outcome).

### settings
`GET/PUT /api/v1/settings/thresholds`, `GET/POST/DELETE /api/v1/settings/exclusions`,
`GET/PUT /api/v1/settings/approval-expiry`, `GET /api/v1/settings/members`,
`PUT /api/v1/settings/members/{id}/role`.

## Action payload contract (execution)

`POST /api/v1/approvals` request body for an actionable recommendation:

```json
{
  "recommendation_id": "uuid",
  "action": "stop_instance",
  "action_parameters": {
    "instance_id": "i-0123456789abcdef0",
    "region": "eu-west-1"
  },
  "idempotency_key": "client-generated-uuid"
}
```

The server computes a canonical `payload_hash` over
`(aws_account_id, region, resource_arn, action, action_parameters)` and binds it to the
approval. Execution re-verifies the hash; **no arbitrary AWS API method is reachable** —
only `stop_instance` / `start_instance` are accepted.
