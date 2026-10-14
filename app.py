"""CloudCostLens Lite — a tiny AWS + Azure cost & usage dashboard.

Auth mirrors each cloud's own CLI login:
  * AWS  -> `aws login`  (AWS CLI v2.32.0+, browser-based console login)
  * Azure-> `az login`   (Azure CLI, browser or device-code)

Both CLI logins cache credentials on disk; the app then reads them read-only to load
cost, usage and right-sizing data:

  * AWS  : Cost Explorer, CloudWatch EC2 CPU, EC2/EBS/EIP describe.
  * Azure: Cost Management query (via `az rest`), Monitor VM CPU, VM/Disk/Public IP list.

The app never modifies anything in either cloud — it only recommends actions.

Set DEMO_MODE=1 (default) to also allow a no-cloud demo login for local testing.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import platform
import random
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

import store

# ------------------------------------------------------------------- environment


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DEMO_MODE = _env_bool("DEMO_MODE", True)
FLASK_DEBUG = _env_bool("FLASK_DEBUG", False)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_CLI_BIN = os.getenv("AWS_CLI_BIN", "aws")
AZ_CLI_BIN = os.getenv("AZ_CLI_BIN", "az")
COST_DAYS = int(os.getenv("COST_DAYS", "30"))
DATA_DIR = os.path.abspath(os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data")))

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if DEMO_MODE:
        # Ephemeral key is fine for the no-cloud demo; sessions reset on restart.
        SECRET_KEY = secrets.token_hex(32)
    else:
        raise RuntimeError(
            "SECRET_KEY must be set when DEMO_MODE=0. Generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )

store.init(DATA_DIR)
try:
    store.prune_sessions(7 * 24 * 3600)
except Exception:  # noqa: BLE001 - cleanup is best-effort
    pass

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_env_bool("COOKIE_SECURE", not DEMO_MODE),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

# ------------------------------------------------------------------------ CSRF
# A random per-session token is embedded in every rendered page (meta tag) and
# echoed back in the X-CSRF-Token header on state-changing requests. The token is
# stored in the signed session cookie, so a cross-site page cannot read it.
_CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _csrf_token() -> str:
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


@app.context_processor
def _inject_csrf() -> dict:
    return {"csrf_token": _csrf_token()}


@app.before_request
def _csrf_protect():
    if request.method in _SAFE_METHODS or not request.path.startswith("/api/"):
        return None
    expected = session.get("csrf")
    sent = request.headers.get(_CSRF_HEADER)
    if not expected or not sent or not secrets.compare_digest(str(sent), str(expected)):
        return jsonify(error="Invalid or missing CSRF token. Reload the page and try again."), 403
    return None


# ------------------------------------------------------------- rate limiting
# Sliding-window limits (per client IP) on the auth endpoints that spawn CLI or
# cloud calls. Interactive GET polling (/api/auth/status, /install-status) is not
# throttled. Two tiers: credential/process-spawning endpoints are tighter than
# the rest of the auth surface.
_RATE_TIERS = {
    "/api/auth/login": (10, 60),
    "/api/auth/check": (10, 60),
    "/api/auth/code": (15, 60),
    "/api/auth/subscription": (10, 60),
    "/api/auth/sso/roles": (30, 60),
    "/api/auth/sso/select": (15, 60),
}
_RATE_DEFAULT_AUTH_POST = (40, 60)


@app.before_request
def _rate_limit_guard():
    if request.method != "POST" or not request.path.startswith("/api/auth/"):
        return None
    limit, window = _RATE_TIERS.get(request.path, _RATE_DEFAULT_AUTH_POST)
    key = f"{request.path}:{request.remote_addr or 'unknown'}"
    allowed, retry = store.rate_limit(key, limit, window)
    if not allowed:
        resp = jsonify(error="Too many requests. Please wait a moment and try again.")
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry)
        return resp
    return None


# ------------------------------------------------------- security headers / CSP
@app.before_request
def _security_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)
    return None


@app.context_processor
def _inject_nonce() -> dict:
    return {"csp_nonce": getattr(g, "csp_nonce", "")}


@app.after_request
def _security_headers(resp):
    nonce = getattr(g, "csp_nonce", "")
    script_src = f"script-src 'self' 'nonce-{nonce}'" if nonce else "script-src 'self'"
    resp.headers.setdefault(
        "Content-Security-Policy",
        "; ".join(
            [
                "default-src 'self'",
                script_src,
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
                "font-src 'self' https://fonts.gstatic.com",
                "img-src 'self' data:",
                "connect-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        ),
    )
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()")
    resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if app.config.get("SESSION_COOKIE_SECURE"):
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


# ------------------------------------------------------- request id + access log
@app.before_request
def _assign_request_id():
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    g.request_start = time.time()
    return None


@app.after_request
def _log_request(resp):
    rid = getattr(g, "request_id", "")
    if rid:
        resp.headers.setdefault("X-Request-ID", rid)
    if request.path.startswith("/static/"):
        return resp
    start = getattr(g, "request_start", None)
    log.info(
        "request",
        extra={
            "event": "request",
            "request_id": rid,
            "method": request.method,
            "path": request.path,
            "status": resp.status_code,
            "ms": round((time.time() - start) * 1000, 1) if start else None,
            "remote": request.remote_addr,
        },
    )
    return resp


# ------------------------------------------------------------- error handling
def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


@app.errorhandler(404)
def _handle_404(exc):
    if _wants_json():
        return jsonify(error="Not found"), 404
    return "<h1>404 Not Found</h1>", 404


@app.errorhandler(405)
def _handle_405(exc):
    if _wants_json():
        return jsonify(error="Method not allowed"), 405
    return "<h1>405 Method Not Allowed</h1>", 405


@app.errorhandler(Exception)
def _handle_exception(exc):
    if isinstance(exc, HTTPException) and exc.code and exc.code < 500:
        return exc
    rid = getattr(g, "request_id", "")
    log.exception(
        "unhandled exception", extra={"event": "error", "request_id": rid, "path": request.path}
    )
    message = f"Internal server error. Reference: {rid}" if rid else "Internal server error."
    if _wants_json():
        return jsonify(error=message), 500
    return f"<h1>500 Internal Server Error</h1><p>{message}</p>", 500


# -------------------------------------------------------------------- logging
# One-line JSON logs on stdout (gunicorn-friendly). Every log record carries a
# request_id when there is one, so a single user action can be traced end to end.
# Values that look like secrets are redacted before they are written.
_REDACT_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.I), "Bearer ***"),
    (
        re.compile(
            r'(?<![A-Za-z0-9_])((?:access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret'
            r'|authorization|password|secret|api[_-]?key)["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)',
            re.I,
        ),
        r"\1***",
    ),
]


def _redact(text: str) -> str:
    if not text:
        return text
    if "SECRET_KEY" in globals() and SECRET_KEY:
        text = text.replace(SECRET_KEY, "***")
    for pattern, repl in _REDACT_PATTERNS:
        text = pattern.sub(repl, text)
    return text


_RESERVED_LOG_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
    "message", "asctime",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": _redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_KEYS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


log = logging.getLogger("cloudcostlens")
if not getattr(log, "_ccl_configured", False):
    log.setLevel(logging.INFO)
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_JsonFormatter())
    log.addHandler(_handler)
    log.propagate = False
    log._ccl_configured = True


# ------------------------------------------------------------------- resilience
# Cloud APIs (Azure Cost Management in particular) intermittently return HTTP 429
# "Too many requests". We retry with the server-provided Retry-After when present,
# a small exponential backoff otherwise, and surface a clean 429 to the UI once the
# retries are exhausted. Read snapshots are also memoised briefly so a page refresh
# does not hammer the APIs.
class CloudThrottled(Exception):
    """Cloud provider is throttling us and retries were exhausted."""

    def __init__(self, message: str, retry_after: int = 15):
        super().__init__(message)
        self.retry_after = retry_after


_RETRY_STATUS_RE = re.compile(r"(?:^|\D)(429|too many requests|throttl)", re.I)
_RETRY_AFTER_RE = re.compile(r"retry[-_]after[\"'\s:]+(\d+)", re.I)

# Ceiling on a single backoff sleep, so one unlucky request cannot hang a worker.
_MAX_BACKOFF = 20.0


def _retry_after_seconds(text: str) -> float | None:
    """Return how long to wait if `text` describes a throttle, else None."""
    if not text or not _RETRY_STATUS_RE.search(text):
        return None
    match = _RETRY_AFTER_RE.search(text)
    if match:
        try:
            return min(float(match.group(1)), _MAX_BACKOFF)
        except ValueError:
            pass
    return 5.0


def _error_response(exc: Exception, status: int = 502):
    """Turn a caught exception into a JSON response, mapping throttles to 429."""
    if isinstance(exc, CloudThrottled):
        resp = jsonify(error=str(exc) or "Cloud provider is throttling requests.", retry_after=exc.retry_after)
        resp.status_code = 429
        resp.headers["Retry-After"] = str(exc.retry_after)
        return resp
    return jsonify(error=_cloud_error(exc)), status


_TTL_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_LOCK = threading.Lock()


def _cache_get(key: str):
    with _CACHE_LOCK:
        entry = _TTL_CACHE.get(key)
        if entry is not None and time.time() < entry[0]:
            return entry[1]
    return None


def _cache_set(key: str, value: object, ttl: int) -> None:
    with _CACHE_LOCK:
        _TTL_CACHE[key] = (time.time() + ttl, value)


def _cached(key: str, ttl: int, force: bool, producer):
    """Return a cached value for `key`, or compute + store it via `producer`."""
    if not force:
        hit = _cache_get(key)
        if hit is not None:
            return hit
    value = producer()
    _cache_set(key, value, ttl)
    return value


# AWS IAM Identity Center (SSO) profile/session we manage for in-app SSO login.
AWS_SSO_SESSION = "cloudcostlens"
AWS_SSO_PROFILE = "cloudcostlens"

HOURS_PER_MONTH = 730

# Rough on-demand hourly USD prices for common AWS instance types (for savings estimates).
AWS_HOURLY_PRICE = {
    "t3.nano": 0.0052,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
    "t3.large": 0.0832,
    "m5.large": 0.096,
    "m5.xlarge": 0.192,
    "m5.2xlarge": 0.384,
    "c5.large": 0.085,
    "c5.xlarge": 0.17,
    "r5.large": 0.126,
    "r5.xlarge": 0.252,
}

# Rough monthly USD prices for common Azure VM sizes (Linux, pay-as-you-go, East US).
AZURE_VM_PRICE = {
    "Standard_B1s": 8.0,
    "Standard_B1ms": 15.0,
    "Standard_B2s": 30.0,
    "Standard_B2ms": 61.0,
    "Standard_B4ms": 122.0,
    "Standard_D2s_v3": 70.0,
    "Standard_D4s_v3": 140.0,
    "Standard_D2s_v5": 76.0,
    "Standard_D4s_v5": 152.0,
    "Standard_E2s_v3": 92.0,
    "Standard_E4s_v3": 184.0,
    "Standard_F2s_v2": 62.0,
    "Standard_F4s_v2": 124.0,
}

# Rough monthly USD per GiB for Azure managed disks, by SKU.
AZURE_DISK_GIB_PRICE = {
    "Premium_LRS": 0.135,
    "PremiumV2_LRS": 0.15,
    "Premium_ZRS": 0.16,
    "StandardSSD_LRS": 0.075,
    "StandardSSD_ZRS": 0.095,
    "Standard_LRS": 0.04,
    "UltraSSD_LRS": 0.12,
}

# ---------------------------------------------------------------------- login state
_lock = threading.Lock()
_logins: dict[str, dict] = {}    # sid -> {"provider", "identity", "subscription"?}
_procs: dict[str, dict] = {}     # sid -> running CLI login process state
_installs: dict[str, dict] = {}  # sid -> CLI install job state

# CLI work is bounded so a burst of requests cannot spawn unbounded threads/processes.
# Installs run on a small pool; logins are capped by a semaphore and killed after a
# generous timeout so a stuck `aws/az login` cannot pin a thread forever.
_INSTALL_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ccl-install")
_MAX_PENDING_LOGINS = 6
_LOGIN_SLOTS = threading.BoundedSemaphore(_MAX_PENDING_LOGINS)
_LOGIN_TIMEOUT_SECONDS = 900


def _sid() -> str:
    sid = session.get("sid")
    if not sid:
        sid = secrets.token_urlsafe(24)
        session["sid"] = sid
    return sid


def _current() -> dict | None:
    sid = session.get("sid", "")
    if not sid:
        return None
    state = _logins.get(sid)
    if state is not None:
        return state
    # Not in this worker's memory (e.g. after a restart or on another future
    # worker) — fall back to the shared SQLite store and rehydrate the cache.
    state = store.load_session(sid)
    if state is not None:
        with _lock:
            _logins[sid] = state
    return state


def _set_login(sid: str, state: dict) -> None:
    with _lock:
        _logins[sid] = state
    try:
        store.save_session(sid, state)
    except Exception:  # noqa: BLE001 - persistence must never break login
        log.exception("failed to persist session", extra={"event": "error", "sid": sid})


def _clear_login(sid: str) -> None:
    with _lock:
        _logins.pop(sid, None)
    try:
        store.delete_session(sid)
    except Exception:  # noqa: BLE001
        log.exception("failed to delete session", extra={"event": "error", "sid": sid})


# --------------------------------------------------------------------- recommendations


def _recommend(kind: str, state: str, cpu: float | None, monthly_cost: float) -> dict:
    """Return {action, reason, monthly_savings} for one resource."""
    if kind in {"EC2", "VM"}:
        if state in {"stopped", "deallocated"}:
            return {
                "action": "terminate",
                "reason": f"Instance is {state} — you still pay for its attached disks.",
                "monthly_savings": round(monthly_cost * 0.1 + 1.0, 2),
            }
        if cpu is not None and cpu < 1.0:
            return {
                "action": "terminate",
                "reason": f"CPU average {cpu}% — looks unused.",
                "monthly_savings": monthly_cost,
            }
        if cpu is not None and cpu < 5.0:
            return {
                "action": "stop",
                "reason": f"CPU average {cpu}% — likely idle outside business hours.",
                "monthly_savings": round(monthly_cost * 0.65, 2),
            }
        return {"action": "keep", "reason": "Utilization looks healthy.", "monthly_savings": 0.0}

    if kind in {"EBS", "Disk"}:
        return {
            "action": "delete",
            "reason": "Volume is unattached — no instance is using it.",
            "monthly_savings": monthly_cost,
        }

    if kind in {"EIP", "PublicIP"}:
        return {
            "action": "release",
            "reason": "Public IP is not associated — you are charged for idle IPs.",
            "monthly_savings": round(monthly_cost, 2),
        }

    return {"action": "keep", "reason": "", "monthly_savings": 0.0}


# =========================================================================== AWS


def _aws_hourly(instance_type: str) -> float:
    return AWS_HOURLY_PRICE.get(instance_type, 0.10)


def _boto3_client(service: str, region: str, profile: str | None = None):
    import boto3

    if profile:
        return boto3.client(service, region_name=region, profile_name=profile)
    return boto3.client(service, region_name=region)


def _aws_identity(profile: str | None = None) -> dict | None:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        ident = _boto3_client("sts", AWS_REGION, profile).get_caller_identity()
    except (BotoCoreError, ClientError, Exception):
        return None
    return {"account": ident["Account"], "name": ident["Arn"], "user": ident["UserId"]}


# ---- AWS IAM Identity Center (SSO) -----------------------------------------


def _aws_config_path() -> str:
    home = os.path.expanduser("~")
    aws_dir = os.path.join(os.getenv("AWS_CONFIG_FILE_DIR") or os.path.join(home, ".aws"))
    os.makedirs(aws_dir, exist_ok=True)
    return os.getenv("AWS_CONFIG_FILE") or os.path.join(aws_dir, "config")


def _write_aws_ini(updates: dict[str, dict]) -> None:
    import configparser

    path = _aws_config_path()
    cp = configparser.ConfigParser()
    try:
        cp.read(path)
    except configparser.Error:
        cp = configparser.ConfigParser()
    for section, kv in updates.items():
        if not cp.has_section(section):
            cp.add_section(section)
        for key, value in kv.items():
            cp.set(section, key, value)
    with open(path, "w") as fh:
        cp.write(fh)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _aws_write_sso_session(start_url: str, region: str) -> None:
    _write_aws_ini(
        {
            f"sso-session {AWS_SSO_SESSION}": {
                "sso_start_url": start_url,
                "sso_region": region,
                "sso_registration_scopes": "sso:account:access",
            }
        }
    )


def _aws_write_sso_profile(account: str, role: str, region: str, start_url: str) -> str:
    _write_aws_ini(
        {
            f"sso-session {AWS_SSO_SESSION}": {
                "sso_start_url": start_url,
                "sso_region": region,
                "sso_registration_scopes": "sso:account:access",
            },
            f"profile {AWS_SSO_PROFILE}": {
                "sso_session": AWS_SSO_SESSION,
                "sso_account_id": account,
                "sso_role_name": role,
                "region": region,
                "output": "json",
            },
        }
    )
    return AWS_SSO_PROFILE


def _aws_run(args: list[str], timeout: int = 60) -> dict:
    cli = _aws_cli_path()
    if not cli:
        raise RuntimeError("AWS CLI not found.")
    proc = subprocess.run([cli, *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "aws command failed").strip())
    return json.loads(proc.stdout or "{}")


def _aws_sso_token() -> str | None:
    cache = os.path.join(os.path.dirname(_aws_config_path()), "sso", "cache")
    if not os.path.isdir(cache):
        return None
    files = [
        os.path.join(cache, f)
        for f in os.listdir(cache)
        if f.endswith(".json")
    ]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for path in files:
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if data.get("accessToken"):
            return data["accessToken"]
    return None


def _aws_sso_list_accounts(region: str, token: str) -> list[dict]:
    data = _aws_run(
        ["sso", "list-accounts", "--access-token", token, "--region", region, "-o", "json"]
    )
    return data.get("accountList", [])


def _aws_sso_list_roles(region: str, token: str, account: str) -> list[dict]:
    data = _aws_run(
        [
            "sso", "list-account-roles",
            "--access-token", token,
            "--account", account,
            "--region", region,
            "-o", "json",
        ]
    )
    return data.get("roleList", [])


def _aws_sso_commit(sid: str, region: str, start_url: str, account: str, role: str):
    profile = _aws_write_sso_profile(account, role, region, start_url)
    identity = _aws_identity(profile)
    if not identity:
        return "error", {
            "error": (
                "SSO login finished, but credentials could not be loaded for "
                f"account {account} / role {role}."
            )
        }
    _set_login(sid, {"provider": "aws", "identity": identity, "profile": profile, "sso": True})
    return "ok", {"identity": identity}



def _fetch_costs_aws(profile: str | None = None) -> tuple[list[dict], list[dict], float]:
    ce = _boto3_client("ce", "us-east-1", profile)
    end = datetime.now(UTC).date()
    start = end - timedelta(days=COST_DAYS)
    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    daily: list[dict] = []
    service_totals: dict[str, float] = {}
    for day in resp.get("ResultsByTime", []):
        day_total = 0.0
        for group in day.get("Groups", []):
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            service = group["Keys"][0]
            service_totals[service] = service_totals.get(service, 0.0) + amount
            day_total += amount
        daily.append({"date": day["TimePeriod"]["Start"], "amount": round(day_total, 2)})
    by_service = [
        {"service": name, "amount": round(amount, 2)}
        for name, amount in sorted(service_totals.items(), key=lambda kv: -kv[1])
        if amount > 0.01
    ]
    return daily, by_service, round(sum(item["amount"] for item in by_service), 2)


def _aws_cpu_avg(cw, instance_id: str, days: int = 14) -> float | None:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    resp = cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=86400,
        Statistics=["Average"],
    )
    points = resp.get("Datapoints", [])
    if not points:
        return None
    return round(sum(p["Average"] for p in points) / len(points), 1)


def _fetch_resources_aws(profile: str | None = None) -> list[dict]:
    ec2 = _boto3_client("ec2", AWS_REGION, profile)
    cw = _boto3_client("cloudwatch", AWS_REGION, profile)
    resources: list[dict] = []

    for reservation in ec2.describe_instances().get("Reservations", []):
        for inst in reservation["Instances"]:
            name = next(
                (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                inst["InstanceId"],
            )
            state = inst["State"]["Name"]
            cpu = _aws_cpu_avg(cw, inst["InstanceId"]) if state == "running" else None
            cost = round(_aws_hourly(inst["InstanceType"]) * HOURS_PER_MONTH, 2)
            resources.append(
                {
                    "id": inst["InstanceId"],
                    "kind": "EC2",
                    "name": name,
                    "state": state,
                    "detail": inst["InstanceType"],
                    "cpu": cpu,
                    "monthly_cost": cost,
                    "recommendation": _recommend("EC2", state, cpu, cost),
                }
            )

    for vol in ec2.describe_volumes(
        Filters=[{"Name": "status", "Values": ["available"]}]
    ).get("Volumes", []):
        cost = round(vol["Size"] * 0.08, 2)
        resources.append(
            {
                "id": vol["VolumeId"],
                "kind": "EBS",
                "name": vol["VolumeId"],
                "state": "unattached",
                "detail": f"{vol['Size']} GiB {vol.get('VolumeType', 'gp2')}",
                "cpu": None,
                "monthly_cost": cost,
                "recommendation": _recommend("EBS", "unattached", None, cost),
            }
        )

    for addr in ec2.describe_addresses().get("Addresses", []):
        if addr.get("AssociationId"):
            continue
        resources.append(
            {
                "id": addr.get("AllocationId", addr.get("PublicIp")),
                "kind": "EIP",
                "name": addr.get("PublicIp"),
                "state": "unassociated",
                "detail": "Elastic IP",
                "cpu": None,
                "monthly_cost": 3.65,
                "recommendation": _recommend("EIP", "unassociated", None, 3.65),
            }
        )

    return resources


# ========================================================================= Azure


def _az_exec(args: list[str], timeout: int, retries: int = 3) -> subprocess.CompletedProcess:
    """Run an az command, retrying transient 429 throttling with backoff."""
    message = "az command failed"
    wait: float | None = None
    for attempt in range(retries + 1):
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0:
            return proc
        message = (proc.stderr or proc.stdout or "az command failed").strip()
        wait = _retry_after_seconds(message)
        if wait is None or attempt == retries:
            break
        time.sleep(wait)
    if wait is not None:
        raise CloudThrottled(f"Cloud provider is throttling requests. {message}", retry_after=int(wait))
    raise RuntimeError(message)


def _az_run(args: list[str], timeout: int = 120) -> object:
    az = _az_cli_path()
    if not az:
        raise RuntimeError("Azure CLI (az) not found.")
    proc = _az_exec([az, *args], timeout)
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def _az_rest(url: str, body: dict | None = None, method: str = "post") -> dict:
    az = _az_cli_path()
    if not az:
        raise RuntimeError("Azure CLI (az) not found.")
    args = [az, "rest", "--method", method, "--url", url, "-o", "json"]
    body_path = None
    if body is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(body, fh)
            body_path = fh.name
        args += ["--body", f"@{body_path}"]
    try:
        proc = _az_exec(args, 180)
    finally:
        if body_path:
            os.unlink(body_path)
    data = json.loads(proc.stdout or "{}")
    # `az rest` sometimes exits 0 while printing a throttling error body.
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        blob = f"{err.get('code', '')} {err.get('message', '')}"
        if _retry_after_seconds(blob) is not None:
            raise CloudThrottled(
                "Cloud provider is throttling requests. " + _cloud_error(RuntimeError(json.dumps(data))),
                retry_after=10,
            )
    return data


def _az_identity(subscription_id: str | None = None) -> dict | None:
    args = ["account", "show", "-o", "json"]
    if subscription_id:
        args += ["--subscription", subscription_id]
    try:
        account = _az_run(args)
    except Exception:
        return None
    if not account:
        return None
    if not _is_real_subscription(account):
        return None
    user = account.get("user") or {}
    return {
        "account": account.get("id"),
        "name": account.get("name"),
        "tenant": account.get("tenantId"),
        "user": user.get("name") or user.get("type"),
    }


_AZ_TENANT_LEVEL_NAME = "N/A(tenant level account)"


def _is_real_subscription(account: dict) -> bool:
    """Tenant-level logins (`az login --allow-no-subscriptions`) surface a fake
    "subscription" whose id is the tenant id and whose name is the sentinel below."""
    if not account.get("id"):
        return False
    if account.get("name") == _AZ_TENANT_LEVEL_NAME:
        return False
    if account.get("state") and account.get("state") != "Enabled":
        return False
    return True


def _az_account_list() -> list[dict]:
    accounts = _az_run(["account", "list", "--all", "-o", "json"]) or []
    rows = [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "tenantId": a.get("tenantId"),
            "tenantName": a.get("tenantDisplayName") or a.get("tenantId"),
            "isDefault": a.get("isDefault", False),
            "state": a.get("state") or "Enabled",
        }
        for a in accounts
        if _is_real_subscription(a)
    ]
    rows.sort(key=lambda r: (r["state"] != "Enabled", not r["isDefault"]))
    return rows


def _fetch_costs_azure(subscription_id: str) -> tuple[list[dict], list[dict], float]:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=COST_DAYS)
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        "/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    )
    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "start": start.isoformat() + "T00:00:00Z",
            "end": end.isoformat() + "T00:00:00Z",
        },
        "dataset": {
            "granularity": "Daily",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ServiceName"}],
        },
    }
    result = _az_rest(url, body)
    props = result.get("properties", {}) if isinstance(result, dict) else {}
    columns = [c.get("name") for c in props.get("columns", [])]
    rows = props.get("rows", [])
    idx = {name: i for i, name in enumerate(columns)}
    cost_i = next((idx[k] for k in ("Cost", "PreTaxCost", "totalCost") if k in idx), None)
    svc_i = next((idx[k] for k in ("ServiceName", "MeterCategory") if k in idx), None)
    date_i = next((idx[k] for k in ("UsageDate", "BillingMonth", "Date") if k in idx), None)
    if cost_i is None:
        raise RuntimeError("Cost Management query returned no cost column.")

    daily_totals: dict[str, float] = {}
    service_totals: dict[str, float] = {}
    for row in rows:
        amount = float(row[cost_i] or 0.0)
        service = row[svc_i] if svc_i is not None else "Other"
        raw_date = row[date_i] if date_i is not None else None
        if isinstance(raw_date, (int, float)) and len(str(int(raw_date))) == 8:
            day = datetime.strptime(str(int(raw_date)), "%Y%m%d").date().isoformat()
        elif isinstance(raw_date, str) and "-" in raw_date:
            day = raw_date[:10]
        else:
            day = end.isoformat()
        daily_totals[day] = daily_totals.get(day, 0.0) + amount
        service_totals[service] = service_totals.get(service, 0.0) + amount

    daily = [{"date": d, "amount": round(v, 2)} for d, v in sorted(daily_totals.items())]
    by_service = [
        {"service": name, "amount": round(amount, 2)}
        for name, amount in sorted(service_totals.items(), key=lambda kv: -kv[1])
        if amount > 0.01
    ]
    return daily, by_service, round(sum(item["amount"] for item in by_service), 2)


def _az_cpu_avg(resource_id: str, days: int = 14) -> float | None:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    args = [
        "monitor", "metrics", "list",
        "--resource", resource_id,
        "--metrics", "Percentage CPU",
        "--aggregation", "Average",
        "--interval", "P1D",
        "--start-time", start.isoformat(),
        "--end-time", end.isoformat(),
        "-o", "json",
    ]
    try:
        data = _az_run(args, timeout=90)
    except Exception:
        return None
    values: list[float] = []
    for metric in (data or {}).get("value", []):
        for series in metric.get("timeseries", []):
            for point in series.get("data", []):
                if point.get("average") is not None:
                    values.append(float(point["average"]))
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _fetch_resources_azure(subscription_id: str) -> tuple[list[dict], list[str]]:
    resources: list[dict] = []
    warnings: list[str] = []

    try:
        vms = _az_run(["vm", "list", "-d", "--subscription", subscription_id, "-o", "json"]) or []
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"virtual machines: {_cloud_error(exc)}")
        vms = []
    for vm in vms:
        power = (vm.get("powerState") or "").replace("VM ", "").lower() or "unknown"
        size = (vm.get("hardwareProfile") or {}).get("vmSize") or "unknown"
        cpu = _az_cpu_avg(vm["id"]) if power == "running" else None
        cost = round(AZURE_VM_PRICE.get(size, 70.0), 2)
        resources.append(
            {
                "id": vm["id"],
                "kind": "VM",
                "name": vm.get("name"),
                "state": power,
                "detail": size,
                "cpu": cpu,
                "monthly_cost": cost,
                "recommendation": _recommend("VM", power, cpu, cost),
            }
        )

    # `az disk list` is resource-group scoped (it requires -g), so list managed disks
    # subscription-wide through the Resource Manager REST API instead.
    disk_url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        "/providers/Microsoft.Compute/disks?api-version=2023-04-02"
    )
    try:
        disks = (_az_rest(disk_url, method="get") or {}).get("value", []) or []
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"managed disks: {_cloud_error(exc)}")
        disks = []
    for disk in disks:
        props = disk.get("properties") or {}
        raw_state = props.get("diskState") or disk.get("diskState")
        if isinstance(raw_state, dict):
            raw_state = raw_state.get("state")
        if (raw_state or "").lower() != "unattached":
            continue
        size = props.get("diskSizeGb") or disk.get("diskSizeGb") or 0
        sku = (disk.get("sku") or {}).get("name") or "Standard_LRS"
        cost = round(size * AZURE_DISK_GIB_PRICE.get(sku, 0.06), 2)
        resources.append(
            {
                "id": disk.get("id"),
                "kind": "Disk",
                "name": disk.get("name"),
                "state": "unattached",
                "detail": f"{size} GiB {sku}",
                "cpu": None,
                "monthly_cost": cost,
                "recommendation": _recommend("Disk", "unattached", None, cost),
            }
        )

    try:
        ips = _az_run(["network", "public-ip", "list", "--subscription", subscription_id, "-o", "json"]) or []
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"public IPs: {_cloud_error(exc)}")
        ips = []
    for ip in ips:
        if ip.get("ipConfiguration"):
            continue
        resources.append(
            {
                "id": ip.get("id"),
                "kind": "PublicIP",
                "name": ip.get("name"),
                "state": "unassociated",
                "detail": ip.get("publicIPAddress") or "Public IP",
                "cpu": None,
                "monthly_cost": 3.65,
                "recommendation": _recommend("PublicIP", "unassociated", None, 3.65),
            }
        )

    return resources, warnings


# ==================================================================== demo data


def _demo_costs() -> tuple[list[dict], list[dict], float]:
    random.seed(7)
    services = [
        ("Virtual Machines", 9.0),
        ("Azure SQL Database", 6.0),
        ("Storage", 2.2),
        ("Functions", 0.8),
        ("Azure Monitor", 0.4),
    ]
    today = datetime.now(UTC).date()
    daily: list[dict] = []
    service_totals: dict[str, float] = {name: 0.0 for name, _ in services}
    for offset in range(COST_DAYS, 0, -1):
        day = today - timedelta(days=offset)
        day_total = 0.0
        for name, base in services:
            amount = round(base * random.uniform(0.75, 1.25), 2)
            service_totals[name] += amount
            day_total += amount
        daily.append({"date": day.isoformat(), "amount": round(day_total, 2)})
    by_service = [
        {"service": name, "amount": round(amount, 2)}
        for name, amount in sorted(service_totals.items(), key=lambda kv: -kv[1])
    ]
    return daily, by_service, round(sum(v["amount"] for v in by_service), 2)


def _demo_resources() -> list[dict]:
    instances = [
        ("vm-web-prod-1", "web-prod-1", "running", "Standard_D2s_v3", 42.1),
        ("vm-web-prod-2", "web-prod-2", "running", "Standard_D2s_v3", 38.7),
        ("vm-batch-worker", "batch-worker", "running", "Standard_F4s_v2", 0.4),
        ("vm-staging-api", "staging-api", "running", "Standard_B2s", 3.2),
        ("vm-old-db-replica", "old-db-replica", "deallocated", "Standard_E4s_v3", None),
        ("vm-dev-sandbox", "dev-sandbox", "running", "Standard_B2ms", 0.9),
        ("vm-ml-training", "ml-training", "running", "Standard_D4s_v5", 71.5),
    ]
    resources: list[dict] = []
    for rid, name, state, size, cpu in instances:
        cost = round(AZURE_VM_PRICE.get(size, 70.0), 2)
        resources.append(
            {
                "id": rid,
                "kind": "VM",
                "name": name,
                "state": state,
                "detail": size,
                "cpu": cpu,
                "monthly_cost": cost,
                "recommendation": _recommend("VM", state, cpu, cost),
            }
        )
    for did, size, sku in [("disk-old-data-01", 512, "Premium_LRS"), ("disk-old-data-02", 128, "StandardSSD_LRS")]:
        cost = round(size * AZURE_DISK_GIB_PRICE.get(sku, 0.06), 2)
        resources.append(
            {
                "id": did,
                "kind": "Disk",
                "name": did,
                "state": "unattached",
                "detail": f"{size} GiB {sku}",
                "cpu": None,
                "monthly_cost": cost,
                "recommendation": _recommend("Disk", "unattached", None, cost),
            }
        )
    resources.append(
        {
            "id": "ip-idle-01",
            "kind": "PublicIP",
            "name": "pip-idle-01",
            "state": "unassociated",
            "detail": "20.0.113.24",
            "cpu": None,
            "monthly_cost": 3.65,
            "recommendation": _recommend("PublicIP", "unassociated", None, 3.65),
        }
    )
    return resources


# ==================================================================== CLI discovery


def _aws_cli_path() -> str | None:
    """Locate the AWS CLI: explicit path, PATH lookup, then common user-local installs."""
    if os.sep in AWS_CLI_BIN or AWS_CLI_BIN.startswith("."):
        return AWS_CLI_BIN if os.access(AWS_CLI_BIN, os.X_OK) else None
    found = shutil.which(AWS_CLI_BIN)
    if found:
        return found
    for candidate in ("~/.local/bin/aws", "/usr/local/bin/aws", "/usr/bin/aws"):
        path = os.path.expanduser(candidate)
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return None


def _az_cli_path() -> str | None:
    """Locate the Azure CLI: explicit path, PATH lookup, then the app-managed venv."""
    if os.sep in AZ_CLI_BIN or AZ_CLI_BIN.startswith("."):
        return AZ_CLI_BIN if os.access(AZ_CLI_BIN, os.X_OK) else None
    found = shutil.which(AZ_CLI_BIN)
    if found:
        return found
    home = os.path.expanduser("~")
    for candidate in (
        os.path.join(home, ".local", "azure-cli", "venv", "bin", "az"),
        os.path.join(home, ".local", "bin", "az"),
        "/usr/local/bin/az",
        "/usr/bin/az",
    ):
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _cli_path(provider: str) -> str | None:
    return _aws_cli_path() if provider == "aws" else _az_cli_path()


# =================================================================== CLI install


def _install_aws(log, info) -> None:
    if _aws_cli_path():
        log(f"AWS CLI is already available at {_aws_cli_path()}.")
        info["status"] = "ok"
        return
    machine = platform.machine().lower()
    arch = "aarch64" if machine in {"aarch64", "arm64"} else "x86_64"
    url = f"https://awscli.amazonaws.com/awscli-exe-linux-{arch}.zip"
    home = os.path.expanduser("~")
    install_dir = os.path.join(home, ".local", "aws-cli")
    bin_dir = os.path.join(home, ".local", "bin")

    log(f"Downloading AWS CLI v2 ({arch}) from awscli.amazonaws.com …")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "awscliv2.zip")
        urllib.request.urlretrieve(url, zip_path)
        log("Download complete. Extracting …")
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(tmp)
            # zipfile does not restore Unix permission bits; do it from the metadata
            # so the bundled `aws` binary and `install` script stay executable.
            for member in archive.infolist():
                mode = member.external_attr >> 16
                target = os.path.join(tmp, member.filename)
                if mode and os.path.exists(target):
                    os.chmod(target, mode)
        installer = os.path.join(tmp, "aws", "install")
        os.chmod(installer, 0o755)
        log(f"Installing to {install_dir} (bin: {bin_dir}) …")
        proc = subprocess.run(
            [installer, "-i", install_dir, "-b", bin_dir, "--update"],
            capture_output=True,
            text=True,
        )
        for line in (proc.stdout + proc.stderr).splitlines():
            log(line)
        if proc.returncode != 0:
            info["status"] = "error"
            log(f"Installer exited with code {proc.returncode}.")
            return
    if _aws_cli_path():
        info["status"] = "ok"
        log("AWS CLI installed successfully. You can sign in now.")
    else:
        info["status"] = "error"
        log("Installer finished but the `aws` binary could not be found.")


def _install_azure(log, info) -> None:
    if _az_cli_path():
        log(f"Azure CLI is already available at {_az_cli_path()}.")
        info["status"] = "ok"
        return
    home = os.path.expanduser("~")
    venv_dir = os.path.join(home, ".local", "azure-cli", "venv")
    bin_dir = os.path.join(home, ".local", "bin")
    os.makedirs(os.path.dirname(venv_dir), exist_ok=True)

    if not os.path.exists(os.path.join(venv_dir, "bin", "python")):
        log(f"Creating virtual environment at {venv_dir} …")
        subprocess.run([sys.executable, "-m", "venv", venv_dir], capture_output=True, text=True)

    py = os.path.join(venv_dir, "bin", "python")
    if not os.path.exists(py):
        info["status"] = "error"
        log("Failed to create the Python virtual environment for the Azure CLI.")
        return

    log("Upgrading pip …")
    subprocess.run([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"], capture_output=True)
    log("Installing azure-cli from PyPI (this can take a few minutes) …")
    proc = subprocess.Popen(
        [py, "-m", "pip", "install", "--progress-bar", "off", "azure-cli"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is not None:
        for line in iter(proc.stdout.readline, ""):
            log(line.rstrip())
    proc.wait()
    if proc.returncode != 0:
        info["status"] = "error"
        log(f"pip exited with code {proc.returncode}.")
        return

    az_link = os.path.join(bin_dir, "az")
    target = os.path.join(venv_dir, "bin", "az")
    os.makedirs(bin_dir, exist_ok=True)
    try:
        if os.path.islink(az_link) or os.path.exists(az_link):
            os.unlink(az_link)
        os.symlink(target, az_link)
    except OSError:
        pass

    if _az_cli_path():
        info["status"] = "ok"
        log("Azure CLI installed successfully. You can sign in now.")
    else:
        info["status"] = "error"
        log("pip finished but the `az` binary could not be found.")


def _install_dir_summary(provider: str) -> str:
    if provider == "aws":
        return "~/.local/aws-cli (binary at ~/.local/bin/aws)"
    return "~/.local/azure-cli (binary at ~/.local/bin/az)"


def _run_install(sid: str, provider: str) -> None:
    info = _installs[sid]

    def log(line: str) -> None:
        with _lock:
            info["output"].append(line)
            info["output"] = info["output"][-150:]

    try:
        if provider == "aws":
            _install_aws(log, info)
        elif provider == "azure":
            _install_azure(log, info)
        else:
            info["status"] = "error"
            log(f"Unknown provider: {provider}")
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        info["status"] = "error"
        log(f"Install failed: {exc}")


# ============================================================================ auth


def _kill_login(sid: str, proc: subprocess.Popen) -> None:
    """Watchdog: terminate a login that has been waiting longer than the timeout."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
    except Exception:  # noqa: BLE001
        return
    info = _procs.get(sid)
    if info is not None:
        with _lock:
            info["output"].append(f"Login timed out after {_LOGIN_TIMEOUT_SECONDS // 60} minutes.")


