"""Detect new results announcements and queue rule-based extractions for human review.

Nothing here writes to fundamentals.yaml. The workflow opens a pull request with the queue so a person can
check each figure against the source PDF before copying it across.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import date, timedelta

from . import announcements, config, http, storage

log = logging.getLogger(__name__)

# Line labels used in the CBK-prescribed bank disclosure format and in most listed-company result notices.
LABELS = {
    "net_income": r"profit\s+after\s+tax(ation)?|profit\s+for\s+the\s+(year|period)",
    "total_assets": r"total\s+assets",
    "total_equity": r"total\s+shareholders'?\s*(funds|equity)|shareholders'?\s+funds",
    "total_liabilities": r"total\s+liabilities",
    "revenue": r"total\s+(operating\s+)?income|revenue|turnover",
    "gross_npl": r"gross\s+non[- ]performing\s+loans",
    "gross_loans": r"gross\s+loans\s+and\s+advances",
    "eps": r"(basic\s+(and\s+diluted\s+)?)?earnings\s+per\s+share",
    "dps": r"dividends?\s+per\s+share",
}
NUMBER = re.compile(r"\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|\(?-?\d+\.\d+\)?|\(?-?\d+\)?")
MAX_AGE_DAYS = 60


def parse_number(tok: str) -> float:
    neg = tok.startswith("(") and tok.endswith(")") or tok.lstrip("(").startswith("-")
    v = float(tok.strip("()").lstrip("-").replace(",", ""))
    return -v if neg else v


def extract(text: str) -> dict[str, list[list[float]]]:
    """Return candidate figures per label: one list of numbers for every matching line, in column order."""
    found: dict[str, list[list[float]]] = {}
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        for key, pat in LABELS.items():
            m = re.search(rf"^\s*(\d+(\.\d+)*\s+)?({pat})\b", line, re.I)
            if not m:
                continue
            nums = [parse_number(t) for t in NUMBER.findall(line[m.end():])]
            nums = [n for n in nums if not (n.is_integer() and 1900 <= n <= 2100)]
            rows = found.setdefault(key, []) if nums else []
            if nums and nums[:6] not in rows:
                rows.append(nums[:6])
            break
    return found


def pdf_text(url: str) -> str:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    data = http.request("GET", url, timeout=90).content
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:12])


def queue_path():
    return config.DATA / "results_queue.yaml"


def run_results_watch(today: date | None = None) -> str:
    import yaml

    today = today or date.today()
    try:
        upd = announcements.update(today)
        log.info("announcements: %d new, %d total", len(upd["new"]), upd["total"])
    except Exception as exc:
        log.warning("announcement fetch failed: %s", exc)
    data = storage.read_json(announcements.path(), {}) or {}
    items = data.get("items", [])
    queue = config.load_yaml(queue_path()) if queue_path().exists() else None
    queue = queue or {"note": "Rule-based extractions awaiting human review. Copy verified figures into "
                              "data/fundamentals.yaml (KES millions) with the source URL, then delete the entry.",
                      "items": []}
    queued, stale, failed = [], 0, 0
    cutoff = (today - timedelta(days=MAX_AGE_DAYS)).isoformat()
    for item in items:
        if item.get("status") != "new" or not item.get("results") or not item.get("ticker"):
            continue
        if item["date"] < cutoff:
            item["status"] = "stale"
            stale += 1
            continue
        entry = {"ticker": item["ticker"], "title": item["title"], "url": item["url"], "date": item["date"],
                 "detected": {}, "status": "needs review"}
        if item["url"].lower().endswith(".pdf"):
            try:
                entry["detected"] = extract(pdf_text(item["url"]))
                entry["units"] = "as printed in the source, usually KES thousands; convert to KES millions"
            except Exception as exc:
                log.warning("%s: PDF parse failed: %s", item["url"], exc)
                entry["error"] = f"PDF parse failed: {type(exc).__name__}"
                failed += 1
        else:
            entry["error"] = "not a PDF link; open the announcement and transcribe manually"
        queue["items"].append(entry)
        item["status"] = "queued"
        queued.append(item["ticker"])
    if queued:
        queue_path().write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True), encoding="utf-8",
                                newline="\n")
    if queued or stale:
        storage.write_json(announcements.path(), data)
    return f"queued={len(queued)} ({', '.join(queued) or 'none'}) stale={stale} parse_failures={failed}"
