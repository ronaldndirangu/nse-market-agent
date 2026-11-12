"""Weekly pipeline: refresh data, analyze, write the report and site, and log picks."""
from __future__ import annotations

import logging

from . import announcements, config, health, market, official, picks_log, portfolio, report, storage
from .engine import analyze
from .fmt import estimate_reliable, pct

log = logging.getLogger(__name__)


def state_path():
    return config.DATA / "weekly_state.json"


def previous_lists(as_of: str) -> dict | None:
    """Last weekly Buy and undervalued lists, seeded from the picks log before the first saved state."""
    state = storage.read_json(state_path(), None)
    if state is not None:
        return state
    earlier = [r for r in picks_log.read() if r["date"] < as_of]
    if not earlier:
        return None
    last = max(r["date"] for r in earlier)
    rows = [r for r in earlier if r["date"] == last]
    return {"buys": [r["ticker"] for r in rows if r["buy"] == "yes"], "picks": [r["ticker"] for r in rows]}


def weekly_changes(result: dict, previous: dict | None) -> list[str]:
    """Buy and undervalued lists added or removed since the last weekly run."""
    now = {"buys": set(result["buys"]), "picks": set(result["picks"])}
    if previous is None:
        return [f"First weekly report: {len(now['buys'])} Buy, {len(now['picks'])} undervalued."] if now["picks"] else []
    lines = []
    for key, label in (("buys", "Buy"), ("picks", "undervalued")):
        before = set(previous.get(key, []))
        if added := sorted(now[key] - before):
            lines.append(f"New {label}: {', '.join(added)}.")
        if dropped := sorted(before - now[key]):
            lines.append(f"No longer {label}: {', '.join(dropped)}.")
    return lines


def run_weekly(fetch: bool = True, alert_file: str | None = None) -> str:
    if fetch:
        official.refresh()
        for name, step in (("companies", market.refresh_companies), ("daily", market.update_daily),
                           ("announcements", announcements.update)):
            try:
                step()
            except Exception as exc:  # a failed source must not stop the report
                log.warning("%s refresh failed: %s", name, exc)
    from . import prices
    prices.clear_cache()
    result = analyze(health.now().date(), health=health.assess())
    held = portfolio.review(result)
    path = report.write(result, portfolio.render(held) or None)
    logged = picks_log.log(result)
    report.build_site()
    changes = weekly_changes(result, previous_lists(result["as_of"]))
    storage.write_json(state_path(), {"as_of": result["as_of"], "buys": sorted(result["buys"]),
                                      "picks": sorted(result["picks"])})
    if alert_file and changes:
        with open(alert_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(f"- {c}" for c in changes) + "\n")
    lines = [f"report={path.relative_to(config.ROOT).as_posix()} valued={len(result['rows'])} "
             f"picks={len(result['picks'])} buys={len(result['buys'])} logged={logged} changes={len(changes)}"]
    for t in result["ranking"]:
        r = result["rows"][t]
        pr = r["projection"]
        rng = f"{pct(pr['bear'])}/{pct(pr['base'])}/{pct(pr['bull'])}" if pr and estimate_reliable(r) else "unclear"
        mos = pct(r["mos"]) if estimate_reliable(r) else "unclear"
        flag = "BUY" if r["buy"] else "PICK" if r["undervalued"] else "WATCH" if r["watch"] else "-"
        lines.append(f"{r['rank']:>2} {t:<5} {flag:<5} price={r['price']:.2f} mos={mos} "
                     f"returns={rng} gate={r['quality']['gate']} conf={r['confidence']}")
    return "\n".join(lines)
