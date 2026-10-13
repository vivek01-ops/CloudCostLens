"""Bounded retry with exponential backoff and jitter.

Every AWS read goes through :func:`retry_call`, which retries only errors that
:func:`core.aws.errors.classify_exception` marks ``retryable`` and re-raises classified
errors otherwise. Sleep/randomness are injectable so tests run without real delays.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from core.aws.errors import AwsError, classify_exception
from core.config import get_settings

SleepFn = Callable[[float], None]
RetryHook = Callable[[int, AwsError, float], None]


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable retry configuration."""

    max_attempts: int = 5
    base_delay: float = 0.2
    max_delay: float = 20.0
    jitter_ratio: float = 0.5

    @classmethod
    def from_settings(cls) -> RetryPolicy:
        settings = get_settings()
        return cls(max_attempts=max(1, settings.aws_max_attempts))


def compute_delay(policy: RetryPolicy, attempt: int, rng: random.Random) -> float:
    """Exponential backoff (attempt is 1-based) capped at ``max_delay``, plus jitter."""
    raw = min(policy.max_delay, policy.base_delay * (2 ** (attempt - 1)))
    return raw + rng.uniform(0.0, raw * policy.jitter_ratio)


def retry_call[T](
    fn: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    operation: str | None = None,
    region: str | None = None,
    sleep: SleepFn = time.sleep,
    rng: random.Random | None = None,
    on_retry: RetryHook | None = None,
) -> T:
    """Invoke ``fn`` with bounded retries on retryable AWS errors."""
    active = policy or RetryPolicy()
    generator = rng or random.Random()
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as exc:
            error = classify_exception(exc, operation=operation, region=region)
            if not error.retryable or attempt >= active.max_attempts:
                raise error from exc
            delay = compute_delay(active, attempt, generator)
            if on_retry is not None:
                on_retry(attempt, error, delay)
            sleep(delay)
