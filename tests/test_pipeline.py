import math
from datetime import date, timedelta

import pytest
import yaml

from nse_agent import DISCLAIMER, config, portfolio, report, storage
from nse_agent.engine import analyze

AS_OF = date(2026, 11, 6)
BANKS = {"EQTY": (45.0, 1.0), "KCB": (40.0, 0.8), "ABSA": (18.0, 1.2)}


def _sessions(n):
    d, out = AS_OF, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return out[::-1]


def _bank_periods(scale):
    periods = []
    for i, year in enumerate((2022, 2023, 2024)):
        equity = 200_000 * scale * (1 + 0.1 * i)
        income = 0.22 * equity
        periods.append({
            "period": f"FY{year}", "period_end": f"{year}-12-31", "published": f"{year + 1}-03-20",
            "type": "annual", "source_url": "https://example.test/results.pdf",
            "values": {
                "net_income": income, "total_equity": equity, "total_assets": equity * 7,
                "total_liabilities": equity * (6 - 0.05 * i), "shares_outstanding": 3_000,
                "eps": income / 3_000, "dps": income / 3_000 * 0.4, "operating_cash_flow": income * 1.3,
                "revenue": income * 3 * (1 + 0.05 * i), "npl_ratio": 0.12 - 0.005 * i,
            },
        })
    return periods


@pytest.fixture
def market(root):
    data = root / "data"
    fund = data / "fundamentals.yaml"
    fund.write_text(yaml.safe_dump({"companies": {t: {"periods": _bank_periods(1 + 0.2 * k)}
                                                  for k, t in enumerate(BANKS)}}), encoding="utf-8")
    days = _sessions(500)
    for k, (t, (price, beta)) in enumerate(BANKS.items()):
        storage.upsert_prices(t, [
            (d, price * (1 + 0.0004 * i) * (1 + 0.01 * beta * math.sin(i / 5 + k)), 2_000_000.0)
            for i, d in enumerate(days)])
    yield
    fund.unlink(missing_ok=True)
    for t in BANKS:
        storage.price_path(t).unlink(missing_ok=True)


def test_analyze_render_and_review(market):
    result = analyze(AS_OF)
    assert set(result["rows"]) == set(BANKS)
    assert sorted(r["rank"] for r in result["rows"].values()) == [1, 2, 3]
    for r in result["rows"].values():
        assert r["fair_value"] and r["projection"]
        assert r["projection"]["bear"] <= r["projection"]["base"] <= r["projection"]["bull"]
        assert r["quality"]["gate"] in {"pass", "fail", "unknown"}
        assert r["confidence"] in {"High", "Medium", "Low"}
    assert any("SCOM: no price history" == g for g in result["gaps"])

    holdings = [{"ticker": "EQTY", "shares": 1000, "cost": 40}, {"ticker": "SCOM", "shares": 500}]
    items = portfolio.review(result, holdings)
    actions = {i["ticker"]: i for i in items}
    assert actions["EQTY"]["action"] in {"Sell", "Trim", "Add", "Hold"}
    assert actions["SCOM"]["reasons"] == ["not covered by the valuation (no sourced fundamentals or prices)"]

    text = report.render(result, portfolio.render(items))
    assert text.startswith(f"# NSE value report: {AS_OF.isoformat()}")
    assert DISCLAIMER.split(".")[0] in text
    for heading in ("## Ranked results", "## Portfolio review", "## Data gaps", "## Method"):
        assert heading in text
    assert "\u2014" not in text and "\u2013" not in text


def test_point_in_time_hides_unpublished_results(market):
    result = analyze(date(2025, 3, 1), point_in_time=True, check_liquidity=False)
    assert set(result["rows"]) == set(BANKS)
    for r in result["rows"].values():
        assert r["latest_period"] == "FY2023"

def test_weekly_changes_report_added_and_dropped_lists():
    from nse_agent.pipeline import weekly_changes

    result = {"buys": ["KCB"], "picks": ["KCB", "NCBA"]}
    assert weekly_changes(result, None) == ["First weekly report: 1 Buy, 2 undervalued."]
    assert weekly_changes({"buys": [], "picks": []}, None) == []
    assert weekly_changes(result, {"buys": ["KCB"], "picks": ["KCB", "NCBA"]}) == []
    assert weekly_changes(result, {"buys": [], "picks": ["KCB", "EQTY"]}) == [
        "New Buy: KCB.", "New undervalued: NCBA.", "No longer undervalued: EQTY."]


def test_previous_lists_seed_from_picks_log_then_use_saved_state():
    from nse_agent import picks_log, pipeline

    log, state = picks_log.path(), pipeline.state_path()
    log.write_text("date,ticker,buy\n2026-10-30,KCB,yes\n2026-10-30,NCBA,no\n2026-10-23,EQTY,no\n"
                   "2026-11-06,ABSA,no\n", encoding="utf-8")
    try:
        assert pipeline.previous_lists("2026-11-06") == {"buys": ["KCB"], "picks": ["KCB", "NCBA"]}
        assert pipeline.previous_lists("2026-10-23") is None
        storage.write_json(state, {"as_of": "2026-11-06", "buys": [], "picks": ["ABSA"]})
        assert pipeline.previous_lists("2026-11-13")["picks"] == ["ABSA"]
    finally:
        log.unlink(missing_ok=True)
        state.unlink(missing_ok=True)
