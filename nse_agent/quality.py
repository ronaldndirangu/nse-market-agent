"""Codified quality checks: Piotroski F-score, Altman Z'', bank NPL trend and warning announcements."""
from __future__ import annotations

from datetime import date, timedelta

from . import config
from .announcements import name_pattern
from .fundamentals import Period


def _ratio(a: float | None, b: float | None) -> float | None:
    return a / b if a is not None and b else None


def piotroski(periods: list[Period], bank: bool) -> dict | None:
    """Share of available F-score signals that pass, or None without both ROA signals and at least 4 in total.

    Banks swap gross margin and current ratio for cost-to-income and core capital trends, and skip leverage:
    bank liabilities are mostly deposits, so deposit growth would read as rising leverage.
    """
    if len(periods) < 2:
        return None
    cur, prev = periods[-1], periods[-2]
    g = lambda p, k: p.get(k)  # noqa: E731
    roa_c = _ratio(g(cur, "net_income"), g(cur, "total_assets"))
    roa_p = _ratio(g(prev, "net_income"), g(prev, "total_assets"))
    cfo = g(cur, "operating_cash_flow")
    signals: dict[str, bool] = {}
    if roa_c is not None:
        signals["roa_positive"] = roa_c > 0
    if cfo is not None:
        signals["cfo_positive"] = cfo > 0
    if roa_c is not None and roa_p is not None:
        signals["roa_improving"] = roa_c > roa_p
    if cfo is not None and g(cur, "net_income") is not None:
        signals["cfo_exceeds_income"] = cfo > g(cur, "net_income")
    if not bank:
        lev_c = _ratio(g(cur, "long_term_debt"), g(cur, "total_assets"))
        lev_p = _ratio(g(prev, "long_term_debt"), g(prev, "total_assets"))
        if lev_c is not None and lev_p is not None:
            signals["leverage_falling"] = lev_c <= lev_p
    if bank:
        ci_c, ci_p = g(cur, "cost_to_income"), g(prev, "cost_to_income")
        if ci_c is not None and ci_p is not None:
            signals["cost_to_income_improving"] = ci_c < ci_p
        cc_c, cc_p = g(cur, "core_capital_ratio"), g(prev, "core_capital_ratio")
        if cc_c is not None and cc_p is not None:
            signals["capital_ratio_improving"] = cc_c >= cc_p
    else:
        cr_c = _ratio(g(cur, "current_assets"), g(cur, "current_liabilities"))
        cr_p = _ratio(g(prev, "current_assets"), g(prev, "current_liabilities"))
        if cr_c is not None and cr_p is not None:
            signals["liquidity_improving"] = cr_c > cr_p
        gm_c = _ratio(g(cur, "gross_profit"), g(cur, "revenue"))
        gm_p = _ratio(g(prev, "gross_profit"), g(prev, "revenue"))
        if gm_c is not None and gm_p is not None:
            signals["gross_margin_improving"] = gm_c > gm_p
    sh_c, sh_p = g(cur, "shares_outstanding"), g(prev, "shares_outstanding")
    if sh_c is not None and sh_p is not None:
        signals["no_dilution"] = sh_c <= sh_p * 1.001
    at_c = _ratio(g(cur, "revenue"), g(cur, "total_assets"))
    at_p = _ratio(g(prev, "revenue"), g(prev, "total_assets"))
    if at_c is not None and at_p is not None:
        signals["asset_turnover_improving"] = at_c > at_p
    if len(signals) < 4 or "roa_positive" not in signals or "roa_improving" not in signals:
        return None
    passed = sum(signals.values())
    return {"score": passed / len(signals), "passed": passed, "available": len(signals), "signals": signals}


def altman_z2(periods: list[Period]) -> float | None:
    """Altman Z'' for non-manufacturing and emerging-market firms."""
    p = periods[-1]
    ta = p.get("total_assets")
    need = [p.get(k) for k in ("current_assets", "current_liabilities", "retained_earnings", "ebit",
                               "total_equity", "total_liabilities")]
    if not ta or any(v is None for v in need) or not need[5]:
        return None
    ca, cl, re_, ebit, eq, tl = need
    return 6.56 * (ca - cl) / ta + 3.26 * re_ / ta + 6.72 * ebit / ta + 1.05 * eq / tl


def npl_trend(periods: list[Period], interim: Period | None = None) -> dict | None:
    dated = sorted(((p.period_end, p.period, p.get("npl_ratio")) for p in periods
                    if p.get("npl_ratio") is not None), key=lambda x: x[0])
    if interim is not None and interim.get("npl_ratio") is not None and (
            not dated or interim.period_end > dated[-1][0]):
        dated.append((interim.period_end, interim.period, interim.get("npl_ratio")))
    series = [(label, v) for _, label, v in dated]
    if not series:
        return None
    q = config.settings()["quality"]
    latest = series[-1][1]
    change = latest - series[-2][1] if len(series) >= 2 else None
    status = "ok"
    if latest > q["npl_max"] or (change is not None and change > q["npl_rise_fail"]):
        status = "fail"
    elif change is not None and change > 0:
        status = "rising"
    return {"latest": latest, "change": change, "status": status, "series": series}


def warnings_for(ticker: str, aliases: list[str], announcements: list[dict], as_of: date) -> list[dict]:
    q = config.settings()["quality"]
    keywords = [k.lower() for k in config.settings()["warning_keywords"]]
    since = as_of - timedelta(days=q["warning_lookback_days"])
    names = name_pattern([ticker, *aliases])
    hits = []
    for a in announcements:
        d = date.fromisoformat(a["date"]) if a.get("date") else None
        if d is None or d < since or d > as_of:
            continue
        title = a["title"]
        if (a.get("ticker") == ticker or names.search(title)) and any(k in title.lower() for k in keywords):
            hits.append(a)
    return hits


def assess(periods: list[Period], bank: bool, interim: Period | None, warnings: list[dict]) -> dict:
    """Combine checks into a gate (pass/fail/unknown) and a 0-1 quality score."""
    q = config.settings()["quality"]
    f = piotroski(periods, bank)
    z = None if bank else altman_z2(periods)
    npl = npl_trend(periods, interim) if bank else None
    parts: list[float] = []
    fails: list[str] = []
    flags: list[str] = []
    if f is not None:
        parts.append(f["score"])
        if f["score"] < q["piotroski_min"]:
            fails.append(f"Piotroski {f['passed']}/{f['available']} below gate")
    if z is not None:
        lo, hi = q["altman_distress"], q["altman_safe"]
        parts.append(min(max((z - lo) / (hi - lo), 0.0), 1.0))
        if z < lo:
            fails.append(f"Altman Z'' {z:.2f} in distress zone")
        elif z < hi:
            flags.append(f"Altman Z'' {z:.2f} in grey zone")
    if npl is not None:
        parts.append({"ok": 1.0, "rising": 0.5, "fail": 0.0}[npl["status"]])
        if npl["status"] == "fail":
            fails.append(f"NPL ratio {npl['latest']:.1%} failing trend check")
        elif npl["status"] == "rising":
            flags.append(f"NPL ratio rising to {npl['latest']:.1%}")
    if warnings:
        fails.append("Warning announcement: " + "; ".join(w["title"] for w in warnings[:2]))
        parts.append(0.0)
    score = sum(parts) / len(parts) if parts else None
    gate = "fail" if fails else ("pass" if f is not None or z is not None or npl is not None else "unknown")
    return {"score": score, "gate": gate, "fails": fails, "flags": flags, "piotroski": f, "altman_z2": z, "npl": npl}
