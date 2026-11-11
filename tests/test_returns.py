import pytest

from nse_agent import config, returns


def test_net_tbill_applies_withholding():
    m = config.macro()
    expected = m["risk_free"]["tbill_364d"]["value"] * (1 - m["taxes_and_costs"]["tbill_interest_wht"])
    assert returns.net_tbill() == pytest.approx(expected)


def test_project_at_fair_value_is_net_yield_less_costs():
    tc = config.macro()["taxes_and_costs"]
    shift = config.settings()["scenarios"]["growth_shift"]
    p = returns.project(100.0, 10.0, {"low": 100.0, "base": 100.0, "high": 100.0}, g=0.0, years=3)
    div = 0.10 * (1 - tc["dividend_wht"])
    costs = 2 * tc["trade_cost_per_side"] / 3
    assert p["base"] == pytest.approx(div - costs)
    assert p["bear"] == pytest.approx(div - shift - costs)
    assert p["bull"] == pytest.approx(div + shift - costs)


def test_project_rerating_over_horizon():
    p = returns.project(100.0, None, {"low": 80.0, "base": 133.1, "high": 200.0}, g=0.0, years=3)
    assert p["base"] == pytest.approx(0.10 - p["cost_drag"], abs=1e-6)
    assert p["bear"] < p["base"] < p["bull"]


def test_zscores():
    assert returns.zscores({"a": 1.0, "b": None}) == {"a": 0.0, "b": 0.0}
    z = returns.zscores({"a": 1.0, "b": 3.0, "c": None})
    assert z == {"a": -1.0, "b": 1.0, "c": 0.0}


def test_rank_prefers_cheap_quality_momentum():
    rows = {
        "CHEAP": {"mos": 0.6, "quality": {"score": 0.9}, "momentum": 0.2},
        "MID": {"mos": 0.2, "quality": {"score": 0.6}, "momentum": 0.0},
        "DEAR": {"mos": -0.3, "quality": {"score": 0.3}, "momentum": -0.2},
    }
    assert returns.rank(rows) == ["CHEAP", "MID", "DEAR"]
    assert rows["CHEAP"]["composite"] > 0 > rows["DEAR"]["composite"]