def _reader(sid: str, proc: subprocess.Popen) -> None:
    timer = threading.Timer(_LOGIN_TIMEOUT_SECONDS, _kill_login, args=(sid, proc))
    timer.daemon = True
    timer.start()
    try:
        if proc.stdout is not None:
            for line in iter(proc.stdout.readline, ""):
                info = _procs.get(sid)
                if info is not None:
                    with _lock:
                        info["output"].append(line.rstrip())
                        info["output"] = info["output"][-60:]
        proc.wait()
    finally:
        timer.cancel()
        _LOGIN_SLOTS.release()
        info = _procs.get(sid)
        if info is not None:
            with _lock:
                info["exit"] = proc.returncode
                info["status"] = "ok" if proc.returncode == 0 else "error"


def _login_command(provider: str, opts: dict) -> list[str]:
    if provider == "aws":
        cli = _aws_cli_path()
        if opts.get("sso"):
            start_url = (opts.get("start_url") or "").strip()
            if not start_url:
                raise RuntimeError("An SSO start URL is required for IAM Identity Center login.")
            region = (opts.get("region") or AWS_REGION).strip() or AWS_REGION
            _aws_write_sso_session(start_url, region)
            cmd = [cli, "sso", "login", "--sso-session", AWS_SSO_SESSION, "--region", region]
            if opts.get("remote") or opts.get("device_code"):
                cmd += ["--use-device-code", "--no-browser"]
            return cmd
        cmd = [cli, "login", "--region", AWS_REGION]
        if opts.get("remote") or (opts.get("signin_url") or "").strip():
            cmd.append("--remote")
        if os.getenv("AWS_PROFILE"):
            cmd += ["--profile", os.getenv("AWS_PROFILE")]
        return cmd
    cli = _az_cli_path()
    cmd = [cli, "login", "--allow-no-subscriptions"]
    if opts.get("device_code"):
        cmd.append("--use-device-code")
    tenant = (opts.get("tenant") or "").strip()
    if tenant:
        cmd += ["--tenant", tenant]
    return cmd


