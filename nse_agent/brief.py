"""Daily brief: top 5 with template reasons, what changed since the last brief, and material-change alerts."""
from __future__ import annotations

import logging
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import announcements, config, dividends, ledger, prices, report, risk, storage
from .engine import analyze
from .fmt import kes, num, pct, table
from .quality import warnings_for
from .returns import weights_text

log = logging.getLogger(__name__)

LABELS = {"margin_of_safety": "margin of safety", "quality": "quality", "momentum": "momentum",
          "dividend_yield": "dividend yield", "low_volatility": "low volatility"}
TOP_N = 5


def daily_dir() -> Path:
    return config.REPORTS / "daily"


def _signed(v: float | None, nd: int = 2) -> str:
    return "n/a" if v is None else f"{v:+.{nd}f}"


def why(r: dict, result: dict) -> str:
    """One templated sentence block: valuation, return versus hurdle, main score driver, binding constraint."""
    parts = []
    if r["mos"] is not None:
        word = "upside" if r["mos"] >= 0 else "downside"
        parts.append(f"{pct(abs(r['mos']))} {word} to base fair value {kes(r['fair_value']['base'])}")
    pr = r["projection"]
    if pr:
        verb = "beats" if pr["base"] > result["hurdle"] else "trails"
        parts.append(f"base return {pct(pr['base'])} a year {verb} the {pct(result['hurdle'], 2)} hurdle")
    text = f"{r['ticker']} #{r['rank']} ({r['tier']}): " + ("; ".join(parts) or "no valuation inputs") + "."
    d = _driver(r)
    if d:
        text += f" Biggest score driver: {d['label']} ({_signed(d['contribution'])})."
    return f"{text} {r['binding']} {risk_short(r)}."


def risk_short(r: dict) -> str:
    rk = r["risk"]
    return f"{rk['level']} risk" + (f" ({'; '.join(rk['drivers'][:2])})" if rk["drivers"] else "")


def unusual_moves(result: dict, since: str | None) -> list[dict]:
    """Latest daily move (split-adjusted) beyond max(5%, 2.5 x the prior 60-session SD)."""
    as_of = date.fromisoformat(result["as_of"])
    max_age = config.settings()["screen"]["max_price_age_days"]
    out = []
    for t in result["ranking"]:
        rs = prices.rows(t, as_of)[-62:]
        if len(rs) < 22:
            continue
        closes = [c * dividends.factor(t, date.fromisoformat(d)) for d, c, _ in rs]
        rets = [b / a - 1 for a, b in zip(closes, closes[1:]) if a > 0]
        day = rs[-1][0]
        if (since and day <= since) or (as_of - date.fromisoformat(day)).days > max_age:
            continue
        sd = statistics.pstdev(rets[:-1]) if len(rets) > 2 else 0.0
        limit = max(0.05, 2.5 * sd)
        if abs(rets[-1]) > limit:
            ex = [amt for d, amt in dividends.history(t) if d.isoformat() == day]
            note = f"dividend of {kes(ex[0])} went ex on this date" if ex else ""
            out.append({"ticker": t, "date": day, "ret": rets[-1], "limit": limit, "note": note})
    return out


def new_announcements(result: dict, since: str | None) -> list[dict]:
    covered = set(result["rows"])
    lo = since or result["as_of"]
    return [a for a in announcements.items()
            if a.get("ticker") in covered and (a["first_seen"] > lo if since else a["first_seen"] == lo)
            and a["first_seen"] <= result["as_of"]]


def new_warnings(result: dict, anns: list[dict]) -> list[dict]:
    as_of = date.fromisoformat(result["as_of"])
    out = []
    for u in config.universe():
        for a in warnings_for(u["ticker"], u.get("aliases", []), anns, as_of):
            out.append({**a, "ticker": u["ticker"]})
    return out


