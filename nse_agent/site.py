"""Static GitHub Pages site: a dashboard, styled report pages and a dated archive."""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from urllib.parse import quote

from . import DISCLAIMER, __version__, config
from .fmt import kes, pct
from .risk import FACTORS

REPO = "https://github.com/ronaldndirangu/nse-market-agent"
DATED = re.compile(r"\d{4}-\d{2}-\d{2}\.md")
PAGES = [  # (source under reports/, output page, nav label, description)
    ("daily/latest.md", "daily.html", "Daily brief", "Today's top 5, tiers, risk profile and what changed."),
    ("latest.md", "weekly.html", "Weekly report", "Fair value ranges, theses and data gaps for every stock."),
    ("retrospective.md", "retrospective.html", "Retrospective",
     "How past rankings performed, per-signal IC and why winners were missed."),
    ("scorecard.md", "scorecard.html", "Scorecard", "Logged picks scored against NASI."),
    ("backtest.md", "backtest.html", "Backtest", "Walk-forward backtest of the ranking rules."),
    ("simulation.md", "simulation.html", "Simulation", "Monte Carlo return ranges and stress tests."),
    ("tuning.md", "tuning.html", "Weight tuning", "Out-of-sample weight selection, proposed for review."),
]
COLLAPSE = ("how to read", "method", "limitations", "data gaps", "exclusions", "holdings by month")
SIGNALS = {"composite": "Composite score", "margin_of_safety": "Margin of safety", "quality": "Quality",
           "momentum": "Momentum", "dividend_yield": "Dividend yield", "low_volatility": "Low volatility"}
MISSES = {"caught": "Caught (ranked in top 5)", "signal miss": "Signal miss", "missing data": "Missing data",
          "macro": "Macro", "event": "Event (takeover, rights issue)", "turnaround": "Turnaround from losses"}

LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">'
        '<rect width="32" height="32" rx="8" fill="#0b6e4f"/><path d="M7 22l6-6 4 4 8-9" fill="none" stroke="#fff" '
        'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="25" cy="11" r="2.4" '
        'fill="#f2c94c"/></svg>')
FAVICON = "data:image/svg+xml," + quote(LOGO)

