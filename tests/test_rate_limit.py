import time

from src.fetchers import base


def test_throttle_enforces_minimum_interval():
    key = "test-source-a"
    base._last_call_at.pop(key, None)

    t0 = time.monotonic()
    base.throttle(key, min_interval_sec=0.3)  # first call, nothing to wait for
    base.throttle(key, min_interval_sec=0.3)  # second call must wait ~0.3s
    elapsed = time.monotonic() - t0

    assert elapsed >= 0.29  # small tolerance for timer precision


def test_throttle_does_not_wait_if_interval_already_elapsed():
    key = "test-source-b"
    base._last_call_at[key] = time.monotonic() - 10  # last call was long ago

    t0 = time.monotonic()
    base.throttle(key, min_interval_sec=0.3)
    elapsed = time.monotonic() - t0

    assert elapsed < 0.1


def test_throttle_is_independent_per_rate_key():
    base._last_call_at["a"] = time.monotonic()
    base._last_call_at.pop("b", None)

    t0 = time.monotonic()
    base.throttle("b", min_interval_sec=0.3)  # different key, should not wait
    elapsed = time.monotonic() - t0

    assert elapsed < 0.1
