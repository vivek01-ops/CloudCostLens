"""Retry/backoff behavior tests (no real sleeps)."""

from __future__ import annotations

import random

import pytest
from core.aws.errors import AwsAccessDenied, AwsThrottlingError
from core.aws.retry import RetryPolicy, compute_delay, retry_call
from tests.unit.aws.helpers import client_error


def _no_sleep(_: float) -> None:
    return None


def test_retries_until_success() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise client_error("Throttling")
        return "ok"

    policy = RetryPolicy(max_attempts=5, base_delay=0.01)
    result = retry_call(flaky, policy=policy, sleep=_no_sleep, rng=random.Random(1))
    assert result == "ok"
    assert calls["n"] == 3


def test_raises_after_exhausting_attempts() -> None:
    calls = {"n": 0}

    def always_throttled() -> None:
        calls["n"] += 1
        raise client_error("Throttling")

    policy = RetryPolicy(max_attempts=3, base_delay=0.01)
    with pytest.raises(AwsThrottlingError):
        retry_call(always_throttled, policy=policy, sleep=_no_sleep, rng=random.Random(1))
    assert calls["n"] == 3


def test_non_retryable_fails_fast() -> None:
    calls = {"n": 0}

    def denied() -> None:
        calls["n"] += 1
        raise client_error("AccessDenied")

    with pytest.raises(AwsAccessDenied):
        retry_call(denied, policy=RetryPolicy(max_attempts=5), sleep=_no_sleep)
    assert calls["n"] == 1


def test_on_retry_hook_receives_attempts() -> None:
    attempts: list[int] = []

    def flaky() -> str:
        if len(attempts) < 2:
            raise client_error("Throttling")
        return "ok"

    retry_call(
        flaky,
        policy=RetryPolicy(max_attempts=5, base_delay=0.01),
        sleep=_no_sleep,
        rng=random.Random(2),
        on_retry=lambda attempt, _err, _delay: attempts.append(attempt),
    )
    assert attempts == [1, 2]


def test_compute_delay_is_capped_and_jittered() -> None:
    policy = RetryPolicy(base_delay=1.0, max_delay=4.0, jitter_ratio=0.5)
    rng = random.Random(0)
    delay = compute_delay(policy, attempt=10, rng=rng)
    assert 4.0 <= delay <= 6.0
