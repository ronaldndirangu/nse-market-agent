import math
import random
from datetime import date

import pytest

from nse_agent import backtest, fundamentals, rates, shadow, simulate, site, strategy
from nse_agent.engine import analyze
from tests.test_daily import _write, outputs  # noqa: F401
from tests.test_pipeline import AS_OF, market  # noqa: F401


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
    ({}, {}, 0.0), ({}, {"A": 1.0}, 1.0), ({"A": 0.5, "B": 0.5}, {"A": 0.5, "B": 0.5}, 0.0),
    ({"A": 0.5, "B": 0.5}, {"C": 0.5, "D": 0.5}, 2.0), ({"A": 0.5, "B": 0.5}, {"A": 0.5, "C": 0.5}, 1.0),
    ({"A": 1.0}, {}, 1.0),
])
def test_turnover(old, new, expected):
    assert strategy.turnover(old, new) == pytest.approx(expected)


def test_book_charges_first_purchase_and_drift_on_unchanged_names():
    book = strategy.Book()
    g = book.step({"A": 0.5, "B": 0.25}, {"A": 0.2, "B": 0.0}, cash=0.01)
    assert g == pytest.approx(0.5 * 0.2 + 0.25 * 0.01)
    assert book.turnover == [pytest.approx(0.75)]
    book.step({"A": 0.5, "B": 0.25}, {"A": 0.0, "B": 0.0}, cash=0.0)
    assert book.turnover[1] == pytest.approx(abs(0.5 - 0.6 / (1 + g)) + abs(0.25 - 0.25 / (1 + g)))
    assert book.net(0.02)[0] == pytest.approx((1 - 0.02 * 0.75) * (1 + g) - 1)


def _row(price, base, high=None, gate="pass", dispersed=False):
    return {"price": price, "fair_value": {"base": base, "high": high or base * 1.2}, "dispersed": dispersed,
            "quality": {"gate": gate}}


def test_rules_use_buys_hold_to_fair_value_tilt_and_skip_expensive():
    assert strategy.buy_rule({"buys": ["A"], "picks": ["A", "B"]}, {"A", "B"}, 3) == {"A": 1.0}
    rows = {"A": _row(90, 100), "B": _row(101, 100), "C": _row(50, 80), "D": _row(130, 100, 110),
            "E": _row(130, 100, 110, dispersed=True)}
    assert strategy.hold(["A", "B"], {"rows": rows, "buys": ["C"]}, set(rows), 3) == ["A", "C"]
    assert strategy.tilt({"A": 0.6, "B": 0.4}, ["B"], 2.0) == {"A": pytest.approx(0.6 / 1.4),
                                                                 "B": pytest.approx(0.8 / 1.4)}
    kept, dropped = strategy.skip_expensive({"A": 0.5, "D": 0.3, "E": 0.2}, rows)
    assert dropped == ["D"] and kept == {"A": pytest.approx(0.5 / 0.7), "E": pytest.approx(0.2 / 0.7)}


def test_quarterly_tilt_trades_only_in_rebalance_months_outside_the_band():
    res = {"buys": ["B"], "rows": {"A": _row(90, 100), "B": _row(90, 100)}}
    core, held = {"A": 0.5, "B": 0.5}, {"A": 0.5, "B": 0.5}
    targets, signals, _ = strategy.experiments(res, date(2026, 3, 1), core, {"A", "B"}, [], held)
    assert targets["tilt_quarterly"] == held and not signals["tilt_quarterly"] and signals["tilt"]
    targets, signals, _ = strategy.experiments(res, date(2026, 5, 1), core, {"A", "B"}, [], held)
    assert targets["tilt_quarterly"] == targets["tilt"] == {"A": pytest.approx(1 / 3), "B": pytest.approx(2 / 3)}
    assert signals["tilt_quarterly"]


