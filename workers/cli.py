"""Worker entry points.

Discovery is fully implemented (Milestone 2). The remaining entry points are runnable
stubs until their milestones land (billing/metrics → M3, analysis → M4, executor → M6,
scheduler → M6). ``--loop`` keeps a worker alive for container deployments.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable

from core.config import get_settings
from core.logging import configure_logging, get_logger

_WORKERS = ("discovery", "billing", "metrics", "analysis", "executor", "scheduler")


def _discovery_pass() -> None:
    from workers.discovery import run_once

    run_once()


def _stub_pass(name: str) -> Callable[[], None]:
    def _run() -> None:
        settings = get_settings()
        log = get_logger(f"workers.{name}")
        log.info(
            "worker_tick",
            worker=name,
            environment=settings.environment,
            note=f"'{name}' implementation arrives in a later milestone",
        )

    return _run


def _dispatch(name: str) -> Callable[[], None]:
    if name == "discovery":
        return _discovery_pass
    return _stub_pass(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ccl-worker")
    parser.add_argument("worker", choices=_WORKERS, help="worker entry point to run")
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=int, default=60, help="loop interval in seconds")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    run_pass = _dispatch(args.worker)

    if not args.loop:
        run_pass()
        return 0

    while True:
        try:
            run_pass()
        except Exception:  # pragma: no cover - defensive heartbeat
            get_logger(f"workers.{args.worker}").exception("worker_pass_failed")
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
