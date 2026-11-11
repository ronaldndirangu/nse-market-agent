"""Price-derived measures: last close, liquidity, momentum, weekly returns and beta."""
from __future__ import annotations

from bisect import bisect_right
from datetime import date
from functools import lru_cache
from statistics import fmean, pvariance

from . import storage


@lru_cache(maxsize=64)
def _rows(ticker: str) -> tuple:
    return tuple((r["date"], r["close"], r["volume"]) for r in storage.read_prices(ticker))


def clear_cache() -> None:
    _rows.cache_clear()


def rows(ticker: str, as_of: date | None = None) -> list[tuple[str, float, float | None]]:
    data = _rows(ticker)
    if as_of is None:
        return list(data)
    i = bisect_right([d for d, _, _ in data], as_of.isoformat())
    return list(data[:i])


def last_close(ticker: str, as_of: date | None = None) -> tuple[str, float] | None:
    r = rows(ticker, as_of)
    return (r[-1][0], r[-1][1]) if r else None


def avg_turnover(ticker: str, as_of: date | None = None, sessions: int = 60) -> tuple[float | None, int]:
    """Average KES turnover per session over recent sessions that have recorded volume."""
    with_vol = [(c, v) for _, c, v in rows(ticker, as_of) if v is not None][-sessions:]
    if not with_vol:
        return None, 0
    return fmean(c * v for c, v in with_vol), len(with_vol)


def momentum(ticker: str, as_of: date | None = None) -> float | None:
    """Average of 12-1 and 6-1 month price returns (skip the latest month)."""
    closes = [c for _, c, _ in rows(ticker, as_of)]
    if len(closes) < 253:
        return None
    skip = closes[-22]
    return fmean([skip / closes[-253] - 1, skip / closes[-127] - 1])


def weekly_closes(ticker: str, as_of: date | None = None) -> dict[str, float]:
    """Last close per ISO week, keyed by 'YYYY-Www'."""
    out: dict[str, float] = {}
    for d, c, _ in rows(ticker, as_of):
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
