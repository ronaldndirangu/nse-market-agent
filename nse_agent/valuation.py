"""Deterministic valuation models. Inputs come only from sourced fundamentals and recorded prices."""
from __future__ import annotations

import math
from statistics import median

from . import config
from .fundamentals import Period, avg, roe

MODEL_NAMES = {
    "justified_pb": "Bank book-value model",
    "gordon_ddm": "Dividend model",
    "earnings_power": "Earnings power",
    "sector_pe": "Peer earnings multiple",
    "sector_pb": "Peer book-value multiple",
}


def cost_of_equity(beta: float | None, macro: dict | None = None) -> float:
    m = macro if macro is not None else config.macro()
    er = m["equity_risk"]
    rf = m["risk_free"]["bond_10y"]["value"] - er["default_spread"]
    b = beta if beta is not None else config.settings()["valuation"]["default_beta"]
    return rf + b * er["mature_market_erp"] + er["country_risk_premium"]


def sustainable_growth(periods: list[Period], ke: float) -> tuple[float, float | None]:
    """g = ROE * retention, clipped to [floor, cap] and kept at least min_ke_minus_g below ke."""
    s = config.settings()["valuation"]
    last = periods[-1]
    r = avg([roe(periods, i) for i in range(max(0, len(periods) - 3), len(periods))])
    eps, dps = last.get("eps"), last.get("dps")
    if r is None or not eps or eps <= 0:
        return s["growth_floor"], r
    payout = min(max((dps or 0.0) / eps, 0.0), 1.0)
    g = min(max(r * (1 - payout), s["growth_floor"]), s["growth_cap"], ke - s["min_ke_minus_g"])
    return g, r


def models(periods: list[Period], bank: bool, ke: float, g: float, avg_roe: float | None,
           sector_pe: float | None, sector_pb: float | None) -> dict[str, float]:
    """Return {model: fair value per share}. Models without valid inputs are omitted."""
    last = periods[-1]
    out: dict[str, float] = {}
    bvps, eps, dps = last.get("bvps"), last.get("eps"), last.get("dps")
    if bank and bvps and avg_roe is not None and avg_roe > g:
        out["justified_pb"] = bvps * (avg_roe - g) / (ke - g)
    if dps and dps > 0:
        out["gordon_ddm"] = dps * (1 + g) / (ke - g)
    avg_eps = avg([p.get("eps") for p in periods[-3:]])
    if avg_eps and avg_eps > 0:
        out["earnings_power"] = avg_eps / ke
    if sector_pe and eps and eps > 0:
        out["sector_pe"] = sector_pe * eps
    if sector_pb and bvps and bvps > 0:
        out["sector_pb"] = sector_pb * bvps
    return {k: v for k, v in out.items() if v > 0 and math.isfinite(v)}


def graham_number(periods: list[Period]) -> float | None:
    last = periods[-1]
    eps, bvps = last.get("eps"), last.get("bvps")
    if eps and bvps and eps > 0 and bvps > 0:
        return math.sqrt(22.5 * eps * bvps)
    return None


def fair_value(values: dict[str, float]) -> dict | None:
    if not values:
        return None
    v = list(values.values())
    return {"low": min(v), "base": median(v), "high": max(v)}


def sector_multiples(rows: dict[str, dict], min_peers: int) -> dict[str, dict]:
    """Median peer P/E and P/B per ticker, excluding the ticker itself."""
    out: dict[str, dict] = {}
    for t, r in rows.items():
        peers = [p for pt, p in rows.items() if pt != t and p["sector"] == r["sector"]]
        pes = [p["pe"] for p in peers if p.get("pe") and p["pe"] > 0]
        pbs = [p["pb"] for p in peers if p.get("pb") and p["pb"] > 0]
        out[t] = {
            "pe": median(pes) if len(pes) >= min_peers else None,
            "pb": median(pbs) if len(pbs) >= min_peers else None,
        }
    return out


def agreeing(values: dict[str, float], price: float, threshold: float) -> list[str]:
    return [k for k, v in values.items() if v / price - 1 >= threshold]


def required_agreement(n_models: int) -> int:
    return max(2, math.ceil(n_models / 2))


def cushion_price(values: dict[str, float], threshold: float) -> float | None:
    """Conservative cent price for the agreement rule, holding every model estimate fixed."""
    need = required_agreement(len(values))
    if len(values) < need:
        return None
    price = math.floor(sorted(values.values(), reverse=True)[need - 1] / (1 + threshold) * 100) / 100
    if price <= 0:
        return None
    if len(agreeing(values, price, threshold)) < need:
        price = round(price - 0.01, 2)
    return price if price > 0 else None
