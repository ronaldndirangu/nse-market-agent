"""Prediction ledger: one row per stock per run with every signal, the tier and the projections.

Live rows go to data/rankings/live/YYYY-MM.csv and are append-only: a date already in the file is never
rewritten. Reconstructed (backtest) rankings go to data/rankings/reconstructed.csv and are regenerated.
"""
from __future__ import annotations

import csv
import os
import subprocess
from functools import lru_cache
from pathlib import Path

from . import config
from .returns import SIGNALS

BASE = ["date", "ticker", "rank", "tier", "composite"]
SIGNAL_COLS = [f"{s}_{k}" for s in SIGNALS for k in ("value", "z", "contribution")]
TAIL = ["price", "price_date", "mos", "agree", "agree_needed", "fair_low", "fair_base", "fair_high",
        "bear", "base", "bull", "horizon_years", "gate", "binding", "confidence", "weights", "code_sha"]
COLUMNS = BASE + SIGNAL_COLS + TAIL
TEXT = {"date", "ticker", "tier", "price_date", "gate", "binding", "confidence", "weights", "code_sha"}


def root() -> Path:
    return config.DATA / "rankings"


def live_path(day: str) -> Path:
    return root() / "live" / f"{day[:7]}.csv"


def reconstructed_path() -> Path:
    return root() / "reconstructed.csv"


@lru_cache(maxsize=1)
def code_sha() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"][:12]
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT, capture_output=True, text=True,
                             timeout=10, check=True)
        return out.stdout.strip()[:12]
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return format(v, ".6g")
    return str(v)


def rows_for(result: dict) -> list[dict]:
    weights = ";".join(f"{k}={v:g}" for k, v in config.settings()["ranking"]["weights"].items())
    out = []
    for t in result["ranking"]:
        r = result["rows"][t]
        fv, pr = r["fair_value"] or {}, r["projection"] or {}
        row = {"date": result["as_of"], "ticker": t, "rank": r["rank"], "tier": r["tier"],
               "composite": r["composite"]}
        for name, s in r["signals"].items():
            row[f"{name}_value"], row[f"{name}_z"], row[f"{name}_contribution"] = s["value"], s["z"], s["contribution"]
        row.update({
            "price": r["price"], "price_date": r["price_date"], "mos": r["mos"], "agree": len(r["agree"]),
            "agree_needed": r["agree_needed"], "fair_low": fv.get("low"), "fair_base": fv.get("base"),
            "fair_high": fv.get("high"), "bear": pr.get("bear"), "base": pr.get("base"), "bull": pr.get("bull"),
            "horizon_years": pr.get("years"), "gate": r["quality"]["gate"], "binding": r["binding"],
            "confidence": r["confidence"], "weights": weights, "code_sha": code_sha(),
        })
        out.append({c: _fmt(row.get(c)) for c in COLUMNS})
    return out


def _parse(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k in TEXT or k not in COLUMNS:
            out[k] = v
        elif v == "":
            out[k] = None
        else:
            out[k] = int(float(v)) if k in {"rank", "agree", "agree_needed", "horizon_years"} else float(v)
    return out


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [_parse(r) for r in csv.DictReader(fh)]


def _write(path: Path, rows: list[dict], mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = mode == "w" or not path.exists() or path.stat().st_size == 0
    with path.open(mode, newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)


def append(result: dict) -> int:
    """Append today's ranking to the live ledger. Returns rows written (0 if the date is already logged)."""
    path = live_path(result["as_of"])
    if any(r["date"] == result["as_of"] for r in _read(path)):
        return 0
    rows = rows_for(result)
    if rows:
        _write(path, rows, "a")
    return len(rows)


def write_reconstructed(results: list[dict]) -> int:
    rows = [r for res in results for r in rows_for(res)]
    _write(reconstructed_path(), rows, "w")
    return len(rows)


def read(kind: str = "live") -> list[dict]:
    if kind == "reconstructed":
        return _read(reconstructed_path())
    files = sorted((root() / "live").glob("*.csv")) if (root() / "live").exists() else []
    return [r for p in files for r in _read(p)]


def by_date(rows: list[dict]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        out.setdefault(r["date"], {})[r["ticker"]] = r
    return dict(sorted(out.items()))


def previous(day: str) -> tuple[str | None, dict[str, dict]]:
    """The latest live snapshot strictly before `day`."""
    snaps = by_date(read("live"))
    earlier = [d for d in snaps if d < day]
    return (earlier[-1], snaps[earlier[-1]]) if earlier else (None, {})
