"""Template-based Markdown report and static GitHub Pages site. No AI: every sentence comes from code."""
from __future__ import annotations

from pathlib import Path

from . import DISCLAIMER, __version__, config, fundamentals as fnd, risk
from .fmt import kes, num, pct, table
from .returns import weights_text

MODEL_NAMES = {
    "justified_pb": "justified P/B",
    "gordon_ddm": "Gordon dividend model",
    "earnings_power": "earnings power value",
    "sector_pe": "sector P/E",
    "sector_pb": "sector P/B",
}

AI_NOTE = (
    "No AI is used anywhere in this pipeline. Screening, valuation, quality checks, projected returns, "
    "ranking and this text all come from deterministic code and fixed templates. GitHub Models, the only "
    "free AI option considered, was retired on 2026-07-30, so the optional AI review step is not wired in."
)

DISCLAIMER_LINE = f"> **Not financial advice.** {DISCLAIMER}"


def _status(r: dict) -> str:
    if r["buy"]:
        return "Buy candidate"
    if r["undervalued"]:
        return "Undervalued (below hurdle)"
    if r["watch"]:
        return "Watch"
    if r["screen_fail"]:
        return "Screened out"
    return "Not undervalued"


def _models_line(r: dict) -> str:
    parts = []
    for k, v in sorted(r["models"].items(), key=lambda kv: -kv[1]):
        mark = " (agrees)" if k in r["agree"] else ""
        parts.append(f"{MODEL_NAMES.get(k, k)} {kes(v)}{mark}")
    return "; ".join(parts) or "none"


def _quality_line(q: dict) -> str:
    bits = []
    if q["piotroski"]:
        f = q["piotroski"]
        bits.append(f"Piotroski {f['passed']}/{f['available']} signals")
    if q["altman_z2"] is not None:
        bits.append(f"Altman Z'' {q['altman_z2']:.2f}")
    if q["npl"]:
        n = q["npl"]
        ch = f", change {n['change'] * 100:+.1f}pp" if n["change"] is not None else ""
        bits.append(f"NPL ratio {pct(n['latest'])}{ch} ({n['status']})")
    gate = {"pass": "passes", "fail": "fails", "unknown": "cannot be assessed (inputs missing)"}[q["gate"]]
    return (", ".join(bits) + "; " if bits else "") + f"quality gate {gate}"


def _risks(r: dict, result: dict) -> list[str]:
    q = r["quality"]
    risks = list(q["fails"]) + list(q["flags"])
    if r["stale"]:
        risks.append(f"Price data is stale (last close {r['price_date']}).")
    if r["beta"] is None:
        risks.append("Beta unavailable (short price history); default beta 1.0 used for cost of equity.")
    if r.get("avg_turnover") is not None and r["avg_turnover"] < 5 * config.settings()["screen"]["min_avg_daily_turnover_kes"]:
        risks.append(f"Thin liquidity: average turnover {kes(r['avg_turnover'], 0)} per session.")
    if len(r["models"]) < 3:
        risks.append(f"Only {len(r['models'])} valuation models had inputs, so the fair value range is narrow evidence.")
    if r["projection"] and r["projection"]["bear"] < result["tbill_net"]:
        risks.append(f"Bear case ({pct(r['projection']['bear'])}) trails the net T-bill yield ({pct(result['tbill_net'])}).")
    if r["fair_value"] and r["fair_value"]["high"] > 2 * r["fair_value"]["low"]:
        risks.append("Models disagree widely (high fair value is more than twice the low).")
    risks.append("Kenyan market risks: shilling depreciation, interest-rate and tax policy changes, thin trading.")
    return risks


def _thesis(r: dict, result: dict) -> str:
    fv, pr = r["fair_value"], r["projection"]
    s = config.settings()
    lines = [
        f"### {r['rank']}. {r['name']} ({r['ticker']}): {_status(r)}, {r['confidence']} confidence, "
        f"{r['risk']['level']} risk" + (", high confidence undervalued" if r["conviction"]["flag"] else ""),
        "",
        f"- **Valuation:** last close {kes(r['price'])} on {r['price_date']}. Fair value range "
        f"{kes(fv['low'])} to {kes(fv['high'])}, base {kes(fv['base'])}, a margin of safety of {pct(r['mos'])}. "
        f"{len(r['agree'])} of {len(r['models'])} models value it at least {pct(s['valuation']['mos_threshold'], 0)} "
        f"above the price (needs {r['agree_needed']}).",
        f"- **Models:** {_models_line(r)}.",
        f"- **Inputs:** {r['latest_period']} results: EPS {kes(r['eps'])}, book value per share {kes(r['bvps'])}, "
        f"DPS {kes(r['dps'])}. P/E {num(r['pe'], 1)}, P/B {num(r['pb'], 2)}. Average ROE {pct(r['roe'])}, "
        f"sustainable growth {pct(r['g'])}, cost of equity {pct(r['ke'])} (beta {num(r['beta'])}).",
        f"- **Projected annual return over {pr['years']} years (net of costs and withholding tax):** "
        f"bear {pct(pr['bear'])}, base {pct(pr['base'])}, bull {pct(pr['bull'])}. Net dividend yield "
        f"{pct(pr['dividend_yield_net'])}. The 364-day T-bill nets {pct(result['tbill_net'])}; the buy hurdle is "
        f"{pct(result['hurdle'])}.",
        f"- **Quality:** {_quality_line(r['quality'])}.",
        f"- **Momentum (average of 6 and 12 month returns, skipping the last month):** {pct(r['momentum'])}.",
        f"- **Risk profile: {r['risk']['level']}.** {r['risk']['summary']}",
        "- **Risks:**",
    ]
    lines += [f"  - {x}" for x in _risks(r, result)]
    lines.append(f"- **Source:** [{r['latest_period']} results]({r['source_url']})")
    return "\n".join(lines)


