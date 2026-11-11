"""Deterministic risk profile and the high confidence undervalued flag.

The flag needs every conviction gate to pass. The risk profile is reported alongside it and never changes a tier,
so a flagged stock can still carry High risk.
"""
from __future__ import annotations

from . import config
from .fmt import kes, pct, table

LEVELS = ("Low", "Moderate", "High")
GATES = ("Valuation", "Quality", "Screen", "Return")


def _band(value: float | None, moderate: float, high: float, lower_is_risky: bool = False) -> str | None:
    if value is None:
        return None
    if lower_is_risky:
        return "High" if value < high else "Moderate" if value < moderate else "Low"
    return "High" if value > high else "Moderate" if value >= moderate else "Low"


def _factor(name: str, level: str | None, value, detail: str) -> dict:
    return {"name": name, "level": level, "value": value, "detail": detail if level else f"{name}: not assessed"}


def _balance_sheet(r: dict, s: dict) -> dict:
    q = r["quality"]
    if r["bank"]:
        npl = q.get("npl")
        if not npl:
            return _factor("Balance sheet", None, None, "")
        latest = npl["latest"]
        level = _band(latest, s["risk"]["npl"]["moderate"], s["risk"]["npl"]["high"])
        if npl["status"] == "fail":
            level = "High"
        elif npl["status"] == "rising" and level == "Low":
            level = "Moderate"
        trend = {"ok": "stable or falling", "rising": "rising", "fail": "rising sharply"}[npl["status"]]
        return _factor("Balance sheet", level, latest, f"NPL ratio {latest:.1%}, {trend}")
    z = q.get("altman_z2")
    if z is None:
        return _factor("Balance sheet", None, None, "")
    level = _band(z, s["quality"]["altman_safe"], s["quality"]["altman_distress"], lower_is_risky=True)
    zone = {"Low": "safe zone", "Moderate": "grey zone", "High": "distress zone"}[level]
    return _factor("Balance sheet", level, z, f"Altman Z'' {z:.2f}, {zone}")


def _events(r: dict) -> dict:
    warns = [f for f in r["quality"]["fails"] if f.startswith("Warning announcement")]
    if warns:
        return _factor("Events", "High", len(warns), warns[0])
    if "suspended" in r.get("screen_fail", []):
        return _factor("Events", "High", 1, "trading suspended")
    return _factor("Events", "Low", 0, "no profit warning or suspension on file")


def factors(r: dict) -> list[dict]:
    s = config.settings()
    k = s["risk"]
    out = []
    vol = r.get("volatility")
    out.append(_factor("Volatility", _band(vol, k["volatility"]["moderate"], k["volatility"]["high"]), vol,
                       f"volatility {vol:.0%}" if vol is not None else ""))
    beta = r.get("beta")
    out.append(_factor("Beta", _band(beta, k["beta"]["moderate"], k["beta"]["high"]), beta,
                       f"beta {beta:.2f}" if beta is not None else ""))
    to = r.get("avg_turnover")
    out.append(_factor("Liquidity", _band(to, k["turnover_kes"]["moderate"], k["turnover_kes"]["high"], True), to,
                       f"turnover KES {to / 1e6:,.1f}M a day" if to is not None else ""))
    bear = (r.get("projection") or {}).get("bear")
    out.append(_factor("Downside", _band(bear, k["bear_return"]["moderate"], k["bear_return"]["high"], True), bear,
                       f"bear case {bear:+.1%} a year" if bear is not None else ""))
    fv = r.get("fair_value") or {}
    spread = fv["high"] / fv["low"] if fv.get("low") and fv["low"] > 0 and fv.get("high") else None
    out.append(_factor("Valuation spread",
                       _band(spread, k["fair_value_spread"]["moderate"], k["fair_value_spread"]["high"]), spread,
                       f"fair value spread {spread:.1f}x ({fv.get('low', 0):,.1f} to {fv.get('high', 0):,.1f})"
                       if spread is not None else ""))
    out.append(_balance_sheet(r, s))
    out.append(_events(r))
    return out


def profile(r: dict) -> dict:
    fs = factors(r)
    high = [f for f in fs if f["level"] == "High"]
    moderate = [f for f in fs if f["level"] == "Moderate"]
    severe = any(f["name"] in ("Balance sheet", "Events") for f in high)
    if severe or len(high) >= 2:
        level = "High"
    elif high or len(moderate) >= 3:
        level = "Moderate"
    else:
        level = "Low"
    drivers = [f["detail"] for f in high + moderate]
    missing = [f["name"] for f in fs if f["level"] is None]
    summary = f"{level} risk"
    if drivers:
        summary += ": " + "; ".join(drivers[:3]) + (f" (+{len(drivers) - 3} more)" if len(drivers) > 3 else "")
    else:
        summary += ": no factor above Low"
    if missing:
        summary += ". Not assessed: " + ", ".join(missing).lower()
    return {"level": level, "factors": fs, "drivers": drivers, "missing": missing, "summary": summary + "."}


