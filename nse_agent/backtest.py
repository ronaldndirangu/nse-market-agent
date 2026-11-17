"""Monthly walk-forward backtest that only uses fundamentals and T-bill rates published before each rebalance date.

Every strategy and benchmark runs through the same accounting (strategy.Book): it starts in cash, pays the per-side
trading cost on the weight it actually trades, and lets weights drift between rebalances.
"""
from __future__ import annotations

import logging
import math
from datetime import date
from statistics import fmean, pstdev

from . import config, dividends, fundamentals as fnd, prices, rates, report, shadow, storage, strategy
from .engine import analyze
from .fmt import kes, pct, points, table
from .returns import net_tbill

log = logging.getLogger(__name__)

STRATEGIES = {
    "buy_rule": "Buy rule (T-bills when there is no Buy)",
    "top": "Top 3 by research score",
    "cap": "Covered stocks, weighted by company size",
    "equal": "Covered stocks, equal weights",
}
AMOUNTS = (100_000, 250_000, 500_000, 1_000_000, 2_000_000, 5_000_000)


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


def _price_return(t: str, a: date, b: date) -> float | None:
    x, y = dividends.adj_close(t, a), dividends.adj_close(t, b)
    return y[1] / x[1] - 1 if x and y and x[1] > 0 else None


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


def illustrative_amount(weights: dict[str, float], as_of: date) -> int:
    """Smallest round amount whose whole-share purchases at these weights leave under 1% uninvested."""
    for amount in AMOUNTS:
        spent, every = 0.0, True
        for t, w in weights.items():
            lc = prices.last_close(t, as_of)
            n = math.floor(amount * w / lc[1]) if lc and lc[1] > 0 else 0
            every = every and n > 0
            spent += n * lc[1] if n else 0.0
        if every and spent >= 0.99 * amount:
            return amount
    return AMOUNTS[-1]


