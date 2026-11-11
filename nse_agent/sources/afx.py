"""Parsers for afx.kwayisi.org (third-party NSE price mirror).

Prices and volumes come from here. AFX's EPS, DPS and share counts are third-party
figures and are only used as labelled cross-checks, never as valuation inputs.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from .. import http

BASE = "https://afx.kwayisi.org"

_UNITS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12, "TR": 1e12,
          "THOUSAND": 1e3, "MILLION": 1e6, "BILLION": 1e9, "TRILLION": 1e12}


def parse_number(text: str | None) -> float | None:
    if text is None:
        return None
    t = html.unescape(text).strip().replace(",", "").replace("KES", "").strip()
    if not t or t in {"-", "--", "N/A"}:
        return None
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(%|[A-Za-z]+)?", t)
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or "").upper()
    if unit == "%":
        return value / 100.0
    if unit:
        if unit not in _UNITS:
            return None
        value *= _UNITS[unit]
    return value


@dataclass
class ListingRow:
    ticker: str
    name: str
    volume: float | None
    price: float | None
    change: float | None
    suspended: bool


@dataclass
class Listing:
    rows: list[ListingRow]
    nasi: float | None
    as_of: str | None


_ROW = re.compile(
    r"<tr(?P<cls>[^>]*)><td><a href=[^>]*?/nse/[^>]*>(?P<ticker>[^<]+)</a>"
    r"<td><a [^>]*>(?P<name>[^<]*)</a><td>(?P<vol>[^<]*)<td>(?P<price>[^<]*)<td[^>]*>(?P<chg>[^<]*)"
)


def parse_listing(page: str) -> Listing:
    start = page.find("<th>Ticker<th>Name")
    body = page[start:] if start >= 0 else page
    rows = []
    for m in _ROW.finditer(body):
        rows.append(ListingRow(
            ticker=html.unescape(m.group("ticker")).strip().upper(),
            name=html.unescape(m.group("name")).strip(),
            volume=parse_number(m.group("vol")),
            price=parse_number(m.group("price")),
            change=parse_number(m.group("chg")),
            suspended="ss" in m.group("cls"),
        ))
    nasi = None
    nm = re.search(r"NASI Index<th>[\s\S]*?<tbody[^>]*><tr><td>([\d.,]+)", page)
    if nm:
        nasi = parse_number(nm.group(1))
    tm = re.search(r"<time[^>]*datetime=\"?([0-9T:+\-]+)", page)
    return Listing(rows=rows, nasi=nasi, as_of=tm.group(1) if tm else None)


@dataclass
class CompanyPage:
    ticker: str
    as_of: str | None
    stats: dict[str, float | None] = field(default_factory=dict)
    perf: dict[str, float | None] = field(default_factory=dict)
    history: list[tuple[str, float, float | None]] = field(default_factory=list)
    avg_session_turnover: float | None = None
    avg_session_volume: float | None = None
    sector: str | None = None
    industry: str | None = None


def parse_company(ticker: str, page: str) -> CompanyPage:
    page = html.unescape(page)
    tm = re.search(r"<time id=u datetime=\"?([0-9T:+\-]+)", page)
    cp = CompanyPage(ticker=ticker.upper(), as_of=tm.group(1) if tm else None)
    for label, value in re.findall(r"<tr><td>([A-Z][^<]{2,40})<td(?: class=\w+)?>([^<]*)", page):
        if re.search(r"\d", value):
            cp.stats[label.replace("\u2019", "'").strip()] = parse_number(value)
    pm = re.search(r"data-perf>([\s\S]*?)</div>", page)
    if pm:
        heads = re.findall(r"<th[^>]*>([^<]+)", pm.group(1))
        vals = re.findall(r"<td[^>]*>([^<]+)", pm.group(1))
        cp.perf = {h: parse_number(v) for h, v in zip(heads, vals)}
    hm = re.search(r"<table data-hist>([\s\S]*?)</table>", page)
    if hm:
        for d, vol, close in re.findall(r"<tr><td>(\d{4}-\d{2}-\d{2})<td>([^<]*)<td>([^<]*)", hm.group(1)):
            c = parse_number(close)
            if c is not None:
                cp.history.append((d, c, parse_number(vol)))
    lm = re.search(
        r"averaging a volume of ([\d.,]+(?: \w+illion| thousand)?) shares \(valued at KES ([\d.,]+(?: \w+illion| thousand)?)\) per session",
        page,
    )
    if lm:
        cp.avg_session_volume = parse_number(lm.group(1))
        cp.avg_session_turnover = parse_number(lm.group(2))
    sm = re.search(r"<dt>Sector<dd>([^<]+)", page)
    im = re.search(r"<dt>Industry<dd>([^<]+)", page)
    cp.sector = sm.group(1).strip() if sm else None
    cp.industry = im.group(1).strip() if im else None
    return cp


def parse_chart(script: str) -> list[tuple[str, float]]:
    return [(d, float(v)) for d, v in re.findall(r'd\("(\d{4}-\d{2}-\d{2})"\),(-?[\d.]+)\]', script)]


def fetch_listing() -> Listing:
    return parse_listing(http.get_text(f"{BASE}/nse/"))


def fetch_company(ticker: str) -> CompanyPage:
    return parse_company(ticker, http.get_text(f"{BASE}/nse/{ticker.lower()}.html"))


def fetch_chart(ticker: str) -> list[tuple[str, float]]:
    return parse_chart(http.get_text(f"{BASE}/chart/nse/{ticker.lower()}"))