def test_share_counts_rebase_for_bonus_and_merger_and_backfill(outputs):
    _write(outputs, "fundamentals.yaml", {"companies": {"TST": {"periods": [
        {"period": "FY2025", "period_end": "2025-12-31", "published": "2026-03-31", "type": "annual",
         "source_url": "https://example.test/r.pdf", "values": {"shares_outstanding": 100}}]}}})
    _write(outputs, "corporate_actions.yaml", {"actions": [
        {"ticker": "TST", "type": "bonus", "ratio": "1:1", "factor": 0.5, "ex_date": "2026-06-01",
         "source_url": "https://example.test/bonus.pdf"},
        {"ticker": "TST", "type": "merger", "factor": 1.0, "ex_date": "2026-04-15", "shares_issued_m": 50,
         "source_url": "https://example.test/merger.pdf"}]})
    fundamentals._load.cache_clear()
    try:
        assert strategy.shares_at("TST", date(2026, 1, 15)) == (pytest.approx(100), True)
        assert strategy.shares_at("TST", date(2026, 4, 1)) == (pytest.approx(100), False)
        assert strategy.shares_at("TST", date(2026, 5, 1)) == (pytest.approx(150), False)
        assert strategy.shares_at("TST", date(2026, 7, 1)) == (pytest.approx(300), False)
    finally:
        (outputs / "data" / "fundamentals.yaml").unlink(missing_ok=True)


def test_gate_needs_every_check_before_human_review():
    steady = [0.01 + 0.001 * math.sin(i) for i in range(40)]
    ready = strategy.gate(steady, steady, 40, {"months": 24, "excess": 0.1})
    assert ready["status"] == "Ready for human review" and ready["ci"][0] > 0
    early = strategy.gate(steady, steady, 40, {"months": 3, "excess": 0.1})
    assert early["status"] == "Not adopted (3 of 4 checks met)" and not early["checks"]["live"]
    assert not strategy.gate(steady, [-x for x in steady], 12, None)["checks"]["cost_stress"]


def test_backtest_uses_dated_rates_for_cash_and_hurdle(market, outputs):
    base = backtest.backtest(end=AS_OF)
    first = base["months"][0]
    assert first["cash_rate"] == pytest.approx(0.08 * 0.85) and first["hurdle"] == pytest.approx(0.09 * 0.85 + 0.05)
    assert all(abs(sum(strategy.cap_weights(["EQTY", "KCB", "ABSA"], date.fromisoformat(m["date"]))[0].values())
                   - 1) < 1e-9 for m in base["months"])
    history = rates.history()
    for r in history:
        if r["month"] == "2026-05":
            r.update(tbill_91d=0.12, tbill_364d=0.5)
    rates.save(history)
    bumped = {m["date"]: m for m in backtest.backtest(end=AS_OF)["months"]}
    assert bumped["2026-06-01"]["cash_rate"] == pytest.approx(0.12 * 0.85)
    before = {m["date"]: m for m in base["months"]}["2026-06-01"]
    assert "EQTY" in before["buys"]
    assert bumped["2026-06-01"]["hurdle"] == pytest.approx(0.5 * 0.85 + 0.05)
    assert "EQTY" not in bumped["2026-06-01"]["buys"] and "EQTY" in bumped["2026-06-01"]["undervalued_below_hurdle"]
    assert bumped["2026-07-01"]["cash_rate"] == pytest.approx(0.08 * 0.85)
    text = backtest.render(base)
    for heading in ("## Result", "## What a fixed mix would have become", "## Shadow experiments", "## Limitations"):
        assert heading in text
    summary = site._backtest_summary(backtest._slim(base))
    assert "Did the Buy rule pay off?" in summary and "<polyline" in summary


def test_shadow_log_writes_once_a_month_and_scores_completed_months(market, outputs):
    try:
        assert shadow.append(analyze(date(2026, 10, 1))) > 0
        assert shadow.append(analyze(date(2026, 10, 2))) == 0
        assert shadow.append(analyze(AS_OF)) > 0
        for month, entry in shadow.logged().items():
            assert set(entry["rules"]) == {"core", "buy_rule", *strategy.EXPERIMENTS}
        cash = {r["rule"]: float(r["weight"]) for r in shadow.read() if r["ticker"] == shadow.CASH}
        assert cash["core"] == pytest.approx(0.0, abs=1e-6)
        scored = shadow.score()
        assert set(scored) == {"buy_rule", *strategy.EXPERIMENTS}
        assert all(s["months"] == 1 and s["excess"] is not None for s in scored.values())
    finally:
        shadow.path().unlink(missing_ok=True)


def test_stats():
    s = backtest.stats([0.1, -0.5, 0.2])
    assert s["total"] == pytest.approx(1.1 * 0.5 * 1.2 - 1)
    assert s["max_dd"] == pytest.approx(-0.5)
    assert s["cagr"] == pytest.approx((1.1 * 0.5 * 1.2) ** 4 - 1)
    assert backtest.stats([])["cagr"] is None
