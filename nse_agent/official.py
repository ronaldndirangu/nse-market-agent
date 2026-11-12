"""Dated official inputs. Financial statements remain subject to human review."""
from __future__ import annotations

import logging
import math
import re
from datetime import date
from html import escape

import requests
from pypdf.errors import PdfReadError

from . import config, http, storage
from .fmt import pct
from .http import Page, trusted_link

log = logging.getLogger(__name__)
CBK = "https://www.centralbank.go.ke/bills-bonds/treasury-bills/"
KNBS = "https://www.knbs.or.ke/"
MONTHS = "January February March April May June July August September October November December".split()


def parse_cbk(text: str, today: date) -> dict:
    sections = re.split(r"(?m)^\s*[BC]\.\s+", text)
    if len(sections) < 3 or not re.search(r"Tenor\s+91\s+DAYS\s+182\s+DAYS\s+364\s+DAYS", sections[0], re.I):
        raise ValueError("CBK tenor columns or comparative sections are missing")
    signature = re.search(r"Director,\s*Financial Markets\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})", text)
    if not signature:
        raise ValueError("CBK signed release date is missing")
    from datetime import datetime
    released = datetime.strptime(signature[1].replace(",", ""), "%B %d %Y").date()
    if released > today:
        raise ValueError("CBK release date is in the future")
    issued = re.search(r"DATED\s+(\d{2}/\d{2}/\d{4})", sections[0])
    issues = re.search(r"ISSUES\s+(\d+)/091,\s*(\d+)/182\s*&\s*(\d+)/364", sections[0], re.I)
    if not issued or not issues:
        raise ValueError("CBK issue identifiers are missing")
    row = re.search(r"(?m)^\s*Weighted Average Interest Rate of\s+([^\n]+)\n\s*accepted bids", sections[0], re.I)
    if not row:
        raise ValueError("CBK accepted-bid row is missing")
    accepted = re.findall(r"\d+(?:\.\d+)?%|(?<!\S)-(?!\S)", row[1])
    if len(accepted) != 3:
        raise ValueError("CBK accepted-bid columns are ambiguous")
    rates = {}
    for tenor, value, issue in zip(("91", "182", "364"), accepted, issues.groups()):
        match = re.search(rf"(?m)^\s*{tenor}\s*-\s*day\s+(\S+)\s+(\S+)", sections[1], re.I)
        if not match:
            raise ValueError(f"CBK comparative rate missing for {tenor} days")
        if value == "-" or float(value.rstrip("%")) == 0:
            if match[1] not in ("-", "0", "0.0000"):
                raise ValueError("CBK missing-tenor rows disagree")
            continue
        rate = float(value.rstrip("%")) / 100
        if not math.isfinite(rate) or not 0.01 <= rate <= 0.30 or abs(rate - float(match[1]) / 100) > 1e-8:
            raise ValueError("CBK accepted and comparative rates disagree or need manual verification")
        rates[tenor] = {"value": rate, "issue": int(issue)}
    if not rates:
        raise ValueError("CBK accepted no usable bids")
    return {"released": released.isoformat(), "issue_date": datetime.strptime(issued[1], "%d/%m/%Y").date().isoformat(),
            "rates": rates}


def collect_cbk(today: date) -> dict:
    page = Page(http.get_text(CBK))
    links = [trusted_link(CBK, u) for u in page.links
             if "91_day_historical_treasury_bill_results/" in u and u.lower().endswith(".pdf")]
    if not links:
        raise ValueError("CBK results links are missing")
    candidates = []
    for url in dict.fromkeys(links):
        match = re.search(r"DATED%20(\d{2})-(\d{2})-(\d{4})", url, re.I)
        if match:
            candidates.append((date(int(match[3]), int(match[2]), int(match[1])), url))
    if not candidates:
        raise ValueError("CBK issue-date links could not be ordered")
    document = http.pdf_document(max(candidates)[1])
    return parse_cbk(document["text"], today) | {"source": document["url"], "sha256": document["sha256"],
                                               "observed_on": today.isoformat()}


def parse_cpi(html: str, url: str, today: date) -> dict:
    text = " ".join(" ".join(Page(html).parts).split())
    match = re.search(r"Annual consumer price inflation was\s+(-?\d+(?:\.\d+)?)\s+per\s*cent\s+in\s+"
                      r"([A-Za-z]+)\s+(\d{4})", text, re.I)
    if not match or match[2].title() not in MONTHS:
        raise ValueError("KNBS annual CPI headline or period is missing")
    period = f"{int(match[3]):04d}-{MONTHS.index(match[2].title()) + 1:02d}"
    value = float(match[1]) / 100
    if period > today.strftime("%Y-%m") or not -0.5 < value < 1:
        raise ValueError("KNBS CPI period or value needs manual verification")
    if f"{match[2].lower()}-{match[3]}" not in url.lower():
        raise ValueError("KNBS headline and release URL periods disagree")
    return {"period": period, "value": value, "source": url, "observed_on": today.isoformat()}


def collect_cpi(today: date) -> dict:
    links = Page(http.get_text(KNBS)).links
    candidates = []
    for link in links:
        match = re.search(r"/reports/consumer-price-indices-and-inflation-rates-([a-z]+)-(\d{4})/?$", link, re.I)
        if match and match[1].title() in MONTHS:
            candidates.append((int(match[2]), MONTHS.index(match[1].title()), trusted_link(KNBS, link)))
    if not candidates:
        raise ValueError("KNBS monthly CPI release links are missing")
    url = max(candidates)[2]
    return parse_cpi(http.get_text(url), url, today)


