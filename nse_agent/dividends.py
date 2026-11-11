"""Sourced dividend history and corporate actions: trailing yield, adjusted prices and total return."""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from . import config, prices


def _d(v) -> date | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _yaml_or_empty(name: str) -> dict:
    path = config.DATA / name
    return (config.load_yaml(path) or {}) if path.exists() else {}


@lru_cache(maxsize=1)
def _dividends() -> dict[str, list[tuple[date, float]]]:
    """Ticker -> [(ex date, KES per share)]; book closure approximates the ex date, payment date is the fallback."""
    raw = _yaml_or_empty("dividends.yaml").get("dividends") or {}
    out: dict[str, list[tuple[date, float]]] = {}
    for t, recs in raw.items():
        rows = []
        for r in recs or []:
            ex = _d(r.get("book_closure")) or _d(r.get("payment"))
            if ex and r.get("amount"):
                rows.append((ex, float(r["amount"])))
        out[t] = sorted(rows)
    return out


@lru_cache(maxsize=1)
def _actions() -> dict[str, list[tuple[date, float]]]:
    """Ticker -> [(ex date, factor)]; factor multiplies prices before the ex date."""
    raw = _yaml_or_empty("corporate_actions.yaml").get("actions") or []
    out: dict[str, list[tuple[date, float]]] = {}
    for a in raw:
        ex, f = _d(a.get("ex_date")), a.get("factor")
        if ex and f:
            out.setdefault(a["ticker"], []).append((ex, float(f)))
    return {t: sorted(v) for t, v in out.items()}


def clear_cache() -> None:
    _dividends.cache_clear()
    _actions.cache_clear()


def history(ticker: str) -> list[tuple[date, float]]:
    return _dividends().get(ticker, [])


def factor(ticker: str, d: date) -> float:
    f = 1.0
    for ex, k in _actions().get(ticker, []):
        if ex > d:
            f *= k
    return f


def trailing_yield(ticker: str, as_of: date, price: float | None, dps: float | None = None) -> float | None:
    """Gross dividends with ex dates in the past 365 days over price.

    Uses the sourced history once it covers as_of; otherwise falls back to the latest reported DPS.
    """
    if not price:
        return None
    hist = history(ticker)
    if hist and hist[0][0] <= as_of:
        start = as_of - timedelta(days=365)
        paid = sum(amt * factor(ticker, ex) / factor(ticker, as_of) for ex, amt in hist if start < ex <= as_of)
        return paid / price
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
