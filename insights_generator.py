#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EQC Insights Generator
======================
Transforma os resumos semanais do screener (PDF) em artigos HTML indexáveis
para SEO, na secção /insights/ do site eqc.investments.

Uso:
    python insights_generator.py EQC_Weekly_Summary_May25-May29_2026.pdf
    python insights_generator.py --rebuild      # só reconstrói índice + sitemap
    python insights_generator.py --all          # processa todos os PDFs semanais

Dependências: pip install pdfplumber
"""
import json
import re
import sys
import glob
import html
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
INSIGHTS = BASE / "insights"
REGISTRY = INSIGHTS / "_articles.json"
SITE = "https://eqc.investments"
CORE_PAGES = ["", "system.html", "portfolio.html", "community.html", "tools.html", "faq.html", "privacy.html", "terms.html"]

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

REGIONS = (r"(?:China\s*&\s*Taiwan|China\s*&\s*Japan|Taiwan\s*&\s*Japan|"
           r"China|Taiwan|Japan|Hong Kong|United States|US|Europe|India|Canada|"
           r"Korea|Australia|Singapore|Turkey|Brazil|Vietnam|Spain|Philippines|"
           r"Global|Asia)")
BIAS_VOCAB = (r"(?:Neutral\s*/\s*Mixed|Risk-O(?:n|ff)[^\n]*|Bullish[^\n]*|Bearish[^\n]*|"
              r"Net Long[^\n]*|Net Short[^\n]*|Mixed)")


# ----------------------------------------------------------------------------
# 1. EXTRAÇÃO DO PDF
# ----------------------------------------------------------------------------
def parse_weekly_pdf(pdf_path: Path) -> dict:
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    full = "\n".join(pages)

    norm = full
    for up, tt in [("MAY", "May"), ("JUN", "Jun"), ("APR", "Apr"), ("JUL", "Jul"),
                   ("MAR", "Mar"), ("AUG", "Aug"), ("SEP", "Sep"), ("OCT", "Oct"),
                   ("NOV", "Nov"), ("DEC", "Dec"), ("JAN", "Jan"), ("FEB", "Feb")]:
        norm = norm.replace(up, tt)
    m = re.search(r"([A-Z][a-z]{2,8})\s+(\d{1,2})\s*[\-–]\s*([A-Z][a-z]{2,8})\s+(\d{1,2}),\s*(\d{4})", norm)
    if m:
        m1, d1, m2, d2, yr = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    else:
        fm = re.search(r"([A-Za-z]{3})(\d{1,2})-([A-Za-z]{3})(\d{1,2})_(\d{4})", pdf_path.stem)
        if not fm:
            raise ValueError("Não consegui extrair a semana do PDF nem do nome.")
        m1, d1, m2, d2, yr = fm.group(1), fm.group(2), fm.group(3), fm.group(4), fm.group(5)

    d1, d2, yr = int(d1), int(d2), int(yr)
    start = date(yr, MONTHS[m1[:3].title()], d1)
    end = date(yr, MONTHS[m2[:3].title()], d2)

    persistent = geo = bias = ""
    vm = re.search(r"MOST PERSISTENT SIGNAL[^\n]*\n([^\n]+)", full)
    if vm:
        value_line = vm.group(1).strip()
        bm = re.search(BIAS_VOCAB, value_line)
        if bm:
            bias = bm.group(0).strip()
            value_line = value_line.replace(bm.group(0), " ")
        gm = re.search(REGIONS, value_line)
        if gm:
            geo = gm.group(0).strip()
            value_line = value_line.replace(gm.group(0), " ")
        persistent = re.sub(r"\s{2,}", " ", value_line).strip(" -—·")

    if start.month == end.month:
        label = f"{start.strftime('%B')} {start.day}–{end.day}, {yr}"
    else:
        label = f"{start.strftime('%B')} {start.day} – {end.strftime('%B')} {end.day}, {yr}"

    return {"start": start, "end": end, "year": yr, "label": label,
            "persistent": persistent, "geography": geo, "bias": bias}


# ----------------------------------------------------------------------------
# 2. TEMPLATE / RENDER
# ----------------------------------------------------------------------------
HEAD_CSS = """
:root{--bg:#050f1e;--bg2:#081628;--navy:#0b1e3a;--surface:#102040;
--border:rgba(180,145,60,.18);--gold:#c9a94a;--goldl:#e8cc7a;--blue:#2d6abf;
--white:#e6eef8;--muted:rgba(230,238,248,.55);--green:#00e87a;--red:#ff4d6a;}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--white);font-family:'Syne',sans-serif;
line-height:1.7;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
background-image:linear-gradient(rgba(74,130,200,.05) 1px,transparent 1px),
linear-gradient(90deg,rgba(74,130,200,.05) 1px,transparent 1px);background-size:80px 80px}
a{color:var(--goldl);text-decoration:none}a:hover{color:var(--gold)}
.wrap{position:relative;z-index:1;max-width:860px;margin:0 auto;padding:0 24px}
nav{position:relative;z-index:5;display:flex;align-items:center;justify-content:space-between;
max-width:1200px;margin:0 auto;padding:22px 24px;border-bottom:1px solid var(--border);flex-wrap:wrap;gap:12px}
.nav-brand{display:flex;align-items:center;gap:12px}
.nav-logo-img{width:42px;height:42px;object-fit:contain}
.nav-logo-text{font-family:'DM Serif Display',serif;font-size:1.1rem;color:var(--white)}
.nav-links{list-style:none;display:flex;gap:22px;flex-wrap:wrap}
.nav-links a{color:var(--muted);font-size:.9rem;letter-spacing:.04em;text-transform:uppercase}
.nav-links a:hover,.nav-links a.nav-active{color:var(--gold)}
.art-hero{position:relative;z-index:1;text-align:center;padding:60px 24px 30px}
.eyebrow{font-family:'DM Mono',monospace;color:var(--gold);font-size:.8rem;
letter-spacing:.22em;text-transform:uppercase}
h1{font-family:'DM Serif Display',serif;font-size:clamp(1.8rem,4.5vw,3rem);
line-height:1.15;margin:18px 0 12px;font-weight:400}
.art-meta{color:var(--muted);font-family:'DM Mono',monospace;font-size:.85rem}
article{position:relative;z-index:1;padding:24px 0 60px}
article h2{font-family:'DM Serif Display',serif;font-weight:400;font-size:1.6rem;
margin:38px 0 14px;color:var(--goldl)}
article p{margin:0 0 16px;color:var(--white)}
article p.lead{font-size:1.15rem;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:24px 0}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}
.card .k{font-family:'DM Mono',monospace;font-size:.72rem;letter-spacing:.16em;
text-transform:uppercase;color:var(--gold)}
.card .v{font-family:'DM Serif Display',serif;font-size:1.25rem;margin-top:8px}
.card .d{color:var(--muted);font-size:.85rem;margin-top:6px}
.disclaimer{margin-top:40px;padding:18px;border:1px solid var(--border);border-radius:12px;
background:var(--bg2);color:var(--muted);font-size:.82rem}
.backlink{display:inline-block;margin:30px 0 0;font-family:'DM Mono',monospace;font-size:.85rem}
footer{position:relative;z-index:1;border-top:1px solid var(--border);margin-top:50px;
padding:30px 24px;text-align:center;color:var(--muted);font-size:.82rem}
.post-list{list-style:none;padding:0;margin:30px 0}
.post-item{border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:18px;
background:var(--surface);transition:border-color .2s}
.post-item:hover{border-color:var(--gold)}
.post-item h2{font-family:'DM Serif Display',serif;font-weight:400;font-size:1.4rem;margin:0 0 8px}
.post-item .date{font-family:'DM Mono',monospace;color:var(--gold);font-size:.78rem;
letter-spacing:.14em;text-transform:uppercase}
.post-item p{color:var(--muted);margin:10px 0 0}
/* ---- MOBILE ---- */
@media (max-width:640px){
  nav{flex-direction:column;align-items:flex-start;padding:16px 18px;gap:10px}
  .nav-logo-text{font-size:1rem}
  .nav-links{gap:14px 16px;width:100%}
  .nav-links a{font-size:.78rem;letter-spacing:.02em}
  .wrap{padding:0 18px}
  .art-hero{padding:34px 18px 18px}
  h1{font-size:1.6rem;line-height:1.2}
  .art-meta{font-size:.78rem}
  article{padding:18px 0 40px}
  article h2{font-size:1.3rem;margin:28px 0 10px}
  article p{font-size:.98rem}
  article p.lead{font-size:1.05rem}
  .cards{grid-template-columns:1fr;gap:12px;margin:18px 0}
  .card{padding:16px}
  .card .v{font-size:1.1rem}
  .disclaimer{padding:14px;font-size:.78rem}
  table{font-size:.8rem}
  th,td{padding:7px 8px}
}
"""

NAV_HTML = """<nav>
  <div class="nav-brand"><a href="/index.html" style="display:flex;align-items:center;gap:12px;text-decoration:none"><img class="nav-logo-img" src="/assets/eqc-logo.png" alt="EQC logo"><span class="nav-logo-text">Evolution Quantum Capital</span></a></div>
  <ul class="nav-links">
    <li><a href="/index.html">Home</a></li>
    <li><a href="/system.html">System</a></li>
    <li><a href="/portfolio.html">Portfolio</a></li>
    <li><a href="/insights/" class="nav-active">Insights</a></li>
    <li><a href="/community.html">Community</a></li>
    <li><a href="/tools.html">Tools</a></li>
    <li><a href="/faq.html">FAQ</a></li>
  </ul>
