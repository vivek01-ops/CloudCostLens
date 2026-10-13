# CloudCostLens — Product Requirements

> See the waste. Understand the cost. Optimize with confidence.

## 1. Purpose

CloudCostLens is an AWS Cloud Cost Intelligence and Optimization platform. It connects
(read-only) to one or more AWS accounts, discovers resources, ingests billing and
utilization telemetry, detects potentially wasteful resources with deterministic rules,
quantifies savings, and proposes optimization actions that a human must explicitly approve
before any change is executed.

The differentiator is explainability: every recommendation states **what** is costly,
**why** it may be wasteful, **how much** could be saved, **what the risks are**, and
**what will happen** if an action is approved.

## 2. Non-negotiable principles

1. Evidence before recommendations.
2. Accurate, deterministic financial calculations before any generated prose.
3. Human approval before any infrastructure change.
4. Least-privilege AWS access; discovery and execution identities are separate.
5. Enterprise-grade user experience.
6. Clear separation between measured facts, derived estimates, and illustrative data.
7. Maintainable, tested, modular Python.
8. No destructive automation in the initial release.

## 3. Target users

Individual AWS users, DevOps engineers/SREs, cloud architects, FinOps professionals,
enterprise engineering teams, administrators and approvers.

## 4. Scope — initial release

### In scope
- Read-only AWS discovery across configured regions (EC2, EBS, snapshots, Elastic IPs,
  RDS instances/clusters, ELB).
- Billing ingestion via Cost Explorer; utilization via CloudWatch.
- Deterministic recommendation engine (5 rules) with structured evidence and savings.
- Enterprise dashboard (Overview, Resources, Cost Explorer, Recommendations, Resource
  Details, Approval Center, Activity & Audit, Settings).
- Approval workflow with validation, audit trail, and **EC2 stop/start only**.
- Multi-user organizations with roles and tenant isolation.

### Out of scope (initial release)
- EC2 termination or any destructive action.
- Automatic remediation without approval.
- AWS Organizations-wide management from a single role.
- Third-party cloud providers.
- Billing data beyond what Cost Explorer exposes.

## 5. Functional requirements

### FR-1 AWS connectivity
- Support local credential chain (profile/env) and cross-account STS role assumption
  with a unique external ID.
- Never store long-lived customer keys; use temporary credentials.
- Enumerate enabled regions; record partial/incomplete scans without deleting inventory.

### FR-2 Resource inventory
- Searchable/filterable inventory (service, region, state, environment, owner, cost band,
  optimization status) with sorting, pagination, CSV export.
- Distinguish idle / stopped / missing-telemetry / not-yet-analyzed.
- Missing metric MUST NOT be treated as zero utilization.

### FR-3 Cost analysis
- Cost Explorer integration: date ranges, daily/weekly/monthly aggregation, service/
  region/account attribution, previous-period comparison, top drivers, unallocated spend.
- Always display currency, reporting period, source, and last-updated timestamp.
- Never present service-level attribution as exact per-resource cost.

### FR-4 Recommendations
- Deterministic rules with versioned thresholds and reproducible evidence.
- Fields: resource identity, account, region, finding type, evidence, observation period,
  metric coverage, current cost, post-optimization cost, monthly/annual savings,
  confidence, risk, reversibility, rule id+version, recommended action, assumptions.
- Support: view details, compare alternatives, request approval, dismiss.
- No destructive action enabled.

### FR-5 Approval & execution
- State machine: pending → approved → executing → completed | failed; plus rejected, expired.
- Approval bound to exact account/region/ARN/action/parameters via payload hash.
- Pre-execution validation and post-execution state verification.
- Idempotency key; every attempt recorded; allowlist = EC2 stop/start only.

### FR-6 Audit
- Append-only audit trail of connections, scans, findings, approvals, executions,
  configuration changes, with filters.

### FR-7 Settings
- AWS connections, enabled regions, scan config, thresholds, protected resources,
  exclusions, approval expiry, notifications, members, roles, audit config.

## 6. Non-functional requirements

- **Security**: server-enforced RBAC, tenant isolation, encrypted external IDs, no secrets
  in logs, secure first-owner bootstrap, no default admin.
- **Correctness**: `Decimal` money with explicit currency; idempotent ingestion.
- **Performance**: cached AWS responses; dashboard responsive while workers run.
- **Observability**: structured logs, job states, last-success timestamps.
- **Deployability**: Docker Compose on Linux, non-root containers, health checks,
  persistent Postgres volume, TLS reverse proxy.
- **Maintainability**: modular monolith, ruff-clean, type-checked frontend, tested.

## 7. Acceptance criteria

The release is acceptable only when all of the following hold (see `TESTING.md` for the
verification mapping):

1. App starts locally via documented commands.
2. Docker Compose starts web, api, worker, scheduler, and PostgreSQL.
3. Migrations apply successfully.
4. Read-only AWS connectivity works against a test account with valid credentials.
5. Inventory is collected across configured regions.
6. Billing/utilization data stored with timestamps and attribution limitations.
7. Rules produce deterministic, testable findings.
8. Dashboard presents findings in a professional enterprise UI.
9. Sample data is visibly labeled and never misrepresented as live.
10. Every recommendation explains evidence, assumptions, and financial impact.
11. No cloud mutation without valid human approval.
12. The release cannot terminate EC2 instances.
13. Failed/incomplete scans never create false deletion conclusions.
14. Cross-tenant access is denied.
15. Audit events recorded for approvals and actions.
16. Automated tests, linting, and deployment validation pass.
17. Documentation reflects the implemented system.
