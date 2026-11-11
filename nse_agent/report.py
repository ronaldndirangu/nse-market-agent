"""Template-based Markdown report and static GitHub Pages site. No AI: every sentence comes from code."""
from __future__ import annotations

import html
import re
from pathlib import Path

from . import DISCLAIMER, __version__, config, fundamentals as fnd
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
        f"### {r['rank']}. {r['name']} ({r['ticker']}): {_status(r)}, {r['confidence']} confidence",
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
        f"- Watchlist (models agree but a screen or quality check is missing or failing): "
        f"{', '.join(result['watchlist']) or 'none'}.",
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
            ])
        out.append(table(["#", "Ticker", "Price", "Fair value low / base / high", "MoS", "Agree", "Return p.a. bear / base / bull",
                          "Quality", "Momentum", "Composite", "Status", "Confidence"], trs))
    else:
        out.append("No counters could be valued. See data gaps.")
    out += ["", f"Composite rank = {weights_text()}.", ""]

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
        f"older than {s['screen']['max_price_age_days']} days.",
        "- **Models:** banks use justified P/B = BVPS x (ROE - g) / (ke - g). Dividend payers use Gordon "
        "V = DPS x (1 + g) / (ke - g). Every counter gets earnings power value (3-year average EPS / ke), and sector "
        f"median P/E and P/B when at least {s['valuation']['min_sector_peers']} peers have them. The Graham number is "
        "shown for reference only.",
        f"- **Cost of equity:** ke = (10-year bond - default spread) + beta x {pct(m['equity_risk']['mature_market_erp'], 2)} "
        f"+ country risk premium {pct(m['equity_risk']['country_risk_premium'], 2)}. Beta is a Blume-adjusted weekly "
        "beta against an equal-weight index of the universe.",
        f"- **Growth:** g = average ROE x retention, clipped to {pct(s['valuation']['growth_floor'], 0)} to "
        f"{pct(s['valuation']['growth_cap'], 0)} and kept {pct(s['valuation']['min_ke_minus_g'], 0)} below ke.",
        f"- **Undervalued:** at least max(2, half) of the models show a margin of safety of "
        f"{pct(s['valuation']['mos_threshold'], 0)} or more, all screens pass and the quality gate passes.",
        f"- **Projected return:** net dividend yield + (1 + g) x (V / P)^(1/{s['valuation']['horizon_years']}) - 1 - "
        "round-trip costs spread over the horizon. Bear uses the low fair value and g - 2pp; bull uses the high fair "
        "value and g + 2pp.",
        "- **Quality gate:** Piotroski F-score share, Altman Z'' (non-financials), bank NPL trend and profit-warning "
        "keywords in NSE announcements over the last 180 days.",
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


PAGES = [("latest.md", "index.html", "Weekly report"), ("daily/latest.md", "daily.html", "Daily brief"),
         ("retrospective.md", "retrospective.html", "Retrospective"), ("simulation.md", "simulation.html", "Simulation"),
         ("backtest.md", "backtest.html", "Backtest"), ("scorecard.md", "scorecard.html", "Scorecard"),
         ("tuning.md", "tuning.html", "Weight tuning")]
DATED = re.compile(r"\d{4}-\d{2}-\d{2}\.md")

CSS = """body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:1100px;margin:2rem auto;
padding:0 1rem;line-height:1.5;color:#1f2328}table{border-collapse:collapse;display:block;overflow-x:auto;margin:1rem 0}
th,td{border:1px solid #d0d7de;padding:4px 8px;text-align:left;white-space:nowrap}th{background:#f6f8fa}
blockquote{border-left:4px solid #d1242f;margin:1rem 0;padding:.5rem 1rem;background:#fff5f5}
nav a{margin-right:1rem}code{background:#f6f8fa;padding:0 3px}"""


def _md_to_html(text: str) -> str:
    try:
        import markdown
        return markdown.markdown(text, extensions=["tables"])
    except ImportError:
        return "<pre>" + html.escape(text) + "</pre>"


def build_site() -> list[Path]:
    """Render the Markdown reports into a static site for GitHub Pages."""
    config.SITE.mkdir(parents=True, exist_ok=True)
    present = [(src, dst, title) for src, dst, title in PAGES if (config.REPORTS / src).exists()]
    archives = [("reports", config.REPORTS, "archive.html", "Weekly report archive"),
                ("daily", config.REPORTS / "daily", "daily-archive.html", "Daily brief archive")]
    links = [(dst, title) for _, dst, title in present] + [("archive.html", "Archive")]
    if (config.REPORTS / "daily").exists():
        links.append(("daily-archive.html", "Daily archive"))
    written = []

    def page(name: str, title: str, body: str) -> None:
        up = "../" * name.count("/")
        nav = " ".join(f'<a href="{up}{dst}">{t}</a>' for dst, t in links)
        nav += ' <a href="https://github.com/ronaldndirangu/nse-market-agent">Source</a>'
        doc = (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
               f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
               f"<title>{html.escape(title)} | NSE value agent</title><style>{CSS}</style></head>"
               f"<body><nav>{nav}</nav>{body}</body></html>\n")
        p = config.SITE / name
        p.write_text(doc, encoding="utf-8", newline="\n")
        written.append(p)

    for src, dst, title in present:
        page(dst, title, _md_to_html((config.REPORTS / src).read_text(encoding="utf-8")))
    for sub, src_dir, index, heading in archives:
        if sub == "daily" and not src_dir.exists():
            continue
        (config.SITE / sub).mkdir(exist_ok=True)
        items = []
        for p in sorted((p for p in src_dir.glob("*.md") if DATED.fullmatch(p.name)), reverse=True):
            name = f"{sub}/{p.stem}.html"
            page(name, p.stem, _md_to_html(p.read_text(encoding="utf-8")))
            items.append(f'<li><a href="{name}">{p.stem}</a></li>')
        page(index, heading, f"<h1>{heading}</h1><ul>" + "".join(items) + "</ul>")
    (config.SITE / ".nojekyll").write_text("", encoding="utf-8")
    return written
