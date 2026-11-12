from datetime import datetime
from copy import deepcopy

import pytest

from nse_agent import announcements, config, health, ledger, storage
from nse_agent.engine import analyze
from tests.test_pipeline import AS_OF, BANKS, market  # noqa: F401


@pytest.fixture
def live(market, monkeypatch):
    stocks = [s for s in config.universe() if s["ticker"] in BANKS]
    monkeypatch.setattr(config, "universe", lambda: stocks)
    macro = config.macro() | {"as_of": AS_OF.isoformat()}
    monkeypatch.setattr(config, "macro", lambda as_of=None: macro)
    storage.write_json(storage.market_path("listing.json"), {
        "trade_date": AS_OF.isoformat(), "intraday": False, "source": "nse",
        "rows": {t: {"volume": 1000, "suspended": None} for t in BANKS},
    })
    storage.write_json(announcements.path(), {"updated": AS_OF.isoformat(),
                                            "items": [{"title": "Results", "url": "https://example.test/results.pdf"}]})
    yield datetime(2026, 11, 6, 17, tzinfo=health.EAT)
    for path in (storage.market_path("listing.json"), storage.market_path("health.json"), announcements.path()):
        path.unlink(missing_ok=True)


def test_session_health_handles_weekends_and_ambiguous_holidays(live):
    friday = health.assess(live)
    assert friday["critical_ok"] and friday["ledger_ready"]
    assert friday["prices"]["current"] == 3
    weekend = health.assess(live.replace(day=8))
    assert weekend["prices"]["status"] == "Current"
    assert weekend["expected_session"] == "2026-11-06"
    assert weekend["next_update_due"].startswith("2026-11-09T17:00:00+03:00")
    delayed = health.assess(live.replace(day=10))
    assert delayed["prices"]["status"] == "Delayed" and not delayed["ledger_ready"]
    assert health.assess(live.replace(day=12))["prices"]["status"] == "Stale"
    storage.write_json(announcements.path(), {"updated": "2026-11-09", "items": [{"title": "Monday release"}]})
    assert health.assess(live.replace(day=9, hour=10))["announcements"]["status"] == "Current"


def test_one_missing_ticker_cannot_hide_behind_the_latest_price(live):
    path = storage.market_path("listing.json")
    listing = storage.read_json(path, {})
    del listing["rows"]["KCB"]
    storage.write_json(path, listing)
    assessed = health.assess(live)
    assert assessed["prices"]["current"] == 2 and not assessed["ledger_ready"]
    result = analyze(AS_OF, health=assessed)
    assert ledger.append(result) == 0
    assert all(not row["conviction"]["flag"] for row in result["rows"].values())


def test_live_evidence_holds_flags_without_changing_valuation_or_backtest(live):
    original = analyze(AS_OF, point_in_time=True, check_liquidity=False, check_suspension=False)
    assessed = health.assess(live)
    assessed["critical_ok"] = False
    assessed["issues"] = ["Announcements: stale"]
    assessed["announcements"]["status"] = "Stale"
    live_result = analyze(AS_OF, point_in_time=True, check_liquidity=False, check_suspension=False, health=assessed)
    for ticker, row in original["rows"].items():
        revised = live_result["rows"][ticker]
        assert (row["tier"], row["risk"]["level"], row["projection"]) == (
            revised["tier"], revised["risk"]["level"], revised["projection"])
        assert not revised["conviction"]["flag"]
        assert revised["conviction"]["held_back"]
    again = analyze(AS_OF, point_in_time=True, check_liquidity=False, check_suspension=False)
    assert ledger.rows_for(original) == ledger.rows_for(again)


def test_empty_announcements_do_not_refresh_the_success_date(live, monkeypatch):
    before = announcements.path().read_bytes()
    monkeypatch.setattr(announcements.nse, "fetch_announcements", lambda: [])
    with pytest.raises(ValueError, match="no documents"):
        announcements.update(AS_OF)
    assert announcements.path().read_bytes() == before
    assert health.assess(live)["announcements"]["status"] == "Delayed"
    assert storage.read_json(storage.market_path("health.json"), {})["announcements"]["successful"] is False


@pytest.mark.parametrize("curated,bill", [("2026-10-01", "2026-11-05"), ("2026-11-06", "2026-10-01")])
def test_fresh_bill_and_curated_dates_cannot_mask_each_other(live, monkeypatch, curated, bill):
    macro = deepcopy(config.macro())
    macro["as_of"] = curated
    macro["risk_free"]["tbill_364d"]["as_of"] = bill
    monkeypatch.setattr(config, "macro", lambda as_of=None: macro)
    result = health.assess(live)
    assert not result["critical_ok"] and result["macro"]["status"] != "Current"


def test_optional_cpi_failure_does_not_invalidate_current_critical_data(live):
    storage.write_json(storage.market_path("health.json"), {"official": {"knbs": {"successful": False}}})
    assert health.assess(live)["critical_ok"]


def test_pending_results_uses_main_announcements_and_known_periods(live):
    notice = {"ticker": "KCB", "results": True, "status": "queued", "date": "2026-11-06",
              "first_seen": "2026-11-06", "url": "https://example.test/interim.pdf",
              "title": "Unaudited results for 30 June 2026"}
    storage.write_json(announcements.path(), {"updated": "2026-11-06", "items": [notice]})
    assessed = health.assess(live)
    assert assessed["tickers"]["KCB"]["pending_results"]
    assert any("human review" in issue for issue in health.evidence(assessed, "KCB"))
    notice["title"] = "Annual results FY2025"
    storage.write_json(announcements.path(), {"updated": "2026-11-06", "items": [notice]})
    assert not health.assess(live)["tickers"]["KCB"]["pending_results"]