CSS = """
:root{--bg:#f5f7f9;--card:#fff;--fg:#17202a;--muted:#5d6b78;--line:#e2e7ec;--soft:#f0f3f6;--brand:#0b6e4f;
--brand-soft:#e6f3ee;--pos:#1a7f37;--neg:#c9252d;--warn:#9a6700;--mod:#b45309;--info:#2f6fb3;--shadow:0 1px 2px
rgba(16,24,40,.05),0 2px 8px rgba(16,24,40,.06);--r:14px}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;--muted:#8d98a5;--line:#2b333d;
--soft:#1c232c;--brand:#3fb950;--brand-soft:#132a1f;--pos:#3fb950;--neg:#ff6b6b;--warn:#d6a530;--mod:#f0883e;
--info:#6ca7ec;--shadow:none}}
*{box-sizing:border-box}html{scroll-padding-top:5rem}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--info);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:0 1.1rem}
.skip{position:absolute;left:-999px;top:.5rem;background:var(--card);padding:.5rem 1rem;border-radius:8px;z-index:9}
.skip:focus{left:.5rem}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--card) 88%,transparent);
backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.bar{display:flex;align-items:center;gap:1.2rem;min-height:3.6rem}
.brand{display:flex;align-items:center;gap:.6rem;color:var(--fg);font-weight:700;white-space:nowrap}
.brand:hover{text-decoration:none}.brand small{display:block;font-weight:500;font-size:.72rem;color:var(--muted)}
.nav{display:flex;gap:.25rem;overflow-x:auto;scrollbar-width:none;flex:1;padding:.4rem 0}
.nav::-webkit-scrollbar{display:none}
.nav a{white-space:nowrap;padding:.35rem .75rem;border-radius:999px;color:var(--muted);font-weight:550;font-size:.9rem}
.nav a:hover{background:var(--soft);color:var(--fg);text-decoration:none}
.nav a[aria-current=page]{background:var(--brand-soft);color:var(--brand)}
main{padding:1.4rem 0 3rem}
h1{font-size:1.75rem;line-height:1.2;margin:.2rem 0 .6rem}h2{font-size:1.22rem;margin:2rem 0 .7rem}
h3{font-size:1.02rem;margin:1.4rem 0 .5rem}
.muted{color:var(--muted)}.small{font-size:.85rem}.pos{color:var(--pos)}.neg{color:var(--neg)}
.num{font-variant-numeric:tabular-nums}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);
padding:1.1rem 1.2rem;margin:1rem 0}
.card>h2:first-child{margin-top:.1rem}
.hero{display:grid;grid-template-columns:1.5fr 1fr;gap:1.2rem;align-items:center}
.eyebrow{text-transform:uppercase;letter-spacing:.06em;font-size:.75rem;font-weight:700;color:var(--brand);margin:0}
.lead{font-size:1.02rem;color:var(--muted);margin:.2rem 0 .8rem}
.chips{display:flex;flex-wrap:wrap;gap:.45rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem}
.hero .kpis{grid-template-columns:1fr 1fr}
.kpi{background:var(--soft);border-radius:12px;padding:.75rem .9rem}
.kpi b{display:block;font-size:1.45rem;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi span{font-size:.8rem;color:var(--muted)}
.badge{display:inline-flex;align-items:center;gap:.25rem;padding:.08rem .55rem;border-radius:999px;font-size:.78rem;
font-weight:650;white-space:nowrap;line-height:1.55;border:1px solid transparent}
.b-buy,.r-low,.c-high{background:color-mix(in srgb,var(--pos) 14%,transparent);color:var(--pos)}
.b-watch,.r-moderate,.c-medium,.c-moderate{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}
.b-avoid,.b-muted,.c-low{background:var(--soft);color:var(--muted);border-color:var(--line)}
.r-high{background:color-mix(in srgb,var(--neg) 13%,transparent);color:var(--neg)}
.b-flag{background:var(--brand);color:#fff}
.chip{display:inline-flex;gap:.35rem;align-items:center;background:var(--soft);border-radius:999px;padding:.3rem .75rem;
font-size:.86rem}.chip b{font-variant-numeric:tabular-nums}
.callout{border:1px solid var(--line);border-left:4px solid var(--info);background:var(--card);border-radius:10px;
margin:1rem 0;padding:.6rem 1rem}.callout p{margin:.3rem 0}
.callout.warn{border-left-color:var(--warn);background:color-mix(in srgb,var(--warn) 7%,var(--card))}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:1rem}
.stock{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:1rem;display:flex;
flex-direction:column;gap:.65rem;box-shadow:var(--shadow)}
.stock.flagged{border-color:var(--brand);box-shadow:0 0 0 1px var(--brand)}
.stock header{display:flex;justify-content:space-between;gap:.5rem;align-items:flex-start}
.tk{font-weight:800;font-size:1.1rem;color:var(--fg)}.rank{color:var(--muted);font-weight:700;margin-right:.3rem}
.nm{display:block;color:var(--muted);font-size:.83rem}.badges{display:flex;gap:.3rem;flex-wrap:wrap;justify-content:flex-end}
.pricebox{display:flex;justify-content:space-between;align-items:flex-end;gap:.6rem}
.price{font-size:1.25rem;font-weight:700;font-variant-numeric:tabular-nums}
.spark{margin:0;text-align:right}.spark svg{width:150px;height:36px;display:block}
.spark polyline{fill:none;stroke-width:1.6;stroke:currentColor;vector-effect:non-scaling-stroke}
.spark figcaption{font-size:.75rem}
.facts{display:grid;grid-template-columns:1fr 1fr;gap:.45rem .8rem;margin:0}
.facts div{min-width:0}.facts dt{font-size:.74rem;color:var(--muted)}
.facts dd{margin:0;font-weight:650;font-variant-numeric:tabular-nums}
.rangebar svg{width:100%;height:40px;display:block}
.rangebar .cap{display:flex;justify-content:space-between;font-size:.76rem;color:var(--muted)}
.rangebar .cap b{color:var(--fg);font-variant-numeric:tabular-nums}
.gates{list-style:none;padding:0;margin:0;display:grid;gap:.25rem;font-size:.84rem}
.gates li{display:flex;gap:.45rem}.gates .ok{color:var(--pos)}.gates .no{color:var(--neg)}
.why{font-size:.88rem;color:var(--muted);margin:0;border-top:1px dashed var(--line);padding-top:.55rem}
.factors{display:flex;flex-wrap:wrap;gap:.3rem}
.empty{background:var(--soft);border-radius:10px;padding:.7rem 1rem;margin:.6rem 0 1rem}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px;margin:1rem 0;max-height:75vh;
background:var(--card)}
table.data{border-collapse:separate;border-spacing:0;width:100%;font-size:.88rem}
table.data th,table.data td{padding:.5rem .7rem;text-align:left;white-space:nowrap;border-bottom:1px solid var(--line)}
table.data td{font-variant-numeric:tabular-nums}
table.data thead th{position:sticky;top:0;background:var(--soft);font-weight:650;z-index:1;color:var(--muted);
font-size:.8rem;text-transform:none}
table.data tbody tr:nth-child(even){background:color-mix(in srgb,var(--soft) 55%,transparent)}
table.data tbody tr:hover{background:var(--brand-soft)}table.data tbody tr:last-child td{border-bottom:0}
table.sortable th{cursor:pointer;user-select:none}table.sortable th:after{content:" \\2195";opacity:.35}
table.sortable th[aria-sort=ascending]:after{content:" \\2191";opacity:1}
table.sortable th[aria-sort=descending]:after{content:" \\2193";opacity:1}
.prose{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:1.2rem 1.6rem 1.6rem;
box-shadow:var(--shadow)}
.prose ul{padding-left:1.25rem}.prose li{margin:.2rem 0}.prose code{background:var(--soft);padding:.05rem .3rem;
border-radius:5px;font-size:.88em}
.toc{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 1rem}
.toc a{background:var(--soft);border-radius:999px;padding:.25rem .7rem;font-size:.82rem;color:var(--fg)}
details.fold{border:1px solid var(--line);border-radius:12px;margin:1rem 0;padding:0 1rem}
details.fold summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:.5rem}
details.fold summary::-webkit-details-marker{display:none}
details.fold summary:before{content:"\\25B8";color:var(--muted)}details.fold[open] summary:before{content:"\\25BE"}
details.fold summary h2{margin:.75rem 0;font-size:1.05rem}
.heat td.ic{text-align:center;font-weight:650}
.bars{display:grid;gap:.45rem}.bars .row{display:grid;grid-template-columns:210px 1fr 92px;gap:.6rem;
align-items:center;font-size:.86rem}.bars .num{white-space:nowrap;text-align:right}
.bars .track{background:var(--soft);border-radius:999px;height:10px;overflow:hidden}
.bars .fill{height:100%;background:var(--brand);border-radius:999px}.bars .fill.miss{background:var(--mod)}
.chart svg{width:100%;height:auto;display:block}.chart text{fill:var(--muted);font-size:11px}
.chart .grid line{stroke:var(--line)}.legend{display:flex;flex-wrap:wrap;gap:1rem;font-size:.85rem;margin:.3rem 0}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:.35rem;vertical-align:middle}
.two{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.two>.card{margin:0}
.links{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.8rem}
.links a{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.85rem 1rem;
color:var(--fg)}.links a:hover{border-color:var(--brand);text-decoration:none}
.links b{display:block}.links span{font-size:.84rem;color:var(--muted)}
.pager{display:flex;justify-content:space-between;gap:.6rem;margin:.4rem 0 1rem;font-size:.9rem}
.months h3{margin:1rem 0 .4rem;font-size:.95rem;color:var(--muted)}.months .chips a{color:var(--fg)}
.foot{border-top:1px solid var(--line);color:var(--muted);font-size:.84rem;padding:1.4rem 0 2rem}
.foot p{margin:.25rem 0}
.plain{background:var(--brand-soft);border-radius:10px;padding:.55rem .8rem;margin:0;font-size:.9rem}
.plain p{margin:.2rem 0}.plain b{color:var(--fg)}
#verdict .big{font-size:1.15rem;font-weight:650;margin:.2rem 0 .5rem}#verdict ol{margin:.4rem 0 0;padding-left:1.2rem}
#verdict li{margin:.25rem 0}.facts dt[title]{cursor:help;text-decoration:underline dotted}
details.more summary{cursor:pointer;color:var(--brand);font-size:.88rem;font-weight:600}
details.more[open] summary{margin-bottom:.5rem}details.more>*+*{margin-top:.5rem}
#glossary dl{margin:0 0 1rem}#glossary dt{font-weight:650;margin-top:.6rem}#glossary dd{margin:.1rem 0 0;color:var(--muted)}
@media (max-width:820px){.hero,.two{grid-template-columns:1fr}.bar{flex-direction:column;align-items:stretch;gap:0;
padding-top:.5rem}.nav{margin:0 -1.1rem;padding:.4rem 1.1rem}h1{font-size:1.45rem}
.prose{padding:1rem}.bars .row{grid-template-columns:120px 1fr 86px}}
"""

JS = """
document.querySelectorAll('table.sortable').forEach(function(t){
  var ths=t.querySelectorAll('thead th');
  ths.forEach(function(th,i){
    th.tabIndex=0;
    function key(r){var c=r.cells[i];if(!c)return null;var s=(c.dataset.v!==undefined?c.dataset.v:c.textContent).trim();
      var k=s.replace(/KES|[,%x\\s]/gi,'');var n=Number(k);if(k!==''&&isFinite(n))return n;
      return s==='n/a'||s===''?null:s.toLowerCase();}
    function go(){var b=t.tBodies[0];if(!b)return;var asc=th.getAttribute('aria-sort')!=='ascending';
      ths.forEach(function(h){h.removeAttribute('aria-sort')});th.setAttribute('aria-sort',asc?'ascending':'descending');
      var rows=Array.prototype.slice.call(b.rows);
      rows.sort(function(x,y){var a=key(x),c=key(y);if(a===null)return 1;if(c===null)return -1;
        var d=(typeof a==='number'&&typeof c==='number')?a-c:String(a).localeCompare(String(c));return asc?d:-d;});
      rows.forEach(function(r){b.appendChild(r)});}
    th.addEventListener('click',go);
    th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}});
  });
});
"""

