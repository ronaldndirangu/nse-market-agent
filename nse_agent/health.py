"""Live evidence health, separate from valuation rules and historical reconstructions."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from . import announcements, config, fundamentals, prices, storage

EAT = timezone(timedelta(hours=3))


def now() -> datetime:
    return datetime.now(EAT)


def _weekday(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def expected_session(stamp: datetime) -> date:
    stamp = stamp.astimezone(EAT)
    day = stamp.date() if stamp.hour >= 16 else stamp.date() - timedelta(days=1)
    return _weekday(day)


def weekdays_between(start: date, end: date) -> int:
    days = 0
    while start < end:
        start += timedelta(days=1)
        days += start.weekday() < 5
    return days


def _age(day: str | None, expected: date, budget: int, business: bool = True,
         latest_allowed: date | None = None) -> str:
    if not day:
        return "Unknown"
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        return "Unknown"
    if parsed > (latest_allowed or expected):
        return "Unknown"
    age = weekdays_between(parsed, expected) if business else (expected - parsed).days
    return "Current" if age <= budget else "Delayed" if business and age <= budget + 3 else "Stale"


def record_market(snapshot: dict) -> None:
    path = storage.market_path("health.json")
    data = storage.read_json(path, {}) or {}
    stamp = now().isoformat(timespec="seconds")
    previous = data.get("prices") or {}
    success = snapshot["source"] != "cache" and not snapshot["intraday"]
    data["prices"] = {
        "last_attempt": stamp, "last_success": stamp if success else previous.get("last_success"),
        "source": snapshot["source"], "errors": snapshot["errors"], "successful": success,
        "consecutive_failures": 0 if success else previous.get("consecutive_failures", 0) + 1,
    }
    storage.write_json(path, data)


def record_announcements(success: bool, error: str | None = None) -> None:
    path = storage.market_path("health.json")
    data = storage.read_json(path, {}) or {}
    previous = data.get("announcements") or {}
    stamp = now().isoformat(timespec="seconds")
    data["announcements"] = {
        "last_attempt": stamp, "last_success": stamp if success else previous.get("last_success"),
        "successful": success, "error": error,
    }
    storage.write_json(path, data)


def assess(stamp: datetime | None = None) -> dict:
    stamp = (stamp or now()).astimezone(EAT)
    expected = expected_session(stamp)
    listing = storage.read_json(storage.market_path("listing.json"), {}) or {}
    attempts = storage.read_json(storage.market_path("health.json"), {}) or {}
    fetch = attempts.get("prices") or {}
    ann = storage.read_json(announcements.path(), {}) or {}
    ann_status = _age(ann.get("updated") if ann.get("items") else None, expected, 1, latest_allowed=stamp.date())
    if (attempts.get("announcements") or {}).get("successful") is False:
        ann_status = "Delayed" if ann_status == "Current" else ann_status
    macro = config.macro()
    macro_status = _age(macro.get("as_of"), stamp.date(), 14, business=False)
    tickers = {}
    for stock in config.universe():
        ticker = stock["ticker"]
        close = prices.last_close(ticker, stamp.date())
        day = close[0] if close else None
        row = (listing.get("rows") or {}).get(ticker) or {}
        status = _age(day, expected, 0, latest_allowed=stamp.date())
        suspended = row.get("suspended") is True
        verified = bool(row and listing.get("trade_date") == day and not listing.get("intraday"))
        suspension_known = row.get("suspended") is not None or bool(row.get("volume"))
        periods = fundamentals.annuals(ticker, stamp.date())
        last = periods[-1] if periods else None
        tickers[ticker] = {
            "price_date": day, "status": status, "verified": verified, "suspended": suspended,
            "suspension_known": suspension_known, "period": last.period if last else None,
            "fundamentals_status": _age(last.period_end.isoformat() if last else None, stamp.date(),
                                      config.settings()["screen"]["max_fundamentals_age_days"], business=False),
        }
    active = [r for r in tickers.values() if not r["suspended"]]
    current = sum(r["status"] == "Current" and r["verified"] for r in active)
    price_ok = bool(active) and current == len(active)
    price_status = "Current" if price_ok else (
        "Stale" if any(r["status"] == "Stale" for r in active) else
        "Delayed" if any(r["status"] == "Delayed" for r in active) else "Unknown")
    due = expected + timedelta(days=1)
    while due.weekday() >= 5:
        due += timedelta(days=1)
    issues = []
    for label, status in (("Prices", price_status), ("Announcements", ann_status), ("Macro rates", macro_status)):
        if status != "Current":
            issues.append(f"{label}: {status.lower()}")
    return {
        "checked_at": stamp.isoformat(timespec="seconds"), "expected_session": expected.isoformat(),
        "next_update_due": datetime.combine(due, time(17), EAT).isoformat(),
        "status": "Current" if not issues else "Degraded", "issues": issues,
        "critical_ok": not issues, "ledger_ready": price_ok,
        "prices": {"status": price_status, "current": current, "total": len(active),
                   "source": listing.get("source"), "fetch": fetch},
        "announcements": {"status": ann_status, "last_success": ann.get("updated"),
                          "fetch": attempts.get("announcements") or {}},
        "macro": {"status": macro_status, "as_of": macro.get("as_of")},
        "tickers": tickers,
        "session_note": "Weekdays only; a delayed session can mean a public holiday or source lag.",
    }


def evidence(live: dict, ticker: str) -> list[str]:
    issues = list(live["issues"])
    row = live["tickers"].get(ticker) or {}
    if row.get("status") != "Current" or not row.get("verified"):
        issues.append("Current closing price not verified")
    if not row.get("suspension_known"):
        issues.append("Trading or suspension status unknown")
    if row.get("fundamentals_status") != "Current":
        issues.append("Annual fundamentals missing or overdue")
    return list(dict.fromkeys(issues))


def markdown(live: dict | None) -> list[str]:
    if live is None:
        return []
    p, a, m = live["prices"], live["announcements"], live["macro"]
    return ["## Data health", "", f"**{live['status']}**. Expected closing session: {live['expected_session']}. "
            f"Verified prices: {p['current']}/{p['total']}. Announcements: {a['status'].lower()} "
            f"(last successful check {a['last_success'] or 'unknown'}). Macro rates: {m['status'].lower()} "
            f"(dated {m['as_of'] or 'unknown'}).", "", live["session_note"], "",
            "Strong-confidence flags require current critical evidence. A rule-based Buy with incomplete "
            "evidence still needs verification.", ""]
