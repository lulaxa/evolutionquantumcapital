#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EQC Sector Rotation Insights Generator
======================================
Gera um artigo HTML /insights/ de **rotação setorial e fluxo de capital** a
partir dos dados produzidos pelo content_sector_screener.py.

Reutiliza os componentes (CSS, nav, footer, índice, sitemap) do
insights_generator.py para manter coerência total com os artigos semanais.

Uso (standalone, lê um JSON com {date, df, meta}):
    python sector_insights_generator.py sector_data.json

Mais comum: é chamado automaticamente pelo content_sector_screener.py
(ver hook no fim do run()).
"""
import json
import sys
import html
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from insights_generator import (  # noqa: E402
    HEAD_CSS, NAV_HTML, FONTS, FOOTER, SITE, INSIGHTS,
    load_registry, save_registry, rebuild_index_and_sitemap,
)

TABLE_CSS = """
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:18px 0}
.tablewrap table{margin:0;min-width:560px}
table{width:100%;border-collapse:collapse;margin:18px 0;font-size:.88rem}
th,td{text-align:right;padding:9px 10px;border-bottom:1px solid rgba(74,130,200,.14)}
th:first-child,td:first-child{text-align:left}
th{font-family:'DM Mono',monospace;font-size:.7rem;letter-spacing:.08em;
text-transform:uppercase;color:var(--gold)}
td.pos{color:var(--green)}td.neg{color:var(--red)}
.tag{font-family:'DM Mono',monospace;font-size:.66rem;letter-spacing:.08em;
text-transform:uppercase;padding:2px 8px;border-radius:6px}
.tag.anom{background:rgba(255,77,106,.15);color:var(--red)}
.tag.elev{background:rgba(201,169,74,.15);color:var(--gold)}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def pct(v):
    if v is None:
        return "—"
    return f"{v:+.2f}%"


def cls(v):
    if v is None:
        return ""
    return "pos" if v > 0 else ("neg" if v < 0 else "")