E = html.escape
LEVEL = re.compile(r"(High|Moderate|Medium|Low)\b")
SIGNED = re.compile(r"(?<![\w.])([+-])(\d[\d,.]*%?)")


def _inline(s: str) -> str:
    """Escape text, then render the small Markdown subset the templates use: bold, code and links."""
    s = E(str(s))
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _signed(fragment: str) -> str:
    parts = re.split(r"(<[^>]+>)", fragment)
    return "".join(p if p.startswith("<") else SIGNED.sub(
        lambda m: f'<span class="{"pos" if m.group(1) == "+" else "neg"}">{m.group(0)}</span>', p) for p in parts)


def _sp(v: float | None, nd: int = 1) -> str:
    """Signed, coloured percentage."""
    if v is None:
        return '<span class="muted">n/a</span>'
    cls = "pos" if v > 0 else "neg" if v < 0 else ""
    return f'<span class="{cls}">{"+" if v > 0 else ""}{pct(v, nd)}</span>'


def tier_badge(tier: str, flagged: bool = False) -> str:
    t = (tier or "").strip()
    low = t.lower()
    cls = ("b-buy" if low.startswith("buy") else "b-watch" if low.startswith(("watch", "undervalued"))
           else "b-avoid" if low.startswith("avoid") else "b-muted")
    out = f'<span class="badge {cls}">{E(t)}</span>'
    return out + (' <span class="badge b-flag" title="All four conviction gates pass">High confidence</span>'
                  if flagged else "")


def risk_badge(level: str | None, label: str = " risk") -> str:
    if not level:
        return '<span class="badge b-muted">Risk n/a</span>'
    return f'<span class="badge r-{E(level.lower())}">{E(level)}{label}</span>'


def _cell(header: str, content: str) -> str:
    h, t = header.lower(), _text(content)
    if h.startswith(("tier", "status")) and t:
        return tier_badge(t) if "high confidence" not in t.lower() else tier_badge(
            t.split("(")[0].strip(), True)
    m = LEVEL.match(t)
    if m and (h.startswith("risk") or header in FACTORS):
        return f'<span class="badge r-{m.group(1).lower()}">{content}</span>'
    if m and "confidence" in h:
        return f'<span class="badge c-{m.group(1).lower()}">{content}</span>'
    return _signed(content)


def _table(m: re.Match) -> str:
    inner = m.group(1)
    if "</thead>" not in inner:
        return f'<div class="table-wrap"><table class="data">{inner}</table></div>'
    head, _, body = inner.partition("</thead>")
    heads = [_text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]

    def row(rm: re.Match) -> str:
        idx = iter(range(len(heads) + 50))

        def cell(cm: re.Match) -> str:
            k = next(idx)
            return f"<td{cm.group(1)}>{_cell(heads[k] if k < len(heads) else '', cm.group(2))}</td>"
        return "<tr>" + re.sub(r"<td([^>]*)>(.*?)</td>", cell, rm.group(1), flags=re.S) + "</tr>"

    body = re.sub(r"<tr>(.*?)</tr>", row, body, flags=re.S)
    return f'<div class="table-wrap"><table class="data sortable">{head}</thead>{body}</table></div>'


