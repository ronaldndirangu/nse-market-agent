import xml.etree.ElementTree as ET

import pytest

from nse_agent import brief, ledger, publication, site, storage
from nse_agent.engine import analyze
from tests.test_daily import outputs  # noqa: F401
from tests.test_pipeline import AS_OF, BANKS, market  # noqa: F401


def test_revisions_link_to_the_unchanged_official_ledger(market, outputs):
    result = analyze(AS_OF)
    ledger.append(result)
    path = ledger.live_path(result["as_of"])
    before = path.read_bytes()
    changes = brief.changes(result, None, {})
    first, fresh = publication.write(brief.snapshot(result, changes, ["New Buy: EQTY #1."]), result)
    assert len(fresh) == 1
    result["rows"]["EQTY"]["rank"] += 1
    second, fresh = publication.write(brief.snapshot(result, changes, ["New Buy: EQTY #1."]), result)
    assert first["revision"] != second["revision"] and not fresh
    assert second["ledger"]["rows"] == len(BANKS)
    assert second["ledger"]["differences"] == [{"ticker": "EQTY", "fields": ["rank"]}]
    assert ledger.append(result) == 0 and path.read_bytes() == before
    manifest = storage.read_json(outputs / "reports" / "daily" / "manifest.json", {})
    publication.validate(second, manifest)
    site.build()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = ET.parse(outputs / "site" / "feed.xml").findall("a:entry", ns)
    assert len(entries) == 2
    ids = [e.find("a:id", ns).text for e in entries]
    assert len(ids) == len(set(ids))
    second["ranking"][0]["price"] += 1
    with pytest.raises(ValueError, match="does not match"):
        publication.validate(second, manifest)


def test_published_monitor_detects_a_missed_run(monkeypatch):
    from nse_agent import health, http
    from datetime import datetime

    status = {"as_of": "2026-11-12", "revision": "abc", "health": {
        "prices": {"status": "Current"}, "announcements": {"status": "Current"}, "macro": {"status": "Current"}}}
    monkeypatch.setattr(health, "now", lambda: datetime(2026, 11, 12, 18, tzinfo=health.EAT))
    monkeypatch.setattr(http, "request", lambda *args, **kwargs: type("Response", (), {"json": lambda self: status})())
    assert "abc" in publication.check_published("https://example.test")
    status["as_of"] = "2026-11-11"
    with pytest.raises(ValueError, match="overdue"):
        publication.check_published("https://example.test")


def test_disagreement_suppresses_consumer_estimates_but_retains_research_values(market, outputs, monkeypatch):
    from nse_agent import config, report

    monkeypatch.setitem(config.settings()["valuation"], "max_model_spread", 1.0)
    result = analyze(AS_OF)
    for row in result["rows"].values():
        row["projection"]["base"] = 0.296
        row["mos"] = 0.569
        row["binding"] = "Avoid: valuation models disagree; base return 29.6% does not beat the 40.0% hurdle."
    changes = brief.changes(result, None, {})
    rendered = brief.render(result, changes, []) + report.render(result)
    assert "29.6%" not in rendered and "56.9%" not in rendered
    for row in result["rows"].values():
        assert "29.6%" not in brief.why(row, result)
        assert "29.6%" not in site._stock_card(brief.snapshot(result, changes, [])["ranking"][0], 0.12, gates=True)
    assert all(float(row["base"]) == 0.296 for row in ledger.rows_for(result))
