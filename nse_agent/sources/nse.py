"""Official NSE share-price ticker API. Used as the fallback price source."""
from __future__ import annotations

import html as _html
import re
from datetime import datetime

from .. import http

TICKER_URL = "https://nsenairobi.nse.co.ke/nseticker/api/v1/ticker"
ANNOUNCEMENTS_URL = "https://www.nse.co.ke/listed-company-announcements/"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.nse.co.ke",
    "Referer": "https://www.nse.co.ke/share-price/",
}


def parse_snapshot(payload: dict) -> tuple[str | None, dict[str, dict]]:
    """Return (trade date ISO, {issuer: row}). Keeps the first row per issuer (ordinary shares)."""
    message = payload.get("message") or []
    snapshot = message[0].get("snapshot", []) if message else []
    rows: dict[str, dict] = {}
    for row in snapshot:
        issuer = str(row.get("issuer", "")).upper()
        if issuer and issuer not in rows:
            rows[issuer] = row
    trade_date = None
    for part in message[1:]:
        upd = part.get("updated_at") if isinstance(part, dict) else None
        if upd and upd.get("date"):
            try:
                trade_date = datetime.strptime(upd["date"], "%d/%m/%Y").date().isoformat()
            except ValueError:
                trade_date = None
    return trade_date, rows


def fetch_snapshot() -> tuple[str | None, dict[str, dict]]:
    resp = http.request("POST", TICKER_URL, json={"nopage": "true", "isinno": "KE3000009674"}, headers=_HEADERS)
    return parse_snapshot(resp.json())


def parse_announcements(page: str) -> list[dict]:
    """Extract (title, pdf url) pairs from the NSE listed-company announcements page."""
    items = []
    pattern = re.compile(r"<h3[^>]*>([\s\S]*?)</h3>[\s\S]{0,600}?<a[^>]+href=\"([^\"]+\.pdf)\"", re.I)
    for title, url in pattern.findall(page):
        text = re.sub(r"<[^>]+>", " ", title)
        text = re.sub(r"\s+", " ", _html.unescape(text)).strip()
        if text:
            items.append({"title": text, "url": url})
    return items


def fetch_announcements() -> list[dict]:
    page = http.get_text(ANNOUNCEMENTS_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; nse-market-agent)"})
    return parse_announcements(page)
