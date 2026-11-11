from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import requests

from .config import USER_AGENT

_last_hit: dict[str, float] = {}
_session: requests.Session | None = None

# afx.kwayisi.org publishes Crawl-delay: 60 in robots.txt.
HOST_DELAYS = {"afx.kwayisi.org": 60.0}


def _delay_for(host: str) -> float:
    override = os.environ.get("NSE_AGENT_DELAY")
    if override is not None:
        return float(override)
    return HOST_DELAYS.get(host, 2.0)


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = USER_AGENT
    return _session


def request(method: str, url: str, *, retries: int = 2, timeout: float = 45, **kwargs) -> requests.Response:
    host = urlparse(url).netloc
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        wait = _delay_for(host) - (time.monotonic() - _last_hit.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.monotonic()
        try:
            resp = session().request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                last_error = requests.HTTPError(f"{resp.status_code} for {url}")
                continue
            resp.raise_for_status()
            return resp
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def get_text(url: str, **kwargs) -> str:
    return request("GET", url, **kwargs).text