def _data_gaps(result: dict) -> list[str]:
    gaps = list(result["gaps"])
    data = fnd.load()
    for u in config.universe():
        comp = data.get(u["ticker"])
        if comp:
            gaps += [f"{u['ticker']}: {g}" for g in comp["meta"].get("gaps") or []]
    for t in result["ranking"]:
        r = result["rows"][t]
        if r["quality"]["gate"] == "unknown":
            gaps.append(f"{t}: not enough sourced line items for Piotroski, Altman Z'' or NPL checks")
        if r["momentum"] is None:
            gaps.append(f"{t}: under 12 months of prices, so no momentum score")
    need = config.settings()["high_confidence"]["min_agreeing_models"]
    short: dict[str, list[str]] = {}
    for t in result["ranking"]:
        r = result["rows"][t]
        if len(r["models"]) < need:
            short.setdefault(r["sector"], []).append(t)
    peers = config.settings()["valuation"]["min_sector_peers"]
    for sector, ts in short.items():
        gaps.append(f"{sector} ({', '.join(ts)}): fewer than {peers} sourced peers, so no sector P/E or P/B model. "
                    f"These stocks get under {need} valuation models and cannot reach High confidence until more "
                    "peers are sourced")
    return gaps


def render(result: dict, portfolio_md: str | None = None) -> str:
    m = config.macro()
    s = config.settings()
    rows = result["rows"]
    ranked = result["ranking"]
    picks = result["picks"]
    excluded = config.load_yaml(config.DATA / "universe.yaml").get("excluded") or []
    out = [
        f"# NSE value report: {result['as_of']}",
        "",
        DISCLAIMER_LINE,
        "",
        "## Summary",
        "",
        f"- Universe: {len(config.universe())} counters; {len(rows)} had prices and sourced fundamentals.",
        f"- Undervalued picks (models agree, screens and quality pass): **{len(picks)}**"
        + (f" ({', '.join(picks)})" if picks else "") + ".",
        f"- Buy candidates (base return clears the hurdle): **{len(result['buys'])}**"
        + (f" ({', '.join(result['buys'])})" if result["buys"] else "") + ".",
        f"- Watchlist (passes quality and misses exactly one gate): "
        f"{', '.join(result['watchlist']) or 'none'}.",
        f"- High confidence undervalued (all four gates pass): **{len(result['high_confidence'])}**"
        + (f" ({', '.join(result['high_confidence'])})" if result["high_confidence"] else "") + ".",
        "",
        "## Market context",
        "",
        table(["Input", "Value", "Source"], [
            ["364-day T-bill (gross)", pct(m["risk_free"]["tbill_364d"]["value"], 2), m["risk_free"]["tbill_364d"]["source"]],
            ["364-day T-bill (net of 15% WHT)", pct(result["tbill_net"], 2), "computed"],
            ["Buy hurdle (net T-bill + premium)", pct(result["hurdle"], 2), "settings.yaml"],
            ["10-year government bond", pct(m["risk_free"]["bond_10y"]["value"], 2), m["risk_free"]["bond_10y"]["source"]],
            ["Cost of equity at beta 1", pct(result["ke_at_beta_1"], 2), "rf less default spread + beta x ERP + CRP"],
            ["Macro inputs as of", str(m["as_of"]), "data/macro.yaml"],
        ]),
        "",
    ]

    out += ["## Ranked results", ""]
    if ranked:
        trs = []
        for t in ranked:
            r = rows[t]
            fv, pr = r["fair_value"], r["projection"]
            trs.append([
                str(r["rank"]), t, kes(r["price"]),
                f"{num(fv['low'])} / {num(fv['base'])} / {num(fv['high'])}" if fv else "n/a",
                pct(r["mos"]), f"{len(r['agree'])}/{len(r['models'])}",
                f"{pct(pr['bear'])} / {pct(pr['base'])} / {pct(pr['bull'])}" if pr else "n/a",
                r["quality"]["gate"], pct(r["momentum"]), num(r["composite"]), _status(r), r["confidence"],
                r["risk"]["level"],
            ])
        out.append(table(["#", "Ticker", "Price", "Fair value low / base / high", "MoS", "Agree", "Return p.a. bear / base / bull",
                          "Quality", "Momentum", "Composite", "Status", "Confidence", "Risk"], trs))
    else:
        out.append("No counters could be valued. See data gaps.")
    out += ["", f"Composite rank = {weights_text()}.", ""]
    if ranked:
        out += risk.section_md(result)

    out += ["## Picks", ""]
    if picks:
        for t in picks:
            out += [_thesis(rows[t], result), ""]
    else:
        near = [t for t in (result["watchlist"] or ranked)[:3] if rows[t]["fair_value"]]
        out += ["No counter passed every rule this week." + (" The closest candidates follow." if near else ""), ""]
        for t in near:
            out += [_thesis(rows[t], result), ""]

    out += ["## Exclusions and screen failures", ""]
    ex_rows = []
    for t in ranked:
        r = rows[t]
        why = r["screen_fail"] + r["quality"]["fails"]
        if not r["undervalued"] and why:
            ex_rows.append([t, "; ".join(why)])
    ex_rows += [[e["ticker"], e["reason"]] for e in excluded]
    out += [table(["Ticker", "Reason"], ex_rows) if ex_rows else "None.", ""]

    if portfolio_md:
        out += ["## Portfolio review", "", portfolio_md, ""]

    out += ["## Data gaps", ""]
    gaps = _data_gaps(result)
    out += ([f"- {g}" for g in gaps] if gaps else ["None."]) + [""]

    out += [
        "## Method",
        "",
        f"- **Screen:** average turnover of at least {kes(s['screen']['min_avg_daily_turnover_kes'], 0)} per session, "
        f"at least {s['screen']['min_annual_periods']} sourced annual periods, positive EPS, not suspended, price no "
        f"older than {s['screen']['max_price_age_days']} days, latest annual period ended no more than "
        f"{s['screen']['max_fundamentals_age_days']} days ago (results are due within 4 months of year end).",
        "- **Models:** banks use justified P/B = BVPS x (ROE - g) / (ke - g). Dividend payers use Gordon "
        "V = DPS x (1 + g) / (ke - g). Every counter gets earnings power value (3-year average EPS / ke), and sector "
        f"median P/E and P/B when at least {s['valuation']['min_sector_peers']} peers have them. The Graham number is "
        "left out: its fixed 22.5 multiple assumes far lower interest rates than Kenya's, so it overstates value "
        "here. When the highest model value is more than "
        f"{s['valuation']['max_model_spread']:.0f}x the lowest, the models disagree too much to trust and the stock "
        "is rated Avoid.",
        f"- **Cost of equity:** ke = (10-year bond - default spread) + beta x {pct(m['equity_risk']['mature_market_erp'], 2)} "
        f"+ country risk premium {pct(m['equity_risk']['country_risk_premium'], 2)}. Beta is a Blume-adjusted weekly "
        "beta against an equal-weight index of the universe.",
        f"- **Growth:** g = average ROE x retention, clipped to {pct(s['valuation']['growth_floor'], 0)} to "
        f"{pct(s['valuation']['growth_cap'], 0)} and kept {pct(s['valuation']['min_ke_minus_g'], 0)} below ke.",
        f"- **Undervalued:** at least max(2, half) of the models show a margin of safety of "
        f"{pct(s['valuation']['mos_threshold'], 0)} or more, the models agree within "
        f"{s['valuation']['max_model_spread']:.0f}x, all screens pass and the quality gate passes.",
        f"- **Projected return:** net dividend yield + (1 + g) x (V / P)^(1/{s['valuation']['horizon_years']}) - 1 - "
        "round-trip costs spread over the horizon. Bear uses the low fair value and g - 2pp; bull uses the high fair "
        "value and g + 2pp.",
        "- **Quality gate:** Piotroski F-score share, Altman Z'' (non-financials), bank NPL trend and profit-warning "
        "keywords in NSE announcements over the last 180 days.",
        "- **Risk profile:** seven factors (volatility, beta, liquidity, bear-case return, fair value spread, balance "
        "sheet and warning announcements) rated Low, Moderate or High from fixed thresholds. Shown beside the status; "
        "it never changes it.",
        "- **High confidence undervalued:** a Buy candidate where at least three models agree and the quality score "
        "is 0.67 or more. Sector P/E and P/B need enough sourced peers, so most non-banks have only two models and "
        "cannot be flagged yet.",
        f"- **AI:** {AI_NOTE}",
        f"- Generated by nse-market-agent {__version__}.",
        "",
        DISCLAIMER_LINE,
        "",
    ]
    return "\n".join(out)


def write(result: dict, portfolio_md: str | None = None) -> Path:
    text = render(result, portfolio_md)
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    dated = config.REPORTS / f"{result['as_of']}.md"
    for p in (dated, config.REPORTS / "latest.md"):
        p.write_text(text, encoding="utf-8", newline="\n")
    return dated



def build_site() -> list[Path]:
    """Render the reports into the static GitHub Pages site."""
    from . import site
    return site.build()
