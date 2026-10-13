# CloudCostLens — Security

## 1. Threat model (summary)

| Threat | Control |
|---|---|
| Cross-tenant data access / IDOR | Server-side tenant scoping in repositories; RLS defense-in-depth; tests |
| Unauthorized approvals | Server-enforced RBAC; approval bound to `payload_hash` |
| Credential/secret leakage | No long-lived customer keys; encrypted external IDs; no secret logging |
| Malicious/accidental destructive action | Allowlist = EC2 stop/start; termination absent everywhere |
| Token theft | Short-lived JWT in httpOnly/Secure/SameSite cookies + rotating refresh |
| Replaying/reusing approvals | Expiry + idempotency key + single-use state transitions |
| Tampered action payloads | Canonical serialization + `payload_hash` re-checked pre-execution |
| Audit tampering | Append-only audit table; no update/delete code path |
| Blind retries of mutations | `action_runs` with `uncertain` state; reconcile before retry |

## 2. Authentication

- `AuthProvider` abstraction. MVP ships a **local credentials provider**: argon2id password
  hashing, email verification flag, and a **secure first-owner bootstrap** (one-time token
  from a CLI/script; no default admin, no hardcoded credentials).
- Sessions: short-lived access JWT (httpOnly/Secure/SameSite=Lax) + rotating refresh token
  stored **hashed** in `auth_sessions`; revocation supported.
- OIDC provider can be added behind the same interface without changing callers.
- Email alone is not identity: `users.email_verified_at` gates sensitive operations.

## 3. Authorization

- Roles: `owner`, `admin`, `finops_analyst`, `approver`, `viewer`.
- Every API call resolves a `Principal(user, organization, roles)` server-side.
- Route handlers and services assert required roles; the frontend hides controls for UX only
  and is **not** an authorization boundary.
- Approvers must hold `approver` or `admin`/`owner`; a requester cannot approve their own
  action when dual control is enabled.

## 4. Tenant isolation

- All customer rows carry `organization_id`; repository methods require it.
- The tenant id is derived from the authenticated principal, never from request payloads.
- PostgreSQL RLS enabled per org-scoped table in production; `app.current_org` is set per
  transaction. Integration tests assert denial of cross-tenant reads and writes.

## 5. AWS credential security

- Customer accounts use STS `AssumeRole` with a unique external ID → temporary credentials.
- External IDs are stored **encrypted** (Fernet, key from environment) and are never logged.
- Discovery identity is read-only; execution identity is limited to start/stop with tag
  conditions. The two are never combined.
- All AWS clients set bounded retries/timeouts; errors are classified, not swallowed.

## 6. Action execution safety

Pre-execution checks (all must pass):
1. Approval is in `approved`/`queued` state and **not expired**.
2. Acting principal holds the required role.
3. Target account, region, and ARN match the stored approval.
4. Live AWS state still permits the action (e.g., instance running for stop).
5. Resource is not excluded/protected.
6. Action + parameters hash equals the approved `payload_hash`.
Execution uses the restricted identity, records an `action_run`, then calls
`DescribeInstances` and marks success **only** on AWS-confirmed state. A changed resource
state or expired approval requires renewed review. Termination is unreachable code.

## 7. Data protection

- Secrets come from the environment/secret store; `.env.example` contains placeholders only.
- Logs are structured and scrubbed of credentials, tokens, external IDs, and PII.
- Backups: encrypted Postgres dumps with documented restore; restore is tested.
- HTTPS terminated at the reverse proxy; Postgres is never exposed publicly.

## 8. Secure defaults

- No default administrator account; bootstrap creates the first owner explicitly.
- Least-privilege IAM; no wildcard mutation actions.
- Dependency pinning; ruff/type checks and tests in CI.
- Failed scans never delete inventory; missing telemetry is never interpreted as zero.

## 9. Verification

Security-critical behaviors are covered by tests (see `TESTING.md`): tenant isolation,
RBAC enforcement, approval expiry, payload tampering, resource-state change after approval,
execution idempotency, audit event creation, and ambiguous AWS operation handling.
