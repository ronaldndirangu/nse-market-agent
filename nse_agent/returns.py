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


def rank(rows: dict[str, dict]) -> list[str]:
    """Composite = weighted z-scores of margin of safety, quality and momentum. Missing z counts as 0."""
    w = config.settings()["ranking"]["weights"]
    zm = zscores({t: r.get("mos") for t, r in rows.items()})
    zq = zscores({t: r["quality"].get("score") for t, r in rows.items()})
    zmo = zscores({t: r.get("momentum") for t, r in rows.items()})
    for t, r in rows.items():
        r["composite"] = w["margin_of_safety"] * zm[t] + w["quality"] * zq[t] + w["momentum"] * zmo[t]
    return sorted(rows, key=lambda t: rows[t]["composite"], reverse=True)
