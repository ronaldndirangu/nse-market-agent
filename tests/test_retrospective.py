import json
from datetime import date

import pytest
import yaml

from nse_agent import DISCLAIMER, config, dividends, ledger
from nse_agent import retrospective as retro
from tests.test_daily import outputs  # noqa: F401
from tests.test_pipeline import AS_OF, BANKS, market  # noqa: F401


def test_spearman_handles_ties_and_too_little_data():
    assert retro.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert retro.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert retro.avg_ranks([5.0, 1.0, 5.0, 3.0]) == [3.5, 1.0, 3.5, 2.0]
    assert retro.spearman([1, 1, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9486833)
    assert retro.spearman([1, None, 3], [1, 2, 3]) is None
    assert retro.spearman([1, 1, 1], [1, 2, 3]) is None


def test_add_months_clamps_and_band_compounds():
    assert retro.add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert retro.add_months(date(2025, 11, 15), 3) == date(2026, 2, 15)
    lo, hi = retro.band({"bear": -0.19, "bull": 0.44}, 6)
    assert (lo, hi) == (pytest.approx(-0.1), pytest.approx(0.2))
    assert retro.band({"bear": None, "bull": 0.2}, 12) is None


def test_classify_checks_causes_in_order(market, outputs, monkeypatch):
    a, b = date(2026, 1, 2), date(2026, 7, 1)
    snap = {"KCB": {"rank": 3}}
    calm = {"EQTY": 0.05, "KCB": 0.2, "ABSA": -0.02}
    rally = {t: 0.3 for t in BANKS}
    assert retro.classify("KCB", a, b, snap, calm)[0] == "signal miss"
    assert retro.classify("KCB", a, b, snap, rally)[0] == "macro"
    assert retro.classify("KCB", a, b, {}, rally) == ("missing data", "no point-in-time fundamentals")
    assert retro.classify("ZZZ", a, b, {}, calm) == ("missing data", "no price history")
    monkeypatch.setattr(retro.fnd, "annuals", lambda t, d: [{"eps": -1.0}, {"eps": 2.0}])
    assert retro.classify("KCB", a, b, snap, rally)[0] == "turnaround"
    (outputs / "data" / "corporate_actions.yaml").write_text(yaml.safe_dump({"actions": [
        {"ticker": "KCB", "type": "bonus", "ratio": "1:10", "factor": 10 / 11, "ex_date": "2026-03-02",
         "source_url": "https://example.test/bonus.pdf"}]}), encoding="utf-8")
    dividends.clear_cache()
    assert retro.classify("KCB", a, b, {}, rally)[0] == "event"


def test_reconstruct_and_retro_report(market, outputs, monkeypatch):
    monkeypatch.setattr(retro, "TOP", 2)
    rows = retro.reconstruct(end=AS_OF)
    recon = ledger.by_date(ledger.read("reconstructed"))
    assert rows == sum(len(s) for s in recon.values()) and rows % len(BANKS) == 0
    assert min(recon) > "2023-03-20"

    summary = retro.run_retro(rebuild=False)
    assert summary.startswith(f"reconstructed_dates={len(recon)} live_dates=0")
    text = (config.REPORTS / "retrospective.md").read_text(encoding="utf-8")
    assert DISCLAIMER in text and "No live window has matured yet" in text
    res = json.loads((config.DATA / "retrospective.json").read_text(encoding="utf-8"))
    one = res["reconstructed"]["1"]
    assert one["windows"] > 0 and one["calibration_n"] > 0
    assert one["calibration"] + one["below_bear"] + one["above_bull"] == pytest.approx(1)
    attr = res["attribution"]["12"]
    assert attr["winners"] == 2 * len({r["start"] for r in attr["rows"]}) > 0
    assert sum(attr["counts"].values()) == attr["winners"]
    assert all(n <= attr["winners"] for n in attr["flag_n"].values())
    assert res["ic"]["momentum"]["source"] == "prices"
