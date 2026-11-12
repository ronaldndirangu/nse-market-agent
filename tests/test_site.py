import json
import shutil

import pytest

from nse_agent import DISCLAIMER, site

ADVICE = f"> **Not financial advice.** {DISCLAIMER}"


@pytest.fixture
def tree(root):
    yield root
    for sub in ("reports", "site"):
        shutil.rmtree(root / sub, ignore_errors=True)
    (root / "data" / "retrospective.json").unlink(missing_ok=True)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_without_snapshots_renders_pages_and_archive(tree):
    _write(tree / "reports" / "daily" / "latest.md", f"# Daily brief\n\n{ADVICE}\n\n## Top 5\n\nKCB\n")
    _write(tree / "reports" / "daily" / "2026-11-10.md", "# Daily brief 2026-11-10\n")
    _write(tree / "reports" / "daily" / "2026-11-11.md", "# Daily brief 2026-11-11\n")
    _write(tree / "reports" / "latest.md", "# Weekly report\n")
    written = {p.relative_to(tree / "site").as_posix() for p in site.build()}
    assert {"index.html", "daily.html", "weekly.html", "archive.html", "daily/2026-11-10.html",
            "daily/2026-11-11.html"} <= written
    assert "retrospective.html" not in written
    assert (tree / "site" / ".nojekyll").exists()

    index = (tree / "site" / "index.html").read_text(encoding="utf-8")
    assert "No daily snapshot yet" in index and "Panel unavailable" not in index
    older = (tree / "site" / "daily" / "2026-11-10.html").read_text(encoding="utf-8")
    assert 'href="2026-11-11.html"' in older and 'href="../index.html"' in older
    archive = (tree / "site" / "archive.html").read_text(encoding="utf-8")
    assert "November 2026" in archive and 'href="daily/2026-11-11.html"' in archive
    for text in (index, older, archive):
        assert "\u2014" not in text and "\u2013" not in text


def test_dashboard_tolerates_sparse_and_broken_snapshots(tree):
    path = tree / "reports" / "daily" / "latest.json"
    _write(path, json.dumps({"as_of": "2026-11-11"}))
    site.build()
    index = (tree / "site" / "index.html").read_text(encoding="utf-8")
    assert "2026-11-11" in index and "Panel unavailable" not in index

    _write(path, json.dumps({"as_of": "2026-11-11", "top": [None], "high_confidence": 5}))
    site.build()
    index = (tree / "site" / "index.html").read_text(encoding="utf-8")
    assert "Panel unavailable" in index and "Not financial advice" in index


KPLC = {
    "rank": 1, "ticker": "KPLC", "name": "Kenya Power", "sector": "Energy", "tier": "Watch", "price": 22.0,
    "price_date": "2026-11-11", "fair_base": 34.52, "fair_low": 28.0, "fair_high": 41.0, "mos": 0.569,
    "bear": -0.139, "base": 0.296, "bull": 0.567, "dividend_yield": 0.045, "composite": 1.21,
    "binding": "Not a Buy: only 1 of 2 valuation models show 15% or more upside, needs 2.", "why": "KPLC #1.",
    "driver": {"signal": "momentum", "label": "Momentum", "contribution": 0.8},
    "conviction": {"flag": False, "failed": ["Value"],
                   "gates": [{"name": "Value", "passed": False, "detail": "1 of 2 models"}]},
    "risk": {"level": "High", "summary": "High risk.", "factors": [{"name": "Volatility", "level": "High",
                                                                   "detail": "Large swings"}]},
}


def test_dashboard_beginner_layer(tree):
    snap = {"as_of": "2026-11-11", "hurdle": 0.1267, "tbill_net": 0.0767, "valued": 16,
            "counts": {"Buy": 0, "Watch": 1, "Avoid": 0}, "top": [KPLC], "near_misses": [KPLC], "high_confidence": []}
    _write(tree / "reports" / "daily" / "latest.json", json.dumps(snap))
    site.build()
    index = (tree / "site" / "index.html").read_text(encoding="utf-8")
    for text in ("No stock is a Buy today", "Closest is <b>KPLC</b>", "KES 10,000 invested", "KES 21,768",
                 "after 3 years", "Jargon buster", "Show the details", "Not financial advice"):
        assert text in index
    assert "Panel unavailable" not in index and "\u2014" not in index and "\u2013" not in index
    assert site._plain_reason(KPLC["binding"]) == "only 1 of 2 valuation methods say it is at least 15% cheap (needs 2)"

    snap["top"] = [dict(KPLC, tier="Buy", binding="Clears every gate.")]
    _write(tree / "reports" / "daily" / "latest.json", json.dumps(snap))
    site.build()
    index = (tree / "site" / "index.html").read_text(encoding="utf-8")
    assert "Buy today: KPLC." in index and "Passes every check" in index
    assert "Looks fairly priced:</b> price KES 22.00 vs fair value estimate KES 22.01." in site._plain(
        dict(KPLC, fair_base=22.01, mos=0.0005), None)


def test_dispersed_card_hides_point_estimates_and_stale_prices_warn(tree):
    kplc = dict(KPLC, tier="Avoid", dispersed=True, model_spread=3.4, agree=1, models=2, agree_needed=2)
    snap = {"as_of": "2026-11-12", "price_date": "2026-11-11", "hurdle": 0.1267, "tbill_net": 0.0767, "valued": 16,
            "counts": {"Buy": 0, "Watch": 0, "Avoid": 1}, "top": [kplc], "near_misses": [kplc],
            "high_confidence": []}
    _write(tree / "reports" / "daily" / "latest.json", json.dumps(snap))
    site.build()
    index = (tree / "site" / "index.html").read_text(encoding="utf-8")
    assert "Fair value unclear" in index and "methods disagree" in index and "3.4x apart" in index
    assert "KES 10,000 invested" not in index and "Looks cheap" not in index
    assert "Prices not refreshed" in index and "Closing prices from 2026-11-11" in index
    assert "Panel unavailable" not in index and "\u2014" not in index and "\u2013" not in index

    plain = site._plain(KPLC, None, cal=0.27)
    assert "middle case" in plain and "only 27% of 12 month results" in plain

    snap["price_date"] = "2026-11-12"
    _write(tree / "reports" / "daily" / "latest.json", json.dumps(snap))
    site.build()
    assert "Prices not refreshed" not in (tree / "site" / "index.html").read_text(encoding="utf-8")


def test_render_markdown_folds_method_sections_and_dedupes_disclaimer():
    md = (f"# Report\n\n{ADVICE}\n\n## Picks\n\n| Ticker | Tier | Risk |\n|---|---|---|\n| KCB | Watch | High |\n\n"
          f"## Method\n\nRules.\n\n## Data gaps\n\nNone.\n\n{ADVICE}\n")
    html = site.render_markdown(md)
    assert html.count("Not financial advice") == 1
    assert '<details class="fold" id="method">' in html and '<details class="fold" id="data-gaps">' in html
    assert '<h2 id="picks">' in html and 'class="toc"' in html
    assert "b-watch" in html and "r-high" in html


def test_badges():
    assert "b-buy" in site.tier_badge("Buy") and "b-flag" not in site.tier_badge("Buy")
    assert "b-flag" in site.tier_badge("Buy", flagged=True)
    assert "b-avoid" in site.tier_badge("Avoid")
    assert "r-moderate" in site.risk_badge("Moderate")
    assert "Risk n/a" in site.risk_badge(None)