def records(kind: str) -> list[dict]:
    return [storage.read_json(p) for p in sorted((config.DATA / "official" / kind).glob("*.json"))]


def save(kind: str, record: dict) -> bool:
    key = record["released"] if kind == "cbk" else record["period"]
    path = config.DATA / "official" / kind / f"{key}.json"
    prior = records(kind)
    if prior and key < max(r["released"] if kind == "cbk" else r["period"] for r in prior):
        raise ValueError("Official source regressed to an older release")
    previous = storage.read_json(path, None)
    if previous:
        ignored = {"observed_on", "sha256"}
        if {k: v for k, v in previous.items() if k not in ignored} != {
                k: v for k, v in record.items() if k not in ignored}:
            raise ValueError("An existing official release changed; human review is required")
        return False
    if kind == "cbk":
        for old in prior:
            for tenor, new in record["rates"].items():
                prev = old["rates"].get(tenor)
                if prev and new["issue"] <= prev["issue"]:
                    raise ValueError("CBK issue identifiers regressed or repeated")
                if prev and new["issue"] == prev["issue"] + 1 and abs(new["value"] - prev["value"]) > 0.015:
                    raise ValueError("CBK rate jump requires manual verification")
    storage.write_json(path, record)
    return True


def refresh(today: date | None = None) -> dict:
    from . import health
    today = today or health.now().date()
    outcomes = {}
    for kind, collect in (("cbk", collect_cbk), ("knbs", collect_cpi)):
        state = storage.read_json(storage.market_path("health.json"), {}) or {}
        previous = (state.get("official") or {}).get(kind) or {}
        attempt = {"last_attempt": health.now().isoformat(timespec="seconds"),
                   "last_success": previous.get("last_success")}
        try:
            record = collect(today)
            outcomes[kind] = "updated" if save(kind, record) else "unchanged"
            attempt.update(successful=True, last_success=attempt["last_attempt"])
        except (ValueError, requests.RequestException, PdfReadError) as exc:
            log.warning("%s official source failed: %s", kind, exc)
            outcomes[kind] = "failed"
            attempt.update(successful=False, error=str(exc))
        state.setdefault("official", {})[kind] = attempt
        storage.write_json(storage.market_path("health.json"), state)
    config.macro.cache_clear()
    return outcomes


def apply(m: dict, as_of: date) -> dict:
    for row in sorted(records("cbk"), key=lambda r: r["released"]):
        if max(row["released"], row["observed_on"]) > as_of.isoformat():
            continue
        for tenor, rate in row["rates"].items():
            key = f"tbill_{tenor}d"
            old = m["risk_free"][key]
            if row["released"] >= old.get("as_of", m["as_of"]):
                if not math.isfinite(rate["value"]) or not 0.01 <= rate["value"] <= 0.30:
                    raise ValueError("Invalid stored CBK rate")
                m["risk_free"][key] = rate | {"source": row["source"], "as_of": row["released"],
                                            "issue_date": row["issue_date"], "method": "automatic"}
    for row in sorted(records("knbs"), key=lambda r: r["period"]):
        existing = m["policy"]["inflation"]
        newest = (row["period"], row["observed_on"]) >= (
            existing.get("period", ""), existing.get("observed_on", ""))
        if row["observed_on"] <= as_of.isoformat() and newest:
            m["policy"]["inflation"] = {k: row[k] for k in ("value", "period", "source", "observed_on")}
            m["policy"]["inflation"]["method"] = "automatic"
    m["_source_status"] = (storage.read_json(storage.market_path("health.json"), {}) or {}).get("official", {})
    return m


def markdown(m: dict, net: float) -> list[str]:
    bill = m["risk_free"]["tbill_364d"]
    inflation = m["policy"]["inflation"]
    out = ["## Rates and inflation", "",
           f"- **T-bill source:** [CBK results]({bill['source']}), released {bill.get('as_of', 'date unavailable')}. "
           f"The accepted 364-day rate is {pct(bill['value'], 4)} gross. This feeds the net T-bill comparison "
           "and Buy hurdle; it does not change the ranking weights.",
           f"- **Inflation:** {pct(inflation['value'])} year-on-year for {inflation.get('period', 'period unavailable')} "
           f"([source]({inflation['source']})). This describes past price increases, not a forecast.",
           f"- **Purchasing power:** if inflation stayed at that rate, the net T-bill return would be about "
           f"{pct((1 + net) / (1 + inflation['value']) - 1)} after inflation. This is an illustration, "
           "comparing a future investment term with observed inflation. Stock projections remain nominal KES.",
           f"- **Separate assumptions:** the 10-year bond yield remains {pct(m['risk_free']['bond_10y']['value'], 2)}, "
           f"from an [approximate third-party source]({m['risk_free']['bond_10y']['source']}); "
           f"curated assumptions were reviewed {m['as_of']}. A new bill auction does "
           "not update bond yields, equity premiums or taxes.",
           "- **Price feed:** existing NSE/AFX sources. A licensed ICE feed is not connected; credentials and "
           "public redistribution rights are still required.", ""]
    for name, state in m.get("_source_status", {}).items():
        if state.get("successful") is False:
            out += [f"- **{name.upper()} refresh failed:** {escape(str(state.get('error', 'unknown error')))}. "
                    "Retained dated inputs are shown above.", ""]
    return out