def _finalize_azure(sid: str, subscription: dict) -> dict:
    identity = _az_identity(subscription["id"]) or {
        "account": subscription["id"],
        "name": subscription["name"],
        "tenant": subscription.get("tenantId"),
        "user": None,
    }
    state = {"provider": "azure", "identity": identity, "subscription": subscription}
    _set_login(sid, state)
    return identity


def _finalize_login(sid: str, provider: str):
    """Called once the CLI login process exits 0. Returns (status, payload)."""
    if provider == "aws":
        info = _procs.get(sid) or {}
        opts = info.get("opts") or {}
        if opts.get("sso"):
            region = (opts.get("region") or AWS_REGION).strip() or AWS_REGION
            start_url = (opts.get("start_url") or "").strip()
            account = (opts.get("account") or "").strip()
            role = (opts.get("role") or "").strip()
            if account and role:
                return _aws_sso_commit(sid, region, start_url, account, role)
            token = _aws_sso_token()
            if not token:
                return "error", {"error": "SSO login finished but no access token was cached."}
            try:
                accounts = _aws_sso_list_accounts(region, token)
            except Exception as exc:  # noqa: BLE001
                return "error", {"error": _cloud_error(exc)}
            if not accounts:
                return "error", {"error": "SSO login succeeded but no accounts were returned."}
            if len(accounts) == 1:
                acct_id = accounts[0]["accountId"]
                try:
                    roles = _aws_sso_list_roles(region, token, acct_id)
                except Exception as exc:  # noqa: BLE001
                    return "error", {"error": _cloud_error(exc)}
                if len(roles) == 1:
                    return _aws_sso_commit(sid, region, start_url, acct_id, roles[0]["roleName"])
            with _lock:
                info["sso"] = {"region": region, "start_url": start_url, "token": token}
            return "sso_account", {
                "accounts": [
                    {"id": a["accountId"], "name": a.get("accountName") or a["accountId"]}
                    for a in accounts
                ]
            }
        identity = _aws_identity()
        if not identity:
            return "error", {"error": "`aws login` finished but credentials are not usable yet."}
        _set_login(sid, {"provider": "aws", "identity": identity})
        return "ok", {"identity": identity}

    # azure
    try:
        subs = _az_account_list()
    except Exception as exc:  # noqa: BLE001
        return "error", {"error": f"Azure login succeeded but listing subscriptions failed: {exc}"}
    if not subs:
        return "no_subscription", {
            "message": (
                "Signed in to Azure, but this account has no accessible subscriptions. "
                "Cost and resource data require an active Azure subscription. If your "
                "subscription lives in another directory, sign in again with that Tenant ID. "
                "If you already know the subscription ID, paste it below."
            )
        }
    if len(subs) == 1:
        identity = _finalize_azure(sid, subs[0])
        return "ok", {"identity": identity, "subscription": subs[0]}
    with _lock:
        _procs[sid]["subscriptions"] = subs
    return "subscription", {"subscriptions": subs}


