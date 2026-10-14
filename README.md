# CloudCostLens Lite

A tiny **AWS + Azure** cost & usage dashboard. One Flask app, two HTML pages, no cloud
SDKs — it drives the official CLIs and reads their output.

Users sign in first by triggering the cloud's own CLI login:

- **AWS** → `aws login` (AWS CLI v2.32.0+, browser-based console login).
- **Azure** → `az login` (browser, or device-code when no browser is available).

Both CLIs cache credentials on disk (`~/.aws`, `~/.azure`); the app then reads them
**read-only** to load:

- **Costs**: AWS Cost Explorer, or Azure Cost Management (`az rest`).
- **Usage**: AWS CloudWatch EC2 CPU, or Azure Monitor `Percentage CPU`.
- **Resources**: AWS EC2/EBS/EIP, or Azure VM/Disk/Public IP.
- **Recommendations**: stop / terminate idle instances, delete unattached disks, release
  idle public IPs — each with an estimated monthly saving.

If you already have credentials configured, use **"I already have cloud credentials"** —
no login is triggered.

## Prerequisites

- **AWS**: AWS CLI **v2.32.0+** on `PATH` (`aws --version`).
- **Azure**: Azure CLI (`az --version`).

If a CLI is missing, the login page shows an **Install the CLI now** button:

- AWS: downloads the official AWS CLI v2 bundle → `~/.local/aws-cli` (binary `~/.local/bin/aws`).
- Azure: creates a venv at `~/.local/azure-cli/venv` and `pip install azure-cli` → `~/.local/bin/az`.

Neither needs `sudo`.

## Run (demo login, no cloud needed)

```bash
python3 -m venv .venv            # or: virtualenv -p python3 .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # http://localhost:5000
```

Click **Continue in demo mode** on the login page.

## Run against real clouds

```bash
cp .env.example .env             # set DEMO_MODE=0 to hide the demo button
.venv/bin/python app.py
```

Pick **AWS** or **Azure**, click **Sign in**, and complete the login. For Azure the app uses
the CLI device-code flow: a sign-in tab opens automatically, the code is shown on the page
(and again in the `az login` output), and after signing in you choose which subscription to
analyze. Uncheck *Use device code* to let `az login` open your desktop browser instead.

For AWS, if the browser can't open (headless/remote host), tick *Headless* to run
`aws login --remote`: the app opens the sign-in page in a tab (and shows the link), you grab
the authorization code it displays and paste it back.

To use a specific sign-in URL, paste it into **Custom sign-in URL** (this implies headless mode
and just changes the link the app opens). To sign in through **AWS IAM Identity Center (SSO)**,
tick *Use AWS IAM Identity Center (SSO)*, enter your **SSO start URL** (and optional region).
The app writes a local `sso-session` to `~/.aws/config`, runs `aws sso login`, then — if you did
not pre-fill an account ID and role — lets you pick the account and role to analyze; the chosen
pair is saved as the `cloudcostlens` profile and used for all data reads.

If your Azure account has **no accessible subscriptions**, the app says so instead of
failing: you can re-run the login with a **Tenant ID/domain** or paste a subscription ID
directly. Azure cost/resource data always requires an active subscription.

Read-only permissions needed:

- AWS: `ce:GetCostAndUsage`, `ec2:DescribeInstances`, `ec2:DescribeVolumes`,
  `ec2:DescribeAddresses`, `cloudwatch:GetMetricStatistics`, `sts:GetCallerIdentity`.
- Azure: Cost Management Reader (or `Microsoft.CostManagement/query/action`),
  Reader on the subscription (VM/Disk/Public IP list), and `Microsoft.Insights/metrics/read`.

Nothing is ever modified in either cloud — this is read-only and only recommends actions.

## Security, persistence & production

- **CSRF**: Per-session CSRF token stored in a signed cookie; mutating endpoints require the `X-CSRF-Token` header (auto-injected by `static/csrf.js`).
- **Security headers/CSP**: Strict CSP with a per-request nonce for inline scripts, HSTS (when cookies are secure), `frame-ancestors 'none'`, nosniff, Referrer-Policy, Permissions-Policy, COOP same-origin.
- **Rate limiting**: Sliding-window, per-IP/route, SQLite-backed; returns `429` with `Retry-After` when exhausted.
- **Structured logging**: JSON request logs with `X-Request-ID`; secrets/tokens are redacted.
- **Persistence**: Login sessions stored in SQLite at `DATA_DIR/sessions.db` (WAL) and rehydrated across restarts; sessions older than 7 days are pruned on startup.
- **TTL caching**: Costs/resources/diagnostics cached in memory (300s/120s/120s) with `?force=1` bypass for UI refresh.
- **Bounded concurrency**: Login jobs use a thread pool + semaphore (max pending logins) with timeouts; reader threads release slots on termination.
- **Health/ready**: `GET /health` (liveness) and `GET /ready` (readiness: SQLite store OK, CLI binaries available).
- **Theme & a11y**: Dark mode (persisted via `localStorage`, respects `prefers-color-scheme`), skip link, landmarks, `:focus-visible`, `aria-live`/`aria-busy`, drawer focus-trap, and `prefers-reduced-motion`; Chart.js is self-hosted.

