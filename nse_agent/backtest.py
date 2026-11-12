"""Monthly walk-forward backtest that only uses fundamentals published before each rebalance date."""
from __future__ import annotations

import logging
import math
from datetime import date
from statistics import fmean, pstdev

from . import config, dividends, fundamentals as fnd, report, storage
from .engine import analyze
from .fmt import pct, table
from .returns import net_tbill

log = logging.getLogger(__name__)


def month_starts(start: date, end: date) -> list[date]:
    out, y, m = [], start.year, start.month
    while date(y, m, 1) <= end:
        if date(y, m, 1) >= start:
            out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _basket(tickers: list[str], a: date, b: date) -> float | None:
    rets = [r for r in (dividends.total_return(t, a, b) for t in tickers) if r is not None]
    return fmean(rets) if rets else None


def _turnover(old: list[str], new: list[str]) -> float:
    """Fraction of the book traded (sold plus bought) when rebalancing equal weights from old to new."""
    w_old = {t: 1 / len(old) for t in old} if old else {}
    w_new = {t: 1 / len(new) for t in new} if new else {}
    return sum(abs(w_new.get(t, 0.0) - w_old.get(t, 0.0)) for t in set(w_old) | set(w_new))


def stats(monthly: list[float]) -> dict:
    if not monthly:
        return {"cagr": None, "vol": None, "max_dd": None, "total": None}
    wealth, peak, dd, curve = 1.0, 1.0, 0.0, []
    for r in monthly:
        wealth *= 1 + r
        peak = max(peak, wealth)
        dd = min(dd, wealth / peak - 1)
        curve.append(wealth)
    years = len(monthly) / 12
    return {"cagr": wealth ** (1 / years) - 1 if wealth > 0 else -1.0, "vol": pstdev(monthly) * math.sqrt(12),
            "max_dd": dd, "total": wealth - 1, "curve": curve}


def first_date() -> date | None:
    """First month where at least two companies have three published annual periods."""
    pubs = []
    for t, comp in fnd.load().items():
        ann = [p.published for p in comp["periods"] if p.type == "annual"]
        if len(ann) >= 3:
            pubs.append(sorted(ann)[2])
    if len(pubs) < 2:
        return None
    d = sorted(pubs)[1]
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def backtest(top: int = 3, end: date | None = None) -> dict:
    end = end or date.today()
    start = first_date()
    if start is None or start >= end:
        return {"months": [], "reason": "fewer than two companies have three published annual periods"}
    cost = config.macro()["taxes_and_costs"]["trade_cost_per_side"]
    tickers = [u["ticker"] for u in config.universe()]
    cash = net_tbill() / 12
    dates = month_starts(start, end)
    months, prev_top, prev_pick = [], [], []
    for a, b in zip(dates, dates[1:] + ([end] if dates[-1] < end else [])):
        if (b - a).days < 20:
            continue
        res = analyze(a, point_in_time=True, check_liquidity=False, check_suspension=False)
        valued = [t for t in res["ranking"] if res["rows"][t]["fair_value"]]
        top_n = valued[:top]
        picks = res["picks"][:top]
        bench = _basket(tickers, a, b)
        r_top = _basket(top_n, a, b)
        r_pick = _basket(picks, a, b) if picks else cash
        if bench is None or r_top is None:
            continue
        r_top -= cost * _turnover(prev_top, top_n)
        if picks:
            r_pick -= cost * _turnover(prev_pick, picks)
        elif prev_pick:
            r_pick -= cost * _turnover(prev_pick, [])
        months.append({"date": a.isoformat(), "end": b.isoformat(), "top": top_n, "picks": picks, "valued": len(valued),
                       "r_top": r_top, "r_pick": r_pick, "r_bench": bench})
        prev_top, prev_pick = top_n, picks
        log.info("%s top=%s picks=%s top=%.3f bench=%.3f", a, top_n, picks, r_top, bench)
    out = {"top": top, "months": months}
    for k in ("r_top", "r_pick", "r_bench"):
        out[k] = stats([m[k] for m in months])
    if months:
        out["hit_rate"] = sum(m["r_top"] > m["r_bench"] for m in months) / len(months)
        out["pick_months"] = sum(bool(m["picks"]) for m in months)
    return out


