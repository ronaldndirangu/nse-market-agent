"""Portfolio accounting and frozen portfolio rules shared by the backtest and the live shadow log.

Every strategy and benchmark goes through the same Book: weights drift with returns between rebalances, trading
costs are charged on the weight actually traded (initial purchase included), and dividends received stay in the
position until the next rebalance.
"""
from __future__ import annotations

import random
from datetime import date
from statistics import fmean

from . import config, fundamentals as fnd, prices
from .simulate import percentile

EXPERIMENTS = {
    "tilt": "Covered basket with Buy stocks at double weight",
    "skip_expensive": "Covered basket without stocks priced above their high fair value",
    "buy_hold": "Buy rule that keeps a stock until it reaches its base fair value",
    "tilt_quarterly": "Buy-stock tilt, rebalanced every three months",
}


def _share_issues(ticker: str) -> list[tuple[date, float]]:
    out = []
    for a in prices._raw_actions():
        if a.get("ticker") == ticker and a.get("shares_issued_m") and a.get("ex_date"):
            out.append((date.fromisoformat(str(a["ex_date"])[:10]), float(a["shares_issued_m"])))
    return out


def shares_at(ticker: str, d: date) -> tuple[float, bool] | None:
    """Shares outstanding (millions) on d and whether the count was backfilled from a later filing.

    Uses the latest filing published by d, rebased for later bonus issues and splits and adding recorded share
    issues such as mergers. With no filing yet, the earliest later filing is rebased back to d."""
    periods = [p for p in fnd.load().get(ticker, {}).get("periods", []) if p.values.get("shares_outstanding")]
    if not periods:
        return None
    known = [p for p in periods if p.published <= d]
    backfilled = not known
    p = max(known, key=lambda p: p.period_end) if known else min(periods, key=lambda p: p.period_end)
    shares = float(p.values["shares_outstanding"]) * prices.factor(ticker, d) / prices.factor(ticker, p.period_end)
    for ex, issued in _share_issues(ticker):
        rebased = issued * prices.factor(ticker, d) / prices.factor(ticker, ex)
        if p.period_end < ex <= d:
            shares += rebased
        elif d < ex <= p.period_end:
            shares -= rebased
    return shares, backfilled


def cap_weights(tickers: list[str], d: date) -> tuple[dict[str, float], list[str]]:
    """Full market-cap weights (not free float) on d, and the tickers whose share count was backfilled."""
    caps, backfilled = {}, []
    for t in tickers:
        lc, sh = prices.last_close(t, d), shares_at(t, d)
        if lc and sh and lc[1] > 0:
            caps[t] = lc[1] * sh[0]
            if sh[1]:
                backfilled.append(t)
    total = sum(caps.values())
    return ({t: c / total for t, c in caps.items()} if total else {}), backfilled


def equal(tickers: list[str]) -> dict[str, float]:
    return {t: 1 / len(tickers) for t in tickers} if tickers else {}


def turnover(held: dict[str, float], target: dict[str, float]) -> float:
    """Weight bought plus weight sold, cash excluded."""
    return sum(abs(target.get(t, 0.0) - held.get(t, 0.0)) for t in set(held) | set(target))


class Book:
    """Monthly gross returns and turnover; net returns at any per-side cost come from the same path."""

    def __init__(self) -> None:
        self.held: dict[str, float] = {}
        self.gross: list[float] = []
        self.turnover: list[float] = []

    def step(self, target: dict[str, float], rets: dict[str, float], cash: float) -> float:
        target = {t: w for t, w in target.items() if w > 1e-12}
        self.turnover.append(turnover(self.held, target))
        g = sum(w * rets[t] for t, w in target.items()) + (1 - sum(target.values())) * cash
        self.held = {t: w * (1 + rets[t]) / (1 + g) for t, w in target.items()}
        self.gross.append(g)
        return g

    def drifted(self, ok: set[str]) -> dict[str, float]:
        """Current weights, selling anything without a usable return this month."""
        return {t: w for t, w in self.held.items() if t in ok}

    def net(self, cost: float) -> list[float]:
        return [(1 - cost * t) * (1 + g) - 1 for g, t in zip(self.gross, self.turnover)]


# Frozen rules ------------------------------------------------------------------------------------------------------

def buy_rule(res: dict, ok: set[str], top: int) -> dict[str, float]:
    return equal([t for t in res["buys"] if t in ok][:top])