def changes(result: dict, prev_date: str | None, prev: dict[str, dict]) -> dict:
    rows, ranked = result["rows"], result["ranking"]
    thr = config.settings()["valuation"]["mos_threshold"]
    hurdle = result["hurdle"]
    anns = new_announcements(result, prev_date)
    ch = {"prev_date": prev_date, "announcements": anns, "warnings": new_warnings(result, anns),
          "moves": unusual_moves(result, prev_date), "top_in": [], "top_out": [], "tiers": [], "ranks": [],
          "crossings": []}
    if not prev_date:
        return ch
    prev_top = [t for t, p in sorted(prev.items(), key=lambda kv: kv[1]["rank"])][:TOP_N]
    ch["top_in"] = [t for t in ranked[:TOP_N] if t not in prev_top]
    ch["top_out"] = [t for t in prev_top if t not in ranked[:TOP_N]]
    for t in ranked:
        r, p = rows[t], prev.get(t)
        if not p:
            ch["tiers"].append((t, "not ranked", r["tier"]))
            continue
        if p["tier"] != r["tier"]:
            ch["tiers"].append((t, p["tier"], r["tier"]))
        if abs(p["rank"] - r["rank"]) >= 2:
            ch["ranks"].append((t, p["rank"], r["rank"]))
        if p["mos"] is not None and r["mos"] is not None and (p["mos"] >= thr) != (r["mos"] >= thr):
            side = "above" if r["mos"] >= thr else "below"
            ch["crossings"].append(f"{t}: margin of safety moved {side} {pct(thr, 0)} "
                                   f"({pct(p['mos'])} to {pct(r['mos'])})")
        base = r["projection"]["base"] if r["projection"] else None
        if p["base"] is not None and base is not None and (p["base"] > hurdle) != (base > hurdle):
            side = "above" if base > hurdle else "below"
            ch["crossings"].append(f"{t}: base return moved {side} the {pct(hurdle, 2)} hurdle "
                                   f"({pct(p['base'])} to {pct(base)})")
    ch["tiers"] += [(t, prev[t]["tier"], "not ranked") for t in prev if t not in rows]
    return ch


def alerts(result: dict, ch: dict, prev: dict[str, dict]) -> list[str]:
    """Material changes only: a new Buy, a dropped Buy or a new warning announcement."""
    rows = result["rows"]
    hc = set(result["high_confidence"])
    out = [("New Buy, high confidence undervalued: " if t in hc else "New Buy: ") + why(rows[t], result)
           for t in result["buys"] if prev.get(t, {}).get("tier") != "Buy"]
    out += [f"Now high confidence undervalued: {why(rows[t], result)}" for t in result["high_confidence"]
            if prev.get(t, {}).get("tier") == "Buy" and prev[t].get("high_confidence") not in ("True", None)]
    for t, p in prev.items():
        if p["tier"] == "Buy" and t not in result["buys"]:
            reason = rows[t]["binding"] if t in rows else "no longer ranked (missing price or fundamentals)."
            out.append(f"Buy dropped: {t}. {reason}")
    out += [f"Warning announcement for {w['ticker']}: [{w['title']}]({w['url']})" for w in ch["warnings"]]
    return out


def _contrib(s: dict, value_fmt) -> str:
    return f"{_signed(s['contribution'])} ({value_fmt(s['value'])})"


def _value_fmt(name: str):
    if name == "quality":
        return lambda v: num(v, 2)
    if name == "low_volatility":
        return lambda v: pct(-v) + " vol" if v is not None else "n/a"
    return pct


def _changes_md(result: dict, ch: dict) -> list[str]:
    out = ["## What changed", ""]
    if not ch["prev_date"]:
        out += ["No earlier brief in the ledger, so there is nothing to compare yet.", ""]
    else:
        out += [f"Compared with the brief for {ch['prev_date']}.", ""]
    items = []
    if ch["top_in"] or ch["top_out"]:
        items.append(f"Top {TOP_N}: entered {', '.join(ch['top_in']) or 'none'}; left {', '.join(ch['top_out']) or 'none'}.")
    items += [f"Tier: {t} moved from {a} to {b}." for t, a, b in ch["tiers"]]
    items += [f"Threshold: {c}." for c in ch["crossings"]]
    items += [f"Rank: {t} moved from #{a} to #{b}." for t, a, b in ch["ranks"]]
    items += [f"Announcement ({a['ticker']}, {a['date']}): [{a['title']}]({a['url']})" for a in ch["announcements"]]
    for m in ch["moves"]:
        note = f" Note: {m['note']}." if m["note"] else ""
        items.append(f"Unusual move: {m['ticker']} {pct(m['ret'])} on {m['date']} (threshold {pct(m['limit'])}).{note}")
    out += [f"- {i}" for i in items] if items else ["No rank, tier, threshold, announcement or price changes worth flagging."]
    out.append("")
    return out