</nav>"""

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1'
         '&family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">')

FOOTER = ('<footer><div class="nav-logo-text" style="margin-bottom:8px">Evolution Quantum Capital</div>'
          '<div>Rule-based. Non-discretionary. <span style="color:var(--gold)">EQC.</span></div>'
          '<div style="margin-top:10px">&copy; 2026 Evolution Quantum Capital · All Rights Reserved</div></footer>')

DISCLAIMER = ('<div class="disclaimer">This report is produced by the EQC automated screener system for '
              'educational purposes only. It does not constitute financial advice or a recommendation to buy '
              'or sell any security. EQC is a systematic, rule-based, non-discretionary trading brand.</div>')


def esc(s):
    return html.escape(str(s), quote=True)


def render_article(data: dict, slug: str) -> str:
    url = f"{SITE}/insights/{slug}.html"
    title = f"EQC Weekly Screener Summary — {data['label']}"
    desc = (f"Weekly systematic screener results for {data['label']}: oversold and overbought "
            f"candidates across 16,000+ stocks in 33 markets, ranked by EQC Score. "
            f"Daily, weekly and monthly oscillator signals.")
    pub = data['end'].strftime("%Y-%m-%d")

    cards = ""
    if data.get("persistent"):
        cards += (f'<div class="card"><div class="k">Most Persistent Signal</div>'
                  f'<div class="v">{esc(data["persistent"])}</div>'
                  f'<div class="d">Highest cross-timeframe persistence this week.</div></div>')
    if data.get("geography"):
        cards += (f'<div class="card"><div class="k">Dominant Geography — Longs</div>'
                  f'<div class="v">{esc(data["geography"])}</div>'
                  f'<div class="d">Where the long candidates clustered.</div></div>')
    if data.get("bias"):
        cards += (f'<div class="card"><div class="k">Market Bias This Week</div>'
                  f'<div class="v">{esc(data["bias"])}</div>'
                  f'<div class="d">Net oversold vs overbought reading.</div></div>')
    cards_block = f'<div class="cards">{cards}</div>' if cards else ""

    jsonld = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": title, "description": desc, "datePublished": pub, "dateModified": pub,
        "url": url, "mainEntityOfPage": url,
        "author": {"@type": "Organization", "name": "Evolution Quantum Capital"},
        "publisher": {"@type": "Organization", "name": "Evolution Quantum Capital",
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/eqc-logo.png"}},
        "image": f"{SITE}/assets/og-image.png",
    }
    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Insights", "item": f"{SITE}/insights/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url},
        ]}

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{SITE}/assets/og-image.png">
<meta property="og:site_name" content="Evolution Quantum Capital">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@EvolutionQC">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE}/assets/og-image.png">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(breadcrumb, ensure_ascii=False)}</script>
<title>{esc(title)}</title>
{FONTS}
<style>{HEAD_CSS}</style>
</head><body>
{NAV_HTML}
<header class="art-hero"><div class="wrap">
<div class="eyebrow">Weekly Screener Summary</div>
<h1>Systematic Screener Results — {esc(data['label'])}</h1>
<div class="art-meta">Published {data['end'].strftime('%B')} {data['end'].day}, {data['year']} · 16,000+ stocks · 33 markets</div>
</div></header>
<div class="wrap"><article>
<p class="lead">The EQC Screener runs three independent scans every day — Daily, Weekly and Monthly
timeframes — flagging stocks where all four oscillators (RSI 14, Stochastic %K, CCI 20, Williams %R)
hit an extreme reading simultaneously. This report consolidates the full week into a single actionable view.</p>
{cards_block}
<h2>How to read this report</h2>
<p>A stock that appears repeatedly earns a <strong>persistence badge</strong> — the more days it holds the
signal, the stronger the structural case. The <strong>EQC Score</strong> ranks signal intensity: higher is
stronger. Oversold readings flag potential <span style="color:var(--green)">long</span> candidates;
overbought readings flag potential <span style="color:var(--red)">short</span> candidates.</p>
<h2>Daily screener — swing setup candidates</h2>
<p>Stocks that hit extreme oscillator readings on the daily chart. Shorter-term signals, ideal for swing-trade
entries, ranked by average EQC Score across the week.</p>
<h2>Weekly &amp; monthly — structural candidates</h2>
<p>Weekly and monthly signals are slower to form and carry higher conviction. A stock oversold on the monthly
chart is the highest-conviction timeframe the screener produces. Full tables, tickers and scores are available
to members inside the <a href="/community.html">EQC community</a>.</p>
<p>Want the live screener and real-time alerts? <a href="/index.html#contact">Request access</a> or explore
the <a href="/system.html">R-system methodology</a> behind every signal.</p>
{DISCLAIMER}
<a class="backlink" href="/insights/">&larr; All insights</a>
</article></div>
{FOOTER}
</body></html>"""


TELEGRAM_NOTE_HTML = '<div class="wrap" style="margin-bottom:64px;"><div style="border:1px solid rgba(201,169,74,0.25);background:rgba(201,169,74,0.03);padding:32px;text-align:center;"><div style="font-family:\'DM Mono\',monospace;font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:#c9a94a;margin-bottom:12px;">// Screeners</div><h2 style="font-family:\'DM Serif Display\',serif;font-size:24px;color:#ffffff;margin:0 0 12px;">Daily &amp; Weekly Screeners &mdash; on Telegram</h2><p style="font-family:\'DM Mono\',monospace;font-size:12px;color:#8899bb;line-height:1.8;max-width:560px;margin:0 auto 20px;">All EQC screener results &mdash; daily oversold/overbought scans across 16,000+ stocks in 33 markets, weekly summaries and sector rotation analysis &mdash; are shared in our Telegram community.</p><a href="https://t.me/+dN1L-SlHNN02ZWI0" target="_blank" rel="noopener" style="display:inline-block;font-family:\'DM Mono\',monospace;font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#c9a94a;border:1px solid #c9a94a;padding:12px 28px;text-decoration:none;">Join the Telegram &rarr;</a></div></div>'


MARKET_INDEX_HTML = '<!-- ===== EQC MARKET INDEX LIVE ===== -->\n<div class="wrap" id="market-index-live" style="margin-top:48px;margin-bottom:56px;">\n  <div style="font-family:\'DM Mono\',monospace;font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:#c9a94a;margin-bottom:6px;">// Live Readings</div>\n  <h2 style="font-family:\'DM Serif Display\',serif;font-size:28px;color:#ffffff;margin:0 0 6px;">EQC Market Index &mdash; US &amp; Asia</h2>\n  <p id="mi-updated" style="font-family:\'DM Mono\',monospace;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:#8899bb;margin:0 0 24px;"></p>\n\n  <div style="border:1px solid rgba(201,169,74,0.25);background:rgba(201,169,74,0.03);padding:22px;margin-bottom:24px;">\n    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:16px;">\n      <div style="font-family:\'DM Mono\',monospace;font-size:9px;letter-spacing:0.3em;text-transform:uppercase;color:#c9a94a;">US vs Asia &mdash; History</div>\n      <div id="mi-chart-tabs" style="display:flex;gap:6px;"></div>\n    </div>\n    <div style="position:relative;height:320px;"><canvas id="mi-chart"></canvas></div>\n  </div>\n\n  <div id="mi-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:22px;"></div>\n\n  <div style="margin-top:26px;display:flex;flex-wrap:wrap;gap:18px;font-family:\'DM Mono\',monospace;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:#8899bb;">\n    <span><span style="color:#e85252;">&#9632;</span> Mania &ge;85</span>\n    <span><span style="color:#f0a04b;">&#9632;</span> Euphoria &ge;70</span>\n    <span><span style="color:#3dba5e;">&#9632;</span> Healthy Bull &ge;50</span>\n    <span><span style="color:#e8cc7a;">&#9632;</span> Recovery &ge;30</span>\n    <span><span style="color:#7e57c2;">&#9632;</span> Bottom / Fear &lt;30</span>\n    <span><span style="color:#e85252;">INVAL</span> = cycle invalidated</span>\n    <span>&mdash; = cycle not defined</span>\n  </div>\n</div>\n\n<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n<script>\n(function(){\n  var ZC = function(v){ if(v==null) return \'#8899bb\';\n    return v>=85?\'#e85252\':v>=70?\'#f0a04b\':v>=50?\'#3dba5e\':v>=30?\'#e8cc7a\':\'#7e57c2\'; };\n  var MONO = "font-family:\'DM Mono\',monospace;";\n  var state = { data:null, tf:{} };\n\n  function card(key, idx){\n    var tf = state.tf[key] || \'W\';\n    var d  = idx.tfs[tf];\n    var tabs = [\'W\',\'M\',\'3M\',\'6M\',\'12M\'].map(function(t){\n      var on = t===tf;\n      return \'<button data-idx="\'+key+\'" data-tf="\'+t+\'" style="\'+MONO+\'font-size:10px;letter-spacing:0.1em;padding:5px 10px;cursor:pointer;background:\'+(on?\'rgba(201,169,74,0.15)\':\'transparent\')+\';border:1px solid \'+(on?\'#c9a94a\':\'rgba(201,169,74,0.25)\')+\';color:\'+(on?\'#c9a94a\':\'#8899bb\')+\';">\'+t+\'</button>\';\n    }).join(\'\');\n    var rows = d.components.map(function(c){\n      var cyc = c.cycle===\'INVAL\' ? \'<span style="color:#e85252;font-weight:700;">INVAL</span>\'\n              : c.cycle===\'NA\' ? \'&mdash;\' : c.cycle;\n      return \'<tr style="border-top:1px solid rgba(201,169,74,0.12);">\'\n        + \'<td style="padding:7px 4px;color:#ffffff;">\'+c.name+\'</td>\'\n        + \'<td style="padding:7px 4px;color:#8899bb;">w=\'+c.weight.toFixed(2)+\'</td>\'\n        + \'<td style="padding:7px 4px;text-align:right;color:\'+ZC(c.score)+\';font-weight:700;">\'+(c.score==null?\'&mdash;\':c.score.toFixed(1))+\'</td>\'\n        + \'<td style="padding:7px 4px;text-align:right;color:#8899bb;">\'+cyc+\'</td></tr>\';\n    }).join(\'\');\n    return \'<div style="border:1px solid rgba(201,169,74,0.25);background:rgba(201,169,74,0.03);padding:22px;">\'\n      + \'<div style="\'+MONO+\'font-size:9px;letter-spacing:0.3em;text-transform:uppercase;color:#c9a94a;margin-bottom:16px;">\'+idx.name+\'</div>\'\n      + \'<div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:16px;">\'\n      +   \'<span style="\'+MONO+\'font-size:40px;font-weight:700;color:\'+ZC(d.index)+\';">\'+(d.index==null?\'&mdash;\':d.index.toFixed(1))+\'</span>\'\n      +   \'<span style="\'+MONO+\'font-size:10px;letter-spacing:0.2em;text-transform:uppercase;padding:4px 10px;border:1px solid \'+ZC(d.index)+\';color:\'+ZC(d.index)+\';">\'+d.regime+\'</span>\'\n      +   \'<span style="\'+MONO+\'font-size:9px;color:#8899bb;">\'+d.valid+\' active</span>\'\n      + \'</div>\'\n      + \'<div style="display:flex;gap:6px;margin-bottom:12px;">\'+tabs+\'</div>\'\n      + \'<table style="width:100%;border-collapse:collapse;\'+MONO+\'font-size:11px;">\'\n      + \'<tr style="color:#8899bb;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;"><td style="padding:4px;">Component</td><td style="padding:4px;">Weight</td><td style="padding:4px;text-align:right;">Score</td><td style="padding:4px;text-align:right;">Cycle</td></tr>\'\n      + rows + \'</table></div>\';\n  }\n\n  function render(){\n    var g = document.getElementById(\'mi-grid\');\n    if(!state.data){ return; }\n    g.innerHTML = Object.keys(state.data.indices).map(function(k){ return card(k, state.data.indices[k]); }).join(\'\');\n    g.querySelectorAll(\'button[data-tf]\').forEach(function(b){\n      b.addEventListener(\'click\', function(){ state.tf[b.dataset.idx]=b.dataset.tf; render(); });\n    });\n  }\n\n  var chart = null, chartTf = \'W\';\n  var CHART_COLS = { us:\'#c9a94a\', asia:\'#5aa9e6\' };\n\n  function chartTabs(){\n    var el = document.getElementById(\'mi-chart-tabs\');\n    if(!el) return;\n    el.innerHTML = [\'W\',\'M\',\'3M\',\'6M\',\'12M\'].map(function(t){\n      var on = t===chartTf;\n      return \'<button data-ctf="\'+t+\'" style="\'+MONO+\'font-size:10px;letter-spacing:0.1em;padding:5px 10px;cursor:pointer;background:\'+(on?\'rgba(201,169,74,0.15)\':\'transparent\')+\';border:1px solid \'+(on?\'#c9a94a\':\'rgba(201,169,74,0.25)\')+\';color:\'+(on?\'#c9a94a\':\'#8899bb\')+\';">\'+t+\'</button>\';\n    }).join(\'\');\n    el.querySelectorAll(\'button\').forEach(function(b){\n      b.addEventListener(\'click\', function(){ chartTf = b.dataset.ctf; renderChart(); });\n    });\n  }\n\n  var zonePlugin = { id:\'eqcZones\', beforeDatasetsDraw:function(ch){\n    var y = ch.scales.y, x = ch.scales.x, ctx = ch.ctx;\n    if(!y || !x) return;\n    ctx.save();\n    ctx.fillStyle = \'rgba(232,82,82,0.07)\';\n    ctx.fillRect(x.left, y.getPixelForValue(100), x.width, y.getPixelForValue(85)-y.getPixelForValue(100));\n    [[85,\'#e85252\'],[70,\'#f0a04b\'],[50,\'#3dba5e\'],[30,\'#e8cc7a\']].forEach(function(z){\n      var py = y.getPixelForValue(z[0]);\n      ctx.strokeStyle = z[1]; ctx.setLineDash([4,4]); ctx.lineWidth = 0.6;\n      ctx.beginPath(); ctx.moveTo(x.left, py); ctx.lineTo(x.right, py); ctx.stroke();\n    });\n    ctx.restore();\n  }};\n\n  function renderChart(){\n    chartTabs();\n    if(!state.data || !state.data.series || typeof Chart === \'undefined\') return;\n    var s = state.data.series[chartTf];\n    if(!s) return;\n    var ds = Object.keys(state.data.indices).map(function(k){\n      return { label: state.data.indices[k].name, data: s[k],\n               borderColor: CHART_COLS[k]||\'#ffffff\', backgroundColor:\'transparent\',\n               borderWidth: 1.6, pointRadius: 0, spanGaps: true, tension: 0 };\n    });\n    if(chart){ chart.data.labels = s.dates; chart.data.datasets = ds; chart.update(); return; }\n    chart = new Chart(document.getElementById(\'mi-chart\'), {\n      type: \'line\',\n      data: { labels: s.dates, datasets: ds },\n      options: { responsive:true, maintainAspectRatio:false,\n        interaction:{ mode:\'index\', intersect:false },\n        scales: {\n          y: { min:0, max:100, grid:{ color:\'rgba(255,255,255,0.05)\' },\n               ticks:{ color:\'#8899bb\', font:{ family:\'DM Mono\', size:9 } } },\n          x: { grid:{ display:false },\n               ticks:{ color:\'#8899bb\', maxTicksLimit:8, maxRotation:0, font:{ family:\'DM Mono\', size:9 } } } },\n        plugins: { legend:{ labels:{ color:\'#e6eef8\', font:{ family:\'DM Mono\', size:10 }, boxWidth:14, boxHeight:2 } },\n                   tooltip:{ backgroundColor:\'rgba(5,15,30,0.92)\', borderColor:\'rgba(201,169,74,0.4)\', borderWidth:1,\n                             titleFont:{ family:\'DM Mono\', size:10 }, bodyFont:{ family:\'DM Mono\', size:10 } } } },\n      plugins: [zonePlugin]\n    });\n  }\n\n  fetch(\'/data/market_index.json\', {cache:\'no-store\'})\n    .then(function(r){ if(!r.ok) throw 0; return r.json(); })\n    .then(function(j){\n      state.data = j;\n      document.getElementById(\'mi-updated\').textContent = \'Last updated: \' + j.generated_at;\n      render();\n      renderChart();\n    })\n    .catch(function(){\n      document.getElementById(\'mi-grid\').innerHTML =\n        \'<p style="\'+MONO+\'font-size:11px;color:#8899bb;">Live data temporarily unavailable.</p>\';\n    });\n})();\n</script>\n<!-- ===== /EQC MARKET INDEX LIVE ===== -->'


