from copy import deepcopy

import pytest

from nse_agent import brief, decision, report, returns, site, valuation
from nse_agent.engine import _tier, analyze
from tests.test_pipeline import AS_OF, market  # noqa: F401
from nse_agent import config


def example():
    models = {"sector_pe": 105.97, "sector_pb": 99.27, "justified_pb": 92.53,
              "earnings_power": 70.19, "gordon_ddm": 62.10}
    fv = valuation.fair_value(models)
    row = {"ticker": "NCBA", "price": 88.0, "models": models, "fair_value": fv,
           "mos": fv["base"] / 88 - 1, "dispersed": False, "estimate_reliable": True,
           "agree": valuation.agreeing(models, 88, 0.15), "agree_needed": 3,
           "screen_fail": [], "quality": {"gate": "pass", "score": 0.55, "fails": []},
           "buy": False, "projection": returns.project(88, 7.1, fv, 0.07)}
    _tier(row, models, [], row["projection"]["base"], 0.1266, config.settings()["valuation"])
    return row


def test_watch_explains_passing_return_hurdle_and_failing_cushion_without_reclassifying():
    row = example()
    before = deepcopy(row)
    d = decision.explain(row, 0.1266)
    assert row == before and row["tier"] == "Watch"
    checks = {c["name"]: c for c in d["checks"]}
    assert checks["Return hurdle"]["passed"] and not checks["Valuation cushion"]["passed"]
    assert d["reason"] == "Insufficient valuation cushion"
    assert "1 of 5" in d["agreement"] and "3 must agree" in d["agreement"]
    assert "Clearing this hurdle alone does not qualify" in d["why"][0]
    assert d["cushion_price"] == 80.46
    assert len(valuation.agreeing(row["models"], d["cushion_price"], 0.15)) >= 3
    assert "not a price target" in d["changes"][0] and "All other entry" in d["changes"][0]


@pytest.mark.parametrize("price,fair,g", [(88, 92.53, 0.07), (100, 75, -0.02), (100, 100, 0), (100, 200, 0.04)])
def test_return_drivers_explain_growth_interaction_without_changing_projection(price, fair, g):
    p = returns.project(price, 5, {"low": fair * .8, "base": fair, "high": fair * 1.2}, g)
    assert sum(p["drivers"].values()) == pytest.approx(p["base"], abs=1e-12)
    assert p["base"] == pytest.approx(
        p["dividend_yield_net"] + (1 + g) * (fair / price) ** (1 / p["years"]) - 1 - p["cost_drag"])


@pytest.mark.parametrize("values", [{"a": 115, "b": 120}, {"a": 100, "b": 100, "c": 160},
                                  {"a": 11.5, "b": 23, "c": 24, "d": 25, "e": 26}])
def test_conditional_price_really_passes_existing_agreement_rule(values):
    price = valuation.cushion_price(values, 0.15)
    need = valuation.required_agreement(len(values))
    assert len(valuation.agreeing(values, price, 0.15)) >= need
    assert len(valuation.agreeing(values, price + 0.01, 0.15)) < need
    assert valuation.cushion_price({"only": 100}, 0.15) is None


def test_unreliable_estimates_offer_no_price_trigger_or_numeric_return_story():
    row = example() | {"dispersed": True, "estimate_reliable": False, "tier": "Avoid"}
    d = decision.explain(row, 0.1266)
    assert d["reason"] == "Cannot value reliably" and d["cushion_price"] is None
    assert next(c for c in d["checks"] if c["name"] == "Return hurdle")["passed"] is None
    assert "lower price alone does not resolve" in d["changes"][0]
    assert site._return_explanation(row) == ""


def test_snapshot_and_reports_preserve_one_decision_explanation(market):
    result = analyze(AS_OF)
    change = brief.changes(result, None, {})
    snapshot = brief.snapshot(result, change, [])
    for stock in snapshot["ranking"]:
        row = result["rows"][stock["ticker"]]
        assert stock["decision"] == row["decision"]
        assert stock["projection"]["drivers"] == row["projection"]["drivers"]
        assert all(c["passed"] for c in row["decision"]["checks"]) == row["buy"]
        text = report._thesis(row, result)
        assert row["decision"]["reason"] in text
        assert "What would change it" in text and "Already own it?" in text
