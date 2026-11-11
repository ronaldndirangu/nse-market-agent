"""Core analysis: screen, value, quality-check, project and rank the universe as of a date."""
from __future__ import annotations

from datetime import date

from . import announcements as ann, config, dividends, fundamentals as fnd, prices, storage
from .quality import assess, warnings_for
from .returns import net_tbill, project, rank
from .valuation import (agreeing, cost_of_equity, fair_value, graham_number, models, required_agreement,
                        sector_multiples, sustainable_growth)


def analyze(as_of: date | None = None, point_in_time: bool = False, check_liquidity: bool = True,
            check_suspension: bool = True) -> dict:
    """point_in_time=True only uses fundamentals published on or before as_of (backtests)."""
    as_of = as_of or date.today()
    s = config.settings()
    uni = config.universe()
    tickers = [u["ticker"] for u in uni]
    listing = storage.read_json(storage.market_path("listing.json"), {}) or {}
    companies = storage.read_json(storage.market_path("companies.json"), {}) or {}
    anns = ann.items()
    index = prices.equal_weight_index_returns(tickers, as_of)
    pit = as_of if point_in_time else None

    rows: dict[str, dict] = {}
    gaps: list[str] = []
    for u in uni:
        t = u["ticker"]
        periods = fnd.annuals(t, pit)
        lc = prices.last_close(t, as_of)
        if not lc:
            gaps.append(f"{t}: no price history")
            continue
        price_date, price = lc
        if not periods:
            gaps.append(f"{t}: no sourced annual fundamentals")
            continue
        b = prices.beta(t, index, as_of, s["valuation"]["beta_weeks"])
        ke = cost_of_equity(b)
        g, avg_roe = sustainable_growth(periods, ke)
        last = periods[-1]
        eps, bvps = last.get("eps"), last.get("bvps")
        rows[t] = {
            "ticker": t, "name": u["name"], "sector": u["sector"], "bank": bool(u.get("bank")),
            "price": price, "price_date": price_date, "beta": b, "ke": ke, "g": g, "roe": avg_roe,
            "eps": eps, "bvps": bvps, "dps": last.get("dps"), "latest_period": last.period,
            "periods": len(periods), "source_url": last.source_url,
            "pe": price / eps if eps and eps > 0 else None,
            "pb": price / bvps if bvps and bvps > 0 else None,
            "_periods": periods, "_aliases": u.get("aliases", []),
        }

    multiples = sector_multiples(rows, s["valuation"]["min_sector_peers"])
    hurdle = net_tbill() + s["buy"]["hurdle_premium_over_tbill"]
    for t, r in rows.items():
        periods = r.pop("_periods")
        aliases = r.pop("_aliases")
        vals = models(periods, r["bank"], r["ke"], r["g"], r["roe"], multiples[t]["pe"], multiples[t]["pb"])
        r["models"] = vals
        r["graham"] = graham_number(periods)
        r["fair_value"] = fair_value(vals)
        r["mos"] = r["fair_value"]["base"] / r["price"] - 1 if r["fair_value"] else None
        r["agree"] = agreeing(vals, r["price"], s["valuation"]["mos_threshold"])
        r["agree_needed"] = required_agreement(len(vals))
        r["momentum"] = prices.momentum(t, as_of)
        r["volatility"] = prices.volatility(t, as_of)
        r["dividend_yield"] = dividends.trailing_yield(t, as_of, r["price"], r["dps"])
        interim = fnd.latest_interim(t, pit)
        warns = warnings_for(t, aliases, anns, as_of)
        r["quality"] = assess(periods, r["bank"], interim, warns)
        r["projection"] = project(r["price"], r["dps"], r["fair_value"], r["g"]) if r["fair_value"] else None

        reasons = []
        stale = (as_of - date.fromisoformat(r["price_date"])).days > s["screen"]["max_price_age_days"]
        if stale:
            reasons.append(f"price is stale ({r['price_date']})")
        if check_suspension and listing.get("rows", {}).get(t, {}).get("suspended"):
            reasons.append("suspended")
        if check_liquidity:
            turnover, n = prices.avg_turnover(t, as_of)
            if n < 20 and companies.get(t, {}).get("avg_session_turnover"):
                turnover = companies[t]["avg_session_turnover"]
            r["avg_turnover"] = turnover
            if turnover is None:
                reasons.append("no turnover data")
            elif turnover < s["screen"]["min_avg_daily_turnover_kes"]:
                reasons.append(f"illiquid (avg turnover KES {turnover:,.0f})")
        if r["periods"] < s["screen"]["min_annual_periods"]:
            reasons.append(f"only {r['periods']} annual periods sourced")
        if not r["eps"] or r["eps"] <= 0:
            reasons.append("latest EPS not positive")
        r["screen_fail"] = reasons
        r["stale"] = stale

        valued = len(r["agree"]) >= r["agree_needed"] and len(vals) >= 2
        r["undervalued"] = valued and not reasons and r["quality"]["gate"] == "pass"
        r["watch"] = valued and not r["undervalued"]
        base = r["projection"]["base"] if r["projection"] else None
        r["buy"] = r["undervalued"] and base is not None and base > hurdle
        _tier(r, vals, valued, reasons, base, hurdle, s["valuation"]["mos_threshold"])
        qs = r["quality"]["score"]
        if len(r["agree"]) >= 3 and qs is not None and qs >= 0.67 and not stale:
            r["confidence"] = "High"
        elif len(r["agree"]) <= 2 or qs is None or qs < 0.5 or stale:
            r["confidence"] = "Low"
        else:
            r["confidence"] = "Medium"

    ranked = rank(rows) if rows else []
    for i, t in enumerate(ranked, 1):
        rows[t]["rank"] = i
    return {
        "as_of": as_of.isoformat(),
        "rows": rows,
        "ranking": ranked,
        "picks": [t for t in ranked if rows[t]["undervalued"]],
        "buys": [t for t in ranked if rows[t]["buy"]],
        "watchlist": [t for t in ranked if rows[t]["watch"]],
        "gaps": gaps,
        "tbill_net": net_tbill(),
        "hurdle": hurdle,
        "ke_at_beta_1": cost_of_equity(1.0),
    }


