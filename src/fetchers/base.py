"""Shared HTTP plumbing: per-source rate limiting, retry/backoff, UA headers."""
import time

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

_last_call_at: dict[str, float] = {}


def throttle(rate_key: str, min_interval_sec: float) -> None:
    """Block until at least min_interval_sec has passed since the last call
    tagged with this rate_key."""
    now = time.monotonic()
    last = _last_call_at.get(rate_key, 0.0)
    wait = min_interval_sec - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_call_at[rate_key] = time.monotonic()


def build_headers(contact_email: str) -> dict:
    return {
        "User-Agent": (
            "data607-job-pipeline-research/0.1 "
            f"(school project; contact: {contact_email})"
        )
    }


def _is_retryable(exc: BaseException) -> bool:
    return (
        isinstance(exc, requests.HTTPError)
        and exc.response is not None
        and exc.response.status_code in (429, 500, 502, 503, 504)
    )


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
def get(session: requests.Session, url: str, *, rate_key: str, min_interval_sec: float,
        timeout: float = 15, **kwargs) -> requests.Response:
    """Rate-limited, retrying GET. Raises on non-2xx after exhausting retries."""
    throttle(rate_key, min_interval_sec)
    resp = session.get(url, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp
