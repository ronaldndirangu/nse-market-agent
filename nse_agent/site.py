"""Static GitHub Pages site: a dashboard, styled report pages and a dated archive."""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from functools import partial
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from . import DISCLAIMER, __version__, config
from .fmt import consumer_binding, estimate_reliable, kes, pct
from .health import EAT
from .risk import FACTORS

REPO = "https://github.com/ronaldndirangu/nse-market-agent"
DATED = re.compile(r"\d{4}-\d{2}-\d{2}\.md")
PAGES = [  # (source under reports/, output page, nav label, description)
    ("daily/latest.md", "daily.html", "Daily brief", "Today's top 5, tiers, risk profile and what changed."),
    ("latest.md", "weekly.html", "Weekly report", "Fair value ranges, theses and data gaps for every stock."),
    ("retrospective.md", "retrospective.html", "Track record",
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
        '<rect width="32" height="32" rx="8" fill="var(--cp-link)"/><path d="M7 22l6-6 4 4 8-9" fill="none" stroke="var(--cp-surface)" '
        'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="25" cy="11" r="2.4" '
        'fill="var(--cp-surface)"/></svg>')
FAVICON = "data:image/svg+xml," + quote('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
                                      '<text x="4" y="26" font-size="28">N</text></svg>')

CSS = """
:root {
  color-scheme: light;
  --cp-bg: #f7f4ef;
  --cp-bg-elevated: #fcfbf8;
  --cp-surface: #ffffff;
  --cp-surface-soft: #f5f5f5;
  --cp-border: #dedede;
  --cp-border-strong: #919191;
  --cp-text: #242424;
  --cp-text-muted: #5c5c5c;
  --cp-text-soft: #6f6f6f;
  --cp-accent: #b11f4b;
  --cp-accent-hover: #9a1a41;
  --cp-accent-soft: rgba(177, 31, 75, 0.08);
  --cp-accent-fg: #ffffff;
  --cp-success: #16a34a;
  --cp-danger: #dc2626;
  --cp-warning: #f59e0b;
  --cp-link: #0078d4;
  --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.12);
  --cp-overlay: rgba(255, 255, 255, 0.8);
  --cp-panel: rgba(255, 255, 255, 0.86);
  --cp-panel-strong: rgba(255, 255, 255, 0.96);
  --cp-sheen: rgba(255, 255, 255, 0.55);
  --cp-highlight: rgba(177, 31, 75, 0.12);
}
html[data-theme="dark"] {
  color-scheme: dark;
  --cp-bg: #3d3b3a;
  --cp-bg-elevated: #343231;
  --cp-surface: #292929;
  --cp-surface-soft: #2e2e2e;
  --cp-border: #474747;
  --cp-border-strong: #5f5f5f;
  --cp-text: #dedede;
  --cp-text-muted: #919191;
  --cp-text-soft: #b0b0b0;
  --cp-accent: #fd8ea1;
  --cp-accent-hover: #fb7b91;
  --cp-accent-soft: rgba(253, 142, 161, 0.14);
  --cp-accent-fg: #1a1a1a;
  --cp-success: #4ade80;
  --cp-danger: #f87171;
  --cp-warning: #fbbf24;
  --cp-link: #4da6ff;
  --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
  --cp-overlay: rgba(41, 41, 41, 0.88);
  --cp-panel: rgba(41, 41, 41, 0.72);
  --cp-panel-strong: rgba(41, 41, 41, 0.96);
  --cp-sheen: rgba(255, 255, 255, 0.04);
  --cp-highlight: rgba(253, 142, 161, 0.12);
}
*{box-sizing:border-box}html{scroll-padding-top:5rem}
body{margin:0;background:var(--cp-surface);color:var(--cp-text);
font:16px/1.55 "Segoe UI",Aptos,Calibri,-apple-system,BlinkMacSystemFont,sans-serif}
a{color:color-mix(in srgb,var(--cp-link) 90%,var(--cp-text));text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1240px;margin:0 auto;padding:0 24px}
a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible,[tabindex]:focus-visible{
outline:3px solid var(--cp-text);outline-offset:3px}
button,input{font:inherit}button{cursor:pointer}
.skip{position:absolute;left:-999px;top:.5rem;background:var(--cp-surface);padding:.5rem 1rem;border-radius:10px;z-index:9}
.skip:focus{left:.5rem}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.top{position:sticky;top:0;z-index:5;background:var(--cp-surface);border-bottom:1px solid var(--cp-border)}
.bar{display:flex;align-items:center;gap:32px;min-height:76px}
.brand{display:flex;align-items:center;gap:.6rem;color:var(--cp-text);font-weight:700;white-space:nowrap}
.brand:hover{text-decoration:none}.brand small{display:block;font-weight:500;font-size:.72rem;color:var(--cp-text-muted)}
.nav{display:flex;flex-wrap:wrap;gap:.25rem;flex:1;padding:.4rem 0;align-items:center;min-width:0}
.nav a,.nav summary{white-space:nowrap;padding:10px 12px;min-height:44px;border-radius:10px;color:var(--cp-text-muted);
font-weight:550;font-size:.9rem;cursor:pointer}
.nav a:hover,.nav summary:hover{background:var(--cp-surface-soft);color:var(--cp-text);text-decoration:none}
.nav a{border-bottom:2px solid transparent;border-radius:0}
.nav a[aria-current=page]{border-bottom-color:var(--cp-link);color:var(--cp-link);font-weight:650}
.nav details{position:relative}.nav details div{position:absolute;right:0;background:var(--cp-surface);
border:1px solid var(--cp-border);border-radius:10px;min-width:180px;padding:.5rem;z-index:6}
.nav details div a{display:block}
main.wrap{padding-top:32px;padding-bottom:48px}
h1{font-size:clamp(2rem,4vw,2.5rem);line-height:1.14;letter-spacing:-.025em;margin:8px 0 12px}
h2{font-size:1.25rem;line-height:1.3;letter-spacing:-.015em;margin:32px 0 12px}
h3{font-size:1.02rem;margin:1.4rem 0 .5rem}
.muted{color:var(--cp-text-muted)}.small{font-size:.85rem}.pos,.neg{color:var(--cp-text);font-weight:600}
.num{font-variant-numeric:tabular-nums}
.card{background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:16px;
padding:24px;margin:16px 0}
.card>h2:first-child{margin-top:.1rem}
.hero{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:1.2rem;align-items:center}
.eyebrow{font-size:.8rem;font-weight:600;color:var(--cp-text-soft);margin:0}
.lead{font-size:1.02rem;color:var(--cp-text-muted);margin:.2rem 0 .8rem}
.chips{display:flex;flex-wrap:wrap;gap:.45rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem}
.hero .kpis{grid-template-columns:1fr 1fr}
.kpi{background:var(--cp-surface-soft);border-radius:10px;padding:.75rem .9rem}
.kpi b{display:block;font-size:1.45rem;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi span{font-size:.8rem;color:var(--cp-text-muted)}
.badge{display:inline-flex;align-items:center;gap:.25rem;padding:.08rem .55rem;border-radius:999px;font-size:.78rem;
font-weight:650;line-height:1.55;border:1px solid var(--cp-border);color:var(--cp-text)}
.b-buy,.r-low,.c-high{background:color-mix(in srgb,var(--cp-success) 14%,var(--cp-surface))}
.b-watch,.r-moderate,.c-medium,.c-moderate{background:color-mix(in srgb,var(--cp-warning) 16%,var(--cp-surface))}
.b-avoid,.b-muted,.c-low{background:var(--cp-surface-soft);color:var(--cp-text-muted)}
.r-high{background:color-mix(in srgb,var(--cp-danger) 13%,var(--cp-surface))}
.b-flag{background:var(--cp-link);color:var(--cp-surface)}
.chip{display:inline-flex;gap:.35rem;align-items:center;background:var(--cp-surface-soft);border-radius:10px;padding:.3rem .75rem;
font-size:.86rem}.chip b{font-variant-numeric:tabular-nums}
.callout{border:1px solid var(--cp-border);border-left:4px solid var(--cp-border-strong);background:var(--cp-surface);border-radius:10px;
margin:1rem 0;padding:.6rem 1rem}.callout p{margin:.3rem 0}
.callout.warn{border-left-color:var(--cp-warning);background:color-mix(in srgb,var(--cp-warning) 7%,var(--cp-surface))}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(310px,100%),1fr));gap:1rem}
.stock{background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:16px;padding:1rem;display:flex;
flex-direction:column;gap:.65rem;min-width:0}
.stock.flagged{border-color:var(--cp-text);box-shadow:0 0 0 1px var(--cp-text)}
.stock header{display:flex;justify-content:space-between;gap:.5rem;align-items:flex-start}
.tk{font-weight:700;font-size:1.1rem;color:var(--cp-text)}.rank{color:var(--cp-text-muted);font-weight:700;margin-right:.3rem}
.nm{display:block;color:var(--cp-text-muted);font-size:.83rem}.badges{display:flex;gap:.3rem;flex-wrap:wrap;justify-content:flex-end}
.pricebox{display:flex;justify-content:space-between;align-items:flex-end;gap:.6rem}
.price{font-size:1.25rem;font-weight:700;font-variant-numeric:tabular-nums}
.spark{margin:0;text-align:right}.spark svg{width:150px;height:36px;display:block}
.spark polyline{fill:none;stroke-width:1.6;stroke:currentColor;vector-effect:non-scaling-stroke}
.spark figcaption{font-size:.75rem}
.facts{display:grid;grid-template-columns:1fr 1fr;gap:.45rem .8rem;margin:0}
.facts div{min-width:0}.facts dt{font-size:.74rem;color:var(--cp-text-muted)}
.facts dd{margin:0;font-weight:650;font-variant-numeric:tabular-nums}
.rangebar svg{width:100%;height:40px;display:block}
.rangebar .cap{display:flex;justify-content:space-between;font-size:.76rem;color:var(--cp-text-muted)}
.rangebar .cap b{color:var(--cp-text);font-variant-numeric:tabular-nums}
.gates{list-style:none;padding:0;margin:0;display:grid;gap:.25rem;font-size:.84rem}
.gates li{display:flex;gap:.45rem}.gates .ok,.gates .no{color:var(--cp-text);font-weight:700}
.why{font-size:.88rem;color:var(--cp-text-muted);margin:0;border-top:1px dashed var(--cp-border);padding-top:.55rem}
.factors{display:flex;flex-wrap:wrap;gap:.3rem}
.empty{background:var(--cp-surface-soft);border-radius:10px;padding:.7rem 1rem;margin:.6rem 0 1rem}
.table-wrap{overflow:auto;border:1px solid var(--cp-border);border-radius:10px;margin:1rem 0;max-height:75vh;
background:var(--cp-surface);max-width:100%}
table.data{border-collapse:separate;border-spacing:0;width:100%;font-size:.88rem}
table.data th,table.data td{padding:.5rem .7rem;text-align:left;white-space:nowrap;border-bottom:1px solid var(--cp-border)}
table.data td{font-variant-numeric:tabular-nums}
table.data thead th{position:sticky;top:0;background:var(--cp-surface-soft);font-weight:650;z-index:1;color:var(--cp-text-muted);
font-size:.8rem;text-transform:none}
table.data tbody tr:nth-child(even){background:var(--cp-surface-soft)}
table.data tbody tr:hover{background:var(--cp-surface-soft)}table.data tbody tr:last-child td{border-bottom:0}
table.sortable th{user-select:none}.sort-button{border:0;background:var(--cp-surface-soft);color:var(--cp-text);
min-height:44px;min-width:24px;padding:4px 0;font-weight:650;text-align:left;white-space:nowrap}
.sort-button:after{content:" \\2195";opacity:.5}
table.sortable th[aria-sort=ascending] .sort-button:after{content:" \\2191";opacity:1}
table.sortable th[aria-sort=descending] .sort-button:after{content:" \\2193";opacity:1}
.prose{background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:16px;padding:1.2rem 1.6rem 1.6rem;
overflow-wrap:anywhere;min-width:0}
.prose ul{padding-left:1.25rem}.prose li{margin:.2rem 0}.prose code{background:var(--cp-surface-soft);padding:.05rem .3rem;
border-radius:5px;font: .88em Consolas,"Courier New",Courier,monospace}
.prose>p,.prose>ul,.prose>ol{max-width:75ch}
.toc{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 1rem}
.toc a{background:var(--cp-surface-soft);border-radius:10px;padding:.25rem .7rem;font-size:.82rem;color:var(--cp-text)}
details.fold{border:1px solid var(--cp-border);border-radius:10px;margin:1rem 0;padding:0 1rem;min-width:0}
details.fold summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:.5rem}
details.fold summary::-webkit-details-marker{display:none}
details.fold summary:before{content:"\\25B8";color:var(--cp-text-muted)}details.fold[open] summary:before{content:"\\25BE"}
details.fold summary h2{margin:.75rem 0;font-size:1.05rem}
details.fold>summary{min-height:56px}
.heat td.ic{text-align:center;font-weight:650}
.bars{display:grid;gap:.45rem}.bars .row{display:grid;grid-template-columns:210px 1fr 92px;gap:.6rem;
align-items:center;font-size:.86rem}.bars .num{white-space:nowrap;text-align:right}
.bars .track{background:var(--cp-surface-soft);border-radius:10px;height:10px;overflow:hidden}
.bars .fill{height:100%;background:var(--cp-text);border-radius:10px}.bars .fill.miss{background:var(--cp-warning)}
.chart svg{width:100%;height:auto;display:block}.chart text{fill:var(--cp-text-muted);font-size:11px}
.chart .grid line{stroke:var(--cp-border)}.legend{display:flex;flex-wrap:wrap;gap:1rem;font-size:.85rem;margin:.3rem 0}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:.35rem;vertical-align:middle}
.two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.two>*{min-width:0}.two>.card{margin:0}
.links{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(230px,100%),1fr));gap:.8rem}
.links a{display:block;background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:10px;padding:.85rem 1rem;
color:var(--cp-text)}.links a:hover{border-color:var(--cp-text);text-decoration:none}
.links b{display:block}.links span{font-size:.84rem;color:var(--cp-text-muted)}
.pager{display:flex;justify-content:space-between;gap:.6rem;margin:.4rem 0 1rem;font-size:.9rem}
.months h3{margin:1rem 0 .4rem;font-size:.95rem;color:var(--cp-text-muted)}.months .chips a{color:var(--cp-text)}
.foot{border-top:1px solid var(--cp-border);color:var(--cp-text-muted);font-size:.84rem;padding:1.4rem 0 2rem}
.foot p{margin:.25rem 0}
.plain{background:var(--cp-surface-soft);border-radius:10px;padding:.55rem .8rem;margin:0;font-size:.9rem}
.plain p{margin:.2rem 0}.plain b{color:var(--cp-text)}
#verdict .big{font-size:1.15rem;font-weight:650;margin:.2rem 0 .5rem}#verdict ol{margin:.4rem 0 0;padding-left:1.2rem}
#verdict li{margin:.25rem 0}.facts dt[title]{cursor:help;text-decoration:underline dotted}
details.more summary{cursor:pointer;color:var(--cp-text);font-size:.88rem;font-weight:600;min-height:44px;
display:flex;align-items:center;gap:8px}
details.more summary:after{content:"";width:7px;height:7px;flex-shrink:0;margin-left:auto;margin-right:4px;
border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg)}
details.more[open]>summary:after{transform:rotate(225deg)}
details.more summary>.icon{display:none}
details.more[open] summary{margin-bottom:.5rem}details.more>*+*{margin-top:.5rem}
#glossary dl{margin:0 0 1rem}#glossary dt{font-weight:650;margin-top:.6rem}#glossary dd{margin:.1rem 0 0;color:var(--cp-text-muted)}
[hidden]{display:none!important}.stock p,.stock dd,.gates span{overflow-wrap:anywhere}
.health-line{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap}.health-line p{margin:.2rem 0}
.icon{width:20px;height:20px;flex-shrink:0;vertical-align:middle}
.mobile-nav{display:none}
.brief-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:24px}
.brief-heading .lead{max-width:60ch;margin-bottom:0}
.brief-heading .eyebrow{margin-bottom:16px}
.brief-heading h1{margin-top:0}
.edition{text-align:right;font-size:.85rem;color:var(--cp-text-muted);padding-top:8px}
.edition time{display:block;color:var(--cp-text);font-weight:600}
.overview-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin:0 0 24px;
border-top:1px solid var(--cp-border);border-bottom:1px solid var(--cp-border)}
.overview-stats>div{border-right:1px solid var(--cp-border);padding:20px 24px}
.overview-stats>div:first-child{padding-left:0}.overview-stats>div:last-child{border-right:0}
.overview-stats dt{display:flex;align-items:center;justify-content:space-between;gap:8px;color:var(--cp-text-muted);font-size:.85rem}
.overview-stats dt .icon{color:var(--cp-text-soft)}
.overview-stats .metric-buy .icon{color:var(--cp-success)}
.overview-stats .metric-watch .icon{color:color-mix(in srgb,var(--cp-warning) 65%,var(--cp-text))}
.overview-stats .metric-confidence .icon{color:var(--cp-link)}
.overview-stats dd{margin:8px 0 0;font-size:2rem;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
.overview-stats .metric-note{font-size:.78rem;line-height:1.5;font-weight:400;color:var(--cp-text-muted);margin-top:8px}
.decision-layout{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:24px;margin:24px 0}
.decision-layout>*{min-width:0;margin:0}
#verdict{padding:28px;--cp-verdict:var(--cp-text-soft);border-left:4px solid var(--cp-verdict)}
#verdict[data-verdict=buy]{--cp-verdict:color-mix(in srgb,var(--cp-success) 75%,var(--cp-text))}
#verdict[data-verdict=no-buy]{--cp-verdict:color-mix(in srgb,var(--cp-danger) 80%,var(--cp-text))}
#verdict[data-verdict=verify]{--cp-verdict:color-mix(in srgb,var(--cp-warning) 55%,var(--cp-text))}
#verdict .big{font-size:clamp(1.45rem,2.5vw,2rem);line-height:1.2;letter-spacing:-.025em;margin:16px 0 12px;
color:var(--cp-verdict)}
#verdict .section-label .icon{color:var(--cp-verdict)}
.verdict-header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.decision-status{display:inline-flex;align-items:center;min-height:28px;padding:4px 10px;border-radius:999px;
border:1px solid color-mix(in srgb,var(--cp-verdict) 40%,var(--cp-border));
background:color-mix(in srgb,var(--cp-verdict) 10%,var(--cp-surface));color:var(--cp-text);
font-size:.75rem;font-weight:650}
.verdict-legend{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
#verdict .decision-copy{max-width:65ch;color:var(--cp-text-muted);margin:0 0 20px}
.section-label{display:flex;align-items:center;gap:8px;color:var(--cp-text-muted);font-size:.8rem;
font-weight:650;margin:0}
.section-label .icon{color:var(--cp-text)}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px}
.button{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:10px 16px;
border-radius:10px;border:1px solid var(--cp-border-strong);color:var(--cp-text);background:var(--cp-surface);
font-size:.88rem;font-weight:600;text-decoration:none}
.button:hover{text-decoration:none;border-color:var(--cp-text);background:var(--cp-surface-soft)}
.button.primary{background:var(--cp-link);border-color:var(--cp-link);color:var(--cp-surface)}
.button.primary:hover{background:color-mix(in srgb,var(--cp-link) 90%,var(--cp-text))}
.benchmark{background:var(--cp-surface-soft)}
.benchmark h2{font-size:1rem;margin:0 0 20px}
.benchmark dl{margin:0}.benchmark dl>div{display:flex;align-items:center;justify-content:space-between;
gap:12px;padding:14px 0;border-bottom:1px solid var(--cp-border)}
.benchmark dt{color:var(--cp-text-muted);font-size:.85rem}.benchmark dd{margin:0;font-size:1.4rem;font-weight:650}
.benchmark p{font-size:.8rem;color:var(--cp-text-muted);margin:16px 0 0;max-width:55ch}
.brief-layout{margin:32px 0}
.brief-side{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;align-items:start;margin-top:24px}
.brief-layout>*{min-width:0}.brief-main>section:first-child h2,.brief-side>section:first-child h2{margin-top:0}
.candidate-stack{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:16px}
.candidate-stack>.stock:last-child:nth-child(odd){grid-column:1/-1}
.section-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}
.section-heading h2{margin:0}.section-heading p{margin:6px 0 0;font-size:.85rem;color:var(--cp-text-muted)}
.count-label{white-space:nowrap;font-size:.8rem;padding:4px 10px;border-radius:10px;background:var(--cp-surface-soft);
color:var(--cp-text-muted)}
.stock{padding:24px;gap:20px}
.stock-identity{display:flex;align-items:center;gap:12px;min-width:0}
.company-mark{display:grid;place-items:center;flex-shrink:0;width:44px;height:44px;border-radius:10px;
background:var(--cp-surface-soft);color:var(--cp-text);font-size:.85rem;font-weight:650}
.stock .tk{font-size:1.1rem}.stock .nm{margin-top:2px;max-width:38ch}
.stock .pricebox{align-items:center;padding-bottom:16px;border-bottom:1px solid var(--cp-border)}
.stock .price{font-size:1.6rem;letter-spacing:-.025em}
.stock .facts{grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.stock .facts dt{font-size:.75rem}.stock .facts dd{font-size:1rem;margin-top:4px}
.stock-reason{font-size:.9rem;max-width:65ch;line-height:1.6;margin:0}
.stock-reason b{display:block;font-size:.78rem;color:var(--cp-text-muted);margin-bottom:4px}
.stock .more{border-top:1px solid var(--cp-border);padding-top:8px}
.stock .more summary{justify-content:space-between}
.stock-footer{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:.8rem;color:var(--cp-text-muted)}
.stock-footer a{font-size:.85rem;font-weight:650;min-height:44px;display:inline-flex;align-items:center;gap:6px}
.risk-list{list-style:none;padding:0;margin:16px 0;display:grid;gap:12px}
.risk-list li{display:flex;justify-content:space-between;align-items:start;gap:16px;font-size:.85rem}
.risk-list .risk-explanation{display:block;font-size:.78rem;color:var(--cp-text-muted);margin-top:3px;max-width:60ch}
.brief-side .card,.brief-side>.fold{margin:0}.brief-side h2{font-size:1.05rem}
.stock-finder{margin:0 0 20px;position:relative;max-width:640px}
.stock-finder label{display:block;font-weight:600;font-size:.85rem;margin-bottom:6px}
.stock-finder input{width:100%;min-height:44px;padding:10px 12px;border:1px solid var(--cp-border-strong);
border-radius:10px;background:var(--cp-surface);color:var(--cp-text);font:inherit}
.stock-matches{position:absolute;top:100%;left:0;right:0;z-index:5;max-height:360px;overflow:auto;
background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:10px;padding:8px}
.stock-matches ul{list-style:none;padding:0;margin:0}.stock-matches a{display:block;padding:10px;min-height:44px}
.stock-matches small{display:block;color:var(--cp-text-muted)}.stock-matches p{margin:8px;font-size:.85rem}
.badge.risk-badge{background:var(--cp-surface);color:var(--cp-text-muted);border:1px solid var(--cp-border-strong)}
.decision-explanation h3{margin:12px 0 8px;font-size:1rem}.decision-explanation p{margin:8px 0}
.decision-explanation{font-size:.9rem;max-width:85ch}.decision-explanation ul{padding-left:20px}
.return-drivers{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin:16px 0}
.return-drivers dt{font-size:.8rem;color:var(--cp-text-muted)}.return-drivers dd{margin:4px 0;font-weight:650}
.confidence-panel>summary h2{font-size:1rem}
.change-list{margin:16px 0 0;display:grid;gap:0}
.change-list>div{display:flex;justify-content:space-between;gap:16px;padding:12px 0;border-top:1px solid var(--cp-border)}
.change-list dt{font-size:.85rem;color:var(--cp-text-muted)}.change-list dd{margin:0;font-size:.85rem;font-weight:600;text-align:right}
.quiet-state{display:flex;align-items:start;gap:12px;color:var(--cp-text-muted);font-size:.85rem;line-height:1.6}
.quiet-state p{margin:0}.quiet-state .icon{color:var(--cp-text-soft);margin-top:3px}
.guide-steps{padding-left:20px;margin:16px 0 0;font-size:.85rem;color:var(--cp-text-muted)}
.guide-steps li{padding-left:4px;margin:12px 0}.guide-steps b{display:block;color:var(--cp-text)}
.health-panel{margin:0;padding:16px 20px;border:1px solid var(--cp-border);border-radius:10px;background:var(--cp-surface);
overflow-wrap:anywhere}
.health-panel .health-line{gap:12px 20px;font-size:.8rem;align-items:center}
.health-panel .health-line>b{display:inline-flex;align-items:center;gap:8px;font-size:.85rem}
.health-panel[data-health-state=current]{border-left:3px solid var(--cp-success)}
.health-panel[data-health-state=current] .health-line .icon{color:var(--cp-success)}
.health-panel[data-health-state=attention]{border-left:3px solid var(--cp-warning)}
.health-panel details{font-size:.85rem}.health-panel details>summary{font-size:.8rem}
.health-panel [data-update-due]{padding:12px;border-radius:10px;background:var(--cp-surface-soft);
border-left:3px solid var(--cp-warning);font-size:.85rem}
.confidence-panel{margin-top:24px;background:var(--cp-surface)}
.confidence-panel .confidence-summary{display:flex;align-items:start;gap:16px}
.confidence-panel .confidence-summary>.icon{color:var(--cp-text);width:28px;height:28px;margin-top:2px}
.confidence-panel h2{font-size:1.05rem;margin:0 0 8px}
.confidence-panel p{max-width:65ch;font-size:.85rem;color:var(--cp-text-muted);margin:0}
.research-heading{margin-top:40px;margin-bottom:16px}
.subscribe-panel{display:flex;align-items:center;justify-content:space-between;gap:24px;margin:32px 0;
background:var(--cp-surface-soft)}
.subscribe-panel h2{margin:0 0 8px}.subscribe-panel p{max-width:60ch;margin:0;font-size:.85rem;color:var(--cp-text-muted)}
.subscribe-panel .actions{flex-shrink:0}
.table-controls{display:flex;flex-wrap:wrap;align-items:end;justify-content:space-between;gap:16px;margin:20px 0}
.stock-search{flex:1;min-width:min(100%,240px);max-width:360px}.stock-search label{display:block;font-size:.85rem;
font-weight:600;margin-bottom:8px}
.stock-search input{width:100%;min-height:44px;border:1px solid var(--cp-border-strong);border-radius:10px;
padding:10px 12px;background:var(--cp-surface);color:var(--cp-text)}
.table-filters{display:flex;flex-wrap:wrap;gap:8px}.table-filters button{min-height:44px;padding:8px 12px;
border:1px solid var(--cp-border);border-radius:10px;background:var(--cp-surface);color:var(--cp-text);font-size:.85rem}
.table-filters button[aria-pressed=true]{border-color:var(--cp-text);background:var(--cp-text);color:var(--cp-surface)}
.result-count{font-size:.8rem;color:var(--cp-text-muted)}
.page-note{font-size:.8rem;color:var(--cp-text-muted);max-width:75ch;margin:24px 0}
.back-link{display:inline-flex;align-items:center;min-height:44px;gap:8px;margin-bottom:12px;font-size:.85rem}
.muted,.lead,.edition,.page-note,.benchmark p,.benchmark dt,.confidence-panel p,.subscribe-panel p,
.section-heading p,.section-label,.count-label,.stock-footer,.risk-explanation,.change-list dt,
.quiet-state,.guide-steps,.foot,.b-avoid,.b-muted,.c-low,.overview-stats dt,.overview-stats .metric-note,
.result-count,.nm,.facts dt,.rangebar .cap,.why,.links span,.months h3,#glossary dd,.kpi span,
table.data thead th{color:var(--cp-text-soft)}
table.data tbody tr:hover .muted{color:var(--cp-text)}
.prose a,.foot a,.page-note a{text-decoration:underline;text-underline-offset:3px}
@media (max-width:820px){.hero,.two{grid-template-columns:1fr}.bar{flex-direction:column;align-items:stretch;gap:0;
padding-top:.5rem}.nav{padding:.4rem 0}.nav details div{position:static}h1{font-size:1.45rem}
.prose{padding:1rem}.bars .row{grid-template-columns:minmax(0,1fr) minmax(0,1fr) 76px}}
@media(max-width:380px){.pricebox{flex-wrap:wrap}.stock header{flex-direction:column}.badges{justify-content:flex-start}}
@media(max-width:960px){.decision-layout{grid-template-columns:minmax(0,1fr)}
.benchmark dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.benchmark p{max-width:75ch}
.brief-side{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.brief-side>.card{margin:0}
.subscribe-panel{align-items:flex-start;flex-direction:column}}
@media(max-width:820px){.wrap{padding:0 16px}.bar{flex-direction:row;align-items:center;justify-content:space-between;
min-height:68px;padding-top:0;gap:12px}.nav{display:none}.mobile-nav{display:block}
.mobile-nav>summary{display:flex;align-items:center;gap:8px;cursor:pointer;min-height:44px;padding:8px 12px;
border:1px solid var(--cp-border);border-radius:10px;font-size:.85rem}
.mobile-nav nav{position:absolute;top:100%;left:0;right:0;background:var(--cp-surface);padding:16px;
border-bottom:1px solid var(--cp-border);display:grid;gap:4px;max-height:70vh;overflow:auto}
.mobile-nav nav a{padding:10px 12px;min-height:44px;border-radius:10px;color:var(--cp-text)}
.mobile-nav nav a[aria-current=page]{background:var(--cp-surface-soft);color:var(--cp-text);font-weight:650}
.brand{font-size:.85rem}.brand small{font-size:.67rem}
main.wrap{padding-top:24px}.brief-heading{gap:12px}.brief-heading h1{font-size:2rem}.edition{display:none}
.overview-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
.overview-stats>div,.overview-stats>div:first-child{padding:16px}.overview-stats>div:nth-child(2n){border-right:0}
.overview-stats>div:nth-child(-n+2){border-bottom:1px solid var(--cp-border)}.overview-stats dd{font-size:1.75rem}
.decision-layout{gap:16px;margin:20px 0}.card,#verdict{padding:20px}.brief-layout{margin:24px 0}
.stock .facts{grid-template-columns:repeat(2,minmax(0,1fr))}.stock{padding:20px;gap:16px}
.brief-side{grid-template-columns:minmax(0,1fr)}.health-panel{padding:12px 16px}
.section-heading{align-items:flex-start}.health-panel .health-line{gap:8px 16px}
.stock .plain{background:var(--cp-surface-soft)}.stock-footer{flex-wrap:wrap}}
@media(max-width:380px){.stock-identity{gap:8px}.company-mark{width:36px;height:36px}
.benchmark dl{grid-template-columns:minmax(0,1fr);gap:0}.overview-stats dt{font-size:.78rem}
.overview-stats dt .icon{width:16px;height:16px}.actions .button{width:100%}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

THEME_SCRIPT = """
(() => {
  const param = new URLSearchParams(window.location.search).get("scoutTheme");
  const theme =
    param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
})();
"""

JS = """
function openHash(){
  var e=document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if(e){if(e.tagName==='DETAILS')e.open=true;var p=e.parentElement;
    while(p){if(p.tagName==='DETAILS')p.open=true;p=p.parentElement;}}
}
openHash();window.addEventListener('hashchange',openHash);
function checkFreshness(){document.querySelectorAll('[data-update-due]').forEach(function(e){
  if(Date.now()>Date.parse(e.dataset.updateDue)){e.hidden=false;}
});}
checkFreshness();setInterval(checkFreshness,60000);
document.querySelectorAll('a[href^="#"]').forEach(function(a){
  a.addEventListener('click',function(){
    var target=document.getElementById(decodeURIComponent(a.hash.slice(1)));
    if(target&&target.tagName==='DETAILS')target.open=true;
  });
});
const explicitTheme=new URLSearchParams(location.search).get('scoutTheme');
if(explicitTheme==='light'||explicitTheme==='dark'){
  document.querySelectorAll('a[href]').forEach(function(a){
    const url=new URL(a.href,location.href);
    if(url.origin===location.origin&&(url.pathname.endsWith('.html')||url.pathname.endsWith('/'))){
      url.searchParams.set('scoutTheme',explicitTheme);a.href=url.href;
    }
  });
}
document.querySelectorAll('table.sortable').forEach(function(t){
  var ths=t.querySelectorAll('thead th');
  ths.forEach(function(th,i){
    var button=document.createElement('button');button.type='button';button.className='sort-button';
    while(th.firstChild)button.appendChild(th.firstChild);th.appendChild(button);
    function key(r){var c=r.cells[i];if(!c)return null;var s=(c.dataset.v!==undefined?c.dataset.v:c.textContent).trim();
      var k=s.replace(/KES|[,%x\\s]/gi,'');var n=Number(k);if(k!==''&&isFinite(n))return n;
      return s==='n/a'||s==='unclear'||s===''?null:s.toLowerCase();}
    function go(){var b=t.tBodies[0];if(!b)return;var asc=th.getAttribute('aria-sort')!=='ascending';
      ths.forEach(function(h){h.removeAttribute('aria-sort')});th.setAttribute('aria-sort',asc?'ascending':'descending');
      var rows=Array.prototype.slice.call(b.rows);
      rows.sort(function(x,y){var a=key(x),c=key(y);if(a===null||c===null)return a===c?0:a===null?1:-1;
        var d=(typeof a==='number'&&typeof c==='number')?a-c:String(a).localeCompare(String(c));return asc?d:-d;});
      rows.forEach(function(r){b.appendChild(r)});}
    button.addEventListener('click',go);
  });
});
document.querySelectorAll('[data-stock-explorer]').forEach(function(section){
  var input=section.querySelector('input[type=search]'),buttons=section.querySelectorAll('[data-tier-filter]');
  var rows=section.querySelectorAll('tbody tr[data-tier]'),tier='all';
  function filter(){
    var query=input.value.trim().toLowerCase(),visible=0;
    rows.forEach(function(row){var match=(tier==='all'||row.dataset.tier===tier)&&row.dataset.search.includes(query);
      row.hidden=!match;if(match)visible++;});
    section.querySelector('[data-result-count]').textContent=visible+' of '+rows.length+' stocks shown';
    section.querySelector('[data-no-results]').hidden=visible!==0;
  }
  input.addEventListener('input',filter);
  buttons.forEach(function(button){button.addEventListener('click',function(){
    tier=button.dataset.tierFilter;
    buttons.forEach(function(b){b.setAttribute('aria-pressed',String(b===button));});filter();
  });});
  filter();section.querySelector('.table-controls').hidden=false;
});
document.querySelectorAll('[data-stock-finder]').forEach(function(section){
  var input=section.querySelector('input'),panel=section.querySelector('.stock-matches');
  var rows=section.querySelectorAll('[data-find-stock]'),status=section.querySelector('[data-find-status]');
  function filter(){
    var query=input.value.trim().toLowerCase(),count=0;
    rows.forEach(function(row){row.hidden=!row.dataset.findStock.includes(query);if(!row.hidden)count++;});
    panel.hidden=!query;input.setAttribute('aria-expanded',String(!!query));
    status.textContent=count?count+' matching stocks. Select a stock to read its verdict.':'No matching stocks.';
  }
  input.addEventListener('input',filter);
  input.addEventListener('keydown',function(e){
    if(e.key==='Escape'){input.value='';filter();}
    if(e.key==='ArrowDown'&&!panel.hidden){
      var first=section.querySelector('[data-find-stock]:not([hidden]) a');
      if(first){e.preventDefault();first.focus();}
    }
    if(e.key==='Enter'&&!panel.hidden){
      var matches=section.querySelectorAll('[data-find-stock]:not([hidden]) a');
      if(matches.length===1){e.preventDefault();matches[0].click();}
    }
  });
  section.addEventListener('keydown',function(e){
    if(e.key==='Escape'){input.value='';filter();input.focus();}
  });
});
document.querySelectorAll('.mobile-nav a').forEach(function(a){a.addEventListener('click',function(){
  a.closest('details').open=false;
});});
document.addEventListener('keydown',function(e){
  if(e.key!=='Escape')return;
  document.querySelectorAll('header details[open]').forEach(function(d){
    if(d.contains(document.activeElement)){d.open=false;d.querySelector('summary').focus();}
  });
});
"""

E = html.escape
LEVEL = re.compile(r"(High|Moderate|Medium|Low)\b")
SIGNED = re.compile(r"(?<![\w.])([+-])(\d[\d,.]*%?)")

ICON_PATHS = {
    "check": '<path d="m6 12 4 4 8-8"/><circle cx="12" cy="12" r="9"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
    "arrow": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    "book": '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "stop": '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
}


def _icon(name: str) -> str:
    return ('<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{ICON_PATHS[name]}</svg>')


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
    return out + (' <span class="badge b-flag" title="Additional checks beyond the Buy rules">Strict checks passed</span>'
                  if flagged else "")


def risk_badge(level: str | None, label: str = " risk") -> str:
    if not level:
        return '<span class="badge b-muted">Risk n/a</span>'
    base = level.split(" ", 1)[0].lower()
    cls = f"r-{base}" if base in ("high", "moderate", "low") else "b-muted"
    text = (f"{level.split(' ', 1)[0]}{label}; assessment incomplete" if "(incomplete)" in level else
            "Risk not fully assessed" if level == "Insufficient data" else level + label)
    return f'<span class="badge {cls} risk-badge">{E(text)}</span>'


def _cell(header: str, content: str) -> str:
    h, t = header.lower(), _text(content)
    if h.startswith(("tier", "status", "verdict")) and t:
        return tier_badge(t) if not any(k in t.lower() for k in ("high confidence", "strict checks passed")) else tier_badge(
            t.split("(")[0].strip(), True)
    m = LEVEL.match(t)
    if m and (h.startswith("risk") or header in FACTORS):
        return risk_badge(t, "")
    if m and "confidence" in h:
        return f'<span class="badge c-{m.group(1).lower()}">{content}</span>'
    return _signed(content)


def _table(m: re.Match) -> str:
    inner = m.group(1)
    if "</thead>" not in inner:
        return (f'<div class="table-wrap" tabindex="0" role="region" aria-label="Report table">'
                f'<table class="data">{inner}</table></div>')
    head, _, body = inner.partition("</thead>")
    heads = [_text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)]

    def row(rm: re.Match) -> str:
        idx = iter(range(len(heads) + 50))

        def cell(cm: re.Match) -> str:
            k = next(idx)
            return f"<td{cm.group(1)}>{_cell(heads[k] if k < len(heads) else '', cm.group(2))}</td>"
        return "<tr>" + re.sub(r"<td([^>]*)>(.*?)</td>", cell, rm.group(1), flags=re.S) + "</tr>"

    body = re.sub(r"<tr>(.*?)</tr>", row, body, flags=re.S)
    head = head.replace("<th>", '<th scope="col">')
    return (f'<div class="table-wrap" tabindex="0" role="region" aria-label="Report table">'
            f'<table class="data sortable">{head}</thead>{body}</table></div>')


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

    hurdle_mark = (f'<line x1="{x(hurdle):.1f}" x2="{x(hurdle):.1f}" y1="4" y2="34" stroke="var(--cp-warning)" '
                   f'stroke-width="2"><title>Hurdle {pct(hurdle, 2)}</title></line>') if hurdle is not None else ""
    svg = (f'<svg viewBox="0 0 300 38" preserveAspectRatio="none" role="img" aria-label="Projected annual return '
           f'bear {pct(bear)}, base {pct(base)}, bull {pct(bull)}">'
           f'<rect x="4" y="16" width="292" height="6" rx="3" fill="var(--cp-surface-soft)"/>'
           f'<rect x="{x(bear):.1f}" y="12" width="{max(x(bull) - x(bear), 2):.1f}" height="14" rx="7" '
           f'fill="color-mix(in srgb,var(--cp-text) 18%,transparent)"/>'
           f'<line x1="{x(0):.1f}" x2="{x(0):.1f}" y1="6" y2="32" stroke="var(--cp-text-muted)" stroke-dasharray="3 3"/>'
           f'{hurdle_mark}<circle cx="{x(base):.1f}" cy="19" r="6" fill="var(--cp-text)" stroke="var(--cp-surface)" '
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
    "Dividend yield": "Regular dividends from the trailing window, or annual DPS if the window is unsourced, before tax.",
    "Top signal": "The input that added most to this stock's score.",
    "Composite": "The overall score used to rank stocks. Higher ranks first.",
}
TIPS.update({"Modelled return / year": TIPS["Base return"], "Estimated value": TIPS["Fair value"],
             "Value gap": TIPS["Upside"]})

PLAIN = [
    (re.compile(r"only (\d+) of (\d+) valuation models show (\S+) or more upside, needs (\d+)"),
     r"only \1 of \2 valuation methods shows the required \3 cushion (needs \4)"),
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
    return (f"In historical one-year checks, {1 - cal:.0%} of stock outcomes fell outside these ranges. "
            "That test is shorter than the projection horizon; these are scenarios, not probability or loss limits.")


def _scenario(it: dict, tbill: float | None, cal: float | None) -> str:
    bear, base, bull = it.get("bear"), it.get("base"), it.get("bull")
    if None in (bear, base, bull) or not estimate_reliable(it):
        return ""
    n = (it.get("projection") or {}).get("years") or config.settings().get("valuation", {}).get("horizon_years", 3)

    def grow(r: float) -> str:
        return _money(10000 * max(1 + r, 0.0) ** n)

    comparison = (f" Rolling over a T-bill would give about {grow(tbill)} if today's net rate stays unchanged."
                  if tbill is not None else "")
    return (f'<p class="small"><b>Illustrative KES 10,000 scenario:</b> {grow(bear)} in a lower case, '
            f'{grow(base)} in a middle case and {grow(bull)} in an upper case after {n} years.{comparison} '
            f'These are not limits on potential loss or gain. {_cal_text(cal)}</p>')


def _plain(it: dict, tbill: float | None, cal: float | None = None, include_scenario: bool = True) -> str:
    lines = []
    price, fair, mos = it.get("price"), it.get("fair_base"), it.get("mos")
    dispersed = not estimate_reliable(it)
    if dispersed:
        lo, hi, spread = it.get("fair_low"), it.get("fair_high"), it.get("model_spread")
        rng = f" (estimates run from {kes(lo)} to {kes(hi)}, {spread:.1f}x apart)" if None not in (lo, hi, spread) else ""
        votes = (f" {it['agree']} of {it['models']} methods say it is at least "
                 f"{pct(config.settings().get('valuation', {}).get('mos_threshold', 0.15), 0)} cheap."
                 if None not in (it.get("agree"), it.get("models")) else "")
        reason = "the valuation methods disagree too much" if it.get("dispersed") else "valuation evidence is insufficient"
        lines.append(f"<b>Fair value unclear:</b> {reason}{rng}, so no single fair "
                     f"value or return is shown.{votes}")
    elif None not in (price, fair, mos):
        gap = f" ({abs(mos):.0%} {'upside' if mos > 0 else 'downside'})" if f"{abs(mos):.0%}" != "0%" else ""
        lines.append(f"<b>Price vs middle estimate:</b> {kes(price)} vs {kes(fair)}{gap}.")
    if it.get("tier") == "Buy":
        lines.append("<b>Entry rules pass; live evidence needs verification.</b>"
                     if (it.get("conviction") or {}).get("held_back") else "<b>Meets the Buy rules.</b>")
    elif reason := _plain_reason(consumer_binding(it)):
        lines.append(f"<b>Why it is not a Buy:</b> {E(reason)}.")
    text = f'<div class="plain">{"".join(f"<p>{x}</p>" for x in lines)}</div>' if lines else ""
    return text + (_scenario(it, tbill, cal) if include_scenario else "")


def _decision_why(it: dict) -> str:
    d = it.get("decision")
    if not d:
        return f'<p class="stock-reason"><b>Why {E(it["tier"])}?</b>{E(_plain_reason(consumer_binding(it)))}</p>'
    return ('<div class="decision-explanation"><h3>Why this verdict?</h3>'
            f'<p><b>{E(d["reason"])}.</b></p>' + "".join(f'<p>{E(text)}</p>' for text in d["why"]) + "</div>")


def _decision_next(it: dict) -> str:
    d = it.get("decision")
    if not d:
        return ""
    filing = "".join(f'<li><a href="{E(p["url"])}">{E(p["period"])} filing</a> '
                     f'(recorded publication {E(p["published"])}).</li>' for p in it.get("filings", []))
    notices = "".join(f'<li><a href="{E(p["url"])}">{E(p["title"])}</a> '
                      f'(first seen {E(p["first_seen"])}; verify the publication date and current terms).</li>'
                      for p in it.get("notices", []))
    notes = it.get("company_notes") or []
    material = [n for n in notes if re.search(r"\btender|rights issue|proposed|takeover|delist|suspension\b", n, re.I)]
    return ('<div class="decision-explanation"><h3>What would change it?</h3>'
            + "".join(f'<p>{E(text)}</p>' for text in d["changes"])
            + '<h3>What to verify next</h3><ul>' + "".join(f'<li>{E(text)}</li>' for text in d["verify"])
            + filing + "</ul>"
            + ('<p><b>Recorded company caveats:</b> verify these before relying on the model.</p><ul>'
               + "".join(f"<li>{E(n)}</li>" for n in material[:2]) + "</ul>" if material else "")
            + ('<details class="more"><summary>Company notices and filing caveats</summary><ul>'
               + notices + "".join(f"<li>{E(n)}</li>" for n in notes)
               + '</ul><p class="small muted">These notes are context, not a complete corporate-event feed.</p></details>'
               if notes or notices else "")
            + f'<p class="small muted"><b>Already own it?</b> {E(d["holder_note"])}</p></div>')


def _return_explanation(it: dict) -> str:
    projection = it.get("projection") or {}
    drivers = projection.get("drivers")
    if not drivers or not estimate_reliable(it):
        return ""
    labels = {"dividends": "Regular dividends after tax", "growth": "Assumed business growth",
              "repricing": "Closing the valuation gap (including growth interaction)", "costs": "Trading costs"}
    return (f'<h3>What makes up the {pct(projection["base"])} middle case?</h3>'
            '<p class="small muted">Annual percentage-point contributions. These assumptions are not guaranteed.</p>'
            '<dl class="return-drivers">' + "".join(
                f'<div><dt>{label}</dt><dd>{value * 100:+.2f} pp</dd></div>'
                for key, label in labels.items() for value in [drivers[key]])
            + '</dl><p class="small muted">Dividends use the latest annual regular DPS, after withholding tax. '
              'The separate dividend-yield figure may use a different trailing window and is before tax.</p>')


def _stock_card(it: dict, hurdle: float | None, gates: bool = False, why: bool = False,
                tbill: float | None = None, cal: float | None = None, detail: bool = False) -> str:
    conv, rk = it.get("conviction") or {}, it.get("risk") or {}
    flagged = bool(conv.get("flag"))
    dispersed = not estimate_reliable(it)
    lo, hi = it.get("fair_low"), it.get("fair_high")
    span = f'<span class="muted small"> ({lo:,.0f} to {hi:,.0f})</span>' if None not in (lo, hi) else ""
    if dispersed and None not in (lo, hi):
        fair = f'{kes(lo)} to {kes(hi)}<span class="muted small"> (methods disagree)</span>'
    else:
        fair = f'{kes(it.get("fair_base"))}{span}' if it.get("fair_base") is not None else "n/a"
    projection = it.get("projection") or {}
    years = projection.get("years", config.settings()["valuation"]["horizon_years"])
    unclear = '<span class="muted">unclear</span>'
    scenarios = (f'{pct(it["bear"], 1)} to {pct(it["bull"], 1)}'
                 if it.get("bear") is not None and it.get("bull") is not None else "n/a")
    div_context = it.get("dividend_context") or {}
    facts = [(f"Scenarios / year over {years} years", unclear if dispersed else scenarios),
             ("Middle case / year", unclear if dispersed else pct(it.get("base"), 0)),
             ("Middle valuation estimate", fair),
             ("Value gap", unclear if dispersed else _sp(it.get("mos")))]

    def dl(rows: list[tuple[str, str]]) -> str:
        return ('<dl class="facts">' + "".join(f'<div><dt title="{E(TIPS.get(k, ""))}">{k}</dt><dd>{v}</dd></div>'
                                               for k, v in rows) + "</dl>")

    gate_html = ""
    if gates and conv.get("gates"):
        passed = sum(1 for g in conv["gates"] if g["passed"])
        gate_html = (f'<h3>Strict checks (separate from Buy)</h3><p class="small muted">'
                     f'{passed} of {len(conv["gates"])} additional checks pass. These are stricter than the entry rules '
                     'and are not a probability of profit.</p><ul class="gates">'
                     + "".join(f'<li><span class="{"ok" if g["passed"] else "no"}" aria-hidden="true">'
                               f'{"&#10003;" if g["passed"] else "&#10007;"}</span><span><b>{E(g["name"])}</b>'
                               f'<span class="sr">{" passes" if g["passed"] else " fails"}</span>: {E(g["detail"])}'
                               f'</span></li>' for g in conv["gates"]) + "</ul>")
    factors = "".join(
        f'<li><div><b>{E(f["name"])}</b><span class="risk-explanation">'
        f'{E("Unclear while valuation methods disagree" if dispersed and f["name"] == "Downside" else f["detail"])}'
        f'</span></div>{risk_badge(None if dispersed and f["name"] == "Downside" else f.get("level"), "")}</li>'
        for f in rk.get("factors", []))
    held = conv.get("held_back") or []
    evidence = (f'<p class="small"><b>Evidence needs verification:</b> {E("; ".join(held))}.</p>' if held else "")
    ticker = E(it["ticker"]) if detail else f'<a href="stocks/{E(it["ticker"])}.html">{E(it["ticker"])}</a>'
    explanation = _decision_why(it) if it.get("decision") else (
        _plain(it, tbill, cal, include_scenario=False) if detail else
        f'<p class="stock-reason"><b>Why {E(it["tier"])}?</b>'
        f'{E(_plain_reason(consumer_binding(it)) or "Meets the Buy rules.")}</p>')
    checks = (it.get("decision") or {}).get("checks") or []
    entry_html = ('<h3>Entry checks</h3><ul class="gates">' + "".join(
        f'<li><b>{E(c["name"])}: {"passes" if c["passed"] else "not assessed" if c["passed"] is None else "fails"}.</b> '
        f'{E(c["detail"])}</li>' for c in checks) + "</ul>") if checks else ""
    model_rows = (it.get("decision") or {}).get("models") or []
    models_html = ('<h3>Valuation methods at this price</h3><div class="table-wrap"><table class="data">'
                   '<thead><tr><th>Method</th><th>Estimate</th><th>Required cushion</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{E(m["name"])}</td><td>{kes(m["value"])}</td>'
                             f'<td>{"Passes" if m["passes"] else "Falls short"}</td></tr>' for m in model_rows)
                   + "</tbody></table></div>") if model_rows else ""
    footer = (f'<footer class="stock-footer"><span>Estimates, not guaranteed returns</span>'
              f'<a href="stocks/{E(it["ticker"])}.html">Full stock review {_icon("arrow")}</a></footer>'
              if not detail else "")
    return (f'<article class="stock{" flagged" if flagged else ""}"><header><div class="stock-identity">'
            f'<span class="company-mark" aria-hidden="true">{E(it["ticker"][:2])}</span>'
            f'<div><span class="tk">{ticker}</span>'
            f'<span class="nm">{E(it["name"])} &middot; {E(it["sector"])}'
            f'</span></div></div><div class="badges">{tier_badge(it["tier"], flagged)}'
            f'{risk_badge(rk.get("label") or rk.get("level"))}</div>'
            f'</header><div class="pricebox"><div><div class="price">{kes(it.get("price"))}</div>'
            f'<div class="small muted">close {E(str(it.get("price_date") or ""))}</div></div>{_spark(it["ticker"])}'
            f'</div>{explanation}{evidence}{dl(facts)}'
            + (f'<p class="small muted">{E(_cal_text(cal))}</p>' if not dispersed else "")
            + (_decision_next(it) if detail else "")
            + '<details class="more"><summary>Checks, assumptions and sources</summary>'
            + ("" if detail else _decision_next(it))
            + _return_explanation(it) + entry_html + models_html
            + f'<p class="small"><b>Dividend yield:</b> {pct(it.get("dividend_yield"))}. '
              f'{E(div_context.get("basis", "Historical dividends or annual DPS fallback, before tax"))}. '
              f'{E(div_context.get("note", ""))}</p>'
            + ("" if dispersed else _range_bar(it.get("bear"), it.get("base"), it.get("bull"), hurdle))
            + (f'<ul class="risk-list">{factors}</ul>' if factors else "")
            + gate_html
            + _scenario(it, tbill, cal)
            + (f'<p class="small muted">{E(rk["summary"])}</p>' if rk.get("summary") else "")
            + f"</details>{footer}</article>")


def _hero(s: dict) -> str:
    pd = s.get("price_date")
    when = f"Closing prices from {E(str(pd))}." if pd else ""
    current_session = (((s.get("health") or {}).get("prices") or {}).get("status") == "Current")
    stale = (f'<div class="callout warn small"><p><b>Prices not refreshed.</b> The latest closing prices are from '
             f'{E(str(pd))}, before this brief\'s date of {E(s["as_of"])}. The market may have been closed or the '
             f'price source failed.</p></div>') if pd and str(pd) < str(s["as_of"]) and not current_session else ""
    day = datetime.fromisoformat(s["as_of"]).strftime("%A, %d %B %Y")
    updated = (datetime.fromisoformat(s["generated"]).astimezone(EAT).strftime("%H:%M EAT")
               if s.get("generated") else None)
    return (f'<section class="brief-heading"><div><p class="eyebrow">Nairobi Securities Exchange</p>'
            f'<h1>Your daily NSE brief</h1><p class="lead">Value, risk and what deserves your attention.</p></div>'
            f'<div class="edition"><time datetime="{E(s["as_of"])}">{E(day)}</time>'
            + (f'Updated {E(updated)}' if updated else "Daily closing assessment") + '</div></section>'
            + f'<p class="small muted">{s.get("valued", 0)} stocks checked. {when}</p>{stale}')


def _economic_context(s: dict) -> str:
    if not s.get("macro"):
        return ""
    from . import official
    m = s["macro"]
    bill, inflation = m["risk_free"]["tbill_364d"], m["policy"]["inflation"]
    metrics = [(pct(s["tbill_net"], 2), "T-bill per year, after tax"),
               (pct(s.get("hurdle"), 2), "Minimum projected return for a Buy"),
               (pct(inflation["value"]), "Observed inflation, year-on-year")]
    return ('<section class="card prose" id="economic-context"><h2>Rates and inflation</h2>'
            f'<p class="small muted">CBK results: {E(str(bill.get("as_of") or "date unknown"))}. '
            f'KNBS CPI period: {E(str(inflation.get("period") or "unknown"))}.</p>'
            '<div class="kpis">' + "".join(f'<div class="kpi"><b>{value}</b><span>{E(label)}</span></div>'
                                         for value, label in metrics) + '</div>'
            '<p class="small">The hurdle uses CBK rates; other Buy checks still apply. '
            'Inflation describes the past year, not a forecast.</p>'
            '<details class="more"><summary>Sources, assumptions and purchasing power</summary>'
            + _md("\n".join(official.markdown(m, s["tbill_net"])[2:])) + "</details></section>")


def _health_panel(s: dict) -> str:
    h = s.get("health")
    if not h:
        return ('<section class="health-panel" id="data-health"><b>Data health: unknown.</b> '
                'This older report has no live evidence assessment.</section>')
    p, a, m = h["prices"], h["announcements"], h["macro"]
    rows = "".join(f'<tr><td>{E(t)}</td><td>{E(str(r.get("price_date") or "unknown"))}</td>'
                   f'<td>{E(r["status"])}</td><td>{E(str(r.get("period") or "unknown"))}</td>'
                   f'<td>{E(r["fundamentals_status"])}'
                   f'{"; results review pending" if r.get("pending_results") else ""}</td></tr>'
                   for t, r in h["tickers"].items())
    ledger = s.get("ledger") or {}
    revised = ledger.get("differences") or []
    provenance = (f'Revision {E(s["revision"])}. ' if s.get("revision") else "")
    provenance += (f'Official ledger: {ledger["rows"]} stocks, first verified snapshot of {E(ledger["date"])}.'
                   if ledger.get("rows") else "No official prediction logged for this report date.")
    if revised:
        provenance += " Revised since the official snapshot: " + ", ".join(E(r["ticker"]) for r in revised) + "."
    fetch = p.get("fetch") or {}
    attempts = ""
    if fetch.get("last_attempt"):
        attempts = (f'<p>Latest price collection: {E(fetch["last_attempt"])} '
                    f'({"succeeded" if fetch.get("successful") else "failed; retained stored closes"}). '
                    f'Last success: {E(str(fetch.get("last_success") or "unknown"))}.</p>')
        if fetch.get("errors"):
            attempts += "<ul>" + "".join(f"<li>{E(error)}</li>" for error in fetch["errors"]) + "</ul>"
    return (f'<section class="health-panel" id="data-health" '
            f'data-health-state="{"current" if h["critical_ok"] else "attention"}"><div class="health-line">'
            f'<b>{_icon("check" if h["critical_ok"] else "clock")}Evidence freshness: {E(h["status"])}</b>'
            f'<span>Current closing prices {p["current"]}/{p["total"]}</span>'
            f'<span>Source: {E(str(p.get("source") or "unknown"))}</span>'
            f'<span>Expected session: {E(h["expected_session"])}</span></div>'
            f'<p hidden data-update-due="{E(h["next_update_due"])}" role="status"><b>Update overdue.</b> '
            f'This report has passed its next expected update time. Recheck freshness before acting.</p>'
            f'<details class="more"><summary>Check sources and freshness</summary>'
            '<p>Freshness checks confirm timing and coverage, not the accuracy of the figures or valuation.</p>'
            f'<p>Announcements: {E(a["status"])}. Last successful check: {E(str(a["last_success"] or "unknown"))}. '
            f'Macro rates: {E(m["status"])}. Curated assumptions: {E(str(m["as_of"] or "unknown"))}; '
            f'T-bill results: {E(str(m.get("tbill_as_of") or "unknown"))}.</p>'
            f'<p>{E(h["session_note"])} Next update due: {E(h["next_update_due"])} (EAT).</p>'
            f'{attempts}<div class="table-wrap" tabindex="0" role="region" aria-label="Source freshness by stock">'
            f'<table class="data"><thead><tr><th scope="col">Stock</th><th scope="col">Price date</th>'
            f'<th scope="col">Price health</th><th scope="col">Annual results</th>'
            f'<th scope="col">Results health</th></tr></thead><tbody>{rows}</tbody>'
            f'</table></div><p>{provenance}</p></details></section>')


def _verdict(s: dict) -> str:
    def dicts(key: str) -> list[dict]:
        v = s.get(key)
        return [i for i in v if isinstance(i, dict)] if isinstance(v, list) else []

    items = dicts("top") + dicts("high_confidence")
    buys = list(dict.fromkeys(i.get("ticker") for i in items if i.get("tier") == "Buy" and i.get("ticker")))
    if buys:
        head = f'Meets the Buy rules: {E(", ".join(buys))}.'
        sub = "The entry checks pass. Risk and evidence limitations still need review."
        if s.get("health") and not s["health"]["critical_ok"]:
            head = f'Buy rules pass for {E(", ".join(buys))}, but data needs verification.'
            sub = "Critical evidence is incomplete. Strict-rule flags are held back."
    else:
        n = (s.get("counts") or {}).get("Buy", 0)
        head = "No stock meets the Buy rules today." if not n else f"{n} stock{'s' if n > 1 else ''} meets the Buy rules."
        near = next((i for i in dicts("top") if i.get("tier") == "Watch"), None)
        sub = ""
        if near and near.get("ticker"):
            reason = (near.get("decision") or {}).get("reason") or _plain_reason(near.get("binding"))
            sub = (f'Watch only: <b>{E(near["ticker"])}</b>'
                   + (f": {E(reason)}." if reason else "."))
    has_buys = bool(buys or (s.get("counts") or {}).get("Buy", 0))
    buy_items = [i for i in items if i.get("tier") == "Buy"]
    if not s.get("health") or not s["health"]["critical_ok"]:
        state, status, icon = "unverified", "Data unverified", "clock"
    elif has_buys and (not buy_items or any((i.get("conviction") or {}).get("held_back") for i in buy_items)):
        state, status, icon = "verify", "Verify first", "clock"
        head = "Buy rules pass, but the assessment needs verification."
        sub = "Read the missing-evidence notes in each stock review before relying on the result."
    elif has_buys:
        state, status, icon = "buy", "Buy rules passed", "check"
    else:
        state, status, icon = "no-buy", "No qualifying Buy", "stop"
    tb, hurdle = s.get("tbill_net"), s.get("hurdle")
    candidates = {i.get("ticker") for i in items if i.get("tier") in ("Buy", "Watch") and i.get("ticker")}
    action = ('<a class="button primary" href="#candidates">Review candidates ' + _icon("arrow") + '</a>'
              if candidates else '<a class="button primary" href="#all-stocks">Explore covered stocks '
              + _icon("arrow") + '</a>')
    money = ('<aside class="card benchmark" aria-label="Return comparison"><h2>The benchmark to beat</h2><dl>'
             f'<div><dt>364-day T-bill, net</dt><dd>{pct(tb)}</dd></div>'
             f'<div><dt>Buy hurdle, per year</dt><dd>{pct(hurdle, 2)}</dd></div></dl>'
             '<p>The middle-case stock return must exceed the T-bill rate plus a premium for stock market risk. '
             'Rates and scenarios can change.</p></aside>') if None not in (tb, hurdle) else (
                 '<aside class="card benchmark"><h2>Return comparison unavailable</h2>'
                 '<p>Check source data before relying on a projected return.</p></aside>')
    return (f'<div class="decision-layout"><section class="card" id="verdict" data-verdict="{state}">'
            f'<div class="verdict-header"><h2 class="section-label">{_icon(icon)}Today in one sentence</h2>'
            f'<span class="decision-status">{status}</span></div><p class="big">{head}</p>'
            + (f'<p class="decision-copy">{sub}</p>' if sub else
               '<p class="decision-copy">The screen is selective. Review the evidence before making an investment decision.</p>')
            + f'<div class="actions">{action}<a class="button" href="#glossary">Understand the ratings</a></div>'
            + '</section>' + money + '</div><p class="page-note"><b>Not financial advice.</b> '
              'Fixed rules and public data. Verify filings before investing.</p>')


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
        ("Buy, Watch, Avoid", "Buy passes the entry checks. Watch passes the business health check but misses one other "
                              "check. Avoid misses more, fails the health check or its valuation methods disagree too "
                              "much. These are entry rules, not instructions to sell existing holdings."),
        ("Strict checks passed", f"A stricter Buy: {hc.get('min_agreeing_models', 3)} or more valuation methods agree and "
                            "the business scores well on health checks, with current critical evidence. This is "
                            "agreement of rules, not a measured probability of profit."),
        ("Risk level", "Low, Moderate or High, from price swings, how easily it trades, debt or bad loans and "
                       "company warnings. It never changes the tier; it tells you how bumpy the ride could be."),
        ("Research score (composite)", f"An independent ranking of all stocks, regardless of entry verdict. "
         f"It does not set Buy, Watch or Avoid. Today's mix: {_weights_plain(s)}."),
        ("Entry and strict checks", "Entry checks set Buy, Watch or Avoid. The separate strict checks require "
         "stronger model agreement, a higher health score and current evidence."),
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
    out = [f'<details class="fold confidence-panel" id="high-confidence"><summary><h2>'
           f'Strict checks: {len(flagged)} stocks pass</h2></summary>'
           '<p class="small">These checks are separate from the entry rules. Passing is not a probability of profit.</p>'
           f'<p class="small muted">{_inline(s.get("rule", ""))}</p>']
    if flagged:
        out.append('<div class="grid">' + "".join(_stock_card(i, hurdle, gates=True, tbill=tb, cal=cal)
                                                  for i in flagged) + "</div>")
    else:
        if near:
            out.append('<details class="more"><summary>Why the strict checks fail</summary><ul>'
                       + "".join(f'<li>{E(i["ticker"])} ({E(i["tier"])}): '
                                 f'{E("; ".join([g["name"] + ": " + g["detail"] for g in (i.get("conviction") or {}).get("gates", []) if not g["passed"]] + (i.get("conviction") or {}).get("held_back", [])))}</li>'
                                 for i in near) + "</ul></details>")
    return "".join(out) + "</details>"


def _alerts_changes(s: dict) -> str:
    ch, alerts = s.get("changes") or {}, s.get("alerts") or []
    since = f'since {E(ch["prev_date"])}' if ch.get("prev_date") else "(first brief, nothing to compare yet)"
    changes = [("New candidates", ", ".join(ch.get("top_in") or [])),
               ("Left candidates", ", ".join(ch.get("top_out") or [])), ("Tier changes", ch.get("tiers", 0)),
               ("Threshold crossings", ch.get("crossings", 0)), ("New announcements", ch.get("announcements", 0)),
               ("Unusual price moves", ch.get("moves", 0))]
    changed = [(label, value) for label, value in changes if value]
    al = ('<ul class="small">' + "".join(f"<li>{_inline(a)}</li>" for a in alerts) + "</ul>") if alerts else (
        f'<div class="quiet-state">{_icon("bell")}<p>No Buy alerts or profit warnings in this brief.</p></div>')
    more = ('<p class="small"><a href="daily.html#what-changed">Details in the daily brief</a></p>'
            if (config.REPORTS / "daily" / "latest.md").exists() else "")
    change_list = ('<dl class="change-list">' + "".join(
        f'<div><dt>{E(label)}</dt><dd>{E(str(value))}</dd></div>' for label, value in changed) + '</dl>'
        if changed else '<p class="small muted">No material changes since the previous brief.</p>')
    change_list += ('<ul class="small">' + "".join(
        f'<li><b>{E(c["ticker"])}:</b> {E(c["before"])} to {E(c["after"])}. '
        f'Current reason: {E(c["reason"])}.</li>' for c in ch.get("verdict_details", [])) + "</ul>"
        if ch.get("verdict_details") else "")
    return (f'<section class="card"><h2>What changed</h2><p class="small muted">Changes {since}.</p>'
            f'{change_list}{more}</section><section class="card"><h2>Alerts</h2>{al}</section>')


def _reading_guide() -> str:
    return ('<details class="fold"><summary><h2>A one-minute reading guide</h2></summary><ol class="guide-steps">'
            '<li><b>Check the evidence.</b> Confirm prices and sources are current.</li>'
            '<li><b>Read the conclusion.</b> Buy passes the entry rules. Watch still misses a check.</li>'
            '<li><b>Open a stock review.</b> Understand its risks and verify the source filing.</li></ol>'
            '<p class="small muted">Verdict color key:</p><div class="verdict-legend">'
            '<span class="badge b-buy">Green: Buy rules pass</span>'
            '<span class="badge b-watch">Amber: Watch / verify</span>'
            '<span class="badge" style="color:var(--cp-danger)">Red: No qualifying Buy</span>'
            '<span class="badge b-muted">Gray: Unverified data</span></div>'
            '<p class="small muted">Green is not a guarantee of profit. Red and Avoid are not automatic '
            'instructions to sell existing holdings.</p><a class="back-link" href="#glossary">Jargon buster '
            + _icon("arrow") + '</a></details>')


def _top(s: dict, cal: float | None = None) -> str:
    top = [i for i in (s.get("top") or []) if i.get("tier") in ("Buy", "Watch")]
    if not top:
        return (f'<section class="card"><div class="quiet-state">{_icon("book")}<div>'
                '<h2>No entry candidates today</h2><p>No Buy or Watch cards are available in this brief. '
                'Explore the full ranking for the recorded assessments.</p></div></div></section>')
    return (f'<section id="candidates"><div class="section-heading"><div><h2>Candidates for review</h2>'
            f'<p>{len(top)} to review. Buy candidates first, then Watch.</p></div>'
            f'<a class="button" href="#all-stocks">All stocks {_icon("arrow")}</a></div><div class="candidate-stack">'
            + "".join(_stock_card(i, s.get("hurdle"), why=True, tbill=s.get("tbill_net"), cal=cal) for i in top)
            + "</div></section>")


def _ranking(s: dict) -> str:
    from .decision import display_order
    rows = s.get("ranking") or []
    if not rows:
        return ""
    lvl = {"High": 3, "Moderate": 2, "Low": 1}

    def num(r: dict, k: str, f) -> str:
        return '<span class="muted" title="valuation evidence is unreliable">unclear</span>' if not estimate_reliable(r) else f(r.get(k))

    research_rows = rows
    rows = sorted(rows, key=display_order)
    body = "".join(
        f'<tr data-tier="{E(r["tier"])}" data-search="{E(" ".join(str(r.get(k, "")) for k in ("ticker", "name", "sector")).lower())}">'
        f'<td><a href="stocks/{E(r["ticker"])}.html"><b>{E(r["ticker"])}</b></a></td>'
        f'<td>{E(r["name"])}</td><td>{E(r["sector"])}</td>'
        f'<td data-v="{E(r["tier"])}">{tier_badge(r["tier"], (r.get("conviction") or {}).get("flag", False))}</td>'
        f'<td>{E((r.get("decision") or {}).get("reason") or _plain_reason(consumer_binding(r)))}</td>'
        f'<td data-v="{lvl.get((r.get("risk") or {}).get("level"), 0)}">'
        f'{risk_badge((r.get("risk") or {}).get("label") or (r.get("risk") or {}).get("level"), "")}'
        f'</td><td>{kes(r.get("price"))}</td><td>{num(r, "mos", _sp)}</td><td>{num(r, "bear", pct)}</td>'
        f'<td>{num(r, "base", pct)}</td><td>{num(r, "bull", pct)}</td><td>{pct(r.get("dividend_yield"))}</td>'
        f'</tr>' for r in rows)
    heads = ["Ticker", "Name", "Sector", "Verdict", "Reason", "Risk", "Price", "Value gap", "Lower / yr",
             "Middle / yr", "Upper / yr", "Dividend before tax"]
    filters = "".join(
        f'<button type="button" data-tier-filter="{tier}" aria-pressed="{"true" if tier == "all" else "false"}" '
        f'aria-controls="stock-table">{label}</button>' for tier, label in
        (("all", "All"), ("Buy", "Buy"), ("Watch", "Watch"), ("Avoid", "Avoid")))
    research = ('<details class="more"><summary>Independent research-score order</summary>'
                '<p class="small muted">This score ranks every stock, including Avoids. It does not set the verdict. '
                f'The mix is {E(_weights_plain(s))}.</p><div class="table-wrap"><table class="data sortable">'
                '<thead><tr><th>Research rank</th><th>Ticker</th><th>Score</th></tr></thead><tbody>'
                + "".join(f'<tr><td>{r["rank"]}</td><td>{E(r["ticker"])}</td><td>{r["composite"]:.2f}</td></tr>'
                          for r in research_rows if r.get("composite") is not None)
                + "</tbody></table></div></details>")
    return ('<section class="card" id="ranking" data-stock-explorer><h2>All stocks by entry verdict</h2>'
            '<p class="small muted">Buy, then Watch, then Avoid; research score orders stocks within each group. '
            'Return scenarios are annualised over the stated model horizon, net of costs and dividend tax. '
            'Dividend yields use trailing regular dividends or an annual-DPS fallback, before tax. '
            'Select a column heading to sort.</p><div class="table-controls" hidden>'
            '<div class="stock-search"><label for="stock-search">Find a stock</label>'
            '<input id="stock-search" type="search" placeholder="Ticker, company or sector" '
            'aria-controls="stock-table" autocomplete="off"></div>'
            f'<div class="table-filters" role="group" aria-label="Filter by entry tier">{filters}</div></div>'
            f'<p class="result-count" data-result-count role="status" aria-live="polite">{len(rows)} stocks shown</p>'
            '<p class="small muted" data-no-results hidden>No stocks match. Try another company, sector or tier.</p>'
            '<div class="table-wrap" tabindex="0" role="region" aria-label="Stock research table">'
            '<table class="data sortable" id="stock-table"><caption class="sr">All covered stocks, '
            'their entry tier, risk and valuation scenarios.</caption><thead><tr>'
            + "".join(f'<th scope="col">{h}</th>' for h in heads) + f"</tr></thead><tbody>{body}"
            "</tbody></table></div>" + research + "</section>")


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
    series = [(1, "var(--cp-text)", "Top 5 each month"), (2, "var(--cp-link)", "Equal-weight universe"),
              (3, "var(--cp-text-muted)", "NASI")]
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
            f'Before trading costs. Dividends are included in each monthly return, and those returns are compounded '
            f'at monthly rebalancing. NASI excludes dividends.</p></div>')


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
            col = "var(--cp-success)" if val >= 0 else "var(--cp-danger)"
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
    top, basket = y12.get("top_return"), y12.get("universe")
    edge = y12.get("excess")
    if edge is None and top is not None and basket is not None:
        edge = top - basket
    conclusion = ("The rankings beat the stock basket on average in this simulation."
                  if edge is not None and edge > 0 else
                  "This simulation did not beat the simple stock basket." if edge is not None else
                  "There is not enough historical data to compare the rankings.")
    kpis = [
        (f"{edge * 100:+.1f} percentage points" if edge is not None else "Not available",
         "Average extra return over the comparison basket"),
        (pct(y12.get("hit_rate")), "Selected stocks that beat the basket, averaged across test windows"),
        (pct(y12.get("calibration"), 0), "Actual one-year returns inside the scenario range (all ranked stocks)"),
    ]
    cal = y12.get("calibration")
    note = (f'<div class="callout warn small"><p><b>The scenarios are poor guides to one-year risk.</b> '
            f'Only {pct(cal, 0)} of checked one-year stock outcomes stayed between the lower and upper scenarios. '
            f'These are valuation scenarios, not probability bands. A bear case is not a worst-case loss limit.'
            f'</p></div>') if cal is not None and cal < 0.6 else ""
    live_windows = ((r.get("live") or {}).get("12") or {}).get("windows", 0)
    if r.get("live_first"):
        days = r.get("live_dates", 0)
        live = (f'<p class="small"><b>Live record:</b> {days} trading {"day" if days == 1 else "days"} tracked since '
                f'{E(str(r["live_first"]))}. ' + (
                    f'Completed 12-month live holding periods: {live_windows}. See the full results.'
                    if live_windows else 'No completed 12-month live outcomes yet.') + '</p>')
    else:
        live = '<p class="small"><b>Live record:</b> no live predictions have been logged yet.</p>'
    comparison = (f'<p class="small"><b>Historical simulation:</b> the top-five basket returned an average '
                  f'{pct(top)} over 12 months, versus {pct(basket)} for the comparison basket, which splits money '
                  f'equally across the stocks we track. '
                  f'These are averages of '
                  f'{y12.get("windows", 0)} overlapping historical holding windows, before trading costs.</p>'
                  if top is not None and basket is not None else "")
    caveat = ('<p class="small muted">This tests the five highest-ranked research scores, including stocks that may fail '
              "the Buy rules. It is not a live record of Buy recommendations. Today's interest rates and the current "
              "covered-stock universe are reused throughout the history. Neighbouring 12-month tests share much of "
              "their history, so the windows are not independent. Fees could reduce or erase the edge.</p>")
    chart = _growth_chart((rec.get("1") or {}).get("detail") or [])
    if chart:
        chart = ('<h3>A separate test: monthly portfolio rotation</h3><p class="small">This chart holds each '
                 "month's top five for one month, then rebalances. It is a different experiment from the "
                 '12-month holding averages above.</p>' + chart)
    link = ('<a class="back-link" href="retrospective.html#forward-scorecard">Full methodology and results</a>'
            if (config.REPORTS / "retrospective.md").exists() else "")
    ic = f'{y12["ic"]:+.3f}' if y12.get("ic") is not None else "Not available"
    stamp = (f'<p class="small muted">Calculated {E(str(r["generated"]))}; outcomes evaluated through '
             f'{E(str(r["data_end"]))}.</p>') if r.get("generated") and r.get("data_end") else ""
    return ('<section class="card" id="track-record"><h2>Do the rankings add value?</h2>'
            f'<p><b>{conclusion}</b></p><p class="small">This measures the research score, not the Buy rules. '
            'It does not establish that the entry verdicts predict profitable investments.</p>'
            f'{stamp}{live}{comparison}'
            '<p class="small muted">The ranking method was chosen using this same history. This is not an '
            'independent test or a forecast.</p><div class="kpis">'
            + "".join(f'<div class="kpi"><b>{v}</b><span>{E(k)}</span></div>' for v, k in kpis) + "</div>"
            + '<p class="small muted">The selected-stock beat rate is not the probability of making a profit.</p>'
            + note + '<details class="more"><summary>How to interpret this evidence</summary>' + caveat
            + '<dl class="facts"><div><dt>NASI price return (excludes dividends)</dt>'
            f'<dd>{pct(y12.get("nasi"))}</dd></div><div><dt>Ranking association (IC)</dt>'
            f'<dd>{ic}</dd></div></dl><p class="small muted">A positive IC means higher ranks tended to '
            'outperform. It is not a return or a probability. NASI excludes dividends, so it is not directly '
            'comparable with the stock baskets, which include dividends.</p>'
            + chart + link + "</details></section>")


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
        panels = {}
        for name, fn in (("hero", _hero), ("health", _health_panel), ("verdict", _verdict),
                         ("context", _economic_context),
                         ("changes", _alerts_changes), ("candidates", partial(_top, cal=cal)),
                         ("confidence", partial(_high_conf, cal=cal)), ("glossary", partial(_glossary, retro=retro))):
            try:
                panels[name] = fn(snap)
            except Exception as exc:  # one broken panel must not take the site down
                panels[name] = f'<div class="empty small">Panel unavailable: {E(type(exc).__name__)}</div>'
        parts.extend(panels[name] for name in ("hero", "verdict", "health"))
        parts.append('<div class="brief-layout"><div class="brief-main">' + panels["candidates"]
                     + panels["confidence"] + '</div><aside class="brief-side" aria-label="Changes and reading guide">'
                     + panels["changes"] + _reading_guide() + '</aside></div>')
        parts.append(panels["context"])
        parts.append('<div class="research-heading"><p class="eyebrow">Go deeper</p>'
                     '<h2>Explore the evidence</h2><p class="small muted">'
                     'Search all stocks, check past performance or look up a term.</p></div>')
        try:
            parts.append('<details class="fold" id="all-stocks"><summary><h2>All stocks by verdict</h2>'
                         '</summary>' + _ranking(snap) + "</details>")
        except Exception as exc:
            parts.append(f'<div class="empty small">Ranking unavailable: {E(type(exc).__name__)}</div>')
        parts.append(panels["glossary"])
    else:
        parts.append('<section class="hero"><div><p class="eyebrow">NSE Value Agent</p><h1>Undervalued NSE stocks, '
                     'ranked by fixed rules</h1><p class="lead">No daily snapshot yet. Run the daily brief to fill this '
                     f'dashboard.</p></div></section><div class="callout warn small"><p><strong>Not financial advice.'
                     f'</strong> {E(DISCLAIMER)}</p></div>')
        parts.append(_health_panel({}))
    if retro:
        for fn in (_track_record, _evidence):
            try:
                parts.append('<details class="fold"><summary><h2>'
                             + ("Track record, explained" if fn == _track_record else "Research: ranking evidence")
                             + "</h2></summary>" + fn(retro) + "</details>")
            except Exception as exc:
                parts.append(f'<div class="empty small">Panel unavailable: {E(type(exc).__name__)}</div>')
    parts.append('<section class="card subscribe-panel" id="subscribe"><div><h2>Keep up with the market</h2><p>'
                 'Follow the daily brief in your feed reader, or subscribe to material-change alerts on GitHub. '
                 'No account or personal holdings are required for the site.</p></div><div class="actions">'
                 f'<a class="button primary" href="feed.xml">{_icon("bell")}Daily RSS/Atom feed</a>'
                 f'<a class="button" href="{REPO}/issues?q=is%3Aissue%20is%3Aopen%20label%3Adaily-alert">'
                 'GitHub alerts</a></div></section><p class="page-note">To receive GitHub alerts, open the active '
                 'daily-alert issue and choose Subscribe. If no alert issue exists yet, check back after the first '
                 'material change.</p>')
    parts.append('<details class="fold"><summary><h2>All reports</h2></summary>' + _report_links(present) + "</details>")
    return "".join(parts)


def _load_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _feed(site: Path) -> None:
    namespace = "http://www.w3.org/2005/Atom"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}feed")

    def field(parent, name, text):
        ET.SubElement(parent, f"{{{namespace}}}{name}").text = text

    base = "https://ronaldndirangu.github.io/nse-market-agent/"
    events_path = config.REPORTS / "daily" / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
    field(root, "id", base + "feed.xml")
    field(root, "title", "NSE daily brief and material changes")
    field(root, "updated", max((e["updated"] for e in events), default="2026-11-11T00:00:00+00:00"))
    ET.SubElement(root, f"{{{namespace}}}link", {"href": base + "feed.xml", "rel": "self"})
    for event in reversed(events):
        item = ET.SubElement(root, f"{{{namespace}}}entry")
        field(item, "id", base + "events/" + event["id"])
        field(item, "title", event["text"])
        field(item, "updated", event["updated"])
        field(item, "summary", event["text"])
        ET.SubElement(item, f"{{{namespace}}}link", {"href": base + f"daily/{event['date']}.html"})
        author = ET.SubElement(item, f"{{{namespace}}}author")
        field(author, "name", "NSE Value Agent")
    ET.ElementTree(root).write(site / "feed.xml", encoding="utf-8", xml_declaration=True)


def _stock_finder(snapshot: dict | None, up: str) -> str:
    if not snapshot:
        return ""
    rows = {r["ticker"]: r for key in ("top", "ranking") for r in (snapshot.get(key) or [])
            if isinstance(r, dict) and re.fullmatch(r"[A-Z0-9]+", str(r.get("ticker", "")))}
    if not rows:
        return ""
    links = "".join(
        f'<li data-find-stock="{E((r["ticker"] + " " + r["name"] + " " + r["sector"]).lower())}">'
        f'<a href="{up}stocks/{E(r["ticker"])}.html"><b>{E(r["ticker"])}</b> {E(r["name"])}'
        f'<small>{E(r["tier"])}: {E((r.get("decision") or {}).get("reason") or "Open the recorded assessment")}'
        '</small></a></li>' for r in sorted(rows.values(), key=lambda r: r["ticker"]))
    return ('<section class="stock-finder" data-stock-finder aria-label="Find a stock">'
            '<label for="quick-stock">Find a stock</label><input id="quick-stock" type="search" '
            'placeholder="Company or ticker, e.g. Safaricom or SCOM" autocomplete="off" '
            'aria-controls="stock-matches" aria-expanded="false">'
            '<div class="stock-matches" id="stock-matches" hidden><p data-find-status role="status" '
            f'aria-live="polite"></p><ul>{links}</ul></div>'
            f'<noscript><a href="{up}index.html#all-stocks">Browse all covered stocks</a></noscript></section>')


def build() -> list[Path]:
    """Render the dashboard, reports and archive into config.SITE for GitHub Pages."""
    site, reports = config.SITE, config.REPORTS
    site.mkdir(parents=True, exist_ok=True)
    present = [p for p in PAGES if (reports / p[0]).exists()]
    destinations = {dst for _, dst, _, _ in present}
    nav = [("index.html", "Today")]
    nav += [(dst, label) for dst, label in (("weekly.html", "Weekly"), ("retrospective.html", "Track record"))
            if dst in destinations]
    nav += [("index.html#data-health", "Data health"), ("archive.html", "Archive")]
    research = [(dst, label) for _, dst, label, _ in present if dst not in ("weekly.html", "retrospective.html")]
    stamp = datetime.now(EAT).strftime("%d %b %Y %H:%M EAT")
    written: list[Path] = []

    def page(name: str, title: str, body: str, active: str) -> None:
        up = "../" * name.count("/")
        links = "".join(f'<a href="{up}{dst}"{" aria-current=page" if dst == active else ""}>{E(label)}</a>'
                        for dst, label in nav)
        if research:
            links += ('<details><summary>Research</summary><div>'
                      + "".join(f'<a href="{up}{dst}">{E(label)}</a>' for dst, label in research) + "</div></details>")
        mobile = ''.join(f'<a href="{up}{dst}"{" aria-current=page" if dst == active else ""}>{E(label)}</a>'
                         for dst, label in nav + research)
        doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
               f'content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">'
               f'<meta name="description" content="Rule-based value agent for the Nairobi Securities Exchange: '
               f'undervalued stocks, risk profiles and projected returns.">'
               f'<script>{THEME_SCRIPT}</script><title>{E(title)} | NSE Value Agent</title>'
               + (f'<meta name="nse-daily-revision" content="{E(snapshot["revision"])}">'
                  if snapshot and snapshot.get("revision") else "")
               + f'<link rel="icon" href="{FAVICON}"><link rel="alternate" type="application/atom+xml" '
               f'title="NSE daily brief" href="{up}feed.xml"><style>{CSS}</style>'
               f'</head><body><a class="skip" href="#main">Skip to content</a><header class="top"><div class="wrap '
               f'bar"><a class="brand" href="{up}index.html">{LOGO}<span>NSE Value Agent<small>Nairobi Securities '
               f'Exchange</small></span></a><nav class="nav" aria-label="Main">{links}</nav>'
               f'<details class="mobile-nav"><summary>{_icon("menu")}Menu</summary>'
               f'<nav aria-label="Mobile">{mobile}</nav></details></div></header>'
               f'<main id="main" class="wrap">{_stock_finder(snapshot, up)}{body}</main>'
               f'<footer class="foot"><div class="wrap"><p><b>Rule-based, '
               f'no AI.</b> Fundamentals come from sourced company filings, prices from public NSE data and rates '
               f'from CBK.</p><p><b>Not financial advice.</b> {E(DISCLAIMER)}</p><p>Version {__version__}. Built '
               f'{stamp}. <a href="{REPO}">Source on GitHub</a>.</p></div></footer><script>{JS}</script></body>'
               f'</html>\n')
        p = site / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc, encoding="utf-8", newline="\n")
        written.append(p)

    snapshot = _load_json(reports / "daily" / "latest.json")
    retro = _load_json(config.DATA / "retrospective.json")
    page("index.html", "Dashboard", dashboard(snapshot, retro, present), "index.html")
    if snapshot:
        stocks = {}
        for key in ("ranking", "top", "high_confidence", "near_misses"):
            items = snapshot.get(key)
            if isinstance(items, list):
                stocks.update({i["ticker"]: i for i in items if isinstance(i, dict)})
        for ticker, item in stocks.items():
            if not re.fullmatch(r"[A-Z0-9]+", ticker):
                raise ValueError(f"Invalid stock page ticker: {ticker}")
            filing = (f'<p><a class="button" href="{E(item["source_url"])}">{_icon("book")}'
                      f'Open {E(item.get("latest_period", "annual"))} filing</a></p>'
                      f'<p class="page-note">Verify the figures against this source. Not financial advice.</p>') if item.get("source_url") else (
                          '<p>Source link unavailable in this older snapshot. Check the weekly report.</p>')
            stock_health = snapshot
            if snapshot.get("health"):
                stock_health = snapshot | {"health": snapshot["health"] | {
                    "tickers": {t: r for t, r in snapshot["health"]["tickers"].items() if t == ticker}}}
            cal = (((retro or {}).get("reconstructed") or {}).get("12") or {}).get("calibration")
            page(f"stocks/{ticker}.html", item["name"],
                 f'<a class="back-link" href="../index.html">Back to today</a>'
                 f'<p class="eyebrow">Stock review &middot; {E(snapshot["as_of"])}</p><h1>{E(item["name"])}</h1>'
                 + _stock_card(item, snapshot.get("hurdle"), gates=True, why=True, tbill=snapshot.get("tbill_net"),
                               cal=cal, detail=True)
                 + filing + _health_panel(stock_health), "index.html")
    for src, dst, label, _ in present:
        body = render_markdown((reports / src).read_text(encoding="utf-8"))
        if dst == "retrospective.html" and retro:
            body = re.sub(r"<h1>.*?</h1>", "", body, count=1, flags=re.S)
            body = ('<h1>Track record, explained</h1>' + _track_record(retro)
                    + '<details class="fold" id="technical-results"><summary><h2>Full technical report</h2></summary>'
                    + body + "</details>")
        page(dst, label, body, dst)

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
        latest_link = (f'<p class="small"><a href="{latest}">Latest</a></p>'
                       if latest in destinations else "")
        sections.append(f'<section class="card months" id="{sub}"><h2>{label}</h2>{latest_link}{items}</section>')
    page("archive.html", "Archive", "<h1>Archive</h1>" + "".join(sections), "archive.html")
    redirect = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=archive.html#daily">'
                '<link rel="canonical" href="archive.html#daily"><a href="archive.html#daily">Daily brief archive</a>\n')
    (site / "daily-archive.html").write_text(redirect, encoding="utf-8", newline="\n")
    (site / ".nojekyll").write_text("", encoding="utf-8")
    _feed(site)
    manifest_path = reports / "daily" / "manifest.json"
    if manifest_path.exists():
        (site / "manifest.json").write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
    if snapshot:
        (site / "status.json").write_text(json.dumps({k: snapshot.get(k) for k in (
            "revision", "as_of", "generated", "health")}, ensure_ascii=True), encoding="utf-8")
    return written


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag in ("a", "link") and values.get("href"):
            self.links.append(values["href"])


def check() -> int:
    """Reject broken generated panels, internal links and mismatched prediction provenance."""
    pages = {}
    for path in config.SITE.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"Panel unavailable|Ranking unavailable|>(?:nan|inf|-inf|None)<", text):
            raise ValueError(f"Invalid generated content: {path.name}")
        parser = _Links()
        parser.feed(text)
        pages[path.resolve()] = parser
    for path, parser in pages.items():
        for href in parser.links:
            link = urlsplit(href)
            if link.scheme or link.netloc:
                continue
            target = (path.parent / unquote(link.path)).resolve() if link.path else path
            if not target.is_relative_to(config.SITE.resolve()) or not target.exists():
                raise ValueError(f"Broken internal link in {path.name}: {href}")
            if link.fragment and target in pages and unquote(link.fragment) not in pages[target].ids:
                raise ValueError(f"Broken anchor in {path.name}: {href}")
    manifest_path = config.REPORTS / "daily" / "manifest.json"
    snapshot_path = config.REPORTS / "daily" / "latest.json"
    if snapshot_path.exists():
        if not isinstance(json.loads(snapshot_path.read_text(encoding="utf-8")), dict):
            raise ValueError("Invalid daily snapshot")
    if manifest_path.exists():
        from . import publication
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        publication.validate(snapshot, manifest)
        index = (config.SITE / "index.html").read_text(encoding="utf-8")
        artifact_manifest = json.loads((config.SITE / "manifest.json").read_text(encoding="utf-8"))
        if artifact_manifest != manifest or f'content="{snapshot["revision"]}"' not in index:
            raise ValueError("Site artifact does not match the publication revision")
        if snapshot["as_of"] not in index:
            raise ValueError("Dashboard date does not match the publication manifest")
    if not pages:
        raise ValueError("No generated site pages")
    ET.parse(config.SITE / "feed.xml")
    return len(pages)
