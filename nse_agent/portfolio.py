"""Rule-based review of the holdings in portfolio.yaml. Output is Sell / Trim / Add / Hold with reasons."""
from __future__ import annotations

from datetime import date

from . import config, prices
from .fmt import kes, pct, table


def path():
    return config.ROOT / "portfolio.yaml"


def load() -> list[dict]:
    p = path()
    if not p.exists():
        return []
    raw = config.load_yaml(p) or {}
    return [h for h in raw.get("holdings") or [] if h.get("ticker") and h.get("shares")]


def review(result: dict, holdings: list[dict] | None = None) -> list[dict]:
    holdings = load() if holdings is None else holdings
    if not holdings:
        return []
    s = config.settings()["buy"]
    as_of = date.fromisoformat(result["as_of"])
    uni = config.universe_map()
    rows = result["rows"]
    values = {}
    for h in holdings:
        t = h["ticker"].upper()
        lc = prices.last_close(t, as_of)
        values[t] = (lc[1] if lc else None, float(h["shares"]))
    total = sum(p * n for p, n in values.values() if p is not None)
    sector_w: dict[str, float] = {}
    for t, (p, n) in values.items():
        if p is not None and total:
            sec = uni.get(t, {}).get("sector", "Other")
            sector_w[sec] = sector_w.get(sec, 0.0) + p * n / total

    out = []
    for h in holdings:
        t = h["ticker"].upper()
        price, shares = values[t]
        cost = h.get("cost")
        r = rows.get(t)
        weight = price * shares / total if price is not None and total else None
        reasons, action = [], "Hold"
        if r is None:
            reasons.append("not covered by the valuation (no sourced fundamentals or prices)")
        else:
            fv, q = r["fair_value"], r["quality"]
            if q["gate"] == "fail":
                action = "Sell"
                reasons += q["fails"]
            if fv and price is not None and price > fv["high"]:
                action = "Sell"
                reasons.append(f"price {kes(price)} is above the high fair value {kes(fv['high'])}")
            if action != "Sell":
                if weight is not None and weight > s["max_position_weight"]:
                    action = "Trim"
                    reasons.append(f"position is {pct(weight)} of the portfolio (limit {pct(s['max_position_weight'], 0)})")
                if fv and price is not None and price > fv["base"]:
                    action = "Trim"
                    reasons.append(f"price is above the base fair value {kes(fv['base'])}")
            if action == "Hold" and r["buy"]:
                sec = uni.get(t, {}).get("sector", "Other")
                if sector_w.get(sec, 0.0) < s["max_sector_weight"]:
                    action = "Add"
                    reasons.append("still a buy candidate and within position and sector limits")
            if action == "Hold" and not reasons:
                reasons.append("no rule triggered")
        out.append({
            "ticker": t, "shares": shares, "price": price, "cost": cost, "weight": weight, "action": action,
            "gain": price / float(cost) - 1 if cost and price is not None else None, "reasons": reasons,
        })
    return out


def render(items: list[dict]) -> str:
    if not items:
        return ""
    rows = [[i["ticker"], f"{i['shares']:,.0f}", kes(i["price"]), kes(i["cost"]) if i["cost"] else "n/a",
             pct(i["gain"]), pct(i["weight"]), f"**{i['action']}**", "; ".join(i["reasons"])] for i in items]
    return table(["Ticker", "Shares", "Price", "Cost", "Gain", "Weight", "Action", "Why"], rows)


def run_review() -> str:
    from .engine import analyze
    items = review(analyze())
    if not items:
        return f"No holdings found. Copy portfolio.example.yaml to {path().name} and list your positions."
    return render(items)
