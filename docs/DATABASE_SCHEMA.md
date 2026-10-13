# CloudCostLens — Database Schema

PostgreSQL. SQLAlchemy 2.x declarative models. Money uses `NUMERIC(18, 6)` with an explicit
`currency` column (ISO-4217). All timestamps are stored in UTC (`timestamptz`) and rendered
in the user's locale by the UI.

## Conventions

- Every customer-owned row is scoped to `organization_id` (and, where relevant,
  `cloud_account_id`).
- Primary keys are UUIDs (`gen_random_uuid()`).
- `created_at` / `updated_at` on mutable tables; `first_seen` / `last_seen` on inventory.
- Ingestion is idempotent via natural unique constraints.
- `audit_events` is append-only at the application layer (no update/delete code path).
- Foreign keys are explicit; hot query paths are indexed.

## Tables

### identity

**organizations** — `id`, `name`, `slug (unique)`, `created_at`, `updated_at`.

**users** — `id`, `email (unique, citext)`, `email_verified_at` (nullable),
`password_hash` (nullable; argon2id), `display_name`, `is_active`, `last_login_at`,
`created_at`, `updated_at`. Email alone is not a verified identity: `email_verified_at`
gates sensitive actions.

**memberships** — `id`, `organization_id → organizations`, `user_id → users`,
`role` (owner|admin|finops_analyst|approver|viewer), `created_at`.
Unique `(organization_id, user_id)`.

**auth_sessions** — `id`, `user_id → users`, `refresh_token_hash`, `issued_at`,
`expires_at`, `revoked_at`, `user_agent`, `ip_hash`. Enables refresh + revocation.

### cloud

**cloud_accounts** — `id`, `organization_id`, `aws_account_id` (12-digit),
`alias`, `role_arn`, `external_id_encrypted` (Fernet), `connection_status`
(pending|connected|error), `default_region`, `enabled_regions` (JSONB array),
`last_verified_at`, `last_error`, `created_at`, `updated_at`.
Unique `(organization_id, aws_account_id)`.

**scan_runs** — `id`, `cloud_account_id`, `scan_type`
(discovery|billing|metrics|analysis), `status` (queued|running|succeeded|partial|failed),
`started_at`, `finished_at`, `region` (nullable), `resources_seen`, `error_summary`,
`created_at`.

**resources** — `id`, `organization_id`, `cloud_account_id`, `resource_type`
(ec2_instance|ebs_volume|ebs_snapshot|elastic_ip|rds_instance|rds_cluster|elb),
`resource_id`, `arn`, `name`, `region`, `state`, `environment` (tag), `owner` (tag),
`tags` (JSONB), `attributes` (JSONB; type-specific config), `monthly_cost_estimate`
(NUMERIC), `currency`, `optimization_status`
(unknown|not_analyzed|idle|underutilized|optimized|excluded),
`first_seen`, `last_seen`, `updated_at`.
Unique `(cloud_account_id, resource_type, resource_id, region)`. Indexes on
`(organization_id, resource_type)`, `(organization_id, region)`, `(organization_id, state)`.

**resource_metric_summaries** — `id`, `resource_id → resources`, `metric_name`,
`statistic` (avg|p95|max|min|sum), `value` (NUMERIC), `unit`, `period_start`,
`period_end`, `window_seconds`, `coverage_pct` (0–100; metric coverage),
`source` (cloudwatch), `collected_at`. Index `(resource_id, metric_name, period_start)`.

**cost_records** — `id`, `organization_id`, `cloud_account_id`, `service`,
`region` (nullable), `resource_id` (nullable; only when source supports resource-level),
`granularity` (daily|monthly), `period_start`, `period_end`, `amount` (NUMERIC),
`currency`, `attribution` (service|region|account|resource), `source` (cost_explorer),
`is_estimated` (bool), `collection_lag_days`, `collected_at`. Index
`(organization_id, period_start)`, `(organization_id, service)`.

