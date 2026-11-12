"""MCP server exposing the deterministic engine as tools. Install with `pip install -e .[mcp]`."""
from __future__ import annotations

import json
import time
from dataclasses import asdict

from . import DISCLAIMER, announcements, fundamentals as fnd

CACHE_SECONDS = 900
_cache: dict = {}


def _plain(obj):
    return json.loads(json.dumps(obj, default=str))


def _analysis():
    """Recompute at most every CACHE_SECONDS so a long-lived server picks up new prices and results."""
    if _cache and time.monotonic() - _cache["at"] < CACHE_SECONDS:
        return _cache["res"]
    from . import dividends, prices
    from .engine import analyze
    prices.clear_cache()
    dividends.clear_cache()
    fnd._load.cache_clear()
    _cache.update(at=time.monotonic(), res=analyze())
    return _cache["res"]


def screen_stocks() -> dict:
    res = _analysis()
    rows = res["rows"]
    out = []
    for t in res["ranking"]:
        r = rows[t]
        out.append({k: r[k] for k in ("rank", "ticker", "name", "sector", "price", "price_date", "fair_value", "mos",
                                      "agree", "agree_needed", "undervalued", "buy", "confidence", "composite",
                                      "screen_fail", "projection")}
                   | {"quality_gate": r["quality"]["gate"], "risk": r.get("risk"), "conviction": r.get("conviction")})
    unranked = [t for t in rows if t not in res["ranking"]]
    return _plain({"as_of": res["as_of"], "tbill_net": res["tbill_net"], "hurdle": res["hurdle"], "ranked": out,
                   "unranked": unranked, "picks": res["picks"], "buys": res["buys"],
                   "high_confidence": res.get("high_confidence", []), "gaps": res["gaps"],
                   "disclaimer": DISCLAIMER})


def run_valuation(ticker: str) -> dict:
    res = _analysis()
    row = res["rows"].get(ticker.upper())
    if row is None:
        return {"error": f"{ticker} is not valued", "gaps": [g for g in res["gaps"] if g.startswith(ticker.upper())]}
    return _plain(row | {"disclaimer": DISCLAIMER})


def get_fundamentals(ticker: str) -> dict:
    _analysis()
    comp = fnd.load().get(ticker.upper())
    if not comp:
        return {"error": f"no sourced fundamentals for {ticker}"}
    return _plain({"meta": comp["meta"], "periods": [asdict(p) for p in comp["periods"]]})


def get_announcements(ticker: str, limit: int = 20) -> list[dict]:
    return [i for i in announcements.items() if i.get("ticker") == ticker.upper()][:limit]


def serve() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("The MCP server needs the optional dependency: pip install -e .[mcp]") from exc
    app = FastMCP("nse-market-agent")
    for fn in (screen_stocks, run_valuation, get_fundamentals, get_announcements):
        app.tool()(fn)
    app.run()
