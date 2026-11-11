"""Score logged picks against the equal-weight universe and NASI."""
from __future__ import annotations

from datetime import date
from statistics import fmean

from . import config, picks_log, prices, report, storage
from .fmt import kes, pct, table


def _close_on_or_before(series: list[tuple[str, float]], day: str) -> float | None:
    vals = [v for d, v in series if d <= day]
    return vals[-1] if vals else None


def _universe_return(start: str, end: date) -> float | None:
    rets = []
    for t in (u["ticker"] for u in config.universe()):
        a = prices.last_close(t, date.fromisoformat(start))
        b = prices.last_close(t, end)
        if a and b and a[1] > 0:
            rets.append(b[1] / a[1] - 1)
    return fmean(rets) if rets else None


def score(today: date | None = None) -> dict:
    today = today or date.today()
    nasi = storage.read_series(storage.nasi_path())
    rows = []
    for p in picks_log.read():
        t, start = p["ticker"], p["date"]
        lc = prices.last_close(t, today)
        if not lc:
            continue
        entry = float(p["price"])
        ret = lc[1] / entry - 1
        uni = _universe_return(start, today)
        n0, n1 = _close_on_or_before(nasi, start), _close_on_or_before(nasi, today.isoformat())
        nasi_ret = n1 / n0 - 1 if n0 and n1 and nasi[0][0] <= start else None
        rows.append({
            "date": start, "ticker": t, "entry": entry, "now": lc[1], "return": ret, "universe": uni,
            "nasi": nasi_ret, "excess": ret - uni if uni is not None else None,
            "hit_fair": lc[1] >= float(p["fair_base"]) if p["fair_base"] else None,
            "days": (today - date.fromisoformat(start)).days,
        })
    excess = [r["excess"] for r in rows if r["excess"] is not None and r["days"] >= 28]
    return {
        "as_of": today.isoformat(), "rows": rows,
        "mature": len(excess), "hit_rate": sum(e > 0 for e in excess) / len(excess) if excess else None,
        "avg_excess": fmean(excess) if excess else None,
    }


def render(s: dict) -> str:
    out = [f"# Pick scorecard ({s['as_of']})", "", report.DISCLAIMER_LINE, ""]
    if not s["rows"]:
        out.append("No picks have been logged yet. The weekly report logs every undervalued pick to `data/picks.csv`.")
        return "\n".join(out) + "\n"
    out += [
        f"Picks at least 4 weeks old: **{s['mature']}**. "
        f"Hit rate against the equal-weight universe: **{pct(s['hit_rate'])}**. "
        f"Average excess return: **{pct(s['avg_excess'])}**.", "",
        "Returns are price-only (dividends excluded). NASI is shown only where the index series covers the pick date.", "",
    ]
    rows = [[r["date"], r["ticker"], kes(r["entry"]), kes(r["now"]), pct(r["return"]), pct(r["universe"]),
             pct(r["nasi"]), pct(r["excess"]), "yes" if r["hit_fair"] else "no", str(r["days"])]
            for r in sorted(s["rows"], key=lambda x: (x["date"], x["ticker"]), reverse=True)]
    out.append(table(["Picked", "Ticker", "Entry", "Now", "Return", "Universe", "NASI", "Excess", "At fair value",
                      "Days"], rows))
    return "\n".join(out) + "\n"


def run_score() -> str:
    s = score()
    path = config.REPORTS / "scorecard.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(s), encoding="utf-8", newline="\n")
    report.build_site()
    return f"scorecard={path.relative_to(config.ROOT).as_posix()} picks={len(s['rows'])} mature={s['mature']} " \
           f"hit_rate={pct(s['hit_rate'])} avg_excess={pct(s['avg_excess'])}"