def render(result: dict, ch: dict, alert_lines: list[str]) -> str:
    rows, ranked = result["rows"], result["ranking"]
    tiers = {k: sum(1 for t in ranked if rows[t]["tier"] == k) for k in ("Buy", "Watch", "Avoid")}
    weighted = [n for n, w in config.settings()["ranking"]["weights"].items() if w]
    out = [
        f"# NSE daily brief: {result['as_of']}", "",
        report.DISCLAIMER_LINE, "",
        f"{len(ranked)} stocks valued. Buy {tiers['Buy']}, Watch {tiers['Watch']}, Avoid {tiers['Avoid']}. "
        f"The 364-day T-bill nets {pct(result['tbill_net'])} after withholding tax; the buy hurdle is "
        f"{pct(result['hurdle'], 2)}.", "",
    ]
    if alert_lines:
        out += ["## Alerts", ""] + [f"- {a}" for a in alert_lines] + [""]
    out += risk.section_md(result)
    out += [f"## Top {TOP_N}", ""]
    for t in ranked[:TOP_N]:
        out.append(f"- {why(rows[t], result)}")
    out += ["", "### Score breakdown", "",
            "Each cell is the signal's contribution to the composite (weight x z-score), with the raw value in "
            "brackets.", ""]
    hdr = ["Rank", "Ticker", "Tier", "Composite"] + [LABELS[n].capitalize() for n in weighted]
    body = [[str(rows[t]["rank"]), t, rows[t]["tier"], _signed(rows[t]["composite"])]
            + [_contrib(rows[t]["signals"][n], _value_fmt(n)) for n in weighted] for t in ranked[:TOP_N]]
    out += [table(hdr, body), ""]
    out += _changes_md(result, ch)
    out += ["## Full ranking", ""]
    body = []
    for t in ranked:
        r, pr = rows[t], rows[t]["projection"]
        body.append([str(r["rank"]), t, r["tier"] + (" (high confidence)" if r["conviction"]["flag"] else ""),
                     _signed(r["composite"]), kes(r["price"]), pct(r["mos"]),
                     f"{pct(pr['bear'])} / {pct(pr['base'])} / {pct(pr['bull'])}" if pr else "n/a",
                     pct(r["dividend_yield"]), pct(r["volatility"]), r["risk"]["level"], r["binding"]])
    out += [table(["Rank", "Ticker", "Tier", "Composite", "Price", "MoS", "Bear / base / bull a year",
                   "Div. yield", "Volatility", "Risk", "Binding constraint"], body), ""]
    s = config.settings()
    unweighted = [LABELS[n] for n in LABELS if n not in weighted]
    one = len(unweighted) == 1
    note = (f" {' and '.join(unweighted).capitalize()} {'is' if one else 'are'} logged for research but "
            f"{'carries' if one else 'carry'} no weight until a reviewed tuning PR changes the weights."
            if unweighted else "")
    out += [
        "## How to read this", "",
        f"- Composite score = {weights_text()}.{note}",
        f"- **Buy** clears every gate: quality passes, the screen passes, at least two valuation models agree on a "
        f"margin of safety of {pct(s['valuation']['mos_threshold'], 0)} or more, and the base return beats the "
        f"hurdle. **Watch** passes quality and misses one gate. **Avoid** misses more, or fails quality.",
        "- **High confidence undervalued** is a stricter Buy: three or more models agree and quality scores 0.67 or "
        "more. In the monthly backtest it fired rarely and lost money over 12 months in none of its cases, but its "
        "excess return over the equal-weight universe was mixed, so treat it as a filter for review, not a "
        "guarantee.",
        "- **Risk** (Low, Moderate or High) rates volatility, beta, liquidity, bear-case return, fair value spread, "
        "balance sheet (Altman Z'' or bank NPL) and warning announcements. It is shown beside the tier and never "
        "changes it.",
        f"- Returns are annualised over {s['valuation']['horizon_years']} years, net of trading costs and dividend "
        "withholding tax.",
        "- Every stock's score, signals, tier and projections are appended daily to `data/rankings/live/` and never "
        "edited, so the retrospective can score these calls later.", "",
        "## Data gaps", "",
    ]
    gaps = report._data_gaps(result)
    out += [f"- {g}" for g in gaps] if gaps else ["None."]
    out += ["", report.DISCLAIMER_LINE, ""]
    return "\n".join(out)


def write(text: str, day: str) -> Path:
    daily_dir().mkdir(parents=True, exist_ok=True)
    dated = daily_dir() / f"{day}.md"
    for p in (dated, daily_dir() / "latest.md"):
        p.write_text(text, encoding="utf-8", newline="\n")
    return dated


