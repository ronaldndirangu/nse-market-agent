"""Retrospective: forward scorecard, per-signal rank IC and reverse attribution of the actual winners.

Everything is point in time: rankings come from the live ledger or from `reconstruct`, which reruns the engine on
each month start using only fundamentals published by then. Forward returns are total returns (split-adjusted
price plus dividends net of withholding tax, no reinvestment).
"""
from __future__ import annotations

import calendar
from datetime import date
from statistics import fmean

from . import config, dividends, fundamentals as fnd, ledger, prices, report, storage
from .backtest import month_starts
from .engine import analyze
from .fmt import pct, table
from .returns import SIGNALS, zscores

HORIZONS = (1, 3, 6, 12)
ATTR_HORIZONS = (3, 6, 12)
TOP = 5
START = date(2016, 12, 1)
EVENT_MOVE = 0.25
MACRO_SHARE = 0.7
MACRO_MOVE = 0.10
PRICE_SIGNALS = ("momentum", "dividend_yield", "low_volatility")
CLASSES = ("event", "missing data", "turnaround", "macro", "signal miss")


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def avg_ranks(values: list[float]) -> list[float]:
    """1-based ranks with ties sharing their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(xs: list[float | None], ys: list[float | None]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    rx, ry = avg_ranks([p[0] for p in pairs]), avg_ranks([p[1] for p in pairs])
    mx, my = fmean(rx), fmean(ry)
    vx, vy = sum((a - mx) ** 2 for a in rx), sum((b - my) ** 2 for b in ry)
    if not vx or not vy:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (vx * vy) ** 0.5


def band(row: dict, months: int) -> tuple[float, float] | None:
    """Annual bear/bull projections compounded to the horizon."""
    bear, bull = row.get("bear"), row.get("bull")
    if bear is None or bull is None or bear <= -1 or bull <= -1:
        return None
    h = months / 12
    return (1 + bear) ** h - 1, (1 + bull) ** h - 1


def _tickers() -> list[str]:
    return [u["ticker"] for u in config.universe()]


def data_end() -> date:
    last = [prices.last_close(t) for t in _tickers()]
    return max(date.fromisoformat(lc[0]) for lc in last if lc)


_RET: dict[tuple[str, date, date], float | None] = {}


def fwd(t: str, a: date, b: date) -> float | None:
    key = (t, a, b)
    if key not in _RET:
        _RET[key] = dividends.total_return(t, a, b)
    return _RET[key]


def _nasi_return(series: list[tuple[str, float]], a: date, b: date) -> float | None:
    if not series or series[0][0] > a.isoformat():
        return None
    v0 = [v for d, v in series if d <= a.isoformat()]
    v1 = [v for d, v in series if d <= b.isoformat()]
    return v1[-1] / v0[-1] - 1 if v0 and v1 and v0[-1] > 0 else None


def _mean(vals) -> float | None:
    vals = [v for v in vals if v is not None]
    return fmean(vals) if vals else None


# Reconstruction -------------------------------------------------------------------------------------------------

def reconstruct(end: date | None = None, start: date = START) -> int:
    """Rerun the engine point in time on every month start and overwrite the reconstructed ledger."""
    end = end or date.today()
    results = []
    for d in month_starts(start, end):
        res = analyze(d, point_in_time=True, check_liquidity=False, check_suspension=False)
        if res["ranking"]:
            results.append(res)
    return ledger.write_reconstructed(results)


# Forward scorecard ----------------------------------------------------------------------------------------------

def scorecard(snaps: dict[str, dict[str, dict]], end: date, nasi: list[tuple[str, float]]) -> dict:
    out = {}
    universe = _tickers()
    for h in HORIZONS:
        windows, inside, below, total = [], 0, 0, 0
        for day, snap in snaps.items():
            a = date.fromisoformat(day)
            b = add_months(a, h)
            if b > end:
                continue
            uni = _mean(fwd(t, a, b) for t in universe)
            ranked = sorted(snap.values(), key=lambda r: r["rank"])
            top = [(r["ticker"], fwd(r["ticker"], a, b)) for r in ranked]
            top = [(t, v) for t, v in top if v is not None][:TOP]
            if not top or uni is None:
                continue
            top_ret = fmean(v for _, v in top)
            ic = spearman([r["composite"] for r in ranked], [fwd(r["ticker"], a, b) for r in ranked])
            for r in ranked:
                bnd, v = band(r, h), fwd(r["ticker"], a, b)
                if bnd and v is not None:
                    total += 1
                    inside += bnd[0] <= v <= bnd[1]
                    below += v < bnd[0]
            windows.append({"start": day, "end": b.isoformat(), "top": [t for t, _ in top], "top_return": top_ret,
                            "universe": uni, "nasi": _nasi_return(nasi, a, b), "excess": top_ret - uni,
                            "hit_rate": sum(v > uni for _, v in top) / len(top), "ic": ic})
        out[h] = {
            "windows": len(windows),
            "top_return": _mean(w["top_return"] for w in windows),
            "universe": _mean(w["universe"] for w in windows),
            "nasi": _mean(w["nasi"] for w in windows),
            "excess": _mean(w["excess"] for w in windows),
            "hit_rate": _mean(w["hit_rate"] for w in windows),
            "ic": _mean(w["ic"] for w in windows),
            "calibration": inside / total if total else None,
            "below_bear": below / total if total else None,
            "above_bull": (total - inside - below) / total if total else None,
            "calibration_n": total,
            "detail": windows,
        }
    return out


# Signals --------------------------------------------------------------------------------------------------------

def price_panel(day: date) -> dict[str, dict[str, float | None]]:
    """Price and dividend signals for every ticker on `day`: these exist for the whole price history."""
    out: dict[str, dict[str, float | None]] = {s: {} for s in PRICE_SIGNALS}
    for t in _tickers():
        lc = prices.last_close(t, day)
        if not lc:
            continue
        vol = prices.volatility(t, day)
        annual = dividends.comparable(t, fnd.annuals(t, day)[-1:], day)
        dps = annual[-1].get("dps") if annual else None
        out["momentum"][t] = prices.momentum(t, day)
        out["low_volatility"][t] = -vol if vol is not None else None
        out["dividend_yield"][t] = dividends.trailing_yield(t, day, lc[1], dps)
    return out


def signal_ic(months: list[date], end: date, recon: dict[str, dict[str, dict]]) -> dict:
    """Mean monthly Spearman IC of each signal against forward total return, per horizon."""
    panels = {d: price_panel(d) for d in months}
    out: dict[str, dict] = {}
    for s in list(SIGNALS) + ["composite"]:
        source = "prices" if s in PRICE_SIGNALS else "reconstructed ledger"
        out[s] = {"source": source}
        for h in HORIZONS:
            ics = []
            for d in months:
                b = add_months(d, h)
                if b > end:
                    continue
                if s in PRICE_SIGNALS:
                    vals = panels[d][s]
                else:
                    snap = recon.get(d.isoformat(), {})
                    col = "composite" if s == "composite" else f"{s}_value"
                    vals = {t: r.get(col) for t, r in snap.items()}
                ts = list(vals)
                ic = spearman([vals[t] for t in ts], [fwd(t, d, b) for t in ts])
                if ic is not None:
                    ics.append(ic)
            out[s][h] = {"ic": _mean(ics), "positive": sum(i > 0 for i in ics) / len(ics) if ics else None,
                         "n": len(ics)}
    return {"table": out, "panels": panels}


# Reverse attribution --------------------------------------------------------------------------------------------

def _event(t: str, a: date, b: date) -> str | None:
    for ex, k in dividends._actions().get(t, []):
        if a < ex <= b:
            return f"corporate action {ex.isoformat()} (factor {k:g})"
    rows = [r for r in prices.rows(t, b) if r[0] > a.isoformat()]
    before = prices.last_close(t, a)
    prev = before[1] if before else None
    for d, c, _ in rows:
        if prev and abs(c / prev - 1) > EVENT_MOVE:
            return f"one-day move {c / prev - 1:+.0%} on {d}"
        prev = c
    return None


def _turnaround(t: str, a: date) -> bool:
    eps = [p.get("eps") for p in fnd.annuals(t, a)[-2:]]
    return any(e is not None and e <= 0 for e in eps)


def _macro(rets: dict[str, float]) -> bool:
    vals = list(rets.values())
    if not vals:
        return False
    up = sum(v > MACRO_MOVE for v in vals) / len(vals)
    down = sum(v < -MACRO_MOVE for v in vals) / len(vals)
    return max(up, down) > MACRO_SHARE


def classify(t: str, a: date, b: date, snap: dict[str, dict], rets: dict[str, float]) -> tuple[str, str]:
    """Why the engine missed a winner, checked in a fixed order."""
    ev = _event(t, a, b)
    if ev:
        return "event", ev
    if t not in snap:
        return "missing data", "no point-in-time fundamentals" if prices.last_close(t, a) else "no price history"
    if _turnaround(t, a):
        return "turnaround", "loss in one of the last two annual results"
    if _macro(rets):
        return "macro", "over 70% of the universe moved more than 10% the same way"
    return "signal miss", "ranked outside the top 5 on available signals"


def attribution(months: list[date], end: date, recon: dict[str, dict[str, dict]], panels: dict) -> dict:
    out: dict[int, dict] = {}
    for h in ATTR_HORIZONS:
        rows, counts = [], {c: 0 for c in ("caught",) + CLASSES}
        flagged = {s: 0 for s in SIGNALS}
        seen = {s: 0 for s in SIGNALS}
        for a in months:
            b = add_months(a, h)
            if b > end:
                continue
            rets = {t: v for t in _tickers() if (v := fwd(t, a, b)) is not None}
            if len(rets) < TOP:
                continue
            snap = recon.get(a.isoformat(), {})
            pz = {s: zscores(panels[a][s]) for s in PRICE_SIGNALS}
            for t in sorted(rets, key=rets.get, reverse=True)[:TOP]:
                r = snap.get(t)
                sigs = []
                for s in SIGNALS:
                    z = pz[s].get(t) if s in PRICE_SIGNALS else (r or {}).get(f"{s}_z")
                    seen[s] += z is not None
                    if z is not None and z > 0:
                        sigs.append(s)
                        flagged[s] += 1
                if r and r["rank"] <= TOP:
                    cls, why = "caught", f"ranked {r['rank']} of {len(snap)}"
                else:
                    cls, why = classify(t, a, b, snap, rets)
                counts[cls] += 1
                rows.append({"start": a.isoformat(), "end": b.isoformat(), "ticker": t, "return": rets[t],
                             "rank": r["rank"] if r else None, "ranked": len(snap), "signals": sigs,
                             "class": cls, "why": why})
        n = len(rows)
        out[h] = {"winners": n, "counts": counts,
                  "flag_rate": {s: (flagged[s] / seen[s] if seen[s] else None) for s in SIGNALS},
                  "flag_n": seen, "rows": rows}
    return out


# Report ---------------------------------------------------------------------------------------------------------

def _ic_cell(c: dict) -> str:
    if c["ic"] is None:
        return "n/a"
    return f"{c['ic']:+.3f} ({pct(c['positive'], 0)} > 0, n={c['n']})"


def _scorecard_table(sc: dict) -> str:
    rows = []
    for h in HORIZONS:
        c = sc[h]
        cal = (f"{pct(c['calibration'], 0)} ({pct(c['below_bear'], 0)} below, {pct(c['above_bull'], 0)} above, "
               f"n={c['calibration_n']})" if c["calibration"] is not None else "n/a")
        ic = f"{c['ic']:+.3f}" if c["ic"] is not None else "n/a"
        rows.append([f"{h}m", c["windows"], pct(c["top_return"]), pct(c["universe"]), pct(c["nasi"]),
                     pct(c["excess"]), pct(c["hit_rate"], 0), ic, cal])
    return table(["Horizon", "Windows", "Top 5", "Universe (EW)", "NASI", "Excess", "Hit rate", "Rank IC",
                  "Inside bear-bull"], rows)


def render(res: dict) -> str:
    live, recon, ics, attr = res["live"], res["reconstructed"], res["ic"], res["attribution"]
    lines = [
        "# Retrospective", "", report.DISCLAIMER_LINE, "",
        f"Generated {res['generated']}. Prices through {res['data_end']}. Reconstructed rankings cover "
        f"{res['recon_dates']} month starts (first {res['recon_first'] or 'n/a'}); the live ledger covers "
        f"{res['live_dates']} days (first {res['live_first'] or 'n/a'}).", "",
        "## Forward scorecard", "",
        "Each ranking date, the top 5 by composite score is held for 1, 3, 6 and 12 months and compared with the "
        "equal-weight universe and NASI on total return. Hit rate is the share of top-5 picks that beat the "
        "equal-weight universe. Rank IC is the Spearman correlation between composite score and forward return "
        "across all ranked stocks. Inside bear-bull is the share of outcomes inside the projected range "
        "(target about 80%).", "",
        "### Live ledger (daily)", "",
    ]
    if any(live[h]["windows"] for h in HORIZONS):
        lines += [_scorecard_table(live), ""]
    else:
        due = add_months(date.fromisoformat(res["live_first"]), 1).isoformat() if res["live_first"] else "n/a"
        lines += [f"No live window has matured yet. The first 1-month results are due on {due}.", ""]
    lines += ["### Reconstructed (monthly, point in time)", "", _scorecard_table(recon), "",
              "## Per-signal rank IC", "",
              "Mean monthly Spearman IC between each signal and the forward total return, with the share of months "
              "where IC was positive. Price signals use the full price history; valuation and quality signals need "
              "point-in-time fundamentals, so they cover fewer months.", ""]
    lines += [table(["Signal", "Source"] + [f"{h}m" for h in HORIZONS],
                    [[s, c["source"]] + [_ic_cell(c[h]) for h in HORIZONS] for s, c in ics.items()]), ""]
    lines += ["## Reverse attribution", "",
              "Each month start, the 5 best actual total returns over the next 3, 6 and 12 months, against the rank "
              "the point-in-time engine gave them. Misses are classified in order: event (corporate action or a "
              "one-day move over 25%), missing data, turnaround (a recent loss), macro (over 70% of the universe "
              "moved more than 10% the same way), then signal miss.", "",
              "### Miss classification", ""]
    lines += [table(["Horizon", "Winners", "Caught (top 5)"] + [c.capitalize() for c in CLASSES],
                    [[f"{h}m", a["winners"], a["counts"]["caught"]] + [a["counts"][c] for c in CLASSES]
                     for h, a in attr.items()]), ""]
    lines += ["### Signals that flagged the winners", "",
              "Share of actual winners with a positive z-score on each signal at the start date, among winners where "
              "the signal could be computed (n). About 50% is no better than chance.", ""]
    lines += [table(["Signal"] + [f"{h}m" for h in ATTR_HORIZONS],
                    [[s] + [f"{pct(attr[h]['flag_rate'][s], 0)} (n={attr[h]['flag_n'][s]})" for h in ATTR_HORIZONS]
                     for s in SIGNALS]), ""]
    lines += ["### Latest winners", ""]
    for h in ATTR_HORIZONS:
        starts = sorted({r["start"] for r in attr[h]["rows"]})[-3:]
        recent = [r for r in attr[h]["rows"] if r["start"] in starts]
        if not recent:
            continue
        lines += [f"**{h}-month windows**", "",
                  table(["Start", "Ticker", "Return", "Rank given", "Signals flagged", "Class", "Why"],
                        [[r["start"], r["ticker"], pct(r["return"]),
                          f"{r['rank']} of {r['ranked']}" if r["rank"] else "unranked",
                          ", ".join(r["signals"]) or "none", r["class"], r["why"]] for r in recent]), ""]
    lines += ["## Limitations", "",
              "- Fundamentals are point in time, but sourced history is short until the backfill lands, so early "
              "months rank few stocks and most early misses are missing data.",
              "- Total return adds dividends net of withholding tax without reinvestment and ignores trading costs. "
              "Prices are adjusted only for corporate actions recorded in data/corporate_actions.yaml.",
              "- The universe is today's 16 counters, so delisted stocks are missing (survivorship bias).",
              "- Calibration scales annual bear and bull projections to each horizon. The bands are valuation "
              "ranges, not price-volatility ranges, so they understate short-term dispersion; the below and above "
              "shares show which way outcomes missed. Read the 12-month figure first.",
              "- Daily live windows overlap, so their statistics are not independent observations.",
              "- With 16 stocks, one month's IC is noisy. Judge signals on the share of positive months and N.", ""]
    return "\n".join(lines)


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def compute(end: date | None = None) -> dict:
    _RET.clear()
    end = end or data_end()
    nasi = storage.read_series(storage.nasi_path())
    live = ledger.by_date(ledger.read("live"))
    recon = ledger.by_date(ledger.read("reconstructed"))
    months = month_starts(START, end)
    ics = signal_ic(months, end, recon)
    return {
        "generated": date.today().isoformat(),
        "data_end": end.isoformat(),
        "live_dates": len(live), "live_first": next(iter(live), None),
        "recon_dates": len(recon), "recon_first": next(iter(recon), None),
        "live": scorecard(live, end, nasi),
        "reconstructed": scorecard(recon, end, nasi),
        "ic": ics["table"],
        "attribution": attribution(months, end, recon, ics["panels"]),
    }


def run_retro(rebuild: bool = True) -> str:
    if rebuild:
        reconstruct()
    res = compute()
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    (config.REPORTS / "retrospective.md").write_text(render(res), encoding="utf-8", newline="\n")
    storage.write_json(config.DATA / "retrospective.json", _jsonable(res))
    report.build_site()
    ic12 = res["ic"]["composite"][12]["ic"]
    a12 = res["attribution"][12]
    return (f"reconstructed_dates={res['recon_dates']} live_dates={res['live_dates']} "
            f"composite_ic_12m={'n/a' if ic12 is None else f'{ic12:+.3f}'} "
            f"winners_12m={a12['winners']} caught_12m={a12['counts']['caught']}")