## API docs

The OpenAPI 3.0 spec is in [`openapi.yaml`](openapi.yaml) (endpoints, schemas, security, rate limiting, error shapes).

## Configuration

Key environment variables (see `.env.example`):

- `DEMO_MODE` (default `1`) — show/hide the demo login; when `0`, `SECRET_KEY` is required.
- `SECRET_KEY` — required in non-demo mode; the app raises on startup if missing/empty when `DEMO_MODE=0`.
- `COOKIE_SECURE` — defaults to `not DEMO_MODE`; enable in HTTPS deployments.
- `FLASK_DEBUG` — default `0` (do not enable in production).
- `DATA_DIR` — directory for the SQLite store (`sessions.db`), defaults to `<repo>/data`.
- `PORT`, `AWS_REGION`, `AWS_PROFILE`, `AWS_CLI_BIN`, `AZ_CLI_BIN`, `COST_DAYS`.
- Boolean env values accept `true/1/yes/y/on` (case-insensitive).

## Run with Docker

The image bakes in Flask **and both CLIs** (AWS CLI v2 + Azure CLI), so it works out of the box:

```bash
docker compose up --build          # http://localhost:5000
```

It defaults to **demo mode**. To target real clouds, copy `.env.example` to `.env`, set
`DEMO_MODE=0`, then re-run. `.env` is read automatically (`DEMO_MODE`, `AWS_REGION`,
`COST_DAYS`, `SECRET_KEY`, `AWS_PROFILE`, ...); the host port follows `PORT` (default 5000).

CLI credentials, installs, and the SQLite session store persist in named volumes
(`aws-credentials`, `azure-credentials`, `cli-tools`, `data` mounted at `DATA_DIR=/app/data`). The container has no browser, so use **Headless** for AWS and the device-code
flow for Azure — the app shows the sign-in URL/code on the page. To reuse credentials already
on the host instead:

```yaml
volumes:
  - ${HOME}/.aws:/home/appuser/.aws:ro
  - ${HOME}/.azure:/home/appuser/.azure:ro
```

The container runs as a non-root user under Gunicorn (`--workers 1 --threads 8`; login/install
state is in-memory, while sessions are persisted to SQLite). It exposes both `/health`
(liveness) and `/ready` (readiness) probes.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /login` | login page (AWS / Azure) |
| `POST /api/auth/install` | download + install the selected CLI locally (no sudo) |
| `GET /api/auth/install-status` | poll install progress/output |
| `POST /api/auth/login` | run `aws login` / `az login` and stream progress |
| `GET /api/auth/status` | poll login status/output |
| `POST /api/auth/code` | submit the code for `aws login --remote` |
| `POST /api/auth/subscription` | choose an Azure subscription |
| `POST /api/auth/sso/roles` | list AWS SSO roles for a chosen account |
| `POST /api/auth/sso/select` | commit the chosen AWS SSO account + role |
| `POST /api/auth/check` | sign in with existing cloud credentials |
| `POST /api/auth/demo` | demo login (when `DEMO_MODE=1`) |
| `GET /api/auth/me` | current login state |
| `POST /api/auth/logout` | sign out |
| `GET /api/costs` | daily spend + spend by service + total |
| `GET /api/resources` | resources with usage + recommendation + savings |
| `GET /api/diagnostics` | read-only connection checks: tenant/subscription, role assignments, effective permissions, per-source API status, required roles |
| `GET /health` | liveness probe (`{status: ok}`) |
| `GET /ready` | readiness probe: SQLite store + CLI availability (200/503) |

The full request/response contract is described in [`openapi.yaml`](openapi.yaml).

## Notes

- Login *process* state (running CLIs, streamed output) is held **in memory**, so the Docker
  image runs Gunicorn with a single worker. Persisted **sessions** live in SQLite, so logins
  survive restarts; set a fixed `SECRET_KEY` to keep browser cookies valid across restarts.
- AWS `aws login` credentials auto-refresh for up to 12 hours; Azure tokens refresh via the CLI.
- Cost Explorer bills $0.01 per request; Cost Management queries are free.
- Azure data is scoped to the selected subscription; AWS data to the single region shown.
