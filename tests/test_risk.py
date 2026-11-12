import csv

from nse_agent import ledger, risk
from nse_agent.engine import analyze
from tests.test_pipeline import AS_OF, BANKS, market  # noqa: F401


def _row(**over):
    r = {"bank": True, "rank": 1, "tier": "Buy", "volatility": 0.20, "beta": 0.6, "avg_turnover": 50e6,
         "projection": {"bear": 0.05, "base": 0.25, "bull": 0.40},
         "fair_value": {"low": 100.0, "base": 120.0, "high": 130.0},
         "quality": {"gate": "pass", "score": 0.8, "fails": [], "npl": {"latest": 0.08, "status": "ok"}},
         "screen_fail": [], "models": {"pb": 1, "gordon": 1, "pe": 1}, "agree": ["pb", "gordon", "pe"],
         "agree_needed": 2}
    for k, v in over.items():
        r[k] = v
    return r


def _levels(r):
    return {f["name"]: f["level"] for f in risk.profile(r)["factors"]}


def test_factor_bands_and_overall_level():
    calm = risk.profile(_row())
    assert calm["level"] == "Low" and not calm["missing"]
    assert set(_levels(_row()).values()) == {"Low"}

    one_high = _row(volatility=0.40)
    assert _levels(one_high)["Volatility"] == "High" and risk.profile(one_high)["level"] == "Moderate"

    three_moderate = _row(volatility=0.30, beta=1.0, avg_turnover=10e6)
    assert risk.profile(three_moderate)["level"] == "Moderate"

    two_high = _row(volatility=0.40, beta=1.5)
    assert risk.profile(two_high)["level"] == "High"


def test_balance_sheet_and_events_alone_make_risk_high():
    bad_npl = _row(quality={"gate": "pass", "score": 0.8, "fails": [], "npl": {"latest": 0.20, "status": "ok"}})
    assert _levels(bad_npl)["Balance sheet"] == "High" and risk.profile(bad_npl)["level"] == "High"

    rising = _row(quality={"gate": "pass", "score": 0.8, "fails": [], "npl": {"latest": 0.05, "status": "rising"}})
    assert _levels(rising)["Balance sheet"] == "Moderate"

    distress = _row(bank=False, quality={"gate": "pass", "score": 0.8, "fails": [], "altman_z2": 0.9})
    assert _levels(distress)["Balance sheet"] == "High"

    warned = _row(quality={"gate": "fail", "score": 0.5, "fails": ["Warning announcement: profit warning"],
                           "npl": {"latest": 0.05, "status": "ok"}})
    assert _levels(warned)["Events"] == "High" and risk.profile(warned)["level"] == "High"


def test_missing_inputs_are_not_assessed():
    p = risk.profile(_row(beta=None, quality={"gate": "pass", "score": 0.8, "fails": []}))
    assert p["missing"] == ["Beta", "Balance sheet"]
    assert "Not assessed: beta, balance sheet." in p["summary"]
    assert p["label"] == "Insufficient data" and not p["complete"]


def test_completely_missing_evidence_never_presents_as_low_risk():
    p = risk.profile({"bank": False, "quality": {"fails": []}})
    assert len(p["missing"]) == 6
    assert p["label"] == "Insufficient data"
    assert "Low risk" not in p["summary"]


def test_conviction_needs_every_gate():
    assert risk.conviction(_row(), hurdle=0.12)["flag"]
    two_models = risk.conviction(_row(agree=["pb", "gordon"]), hurdle=0.12)
    assert two_models["failed"] == ["Valuation"] and "2 of 3 models" in two_models["gates"][0]["detail"]
    weak = _row(quality={"gate": "pass", "score": 0.6, "fails": [], "npl": None})
    assert risk.conviction(weak, hurdle=0.12)["failed"] == ["Quality"]
    assert risk.conviction(_row(screen_fail=["illiquid"]), hurdle=0.12)["failed"] == ["Screen"]
    assert risk.conviction(_row(), hurdle=0.30)["failed"] == ["Return"]


def test_near_misses_order_by_failed_gates_then_rank():
    rows = {"A": {"rank": 1, "conviction": {"flag": False, "failed": ["Valuation", "Return"]}},
            "B": {"rank": 2, "conviction": {"flag": False, "failed": ["Return"]}},
            "C": {"rank": 3, "conviction": {"flag": True, "failed": []}},
            "D": {"rank": 4, "conviction": {"flag": False, "failed": ["Quality"]}}}
    assert risk.near_misses(rows, ["A", "B", "C", "D"]) == ["B", "D", "A"]


def test_engine_attaches_risk_and_flag(market):
    result = analyze(AS_OF)
    for t, r in result["rows"].items():
        assert r["risk"]["level"] in risk.LEVELS
        assert [f["name"] for f in r["risk"]["factors"]] == list(risk.FACTORS)
        assert [g["name"] for g in r["conviction"]["gates"]] == list(risk.GATES)
        assert (t in result["high_confidence"]) == r["conviction"]["flag"]
        if r["conviction"]["flag"]:
            assert r["tier"] == "Buy"
    text = "\n".join(risk.section_md(result))
    assert "## High confidence undervalued" in text and "### Risk profile" in text


def test_ledger_keeps_old_header_when_columns_are_added(market, root):
    path = ledger.live_path(AS_OF.isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    old = [c for c in ledger.COLUMNS if c not in ("risk", "high_confidence")]
    path.write_text(",".join(old) + "\n", encoding="utf-8")
    try:
        assert ledger.append(analyze(AS_OF)) == len(BANKS)
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            assert reader.fieldnames == old
            assert len(list(reader)) == len(BANKS)
    finally:
        path.unlink()