def _slug(title: str, used: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"
    s, i = base, 2
    while s in used:
        s, i = f"{base}-{i}", i + 1
    used.add(s)
    return s


def _md(text: str) -> str:
    try:
        import markdown
        return markdown.markdown(text, extensions=["tables"])
    except ImportError:
        return "<pre>" + E(text) + "</pre>"


def _dedupe_disclaimer(text: str) -> str:
    seen, out = False, []
    for line in text.splitlines():
        if line.startswith("> **Not financial advice.**"):
            if seen:
                continue
            seen = True
        out.append(line)
    return "\n".join(out) + "\n"


def render_markdown(text: str) -> str:
    """Markdown report to enhanced HTML: badges, scrollable sortable tables, callouts, TOC and folded sections."""
    body = _md(_dedupe_disclaimer(text))
    body = re.sub(r"<table>(.*?)</table>", _table, body, flags=re.S)
    body = re.sub(r"<blockquote>(\s*<p><strong>Not financial advice)", r'<blockquote class="callout warn">\1', body)
    body = body.replace("<blockquote>", '<blockquote class="callout">')
    parts = re.split(r"(?=<h2>)", body)
    used: set = set()
    toc, out = [], [parts[0]]
    for part in parts[1:]:
        m = re.match(r"<h2>(.*?)</h2>", part, re.S)
        title = _text(m.group(1))
        slug = _slug(title, used)
        toc.append((slug, title))
        rest = part[m.end():]
        if title.lower().startswith(COLLAPSE):
            out.append(f'<details class="fold" id="{slug}"><summary><h2>{m.group(1)}</h2></summary>{rest}</details>')
        else:
            out.append(f'<h2 id="{slug}">{m.group(1)}</h2>{rest}')
    body = "".join(out)
    if len(toc) >= 3:
        nav = ('<nav class="toc" aria-label="On this page">'
               + "".join(f'<a href="#{s}">{E(t)}</a>' for s, t in toc) + "</nav>")
        body = body.replace("</h1>", "</h1>" + nav, 1) if "</h1>" in body else nav + body
    return f'<article class="prose">{body}</article>'


# Dashboard components

def _spark(ticker: str, n: int = 260) -> str:
    try:
        from . import prices
        pts = [c for _, c, _ in prices.adj_rows(ticker)[-n:] if c]
    except Exception:
        return ""
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span, w, h = (hi - lo) or 1.0, 150, 36
    xy = " ".join(f"{i * w / (len(pts) - 1):.1f},{h - 3 - (p - lo) / span * (h - 6):.1f}" for i, p in enumerate(pts))
    ch = pts[-1] / pts[0] - 1
    return (f'<figure class="spark {"pos" if ch >= 0 else "neg"}"><svg viewBox="0 0 {w} {h}" '
            f'preserveAspectRatio="none" role="img" aria-label="Split-adjusted price over about a year, {pct(ch)}">'
            f'<polyline points="{xy}"/></svg><figcaption>{"+" if ch > 0 else ""}{pct(ch)} over a year'
            f'</figcaption></figure>')


def _range_bar(bear: float | None, base: float | None, bull: float | None, hurdle: float | None) -> str:
    if None in (bear, base, bull):
        return ""
    marks = [bear, bull, 0.0] + ([hurdle] if hurdle is not None else [])
    lo, hi = min(marks), max(marks)
    pad = (hi - lo) * 0.06 or 0.05
    lo, hi = lo - pad, hi + pad

    def x(v: float) -> float:
        return 4 + (v - lo) / (hi - lo) * 292

    hurdle_mark = (f'<line x1="{x(hurdle):.1f}" x2="{x(hurdle):.1f}" y1="4" y2="34" stroke="var(--warn)" '
                   f'stroke-width="2"><title>Hurdle {pct(hurdle, 2)}</title></line>') if hurdle is not None else ""
    svg = (f'<svg viewBox="0 0 300 38" preserveAspectRatio="none" role="img" aria-label="Projected annual return '
           f'bear {pct(bear)}, base {pct(base)}, bull {pct(bull)}">'
           f'<rect x="4" y="16" width="292" height="6" rx="3" fill="var(--soft)"/>'
           f'<rect x="{x(bear):.1f}" y="12" width="{max(x(bull) - x(bear), 2):.1f}" height="14" rx="7" '
           f'fill="color-mix(in srgb,var(--brand) 28%,transparent)"/>'
           f'<line x1="{x(0):.1f}" x2="{x(0):.1f}" y1="6" y2="32" stroke="var(--muted)" stroke-dasharray="3 3"/>'
           f'{hurdle_mark}<circle cx="{x(base):.1f}" cy="19" r="6" fill="var(--brand)" stroke="var(--card)" '
           f'stroke-width="2"/></svg>')
    return (f'<div class="rangebar">{svg}<div class="cap"><span>Bear <b>{pct(bear)}</b></span>'
            f'<span>Base <b>{pct(base)}</b></span><span>Bull <b>{pct(bull)}</b></span></div>'
            f'<div class="cap small"><span>Projected return a year. Dashed line 0%, amber line '
            f'{pct(hurdle, 2) if hurdle is not None else "hurdle"} hurdle.</span></div></div>')


TIPS = {
    "Upside": "How far the price would rise to reach our fair value estimate (fair value divided by price, minus 1). "
              "Bigger is cheaper.",
    "Base return": "The middle of three estimates of the average yearly return over the next 3 years: dividends, "
                   "growth and the price moving toward fair value, after costs and tax. Real results often land far "
                   "from it.",
    "Fair value": "What the rules estimate one share is worth. The bracket shows the low and high estimates.",
    "Dividend yield": "Cash dividends paid in a year as a share of today's price.",
    "Top signal": "The input that added most to this stock's score.",
    "Composite": "The overall score used to rank stocks. Higher ranks first.",
}

PLAIN = [
    (re.compile(r"only (\d+) of (\d+) valuation models show (\S+) or more upside, needs (\d+)"),
     r"only \1 of \2 valuation methods say it is at least \3 cheap (needs \4)"),
    (re.compile(r"only (\d+) valuation model\(s\) available, needs (\d+)"),
     r"only \1 valuation method has enough data (needs \2)"),
    (re.compile(r"valuation models disagree \(high is (\S+) the low, limit (\S+)\)"),
     r"the valuation methods disagree too much (the highest estimate is \1 the lowest, the limit is \2)"),
    (re.compile(r"base return (\S+) does not beat the (\S+) hurdle"),
     r"its middle-case return of \1 a year is below the \2 a Buy must beat"),
    (re.compile(r"quality gate failed"), "the business fails a health check"),
    (re.compile(r"quality unknown \(no Piotroski, Altman or NPL data\)"), "its business health cannot be checked yet"),
    (re.compile(r"price is stale"), "the last price is out of date"),
    (re.compile(r"(^|; )suspended\b"), r"\1trading is suspended"),
    (re.compile(r"no turnover data"), "there is no trading volume data"),
    (re.compile(r"illiquid \(avg turnover"), "it trades too rarely to buy and sell easily (average daily trading"),
    (re.compile(r"only (\d+) annual periods sourced"), r"only \1 years of results are on file"),
    (re.compile(r"latest EPS not positive"), "the company made a loss in its latest year"),
    (re.compile(r"\(\+(\d+) more\)"), r"(and \1 more)"),
]


def _plain_reason(binding: str | None) -> str:
    """Rewrite the engine's blocker text in everyday words."""
    s = re.sub(r"^(Not a Buy|Avoid):\s*", "", (binding or "").strip()).rstrip(".")
    if s == "Clears every gate":
        return ""
    for pat, rep in PLAIN:
        s = pat.sub(rep, s)
    return s


def _money(v: float) -> str:
    return f"KES {v:,.0f}"


SIGNAL_WORDS = {"momentum": "price trend", "dividend_yield": "dividend yield", "quality": "business health",
                "margin_of_safety": "upside to fair value", "low_volatility": "steady price"}


def _weights_plain(s: dict) -> str:
    w = s.get("weights") or {k: v for k, v in config.settings().get("ranking", {}).get("weights", {}).items() if v}
    return ", ".join(f"{SIGNAL_WORDS.get(k, k.replace('_', ' '))} {v:.0%}"
                     for k, v in sorted(w.items(), key=lambda kv: -kv[1]))


def _cal_text(cal: float | None) -> str:
    if cal is None:
        return "These are estimates; real results often land outside them."
    return f"In past tests only {cal:.0%} of 12 month results landed between the bad and good case."


def _plain(it: dict, tbill: float | None, cal: float | None = None) -> str:
    lines = []
    price, fair, mos = it.get("price"), it.get("fair_base"), it.get("mos")
    dispersed = bool(it.get("dispersed"))
    if dispersed:
        lo, hi, spread = it.get("fair_low"), it.get("fair_high"), it.get("model_spread")
        rng = f" (estimates run from {kes(lo)} to {kes(hi)}, {spread:.1f}x apart)" if None not in (lo, hi, spread) else ""
        votes = (f" {it['agree']} of {it['models']} methods say it is at least "
                 f"{pct(config.settings().get('valuation', {}).get('mos_threshold', 0.15), 0)} cheap."
                 if None not in (it.get("agree"), it.get("models")) else "")
        lines.append(f"<b>Fair value unclear:</b> the valuation methods disagree too much{rng}, so no single fair "
                     f"value or return is shown.{votes}")
    elif None not in (price, fair, mos):
        look = ("Looks fairly priced" if abs(mos) < 0.05 else "Looks cheap" if mos > 0 else "Looks expensive")
        gap = f" ({abs(mos):.0%} {'upside' if mos > 0 else 'downside'})" if f"{abs(mos):.0%}" != "0%" else ""
        lines.append(f"<b>{look}:</b> price {kes(price)} vs fair value estimate {kes(fair)}{gap}.")
    if it.get("tier") == "Buy":
        lines.append("<b>Passes every check.</b>")
    elif reason := _plain_reason(it.get("binding")):
        lines.append(f"<b>Why it is not a Buy:</b> {E(reason)}.")
    bear, base, bull = it.get("bear"), it.get("base"), it.get("bull")
    if None not in (bear, base, bull) and not dispersed:
        n = config.settings().get("valuation", {}).get("horizon_years", 3)

        def grow(r: float) -> str:
            return _money(10000 * max(1 + r, 0.0) ** n)

        t = f" Rolling over a T-bill would give about {grow(tbill)}." if tbill is not None else ""
        lines.append(f"<b>KES 10,000 invested</b> today could be worth about {grow(bear)} in a bad case, "
                     f"{grow(base)} in a middle case and {grow(bull)} in a good case after {n} years.{t} "
                     f"{_cal_text(cal)}")
    return f'<div class="plain">{"".join(f"<p>{x}</p>" for x in lines)}</div>' if lines else ""


def _stock_card(it: dict, hurdle: float | None, gates: bool = False, why: bool = False,
                tbill: float | None = None, cal: float | None = None) -> str:
    conv, rk = it.get("conviction") or {}, it.get("risk") or {}
    flagged = bool(conv.get("flag"))
    dispersed = bool(it.get("dispersed"))
    lo, hi = it.get("fair_low"), it.get("fair_high")
    span = f'<span class="muted small"> ({lo:,.0f} to {hi:,.0f})</span>' if None not in (lo, hi) else ""
    if dispersed and None not in (lo, hi):
        fair = f'{kes(lo)} to {kes(hi)}<span class="muted small"> (methods disagree)</span>'
    else:
        fair = f'{kes(it.get("fair_base"))}{span}' if it.get("fair_base") is not None else "n/a"
    drv = it.get("driver")
    unclear = '<span class="muted">unclear</span>'
    facts = [("Upside", unclear if dispersed else _sp(it.get("mos"))),
             ("Base return", unclear if dispersed else _sp(it.get("base"))),
             ("Fair value", fair), ("Dividend yield", pct(it.get("dividend_yield")))]
    extra = [("Top signal", E(drv["label"]) if drv else "n/a"),
             ("Composite", f'{it["composite"]:.2f}' if it.get("composite") is not None else "n/a")]

    def dl(rows: list[tuple[str, str]]) -> str:
        return ('<dl class="facts">' + "".join(f'<div><dt title="{E(TIPS.get(k, ""))}">{k}</dt><dd>{v}</dd></div>'
                                               for k, v in rows) + "</dl>")

    gate_html = ""
    if gates and conv.get("gates"):
        passed = sum(1 for g in conv["gates"] if g["passed"])
        gate_html = (f'<div class="small muted">{passed} of {len(conv["gates"])} gates pass</div><ul class="gates">'
                     + "".join(f'<li><span class="{"ok" if g["passed"] else "no"}" aria-hidden="true">'
                               f'{"&#10003;" if g["passed"] else "&#10007;"}</span><span><b>{E(g["name"])}</b>'
                               f'<span class="sr">{" passes" if g["passed"] else " fails"}</span>: {E(g["detail"])}'
                               f'</span></li>' for g in conv["gates"]) + "</ul>")
    factors = "".join(f'<span class="badge r-{E(f["level"].lower())}" title="{E(f["detail"])}">{E(f["name"])}: '
                      f'{E(f["level"])}</span>' for f in rk.get("factors", []) if f.get("level") in ("High", "Moderate"))
    return (f'<article class="stock{" flagged" if flagged else ""}"><header><div><span class="rank">#{it["rank"]}'
            f'</span><span class="tk">{E(it["ticker"])}</span><span class="nm">{E(it["name"])} &middot; {E(it["sector"])}'
            f'</span></div><div class="badges">{tier_badge(it["tier"], flagged)}{risk_badge(rk.get("level"))}</div>'
            f'</header><div class="pricebox"><div><div class="price">{kes(it.get("price"))}</div>'
            f'<div class="small muted">close {E(str(it.get("price_date") or ""))}</div></div>{_spark(it["ticker"])}'
            f'</div>{_plain(it, tbill, cal)}{dl(facts)}'
            + ("" if dispersed else _range_bar(it.get("bear"), it.get("base"), it.get("bull"), hurdle))
            + (f'<div class="factors">{factors}</div>' if factors else "")
            + f'<details class="more"><summary>Show the details</summary>{dl(extra)}{gate_html}'
            + (f'<p class="small muted">{E(rk["summary"])}</p>' if rk.get("summary") else "")
            + (f'<p class="why">{_inline(it["why"])}</p>' if why and it.get("why") else "") + "</details></article>")


def _hero(s: dict) -> str:
    c = s.get("counts", {})
    flagged = len(s.get("high_confidence") or [])
    chips = "".join(f'<span class="chip">{tier_badge(k)}<b>{c.get(k, 0)}</b></span>' for k in ("Buy", "Watch", "Avoid"))
    pd = s.get("price_date")
    when = f"Closing prices from {E(str(pd))}." if pd else ""
    stale = (f'<div class="callout warn small"><p><b>Prices not refreshed.</b> The latest closing prices are from '
             f'{E(str(pd))}, before this brief\'s date of {E(s["as_of"])}. The market may have been closed or the '
             f'price source failed.</p></div>') if pd and str(pd) < str(s["as_of"]) else ""
    return (f'<section class="hero"><div><p class="eyebrow">Daily brief for {E(s["as_of"])}</p>'
            f'<h1>Undervalued NSE stocks, ranked by fixed rules</h1><p class="lead">{s.get("valued", 0)} stocks '
            f'valued. {when} Every number comes from sourced filings and prices; no AI is used.</p>'
            f'<div class="chips">{chips}</div></div><div class="kpis">'
            f'<div class="kpi"><b>{flagged}</b><span>High confidence undervalued</span></div>'
            f'<div class="kpi"><b>{pct(s.get("hurdle"), 2)}</b><span>Buy hurdle a year</span></div>'
            f'<div class="kpi"><b>{pct(s.get("tbill_net"))}</b><span>364-day T-bill, net of tax</span></div>'
            f'<div class="kpi"><b>{c.get("Buy", 0)}</b><span>Buy tier</span></div></div></section>{stale}'
            f'<div class="callout warn small"><p><strong>Not financial advice.</strong> {E(DISCLAIMER)}</p></div>')


def _verdict(s: dict) -> str:
    def dicts(key: str) -> list[dict]:
        v = s.get(key)
        return [i for i in v if isinstance(i, dict)] if isinstance(v, list) else []

    items = dicts("top") + dicts("high_confidence")
    buys = list(dict.fromkeys(i.get("ticker") for i in items if i.get("tier") == "Buy" and i.get("ticker")))
    if buys:
        head = f'Buy today: {E(", ".join(buys))}.'
        sub = "These pass every check. Read each card below before acting."
    else:
        n = (s.get("counts") or {}).get("Buy", 0)
        head = "No stock is a Buy today." if not n else f"{n} stock{'s' if n > 1 else ''} rated Buy today."
        near = next(iter(dicts("near_misses") + dicts("top")), None)
        sub = ""
        if near and near.get("ticker"):
            reason = _plain_reason(near.get("binding"))
            sub = (f'Closest is <b>{E(near["ticker"])}</b> ({E(str(near.get("tier", "")))})'
                   + (f": {E(reason)}." if reason else "."))
    tb, hurdle = s.get("tbill_net"), s.get("hurdle")
    money = (f'<p>A 364-day government T-bill pays about <b>{pct(tb)}</b> a year after tax with almost no risk. A '
             f'stock\'s middle-case return must beat <b>{pct(hurdle, 2)}</b> a year to be a Buy.</p>'
             if None not in (tb, hurdle) else "")
    return (f'<section class="card" id="verdict"><h2>Today in one sentence</h2><p class="big">{head}</p>'
            + (f"<p>{sub}</p>" if sub else "") + money
            + '<p class="small muted"><b>How to use this page</b></p><ol class="small">'
              "<li>Read the sentence above. Most days the answer is to wait.</li>"
              f'<li>Scan the cards: {tier_badge("Buy")} passes every check, {tier_badge("Watch")} misses one, '
              f'{tier_badge("Avoid")} misses more. The risk badge says how bumpy the ride could be.</li>'
              '<li>Unsure about a word? Open the <a href="#glossary">Jargon buster</a> or a card\'s '
              "<b>Show the details</b>.</li></ol></section>")


def _glossary(s: dict, retro: dict | None = None) -> str:
    cfg = config.settings()
    v, hc = cfg.get("valuation", {}), cfg.get("high_confidence", {})
    mos, years = pct(v.get("mos_threshold", 0.15), 0), v.get("horizon_years", 3)
    prem = pct(cfg.get("buy", {}).get("hurdle_premium_over_tbill", 0.05), 0)
    spread = v.get("max_model_spread")
    cal = (((retro or {}).get("reconstructed") or {}).get("12") or {}).get("calibration")
    cal_now = (f" In past tests only {pct(cal, 0)} of 12 month outcomes landed between bad and good, so real "
               "results often fall outside these ranges." if cal is not None else
               " Real results often fall outside these ranges.")
    terms = [
        ("Fair value", "What the rules estimate one share is worth, from the company's own reported profits, "
                       "dividends and book value."),
        ("Upside (margin of safety)",
         f"How far the price would have to rise to reach fair value: fair value divided by price, minus 1. 25% means "
         f"you pay KES 80 for KES 100 of value. A Buy needs {mos} or more from at least half the methods that apply "
         f"(minimum two)" + (f", and the highest estimate can be at most {spread:g}x the lowest." if spread else ".")),
        ("Bad / middle / good case (bear, base, bull)",
         f"Three scenario estimates of the average yearly return over the next {years} years, after trading costs "
         f"and dividend tax. The middle case is not a forecast of the most likely result.{cal_now}"),
        ("Hurdle", f"The yearly return a stock must beat to be a Buy: the T-bill rate plus {prem} for taking stock "
                   "market risk."),
        ("T-bill", "A short loan to the Kenyan government. Low risk, so it is the yardstick every stock must beat."),
        ("Buy, Watch, Avoid", "Buy passes every check. Watch passes the business health check but misses one other "
                              "check. Avoid misses more, fails the health check or its valuation methods disagree too "
                              "much."),
        ("High confidence", f"A stricter Buy: {hc.get('min_agreeing_models', 3)} or more valuation methods agree and "
                            "the business scores well on health checks."),
        ("Risk level", "Low, Moderate or High, from price swings, how easily it trades, debt or bad loans and "
                       "company warnings. It never changes the tier; it tells you how bumpy the ride could be."),
        ("Score (composite)", f"The number that orders stocks within each tier. Today's mix: {_weights_plain(s)}."),
        ("Gates", "The pass or fail checks a stock must clear to be a Buy."),
        ("NASI", "The index of all shares on the Nairobi Securities Exchange. Picks are judged against it. It tracks "
                 "prices only, so it leaves out dividends."),
        ("IC (information coefficient)", "How well the score predicted later returns. Above 0 helps, above 0.05 "
                                         "is useful, below 0 means it pointed the wrong way."),
        ("Calibration", "How often real returns landed inside the bad to good range. The ranges are scenarios, not "
                        "statistical bands; the project checks them against a goal of about 80%"
                        + (f", and so far it is {pct(cal, 0)}, so the ranges are too narrow." if cal is not None and
                           cal < 0.6 else f"; so far it is {pct(cal, 0)}." if cal is not None else ".")),
    ]
    return ('<details class="fold" id="glossary"><summary><h2>Jargon buster</h2></summary><dl>'
            + "".join(f"<dt>{E(k)}</dt><dd>{E(d)}</dd>" for k, d in terms) + "</dl></details>")


def _high_conf(s: dict, cal: float | None = None) -> str:
    hurdle, flagged, near = s.get("hurdle"), s.get("high_confidence") or [], s.get("near_misses") or []
    tb = s.get("tbill_net")
    out = [f'<section class="card" id="high-confidence"><h2>High confidence undervalued</h2>'
           f'<p class="small muted">{_inline(s.get("rule", ""))}</p>']
    if flagged:
        out.append('<div class="grid">' + "".join(_stock_card(i, hurdle, gates=True, tbill=tb, cal=cal)
                                                  for i in flagged) + "</div>")
    else:
        out.append('<div class="empty"><b>No stock clears all four gates today.</b> These are the closest '
                   'candidates and the gates they still fail.</div>')
        out.append('<div class="grid">' + "".join(_stock_card(i, hurdle, gates=True, tbill=tb, cal=cal) for i in near)
                   + "</div>" if near else "")
    return "".join(out) + "</section>"


def _alerts_changes(s: dict) -> str:
    ch, alerts = s.get("changes") or {}, s.get("alerts") or []
    since = f'since {E(ch["prev_date"])}' if ch.get("prev_date") else "(first brief, nothing to compare yet)"
    chips = [("Entered top 5", ", ".join(ch.get("top_in") or []) or "none"),
             ("Left top 5", ", ".join(ch.get("top_out") or []) or "none"), ("Tier changes", ch.get("tiers", 0)),
             ("Threshold crossings", ch.get("crossings", 0)), ("New announcements", ch.get("announcements", 0)),
             ("Unusual price moves", ch.get("moves", 0))]
    al = ("<ul>" + "".join(f"<li>{_inline(a)}</li>" for a in alerts) + "</ul>") if alerts else (
        '<p class="muted small">No material change today: no new Buy, no Buy dropped and no profit warning.</p>')
    return (f'<div class="two"><section class="card"><h2>Alerts</h2>{al}</section><section class="card">'
            f'<h2>What changed</h2><p class="small muted">Changes {since}.</p><div class="chips">'
            + "".join(f'<span class="chip">{E(k)} <b>{E(str(v))}</b></span>' for k, v in chips)
            + '</div><p class="small"><a href="daily.html#what-changed">Details in the daily brief</a></p>'
              '</section></div>')


def _top(s: dict, cal: float | None = None) -> str:
    top = s.get("top") or []
    if not top:
        return ""
    return (f'<section id="top5"><h2>Top 5 today</h2><p class="small muted">Buys first, then Watch, then Avoid. Within '
            f'each group the score orders them: {E(_weights_plain(s))}. A high rank is not a buy signal; only the Buy '
            f'tier is. Each card explains the score and what blocks a Buy.</p><div class="grid">'
            + "".join(_stock_card(i, s.get("hurdle"), why=True, tbill=s.get("tbill_net"), cal=cal) for i in top)
            + "</div></section>")


def _ranking(s: dict) -> str:
    rows = s.get("ranking") or []
    if not rows:
        return ""
    lvl = {"High": 3, "Moderate": 2, "Low": 1}

    def num(r: dict, k: str, f) -> str:
        return '<span class="muted" title="valuation methods disagree">unclear</span>' if r.get("dispersed") else f(r.get(k))

    body = "".join(
        f'<tr><td>{r["rank"]}</td><td><b>{E(r["ticker"])}</b></td><td>{E(r["name"])}</td><td>{E(r["sector"])}</td>'
        f'<td data-v="{E(r["tier"])}">{tier_badge(r["tier"], (r.get("conviction") or {}).get("flag", False))}</td>'
        f'<td data-v="{lvl.get((r.get("risk") or {}).get("level"), 0)}">{risk_badge((r.get("risk") or {}).get("level"), "")}'
        f'</td><td>{kes(r.get("price"))}</td><td>{num(r, "mos", _sp)}</td><td>{num(r, "bear", pct)}</td>'
        f'<td>{num(r, "base", _sp)}</td><td>{num(r, "bull", pct)}</td><td>{pct(r.get("dividend_yield"))}</td>'
        f'<td>{r["composite"]:.2f}</td></tr>' if r.get("composite") is not None else "" for r in rows)
    heads = ["#", "Ticker", "Name", "Sector", "Tier", "Risk", "Price", "Upside", "Bear", "Base", "Bull",
             "Yield", "Score"]
    return ('<section class="card" id="ranking"><h2>Full ranking</h2><p class="small muted">Click a column to sort. '
            'Returns are a year, net of costs and withholding tax.</p><div class="table-wrap"><table class="data '
            'sortable"><thead><tr>' + "".join(f"<th>{h}</th>" for h in heads) + f"</tr></thead><tbody>{body}"
            "</tbody></table></div></section>")


def _growth_chart(detail: list[dict]) -> str:
    pts, a, b, c = [], 1.0, 1.0, 1.0
    for d in sorted(detail, key=lambda d: d["start"]):
        if d.get("top_return") is None or d.get("universe") is None:
            continue
        if not pts:
            pts.append((d["start"], 1.0, 1.0, 1.0))
        a, b, c = a * (1 + d["top_return"]), b * (1 + d["universe"]), c * (1 + (d.get("nasi") or 0.0))
        pts.append((d.get("end") or d["start"], a, b, c))
    if len(pts) < 3:
        return ""
    W, H, L, R, T, B = 720, 250, 40, 12, 10, 24
    top = max(max(p[1:]) for p in pts) * 1.05
    step = 1 if top <= 6 else 2 if top <= 12 else 5

    def x(i: int) -> float:
        return L + i * (W - L - R) / (len(pts) - 1)

    def y(v: float) -> float:
        return T + (1 - v / top) * (H - T - B)

    grid = "".join(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}x</text>'
                   for v in range(0, int(top) + 1, step))
    years, seen = [], set()
    for i, p in enumerate(pts):
        yr = p[0][:4]
        if yr not in seen:
            seen.add(yr)
            years.append(f'<text x="{x(i):.1f}" y="{H - 6}" text-anchor="middle">{yr}</text>')
    series = [(1, "var(--brand)", "Top 5 each month"), (2, "var(--info)", "Equal-weight universe"),
              (3, "var(--muted)", "NASI")]
    lines = "".join(f'<polyline fill="none" stroke="{col}" stroke-width="2.2" points="'
                    + " ".join(f"{x(i):.1f},{y(p[k]):.1f}" for i, p in enumerate(pts)) + '"/>'
                    for k, col, _ in series)
    legend = "".join(f'<span><i style="background:{col}"></i>{n} <b>{pts[-1][k]:.2f}x</b></span>'
                     for k, col, n in series)
    return (f'<div class="chart"><div class="legend">{legend}</div><svg viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Growth of 1 shilling: top 5 {pts[-1][1]:.2f}x, universe {pts[-1][2]:.2f}x, NASI '
            f'{pts[-1][3]:.2f}x"><g class="grid">{grid}</g>{"".join(years)}{lines}</svg><p class="small muted">'
            f'Growth of KES 1 from {E(pts[0][0])} to {E(pts[-1][0])}, rebalanced monthly into the top 5 the engine '
            f'ranked with data published by each date and today\'s interest rates. '
            f'Before trading costs; dividends added without reinvestment; NASI is price only.</p></div>')