def conviction(r: dict, hurdle: float) -> dict:
    """High confidence undervalued: broad model agreement, strong quality, a clean screen and a return edge."""
    s = config.settings()
    hc = s["high_confidence"]
    mos = s["valuation"]["mos_threshold"]
    n_models, n_agree = len(r["models"]), len(r["agree"])
    need = max(hc["min_agreeing_models"], r["agree_needed"])
    q = r["quality"]
    qs = q["score"]
    base = (r.get("projection") or {}).get("base")
    gates = [
        {"name": "Valuation", "passed": n_agree >= need and n_models >= 2,
         "detail": f"{n_agree} of {n_models} models show at least {mos:.0%} upside, needs {need}"},
        {"name": "Quality", "passed": q["gate"] == "pass" and qs is not None and qs >= hc["min_quality_score"],
         "detail": (f"quality gate {q['gate']}, score " + (f"{qs:.2f}" if qs is not None else "n/a")
                    + f", needs pass and {hc['min_quality_score']:.2f}")},
        {"name": "Screen", "passed": not r["screen_fail"],
         "detail": "liquid, fresh price, enough history, positive EPS" if not r["screen_fail"]
         else "; ".join(r["screen_fail"])},
        {"name": "Return", "passed": base is not None and base > hurdle,
         "detail": (f"base return {base:.1%} against the {hurdle:.2%} hurdle" if base is not None
                    else "no projection")},
    ]
    failed = [g["name"] for g in gates if not g["passed"]]
    return {"flag": not failed, "gates": gates, "failed": failed}


def near_misses(rows: dict, ranking: list[str], n: int = 3) -> list[str]:
    """Unflagged stocks closest to the flag: fewest failed gates, then rank."""
    cands = [t for t in ranking if not rows[t]["conviction"]["flag"]]
    return sorted(cands, key=lambda t: (len(rows[t]["conviction"]["failed"]), rows[t]["rank"]))[:n]


def _short(f: dict) -> str:
    v, name = f["value"], f["name"]
    if f["level"] is None:
        return "n/a"
    if name == "Volatility":
        txt = pct(v, 0)
    elif name == "Beta":
        txt = f"{v:.2f}"
    elif name == "Liquidity":
        txt = f"KES {v / 1e6:,.1f}M"
    elif name == "Downside":
        txt = f"{v:+.1%}"
    elif name == "Valuation spread":
        txt = f"{v:.1f}x"
    elif name == "Balance sheet":
        txt = f"NPL {v:.1%}" if f["detail"].startswith("NPL") else f"Z'' {v:.2f}"
    else:
        txt = "warning" if v else "none"
    return f"{f['level']} ({txt})"


FACTORS = ("Volatility", "Beta", "Liquidity", "Downside", "Valuation spread", "Balance sheet", "Events")


def matrix_md(rows: dict, tickers: list[str]) -> str:
    body = [[t, rows[t]["risk"]["level"]] + [_short(f) for f in rows[t]["risk"]["factors"]] for t in tickers]
    return table(["Ticker", "Risk"] + list(FACTORS), body)


def rule_text(hurdle: float) -> str:
    s = config.settings()
    hc = s["high_confidence"]
    return (f"A stock is flagged **High confidence undervalued** only when all four gates pass: at least "
            f"{hc['min_agreeing_models']} valuation models agree on {pct(s['valuation']['mos_threshold'], 0)} or "
            f"more upside (Valuation), the quality gate passes with a score of {hc['min_quality_score']:.2f} or more "
            f"(Quality), the liquidity, freshness and history screen passes (Screen), and the base return beats the "
            f"{pct(hurdle, 2)} hurdle (Return). Risk is rated separately from seven factors and never changes the "
            f"flag, so check it before sizing a position.")


def section_md(result: dict, heading: str = "##") -> list[str]:
    rows, ranked, flagged = result["rows"], result["ranking"], result["high_confidence"]
    out = [f"{heading} High confidence undervalued", "", rule_text(result["hurdle"]), ""]
    if flagged:
        body = []
        for t in flagged:
            r, pr, fv = rows[t], rows[t]["projection"], rows[t]["fair_value"]
            body.append([t, kes(r["price"]), f"{kes(fv['low'])} / {kes(fv['base'])} / {kes(fv['high'])}",
                         pct(r["mos"]), f"{pct(pr['bear'])} / {pct(pr['base'])} / {pct(pr['bull'])}",
                         r["risk"]["level"], "; ".join(r["risk"]["drivers"][:3]) or "none above Low"])
        out += [table(["Ticker", "Price", "Fair value low / base / high", "MoS", "Bear / base / bull a year",
                       "Risk", "Risk drivers"], body), ""]
        shown = flagged
    else:
        near = near_misses(rows, ranked)
        out += [f"No stock qualifies on {result['as_of']}. The closest candidates and the gates they miss:", ""]
        body = [[t, rows[t]["tier"], f"{4 - len(rows[t]['conviction']['failed'])} of 4",
                 "; ".join(f"{g['name']}: {g['detail']}" for g in rows[t]["conviction"]["gates"] if not g["passed"]),
                 rows[t]["risk"]["level"]] for t in near]
        out += [table(["Ticker", "Tier", "Gates passed", "Missing", "Risk"], body), ""]
        shown = near
    out += [f"{heading}# Risk profile", "",
            "Each factor is rated Low, Moderate or High from fixed thresholds in `data/settings.yaml`. Overall risk "
            "is High when the balance sheet or events factor is High or two factors are High, and Moderate when "
            "one factor is High or three are Moderate.", "",
            matrix_md(rows, list(dict.fromkeys(list(shown) + ranked[:5]))), ""]
    return out
