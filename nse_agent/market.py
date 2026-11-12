"""Price collection: AFX listing first, official NSE ticker API as fallback, cache last."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import config, storage
from .sources import afx, nse

log = logging.getLogger(__name__)
EAT = timezone(timedelta(hours=3))
MARKET_CLOSE_HOUR_EAT = 15
MIN_AFX_COVERAGE = 0.5


def _eat(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(EAT)
    except ValueError:
        return None


def _from_afx(tickers: list[str]) -> dict:
    listing = afx.fetch_listing()
    stamp = _eat(listing.as_of)
    if not listing.rows or stamp is None:
        raise ValueError("AFX listing returned no rows")
    # A blank AFX volume means no trades in the session.
    rows = {
        row.ticker: {"price": row.price, "volume": row.volume if row.volume is not None else 0.0,
                     "suspended": row.suspended, "name": row.name}
        for row in listing.rows
    }
    covered = sum(1 for t in tickers if t in rows)
    if tickers and covered < MIN_AFX_COVERAGE * len(tickers):
        raise ValueError(f"AFX listing covers only {covered} of {len(tickers)} universe tickers")
    return {"source": "afx", "trade_date": stamp.date().isoformat(), "as_of": listing.as_of,
            "intraday": stamp.hour < MARKET_CLOSE_HOUR_EAT, "rows": rows, "nasi": listing.nasi}


def _now_eat() -> datetime:
    return datetime.now(EAT)


def _from_nse() -> dict:
    trade_date, rows, status = nse.fetch_snapshot()
    if not rows or not trade_date:
        raise ValueError("NSE ticker API returned no rows")
    if status:
        intraday = status != "closed"
    else:
        now = _now_eat()
        intraday = trade_date >= now.date().isoformat() and now.hour < MARKET_CLOSE_HOUR_EAT
    # `today_close` is the official close; `price` is the last trade. A missing volume stays unknown.
    # The ticker API carries no suspension flag, so suspension stays unknown (None).
    return {"source": "nse", "trade_date": trade_date, "market_status": status, "intraday": intraday,
            "rows": {issuer: {"price": r["today_close"] if r.get("today_close") is not None else r.get("price"),
                              "volume": r.get("volume"), "suspended": None, "turnover": r.get("turnover")}
                     for issuer, r in rows.items()}}


def _carry_suspension(snapshot: dict, previous: dict) -> None:
    """Keep the last known suspension flag when the new source has none, unless the stock traded today."""
    rows = snapshot["rows"]
    for t, old in (previous.get("rows") or {}).items():
        if old.get("suspended") is None:
            continue
        new = rows.get(t)
        if new is None:
            if old["suspended"]:
                rows[t] = {"price": None, "volume": None, "suspended": True,
                           "suspended_as_of": old.get("suspended_as_of") or previous.get("trade_date")}
            continue
        if new.get("suspended") is not None:
            continue
        if new.get("volume"):
            new["suspended"] = False
        else:
            new["suspended"] = old["suspended"]
            new["suspended_as_of"] = old.get("suspended_as_of") or previous.get("trade_date")


def update_daily(tickers: list[str] | None = None) -> dict:
    """Record today's close and volume for the universe plus the NASI level.

    Tries AFX, then the NSE ticker API. An intraday snapshot never overwrites stored closes;
    it only refreshes listing.json (suspension flags) when no closing snapshot is available.
    """
    tickers = tickers or [s["ticker"] for s in config.universe()]
    snapshot: dict = {"source": None, "trade_date": None, "intraday": None, "rows": {}, "errors": []}
    intraday_snap = None
    for name, fetch in (("afx", lambda: _from_afx(tickers)), ("nse", _from_nse)):
        try:
            got = fetch()
        except Exception as exc:  # noqa: BLE001 - any source failure triggers the next source
            log.warning("%s price source failed: %s", name, exc)
            snapshot["errors"].append(f"{name}: {exc}")
            continue
        if got["intraday"]:
            log.warning("%s snapshot for %s is intraday; trying the next source", name, got["trade_date"])
            snapshot["errors"].append(f"{name}: intraday snapshot for {got['trade_date']}")
            intraday_snap = intraday_snap or got
            continue
        snapshot.update(got)
        break
    else:
        if intraday_snap:
            snapshot.update(intraday_snap)
        else:
            log.error("no price source succeeded; keeping cached prices")
            snapshot["source"] = "cache"
    if snapshot["source"] in ("afx", "nse"):
        listing_path = storage.market_path("listing.json")
        _carry_suspension(snapshot, storage.read_json(listing_path, {}) or {})
        if not snapshot["intraday"]:
            for t in tickers:
                r = snapshot["rows"].get(t)
                if not r or r.get("price") is None or r.get("suspended"):
                    continue
                volume = float(r["volume"]) if r.get("volume") is not None else None
                storage.upsert_prices(t, [(snapshot["trade_date"], float(r["price"]), volume)])
            if snapshot.get("nasi"):
                storage.upsert_series(storage.nasi_path(), [(snapshot["trade_date"], snapshot["nasi"])])
        storage.write_json(listing_path, snapshot)
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
