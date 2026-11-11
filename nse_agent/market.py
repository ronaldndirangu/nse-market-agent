"""Price collection: AFX listing first, official NSE ticker API as fallback, cache last."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import config, storage
from .sources import afx, nse

log = logging.getLogger(__name__)
EAT = timezone(timedelta(hours=3))
MARKET_CLOSE_HOUR_EAT = 15


def _eat(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(EAT)
    except ValueError:
        return None


def update_daily(tickers: list[str] | None = None) -> dict:
    """Record today's close and volume for the universe plus the NASI level."""
    tickers = tickers or [s["ticker"] for s in config.universe()]
    snapshot: dict = {"source": None, "trade_date": None, "intraday": None, "rows": {}, "errors": []}
    try:
        listing = afx.fetch_listing()
        stamp = _eat(listing.as_of)
        if not listing.rows or stamp is None:
            raise ValueError("AFX listing returned no rows")
        snapshot.update(source="afx", trade_date=stamp.date().isoformat(),
                        intraday=stamp.hour < MARKET_CLOSE_HOUR_EAT, as_of=listing.as_of)
        for row in listing.rows:
            snapshot["rows"][row.ticker] = {
                "price": row.price, "volume": row.volume, "suspended": row.suspended, "name": row.name,
            }
        if listing.nasi:
            snapshot["nasi"] = listing.nasi
            storage.upsert_series(storage.nasi_path(), [(snapshot["trade_date"], listing.nasi)])
    except Exception as exc:  # noqa: BLE001 - any source failure triggers the fallback
        log.warning("AFX listing failed: %s; trying NSE ticker API", exc)
        snapshot["errors"].append(f"afx: {exc}")
        try:
            trade_date, rows = nse.fetch_snapshot()
            if not rows or not trade_date:
                raise ValueError("NSE ticker API returned no rows")
            snapshot.update(source="nse", trade_date=trade_date, intraday=None)
            for issuer, r in rows.items():
                snapshot["rows"][issuer] = {
                    "price": r.get("price"), "volume": r.get("volume"), "suspended": False,
                    "turnover": r.get("turnover"),
                }
        except Exception as exc2:  # noqa: BLE001
            log.error("NSE ticker API failed: %s; keeping cached prices", exc2)
            snapshot["errors"].append(f"nse: {exc2}")
            snapshot["source"] = "cache"
    if snapshot["source"] in ("afx", "nse"):
        for t in tickers:
            r = snapshot["rows"].get(t)
            if not r or r.get("price") is None or r.get("suspended"):
                continue
            volume = r.get("volume") if r.get("volume") is not None else 0.0
            storage.upsert_prices(t, [(snapshot["trade_date"], float(r["price"]), float(volume))])
        storage.write_json(storage.market_path("listing.json"), snapshot)
    return snapshot


def refresh_companies(tickers: list[str] | None = None) -> dict:
    """Fetch AFX company pages: last 10 sessions with volume, liquidity sentence, cross-check stats."""
    tickers = tickers or [s["ticker"] for s in config.universe()]
    path = storage.market_path("companies.json")
    data = storage.read_json(path, {}) or {}
    for t in tickers:
        try:
            page = afx.fetch_company(t)
        except Exception as exc:  # noqa: BLE001
            log.warning("AFX page for %s failed: %s", t, exc)
            if t in data:
                data[t]["stale"] = True
            continue
        storage.upsert_prices(t, page.history)
        data[t] = {
            "as_of": page.as_of,
            "afx_stats_third_party": page.stats,
            "perf": page.perf,
            "avg_session_turnover": page.avg_session_turnover,
            "avg_session_volume": page.avg_session_volume,
            "sector": page.sector,
            "industry": page.industry,
            "stale": False,
        }
        storage.write_json(path, data)
    return data


def backfill(tickers: list[str] | None = None, min_rows: int = 500) -> None:
    tickers = tickers or [s["ticker"] for s in config.universe()]
    for t in tickers:
        if len(storage.read_prices(t)) >= min_rows:
            log.info("%s already has history; skipping chart", t)
            continue
        try:
            closes = afx.fetch_chart(t)
            storage.upsert_prices(t, [(d, c, None) for d, c in closes])
            log.info("%s: %d closes", t, len(closes))
        except Exception as exc:  # noqa: BLE001
            log.warning("chart for %s failed: %s", t, exc)
    refresh_companies(tickers)
