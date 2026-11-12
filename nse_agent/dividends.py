"""Sourced dividend history and corporate actions: trailing yield, adjusted prices and total return."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from functools import lru_cache

from . import config, prices

PER_SHARE = ("eps", "bvps", "dps")


def _d(v) -> date | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _yaml_or_empty(name: str) -> dict:
    path = config.DATA / name
    return (config.load_yaml(path) or {}) if path.exists() else {}


@lru_cache(maxsize=1)
def _records() -> dict[str, list[tuple[date | None, float, str, str]]]:
    """Ticker -> [(approximate ex date, KES per share, type, fiscal period)].

    The ex date is approximate: book closure, else payment, else announcement date.
    """
    raw = _yaml_or_empty("dividends.yaml").get("dividends") or {}
    out: dict[str, list] = {}
    for t, recs in raw.items():
        rows = []
        for r in recs or []:
            if r.get("amount"):
                ex = _d(r.get("book_closure")) or _d(r.get("payment")) or _d(r.get("announced"))
                rows.append((ex, float(r["amount"]), str(r.get("type", "")), str(r.get("fiscal_period", ""))))
        out[t] = sorted(rows, key=lambda x: (x[0] or date.min, x[1]))
    return out


@lru_cache(maxsize=1)
def _dividends() -> dict[str, list[tuple[date, float]]]:
    return {t: [(ex, amt) for ex, amt, _, _ in recs if ex] for t, recs in _records().items()}


_actions = prices.actions
factor = prices.factor


def clear_cache() -> None:
    _records.cache_clear()
    _dividends.cache_clear()
    prices.clear_cache()


def history(ticker: str) -> list[tuple[date, float]]:
    """Every dated dividend, specials included, for total return."""
    return _dividends().get(ticker, [])


def regular_dps(ticker: str, fiscal_period: str, dps: float | None) -> float | None:
    """Reported DPS less special dividends declared for the same fiscal period.

    Reported DPS includes specials unless the sourced regular dividends alone already add up to it.
    """
    if dps is None:
        return None
    recs = [r for r in _records().get(ticker, []) if r[3] == fiscal_period]
    special = sum(amt for _, amt, kind, _ in recs if kind == "special")
    if not special:
        return dps
    regular = sum(amt for _, amt, kind, _ in recs if kind != "special")
    if regular and abs(regular - dps) <= 0.005 + 0.01 * dps:
        return dps
    return max(dps - special, 0.0)


def comparable(ticker: str, periods: list, as_of: date) -> list:
    """Annual periods with EPS, BVPS and regular DPS on the share basis of `as_of`.

    Bonus issues and splits after a period end shrink its per-share figures, so they compare with today's price.
    Shares outstanding move the other way, so a bonus issue does not read as dilution.
    """
    now = factor(ticker, as_of)
    out = []
    for p in periods:
        k = factor(ticker, p.period_end) / now
        vals = dict(p.values)
        for key in PER_SHARE:
            v = regular_dps(ticker, p.period, p.get(key)) if key == "dps" else p.get(key)
            if v is not None:
                vals[key] = v * k
        if k != 1 and vals.get("shares_outstanding"):
            vals["shares_outstanding"] = float(vals["shares_outstanding"]) / k
        out.append(replace(p, values=vals))
    return out


def trailing_yield(ticker: str, as_of: date, price: float | None, dps: float | None = None) -> float | None:
    """Regular dividends with ex dates in the past 365 days over price; specials are one-offs and excluded.

    Uses sourced dividends in the window; when the window has none (history not started or a sourcing gap),
    falls back to the latest reported regular DPS, which is 0 for a company that skipped its dividend.
    """
    if not price:
        return None
    start = as_of - timedelta(days=365)
    paid = [amt * factor(ticker, ex) / factor(ticker, as_of)
            for ex, amt, kind, _ in _records().get(ticker, []) if ex and start < ex <= as_of and kind != "special"]
    if paid:
        return sum(paid) / price
    return dps / price if dps is not None else None


def adj_close(ticker: str, as_of: date) -> tuple[date, float] | None:
    lc = prices.last_close(ticker, as_of)
    if not lc:
        return None
    d = date.fromisoformat(lc[0])
    return d, lc[1] * factor(ticker, d)


def total_return(ticker: str, start: date, end: date, net: bool = True) -> float | None:
    """Split-adjusted price change plus dividends (net of withholding tax by default) without reinvestment."""
    a, b = adj_close(ticker, start), adj_close(ticker, end)
    if not a or not b or a[1] <= 0:
        return None
    wht = config.macro()["taxes_and_costs"]["dividend_wht"] if net else 0.0
    divs = sum(amt * factor(ticker, ex) for ex, amt in history(ticker) if a[0] < ex <= b[0])
    return (b[1] + divs * (1 - wht)) / a[1] - 1
