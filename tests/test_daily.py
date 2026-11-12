import shutil
from datetime import date

import pytest
import yaml

from nse_agent import announcements, brief, config, dividends, ledger, storage
from nse_agent.engine import analyze
from nse_agent.fmt import pct
from nse_agent.returns import SIGNALS
from tests.test_pipeline import AS_OF, BANKS, market  # noqa: F401

PREFIX = {"Buy": "Clears every gate.", "Watch": "Not a Buy: ", "Avoid": "Avoid: "}


@pytest.fixture
def outputs(root):
    yield root
    for sub in ("data/rankings", "reports", "site"):
        shutil.rmtree(root / sub, ignore_errors=True)
    for name in ("announcements.json", "dividends.yaml", "corporate_actions.yaml"):
        (root / "data" / name).unlink(missing_ok=True)


def test_tiers_binding_and_signal_breakdown(market):
    weights = config.settings()["ranking"]["weights"]
    result = analyze(AS_OF)
    for t, r in result["rows"].items():
        assert r["binding"].startswith(PREFIX[r["tier"]])
        assert (r["tier"] == "Buy") == (t in result["buys"])
        assert set(r["signals"]) == set(SIGNALS)
        assert r["composite"] == pytest.approx(sum(s["contribution"] for s in r["signals"].values()))
        for name, s in r["signals"].items():
            assert s["weight"] == weights.get(name, 0)
            assert s["contribution"] == pytest.approx(s["weight"] * s["z"])
        assert r["volatility"] > 0


def test_ledger_is_append_only(market, outputs):
    result = analyze(AS_OF)
    assert ledger.append(result) == len(BANKS)
    assert ledger.append(result) == 0
    rows = ledger.read()
    assert len(rows) == len(BANKS)
    assert {r["rank"] for r in rows} == {1, 2, 3}
    assert all(isinstance(r["composite"], float) and r["code_sha"] for r in rows)
    assert ledger.previous(AS_OF.isoformat()) == (None, {})
    prev_date, snap = ledger.previous("2026-11-09")
    assert prev_date == AS_OF.isoformat() and set(snap) == set(BANKS)


def test_brief_flags_changes_and_material_alerts(market, outputs, tmp_path):
    earlier = analyze(AS_OF)
    promoted = earlier["buys"][0]
    earlier["as_of"] = "2026-11-05"
    earlier["rows"][promoted]["tier"] = "Watch"
    ledger.append(earlier)

    last = storage.read_prices("EQTY")[-1]
    storage.upsert_prices("EQTY", [(last["date"], last["close"] * 1.12, last["volume"])])
    storage.write_json(announcements.path(), {"items": [{
        "title": "KCB Group PLC profit warning", "url": "https://example.test/kcb.pdf", "date": AS_OF.isoformat(),
        "first_seen": AS_OF.isoformat(), "ticker": "KCB", "results": False, "status": "new"}]})

    alert = tmp_path / "alert.md"
    out = brief.run_brief(fetch=False, alert_file=str(alert), as_of=AS_OF)
    assert f"ledger_rows={len(BANKS)}" in out and "prev=2026-11-05" in out

    text = (outputs / "reports" / "daily" / f"{AS_OF.isoformat()}.md").read_text(encoding="utf-8")
    for heading in ("## Alerts", "## Top 5", "### Score breakdown", "## What changed", "## Full ranking",
                    "## Data gaps"):
        assert heading in text
    assert "Compared with the brief for 2026-11-05." in text
    assert f"Tier: {promoted} moved from Watch to " in text
    eqty = storage.read_prices("EQTY")
    assert f"Unusual move: EQTY {pct(eqty[-1]['close'] / eqty[-2]['close'] - 1)} on {AS_OF}" in text
    assert "Tier: KCB moved from Buy to Avoid." in text
    assert "\u2014" not in text and "\u2013" not in text
    weights = config.settings()["ranking"]["weights"]
    formula = next(ln for ln in text.splitlines() if ln.startswith("- Composite score = "))
    note = formula.rsplit(").", 1)[-1].lower()
    assert not [n for n, w in weights.items() if w and brief.LABELS[n] in note]
    assert (outputs / "site" / "daily.html").exists() and (outputs / "site" / "daily" / f"{AS_OF}.html").exists()

    body = alert.read_text(encoding="utf-8")
    assert "Warning announcement for KCB" in body
    assert "Buy dropped: KCB." in body
    result = analyze(AS_OF)
    if promoted in result["buys"]:
        label = "New Buy, high confidence undervalued" if promoted in result["high_confidence"] else "New Buy"
        assert f"{label}: {promoted} #" in body

    alert.unlink()
    assert "ledger_rows=0" in brief.run_brief(fetch=False, alert_file=str(alert), as_of=AS_OF)


def test_alerts_flag_dropped_buys(market):
    result = analyze(AS_OF)
    prev = {t: {"tier": "Buy"} for t in result["rows"]} | {"XYZ": {"tier": "Buy"}}
    ch = {"warnings": []}
    lines = brief.alerts(result, ch, prev)
    assert "Buy dropped: XYZ. no longer ranked (missing price or fundamentals)." in lines
    assert not any(line.startswith("New Buy") for line in lines)
    assert brief.alerts(result, ch, {t: {"tier": "Buy"} for t in result["buys"]}) == []


def test_dividends_adjust_for_splits_and_withholding(outputs):
    data = outputs / "data"
    (data / "dividends.yaml").write_text(yaml.safe_dump({"dividends": {"TST": [
        {"fiscal_period": "FY2025", "type": "final", "amount": 4.0, "book_closure": "2026-03-01",
         "source_url": "https://example.test/div.pdf"},
        {"fiscal_period": "FY2026", "type": "final", "amount": 1.0, "announced": "2027-04-01",
         "source_url": "https://example.test/div2.pdf"}]}}), encoding="utf-8")
    (data / "corporate_actions.yaml").write_text(yaml.safe_dump({"actions": [
        {"ticker": "TST", "type": "split", "ratio": "2:1", "factor": 0.5, "ex_date": "2026-06-01",
         "source_url": "https://example.test/split.pdf"}]}), encoding="utf-8")
    storage.upsert_prices("TST", [("2026-01-02", 100.0, 1.0), ("2026-12-01", 55.0, 1.0)])
    try:
        assert dividends.factor("TST", date(2026, 1, 2)) == 0.5
        assert dividends.factor("TST", date(2026, 7, 1)) == 1.0
        assert dividends.total_return("TST", date(2026, 1, 2), date(2026, 12, 1), net=False) == pytest.approx(0.14)
        assert dividends.total_return("TST", date(2026, 1, 2), date(2026, 12, 1)) == pytest.approx(0.138)
        assert dividends.trailing_yield("TST", date(2026, 12, 1), 55.0) == pytest.approx(2 / 55)
        assert dividends.trailing_yield("TST", date(2025, 6, 1), 50.0, dps=3.0) == pytest.approx(0.06)
        assert dividends.history("TST")[-1] == (date(2027, 4, 1), 1.0)
        assert dividends.trailing_yield("TST", date(2027, 3, 1), 55.0, dps=3.0) == pytest.approx(3 / 55)
    finally:
        storage.price_path("TST").unlink(missing_ok=True)