def render(bt: dict) -> str:
    out = ["# Walk-forward backtest", "", report.DISCLAIMER_LINE, ""]
    if not bt["months"]:
        out.append(f"No backtest yet: {bt.get('reason', 'not enough history')}.")
        return "\n".join(out) + "\n"
    ms = bt["months"]
    out += [
        f"Monthly rebalance from {ms[0]['date']} to {ms[-1]['end']} ({len(ms)} months). At each date the engine "
        "only sees annual results published on or before that date.", "",
        table(["Strategy", "CAGR", "Volatility", "Max drawdown", "Total return"], [
            [f"Top {bt['top']} by composite rank", pct(bt["r_top"]["cagr"]), pct(bt["r_top"]["vol"]),
             pct(bt["r_top"]["max_dd"]), pct(bt["r_top"]["total"])],
            [f"Undervalued picks only (cash at net T-bill otherwise)", pct(bt["r_pick"]["cagr"]),
             pct(bt["r_pick"]["vol"]), pct(bt["r_pick"]["max_dd"]), pct(bt["r_pick"]["total"])],
            ["Equal-weight universe", pct(bt["r_bench"]["cagr"]), pct(bt["r_bench"]["vol"]),
             pct(bt["r_bench"]["max_dd"]), pct(bt["r_bench"]["total"])],
        ]), "",
        f"- Months the top {bt['top']} beat the universe: **{pct(bt['hit_rate'])}**.",
        f"- Months with at least one undervalued pick: **{bt['pick_months']} of {len(ms)}**.", "",
        "## Limitations", "",
        "- Returns adjust for sourced bonus issues and splits and add sourced dividends net of withholding tax, "
        "without reinvestment. Dividends missing from `data/dividends.yaml` understate high-yield names.",
        "- The universe is today's coverage list, so delisted and failed counters are missing (survivorship bias).",
        "- Macro inputs (bond yield, risk premiums) are today's values, not the values known at each date.",
        "- Liquidity and suspension screens are off because historical volume and suspension data are not stored.",
        "- Trading costs use the current per-side rate on names that change at each rebalance.",
        "- Short samples and a small universe make these numbers noisy. Treat them as a sanity check.", "",
        "## Holdings by month", "",
        table(["Month", "Valued", f"Top {bt['top']}", "Picks", "Top return", "Picks return", "Universe"],
              [[m["date"], str(m["valued"]), ", ".join(m["top"]), ", ".join(m["picks"]) or "cash",
                pct(m["r_top"]), pct(m["r_pick"]), pct(m["r_bench"])] for m in reversed(ms)]),
    ]
    return "\n".join(out) + "\n"


def run_backtest(top: int = 3) -> str:
    bt = backtest(top)
    path = config.REPORTS / "backtest.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(bt), encoding="utf-8", newline="\n")
    slim = {k: v for k, v in bt.items() if k != "months"}
    for k in ("r_top", "r_pick", "r_bench"):
        if k in slim:
            slim[k] = {kk: vv for kk, vv in slim[k].items() if kk != "curve"}
    storage.write_json(config.DATA / "backtest.json", {**slim, "months": bt["months"]})
    report.build_site()
    if not bt["months"]:
        return f"backtest skipped: {bt.get('reason')}"
    return (f"backtest={path.relative_to(config.ROOT).as_posix()} months={len(bt['months'])} "
            f"top_cagr={pct(bt['r_top']['cagr'])} picks_cagr={pct(bt['r_pick']['cagr'])} "
            f"universe_cagr={pct(bt['r_bench']['cagr'])} hit_rate={pct(bt['hit_rate'])}")