def _ic_table(ic: dict) -> str:
    hs = ["1", "3", "6", "12"]
    rows = []
    for sig, label in SIGNALS.items():
        if sig not in ic:
            continue
        cells = []
        for h in hs:
            v = (ic[sig].get(h) or {}) if isinstance(ic[sig], dict) else {}
            val = v.get("ic")
            if val is None:
                cells.append('<td class="ic muted">n/a</td>')
                continue
            shade = min(abs(val) / 0.15, 1) * 45
            col = "var(--pos)" if val >= 0 else "var(--neg)"
            cells.append(f'<td class="ic" style="background:color-mix(in srgb,{col} {shade:.0f}%,transparent)" '
                         f'title="n={v.get("n")}, positive in {pct(v.get("positive"), 0)} of months">{val:+.3f}</td>')
        rows.append(f"<tr><td><b>{E(label)}</b></td>{''.join(cells)}</tr>")
    if not rows:
        return ""
    return ('<div class="table-wrap"><table class="data heat"><thead><tr><th>Signal</th><th>1 month</th>'
            '<th>3 months</th><th>6 months</th><th>12 months</th></tr></thead><tbody>' + "".join(rows)
            + "</tbody></table></div><p class=\"small muted\">Spearman rank IC between each signal and the forward "
              "total return, averaged across monthly reconstructions. Above 0.05 is useful for a stock ranking.</p>")