# =========================================================================== routes


@app.get("/login")
def login_page():
    return render_template(
        "login.html",
        demo=DEMO_MODE,
        aws_available=_aws_cli_path() is not None,
        azure_available=_az_cli_path() is not None,
    )


@app.post("/api/auth/check")
def auth_check():
    """Sign in using credentials that already exist (env, ~/.aws or ~/.azure, or a cached login)."""
    provider = ((request.get_json(force=True, silent=True) or {}).get("provider")) or "aws"
    if provider == "aws":
        identity = _aws_identity()
        if not identity:
            return jsonify(ok=False, error="No usable AWS credentials found."), 400
        _set_login(_sid(), {"provider": "aws", "identity": identity})
        return jsonify(ok=True, provider="aws", identity=identity)

    if provider == "azure":
        try:
            subs = _az_account_list()
        except Exception as exc:  # noqa: BLE001
            return jsonify(ok=False, error=f"No usable Azure credentials found: {exc}"), 400
        if not subs:
            return jsonify(ok=False, error="No Azure subscriptions found."), 400
        sid = _sid()
        chosen = next((s for s in subs if s.get("isDefault")), subs[0])
        identity = _finalize_azure(sid, chosen)
        return jsonify(ok=True, provider="azure", identity=identity, subscription=chosen)

    return jsonify(ok=False, error=f"Unknown provider: {provider}"), 400


