from datetime import date

import pytest

from nse_agent import announcements as ann, results_watch as rw


@pytest.mark.parametrize("title, ticker", [
    ("KCB Group Plc Unaudited Results for the period ended 30 Sep 2026", "KCB"),
    ("Equity Group Holdings Plc Notice of AGM", "EQTY"),
    ("I&M Group Plc Interim Dividend", "IMH"),
    ("Kenya Power and Lighting Plc Profit Warning", "KPLC"),
    ("Kenya Re Insurance Notice", None),
])
def test_match_ticker(title, ticker):
    assert ann.match_ticker(title) == ticker


def test_is_results():
    assert ann.is_results("Audited Financial Results for the year ended 31 Dec 2025")
    assert ann.is_results("Half-Year results")
    assert not ann.is_results("Notice of Annual General Meeting")


def test_date_for_prefers_older_upload_month():
    seen = date(2026, 11, 11)
    assert ann.date_for("https://x/wp-content/uploads/2026/03/a.pdf", seen) == "2026-03-01"
    assert ann.date_for("https://x/wp-content/uploads/2026/11/a.pdf", seen) == "2026-11-11"
    assert ann.date_for("https://x/a.pdf", seen) == "2026-11-11"


def test_results_parse_number():
    assert rw.parse_number("(1,234)") == -1234
    assert rw.parse_number("-5.5") == -5.5
    assert rw.parse_number("12,345.6") == 12345.6


def test_results_extract_bank_statement_lines():
    text = "\n".join([
        "STATEMENT OF FINANCIAL POSITION 30-Sep-2026 31-Dec-2025",
        "Total assets 2,345,678 2,100,000",
        "12 Total liabilities 2,000,000 1,800,000",
        "Total shareholders' funds 345,678 300,000",
        "Gross non-performing loans and advances 210,000 195,000",
        "Profit after tax 45,000 (1,200)",
        "Basic earnings per share 14.25 12.10",
        "Dividend per share 2025 3.00",
        "Unrelated line 999",
        "Total assets 2,345,678 2,100,000",
    ])
    out = rw.extract(text)
    assert out["total_assets"] == [[2345678, 2100000]]
    assert out["total_liabilities"] == [[2000000, 1800000]]
    assert out["total_equity"] == [[345678, 300000]]
    assert out["gross_npl"] == [[210000, 195000]]
    assert out["net_income"] == [[45000, -1200]]
    assert out["eps"] == [[14.25, 12.10]]
    assert out["dps"] == [[3.0]]
    assert "revenue" not in out