def _tier(r: dict, vals: dict, valued: bool, screen: list[str], base: float | None, hurdle: float,
          mos_threshold: float) -> None:
    """Buy clears every gate. Watch passes quality and misses exactly one other threshold. Otherwise Avoid."""
    gate = r["quality"]["gate"]
    blockers: list[str] = []
    if gate == "fail":
        blockers.append("quality gate failed (" + "; ".join(r["quality"]["fails"][:2]) + ")")
    elif gate == "unknown":
        blockers.append("quality unknown (no Piotroski, Altman or NPL data)")
    blockers += screen
    if len(vals) < 2:
        blockers.append(f"only {len(vals)} valuation model(s) available, needs 2")
    elif not valued:
        blockers.append(f"margin of safety under {mos_threshold:.0%} "
                        f"({len(r['agree'])} of {len(vals)} models agree, needs {r['agree_needed']})")
    if base is not None and base <= hurdle:
        blockers.append(f"base return {base:.1%} does not beat the {hurdle:.2%} hurdle")
    r["blockers"] = blockers
    if r["buy"]:
        r["tier"], r["binding"] = "Buy", "Clears every gate."
    elif gate == "pass" and len(blockers) == 1:
        r["tier"], r["binding"] = "Watch", f"Not a Buy: {blockers[0]}."
    else:
        r["tier"] = "Avoid"
        more = f" (+{len(blockers) - 2} more)" if len(blockers) > 2 else ""
        r["binding"] = "Avoid: " + "; ".join(blockers[:2]) + more + "."