@app.post("/api/auth/install")
def install_cli():
    provider = ((request.get_json(force=True, silent=True) or {}).get("provider")) or "aws"
    if provider not in {"aws", "azure"}:
        return jsonify(error=f"Unknown provider: {provider}"), 400
    if _cli_path(provider):
        return jsonify(status="ok", message=f"CLI for {provider} is already installed.")
    sid = _sid()
    with _lock:
        if _installs.get(sid, {}).get("status") == "running":
            return jsonify(status="running")
        _installs[sid] = {"status": "running", "output": [f"Target: {_install_dir_summary(provider)}"]}
    _INSTALL_POOL.submit(_run_install, sid, provider)
    return jsonify(status="started", provider=provider)


@app.get("/api/auth/install-status")
def install_status():
    info = _installs.get(_sid())
    if not info:
        return jsonify(status="idle")
    with _lock:
        return jsonify(status=info["status"], output=list(info["output"]))


@app.post("/api/auth/login")
def auth_login():
    data = request.get_json(force=True, silent=True) or {}
    provider = data.get("provider") or "aws"
    if provider not in {"aws", "azure"}:
        return jsonify(error=f"Unknown provider: {provider}"), 400
    cli = _cli_path(provider)
    if not cli:
        name = "AWS CLI (`aws login`)" if provider == "aws" else "Azure CLI (`az login`)"
        return jsonify(error=f"{name} was not found. Install it first."), 400

    sid = _sid()
    try:
        cmd = _login_command(provider, data)
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=str(exc)), 400

    if not _LOGIN_SLOTS.acquire(blocking=False):
        return jsonify(error="Too many sign-in attempts are in progress. Please wait a moment and try again."), 429
    with _lock:
        old = _procs.get(sid)
        if old and old.get("proc") and old["proc"].poll() is None:
            try:
                old["proc"].terminate()
            except Exception:  # noqa: BLE001
                pass
        _procs[sid] = {"provider": provider, "proc": None, "output": [], "status": "running", "exit": None, "opts": data}
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        _LOGIN_SLOTS.release()
        with _lock:
            _procs.pop(sid, None)
        return jsonify(error=f"Failed to start login: {exc}"), 500
    with _lock:
        _procs[sid]["proc"] = proc
    threading.Thread(target=_reader, args=(sid, proc), daemon=True).start()
    return jsonify(status="started", provider=provider)


