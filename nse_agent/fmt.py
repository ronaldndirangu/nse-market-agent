"""Formatting helpers shared by the report, scorecard, backtest and simulation pages."""
from __future__ import annotations

import re


def pct(v: float | None, nd: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{nd}f}%"


def num(v: float | None, nd: int = 2) -> str:
    return "n/a" if v is None else f"{v:,.{nd}f}"


def kes(v: float | None, nd: int = 2) -> str:
    return "n/a" if v is None else f"KES {v:,.{nd}f}"


def estimate_reliable(row: dict) -> bool:
    if "estimate_reliable" in row:
        return bool(row["estimate_reliable"])
    models = row.get("models")
    count = models if isinstance(models, int) else len(models) if models is not None else 2
    return not row.get("dispersed", False) and count >= 2


def consumer_binding(row: dict) -> str:
    text = row.get("binding") or ""
    return text if estimate_reliable(row) else re.sub(r"\bbase return [^;]*", "projected return unclear", text)


def table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)
