# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Sensible, overridable defaults. DEMO_MODE is on so the dashboard works with no cloud.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000 \
    DEMO_MODE=1 \
    DATA_DIR=/app/data \
    AWS_REGION=us-east-1 \
    COST_DAYS=30 \
    HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH

# System packages needed by the AWS and Azure CLI installers.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip gnupg lsb-release apt-transport-https \
 && rm -rf /var/lib/apt/lists/*

# --- AWS CLI v2 (architecture-aware) ---------------------------------------
ARG TARGETARCH
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
      arm64|aarch64) awsarch=aarch64 ;; \
      *)             awsarch=x86_64  ;; \
    esac; \
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${awsarch}.zip" -o /tmp/awscliv2.zip; \
    unzip -q /tmp/awscliv2.zip -d /tmp; \
    /tmp/aws/install; \
    rm -rf /tmp/aws /tmp/awscliv2.zip

# --- Azure CLI --------------------------------------------------------------
RUN curl -fsSL https://aka.ms/InstallAzureCLIDeb | bash \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Non-root runtime user with a writable HOME for ~/.aws, ~/.azure and ~/.local.
RUN useradd -m -u 10001 appuser \
 && mkdir -p /home/appuser/.aws /home/appuser/.azure /home/appuser/.local/bin /app/data \
 && chown -R appuser:appuser /home/appuser /app
USER appuser

EXPOSE 5000

# Readiness (not liveness): also confirms the SQLite store is reachable.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/ready', timeout=4).status == 200 else 1)"]

# IMPORTANT: keep --workers 1. Login and CLI-install state is held in memory,
# so multiple worker processes would not share sessions. Threads handle concurrency.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 8 --timeout 300 --graceful-timeout 30 app:app"]