**pricing_cache** — `id`, `provider` (aws_price_list|fixture), `service_code`,
`instance_type`, `region`, `term` (OnDemand|Reserved|Spot), `unit`, `price_per_unit`
(NUMERIC), `currency`, `effective_at`, `fetched_at`, `raw` (JSONB).
Unique `(provider, service_code, instance_type, region, term)`.

### optimization

**recommendations** — `id`, `organization_id`, `cloud_account_id`, `resource_id`
(nullable), `finding_type`
(idle_ec2|rightsizing_ec2|unattached_ebs|idle_elastic_ip|cost_anomaly),
`rule_id`, `rule_version`, `config_version`, `severity`, `confidence`, `operational_risk`,
`reversibility` (reversible|partially_reversible|irreversible),
`evidence` (JSONB), `observation_window_days`, `metric_coverage_pct`,
`current_monthly_cost` (NUMERIC), `projected_monthly_cost` (NUMERIC),
`estimated_monthly_savings` (NUMERIC), `estimated_annual_savings` (NUMERIC),
`currency`, `is_estimate` (bool), `assumptions` (JSONB), `recommended_action` (TEXT),
`status` (open|dismissed|approval_requested|approved|executed|superseded|expired),
`supersedes_id`, `created_at`, `updated_at`.
Unique `(cloud_account_id, resource_id, rule_id, rule_version, observation_fingerprint)`.

**resource_exclusions** — `id`, `organization_id`, `cloud_account_id`,
`resource_id` (nullable), `match_type` (resource|tag|type),
`match_key`, `match_value`, `reason`, `created_by`, `created_at`.
A resource is protected if any exclusion matches; protected resources never produce
actionable findings.

**rule_configs** — `id`, `organization_id` (nullable = platform default), `rule_id`,
`version`, `parameters` (JSONB), `is_active`, `created_by`, `created_at`.
Immutable once referenced by a recommendation (new version required to change thresholds).

### workflow

**approval_requests** — `id`, `organization_id`, `recommendation_id → recommendations`,
`cloud_account_id`, `resource_id`, `action` (stop_instance|start_instance),
`action_parameters` (JSONB), `payload_hash` (sha256 of canonical account+region+arn+
action+params), `idempotency_key` (unique), `requested_by`, `requested_at`,
`estimated_monthly_savings`, `currency`, `operational_risk`, `status`
(pending|approved|queued|executing|completed|failed|rejected|expired),
`decided_by`, `decided_at`, `decision_note`, `expires_at`, `created_at`, `updated_at`.

**action_runs** — `id`, `organization_id`, `approval_request_id → approval_requests`,
`attempt_no`, `status` (running|succeeded|failed|uncertain),
`aws_request_id`, `request_payload` (JSONB), `result` (JSONB),
`verified_state` (JSONB), `error_summary`, `started_at`, `finished_at`, `created_at`.
Prevents blind retries: an `uncertain` run must be reconciled before another attempt.

**audit_events** — `id`, `organization_id` (nullable), `actor_user_id` (nullable),
`actor_type` (user|system|worker), `event_type`, `severity` (info|warning|critical),
`entity_type`, `entity_id`, `summary`, `data` (JSONB), `created_at`.
Append-only. Index `(organization_id, created_at)`, `(organization_id, event_type)`.

**scheduled_jobs** — `id`, `organization_id`, `cloud_account_id` (nullable), `job_type`,
`status` (queued|running|succeeded|failed), `priority`, `run_after`, `locked_at`,
`locked_by`, `attempts`, `max_attempts`, `last_error`, `last_success_at`,
`created_at`, `updated_at`. Unique partial index prevents overlapping running jobs for the
same `(cloud_account_id, job_type)`.

## Migration policy

Schema is created and evolved **only** through Alembic migrations
(`alembic upgrade head`). The application never issues DDL at startup. The initial revision
is `0001_initial`.

## Tenant isolation

Repository methods require an `organization_id` and filter on it. PostgreSQL Row-Level
Security (RLS) policies are enabled per org-scoped table in the production profile as
defense-in-depth; the application sets `app.current_org` per transaction. Tests assert that
a principal from org A cannot read or mutate org B rows.