def _miss_bars(att: dict) -> str:
    counts = att.get("counts") or {}
    total = sum(counts.values())
    if not total:
        return ""
    rows = "".join(f'<div class="row"><span>{E(MISSES.get(k, k))}</span><div class="track"><div class="fill'
                   f'{"" if k == "caught" else " miss"}" style="width:{counts[k] / total * 100:.1f}%"></div></div>'
                   f'<span class="num">{counts[k]} ({pct(counts[k] / total, 0)})</span></div>'
                   for k in sorted(counts, key=lambda k: (k != "caught", -counts[k])))
    return (f'<div class="bars">{rows}</div><p class="small muted">The actual top 5 performers over each following '
            f'12 months ({total} winners), classified by what the engine knew at the start date.</p>')


def _track_record(r: dict) -> str:
    rec = (r.get("reconstructed") or {})
    y12 = rec.get("12") or {}
    if not y12:
        return ""
    kpis = [(pct(y12.get("top_return")), "Top 5, average 12 month total return"),
            (pct(y12.get("universe")), "Equal-weight universe, same windows"),
            (pct(y12.get("nasi")), "NASI, same windows"), (pct(y12.get("hit_rate")), "Hit rate against the universe"),
            (f'{y12["ic"]:+.3f}' if y12.get("ic") is not None else "n/a", "Rank IC of the composite"),
            (pct(y12.get("calibration"), 0), "Outcomes inside the bear to bull range (goal about 80%)")]
    cal = y12.get("calibration")
    note = (f'<div class="callout small"><p><b>Ranges are too narrow.</b> Only {pct(cal, 0)} of 12 month outcomes '
            f'landed inside the projected bear to bull range against a goal of about 80%, so treat each range as a '
            f'rough scenario and size positions for wider swings.</p></div>') if cal is not None and cal < 0.6 else ""
    live = (f'<p class="small muted">Live ledger started {E(str(r.get("live_first")))} with '
            f'{r.get("live_dates", 0)} trading day(s); live scores appear once a month of outcomes exists. The figures '
            f'above are reconstructions over {r.get("recon_dates", 0)} month-ends from '
            f'{E(str(r.get("recon_first")))}.</p>') if r.get("live_first") else ""
    caveat = ('<p class="small muted"><b>Backtest, in-sample.</b> The current weights were chosen on this same history '
              "and every month uses today's interest rates, so these figures flatter the method. Treat them as an "
              "upper bound until the live record builds up.</p>")
    return ('<section class="card" id="track-record"><h2>Track record (backtest)</h2>' + caveat + '<div class="kpis">'
            + "".join(f'<div class="kpi"><b>{v}</b><span>{E(k)}</span></div>' for v, k in kpis) + "</div>"
            + _growth_chart((rec.get("1") or {}).get("detail") or []) + note + live + "</section>")


