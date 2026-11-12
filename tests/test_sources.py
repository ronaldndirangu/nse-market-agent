import json

import pytest

from nse_agent.sources import afx, nse


@pytest.mark.parametrize("text, expected", [
    ("1,234", 1234.0),
    ("288B", 288e9),
    ("4.06Tr", 4.06e12),
    ("1.39 million", 1.39e6),
    ("KES 126 million", 126e6),
    ("+3.46%", 0.0346),
    ("-0.28%", -0.0028),
    ("-", None),
    ("", None),
    (None, None),
    ("12 parsecs", None),
])
def test_afx_parse_number(text, expected):
    got = afx.parse_number(text)
    assert got == pytest.approx(expected) if expected is not None else got is None


def test_afx_listing(fixture_text):
    listing = afx.parse_listing(fixture_text("afx_listing.html"))
    rows = {r.ticker: r for r in listing.rows}
    assert set(rows) == {"ABSA", "ALP", "AMAC", "ARM"}
    assert rows["ABSA"].volume == 2110546 and rows["ABSA"].price == 31.0 and rows["ABSA"].change == pytest.approx(0.6)
    assert rows["ALP"].volume is None
    assert rows["ARM"].suspended and not rows["ABSA"].suspended
    assert listing.nasi == pytest.approx(239.04)
    assert listing.as_of == "2026-11-11T11:45:02+00:00"


def test_afx_company(fixture_text):
    cp = afx.parse_company("kcb", fixture_text("afx_kcb.html"))
    assert cp.ticker == "KCB"
    assert cp.as_of.startswith("2026-11-11")
    assert cp.stats["Market Capitalization"] == pytest.approx(288e9)
    assert cp.perf["1WK"] == pytest.approx(0.0346)
    assert cp.history[0] == ("2026-11-10", 89.75, 333134.0)
    assert len(cp.history) == 10
    assert cp.avg_session_volume == pytest.approx(1.39e6)
    assert cp.avg_session_turnover == pytest.approx(126e6)
    assert (cp.sector, cp.industry) == ("Financials", "Banking")


def test_afx_chart(fixture_text):
    pts = afx.parse_chart(fixture_text("afx_kcb_chart.js"))
    assert len(pts) == 6
    assert pts[0] == ("2016-11-14", 30.5)
    assert pts[-1] == ("2026-11-10", 89.75)


def test_nse_snapshot(fixture_text):
    trade_date, rows = nse.parse_snapshot(json.loads(fixture_text("nse_ticker.json")))
    assert trade_date == "2026-11-11"
    assert rows["SCOM"]["price"] == 35.25 and rows["KCB"]["volume"] == 750955


def test_nse_snapshot_empty():
    assert nse.parse_snapshot({}) == (None, {})


def test_nse_announcements():
    page = (
        '<div><h3 class="t">KCB Group Plc &amp; Subsidiaries <b>Unaudited Results</b></h3>'
        '<p>text</p><a href="https://www.nse.co.ke/wp-content/uploads/2026/11/kcb.pdf">Download</a></div>'
        '<div><h3>No document</h3></div>'
    )
    items = nse.parse_announcements(page)
    assert items == [{"title": "KCB Group Plc & Subsidiaries Unaudited Results",
                      "url": "https://www.nse.co.ke/wp-content/uploads/2026/11/kcb.pdf"}]

def test_unreachable_host_is_skipped_after_retries(monkeypatch):
    import requests

    from nse_agent import http

    calls = []

    class DeadSession:
        def request(self, method, url, **kwargs):
            calls.append(url)
            raise requests.ConnectionError("Network is unreachable")

    monkeypatch.setattr(http, "_down_hosts", set())
    monkeypatch.setattr(http, "session", lambda: DeadSession())

    with pytest.raises(requests.ConnectionError):
        http.get_text("https://blocked.example/a")
    assert len(calls) == 3

    with pytest.raises(requests.ConnectionError, match="unreachable earlier"):
        http.get_text("https://blocked.example/b")
    assert len(calls) == 3

    with pytest.raises(requests.ConnectionError):
        http.get_text("https://other.example/c")
    assert len(calls) == 6


def test_server_error_backs_off_before_retrying(monkeypatch):
    from nse_agent import http

    statuses = iter([500, 503, 200])

    class FlakySession:
        def request(self, method, url, **kwargs):
            resp = type("Resp", (), {})()
            resp.status_code = next(statuses)
            resp.text = "ok"
            resp.raise_for_status = lambda: None
            return resp

    sleeps = []
    monkeypatch.delenv("NSE_AGENT_DELAY")
    monkeypatch.setattr(http, "_last_hit", {})
    monkeypatch.setattr(http, "session", lambda: FlakySession())
    monkeypatch.setattr(http.time, "sleep", sleeps.append)
    monkeypatch.setattr(http.random, "uniform", lambda lo, hi: 0)

    assert http.get_text("https://flaky.example/ticker") == "ok"
    assert http.SERVER_ERROR_BACKOFF in sleeps
    assert 2 * http.SERVER_ERROR_BACKOFF in sleeps


def test_retry_after_is_bounded_and_test_override_skips_waits(monkeypatch):
    from nse_agent import http

    assert http._backoff(0, "120") == 0
    monkeypatch.delenv("NSE_AGENT_DELAY")
    monkeypatch.setattr(http.random, "uniform", lambda lo, hi: 0)
    monkeypatch.setattr(http.time, "time", lambda: 0)
    assert http._backoff(0, "40") == 40
    assert http._backoff(0, "Thu, 01 Jan 1970 00:00:45 GMT") == 45
    assert http._backoff(0, "120") == 60
    assert http._backoff(0, "invalid") == http.SERVER_ERROR_BACKOFF
