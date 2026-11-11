"""NSE listed-company announcements: fetch, date, match to tickers and persist."""
from __future__ import annotations

import re
from datetime import date

from . import config, storage
from .sources import nse

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


def update(today: date | None = None) -> dict:
    today = today or date.today()
    data = storage.read_json(path(), {}) or {}
    existing = data.get("items", [])
    known = {i["url"] for i in existing}
    new = []
    for a in nse.fetch_announcements():
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
    return {"new": new, "total": len(data["items"])}
