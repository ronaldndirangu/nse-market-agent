"""Formatting helpers shared by the report, scorecard, backtest and simulation pages."""
from __future__ import annotations


def pct(v: float | None, nd: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{nd}f}%"


def num(v: float | None, nd: int = 2) -> str:
    return "n/a" if v is None else f"{v:,.{nd}f}"


def kes(v: float | None, nd: int = 2) -> str:
    return "n/a" if v is None else f"KES {v:,.{nd}f}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)