@app.post("/api/auth/code")
def auth_code():
    """Provide the authorization code for `aws login --remote`."""
    sid = _sid()
    info = _procs.get(sid)
    code = ((request.get_json(force=True, silent=True) or {}).get("code") or "").strip()
    if not info or info.get("proc") is None or info["proc"].stdin is None:
        return jsonify(error="No running login to submit a code to."), 400
    if not code:
        return jsonify(error="Authorization code is empty."), 400
    info["proc"].stdin.write(code + "\n")
    info["proc"].stdin.flush()
    return jsonify(status="submitted")


@app.get("/api/auth/status")
def auth_status():
    sid = _sid()
    info = _procs.get(sid)
    if not info:
        return jsonify(status="idle")
    with _lock:
        status = info["status"]
        output = list(info["output"])
        subscriptions = info.get("subscriptions")
    if status == "running":
        return jsonify(status="running", output=output)
    if info["provider"] == "azure":
        if subscriptions:
            return jsonify(status="subscription", subscriptions=subscriptions, output=output)
        state, payload = _finalize_login(sid, "azure")
        if state == "ok":
            return jsonify(status="ok", output=output, **payload)
        if state == "subscription":
            return jsonify(status="subscription", output=output, **payload)
        return jsonify(status=state, output=output, **payload)
    if status == "ok":
        state, payload = _finalize_login(sid, info["provider"])
        if state == "ok":
            return jsonify(status="ok", output=output, **payload)
        if state == "subscription":
            return jsonify(status="subscription", output=output, **payload)
        return jsonify(status=state, output=output, **payload)
    return jsonify(status="error", error=_login_error_text(output), output=output)


@app.post("/api/auth/sso/roles")
def auth_sso_roles():
    """List the roles available for an account after an AWS SSO device login."""
    sid = _sid()
    info = _procs.get(sid)
    sso = (info or {}).get("sso")
    if not info or not sso:
        return jsonify(error="No pending SSO login. Start the SSO login again."), 400
    account = ((request.get_json(force=True, silent=True) or {}).get("account") or "").strip()
    if not account:
        return jsonify(error="Select an account."), 400
    try:
        roles = _aws_sso_list_roles(sso["region"], sso["token"], account)
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=_cloud_error(exc)), 502
    return jsonify(roles=[{"name": r["roleName"]} for r in roles])


@app.post("/api/auth/sso/select")
def auth_sso_select():
    """Commit the chosen AWS SSO account + role as the active profile."""
    sid = _sid()
    info = _procs.get(sid)
    sso = (info or {}).get("sso")
    data = request.get_json(force=True, silent=True) or {}
    if not info or not sso:
        return jsonify(error="No pending SSO login. Start the SSO login again."), 400
    account = (data.get("account") or "").strip()
    role = (data.get("role") or "").strip()
    if not account or not role:
        return jsonify(error="Select an account and a role."), 400
    state, payload = _aws_sso_commit(sid, sso["region"], sso["start_url"], account, role)
    if state == "ok":
        return jsonify(status="ok", **payload)
    return jsonify(error=payload.get("error", "SSO selection failed.")), 400


def _login_error_text(output: list[str]) -> str:
    """Pick the most useful error line from CLI output instead of a generic message."""
    lines = [ln.strip() for ln in (output or []) if ln and ln.strip()]
    for line in reversed(lines):
        low = line.lower()
        if any(k in low for k in ("error", "404", "bad request", "badrequest", "denied", "invalid", "failed", "expired", "unable")):
            return _cloud_error(RuntimeError(line))
    return lines[-1] if lines else "Login failed. See the log above."


@app.post("/api/auth/subscription")
def auth_subscription():
    sid = _sid()
    info = _procs.get(sid)
    sub_id = ((request.get_json(force=True, silent=True) or {}).get("id") or "").strip()
    subs = (info or {}).get("subscriptions") or []
    chosen = next((s for s in subs if s["id"] == sub_id), None)
    if not chosen and sub_id:
        identity = _az_identity(sub_id)
        if identity:
            chosen = {
                "id": sub_id,
                "name": identity.get("name") or sub_id,
                "tenantId": identity.get("tenant"),
                "tenantName": identity.get("tenant"),
                "isDefault": False,
                "state": "Enabled",
            }
    if not chosen:
        return jsonify(error="That subscription is not accessible to this account."), 400
    identity = _finalize_azure(sid, chosen)
    return jsonify(status="ok", identity=identity, subscription=chosen)


@app.post("/api/auth/demo")
def auth_demo():
    if not DEMO_MODE:
        return jsonify(error="Demo mode is disabled."), 400
    _set_login(_sid(), {"provider": "demo", "identity": None})
    return jsonify(status="ok")


@app.get("/api/auth/me")
def auth_me():
    state = _current()
    if not state:
        return jsonify(logged_in=False)
    return jsonify(
        logged_in=True,
        provider=state["provider"],
        identity=state.get("identity"),
        subscription=state.get("subscription"),
        role=_role_label(state),
        region=AWS_REGION if state["provider"] == "aws" else None,
    )


@app.post("/api/auth/logout")
def auth_logout():
    sid = session.get("sid", "")
    info = _procs.get(sid)
    if info and info.get("proc") and info["proc"].poll() is None:
        info["proc"].terminate()
    _clear_login(sid)
    with _lock:
        _procs.pop(sid, None)
    session.clear()
    return jsonify(status="ok")


# =========================================================================== data


@app.get("/")
def dashboard():
    state = _current()
    if not state:
        return redirect(url_for("login_page"))
    identity = state.get("identity") or {}
    sub = state.get("subscription") or {}
    return render_template(
        "index.html",
        provider=state["provider"],
        demo=state["provider"] == "demo",
        region=AWS_REGION if state["provider"] == "aws" else None,
        account=identity.get("name") or identity.get("account"),
        detail=sub.get("name") if state["provider"] == "azure" else identity.get("user"),
        days=COST_DAYS,
    )


@app.get("/api/costs")
def api_costs():
    state = _current()
    if not state:
        return jsonify(error="not authenticated"), 401
    force = request.args.get("force") in {"1", "true", "yes"}
    try:
        if state["provider"] == "demo":
            daily, by_service, total = _demo_costs()
        elif state["provider"] == "aws":
            profile = state.get("profile")
            daily, by_service, total = _cached(
                f"aws:cost:{profile}:{COST_DAYS}", 300, force, lambda: _fetch_costs_aws(profile)
            )
        else:
            sub_id = state["subscription"]["id"]
            daily, by_service, total = _cached(
                f"az:cost:{sub_id}:{COST_DAYS}", 300, force, lambda: _fetch_costs_azure(sub_id)
            )
    except Exception as exc:  # noqa: BLE001
        return _error_response(exc)
    return jsonify(currency="USD", days=COST_DAYS, total=total, daily=daily, by_service=by_service)


@app.get("/api/resources")
def api_resources():
    state = _current()
    if not state:
        return jsonify(error="not authenticated"), 401
    force = request.args.get("force") in {"1", "true", "yes"}
    warnings: list[str] = []
    try:
        if state["provider"] == "demo":
            resources = _demo_resources()
        elif state["provider"] == "aws":
            profile = state.get("profile")
            resources = _cached(f"aws:res:{profile}", 120, force, lambda: _fetch_resources_aws(profile))
        else:
            sub_id = state["subscription"]["id"]
            resources, warnings = _cached(
                f"az:res:{sub_id}", 120, force, lambda: _fetch_resources_azure(sub_id)
            )
    except Exception as exc:  # noqa: BLE001
        return _error_response(exc)
    actionable = [r for r in resources if r["recommendation"]["action"] != "keep"]
    monthly_savings = round(sum(r["recommendation"]["monthly_savings"] for r in actionable), 2)
    scope = AWS_REGION if state["provider"] in {"aws", "demo"} else (state.get("subscription") or {}).get("name")
    return jsonify(
        scope=scope,
        resources=resources,
        actionable=len(actionable),
        monthly_savings=monthly_savings,
        warnings=warnings,
    )


# =============================================================== diagnostics


