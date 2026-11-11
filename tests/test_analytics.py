import math
import random
from datetime import date

import pytest

from nse_agent import backtest, simulate


def test_bootstrap_constant_returns():
    out = simulate.bootstrap([0.01] * 20, weeks=52, paths=5, block=4, rng=random.Random(1))
    assert out == pytest.approx([1.01 ** 52 - 1] * 5)


def test_bootstrap_drift_replaces_mean():
    rets = [0.05, -0.04, 0.02, -0.01, 0.03, -0.02, 0.0, 0.01]
    out = simulate.bootstrap(rets, weeks=8, paths=2000, block=1, rng=random.Random(7), drift=0.0)
    median = simulate.percentile([math.log1p(x) for x in out], 0.5)
    assert abs(median) < 0.02


def test_percentile_interpolates():
    assert simulate.percentile([4.0, 1.0, 3.0, 2.0], 0.5) == 2.5
    assert simulate.percentile([1.0, 2.0, 3.0], 0.0) == 1.0
    assert simulate.percentile([1.0, 2.0, 3.0], 1.0) == 3.0


def test_month_starts():
    assert backtest.month_starts(date(2024, 11, 15), date(2025, 2, 1)) == [
        date(2024, 12, 1), date(2025, 1, 1), date(2025, 2, 1)]


@pytest.mark.parametrize("old, new, expected", [
    ([], [], 0.0), ([], ["A"], 1.0), (["A", "B"], ["A", "B"], 0.0),
    (["A", "B"], ["C", "D"], 2.0), (["A", "B"], ["A", "C"], 1.0),
])
def test_turnover(old, new, expected):
    assert backtest._turnover(old, new) == pytest.approx(expected)


def test_stats():
    s = backtest.stats([0.1, -0.5, 0.2])
    assert s["total"] == pytest.approx(1.1 * 0.5 * 1.2 - 1)
    assert s["max_dd"] == pytest.approx(-0.5)
    assert s["cagr"] == pytest.approx((1.1 * 0.5 * 1.2) ** 4 - 1)
    assert backtest.stats([])["cagr"] is None
