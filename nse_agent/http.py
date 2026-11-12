from __future__ import annotations

import os
import random
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

from .config import USER_AGENT

_last_hit: dict[str, float] = {}
_down_hosts: set[str] = set()
_session: requests.Session | None = None

# afx.kwayisi.org publishes Crawl-delay: 60 in robots.txt.
HOST_DELAYS = {"afx.kwayisi.org": 60.0}
# Applies per resolved address, so a host with several A records that drops packets fails in seconds.
CONNECT_TIMEOUT = 10.0
# Base wait before retrying a 429 or 5xx, growing with each attempt, so a brief upstream outage is ridden out.
SERVER_ERROR_BACKOFF = 15.0


def _delay_for(host: str) -> float:
    override = os.environ.get("NSE_AGENT_DELAY")
    if override is not None:
        return float(override)
    return HOST_DELAYS.get(host, 2.0)


def _backoff(attempt: int, retry_after: str | None = None) -> float:
    override = os.environ.get("NSE_AGENT_DELAY")
    if override is not None:
        return float(override) * (attempt + 1)
    wait = SERVER_ERROR_BACKOFF * (attempt + 1)
    if retry_after:
        try:
            delay = float(retry_after)
        except ValueError:
            try:
                delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
            except (ValueError, TypeError, OverflowError):
                delay = 0.0
        wait = max(wait, delay)
    return min(60.0, wait + random.uniform(0, 1))


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = USER_AGENT
    return _session


def request(method: str, url: str, *, retries: int = 2, timeout: float = 45, **kwargs) -> requests.Response:
    """Rate-limited request with retries.

    A host that stays unreachable through every retry is skipped for the rest of the process,
    so a source that blocks the runner costs one failed request instead of one per page.
    """
    host = urlparse(url).netloc
    if host in _down_hosts:
        raise requests.ConnectionError(f"{host} was unreachable earlier in this run; skipping {url}")
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        wait = _delay_for(host) - (time.monotonic() - _last_hit.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.monotonic()
        try:
            resp = session().request(method, url, timeout=(CONNECT_TIMEOUT, timeout), **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                last_error = requests.HTTPError(f"{resp.status_code} for {url}")
                time.sleep(_backoff(attempt, getattr(resp, "headers", {}).get("Retry-After")))
                continue
            resp.raise_for_status()
            return resp
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(_backoff(attempt))
    assert last_error is not None
    if isinstance(last_error, (requests.ConnectionError, requests.Timeout)):
        _down_hosts.add(host)
    raise last_error


def get_text(url: str, **kwargs) -> str:
    return request("GET", url, **kwargs).text
