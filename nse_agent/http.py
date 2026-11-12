from __future__ import annotations

import os
import random
import ssl
import time
import hashlib
import io
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse, urlsplit

import requests

from .config import USER_AGENT

_last_hit: dict[str, float] = {}
_down_hosts: set[str] = set()
_session: requests.Session | None = None


class _SystemTrustAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl.create_default_context()
        return super().init_poolmanager(*args, **kwargs)


class Page(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.parts: list[str] = []
        self.skip = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def trusted_link(base: str, link: str) -> str:
    url = requests.utils.requote_uri(urljoin(base, link))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != urlsplit(base).netloc or parsed.username:
        raise ValueError("Document link leaves the official HTTPS host")
    return url

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
        # KNBS's certificate chain validates through the OS store on managed Windows hosts.
        _session.mount("https://www.knbs.or.ke/", _SystemTrustAdapter())
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
        except requests.exceptions.SSLError:
            raise
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


def pdf_document(url: str) -> dict[str, str]:
    from pypdf import PdfReader

    limit = 10 * 1024 * 1024
    with request("GET", url, stream=True, allow_redirects=False, timeout=45) as response:
        if response.status_code != 200:
            raise ValueError(f"PDF response must be 200, got {response.status_code}")
        chunks, size = [], 0
        for chunk in response.iter_content(64 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError("PDF exceeds the 10 MB limit")
            chunks.append(chunk)
        content = b"".join(chunks)
        if not content.startswith(b"%PDF-"):
            raise ValueError("Source did not return a PDF")
        text = "\n".join(p.extract_text(extraction_mode="layout") or ""
                         for p in PdfReader(io.BytesIO(content)).pages[:12])
        return {"text": text, "sha256": hashlib.sha256(content).hexdigest(), "url": response.url}
