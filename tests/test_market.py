import json

import pytest

from nse_agent import config, market, storage
from nse_agent.sources import afx, nse

AFTER_CLOSE = "2026-11-12T13:14:10+00:00"
INTRADAY = "2026-11-12T08:30:00+00:00"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "PRICES_DIR", tmp_path / "prices")
    return tmp_path


def _afx(as_of, rows=None, nasi=240.0):
    rows = rows if rows is not None else [
        afx.ListingRow("AAA", "Alpha", 1000.0, 10.0, 0.0, False),
        afx.ListingRow("BBB", "Beta", None, 20.0, 0.0, False),
        afx.ListingRow("CCC", "Gamma", 50.0, 30.0, 0.0, True),
    ]
    return lambda: afx.Listing(rows=rows, nasi=nasi, as_of=as_of)


def _nse(status="closed"):
    rows = {t: {"price": p, "volume": 5.0, "turnover": p * 5} for t, p in (("AAA", 11.0), ("BBB", 21.0), ("CCC", 31.0))}
    return lambda: ("2026-11-12", rows, status)


def _closes(ticker):
    return [(r["date"], r["close"], r["volume"]) for r in storage.read_prices(ticker)]


def test_afx_close_records_prices_and_nasi(data_dir, monkeypatch):
    monkeypatch.setattr(afx, "fetch_listing", _afx(AFTER_CLOSE))
    monkeypatch.setattr(nse, "fetch_snapshot", lambda: pytest.fail("NSE should not be called"))
    snap = market.update_daily(["AAA", "BBB", "CCC"])
    assert (snap["source"], snap["intraday"]) == ("afx", False)
    assert _closes("AAA") == [("2026-11-12", 10.0, 1000.0)]
    assert _closes("BBB") == [("2026-11-12", 20.0, 0.0)]
    assert _closes("CCC") == []
    assert storage.read_series(storage.nasi_path()) == [("2026-11-12", 240.0)]


def test_intraday_afx_falls_back_to_closed_nse(data_dir, monkeypatch):
    monkeypatch.setattr(afx, "fetch_listing", _afx(INTRADAY))
    monkeypatch.setattr(nse, "fetch_snapshot", _nse("closed"))
    snap = market.update_daily(["AAA", "CCC"])
    assert (snap["source"], snap["intraday"]) == ("nse", False)
    assert snap["rows"]["AAA"]["suspended"] is None
    assert _closes("AAA") == [("2026-11-12", 11.0, 5.0)]
    assert _closes("CCC") == [("2026-11-12", 31.0, 5.0)]
    assert storage.read_series(storage.nasi_path()) == []


def test_intraday_everywhere_keeps_stored_closes(data_dir, monkeypatch):
    storage.upsert_prices("AAA", [("2026-11-11", 9.5, 100.0)])
    monkeypatch.setattr(afx, "fetch_listing", _afx(INTRADAY))
    monkeypatch.setattr(nse, "fetch_snapshot", _nse("open"))
    snap = market.update_daily(["AAA"])
    assert (snap["source"], snap["intraday"]) == ("afx", True)
    assert _closes("AAA") == [("2026-11-11", 9.5, 100.0)]
    assert storage.read_series(storage.nasi_path()) == []
    listing = json.loads(storage.market_path("listing.json").read_text(encoding="utf-8"))
    assert listing["rows"]["CCC"]["suspended"] is True


def test_partial_afx_listing_falls_back_to_nse(data_dir, monkeypatch):
    monkeypatch.setattr(afx, "fetch_listing", _afx(AFTER_CLOSE, rows=[afx.ListingRow("AAA", "Alpha", 1.0, 10.0, 0.0, False)]))
    monkeypatch.setattr(nse, "fetch_snapshot", _nse("closed"))
    snap = market.update_daily(["AAA", "BBB", "CCC"])
    assert snap["source"] == "nse"
    assert "covers only 1 of 3" in snap["errors"][0]


def test_nse_status(fixture_text):
    assert nse.parse_status(json.loads(fixture_text("nse_ticker.json"))) == "open"
    assert nse.parse_status({}) is None
