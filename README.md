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

## Run with Docker

The image bakes in Flask **and both CLIs** (AWS CLI v2 + Azure CLI), so it works out of the box:

```bash
docker compose up --build          # http://localhost:5000
```

It defaults to **demo mode**. To target real clouds, copy `.env.example` to `.env`, set
`DEMO_MODE=0`, then re-run. `.env` is read automatically (`DEMO_MODE`, `AWS_REGION`,
`COST_DAYS`, `SECRET_KEY`, `AWS_PROFILE`, ...); the host port follows `PORT` (default 5000).

CLI credentials and installs persist in named volumes (`aws-credentials`, `azure-credentials`,
`cli-tools`). The container has no browser, so use **Headless** for AWS and the device-code
flow for Azure — the app shows the sign-in URL/code on the page. To reuse credentials already
on the host instead:

```yaml
volumes:
  - ${HOME}/.aws:/home/appuser/.aws:ro
  - ${HOME}/.azure:/home/appuser/.azure:ro
```

The container runs as a non-root user under a **single** Gunicorn worker (login/install state
is in-memory) with threads, and exposes a `/health` healthcheck.

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
| `GET /health` | health / demo flag / CLI availability |

## Notes

- Login state is held **in memory** in the Flask process (fine for a small single-process app —
  the Docker image therefore runs Gunicorn with `--workers 1`).
- AWS `aws login` credentials auto-refresh for up to 12 hours; Azure tokens refresh via the CLI.
- Set a fixed `SECRET_KEY` if you restart often, so browser sessions survive.
- Cost Explorer bills $0.01 per request; Cost Management queries are free.
- Azure data is scoped to the selected subscription; AWS data to the single region shown.
