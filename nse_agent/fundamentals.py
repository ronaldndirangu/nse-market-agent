"""Sourced fundamentals. Values are never estimated: a missing field stays missing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import config

# Canonical value keys. Amounts in KES millions, per-share in KES, ratios as decimals, shares in millions.
KEYS = (
    "revenue", "gross_profit", "ebit", "net_income", "eps", "dps", "total_assets", "total_liabilities",
    "total_equity", "current_assets", "current_liabilities", "retained_earnings", "long_term_debt",
    "operating_cash_flow", "shares_outstanding", "bvps", "npl_ratio",
)


@dataclass
class Period:
    ticker: str
    period: str
    period_end: date
    published: date
    type: str
    source_url: str
    values: dict = field(default_factory=dict)
    source_note: str = ""

    def get(self, key: str) -> float | None:
        v = self.values.get(key)
        if v is not None:
            return float(v)
        shares = self.values.get("shares_outstanding")
        if key == "bvps" and shares and self.values.get("total_equity") is not None:
            return float(self.values["total_equity"]) / float(shares)
        if key == "eps" and shares and self.values.get("net_income") is not None:
            return float(self.values["net_income"]) / float(shares)
        return None


def _date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def path() -> Path:
    return config.DATA / "fundamentals.yaml"


@lru_cache(maxsize=4)
def _load(p: str) -> dict[str, dict]:
    raw = (config.load_yaml(Path(p)) or {}) if Path(p).exists() else {}
    out: dict[str, dict] = {}
    for ticker, comp in (raw.get("companies") or {}).items():
        periods = []
        for rec in comp.get("periods") or []:
            vals = {k: v for k, v in (rec.get("values") or {}).items() if v is not None}
            periods.append(Period(
                ticker=ticker, period=str(rec["period"]), period_end=_date(rec["period_end"]),
                published=_date(rec["published"]), type=rec.get("type", "annual"),
                source_url=rec.get("source_url", ""), values=vals, source_note=rec.get("source_note", ""),
            ))
        periods.sort(key=lambda x: x.period_end)
        out[ticker] = {"meta": {k: v for k, v in comp.items() if k != "periods"}, "periods": periods}
    return out


def load() -> dict[str, dict]:
    return _load(str(path()))


def annuals(ticker: str, as_of: date | None = None) -> list[Period]:
    comp = load().get(ticker)
    if not comp:
        return []
    return [p for p in comp["periods"] if p.type == "annual" and (as_of is None or p.published <= as_of)]


def latest_interim(ticker: str, as_of: date | None = None) -> Period | None:
    comp = load().get(ticker)
    if not comp:
        return None
    rows = [p for p in comp["periods"] if p.type != "annual" and (as_of is None or p.published <= as_of)]
    return rows[-1] if rows else None


def roe(periods: list[Period], idx: int) -> float | None:
    p = periods[idx]
    ni, eq = p.get("net_income"), p.get("total_equity")
    if ni is None or not eq:
        eps, bvps = p.get("eps"), p.get("bvps")
        return eps / bvps if eps is not None and bvps else None
    if idx > 0 and periods[idx - 1].get("total_equity"):
        eq = (eq + periods[idx - 1].get("total_equity")) / 2
    return ni / eq


def avg(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None