def backtest(top: int = 3, end: date | None = None, dated_rates: bool = True) -> dict:
    end = end or date.today()
    start = first_date()
    if start is None or start >= end:
        return {"months": [], "reason": "fewer than two companies have three published annual periods"}
    s = config.settings()
    costs = config.macro()["taxes_and_costs"]
    cost, stress = costs["trade_cost_per_side"], costs["small_trade_cost_per_side"]
    tickers = [u["ticker"] for u in config.universe()]
    nasi = storage.read_series(storage.nasi_path())
    mixes = {f"mix_{round(e * 100)}": e for e in s["experiments"]["mixes"]}
    books = {k: strategy.Book() for k in (*STRATEGIES, *strategy.EXPERIMENTS, *mixes)}
    price_only = strategy.Book()
    months, prev_hold, backfilled = [], [], set()
    dates = month_starts(start, end)
    for a, b in zip(dates, dates[1:] + ([end] if dates[-1] < end else [])):
        if (b - a).days < 20:
            continue
        macro = rates.macro_at(a) if dated_rates else None
        res = analyze(a, point_in_time=True, check_liquidity=False, check_suspension=False, macro=macro)
        rets = {t: dividends.total_return(t, a, b) for t in tickers}
        ok = {t for t, r in rets.items() if r is not None}
        valued = [t for t in res["ranking"] if res["rows"][t]["fair_value"] and t in ok]
        core, bf = strategy.cap_weights(sorted(ok), a)
        if len(ok) < 2 or not valued or not core:
            continue
        backfilled.update(bf)
        cash = rates.cash_return(res["macro"]) if dated_rates else net_tbill() / 12
        quarterly = books["tilt_quarterly"]
        exp_targets, signals, prev_hold = strategy.experiments(
            res, a, core, ok, prev_hold, quarterly.drifted(ok) if quarterly.gross else None)
        targets = {"buy_rule": strategy.buy_rule(res, ok, top), "top": strategy.equal(valued[:top]),
                   "cap": core, "equal": strategy.equal(sorted(ok)), **exp_targets,
                   **{k: {t: w * e for t, w in core.items()} for k, e in mixes.items()}}
        gross = {k: book.step(targets[k], rets, cash) for k, book in books.items()}
        price_only.step(core, {t: _price_return(t, a, b) or 0.0 for t in core}, 0.0)
        bill = res["macro"]["risk_free"]["tbill_364d"]
        months.append({
            "date": a.isoformat(), "end": b.isoformat(), "valued": len(valued), "top": valued[:top],
            "buys": [t for t in res["buys"] if t in ok][:top],
            "undervalued_below_hurdle": [t for t in res["picks"] if t not in res["buys"]],
            "cash_rate": cash * 12, "hurdle": res["hurdle"], "tbill_364d": bill["value"],
            "rate_month": bill.get("as_of"), "carried_months": bill.get("carried_months", 0),
            "nasi": storage.series_return(nasi, a, b), "signals": signals, "gross": gross,
            "net": {k: (1 - cost * book.turnover[-1]) * (1 + gross[k]) - 1 for k, book in books.items()},
            "largest": sorted(core, key=core.get, reverse=True)[:3],
        })
        log.info("%s buys=%s cap=%.3f buy_rule=%.3f", a, months[-1]["buys"], gross["cap"], gross["buy_rule"])
    if not months:
        return {"months": [], "reason": "no month had prices for at least two covered stocks"}
    years = len(months) / 12
    out = {"top": top, "months": months, "dated_rates": dated_rates, "cost": cost, "stress_cost": stress,
           "start": months[0]["date"], "end": months[-1]["end"], "backfilled_shares": sorted(backfilled)}
    out["strategies"] = {k: {"net": stats(books[k].net(cost)), "gross": stats(books[k].gross),
                             "turnover": sum(books[k].turnover) / years}
                         for k in (*STRATEGIES, *strategy.EXPERIMENTS)}
    nasi_rets = [m["nasi"] for m in months]
    out["nasi"] = stats(nasi_rets) if all(r is not None for r in nasi_rets) else None
    out["check"] = _benchmark_check(price_only.gross, nasi_rets, s["benchmark_check"])
    cap_net, cap_stress = books["cap"].net(cost), books["cap"].net(stress)
    live = shadow.score()
    out["experiments"] = {}
    for k in strategy.EXPERIMENTS:
        net, net_stress = books[k].net(cost), books[k].net(stress)
        out["experiments"][k] = strategy.gate(
            [e - c for e, c in zip(net, cap_net)], [e - c for e, c in zip(net_stress, cap_stress)],
            sum(m["signals"][k] for m in months), live.get(k)) | {"label": strategy.EXPERIMENTS[k]}
    out["live"] = live
    out["live_first"] = next(iter(shadow.logged()), None)
    buy_net = books["buy_rule"].net(cost)
    g = s["experiments"]["gate"]
    ci = strategy.block_ci([e - c for e, c in zip(buy_net, cap_net)], g["block_months"], g["resamples"],
                           g["confidence"], s["simulation"]["seed"])
    held = [i for i, m in enumerate(months) if m["buys"]]
    out["buy_rule"] = {
        "excess": fmean(e - c for e, c in zip(buy_net, cap_net)) * 12,
        "ci": [ci[0] * 12, ci[1] * 12] if ci else None,
        "months": len(held),
        "gross_in_buy_months": fmean(books["buy_rule"].gross[i] for i in held) if held else None,
        "net_in_buy_months": fmean(buy_net[i] for i in held) if held else None,
        "cap_gross_in_buy_months": fmean(books["cap"].gross[i] for i in held) if held else None,
        "hurdle_months": sum(bool(m["undervalued_below_hurdle"]) for m in months),
    }
    latest, _ = strategy.cap_weights(tickers, end)
    amount = illustrative_amount(latest, end)
    out["mixes"] = {"amount": amount, "rows": []}
    for k, e in mixes.items():
        st = stats(books[k].net(cost))
        out["mixes"]["rows"].append({"key": k, "equity": e, "label": f"{e:.0%} stocks, {1 - e:.0%} T-bills",
                                     "cagr": st["cagr"], "max_dd": st["max_dd"], "final": amount * (1 + st["total"]),
                                     "curve": [round(amount * v) for v in st["curve"]]})
    cash_rates = [(m["cash_rate"], m["date"]) for m in months]
    out["rates"] = {"low": min(cash_rates), "high": max(cash_rates),
                    "carried": [m["date"] for m in months if m["carried_months"]]}
    out["headline"] = headline(out)
    return out


def _benchmark_check(price_only: list[float], nasi: list[float | None], limits: dict) -> dict | None:
    pairs = [(p, n) for p, n in zip(price_only, nasi) if n is not None]
    if len(pairs) < 12:
        return None
    ours, theirs = stats([p for p, _ in pairs]), stats([n for _, n in pairs])
    gap = ours["cagr"] - theirs["cagr"]
    te = pstdev([p - n for p, n in pairs]) * math.sqrt(12)
    return {"ours": ours["cagr"], "nasi": theirs["cagr"], "gap": gap, "tracking_error": te,
            "passed": abs(gap) <= limits["max_cagr_gap"] and te <= limits["max_tracking_error"],
            "limits": limits}