def render(data: dict, slug: str) -> str:
    run_date = data["date"]                       # YYYY-MM-DD
    d = datetime.strptime(run_date, "%Y-%m-%d").date()
    label = f"{d.strftime('%B')} {d.day}, {d.year}"
    df = data["df"]
    meta = data.get("meta", {})

    url = f"{SITE}/insights/{slug}.html"
    title = f"Sector Rotation & Capital Flow — {label}"
    leaders = ", ".join(meta.get("leaders", []) or []) or "—"
    laggards = ", ".join(meta.get("laggards", []) or []) or "—"
    rotation = meta.get("rotation_note", "")
    corr = meta.get("corr_note", "") or ""
    desc = (f"Weekly sector rotation and capital-flow analysis across 11 SPDR sector ETFs "
            f"as of {label}. Leaders: {leaders}. {rotation}").strip()

    # tabela
    rows_html = ""
    for r in df:
        vf = r.get("vol_flag", "NORMAL")
        vtag = (f'<span class="tag anom">{vf}</span>' if vf == "ANOMALY"
                else f'<span class="tag elev">{vf}</span>' if vf == "ELEVATED" else "—")
        rows_html += (
            f'<tr><td>{esc(r["sector"])} <span style="color:var(--muted)">{esc(r["ticker"])}</span></td>'
            f'<td class="{cls(r.get("chg_1d"))}">{pct(r.get("chg_1d"))}</td>'
            f'<td class="{cls(r.get("chg_1w"))}">{pct(r.get("chg_1w"))}</td>'
            f'<td class="{cls(r.get("chg_1m"))}">{pct(r.get("chg_1m"))}</td>'
            f'<td class="{cls(r.get("vs_spy_1w"))}">{pct(r.get("vs_spy_1w"))}</td>'
            f'<td>{esc(r.get("trend","—"))}</td>'
            f'<td>{vtag}</td></tr>')

    cards = (f'<div class="card"><div class="k">Leaders (vs S&amp;P)</div><div class="v">{esc(leaders)}</div>'
             f'<div class="d">Sectors outperforming the broad market this week.</div></div>'
             f'<div class="card"><div class="k">Laggards</div><div class="v">{esc(laggards)}</div>'
             f'<div class="d">Sectors underperforming — potential outflows.</div></div>')
    if rotation:
        cards += (f'<div class="card"><div class="k">Rotation Signal</div><div class="v" style="font-size:1rem;line-height:1.5">{esc(rotation)}</div></div>')

    vol_alerts = meta.get("vol_alerts", []) or []
    vol_html = ""
    if vol_alerts:
        items = ", ".join(f'{esc(a["sector"])} ({a["vol_ratio"]:.1f}×)' for a in vol_alerts)
        vol_html = f'<p><strong>Volume alerts:</strong> {items} — abnormal trading activity vs the 20-day average.</p>'

    jsonld = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": title, "description": desc, "datePublished": run_date, "dateModified": run_date,
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
<style>{HEAD_CSS}{TABLE_CSS}</style>
</head><body>
{NAV_HTML}
<header class="art-hero"><div class="wrap">
<div class="eyebrow">Sector Rotation &amp; Capital Flow</div>
<h1>Sector Rotation &amp; Capital Flow — {esc(label)}</h1>
<div class="art-meta">11 SPDR sector ETFs · performance vs S&amp;P 500 · {esc(label)}</div>
</div></header>
<div class="wrap"><article>
<p class="lead">A systematic, rule-based read on where capital is rotating across the 11 major US
sectors. We track 1-day, 1-week and 1-month performance, relative strength versus the S&amp;P 500,
volume anomalies and inter-sector correlation — no individual stock picks, pure sector-level flow.</p>
<div class="cards">{cards}</div>
<h2>Sector performance table</h2>
<div class="tablewrap"><table>
<thead><tr><th>Sector</th><th>1D</th><th>1W</th><th>1M</th><th>vs S&amp;P 1W</th><th>Trend</th><th>Volume</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
<h2>What the rotation is telling us</h2>
<p>{esc(rotation)}</p>
{f'<p>{esc(corr)}</p>' if corr else ''}
{vol_html}
<p>Relative strength versus the S&amp;P 500 is the cleanest signal of capital inflows and outflows:
a sector beating the index is attracting money; one lagging is bleeding it. Combined with volume
anomalies and correlation shifts, this maps the market's risk appetite week to week.</p>
<p>This sector view complements our <a href="/insights/">weekly stock screener</a> and the
rules-based <a href="/system.html">R-system methodology</a>. For live signals and alerts,
<a href="/index.html#contact">request access</a>.</p>
<div class="disclaimer">Produced by the EQC automated analysis system for educational purposes only.
Not financial advice or a recommendation to buy or sell any security. Sector data via public market
sources. EQC is a systematic, rule-based, non-discretionary trading brand.</div>
<a class="backlink" href="/insights/">&larr; All insights</a>
</article></div>
{FOOTER}
</body></html>"""


def process(data: dict):
    # DESATIVADO (Jul 2026): os screeners passaram a ser partilhados no Telegram.
    # A pagina /insights/ mostra apenas o Market Index live + nota Telegram.
    # Para reactivar a geracao de artigos, remove estas 3 linhas.
    print("insights: geracao de artigos DESATIVADA (so rebuild da pagina/sitemap).")
    rebuild_index_and_sitemap()
    return
    run_date = data["date"]
    slug = f"sector-rotation-{run_date}"
    INSIGHTS.mkdir(exist_ok=True)
    (INSIGHTS / f"{slug}.html").write_text(render(data, slug), encoding="utf-8")

    d = datetime.strptime(run_date, "%Y-%m-%d").date()
    meta = data.get("meta", {})
    leaders = ", ".join(meta.get("leaders", []) or []) or "—"
    excerpt = (f"Weekly sector rotation and capital-flow analysis across 11 SPDR sector ETFs. "
               f"Leaders: {leaders}. {meta.get('rotation_note','')}").strip()

    reg = [a for a in load_registry() if a["slug"] != slug]
    reg.append({
        "slug": slug,
        "title": f"Sector Rotation & Capital Flow — {d.strftime('%B')} {d.day}, {d.year}",
        "date": run_date,
        "date_label": f"{d.strftime('%B')} {d.day}, {d.year}",
        "excerpt": excerpt,
    })
    save_registry(reg)
    print(f"OK artigo setorial gerado: insights/{slug}.html")
    rebuild_index_and_sitemap()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    process(data)


if __name__ == "__main__":
    main()