def tilt(core: dict[str, float], buys: list[str], mult: float) -> dict[str, float]:
    w = {t: v * (mult if t in buys else 1.0) for t, v in core.items()}
    total = sum(w.values())
    return {t: v / total for t, v in w.items()} if total else {}


def expensive(row: dict) -> bool:
    fv = row.get("fair_value")
    return bool(fv) and not row.get("dispersed") and row["price"] > fv["high"]


def skip_expensive(core: dict[str, float], rows: dict) -> tuple[dict[str, float], list[str]]:
    dropped = [t for t in core if t in rows and expensive(rows[t])]
    kept = {t: v for t, v in core.items() if t not in dropped}
    total = sum(kept.values())
    return ({t: v / total for t, v in kept.items()} if total else {}), dropped


def hold(prev: list[str], res: dict, ok: set[str], top: int) -> list[str]:
    """Keep a holding while its valuation is reliable, its price is below base fair value and health holds."""
    rows = res["rows"]
    kept = []
    for t in prev:
        r = rows.get(t)
        fv = (r or {}).get("fair_value")
        if t in ok and r and fv and not r.get("dispersed") and r["price"] < fv["base"] \
                and r["quality"]["gate"] != "fail":
            kept.append(t)
    for t in res["buys"]:
        if len(kept) >= top:
            break
        if t in ok and t not in kept:
            kept.append(t)
    return kept


def band_breached(held: dict[str, float], target: dict[str, float], band: float) -> bool:
    return any(abs(held.get(t, 0.0) - w) > band * w for t, w in target.items()) or any(
        t not in target for t in held)


def experiments(res: dict, d: date, core: dict[str, float], ok: set[str], prev_hold: list[str],
                held_quarterly: dict[str, float] | None) -> tuple[dict, dict, list[str]]:
    """Targets and whether each rule's signal changed the book this month, plus the new buy_hold holdings."""
    x = config.settings()["experiments"]
    buys = [t for t in res["buys"] if t in core]
    tilted = tilt(core, buys, x["tilt_multiplier"])
    skipped, dropped = skip_expensive(core, res["rows"])
    held = hold(prev_hold, res, ok, x["top"])
    if held_quarterly is None or (d.month in x["rebalance_months"]
                                  and band_breached(held_quarterly, tilted, x["drift_band"])):
        quarterly = tilted
    else:
        quarterly = held_quarterly
    targets = {"tilt": tilted, "skip_expensive": skipped, "buy_hold": equal(held), "tilt_quarterly": quarterly}
    signals = {"tilt": bool(buys), "skip_expensive": bool(dropped), "buy_hold": bool(held),
               "tilt_quarterly": bool(buys) and quarterly is tilted}
    return targets, signals, held


# Evidence gate -----------------------------------------------------------------------------------------------------

def block_ci(xs: list[float], block: int, resamples: int, level: float, seed: int) -> tuple[float, float] | None:
    """Circular block bootstrap interval for the mean, keeping runs of neighbouring months together."""
    n = len(xs)
    if n < 2 * block:
        return None
    rng, means = random.Random(seed), []
    for _ in range(resamples):
        sample: list[float] = []
        while len(sample) < n:
            s = rng.randrange(n)
            sample.extend(xs[(s + i) % n] for i in range(block))
        means.append(fmean(sample[:n]))
    tail = (1 - level) / 2
    return percentile(means, tail), percentile(means, 1 - tail)


def gate(excess: list[float], stress_excess: list[float], signal_months: int, live: dict | None) -> dict:
    """Four conditions before a rule can be put to human review. Excess figures are annualised monthly means."""
    g = config.settings()["experiments"]["gate"]
    seed = config.settings()["simulation"]["seed"]
    ci = block_ci(excess, g["block_months"], g["resamples"], g["confidence"], seed)
    ann = fmean(excess) * 12 if excess else None
    stress = fmean(stress_excess) * 12 if stress_excess else None
    live = live or {}
    checks = {
        "interval": bool(ci) and ci[0] > 0,
        "signal_months": signal_months >= g["min_signal_months"],
        "cost_stress": stress is not None and stress > 0,
        "live": live.get("months", 0) >= g["min_live_months"] and (live.get("excess") or 0) > 0,
    }
    met = sum(checks.values())
    return {"excess": ann, "ci": [ci[0] * 12, ci[1] * 12] if ci else None, "stress_excess": stress,
            "signal_months": signal_months, "live_months": live.get("months", 0),
            "live_excess": live.get("excess"), "checks": checks, "met": met,
            "status": "Ready for human review" if met == len(checks) else f"Not adopted ({met} of {len(checks)} checks met)"}
