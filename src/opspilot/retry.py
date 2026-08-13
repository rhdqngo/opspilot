"""Small bounded retry policy shared by network adapters."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 0.5
    deadline_seconds: float = 10.0

    def delay(self, attempt: int, *, random_value: float) -> float:
        ceiling = min(self.max_delay_seconds, self.base_delay_seconds * (2**attempt))
        bounded_random = min(max(float(random_value), 0.0), 1.0)
        return float(max(0.0, ceiling * bounded_random))


def run_with_retry[T](
    operation: Callable[[], T],
    *,
    should_retry: Callable[[Exception], bool],
    policy: RetryPolicy,
    sleeper: Callable[[float], None] = time.sleep,
    random_source: Callable[[], float] = random.random,
    monotonic: Callable[[], float] = time.monotonic,
) -> T:
    started = monotonic()
    for attempt in range(policy.max_attempts):
        try:
            return operation()
        except Exception as error:
            if attempt + 1 >= policy.max_attempts or not should_retry(error):
                raise
            delay = policy.delay(attempt, random_value=random_source())
            if monotonic() - started + delay >= policy.deadline_seconds:
                raise
            sleeper(delay)
    raise RuntimeError("retry policy exhausted without a result")