def _evidence(r: dict) -> str:
    ic = _ic_table(r.get("ic") or {})
    bars = _miss_bars((r.get("attribution") or {}).get("12") or {})
    if not (ic or bars):
        return ""
    return (f'<div class="two"><section class="card"><h2>Which signals work</h2>{ic}</section><section class="card">'
            f'<h2>Why winners were missed</h2>{bars}<p class="small"><a href="retrospective.html">Full retrospective'
            f'</a></p></section></div>')


def _report_links(present: list[tuple]) -> str:
    return ('<section><h2>Reports</h2><div class="links">'
            + "".join(f'<a href="{dst}"><b>{E(label)}</b><span>{E(desc)}</span></a>' for _, dst, label, desc in present)
            + '<a href="archive.html"><b>Archive</b><span>Every dated daily brief and weekly report.</span></a>'
              "</div></section>")


def dashboard(snap: dict | None, retro: dict | None, present: list[tuple]) -> str:
    parts = []
    if snap:
        cal = (((retro or {}).get("reconstructed") or {}).get("12") or {}).get("calibration")
        for fn in (_hero, _verdict, partial(_glossary, retro=retro), partial(_high_conf, cal=cal),
                   partial(_top, cal=cal), _alerts_changes):
            try:
                parts.append(fn(snap))
            except Exception as exc:  # one broken panel must not take the site down
                parts.append(f'<div class="empty small">Panel unavailable: {E(type(exc).__name__)}</div>')
    else:
        parts.append('<section class="hero"><div><p class="eyebrow">NSE Value Agent</p><h1>Undervalued NSE stocks, '
                     'ranked by fixed rules</h1><p class="lead">No daily snapshot yet. Run the daily brief to fill this '
                     f'dashboard.</p></div></section><div class="callout warn small"><p><strong>Not financial advice.'
                     f'</strong> {E(DISCLAIMER)}</p></div>')
    if retro:
        for fn in (_track_record, _evidence):
            try:
                parts.append(fn(retro))
            except Exception as exc:
                parts.append(f'<div class="empty small">Panel unavailable: {E(type(exc).__name__)}</div>')
    if snap:
        try:
            parts.append(_ranking(snap))
        except Exception as exc:
            parts.append(f'<div class="empty small">Ranking unavailable: {E(type(exc).__name__)}</div>')
    parts.append(_report_links(present))
    return "".join(parts)