def _usd(amount: float) -> str:
    return f"${amount:,.2f}"


def _az_current_principal() -> str | None:
    """Object ID of the currently signed-in Azure user (needs Graph access)."""
    try:
        user = _az_run(["ad", "signed-in-user", "show", "-o", "json"])
    except Exception:  # noqa: BLE001
        return None
    return (user or {}).get("id")


def _az_role_assignments(subscription_id: str) -> list[dict]:
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        "/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01"
    )
    return (_az_rest(url, method="get") or {}).get("value", []) or []


def _az_role_name(subscription_id: str, role_definition_id: str) -> str:
    rid = (role_definition_id or "").rsplit("/", 1)[-1]
    if not rid:
        return "Unknown"
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/Microsoft.Authorization/roleDefinitions/{rid}?api-version=2022-04-01"
    )
    try:
        data = _az_rest(url, method="get") or {}
        return (data.get("properties") or {}).get("roleName") or rid
    except Exception:  # noqa: BLE001
        return rid


def _az_permission_actions(subscription_id: str) -> list[str]:
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        "/providers/Microsoft.Authorization/permissions?api-version=2022-04-01"
    )
    data = _az_rest(url, method="get") or {}
    actions: list[str] = []
    for entry in data.get("value", []) or []:
        actions.extend(entry.get("actions", []) or [])
    return sorted(set(actions))


def _disk_is_unattached(disk: dict) -> bool:
    props = disk.get("properties") or {}
    raw = props.get("diskState") or disk.get("diskState")
    if isinstance(raw, dict):
        raw = raw.get("state")
    return (raw or "").lower() == "unattached"


_AZ_TOKEN_OID_CACHE: dict[str, tuple[float, str | None]] = {}
_AZ_USER_ROLES_CACHE: dict[tuple[str, str], tuple[float, list]] = {}


def _az_token_oid(subscription_id: str) -> str | None:
    """Object ID (oid) of the principal the ARM token actually represents."""
    now = time.time()
    cached = _AZ_TOKEN_OID_CACHE.get(subscription_id)
    if cached and now - cached[0] < 1800:
        return cached[1]
    oid = None
    try:
        data = _az_run(["account", "get-access-token", "--subscription", subscription_id, "-o", "json"])
        token = (data or {}).get("accessToken") or ""
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        oid = claims.get("oid")
    except Exception:  # noqa: BLE001
        oid = None
    _AZ_TOKEN_OID_CACHE[subscription_id] = (now, oid)
    return oid


def _az_scope_type(scope: str) -> str:
    low = (scope or "").lower()
    if "/resourcegroups/" in low:
        return "Resource group"
    if "microsoft.management/managementgroups" in low:
        return "Management group"
    if low.startswith("/subscriptions/"):
        return "Subscription"
    return "Other"


def _az_user_roles(subscription_id: str, principal_id: str) -> list[dict]:
    """Role assignments granted to a principal at the subscription scope (and inherited)."""
    key = (subscription_id, principal_id)
    now = time.time()
    cached = _AZ_USER_ROLES_CACHE.get(key)
    if cached and now - cached[0] < 120:
        return [dict(r) for r in cached[1]]
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        "/providers/Microsoft.Authorization/roleAssignments"
        f"?api-version=2022-04-01&$filter=assignedTo('{principal_id}')"
    )
    data = _az_rest(url, method="get") or {}
    roles: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for a in data.get("value", []) or []:
        props = a.get("properties") or {}
        scope = props.get("scope") or ""
        name = _az_role_name(subscription_id, props.get("roleDefinitionId") or "")
        key = (name, scope)
        if key in seen:
            continue
        seen.add(key)
        roles.append({"role": name, "scope": scope, "scope_type": _az_scope_type(scope)})
    _AZ_USER_ROLES_CACHE[(subscription_id, principal_id)] = (now, roles)
    return roles


def _aws_role_label(arn: str | None) -> str:
    if not arn:
        return "—"
    if ":assumed-role/" in arn:
        return arn.split(":assumed-role/", 1)[1].split("/", 1)[0] or "—"
    if ":user/" in arn:
        return "IAM user " + arn.split(":user/", 1)[1]
    return "—"


def _aws_user_roles(profile: str | None, arn: str | None) -> tuple[list[dict], str | None]:
    policies: list[dict] = []
    try:
        iam = _boto3_client("iam", AWS_REGION, profile)
        if ":assumed-role/" in (arn or ""):
            role_name = arn.split(":assumed-role/", 1)[1].split("/", 1)[0]
            for p in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", []) or []:
                policies.append({"role": p.get("PolicyName"), "scope": role_name, "scope_type": "Attached policy"})
            for name in iam.list_role_policies(RoleName=role_name).get("PolicyNames", []) or []:
                policies.append({"role": name, "scope": role_name, "scope_type": "Inline policy"})
        elif ":user/" in (arn or ""):
            user_name = arn.split(":user/", 1)[1]
            for p in iam.list_attached_user_policies(UserName=user_name).get("AttachedPolicies", []) or []:
                policies.append({"role": p.get("PolicyName"), "scope": user_name, "scope_type": "Attached policy"})
            for name in iam.list_user_policies(UserName=user_name).get("PolicyNames", []) or []:
                policies.append({"role": name, "scope": user_name, "scope_type": "Inline policy"})
    except Exception as exc:  # noqa: BLE001
        return policies, _cloud_error(exc)
    return policies, None


def _role_label(state: dict) -> str:
    """Short human label of the role the current session is operating as."""
    identity = state.get("identity") or {}
    provider = state.get("provider")
    if provider == "aws":
        return _aws_role_label(identity.get("name"))
    if provider == "azure":
        subscription_id = (state.get("subscription") or {}).get("id")
        if not subscription_id:
            return "—"
        oid = _az_token_oid(subscription_id)
        if not oid:
            return "—"
        try:
            roles = _az_user_roles(subscription_id, oid)
        except Exception:  # noqa: BLE001
            return "—"
        return ", ".join(dict.fromkeys(r["role"] for r in roles)) or "—"
    return "—"


def _azure_checks(subscription_id: str) -> list[dict]:
    checks: list[dict] = [{"name": "Cost Management", "ok": False, "detail": "Query failed", "count": None, "error": None}]
    try:
        _daily, by_service, total = _fetch_costs_azure(subscription_id)
        checks[0] = {
            "name": "Cost Management", "ok": True,
            "detail": f"{len(by_service)} service(s) · {_usd(total)} over {COST_DAYS}d",
            "count": len(by_service), "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        checks[0]["error"] = _cloud_error(exc)

    try:
        vms = _az_run(["vm", "list", "-d", "--subscription", subscription_id, "-o", "json"]) or []
        checks.append({"name": "Virtual machines", "ok": True, "detail": f"{len(vms)} VM(s)", "count": len(vms), "error": None})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "Virtual machines", "ok": False, "detail": "List failed", "count": None, "error": _cloud_error(exc)})

    disk_url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        "/providers/Microsoft.Compute/disks?api-version=2023-04-02"
    )
    try:
        disks = (_az_rest(disk_url, method="get") or {}).get("value", []) or []
        unattached = [d for d in disks if _disk_is_unattached(d)]
        checks.append({
            "name": "Managed disks", "ok": True,
            "detail": f"{len(disks)} disk(s) · {len(unattached)} unattached",
            "count": len(disks), "error": None,
        })
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "Managed disks", "ok": False, "detail": "List failed", "count": None, "error": _cloud_error(exc)})

    try:
        ips = _az_run(["network", "public-ip", "list", "--subscription", subscription_id, "-o", "json"]) or []
        free = [i for i in ips if not i.get("ipConfiguration")]
        checks.append({
            "name": "Public IPs", "ok": True,
            "detail": f"{len(ips)} IP(s) · {len(free)} unassociated",
            "count": len(ips), "error": None,
        })
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "Public IPs", "ok": False, "detail": "List failed", "count": None, "error": _cloud_error(exc)})

    try:
        assignments = _az_role_assignments(subscription_id)
        checks.append({"name": "Role assignments", "ok": True, "detail": f"{len(assignments)} assignment(s)", "count": len(assignments), "error": None})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "Role assignments", "ok": False, "detail": "Read failed", "count": None, "error": _cloud_error(exc)})

    return checks


