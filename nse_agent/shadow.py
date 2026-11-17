"""Live shadow log of the frozen portfolio experiments.

On the first verified daily run of each month the target weights of every rule are appended to
data/shadow/experiments.csv and never rewritten. Completed months are scored with the same accounting as the
backtest, so the adoption gate's live check uses outcomes nobody could have seen when the rules were frozen.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from . import config, dividends, prices, strategy

FIELDS = ["month", "price_date", "rule", "ticker", "weight", "version"]
CASH = "CASH"


def path() -> Path:
    return config.DATA / "shadow" / "experiments.csv"


def read() -> list[dict]:
    if not path().exists():
        return []
    with path().open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def logged() -> dict[str, dict]:
    """month -> {"price_date": str, "rules": {rule: {ticker: weight}}}, cash excluded."""
    out: dict[str, dict] = {}
    for r in read():
        m = out.setdefault(r["month"], {"price_date": r["price_date"], "rules": {}})
        weights = m["rules"].setdefault(r["rule"], {})
        if r["ticker"] != CASH:
            weights[r["ticker"]] = float(r["weight"])
    return dict(sorted(out.items()))


def _cash(a: date, b: date) -> float:
    m = config.macro(a)
    return m["risk_free"]["tbill_91d"]["value"] * (1 - m["taxes_and_costs"]["tbill_interest_wht"]) * (b - a).days / 365


def append(result: dict) -> int:
    """Log this month's targets once. Returns rows written."""
    month = result["as_of"][:7]
    history = logged()
    if month in history:
        return 0
    x = config.settings()["experiments"]
    as_of = date.fromisoformat(result["as_of"])
    ok = {u["ticker"] for u in config.universe() if prices.last_close(u["ticker"], as_of)}
    core, _ = strategy.cap_weights(sorted(ok), as_of)
    if not core:
        return 0
    prev = history[max(history)] if history else None
    held_quarterly = None
    if prev:
        a = date.fromisoformat(prev["price_date"])
        weights = prev["rules"].get("tilt_quarterly", {})
        book = strategy.Book()
        book.step(weights, {t: dividends.total_return(t, a, as_of) or 0.0 for t in weights}, _cash(a, as_of))
        held_quarterly = book.drifted(ok)
    prev_hold = list((prev or {}).get("rules", {}).get("buy_hold", {}))
    targets, _, _ = strategy.experiments(result, as_of, core, ok, prev_hold, held_quarterly)
    targets = {"core": core, "buy_rule": strategy.buy_rule(result, ok, x["top"]), **targets}
    rows = []
    for rule, weights in targets.items():
        weights = {t: w for t, w in weights.items() if w > 1e-12}
        rows += [{"month": month, "price_date": result["as_of"], "rule": rule, "ticker": t, "weight": f"{w:.6f}",
                  "version": x["version"]} for t, w in sorted(weights.items())]
        rows.append({"month": month, "price_date": result["as_of"], "rule": rule, "ticker": CASH,
                     "weight": f"{max(0.0, 1 - sum(weights.values())):.6f}", "version": x["version"]})
    path().parent.mkdir(parents=True, exist_ok=True)
    new = not path().exists()
    with path().open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


def score() -> dict[str, dict]:
    """Completed live months per rule: months scored, return after costs and the gain over the core basket."""
    history = list(logged().values())
    if len(history) < 2:
        return {}
    cost = config.macro()["taxes_and_costs"]["trade_cost_per_side"]
    rules = sorted({r for m in history for r in m["rules"]})
    books = {r: strategy.Book() for r in rules}
    for start, stop in zip(history, history[1:]):
        a, b = date.fromisoformat(start["price_date"]), date.fromisoformat(stop["price_date"])
        tickers = {t for w in start["rules"].values() for t in w}
        rets = {t: dividends.total_return(t, a, b) or 0.0 for t in tickers}
        cash = _cash(a, b)
        for r, book in books.items():
            book.step(start["rules"].get(r, {}), rets, cash)
    wealth = {}
    for r, book in books.items():
        w = 1.0
        for x in book.net(cost):
            w *= 1 + x
        wealth[r] = w
    core = wealth.get("core")
    return {r: {"months": len(history) - 1, "return": w - 1,
                "excess": w - core if core is not None else None} for r, w in wealth.items() if r != "core"}