def render_index(articles: list) -> str:
    title = "Market Insights & Weekly Screener Reports | EQC"
    desc = ("Weekly systematic screener summaries and market insights from Evolution Quantum Capital — "
            "oversold/overbought candidates across 16,000+ stocks in 33 markets, ranked by EQC Score.")
    url = f"{SITE}/insights/"
    items = ""
    for a in articles:
        items += (f'<li class="post-item"><div class="date">{esc(a["date_label"])}</div>'
                  f'<h2><a href="/insights/{a["slug"]}.html">{esc(a["title"])}</a></h2>'
                  f'<p>{esc(a["excerpt"])}</p></li>')
    if not items:
        items = '<li class="post-item"><p>Coming soon: weekly screener summaries.</p></li>'
    jsonld = {"@context": "https://schema.org", "@type": "CollectionPage",
              "name": title, "description": desc, "url": url}
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{SITE}/assets/og-image.png">
<meta property="og:site_name" content="Evolution Quantum Capital">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
<title>{esc(title)}</title>
{FONTS}
<style>{HEAD_CSS}</style>
</head><body>
{NAV_HTML}
<header class="art-hero"><div class="wrap">
<div class="eyebrow">Insights</div>
<h1>Market Insights &amp; Weekly Screener Reports</h1>
<div class="art-meta">Systematic, rule-based market scans — published weekly.</div>
</div></header>
{MARKET_INDEX_HTML}
{TELEGRAM_NOTE_HTML}
{FOOTER}
</body></html>"""


# ----------------------------------------------------------------------------
# 3. REGISTO + SITEMAP
# ----------------------------------------------------------------------------
def load_registry():
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return []


def save_registry(reg):
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def rebuild_index_and_sitemap():
    reg = load_registry()
    reg.sort(key=lambda a: a["date"], reverse=True)
    (INSIGHTS / "index.html").write_text(render_index(reg), encoding="utf-8")
    today = date.today().isoformat()
    urls = []
    for p in CORE_PAGES:
        urls.append((f"{SITE}/{p}", today, "weekly", "1.0" if p == "" else "0.8"))
    urls.append((f"{SITE}/insights/", today, "weekly", "0.8"))
    for a in reg:
        urls.append((f"{SITE}/insights/{a['slug']}.html", a["date"], "monthly", "0.6"))
    body = "".join(
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{lm}</lastmod>\n"
        f"    <changefreq>{cf}</changefreq>\n    <priority>{pr}</priority>\n  </url>\n"
        for u, lm, cf, pr in urls)
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               f"{body}</urlset>\n")
    (BASE / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"OK indice reconstruido com {len(reg)} artigo(s)")
    print(f"OK sitemap atualizado com {len(urls)} URLs")


def build_excerpt(data):
    parts = ["Systematic screener results: oversold and overbought candidates across 16,000+ stocks in 33 markets."]
    if data.get("persistent"):
        parts.append(f"Most persistent: {data['persistent'].rstrip('.')}.")
    if data.get("bias"):
        parts.append(f"Bias: {data['bias']}.")
    return " ".join(parts)


def process_pdf(pdf_path: Path):
    # DESATIVADO (Jul 2026): os screeners passaram a ser partilhados no Telegram.
    # A pagina /insights/ mostra apenas o Market Index live + nota Telegram.
    # Para reactivar a geracao de artigos, remove estas 3 linhas.
    print("insights: geracao de artigos DESATIVADA (so rebuild da pagina/sitemap).")
    rebuild_index_and_sitemap()
    return
    data = parse_weekly_pdf(pdf_path)
    slug = f"weekly-screener-{data['start'].strftime('%Y-%m-%d')}"
    INSIGHTS.mkdir(exist_ok=True)
    (INSIGHTS / f"{slug}.html").write_text(render_article(data, slug), encoding="utf-8")
    reg = [a for a in load_registry() if a["slug"] != slug]
    reg.append({
        "slug": slug,
        "title": f"Weekly Screener Summary — {data['label']}",
        "date": data["end"].strftime("%Y-%m-%d"),
        "date_label": f"{data['end'].strftime('%B')} {data['end'].day}, {data['year']}",
        "excerpt": build_excerpt(data),
    })
    save_registry(reg)
    print(f"OK artigo gerado: insights/{slug}.html")
    rebuild_index_and_sitemap()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == "--rebuild":
        rebuild_index_and_sitemap()
    elif args[0] == "--all":
        for f in sorted(glob.glob(str(BASE / "EQC_Weekly_Summary_*.pdf"))):
            try:
                process_pdf(Path(f))
            except Exception as e:
                print(f"ERRO {f}: {e}")
    else:
        process_pdf(Path(args[0]))


if __name__ == "__main__":
    main()
