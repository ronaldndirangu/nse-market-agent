"""Weekly pipeline: refresh data, analyze, write the report and site, and log picks."""
from __future__ import annotations

import logging

from . import announcements, config, market, picks_log, portfolio, report
from .engine import analyze
from .fmt import pct

log = logging.getLogger(__name__)


def run_weekly(fetch: bool = True) -> str:
    if fetch:
        for name, step in (("companies", market.refresh_companies), ("daily", market.update_daily),
                           ("announcements", announcements.update)):
            try:
                step()
            except Exception as exc:  # a failed source must not stop the report
                log.warning("%s refresh failed: %s", name, exc)
    from . import prices
    prices.clear_cache()
    result = analyze()
    held = portfolio.review(result)
    path = report.write(result, portfolio.render(held) or None)
    logged = picks_log.log(result)
    report.build_site()
    lines = [f"report={path.relative_to(config.ROOT).as_posix()} valued={len(result['rows'])} "
             f"picks={len(result['picks'])} buys={len(result['buys'])} logged={logged}"]
    for t in result["ranking"]:
        r = result["rows"][t]
        pr = r["projection"]
        rng = f"{pct(pr['bear'])}/{pct(pr['base'])}/{pct(pr['bull'])}" if pr else "n/a"
        flag = "BUY" if r["buy"] else "PICK" if r["undervalued"] else "WATCH" if r["watch"] else "-"
        lines.append(f"{r['rank']:>2} {t:<5} {flag:<5} price={r['price']:.2f} mos={pct(r['mos'])} "
                     f"returns={rng} gate={r['quality']['gate']} conf={r['confidence']}")
    return "\n".join(lines)