def _load_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build() -> list[Path]:
    """Render the dashboard, reports and archive into config.SITE for GitHub Pages."""
    site, reports = config.SITE, config.REPORTS
    site.mkdir(parents=True, exist_ok=True)
    present = [p for p in PAGES if (reports / p[0]).exists()]
    nav = [("index.html", "Dashboard")] + [(dst, label) for _, dst, label, _ in present] + [("archive.html", "Archive")]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    written: list[Path] = []

    def page(name: str, title: str, body: str, active: str) -> None:
        up = "../" * name.count("/")
        links = "".join(f'<a href="{up}{dst}"{" aria-current=page" if dst == active else ""}>{E(label)}</a>'
                        for dst, label in nav) + f'<a href="{REPO}">Source</a>'
        doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
               f'content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">'
               f'<meta name="description" content="Rule-based value agent for the Nairobi Securities Exchange: '
               f'undervalued stocks, risk profiles and projected returns.">'
               f'<title>{E(title)} | NSE Value Agent</title><link rel="icon" href="{FAVICON}"><style>{CSS}</style>'
               f'</head><body><a class="skip" href="#main">Skip to content</a><header class="top"><div class="wrap '
               f'bar"><a class="brand" href="{up}index.html">{LOGO}<span>NSE Value Agent<small>Nairobi Securities '
               f'Exchange</small></span></a><nav class="nav" aria-label="Main">{links}</nav></div></header>'
               f'<main id="main" class="wrap">{body}</main><footer class="foot"><div class="wrap"><p><b>Rule-based, '
               f'no AI.</b> Fundamentals come from sourced company filings, prices from public NSE data and rates '
               f'from CBK.</p><p><b>Not financial advice.</b> {E(DISCLAIMER)}</p><p>Version {__version__}. Built '
               f'{stamp}. <a href="{REPO}">Source on GitHub</a>.</p></div></footer><script>{JS}</script></body>'
               f'</html>\n')
        p = site / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc, encoding="utf-8", newline="\n")
        written.append(p)

    page("index.html", "Dashboard", dashboard(_load_json(reports / "daily" / "latest.json"),
                                              _load_json(config.DATA / "retrospective.json"), present), "index.html")
    for src, dst, label, _ in present:
        page(dst, label, render_markdown((reports / src).read_text(encoding="utf-8")), dst)

    sections = []
    for sub, src_dir, label, latest in (("daily", reports / "daily", "Daily briefs", "daily.html"),
                                        ("reports", reports, "Weekly reports", "weekly.html")):
        dates = sorted(p.stem for p in src_dir.glob("*.md") if DATED.fullmatch(p.name)) if src_dir.exists() else []
        for i, d in enumerate(dates):
            older = f'<a href="{dates[i - 1]}.html">&larr; {dates[i - 1]}</a>' if i else "<span></span>"
            newer = f'<a href="{dates[i + 1]}.html">{dates[i + 1]} &rarr;</a>' if i + 1 < len(dates) else "<span></span>"
            pager = (f'<nav class="pager" aria-label="{label}">{older}<a href="../archive.html#{sub}">All '
                     f'{label.lower()}</a>{newer}</nav>')
            body = pager + render_markdown((src_dir / f"{d}.md").read_text(encoding="utf-8")) + pager
            page(f"{sub}/{d}.html", f"{label[:-1]} {d}", body, "archive.html")
        months: dict[str, list[str]] = {}
        for d in reversed(dates):
            months.setdefault(d[:7], []).append(d)
        items = "".join(f'<h3>{datetime.strptime(m, "%Y-%m").strftime("%B %Y")}</h3><div class="chips">'
                        + "".join(f'<a class="chip" href="{sub}/{d}.html">{d}</a>' for d in ds) + "</div>"
                        for m, ds in months.items()) or '<p class="muted">None yet.</p>'
        sections.append(f'<section class="card months" id="{sub}"><h2>{label}</h2><p class="small"><a href="{latest}">'
                        f'Latest</a></p>{items}</section>')
    page("archive.html", "Archive", "<h1>Archive</h1>" + "".join(sections), "archive.html")
    redirect = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=archive.html#daily">'
                '<link rel="canonical" href="archive.html#daily"><a href="archive.html#daily">Daily brief archive</a>\n')
    (site / "daily-archive.html").write_text(redirect, encoding="utf-8", newline="\n")
    (site / ".nojekyll").write_text("", encoding="utf-8")
    return written
