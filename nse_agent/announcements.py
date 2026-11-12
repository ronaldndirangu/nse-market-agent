"""NSE listed-company announcements: fetch, date, match to tickers and persist."""
from __future__ import annotations

import re
import logging
from datetime import date, timedelta

from . import config, storage
from .sources import nse
log = logging.getLogger(__name__)

RESULTS_PATTERN = re.compile(
    r"\b(financial (statements|results)|results for|audited|unaudited|half[- ]year|interim results|"
    r"full[- ]year results|trading update)\b", re.I)


def path():
    return config.DATA / "announcements.json"


def _names(stock: dict) -> list[str]:
    return [stock["ticker"], *stock.get("aliases", [])]


def name_pattern(names: list[str]) -> re.Pattern:
    return re.compile(r"(?<![\w&])(" + "|".join(re.escape(n) for n in names) + r")(?![\w&])", re.I)


def match_ticker(title: str) -> str | None:
    for s in config.universe():
        if name_pattern(_names(s)).search(title):
            return s["ticker"]
    return None


def is_results(title: str) -> bool:
    return bool(RESULTS_PATTERN.search(title))


def date_for(url: str, first_seen: date) -> str:
    """Use the upload month when it is older than the first-seen month; otherwise the first-seen date."""
    m = re.search(r"/uploads/(\d{4})/(\d{2})/", url)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if (y, mo) < (first_seen.year, first_seen.month):
            return date(y, mo, 1).isoformat()
    return first_seen.isoformat()


def items() -> list[dict]:
    return (storage.read_json(path(), {}) or {}).get("items", [])


def unreviewed_results(ticker: str, as_of: date) -> list[dict]:
    from . import fundamentals
    known = fundamentals.annuals(ticker, as_of)
    if not known:
        return []
    interim = fundamentals.latest_interim(ticker, as_of)
    if interim:
        known = known + [interim]
    latest = max(p.period_end for p in known)
    sources = {p.source_url for p in known}
    pending = []
    for item in items():
        if item.get("ticker") != ticker or not item.get("results") or item.get("status") == "reviewed":
            continue
        if item["first_seen"] > as_of.isoformat():
            continue
        restated = bool(re.search(r"\b(restated|revised|restatement)\b", item["title"], re.I))
        if item["url"] in sources and not restated:
            continue
        period = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
                           r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                           r"\s+(20\d{2})\b", item["title"], re.I)
        if period:
            from datetime import datetime
            try:
                ended = datetime.strptime(f"{period[1]} {period[2]} {period[3]}", "%d %B %Y").date()
            except ValueError:
                log.warning("Results period needs verification: %s", item["url"])
                pending.append(item)
                continue
            if ended <= latest and not restated:
                continue
        else:
            annual = re.search(r"\b(?:FY\s*|annual\D{0,30}|full.year\D{0,30})(20\d{2})\b", item["title"], re.I)
            if annual and int(annual[1]) <= max(p.period_end.year for p in known if p.type == "annual") and not restated:
                continue
            if item["date"] < (as_of - timedelta(days=180)).isoformat() and not restated:
                continue
        pending.append(item)
    return pending[:3]


def update(today: date | None = None) -> dict:
    today = today or date.today()
    data = storage.read_json(path(), {}) or {}
    existing = data.get("items", [])
    known = {i["url"] for i in existing}
    new = []
    from . import health
    try:
        fetched = nse.fetch_announcements()
        if not fetched:
            raise ValueError("NSE announcements returned no documents; keeping the last successful check")
    except Exception as exc:
        health.record_announcements(False, str(exc))
        raise
    for a in fetched:
        if a["url"] in known:
            continue
        known.add(a["url"])
        item = {
            "title": a["title"], "url": a["url"], "date": date_for(a["url"], today),
            "first_seen": today.isoformat(), "ticker": match_ticker(a["title"]),
            "results": is_results(a["title"]), "status": "new",
        }
        new.append(item)
    data["items"] = sorted(existing + new, key=lambda i: (i["date"], i["title"]), reverse=True)
    data["updated"] = today.isoformat()
    storage.write_json(path(), data)
    health.record_announcements(True)
    return {"new": new, "total": len(data["items"])}