def _driver(r: dict) -> dict | None:
    weighted = [(n, s) for n, s in r["signals"].items() if s["weight"]]
    if not weighted:
        return None
    name, s = max(weighted, key=lambda kv: kv[1]["contribution"])
    return {"signal": name, "label": LABELS[name], "contribution": s["contribution"]}


def snapshot(result: dict, ch: dict, alert_lines: list[str]) -> dict:
    """Structured copy of the brief for the site dashboard."""
    rows, ranked = result["rows"], result["ranking"]

    def item(t: str) -> dict:
        r, pr = rows[t], rows[t]["projection"] or {}
        fv = r["fair_value"] or {}
        return {"rank": r["rank"], "ticker": t, "name": r["name"], "sector": r["sector"], "tier": r["tier"],
                "price": r["price"], "price_date": r["price_date"], "mos": r["mos"], "fair_low": fv.get("low"),
                "fair_base": fv.get("base"), "fair_high": fv.get("high"), "bear": pr.get("bear"),
                "base": pr.get("base"), "bull": pr.get("bull"), "composite": r["composite"],
                "dividend_yield": r["dividend_yield"], "binding": r["binding"], "driver": _driver(r),
                "risk": {"level": r["risk"]["level"], "summary": r["risk"]["summary"],
                         "factors": [{"name": f["name"], "level": f["level"], "detail": f["detail"]}
                                     for f in r["risk"]["factors"]]},
                "conviction": {"flag": r["conviction"]["flag"], "failed": r["conviction"]["failed"],
                               "gates": r["conviction"]["gates"]},
                "why": why(r, result)}

    return {"as_of": result["as_of"], "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "valued": len(ranked), "hurdle": result["hurdle"], "tbill_net": result["tbill_net"],
            "counts": {k: sum(1 for t in ranked if rows[t]["tier"] == k) for k in ("Buy", "Watch", "Avoid")},
            "alerts": alert_lines,
            "high_confidence": [item(t) for t in result["high_confidence"]],
            "near_misses": [] if result["high_confidence"] else [item(t) for t in risk.near_misses(rows, ranked)],
            "rule": risk.rule_text(result["hurdle"]),
            "changes": {"prev_date": ch["prev_date"], "top_in": ch["top_in"], "top_out": ch["top_out"],
                        "tiers": len(ch["tiers"]), "crossings": len(ch["crossings"]),
                        "announcements": len(ch["announcements"]), "moves": len(ch["moves"])},
            "top": [item(t) for t in ranked[:TOP_N]],
            "ranking": [{k: v for k, v in item(t).items() if k not in ("why", "binding")} for t in ranked]}


def write_snapshot(result: dict, ch: dict, alert_lines: list[str]) -> Path:
    p = daily_dir() / "latest.json"
    storage.write_json(p, snapshot(result, ch, alert_lines))
    return p


def alert_body(result: dict, alert_lines: list[str]) -> str:
    return "\n".join([f"Material changes in the NSE daily brief for {result['as_of']}:", ""]
                     + [f"- {a}" for a in alert_lines]
                     + ["", "Generated by fixed rules from public data. Not financial advice.", ""])


def run_brief(fetch: bool = True, alert_file: str | None = None, as_of: date | None = None,
              fetch_prices: bool = True) -> str:
    if fetch:
        from . import market
        steps = (("daily", market.update_daily),) if fetch_prices else ()
        for name, step in steps + (("announcements", announcements.update),):
            try:
                step()
            except Exception as exc:  # a failed source must not stop the brief
                log.warning("%s refresh failed: %s", name, exc)
    prices.clear_cache()
    dividends.clear_cache()
    result = analyze(as_of)
    prev_date, prev = ledger.previous(result["as_of"])
    ch = changes(result, prev_date, prev)
    alert_lines = alerts(result, ch, prev)
    path = write(render(result, ch, alert_lines), result["as_of"])
    logged = ledger.append(result)
    write_snapshot(result, ch, alert_lines)
    report.build_site()
    if alert_file and alert_lines:
        Path(alert_file).write_text(alert_body(result, alert_lines), encoding="utf-8", newline="\n")
    lines = [f"brief={path.relative_to(config.ROOT).as_posix()} valued={len(result['ranking'])} "
             f"buys={len(result['buys'])} ledger_rows={logged} alerts={len(alert_lines)} prev={prev_date}"]
    lines += [why(result["rows"][t], result) for t in result["ranking"][:TOP_N]]
    return "\n".join(lines)