def _diagnostics_azure(state: dict) -> dict:
    sub = state.get("subscription") or {}
    subscription_id = sub.get("id")
    result: dict = {
        "provider": "azure",
        "scope": sub.get("name") or subscription_id,
        "identity": state.get("identity") or {},
        "subscription": sub,
        "tenant": sub.get("tenantId"),
        "current_principal": None,
        "role": "—",
        "roles": [],
        "roles_error": None,
        "user_roles": [],
        "user_roles_error": None,
        "permissions": {"actions": [], "error": None},
        "checks": [],
        "required_access": [],
        "hint": None,
    }
    if not subscription_id:
        result["hint"] = "No Azure subscription is selected for this session."
        return result

    result["current_principal"] = _az_token_oid(subscription_id) or _az_current_principal()

    role_cache: dict[str, str] = {}
    try:
        assignments = _az_role_assignments(subscription_id)
        roles = []
        for a in assignments[:100]:
            props = a.get("properties") or {}
            definition = props.get("roleDefinitionId") or ""
            if definition not in role_cache:
                role_cache[definition] = _az_role_name(subscription_id, definition)
            pid = props.get("principalId")
            roles.append({
                "role": role_cache[definition],
                "principal_id": pid,
                "principal_type": props.get("principalType") or "Unknown",
                "is_you": bool(result["current_principal"] and pid and pid.lower() == result["current_principal"].lower()),
                "scope": props.get("scope"),
            })
        roles.sort(key=lambda r: (not r["is_you"], r["role"]))
        result["roles"] = roles
    except Exception as exc:  # noqa: BLE001
        result["roles_error"] = _cloud_error(exc)

    if result["current_principal"]:
        try:
            result["user_roles"] = _az_user_roles(subscription_id, result["current_principal"])
        except Exception as exc:  # noqa: BLE001
            result["user_roles_error"] = _cloud_error(exc)
    result["role"] = ", ".join(dict.fromkeys(r["role"] for r in result["user_roles"])) or "—"

    try:
        result["permissions"]["actions"] = _az_permission_actions(subscription_id)
    except Exception as exc:  # noqa: BLE001
        result["permissions"]["error"] = _cloud_error(exc)

    result["checks"] = _azure_checks(subscription_id)

    resource_checks = {c["name"] for c in result["checks"] if c["name"] in {"Virtual machines", "Managed disks", "Public IPs"}}
    resources_ok = bool(resource_checks) and all(c["ok"] for c in result["checks"] if c["name"] in resource_checks)
    cost_check = next((c for c in result["checks"] if c["name"] == "Cost Management"), None)
    costs_ok = bool(cost_check and cost_check["ok"])

    you = [r for r in result["roles"] if r.get("is_you")]
    your_roles = {r["role"].strip().lower() for r in you}
    read_roles = {"owner", "contributor", "reader"}
    cost_roles = {"owner", "contributor", "cost management reader", "billing reader"}
    if result["roles"]:
        resources_present = any(r in your_roles for r in read_roles)
        costs_present = any(r in your_roles for r in cost_roles)
    else:
        resources_present, costs_present = resources_ok, costs_ok

    result["required_access"] = [
        {"name": "Reader", "purpose": "List virtual machines, managed disks and public IPs.", "present": resources_present},
        {"name": "Cost Management Reader", "purpose": "Run the Cost Management query for spend data.", "present": costs_present},
    ]

    if result["roles"] and not you:
        result["hint"] = (
            "Your signed-in identity does not appear in this subscription's role assignments. "
            "Grant this account Reader + Cost Management Reader at the subscription, or sign in to the "
            "tenant that owns the subscription."
        )
    elif result["roles_error"] and not result["roles"]:
        result["hint"] = (
            "Role assignments could not be read — this usually means your token belongs to a different "
            "tenant than the subscription. Sign in with the subscription's home tenant."
        )
    elif not resources_present or not costs_present:
        missing = [n for n, p in (("Reader", resources_present), ("Cost Management Reader", costs_present)) if not p]
        result["hint"] = "Add the missing role(s) on this subscription: " + ", ".join(missing) + "."
    elif not resources_ok and not costs_ok:
        result["hint"] = "The APIs returned no data. Confirm the subscription has resources and that cost management is enabled."
    return result


def _diagnostics_aws(state: dict) -> dict:
    profile = state.get("profile")
    identity = state.get("identity") or {}
    arn = identity.get("name")
    role = _aws_role_label(arn)
    user_roles, user_roles_error = _aws_user_roles(profile, arn)
    checks: list[dict] = []

    try:
        _daily, by_service, total = _fetch_costs_aws(profile)
        checks.append({
            "name": "Cost Explorer", "ok": True,
            "detail": f"{len(by_service)} service(s) · {_usd(total)} over {COST_DAYS}d",
            "count": len(by_service), "error": None,
        })
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "Cost Explorer", "ok": False, "detail": "Query failed", "count": None, "error": _cloud_error(exc)})

    try:
        ec2 = _boto3_client("ec2", AWS_REGION, profile)
        reservations = ec2.describe_instances().get("Reservations", [])
        n = sum(len(r.get("Instances", [])) for r in reservations)
        checks.append({"name": "EC2 instances", "ok": True, "detail": f"{n} instance(s)", "count": n, "error": None})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "EC2 instances", "ok": False, "detail": "DescribeInstances failed", "count": None, "error": _cloud_error(exc)})

    try:
        volumes = _boto3_client("ec2", AWS_REGION, profile).describe_volumes().get("Volumes", [])
        n = sum(1 for v in volumes if (v.get("State") or "").lower() == "available")
        checks.append({"name": "EBS volumes", "ok": True, "detail": f"{len(volumes)} volume(s) · {n} unattached", "count": len(volumes), "error": None})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "EBS volumes", "ok": False, "detail": "DescribeVolumes failed", "count": None, "error": _cloud_error(exc)})

    try:
        addresses = _boto3_client("ec2", AWS_REGION, profile).describe_addresses().get("Addresses", [])
        n = sum(1 for a in addresses if not a.get("AssociationId"))
        checks.append({"name": "Elastic IPs", "ok": True, "detail": f"{len(addresses)} IP(s) · {n} unassociated", "count": len(addresses), "error": None})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "Elastic IPs", "ok": False, "detail": "DescribeAddresses failed", "count": None, "error": _cloud_error(exc)})

    return {
        "provider": "aws",
        "scope": AWS_REGION,
        "identity": state.get("identity") or {},
        "tenant": None,
        "subscription": None,
        "current_principal": None,
        "role": role,
        "roles": [],
        "roles_error": None,
        "user_roles": user_roles,
        "user_roles_error": user_roles_error,
        "permissions": {"actions": [], "error": "IAM permissions cannot be enumerated from the caller's own credentials."},
        "checks": checks,
        "required_access": [
            {"name": "sts:GetCallerIdentity", "purpose": "Confirm the signed-in account.", "present": None},
            {"name": "ce:GetCostAndUsage", "purpose": "Read cost data (Cost Explorer must be enabled).", "present": None},
            {"name": "ec2:DescribeInstances", "purpose": "List EC2 instances.", "present": None},
            {"name": "ec2:DescribeVolumes", "purpose": "List EBS volumes.", "present": None},
            {"name": "ec2:DescribeAddresses", "purpose": "List Elastic IPs.", "present": None},
            {"name": "cloudwatch:GetMetricStatistics", "purpose": "Read instance CPU metrics.", "present": None},
        ],
        "hint": "The AWS managed policy ReadOnlyAccess covers every call above.",
    }


@app.get("/api/diagnostics")
def api_diagnostics():
    state = _current()
    if not state:
        return jsonify(error="not authenticated"), 401
    force = request.args.get("force") in {"1", "true", "yes"}
    try:
        if state["provider"] == "azure":
            sub_id = (state.get("subscription") or {}).get("id", "")
            data = _cached(f"az:diag:{sub_id}", 120, force, lambda: _diagnostics_azure(state))
        elif state["provider"] == "aws":
            acct = (state.get("identity") or {}).get("account", "")
            data = _cached(f"aws:diag:{acct}", 120, force, lambda: _diagnostics_aws(state))
        else:
            data = {
                "provider": "demo",
                "scope": "Demo sandbox",
                "identity": state.get("identity") or {},
                "tenant": None,
                "subscription": None,
                "current_principal": None,
                "role": "—",
                "roles": [],
                "roles_error": None,
                "user_roles": [],
                "user_roles_error": None,
                "permissions": {"actions": [], "error": None},
                "checks": [],
                "required_access": [],
                "hint": "Running in demo mode — no cloud API calls are made.",
            }
    except Exception as exc:  # noqa: BLE001
        return _error_response(exc)
    return jsonify(data)


@app.get("/health")
def health():
    """Liveness probe: cheap and dependency-free so it never restarts a healthy app."""
    return jsonify(status="ok")


@app.get("/ready")
def ready():
    """Readiness probe: the database must be reachable to serve traffic. Missing
    cloud CLIs are reported but do not make the app unready (demo mode is valid)."""
    db_ok = store.ping()
    return (
        jsonify(
            status="ok" if db_ok else "error",
            db=db_ok,
            demo_mode=DEMO_MODE,
            aws_cli=_aws_cli_path() is not None,
            azure_cli=_az_cli_path() is not None,
        ),
        200 if db_ok else 503,
    )


def _cloud_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response and response.get("Error", {}).get("Message"):
        code = response["Error"].get("Code", "")
        message = response["Error"]["Message"]
        return f"{code}: {message}" if code else message
    text = str(exc).strip()
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            payload = json.loads(match.group(0))
            error = payload.get("error") or {}
            code = error.get("code") or ""
            message = error.get("message") or ""
            if message:
                return f"{code}: {message}" if code else message
        except (ValueError, AttributeError):
            pass
    text = re.sub(r"^ERROR:\s*", "", text)
    # Drop the Azure CLI help footer / reference links that it appends to usage errors.
    text = re.sub(r"\n?\s*https?://aka\.ms/\S+\s*", " ", text)
    text = re.sub(r"\n?\s*Read more about the command in reference docs.*$", "", text, flags=re.S)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if "traceback (most recent call last)" in text.lower():
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        err = next((ln for ln in lines if ln.upper().startswith("ERROR:")), "")
        head = text.split("Traceback", 1)[0].strip()
        text = err or head or (lines[0] if lines else text)
    low = text.lower()
    if "following arguments are required" in low:
        missing = text.split("required:", 1)[-1].strip()
        return f"Azure CLI usage error — a required argument ({missing}) was not provided."
    if re.search(r"\b404\b", low):
        return f"Resource not found (404) — the URL or resource ID may be wrong. {text}"
    if "bad request" in low or "badrequest" in low:
        return f"Bad request — the cloud API rejected the request. {text}"
    return text


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=FLASK_DEBUG)
