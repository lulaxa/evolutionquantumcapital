#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EQC Capital Rotation (RRG) — motor de dados
============================================
Relative Rotation Graph estilo JdK, semanal, com rasto de N semanas.
Réplica aproximada (proxies livres) do EQC_Global_RS_Monitor.pine —
os índices FTSE Russell exactos não têm fonte gratuita com histórico
(ver nota "proxy_note" por componente).

Ficheiro: C:\\EQC\\eqc_rotation_live.py
Output:   C:\\EQC\\data\\rs_rotation.json

Uso:  python eqc_rotation_live.py            (calcula + grava)
      python eqc_rotation_live.py --push     (calcula + grava + git commit/push)
"""

import json
import os
import subprocess
import sys
import warnings
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

FOLDER      = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(FOLDER, "data", "rs_rotation.json")

# ── Parâmetros do modelo ────────────────────────────────────────────────────
RATIO_WIN = 10   # semanas — janela do RS-Ratio (baseline da força relativa)
MOM_WIN   = 4    # semanas — janela do RS-Momentum (ROC do RS-Ratio)
TRAIL_LEN = 10   # semanas de rasto mostradas no gráfico
HISTORY   = "3y" # profundidade de download (folga para as janelas acima)

BENCH = {"symbol": "^GSPC", "label": "S&P 500", "note": "Proxy do benchmark FTSE:RU500 (Russell Top 500) — mesmo universo conceptual (maiores ~500 US), fornecedor diferente."}

# Cores alinhadas com o EQC_Global_RS_Monitor.pine (mesmo papel visual)
COMPONENTS = {
    "RU50":   {"symbol": "^OEX",  "label": "RU50",   "color": "#ffffff", "note": "Proxy do FTSE:RU50 (Russell Top 50 Mega Cap) — usado S&P 100 (mega/large-cap real, sem equivalente directo grátis)."},
    "NDX":    {"symbol": "^NDX",  "label": "NDX",    "color": "#6688aa", "note": "Exacto — mesmo índice do indicador."},
    "JAPAN":  {"symbol": "^N225", "label": "Japan",  "color": "#3dba5e", "note": "Proxy do FTSE:JAPAN — usado Nikkei 225 (índice real japonês, fornecedor diferente)."},
    "XIN9":   {"symbol": "ASHR",  "label": "China A50", "color": "#e05555", "note": "Proxy do FTSE:XIN9 (China A50, onshore) — usado ETF ASHR sobre CSI 300 (também onshore A-shares, mesma natureza)."},
    "WIKOR":  {"symbol": "^KS11", "label": "Korea",  "color": "#55c8e0", "note": "Proxy do FTSE:WIKOR — usado KOSPI (índice real coreano, fornecedor diferente)."},
    "TW50":   {"symbol": "^TWII", "label": "Taiwan", "color": "#e0a355", "note": "Proxy do FTSE:TW50 — usado Taiwan Weighted Index (índice real, mercado principal em vez de só top 50)."},
    "WIIND":  {"symbol": "^NSEI", "label": "India",  "color": "#a878e0", "note": "Proxy do FTSE:WIIND — usado Nifty 50 (índice real indiano, fornecedor diferente). Desligado por omissão no indicador original.", "enabled_default": False},
    "AW07":   {"symbol": "AAXJ",  "label": "APAC xJP", "color": "#e078b4", "note": "Proxy do FTSE:AW07 (Ásia-Pacífico ex-Japão) — usado ETF AAXJ (mesma exclusão de Japão)."},
    "FTATPU": {"symbol": "KWEB",  "label": "Asia Tech+", "color": "#a8d05a", "note": "Proxy mais fraco: FTSE:FTATPU cobre tech pan-asiática (Taiwan semis, Coreia, Japão, China). Usado KWEB (só internet/tech China) por não existir ETF/índice pan-asiático de tech livre com histórico longo."},
}


def fetch_weekly(symbols):
    """Fecho semanal (sexta) por símbolo, período HISTORY."""
    out = {}
    for sym in sorted(set(symbols)):
        try:
            h = yf.Ticker(sym).history(period=HISTORY, interval="1wk")["Close"].dropna()
            h.index = h.index.tz_localize(None)
            out[sym] = h
            print(f"  [{sym}] {len(h)} semanas, desde {h.index[0].date()}, último {h.iloc[-1]:.2f}")
        except Exception as e:
            out[sym] = None
            print(f"  [{sym}] ERRO: {e}")
    return out


NEUTRAL_TOL = 1.0  # pontos tao perto do cruzamento (100,100) que rotular como
                    # LEADING/LAGGING seria falsa precisao — fica "NEUTRAL"


def quadrant(x, y):
    if abs(x - 100) < NEUTRAL_TOL and abs(y - 100) < NEUTRAL_TOL:
        return "NEUTRAL"
    if x >= 100 and y >= 100:
        return "LEADING"
    if x >= 100 and y < 100:
        return "WEAKENING"
    if x < 100 and y < 100:
        return "LAGGING"
    return "IMPROVING"


def build_rrg(hist, bench_symbol):
    bench = hist.get(bench_symbol)
    if bench is None or len(bench) < RATIO_WIN + MOM_WIN + TRAIL_LEN:
        raise RuntimeError(f"Benchmark {bench_symbol} sem histórico suficiente")

    components_out = []
    for key, c in COMPONENTS.items():
        h = hist.get(c["symbol"])
        if h is None or len(h) < RATIO_WIN + MOM_WIN + TRAIL_LEN:
            print(f"  [{key}] histórico insuficiente — ignorado")
            continue

        df = pd.concat([h.rename("px"), bench.rename("bx")], axis=1).dropna()
        rel = df["px"] / df["bx"]
        rs_ratio = 100.0 * (rel / rel.rolling(RATIO_WIN).mean())
        rs_mom = 100.0 * (rs_ratio / rs_ratio.shift(MOM_WIN))

        combo = pd.concat([rs_ratio.rename("x"), rs_mom.rename("y")], axis=1).dropna()
        if combo.empty:
            print(f"  [{key}] sem pontos válidos após cálculo — ignorado")
            continue

        # Exporta o historico completo disponivel (nao so as ultimas TRAIL_LEN
        # semanas) para o widget do site poder oferecer 1W/1M/YTD/1Y a
        # gosto do utilizador. Os cards estaticos (v2/v3) ja fatiam o fim
        # deste array pelas suas proprias constantes (ARROW_WEEKS etc.) —
        # continuam a funcionar sem alteracoes.
        trail = [{"date": d.strftime("%Y-%m-%d"), "x": round(r.x, 2), "y": round(r.y, 2)}
                  for d, r in combo.iterrows()]
        cur = combo.iloc[-1]
        components_out.append({
            "key": key,
            "label": c["label"],
            "symbol_used": c["symbol"],
            "color": c["color"],
            "proxy_note": c["note"],
            "enabled_default": c.get("enabled_default", True),
            "trail": trail,
            "current": {"x": round(cur.x, 2), "y": round(cur.y, 2), "quadrant": quadrant(cur.x, cur.y)},
        })
    return components_out


def git_push():
    try:
        rel = os.path.relpath(OUTPUT_FILE, FOLDER)
        subprocess.run(["git", "add", rel], cwd=FOLDER, check=True)
        r = subprocess.run(["git", "commit", "-m", "chore: update capital rotation (RRG) data"],
                           cwd=FOLDER, capture_output=True, text=True)
        if r.returncode != 0:
            print("  [git] nada para commitar" if "nothing to commit" in r.stdout + r.stderr else f"  [git] commit falhou: {r.stderr}")
            return
        subprocess.run(["git", "push"], cwd=FOLDER, check=True)
        print("  [git] push OK")
    except Exception as e:
        print(f"  [git] ERRO: {e}")


def main():
    print("=== EQC Capital Rotation (RRG) — motor de dados ===")
    symbols = [BENCH["symbol"]] + [c["symbol"] for c in COMPONENTS.values()]
    print("A obter histórico semanal...")
    hist = fetch_weekly(symbols)

    print("A calcular RS-Ratio / RS-Momentum...")
    components = build_rrg(hist, BENCH["symbol"])

    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "methodology": {
            "timeframe": "weekly",
            "ratio_window_weeks": RATIO_WIN,
            "momentum_window_weeks": MOM_WIN,
            "trail_weeks": TRAIL_LEN,
            "note": "RS-Ratio e RS-Momentum normalizados em torno de 100 (estilo JdK simplificado). "
                    "Todos os componentes são proxies livres dos índices FTSE Russell do EQC_Global_RS_Monitor.pine — "
                    "ver proxy_note por componente.",
        },
        "benchmark": BENCH,
        "components": components,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print(f"\nGravado: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE)} bytes)")

    print("\nEstado actual por componente:")
    for c in components:
        cur = c["current"]
        print(f"  {c['label']:12s} x={cur['x']:6.2f} y={cur['y']:6.2f}  {cur['quadrant']}")

    if "--push" in sys.argv:
        git_push()


if __name__ == "__main__":
    main()
