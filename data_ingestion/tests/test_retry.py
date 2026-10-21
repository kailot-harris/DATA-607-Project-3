import requests

from src.fetchers import base


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err

    def json(self):
        return self._json


class _FakeSession:
    """Returns failures for the first N calls, then succeeds."""

    def __init__(self, fail_codes):
        self.fail_codes = list(fail_codes)
        self.call_count = 0

    def get(self, url, timeout=None, **kwargs):
        self.call_count += 1
        if self.fail_codes:
            return _FakeResponse(self.fail_codes.pop(0))
        return _FakeResponse(200, {"ok": True})


def test_retries_on_429_then_succeeds():
    base._last_call_at.pop("retry-test-1", None)
    session = _FakeSession(fail_codes=[429, 503])

    resp = base.get(session, "https://example.test", rate_key="retry-test-1", min_interval_sec=0)

    assert resp.status_code == 200
    assert session.call_count == 3  # two failures + one success


def test_does_not_retry_on_404():
    base._last_call_at.pop("retry-test-2", None)
    session = _FakeSession(fail_codes=[404])

    try:
        base.get(session, "https://example.test", rate_key="retry-test-2", min_interval_sec=0)
        assert False, "expected HTTPError to propagate"
    except requests.HTTPError:
        pass

    assert session.call_count == 1  # no retry attempted for a non-retryable status
