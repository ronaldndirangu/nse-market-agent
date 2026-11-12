"""Immutable report revisions and links to the unchanged official prediction ledger."""
from __future__ import annotations

import csv
import hashlib
import json
import logging

from . import config, ledger, storage


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def ledger_reference(result: dict) -> dict:
    path = ledger.live_path(result["as_of"])
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["date"] == result["as_of"]]
    rows.sort(key=lambda r: r["ticker"])
    current = {r["ticker"]: r for r in ledger.rows_for(result)}
    differences = []
    for old in rows:
        new = current.get(old["ticker"]) or {}
        changed = [key for key in ("rank", "tier", "price", "base", "mos") if old.get(key) != new.get(key)]
        if changed:
            differences.append({"ticker": old["ticker"], "fields": changed})
    return {"path": path.relative_to(config.ROOT).as_posix(), "date": result["as_of"], "rows": len(rows),
            "sha256": _digest(rows), "code_sha": rows[0].get("code_sha") if rows else None,
            "differences": differences}


def write(snapshot: dict, result: dict) -> tuple[dict, list[str]]:
    folder = config.REPORTS / "daily"
    snapshot["code_sha"] = ledger.code_sha()
    snapshot["ledger"] = ledger_reference(result)
    revision = _digest(snapshot)[:20]
    snapshot["revision"] = revision
    relative = f"snapshots/{revision}.json"
    immutable = folder / relative
    if immutable.exists():
        if storage.read_json(immutable, None) != snapshot:
            raise ValueError(f"Report revision collision: {revision}")
    else:
        storage.write_json(immutable, snapshot)
    storage.write_json(folder / "latest.json", snapshot)
    storage.write_json(folder / "manifest.json", {
        "revision": revision, "snapshot": relative, "as_of": snapshot["as_of"],
        "generated": snapshot["generated"], "ledger": snapshot["ledger"],
    })
    events_path = folder / "events.json"
    events = storage.read_json(events_path, []) or []
    known = {event["id"] for event in events}
    fresh_alerts = []
    day = snapshot["as_of"]
    for text in snapshot["alerts"]:
        kind, _, remainder = text.partition(": ")
        ticker = remainder.split(" ", 1)[0].rstrip(".")
        key = _digest([day, kind, ticker, text if kind.startswith("Warning") else ""])
        if key in known:
            continue
        fresh_alerts.append(text)
        events.append({"id": key, "date": day, "updated": snapshot["generated"], "text": text})
        known.add(key)
    daily_id = f"daily-{day}"
    if daily_id not in known:
        counts = snapshot["counts"]
        events.append({"id": daily_id, "date": day, "updated": snapshot["generated"],
                       "text": f"Daily brief: {counts['Buy']} Buy, {counts['Watch']} Watch. Not financial advice."})
    storage.write_json(events_path, events[-100:])
    return snapshot, fresh_alerts


def validate(snapshot: dict, manifest: dict) -> None:
    if manifest["revision"] != snapshot["revision"] or manifest["as_of"] != snapshot["as_of"]:
        raise ValueError("Publication manifest does not match the daily snapshot")
    if manifest["snapshot"] != f"snapshots/{snapshot['revision']}.json":
        raise ValueError("Invalid immutable snapshot reference")
    original = storage.read_json(config.REPORTS / "daily" / manifest["snapshot"], None)
    if original != snapshot:
        raise ValueError("Immutable report revision does not match latest.json")
    body = {k: v for k, v in snapshot.items() if k != "revision"}
    if _digest(body)[:20] != snapshot["revision"]:
        raise ValueError("Report revision checksum failed")
    reference = manifest["ledger"]
    path = config.ROOT / reference["path"]
    if path.resolve() != ledger.live_path(reference["date"]).resolve():
        raise ValueError("Invalid prediction ledger reference")
    if reference["rows"]:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = sorted((r for r in csv.DictReader(fh) if r["date"] == reference["date"]),
                          key=lambda r: r["ticker"])
        if len(rows) != reference["rows"] or _digest(rows) != reference["sha256"]:
            raise ValueError("Official prediction ledger checksum failed")


def check_published(url: str) -> str:
    from . import health, http

    status = http.request("GET", url.rstrip("/") + "/status.json", timeout=15).json()
    expected = health.expected_session(health.now()).isoformat()
    if not status.get("as_of") or status["as_of"] < expected:
        raise ValueError(f"Published daily brief is overdue: {status.get('as_of')}, expected {expected}")
    live = status.get("health")
    if not live:
        raise ValueError("Published report has no live data-health assessment")
    issues = [name for name in ("announcements", "macro") if live[name]["status"] != "Current"]
    if live["prices"]["status"] not in ("Current", "Delayed"):
        issues.append("prices")
    if issues:
        raise ValueError("Published evidence needs attention: " + ", ".join(issues))
    if live["prices"]["status"] == "Delayed":
        logging.getLogger(__name__).warning("Prices are delayed; check for a public holiday or source lag")
    return f"Published revision {status.get('revision')} dated {status['as_of']}"
