from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

from . import config


def price_path(ticker: str) -> Path:
    return config.PRICES_DIR / f"{ticker.upper()}.csv"


def _fmt(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.4f}".rstrip("0").rstrip(".")


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_prices(ticker: str) -> list[dict]:
    """Rows sorted by date: {date, close: float, volume: float | None}."""
    out = []
    for r in _read_csv(price_path(ticker)):
        out.append({
            "date": r["date"],
            "close": float(r["close"]),
            "volume": float(r["volume"]) if r.get("volume") else None,
        })
    return out


def upsert_prices(ticker: str, rows: Iterable[tuple[str, float, float | None]]) -> int:
    path = price_path(ticker)
    existing = {r["date"]: r for r in read_prices(ticker)}
    changed = 0
    for date, close, volume in rows:
        if close is None or close <= 0:
            continue
        cur = existing.get(date)
        if cur is None:
            existing[date] = {"date": date, "close": close, "volume": volume}
            changed += 1
        else:
            new_vol = volume if volume is not None else cur["volume"]
            if cur["close"] != close or cur["volume"] != new_vol:
                cur["close"], cur["volume"] = close, new_vol
                changed += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "close", "volume"])
        for d in sorted(existing):
            r = existing[d]
            w.writerow([d, _fmt(r["close"]), _fmt(r["volume"])])
    return changed


def read_series(path: Path) -> list[tuple[str, float]]:
    return [(r["date"], float(r["value"])) for r in _read_csv(path)]


def upsert_series(path: Path, rows: Iterable[tuple[str, float]]) -> None:
    existing = dict(read_series(path))
    for d, v in rows:
        if v is not None:
            existing[d] = v
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "value"])
        for d in sorted(existing):
            w.writerow([d, _fmt(existing[d])])


def nasi_path() -> Path:
    return config.DATA / "nasi.csv"


def market_path(name: str) -> Path:
    return config.DATA / "market" / name


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", newline="\n",
                                         delete=False, suffix=".tmp") as fh:
            temporary = Path(fh.name)
            json.dump(obj, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
