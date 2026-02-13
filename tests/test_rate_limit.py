from nhl_pxp.rate_limit import GameLogRateLimiter


def test_rate_limiter_sleeps_when_called_too_fast():
    times = iter([0.0, 10.0, 60.0])
    slept = []

    limiter = GameLogRateLimiter(
        interval_seconds=60,
        clock=lambda: next(times),
        sleep=lambda seconds: slept.append(seconds),
    )

    limiter.wait_for_slot()
    limiter.wait_for_slot()

    assert slept == [50.0]
