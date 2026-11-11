"""Append-only log of recommendations so later runs can score them."""
from __future__ import annotations

import csv

from . import config

FIELDS = ["date", "ticker", "rank", "price", "fair_low", "fair_base", "fair_high", "mos", "bear", "base", "bull",
          "buy", "confidence", "composite"]


def path():
    return config.DATA / "picks.csv"


def read() -> list[dict]:
    p = path()
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v: float | None, nd: int = 4) -> str:
    return "" if v is None else f"{v:.{nd}f}"


def log(result: dict) -> int:
    """Record every undervalued pick for the run date, replacing any earlier rows for that date."""
    keep = [r for r in read() if r["date"] != result["as_of"]]
    new = []
    for t in result["picks"]:
        r = result["rows"][t]
        fv, pr = r["fair_value"], r["projection"]
        new.append({
            "date": result["as_of"], "ticker": t, "rank": r["rank"], "price": _f(r["price"], 2),
            "fair_low": _f(fv["low"], 2), "fair_base": _f(fv["base"], 2), "fair_high": _f(fv["high"], 2),
            "mos": _f(r["mos"]), "bear": _f(pr["bear"]), "base": _f(pr["base"]), "bull": _f(pr["bull"]),
            "buy": "yes" if r["buy"] else "no", "confidence": r["confidence"], "composite": _f(r["composite"]),
        })
    rows = sorted(keep + new, key=lambda x: (x["date"], int(x["rank"])))
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(new)
