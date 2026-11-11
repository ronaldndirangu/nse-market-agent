import math

import pytest

from nse_agent import config, valuation as v
from tests.helpers import period


def test_cost_of_equity_matches_macro_inputs():
    m = config.macro()
    er = m["equity_risk"]
    rf = m["risk_free"]["bond_10y"]["value"] - er["default_spread"]
    assert v.cost_of_equity(1.0) == pytest.approx(rf + er["mature_market_erp"] + er["country_risk_premium"])
    assert v.cost_of_equity(1.5) > v.cost_of_equity(1.0)
    assert v.cost_of_equity(None) == v.cost_of_equity(config.settings()["valuation"]["default_beta"])


def test_sustainable_growth_is_capped():
    periods = [period(year=y, net_income=250, total_equity=1000, eps=2.5, dps=1.0) for y in (2022, 2023, 2024)]
    g, roe = v.sustainable_growth(periods, ke=0.20)
    assert roe == pytest.approx(0.25)
    assert g == config.settings()["valuation"]["growth_cap"]


def test_sustainable_growth_floor_when_eps_negative():
    g, _ = v.sustainable_growth([period(eps=-1.0, net_income=-10, total_equity=100)], ke=0.2)
    assert g == config.settings()["valuation"]["growth_floor"]


def test_models_for_a_bank():
    periods = [period(year=y, eps=10.0, bvps=50.0, dps=4.0) for y in (2022, 2023, 2024)]
    out = v.models(periods, bank=True, ke=0.20, g=0.05, avg_roe=0.20, sector_pe=4.0, sector_pb=0.8)
    assert out["justified_pb"] == pytest.approx(50 * (0.20 - 0.05) / (0.20 - 0.05))
    assert out["gordon_ddm"] == pytest.approx(4 * 1.05 / 0.15)
    assert out["earnings_power"] == pytest.approx(10 / 0.20)
    assert out["sector_pe"] == pytest.approx(40.0)
    assert out["sector_pb"] == pytest.approx(40.0)


def test_models_skip_missing_inputs():
    out = v.models([period(eps=-2.0)], bank=False, ke=0.2, g=0.03, avg_roe=None, sector_pe=8.0, sector_pb=None)
    assert out == {}


def test_graham_number():
    assert v.graham_number([period(eps=4.0, bvps=40.0)]) == pytest.approx(math.sqrt(22.5 * 160))
    assert v.graham_number([period(eps=-1.0, bvps=40.0)]) is None


def test_fair_value_range():
    assert v.fair_value({}) is None
    assert v.fair_value({"a": 10, "b": 20, "c": 40}) == {"low": 10, "base": 20, "high": 40}


def test_sector_multiples_exclude_self():
    rows = {t: {"sector": "Banking", "pe": pe, "pb": 1.0} for t, pe in (("A", 2.0), ("B", 4.0), ("C", 6.0), ("D", 100.0))}
    rows["E"] = {"sector": "Energy", "pe": 5.0, "pb": 1.0}
    out = v.sector_multiples(rows, min_peers=3)
    assert out["A"]["pe"] == 6.0
    assert out["D"]["pe"] == 4.0
    assert out["E"] == {"pe": None, "pb": None}


def test_agreement_rules():
    assert v.agreeing({"a": 11.0, "b": 20.0}, price=10.0, threshold=0.15) == ["b"]
    assert [v.required_agreement(n) for n in (1, 2, 3, 4, 5)] == [2, 2, 2, 2, 3]
