from pytest import approx

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


def test_rate_limiter_boundary_conditions_do_not_oversleep():
    # first call: set last_request_at to 0.0
    # second call at 10.0 -> sleep 50.0, then clock updates to 60.0
    # third call at 119.9 -> sleep 0.1, then clock updates to 120.0
    # fourth call at 180.0 -> no sleep (already >= interval)
    times = iter([0.0, 10.0, 60.0, 119.9, 120.0, 180.0, 180.0])
    slept = []

    limiter = GameLogRateLimiter(
        interval_seconds=60,
        clock=lambda: next(times),
        sleep=lambda seconds: slept.append(seconds),
    )

    limiter.wait_for_slot()
    limiter.wait_for_slot()
    limiter.wait_for_slot()
    limiter.wait_for_slot()

    assert slept[0] == approx(50.0)
    assert slept[1] == approx(0.1)
    assert len(slept) == 2
