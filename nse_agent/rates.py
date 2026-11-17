"""Dated CBK Treasury-bill history for point-in-time backtests.

CBK publishes monthly 91, 182 and 364-day rates in its Central Bank Rates CSV. Weekly auction results are public as
they happen, so a month's figure is treated as known from the first day of the next month. Stored months are
append-only: a revised past value needs human review.
"""
from __future__ import annotations

import csv
import io
import logging
from copy import deepcopy
from datetime import date

import requests

from . import config, http, storage

log = logging.getLogger(__name__)
SOURCE = ("https://www.centralbank.go.ke/uploads/interest_rates/"
          "648402325_Central%20Bank%20Rates_with%20Heads.csv")
PAGE = "https://www.centralbank.go.ke/statistics/interest-rates/"
TENORS = ("91", "182", "364")
FIRST_MONTH = "2010-01"
MAX_CARRY_MONTHS = 3
MAX_MONTHLY_JUMP = 0.04
FIELDS = ["month", "tbill_91d", "tbill_182d", "tbill_364d", "source"]
MONTHS = [m[:3] for m in "January February March April May June July August September October November December".split()]


def path():
    return config.DATA / "official" / "cbk_monthly.csv"


def _rate(cell: str) -> float | None:
    cell = (cell or "").strip()
    if not cell or set(cell) <= {"-", " "}:
        return None
    value = round(float(cell) / 100, 6)
    if not 0 < value < 1:
        raise ValueError(f"CBK monthly rate {cell} is outside 0 to 100%")
    return value


def parse(text: str) -> list[dict]:
    """Rows from CBK's CSV, oldest first, from FIRST_MONTH. Year cells are blank after each year's first month."""
    rows = list(csv.reader(io.StringIO(text)))
    head = next((i for i, r in enumerate(rows) if any("91-Day" in c for c in r)), None)
    if head is None:
        raise ValueError("CBK monthly CSV has no 91-day T-bill column")
    names = [c.strip().lower() for c in rows[head]]
    cols = {}
    for tenor in TENORS:
        match = [i for i, n in enumerate(names) if n.startswith(f"{tenor}-day") and "tbill" in n.replace("-", "")]
        if len(match) != 1:
            raise ValueError(f"CBK monthly CSV {tenor}-day column is missing or ambiguous")
        cols[tenor] = match[0]
    year, out = None, []
    for r in rows[head + 1:]:
        if len(r) <= max(cols.values()) or not r[1].strip():
            continue
        if r[0].strip():
            year = int(r[0].strip())
        abbr = r[1].strip()[:3].title()
        if year is None or abbr not in MONTHS:
            raise ValueError(f"CBK monthly CSV row has no recognisable year or month: {r[:2]}")
        month = f"{year:04d}-{MONTHS.index(abbr) + 1:02d}"
        if month < FIRST_MONTH:
            continue
        rates = {t: _rate(r[cols[t]]) for t in TENORS}
        if any(v is not None for v in rates.values()):
            out.append({"month": month, **{f"tbill_{t}d": v for t, v in rates.items()}, "source": SOURCE})
    if not out:
        raise ValueError("CBK monthly CSV has no T-bill rows")
    seen = [r["month"] for r in out]
    if seen != sorted(set(seen)):
        raise ValueError("CBK monthly CSV months are duplicated or out of order")
    return out


def history() -> list[dict]:
    if not path().exists():
        return []
    with open(path(), encoding="utf-8", newline="") as fh:
        return [{"month": r["month"], **{f"tbill_{t}d": float(r[f"tbill_{t}d"]) if r[f"tbill_{t}d"] else None
                                          for t in TENORS}, "source": r["source"]} for r in csv.DictReader(fh)]


def merge(stored: list[dict], fetched: list[dict], today: date) -> list[dict]:
    """Append completed months. A changed stored month or an implausible jump is rejected for review; the current
    month is left out until it has ended."""
    old = {r["month"]: r for r in stored}
    fetched = [r for r in fetched if r["month"] < today.strftime("%Y-%m")]
    for r in fetched:
        prev = old.get(r["month"])
        if prev and any(prev[f"tbill_{t}d"] != r[f"tbill_{t}d"] for t in TENORS):
            raise ValueError(f"CBK revised the stored {r['month']} T-bill rates; human review is required")
    new = [r for r in fetched if r["month"] not in old and (not stored or r["month"] > stored[-1]["month"])]
    last = stored[-1] if stored else None
    for r in new:
        for t in TENORS:
            a, b = (last or {}).get(f"tbill_{t}d"), r[f"tbill_{t}d"]
            if last and stored and a is not None and b is not None and abs(a - b) > MAX_MONTHLY_JUMP:
                raise ValueError(f"CBK {t}-day rate moved {abs(a - b):.2%} in {r['month']}; manual verification needed")
        last = r
    return stored + new


def save(rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r[k]) for k in FIELDS})
    path().parent.mkdir(parents=True, exist_ok=True)
    tmp = path().with_suffix(".tmp")
    tmp.write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    tmp.replace(path())


def refresh(today: date | None = None) -> str:
    """Download CBK's monthly CSV and append new months. Returns updated, unchanged or failed."""
    today = today or date.today()
    stored = history()
    state = storage.read_json(storage.market_path("health.json"), {}) or {}
    attempt = {"last_attempt": today.isoformat(), "last_success": (state.get("cbk_history") or {}).get("last_success")}
    try:
        merged = merge(stored, parse(http.get_text(SOURCE)), today)
        outcome = "unchanged" if merged == stored else "updated"
        if outcome == "updated":
            save(merged)
        attempt.update(successful=True, last_success=today.isoformat())
    except (ValueError, requests.RequestException) as exc:
        log.warning("CBK monthly T-bill history failed: %s", exc)
        outcome = "failed"
        attempt.update(successful=False, error=str(exc))
    state["cbk_history"] = attempt
    storage.write_json(storage.market_path("health.json"), state)
    return outcome


def at(d: date, tenor: str = "364") -> dict:
    """The latest monthly rate published before d: the previous month's figure, carried forward at most 3 months."""
    key = f"tbill_{tenor}d"
    rows = [r for r in history() if r["month"] < d.strftime("%Y-%m") and r[key] is not None]
    if not rows:
        raise ValueError(f"No CBK {tenor}-day T-bill rate was published before {d}")
    r = rows[-1]
    y, m = map(int, r["month"].split("-"))
    gap = (d.year - y) * 12 + d.month - m - 1
    if gap > MAX_CARRY_MONTHS:
        raise ValueError(f"The latest CBK {tenor}-day rate before {d} is from {r['month']}, too old to use")
    return {"value": r[key], "month": r["month"], "carried_months": gap, "source": r["source"]}


def macro_at(d: date) -> dict:
    """Today's macro inputs with the T-bill rates replaced by those published before d.

    Bond yields, risk premiums and taxes stay at today's reviewed values, so valuations are unchanged and only the
    Buy hurdle and cash return move with history.
    """
    m = deepcopy(config.macro())
    for tenor in TENORS:
        r = at(d, tenor)
        m["risk_free"][f"tbill_{tenor}d"] = {"value": r["value"], "as_of": r["month"], "source": r["source"],
                                            "method": "dated monthly history", "carried_months": r["carried_months"]}
    return m


def cash_return(macro: dict) -> float:
    """One month on 91-day bills after withholding tax, the closest proxy for cash a small investor can hold."""
    return macro["risk_free"]["tbill_91d"]["value"] * (1 - macro["taxes_and_costs"]["tbill_interest_wht"]) / 12
