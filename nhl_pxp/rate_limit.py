from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class GameLogRateLimiter:
    """Simple limiter that allows one game-log request every `interval_seconds`."""

    interval_seconds: float = 60.0
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _last_request_at: float | None = field(default=None, init=False)

    def wait_for_slot(self) -> None:
        now = self.clock()
        if self._last_request_at is None:
            self._last_request_at = now
            return

        elapsed = now - self._last_request_at
        remaining = self.interval_seconds - elapsed
        if remaining > 0:
            self.sleep(remaining)
        self._last_request_at = self.clock()
