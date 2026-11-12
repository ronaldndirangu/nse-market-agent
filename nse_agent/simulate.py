"""Block-bootstrap Monte Carlo of the current basket, plus historical stress windows."""
from __future__ import annotations

import math
import random
from datetime import date
from statistics import fmean

from . import config, dividends, prices, report
from .engine import analyze
from .fmt import pct, table


def basket(result: dict) -> tuple[list[str], str]:
    for key, label in (("buys", "buy candidates"), ("picks", "undervalued picks")):
        if result[key]:
            return result[key], label
    top = [t for t in result["ranking"] if result["rows"][t]["fair_value"]][:3]
    return top, "top 3 ranked (no undervalued picks this week)"


def basket_weekly(tickers: list[str], as_of: date | None = None, years: int = 10) -> list[tuple[str, float]]:
    per = [prices.weekly_returns(t, as_of) for t in tickers]
    weeks = sorted(set().union(*per)) if per else []
    out = []
    for w in weeks[-52 * years:]:
        vals = [r[w] for r in per if w in r]
        if vals:
            out.append((w, fmean(vals)))
    return out


def bootstrap(rets: list[float], weeks: int, paths: int, block: int, rng: random.Random,
              drift: float | None = None) -> list[float]:
    """Total price return per path. With drift, returns are demeaned and shifted to that weekly log drift."""
    logs = [math.log1p(r) for r in rets]
    if drift is not None:
        mu = fmean(logs)
        logs = [x - mu + drift for x in logs]
    n = len(logs)
    out = []
    for _ in range(paths):
        total, left = 0.0, weeks
        while left > 0:
            i = rng.randrange(0, n - block + 1)
            take = min(block, left)
            total += sum(logs[i:i + take])
            left -= take
        out.append(math.exp(total) - 1)
    return out


def percentile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def window_return(tickers: list[str], start: str, end: str) -> float | None:
    rets = []
    a_day, b_day = date.fromisoformat(start), date.fromisoformat(end)
    for t in tickers:
        a, b = prices.last_close(t, a_day), prices.last_close(t, b_day)
        r = dividends.total_return(t, a_day, b_day) if a and b and a[0] < b[0] else None
        if r is not None:
            rets.append(r)
    return fmean(rets) if rets else None


def simulate(paths: int | None = None, result: dict | None = None) -> dict:
    s = config.settings()["simulation"]
    m = config.macro()["taxes_and_costs"]
    result = result or analyze()
    tickers, label = basket(result)
    out = {"as_of": result["as_of"], "tickers": tickers, "label": label, "scenarios": {}, "stress": []}
    if not tickers:
        return out
    weekly = basket_weekly(tickers, date.fromisoformat(result["as_of"]))
    paths = paths or s["paths"]
    block = s["block_weeks"]
    rows = result["rows"]
    div = fmean([(rows[t]["dps"] or 0) / rows[t]["price"] * (1 - m["dividend_wht"]) for t in tickers])
    projs = [rows[t]["projection"]["base"] for t in tickers if rows[t]["projection"]]
    tbill = result["tbill_net"]
    out.update(dividend_yield_net=div, weeks=len(weekly), engine_base=fmean(projs) if projs else None, tbill_net=tbill,
               first_week=weekly[0][0] if weekly else None, last_week=weekly[-1][0] if weekly else None)
    if len(weekly) < 104:
        out["reason"] = f"only {len(weekly)} weeks of basket history"
        return out
    rets = [r for _, r in weekly]
    anchored_price = out["engine_base"] - div + 2 * m["trade_cost_per_side"] / config.settings()["valuation"][
        "horizon_years"] if projs else None
    variants = {"history": None}
    if anchored_price is not None and anchored_price > -1:
        variants["valuation"] = math.log1p(anchored_price) / 52
    for name, drift in variants.items():
        rng = random.Random(s["seed"])
        res = {}
        for y in s["horizons_years"]:
            totals = bootstrap(rets, 52 * y, paths, block, rng, drift)
            ann = [((1 + t) * (1 + div) ** y * (1 - m["trade_cost_per_side"]) ** 2) ** (1 / y) - 1 for t in totals]
            res[y] = {q: percentile(ann, q) for q in (0.05, 0.25, 0.5, 0.75, 0.95)}
            res[y]["p_beat_tbill"] = sum(a > tbill for a in ann) / len(ann)
            res[y]["p_loss"] = sum(a < 0 for a in ann) / len(ann)
        out["scenarios"][name] = res
    uni = [u["ticker"] for u in config.universe()]
    for w in s["stress_windows"]:
        out["stress"].append({"name": w["name"], "start": w["start"], "end": w["end"],
                              "basket": window_return(tickers, w["start"], w["end"]),
                              "universe": window_return(uni, w["start"], w["end"])})
    worst = {}
    for span in (4, 13, 52):
        rolls = [math.expm1(sum(math.log1p(r) for r in rets[i:i + span])) for i in range(len(rets) - span + 1)]
        if rolls:
            i = min(range(len(rolls)), key=rolls.__getitem__)
            worst[span] = (weekly[i][0], rolls[i])
    out["worst"] = worst
    return out


