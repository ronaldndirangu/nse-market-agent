from copy import deepcopy
from datetime import date
import shutil
import ssl

import pytest
import requests

from nse_agent import config, http, official, storage
from nse_agent.engine import analyze
from nse_agent.returns import net_tbill

TODAY = date(2026, 11, 12)
CBK_TEXT = """A. RESULTS OF BILLS ISSUES 2708/091, 2682/182 & 2637/364 DATED 16/11/2026
Tenor 91 DAYS 182 DAYS 364 DAYS TOTAL
Market Weighted Average Interest 8.7477% 8.8382% 9.0198%
Weighted Average Interest Rate of 8.7448% 8.8372% 9.0098%
accepted bids
B. COMPARATIVE AVERAGE INTEREST RATES OF ACCEPTED BIDS
This Auction Last Auction Variance
91 - day 8.7448 8.7500 0.0052
182-day 8.8372 8.8450 0.0078
364 - day 9.0098 9.0282 0.0184
C. NEXT AUCTIONS DATED 23/11/2026
Results Announcement 19/11/2026
Director, Financial Markets
November 12, 2026
"""


@pytest.fixture
def inputs(root):
    config.macro.cache_clear()
    yield
    shutil.rmtree(root / "data" / "official", ignore_errors=True)
    storage.market_path("health.json").unlink(missing_ok=True)
    config.macro.cache_clear()


def cbk_record():
    return official.parse_cbk(CBK_TEXT, TODAY) | {
        "source": "https://www.centralbank.go.ke/results.pdf", "sha256": "a" * 64, "observed_on": TODAY.isoformat()}


def test_cbk_rates_are_accepted_bids_with_independent_date_and_column_checks():
    record = official.parse_cbk(CBK_TEXT, TODAY)
    assert record["released"] == "2026-11-12" and record["issue_date"] == "2026-11-16"
    assert [r["value"] for r in record["rates"].values()] == pytest.approx([0.087448, 0.088372, 0.090098])
    for bad in (CBK_TEXT.replace("91 DAYS 182 DAYS", "182 DAYS 91 DAYS"),
                CBK_TEXT.replace("364 - day 9.0098", "364 - day 9.0198"),
                CBK_TEXT.replace("November 12, 2026", "November 19, 2026")):
        with pytest.raises(ValueError):
            official.parse_cbk(bad, TODAY)


@pytest.mark.parametrize("missing", ["-", "0.0000"])
def test_missing_tenor_keeps_its_old_value_and_date(inputs, missing):
    text = CBK_TEXT.replace("9.0098%", missing if missing == "-" else missing + "%").replace(
        "364 - day 9.0098", "364 - day " + missing)
    record = official.parse_cbk(text, TODAY) | {
        "source": "https://www.centralbank.go.ke/results.pdf", "observed_on": TODAY.isoformat(), "sha256": "a" * 64}
    official.save("cbk", record)
    config.macro.cache_clear()
    m = config.macro(TODAY)
    assert m["risk_free"]["tbill_91d"]["value"] == pytest.approx(0.087448)
    assert m["risk_free"]["tbill_364d"]["value"] == pytest.approx(0.090282)
    assert m["risk_free"]["tbill_364d"]["as_of"] == "2026-11-05"


def test_inputs_reach_actual_hurdle_without_future_use_or_unrelated_changes(inputs, monkeypatch):
    before = config.macro(TODAY)
    official.save("cbk", cbk_record())
    config.macro.cache_clear()
    after = config.macro(TODAY)
    assert net_tbill(after) == pytest.approx(0.0765833)
    assert after["as_of"] == before["as_of"]
    assert after["risk_free"]["bond_10y"] == before["risk_free"]["bond_10y"]
    assert after["equity_risk"] == before["equity_risk"]
    assert config.macro(date(2026, 11, 11))["risk_free"]["tbill_364d"]["value"] == before["risk_free"]["tbill_364d"]["value"]
    monkeypatch.setattr(config, "universe", lambda: [])
    result = analyze(TODAY)
    assert result["hurdle"] == pytest.approx(0.1265833)
    assert result["ke_at_beta_1"] == pytest.approx(0.2005)
    assert result["macro"]["risk_free"]["tbill_364d"]["source"].startswith("https://www.centralbank.go.ke/")


def test_refresh_failure_retains_facts_and_clears_same_process_cache(inputs, monkeypatch):
    before = net_tbill()
    monkeypatch.setattr(official, "collect_cbk", lambda _: cbk_record())
    monkeypatch.setattr(official, "collect_cpi", lambda _: {
        "period": "2026-10", "value": 0.073, "source": official.KNBS, "observed_on": TODAY.isoformat()})
    assert official.refresh(TODAY)["cbk"] == "updated"
    assert net_tbill() != before
    path = config.DATA / "official" / "cbk" / "2026-11-12.json"
    body = path.read_bytes()

    def failed(_):
        raise requests.exceptions.SSLError("test certificate chain failure")
    monkeypatch.setattr(official, "collect_cbk", failed)
    assert official.refresh(TODAY)["cbk"] == "failed"
    assert path.read_bytes() == body
    assert "test certificate" in config.macro()["_source_status"]["cbk"]["error"]