def headline(bt: dict) -> str:
    st, ci = bt["strategies"], bt["buy_rule"]["ci"]
    verdict = ("beat" if ci and ci[0] > 0 else "trailed" if ci and ci[1] < 0 else "did not clearly beat or trail")
    return (f"The Buy rule {verdict} the covered stocks weighted by company size: "
            f"{pct(st['buy_rule']['net']['cagr'])} a year against {pct(st['cap']['net']['cagr'])} after trading "
            f"costs, with a worst fall of {pct(st['buy_rule']['net']['max_dd'])} against "
            f"{pct(st['cap']['net']['max_dd'])}. The 95% range for the yearly difference is "
            + (f"{points(ci[0])} to {points(ci[1])}." if ci else "not available."))


def render(bt: dict) -> str:
    out = ["# Walk-forward backtest", "", report.DISCLAIMER_LINE, ""]
    if not bt["months"]:
        out.append(f"No backtest yet: {bt.get('reason', 'not enough history')}.")
        return "\n".join(out) + "\n"
    ms, st, br = bt["months"], bt["strategies"], bt["buy_rule"]
    gate = config.settings()["experiments"]["gate"]
    rate_text = ("the CBK T-bill rates published before each month start (the Buy hurdle uses the 364-day rate; "
                 "cash earns the 91-day rate after 15% tax)" if bt["dated_rates"] else "today's T-bill rate")

    def row(label: str, s: dict) -> list[str]:
        return [label, pct(s["net"]["cagr"]), pct(s["gross"]["cagr"]), pct(s["net"]["vol"]),
                pct(s["net"]["max_dd"]), f"{s['turnover']:.2f}x"]

    rows = [row(label, st[k]) for k, label in STRATEGIES.items()]
    if bt["nasi"]:
        n = bt["nasi"]
        rows.append(["NASI, all listed shares (price only, no dividends or costs)", pct(n["cagr"]), pct(n["cagr"]),
                     pct(n["vol"]), pct(n["max_dd"]), "n/a"])
    bills = next(r for r in bt["mixes"]["rows"] if r["equity"] == 0)
    rows.append(["91-day T-bills after tax", pct(bills["cagr"]), pct(bills["cagr"]), "n/a", pct(bills["max_dd"]),
                 "0.00x"])
    out += [
        f"Monthly rebalance from {bt['start']} to {bt['end']} ({len(ms)} months). At each date the engine only sees "
        f"annual results published by then and {rate_text}.", "",
        "## Result", "", f"**{headline(bt)}**", "",
        table(["Strategy", "Return a year after costs", "Before costs", "Volatility", "Worst fall",
               "Turnover a year"], rows), "",
        f"- Every strategy starts in cash and pays {pct(bt['cost'], 2)} per side on the weight it trades, including "
        "the first purchase and monthly rebalancing. Dividends stay invested until the next rebalance.",
        f"- The Buy rule held stocks in **{br['months']} of {len(ms)}** months. In those months it earned "
        f"{pct(br['gross_in_buy_months'], 2)} a month before costs and {pct(br['net_in_buy_months'], 2)} after, "
        f"against {pct(br['cap_gross_in_buy_months'], 2)} for the size-weighted basket.",
        (f"- In **{br['hurdle_months']}** months at least one stock passed the valuation checks but not the T-bill "
         "hurdle, so the Buy rule did not buy it." if br["hurdle_months"] else
         "- The T-bill hurdle never blocked a stock that passed the valuation checks, even when 364-day bills paid "
         f"{pct(max(m['tbill_364d'] for m in ms))}." if bt["dated_rates"] else "- The T-bill hurdle never blocked a stock that passed the valuation checks."), "",
    ]
    c = bt["check"]
    if c:
        out += ["## Benchmark check", "",
                f"The size-weighted covered basket, price only, returned {pct(c['ours'])} a year against "
                f"{pct(c['nasi'])} for NASI: a gap of {points(c['gap'])} and a tracking error of "
                f"{pct(c['tracking_error'])}. **{'Passed' if c['passed'] else 'Failed'}** (limits: "
                f"{pct(c['limits']['max_cagr_gap'])} gap, {pct(c['limits']['max_tracking_error'])} tracking error). "
                "A close match means the 16 covered stocks stand in reasonably for the whole market.", ""]
    mx = bt["mixes"]
    out += ["## What a fixed mix would have become", "",
            f"{kes(mx['amount'], 0)} invested on {bt['start']} in the size-weighted covered basket and 91-day "
            f"T-bills, rebalanced monthly after costs. {kes(mx['amount'], 0)} is the smallest round amount that "
            "buys whole shares of every covered stock at today's weights with under 1% left over.", "",
            table(["Mix", f"Value on {bt['end']}", "Return a year", "Worst fall"],
                  [[r["label"], kes(r["final"], 0), pct(r["cagr"]), pct(r["max_dd"])] for r in mx["rows"]]), "",
            "These illustrate fixed rules and are the same for every reader. They are not a recommended mix.", ""]
    out += ["## Shadow experiments", "",
            "Each rule below is frozen and compared with the size-weighted basket. None changes a published verdict. "
            "A rule goes to human review only when all four checks pass: the 95% range of its yearly gain over the "
            f"basket is above zero, its signal changed the portfolio in at least {gate['min_signal_months']} months, "
            f"it still gains at {pct(bt['stress_cost'], 2)} per side, and it has at least "
            f"{gate['min_live_months']} months of positive live results.", "",
            table(["Experiment", "Return a year", "Gain over basket", "95% range", "Signal months",
                   f"Gain at {pct(bt['stress_cost'], 2)}", "Live months", "Status"],
                  [[strategy.EXPERIMENTS[k], pct(st[k]["net"]["cagr"]), points(e["excess"]),
                    f"{points(e['ci'][0])} to {points(e['ci'][1])}" if e["ci"] else "n/a", str(e["signal_months"]),
                    points(e["stress_excess"]), str(e["live_months"]), e["status"]]
                   for k, e in bt["experiments"].items()]), "",
            "Both halves of this history have already been seen, so a split-half result could only veto a rule. "
            "The live shadow log is the only untouched test: "
            + (f"it began in {bt['live_first']}." if bt.get("live_first") else
               "it starts with the first verified daily brief after this change."), ""]
    rt = bt["rates"]
    cash_line = (f"- Cash earned between {pct(rt['low'][0])} ({rt['low'][1]}) and {pct(rt['high'][0])} "
                 f"({rt['high'][1]}) a year after tax. Each month uses the previous month's CBK figure"
                 + (f"; {len(rt['carried'])} month(s) carried an older figure forward." if rt["carried"] else ".")
                 if bt["dated_rates"] else "- Every month uses today's T-bill rate.")
    share_line = ("- Size weights use full market value from published share counts, not free float, so "
                  "majority-owned companies weigh more than an index fund could hold.")
    if bt["backfilled_shares"]:
        share_line += (f" Share counts for {', '.join(bt['backfilled_shares'])} were backfilled from their earliest "
                       "sourced filing for months before it, rebased for bonus issues and splits.")
    out += ["## Limitations", "", cash_line,
            "- The 10-year bond yield, risk premiums and taxes are today's values, so valuations stay provisional "
            "until dated versions are sourced.",
            "- The universe is today's 16 covered stocks, so delisted and failed counters are missing "
            "(survivorship bias). The NASI check above bounds the effect on the size-weighted basket.",
            share_line,
            *([f"- {fnd.timing_note()}"] if fnd.timing_note() else []),
            "- Liquidity and suspension screens are off because historical volume and suspension data are not stored.",
            "- Small trades can cost more than the base rate, and whole-share rounding is ignored after the start.",
            f"- {len(ms)} months of one market make every figure noisy. Treat them as a sanity check, not a forecast.",
            "", "## Holdings by month", "",
            table(["Month", "Buys", "Buy rule", "Size-weighted", "Equal", "NASI", "Cash rate", "Hurdle"],
                  [[m["date"], ", ".join(m["buys"]) or "cash", pct(m["net"]["buy_rule"]), pct(m["net"]["cap"]),
                    pct(m["net"]["equal"]), pct(m["nasi"]), pct(m["cash_rate"], 2), pct(m["hurdle"], 2)]
                   for m in reversed(ms)])]
    return "\n".join(out) + "\n"