def render(sim: dict) -> str:
    out = ["# Monte Carlo simulation", "", report.DISCLAIMER_LINE, ""]
    if not sim["tickers"]:
        out.append("No basket to simulate: no stock has a fair value yet.")
        return "\n".join(out) + "\n"
    out += [f"Basket ({sim['label']}): **{', '.join(sim['tickers'])}**, equal weight, as of {sim['as_of']}.", ""]
    if not sim["scenarios"]:
        out.append(f"Simulation skipped: {sim.get('reason')}.")
        return "\n".join(out) + "\n"
    out += [
        f"Weekly basket returns from {sim['first_week']} to {sim['last_week']} ({sim['weeks']} weeks) are resampled "
        "in 4-week blocks to keep short-term momentum and volatility clustering. Each path adds the basket's net "
        f"dividend yield ({pct(sim['dividend_yield_net'])}) and one round trip of trading costs. Results are annualised.",
        "",
        f"- **History:** repeats the basket's own past drift and volatility.",
        f"- **Valuation-anchored:** keeps the historical volatility but centres the drift on the engine's base "
        f"projection ({pct(sim['engine_base'])} a year).",
        f"- Net 364-day T-bill: {pct(sim['tbill_net'], 2)}.", "",
    ]
    names = {"history": "History", "valuation": "Valuation-anchored"}
    rows = []
    for key, res in sim["scenarios"].items():
        for y, r in res.items():
            rows.append([names[key], f"{y}y", pct(r[0.05]), pct(r[0.25]), pct(r[0.5]), pct(r[0.75]), pct(r[0.95]),
                         pct(r["p_beat_tbill"], 0), pct(r["p_loss"], 0)])
    out += [table(["Model", "Horizon", "P5", "P25", "Median", "P75", "P95", "P(beat T-bill)", "P(loss)"], rows), "",
            "## Stress tests", "",
            table(["Window", "Dates", "Basket", "Universe"],
                  [[w["name"], f"{w['start']} to {w['end']}", pct(w["basket"]), pct(w["universe"])]
                   for w in sim["stress"]]), ""]
    if sim.get("worst"):
        out += ["Worst historical stretches for this basket (split-adjusted prices, dividends excluded):", ""]
        out += [f"- {span} weeks starting {wk}: {pct(r)}" for span, (wk, r) in sim["worst"].items()]
        out.append("")
    out += ["## Limitations", "",
            "- The past is resampled, so regimes that never happened in the sample cannot appear.",
            "- Stress returns add dividends net of withholding tax and use today's basket, not what the engine "
            "would have picked then.",
            "- Dividends are assumed constant at the current net yield."]
    return "\n".join(out) + "\n"


def run_simulation(paths: int | None = None) -> str:
    sim = simulate(paths)
    path = config.REPORTS / "simulation.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(sim), encoding="utf-8", newline="\n")
    report.build_site()
    head = f"simulation={path.relative_to(config.ROOT).as_posix()} basket={','.join(sim['tickers']) or 'none'}"
    for key, res in sim["scenarios"].items():
        for y, r in res.items():
            head += f"\n{key} {y}y median={pct(r[0.5])} p5={pct(r[0.05])} p95={pct(r[0.95])} " \
                    f"p_beat_tbill={pct(r['p_beat_tbill'], 0)}"
    return head
