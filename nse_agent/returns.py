"""Projected returns net of costs and withholding tax, plus ranking."""
from __future__ import annotations

from statistics import fmean, pstdev

from . import config


def net_tbill() -> float:
    m = config.macro()
    return m["risk_free"]["tbill_364d"]["value"] * (1 - m["taxes_and_costs"]["tbill_interest_wht"])


def project(price: float, dps: float | None, fv: dict, g: float, years: int | None = None) -> dict:
    """Annual total return = net dividend yield + (1+g)(V/P)^(1/N) - 1 - round-trip costs / N."""
    m, s = config.macro(), config.settings()
    n = years or s["valuation"]["horizon_years"]
    shift = s["scenarios"]["growth_shift"]
    costs = 2 * m["taxes_and_costs"]["trade_cost_per_side"] / n
    div = (dps or 0.0) / price * (1 - m["taxes_and_costs"]["dividend_wht"])
    out = {"years": n, "dividend_yield_net": div, "cost_drag": costs}
    for name, v, gg in (("bear", fv["low"], g - shift), ("base", fv["base"], g), ("bull", fv["high"], g + shift)):
        price_ret = (1 + gg) * (v / price) ** (1 / n) - 1
        out[name] = div + price_ret - costs
    return out


def zscores(values: dict[str, float | None]) -> dict[str, float]:
    vals = [v for v in values.values() if v is not None]
    if len(vals) < 2:
        return {k: 0.0 for k in values}
    mu, sd = fmean(vals), pstdev(vals)
    return {k: ((v - mu) / sd if v is not None and sd > 0 else 0.0) for k, v in values.items()}


def _neg(v: float | None) -> float | None:
    return -v if v is not None else None


SIGNALS = {
    "margin_of_safety": lambda r: r.get("mos"),
    "quality": lambda r: (r.get("quality") or {}).get("score"),
    "momentum": lambda r: r.get("momentum"),
    "dividend_yield": lambda r: r.get("dividend_yield"),
    "low_volatility": lambda r: _neg(r.get("volatility")),
}


def rank(rows: dict[str, dict], weights: dict[str, float] | None = None) -> list[str]:
    """Composite = weighted z-scores of the signals (margin of safety, quality, momentum by default).

    Missing values count as z = 0. Every row gets signals[name] = {value, z, weight, contribution} for all
    SIGNALS, with weight 0 for signals outside the weights, so the ledger can study unweighted signals too.
    """
    w = weights or config.settings()["ranking"]["weights"]
    z = {name: zscores({t: f(r) for t, r in rows.items()}) for name, f in SIGNALS.items()}
    for t, r in rows.items():
        r["signals"] = {}
        for name, f in SIGNALS.items():
            wt = float(w.get(name, 0.0))
            r["signals"][name] = {"value": f(r), "z": z[name][t], "weight": wt, "contribution": wt * z[name][t]}
        r["composite"] = sum(s["contribution"] for s in r["signals"].values())
    return sorted(rows, key=lambda t: rows[t]["composite"], reverse=True)


def weights_text(weights: dict[str, float] | None = None) -> str:
    w = weights or config.settings()["ranking"]["weights"]
    return " + ".join(f"{wt:g} z({name.replace('_', ' ')})" for name, wt in w.items() if wt)