def _slim(bt: dict) -> dict:
    """JSON without strategy curves; the site rebuilds them from the monthly net returns."""
    out = dict(bt)
    if "strategies" in out:
        out["strategies"] = {k: {kind: ({kk: vv for kk, vv in v.items() if kk != "curve"}
                                        if isinstance(v, dict) else v) for kind, v in s.items()}
                             for k, s in out["strategies"].items()}
    if out.get("nasi"):
        out["nasi"] = {k: v for k, v in out["nasi"].items() if k != "curve"}
    return out


def run_backtest(top: int = 3, fetch: bool = True) -> str:
    if fetch:
        log.info("CBK monthly T-bill history: %s", rates.refresh())
    bt = backtest(top)
    path = config.REPORTS / "backtest.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(bt), encoding="utf-8", newline="\n")
    storage.write_json(config.DATA / "backtest.json", _slim(bt))
    report.build_site()
    if not bt["months"]:
        return f"backtest skipped: {bt.get('reason')}"
    st = bt["strategies"]
    return (f"backtest={path.relative_to(config.ROOT).as_posix()} months={len(bt['months'])} "
            f"buy_rule={pct(st['buy_rule']['net']['cagr'])} cap={pct(st['cap']['net']['cagr'])} "
            f"equal={pct(st['equal']['net']['cagr'])} buy_months={bt['buy_rule']['months']}")
