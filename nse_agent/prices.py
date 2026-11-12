"""Price-derived measures: last close, liquidity, momentum, weekly returns and beta.

Return-based measures use closes adjusted for bonus issues and splits, so a 1:1 bonus is not read as a 50% drop.
Valuation and turnover use the raw close.
"""
from __future__ import annotations

import logging
from bisect import bisect_right
from datetime import date
from functools import lru_cache
from statistics import fmean, pvariance

from . import config, storage

log = logging.getLogger(__name__)


def _d(v) -> date | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


@lru_cache(maxsize=1)
def _raw_actions() -> tuple:
    path = config.DATA / "corporate_actions.yaml"
    return tuple(((config.load_yaml(path) or {}) if path.exists() else {}).get("actions") or [])


@lru_cache(maxsize=1)
def actions() -> dict[str, list[tuple[date, float]]]:
    """Ticker -> [(ex date, factor)]; factor multiplies closes dated before the ex date."""
    out: dict[str, list[tuple[date, float]]] = {}
    for a in _raw_actions():
        ex, f = _d(a.get("ex_date")), a.get("factor")
        if ex and f:
            out.setdefault(a["ticker"], []).append((ex, float(f)))
    return {t: sorted(v) for t, v in out.items()}


@lru_cache(maxsize=1)
def action_gaps() -> tuple[str, ...]:
    """Actions inside a ticker's price history that cannot be applied because the ex date or factor is missing."""
    out = []
    for a in _raw_actions():
        if _d(a.get("ex_date")) and a.get("factor"):
            continue
        when = _d(a.get("ex_date")) or _d(a.get("book_closure")) or _d(a.get("announced"))
        first = _dates(a["ticker"])[:1]
        if when is None or (first and when.isoformat() >= first[0]):
            missing = " and ".join(k for k in ("ex_date", "factor") if not a.get(k))
            out.append(f"{a['ticker']}: {a.get('type', 'corporate action')} {when or 'undated'} has no {missing}; "
                       "prices around it are unadjusted")
    for g in out:
        log.warning(g)
    return tuple(out)


def factor(ticker: str, d: date) -> float:
    f = 1.0
    for ex, k in actions().get(ticker, []):
        if ex > d:
            f *= k
    return f


@lru_cache(maxsize=64)
def _rows(ticker: str) -> tuple:
    return tuple((r["date"], r["close"], r["volume"]) for r in storage.read_prices(ticker))


@lru_cache(maxsize=64)
def _adj(ticker: str) -> tuple:
    acts = actions().get(ticker, [])
    if not acts:
        return _rows(ticker)
    return tuple((d, c * factor(ticker, date.fromisoformat(d)) if c is not None else c, v)
                 for d, c, v in _rows(ticker))


@lru_cache(maxsize=64)
def _dates(ticker: str) -> tuple:
    return tuple(d for d, _, _ in _rows(ticker))


def clear_cache() -> None:
    for f in (_rows, _adj, _dates, _raw_actions, actions, action_gaps):
        f.cache_clear()


def rows(ticker: str, as_of: date | None = None) -> list[tuple[str, float, float | None]]:
    data = _rows(ticker)
    if as_of is None:
        return list(data)
    return list(data[:bisect_right(_dates(ticker), as_of.isoformat())])


def adj_rows(ticker: str, as_of: date | None = None) -> list[tuple[str, float, float | None]]:
    """Rows with closes adjusted for corporate actions, comparable with the latest close."""
    data = _adj(ticker)
    if as_of is None:
        return list(data)
    return list(data[:bisect_right(_dates(ticker), as_of.isoformat())])


def last_close(ticker: str, as_of: date | None = None) -> tuple[str, float] | None:
    data = _rows(ticker)
    i = len(data) if as_of is None else bisect_right(_dates(ticker), as_of.isoformat())
    return (data[i - 1][0], data[i - 1][1]) if i else None


def avg_turnover(ticker: str, as_of: date | None = None, sessions: int = 60) -> tuple[float | None, int]:
    """Average KES turnover per session over recent sessions that have recorded volume."""
    with_vol = [(c, v) for _, c, v in rows(ticker, as_of) if v is not None][-sessions:]
    if not with_vol:
        return None, 0
    return fmean(c * v for c, v in with_vol), len(with_vol)


def momentum(ticker: str, as_of: date | None = None) -> float | None:
    """Average of 12-1 and 6-1 month price returns (skip the latest month)."""
    closes = [c for _, c, _ in adj_rows(ticker, as_of)]
    if len(closes) < 253:
        return None
    skip = closes[-22]
    return fmean([skip / closes[-253] - 1, skip / closes[-127] - 1])


def volatility(ticker: str, as_of: date | None = None, weeks: int = 52) -> float | None:
    """Annualised standard deviation of the last `weeks` weekly returns (needs at least half)."""
    wr = weekly_returns(ticker, as_of)
    recent = [wr[k] for k in sorted(wr)[-weeks:]]
    if len(recent) < weeks // 2:
        return None
    return pvariance(recent) ** 0.5 * 52 ** 0.5


def weekly_closes(ticker: str, as_of: date | None = None) -> dict[str, float]:
    """Last adjusted close per ISO week, keyed by 'YYYY-Www'."""
    out: dict[str, float] = {}
    for d, c, _ in adj_rows(ticker, as_of):
        y, w, _ = date.fromisoformat(d).isocalendar()
        out[f"{y}-W{w:02d}"] = c
    return out


def weekly_returns(ticker: str, as_of: date | None = None) -> dict[str, float]:
    wc = weekly_closes(ticker, as_of)
    keys = sorted(wc)
    return {k: wc[k] / wc[p] - 1 for p, k in zip(keys, keys[1:]) if wc[p] > 0}


def equal_weight_index_returns(tickers: list[str], as_of: date | None = None) -> dict[str, float]:
    per = [weekly_returns(t, as_of) for t in tickers]
    weeks = sorted(set().union(*per)) if per else []
    out = {}
    for w in weeks:
        vals = [r[w] for r in per if w in r]
        if vals:
            out[w] = fmean(vals)
    return out


def beta(ticker: str, index: dict[str, float], as_of: date | None = None, weeks: int = 156) -> float | None:
    """Blume-adjusted weekly beta against an equal-weight universe index."""
    stock = weekly_returns(ticker, as_of)
    common = sorted(set(stock) & set(index))[-weeks:]
    if len(common) < 52:
        return None
    xs = [index[w] for w in common]
    ys = [stock[w] for w in common]
    var = pvariance(xs)
    if var == 0:
        return None
    mx, my = fmean(xs), fmean(ys)
    raw = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs) / var
    return 0.67 * raw + 0.33