def test_changed_or_regressed_release_is_not_silently_accepted(inputs):
    record = cbk_record()
    official.save("cbk", record)
    changed = deepcopy(record)
    changed["rates"]["364"]["value"] += 0.001
    with pytest.raises(ValueError, match="human review"):
        official.save("cbk", changed)
    older = record | {"released": "2026-11-05"}
    with pytest.raises(ValueError, match="older"):
        official.save("cbk", older)


def test_backdated_document_cannot_precede_its_first_observation(inputs):
    record = cbk_record() | {"observed_on": "2026-11-13"}
    official.save("cbk", record)
    config.macro.cache_clear()
    assert net_tbill(config.macro(TODAY)) == pytest.approx(0.090282 * 0.85)
    assert net_tbill(config.macro(date(2026, 11, 13))) == pytest.approx(0.090098 * 0.85)


def test_cached_cpi_cannot_overwrite_a_newer_reviewed_period(inputs):
    official.save("knbs", {"period": "2026-10", "value": 0.073, "source": official.KNBS,
                           "observed_on": TODAY.isoformat()})
    macro = deepcopy(config.load_yaml(config.DATA / "macro.yaml"))
    macro["policy"]["inflation"] = {"period": "2026-11", "value": 0.08, "source": official.KNBS,
                                   "observed_on": "2026-11-30", "method": "reviewed"}
    assert official.apply(macro, date(2026, 11, 30))["policy"]["inflation"]["value"] == 0.08


def test_cpi_has_period_provenance_and_is_not_a_forward_forecast():
    url = official.KNBS + "reports/consumer-price-indices-and-inflation-rates-october-2026/"
    html = "<h1>October 2026</h1><p>Annual consumer price inflation was 7.3 per cent in October 2026.</p>"
    row = official.parse_cpi(html, url, TODAY)
    assert row["period"] == "2026-10" and row["value"] == pytest.approx(0.073)
    assert row["observed_on"] == TODAY.isoformat()
    with pytest.raises(ValueError, match="period"):
        official.parse_cpi(html, url.replace("october", "september"), TODAY)


def test_tls_errors_are_not_retried_and_certificate_checks_stay_enabled(monkeypatch):
    context = http._SystemTrustAdapter().poolmanager.connection_pool_kw["ssl_context"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    calls = []

    class Session:
        def request(self, *args, **kwargs):
            calls.append(1)
            raise requests.exceptions.SSLError("invalid certificate")
    monkeypatch.setattr(http, "_session", Session())
    with pytest.raises(requests.exceptions.SSLError):
        http.request("GET", "https://certificate.test/")
    assert len(calls) == 1


@pytest.mark.parametrize("oversized", [False, True])
def test_pdf_reader_rejects_non_pdf_and_oversized_downloads(monkeypatch, oversized):
    class Response:
        status_code = 200
        url = "https://example.test/results.pdf"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_content(self, size):
            if oversized:
                yield from [b"x" * (1024 * 1024)] * 11
            else:
                yield b"<html>not a PDF</html>"
    monkeypatch.setattr(http, "request", lambda *a, **k: Response())
    with pytest.raises(ValueError, match="10 MB|not return a PDF"):
        http.pdf_document(Response.url)


def test_atomic_fact_write_keeps_previous_release_after_failure(tmp_path, monkeypatch):
    path = tmp_path / "release.json"
    storage.write_json(path, {"rate": 0.09})
    before = path.read_bytes()

    def broken_dump(obj, fh, **kwargs):
        fh.write("partial")
        raise ValueError("serialization failed")
    monkeypatch.setattr(storage.json, "dump", broken_dump)
    with pytest.raises(ValueError, match="serialization"):
        storage.write_json(path, {})
    assert path.read_bytes() == before and not list(tmp_path.glob("*.tmp"))


def test_html_notice_pdf_resolution_requires_one_same_host_document(monkeypatch):
    from nse_agent import results_watch
    url = "https://www.nse.co.ke/notices/results/"
    monkeypatch.setattr(http, "get_text", lambda *a, **k: '<a href="/files/results.pdf?download=1">PDF</a>')
    assert results_watch.document_url(url) == "https://www.nse.co.ke/files/results.pdf?download=1"
    monkeypatch.setattr(http, "get_text", lambda *a, **k: '<a href="https://other.test/results.pdf">PDF</a>')
    with pytest.raises(ValueError, match="official HTTPS host"):
        results_watch.document_url(url)
    monkeypatch.setattr(http, "get_text", lambda *a, **k: '<a href="a.pdf">A</a><a href="b.pdf">B</a>')
    with pytest.raises(ValueError, match="exactly one"):
        results_watch.document_url(url)
