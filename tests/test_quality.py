from datetime import date

import pytest

from nse_agent import quality
from nse_agent.fundamentals import Period
from tests.helpers import period

GOOD = dict(net_income=120, total_assets=1000, operating_cash_flow=150, long_term_debt=100, current_assets=400,
            current_liabilities=200, gross_profit=500, revenue=1100, shares_outstanding=100)
PREV = dict(net_income=100, total_assets=1000, operating_cash_flow=110, long_term_debt=150, current_assets=380,
            current_liabilities=210, gross_profit=450, revenue=1000, shares_outstanding=100)


def test_piotroski_all_signals_pass():
    f = quality.piotroski([period(year=2023, **PREV), period(year=2024, **GOOD)], bank=False)
    assert f["available"] == 9 and f["passed"] == 9 and f["score"] == 1.0


def test_piotroski_needs_two_periods_and_four_signals():
    assert quality.piotroski([period(**GOOD)], bank=False) is None
    assert quality.piotroski([period(year=2023, eps=1), period(year=2024, eps=2)], bank=False) is None


def test_piotroski_bank_uses_total_liabilities():
    prev = dict(net_income=10, total_assets=100, total_liabilities=90, shares_outstanding=10, revenue=20)
    cur = dict(net_income=12, total_assets=110, total_liabilities=95, shares_outstanding=10, revenue=23)
    f = quality.piotroski([period(year=2023, **prev), period(year=2024, **cur)], bank=True)
    assert "leverage_falling" in f["signals"] and "gross_margin_improving" not in f["signals"]


def test_piotroski_bank_signals_from_sourced_bank_fields():
    prev = dict(net_income=10, total_assets=100, total_equity=12, shares_outstanding=10, cost_to_income=0.50,
                core_capital_ratio=0.16)
    cur = dict(net_income=12, total_assets=110, total_equity=14, shares_outstanding=10, cost_to_income=0.45,
               core_capital_ratio=0.15)
    f = quality.piotroski([period(year=2023, **prev), period(year=2024, **cur)], bank=True)
    assert f["signals"] == {"roa_positive": True, "roa_improving": True, "leverage_falling": True,
                            "cost_to_income_improving": True, "capital_ratio_improving": False,
                            "no_dilution": True}


def test_altman_z2():
    p = period(current_assets=400, current_liabilities=200, retained_earnings=300, ebit=150, total_equity=500,
               total_liabilities=500, total_assets=1000)
    assert quality.altman_z2([p]) == pytest.approx(6.56 * 0.2 + 3.26 * 0.3 + 6.72 * 0.15 + 1.05 * 1.0)
    assert quality.altman_z2([period(total_assets=1000)]) is None


def test_npl_trend_states():
    ok = quality.npl_trend([period(year=2023, npl_ratio=0.10), period(year=2024, npl_ratio=0.09)])
    rising = quality.npl_trend([period(year=2023, npl_ratio=0.10), period(year=2024, npl_ratio=0.11)])
    jump = quality.npl_trend([period(year=2023, npl_ratio=0.10), period(year=2024, npl_ratio=0.14)])
    assert (ok["status"], rising["status"], jump["status"]) == ("ok", "rising", "fail")
    assert quality.npl_trend([period(eps=1)]) is None


def test_npl_trend_ignores_interim_older_than_latest_annual():
    annuals = [period(year=2023, npl_ratio=0.10), period(year=2024, npl_ratio=0.09)]
    stale = Period(ticker="TEST", period="H1 2024", period_end=date(2024, 6, 30), published=date(2024, 8, 30),
                   type="interim", source_url="https://example.test/h1.pdf", values={"npl_ratio": 0.20})
    fresh = Period(ticker="TEST", period="H1 2025", period_end=date(2025, 6, 30), published=date(2025, 8, 30),
                   type="interim", source_url="https://example.test/h1.pdf", values={"npl_ratio": 0.095})
    old = quality.npl_trend(annuals, stale)
    assert (old["latest"], old["status"]) == (0.09, "ok") and old["series"][-1][0] == "FY2024"
    new = quality.npl_trend(annuals, fresh)
    assert (new["latest"], new["status"]) == (0.095, "rising") and new["series"][-1][0] == "H1 2025"


def test_warnings_for_matches_name_keyword_and_window():
    anns = [
        {"title": "KCB Group Plc profit warning", "date": "2026-10-01"},
        {"title": "Safaricom profit warning", "date": "2026-10-01"},
        {"title": "KCB Group dividend notice", "date": "2026-10-01"},
        {"title": "KCB Group cautionary announcement", "date": "2025-01-01"},
    ]
    hits = quality.warnings_for("KCB", ["KCB Group"], anns, date(2026, 11, 11))
    assert [h["title"] for h in hits] == ["KCB Group Plc profit warning"]


def test_assess_gate():
    periods = [period(year=2023, **PREV), period(year=2024, **GOOD)]
    ok = quality.assess(periods, bank=False, interim=None, warnings=[])
    assert ok["gate"] == "pass" and ok["score"] == 1.0
    warned = quality.assess(periods, bank=False, interim=None, warnings=[{"title": "profit warning"}])
    assert warned["gate"] == "fail" and warned["score"] == 0.5
    assert quality.assess([period(eps=1)], bank=False, interim=None, warnings=[])["gate"] == "unknown"
