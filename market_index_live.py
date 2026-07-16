# =============================================================
#  EQC Market Index Live — recalcula os indicadores (US + Asia)
#  com o MESMO motor do Pine (modelo 4 pontos) e publica
#  data/market_index.json para o site (GitHub Pages).
#  Inclui SÉRIES HISTÓRICAS por TF (W/M/3M/6M/12M) para o gráfico.
#
#  Ficheiro: C:\EQC\market_index_live.py
#  Config:   C:\EQC\data\market_index_cycles.json  (anchors = inputs do TradingView)
#  Output:   C:\EQC\data\market_index.json
#
#  Uso:  python market_index_live.py            (calcula + grava)
#        python market_index_live.py --push     (calcula + grava + git commit/push)
# =============================================================

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

FOLDER      = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(FOLDER, "data", "market_index_cycles.json")
OUTPUT_FILE = os.path.join(FOLDER, "data", "market_index.json")

TFS = ["W", "M", "3M", "6M", "12M"]
RESAMPLE   = {"W": "W-FRI", "M": "ME", "3M": "QE", "6M": "6ME", "12M": "YE"}
SERIES_CAP = {"W": 1600, "M": 600, "3M": 240, "6M": 120, "12M": 60}

# Níveis de regime (iguais ao Pine)
LVL_MANIA, LVL_EUF, LVL_BULL, LVL_RECUP = 85, 70, 50, 30


# ─── MOTOR (port exacto do Pine score4 / fibScoreInv) ─────────────────────────
def score4(src, pS, pR, pM, pT, r_mania, r_extreme):
    """Modelo 4 pontos: Start(0) / Ref(50) / Mania(85) / Target(100).
    Devolve (score, status) com status em ASC / DESC / INVAL / NA."""
    if src is None or pS == pR or pS <= 0 or pR <= 0:
        return None, "NA"
    if pS < pR:  # ── ciclo ASCENDENTE ──
        if src < pS:
            return None, "INVAL"
        amp = pR - pS
        use3 = pT > 0 and pM <= 0
        fM = pM if pM > 0 else pS + amp * r_mania
        fE = pT if pT > 0 else pS + amp * r_extreme
        if src <= pR:
            sc = 50.0 * (src - pS) / (pR - pS)
        elif use3:
            sc = min(100.0, 50.0 + 50.0 * (src - pR) / (fE - pR))
        elif src <= fM:
            sc = 50.0 + 35.0 * (src - pR) / (fM - pR)
        elif src <= fE:
            sc = 85.0 + 15.0 * (src - fM) / (fE - fM)
        else:
            sc = 100.0
        return sc, "ASC"
    else:  # ── ciclo DESCENDENTE (Start acima, Ref abaixo) ──
        if src > pS:
            return None, "INVAL"
        amp = pS - pR
        use3 = pT > 0 and pM <= 0
        eM = pM if pM > 0 else pR - amp * (r_mania - 1.0)
        eE = pT if pT > 0 else pR - amp * (r_extreme - 1.0)
        if src >= pR:
            sc = 50.0 - 35.0 * (pS - src) / (pS - pR)
        elif use3:
            sc = max(0.0, 15.0 - 15.0 * (pR - src) / (pR - eE))
        elif src >= eM:
            sc = 15.0 - 10.0 * (pR - src) / (pR - eM)
        elif src >= eE:
            sc = 5.0 - 5.0 * (eM - src) / (eM - eE)
        else:
            sc = 0.0
        return sc, "DESC"


def fib_score_inv(src, fear, calm, r_mania, r_extreme):
    """VIX invertido (fixo, igual em todas as TFs)."""
    if src is None or fear == calm:
        return None
    amp = fear - calm
    fM = calm - amp * (r_mania - 1.0)
    fE = calm - amp * (r_extreme - 1.0)
    if src >= fear:
        return 0.0
    if src >= calm:
        return 50.0 * (fear - src) / (fear - calm)
    if src >= fM:
        return 50.0 + 35.0 * (calm - src) / (calm - fM)
    if src >= fE:
        return 85.0 + 15.0 * (fM - src) / (fE - fM)
    return 100.0


def regime_of(v):
    if v is None:
        return "NO DATA"
    if v >= LVL_MANIA:
        return "MANIA"
    if v >= LVL_EUF:
        return "EUPHORIA"
    if v >= LVL_BULL:
        return "HEALTHY BULL"
    if v >= LVL_RECUP:
        return "RECOVERY"
    return "BOTTOM / FEAR"


def comp_score(price, comp, tf, r_mania, r_extreme):
    """Score de um componente (tabela e séries usam o mesmo caminho)."""
    if comp.get("inverse"):
        sc = fib_score_inv(price, comp["fear"], comp["calm"], r_mania, r_extreme)
        return sc, ("INV" if sc is not None else "NA")
    s, r, m, t = comp["cycles"][tf]
    return score4(price, s, r, m, t, r_mania, r_extreme)


# ─── DADOS ────────────────────────────────────────────────────────────────────
def fetch_history(symbols):
    """Histórico máximo de fechos por símbolo (Series indexadas por data, sem tz)."""
    hist = {}
    for sym in sorted(set(symbols)):
        try:
            h = yf.Ticker(sym).history(period="max")["Close"].dropna()
            h.index = h.index.tz_localize(None)
            hist[sym] = h
            print(f"  [{sym}] {len(h)} barras desde {h.index[0].date()} | último {h.iloc[-1]:.2f}")
        except Exception as e:
            hist[sym] = None
            print(f"  [{sym}] ERRO: {e}")
    return hist


# ─── TABELA (valores actuais) ────────────────────────────────────────────────
def build_index(idx_cfg, prices, r_mania, r_extreme):
    out_tfs = {}
    for tf in TFS:
        comps, num, den = [], 0.0, 0.0
        for name, c in idx_cfg["components"].items():
            sc, st = comp_score(prices.get(c["symbol"]), c, tf, r_mania, r_extreme)
            if sc is not None:
                num += sc * c["weight"]
                den += c["weight"]
            comps.append({"name": name, "weight": c["weight"],
                          "score": round(sc, 1) if sc is not None else None,
                          "cycle": st})
        idx = round(num / den, 1) if den > 0 else None
        out_tfs[tf] = {"index": idx, "regime": regime_of(idx),
                       "valid": f"{sum(1 for c in comps if c['score'] is not None)}/{len(comps)}",
                       "components": comps}
    return {"name": idx_cfg["name"], "tfs": out_tfs}


# ─── SÉRIES HISTÓRICAS (para o gráfico) ──────────────────────────────────────
def build_series(cfg, hist, r_mania, r_extreme):
    keys = list(cfg["indices"].keys())
    out = {}
    for tf in TFS:
        res = {sym: (h.resample(RESAMPLE[tf]).last().dropna() if h is not None else None)
               for sym, h in hist.items()}
        all_dates = sorted(set().union(*[set(r.index) for r in res.values() if r is not None]))
        series = {"dates": [d.strftime("%Y-%m-%d") for d in all_dates]}
        for key in keys:
            idx_cfg = cfg["indices"][key]
            vals = []
            for d in all_dates:
                num = den = 0.0
                for c in idx_cfg["components"].values():
                    r = res.get(c["symbol"])
                    v = r.get(d) if r is not None else None
                    price = float(v) if v is not None and not pd.isna(v) else None
                    sc, _ = comp_score(price, c, tf, r_mania, r_extreme)
                    if sc is not None:
                        num += sc * c["weight"]
                        den += c["weight"]
                vals.append(round(num / den, 1) if den > 0 else None)
            series[key] = vals
        # corta o início sem dados e aplica o limite de pontos
        n = len(all_dates)
        first = next((i for i in range(n) if any(series[k][i] is not None for k in keys)), 0)
        start = max(first, n - SERIES_CAP[tf])
        out[tf] = {k: v[start:] for k, v in series.items()}
        print(f"  [série {tf}] {len(out[tf]['dates'])} pontos")
    return out


def git_push():
    try:
        rel = os.path.relpath(OUTPUT_FILE, FOLDER)
        subprocess.run(["git", "add", rel], cwd=FOLDER, check=True)
        r = subprocess.run(["git", "commit", "-m", "chore: update market index data"],
                           cwd=FOLDER, capture_output=True, text=True)
        if r.returncode != 0:
            print("  [git] nada para commitar" if "nothing to commit" in r.stdout + r.stderr else f"  [git] commit falhou: {r.stderr}")
            return
        subprocess.run(["git", "push"], cwd=FOLDER, check=True)
        print("  [git] push OK — site actualiza em ~1 min")
    except Exception as e:
        print(f"  [git] ERRO: {e}")


def main():
    print("=== EQC Market Index Live ===")
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    r_mania, r_extreme = cfg["ratios"]["mania"], cfg["ratios"]["extreme"]

    symbols = [c["symbol"] for idx in cfg["indices"].values() for c in idx["components"].values()]
    print("A obter histórico…")
    hist = fetch_history(symbols)
    prices = {sym: (float(h.iloc[-1]) if h is not None and len(h) else None)
              for sym, h in hist.items()}

    print("A construir séries…")
    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "levels": {"mania": LVL_MANIA, "euphoria": LVL_EUF, "bull": LVL_BULL, "recovery": LVL_RECUP},
        "indices": {key: build_index(idx, prices, r_mania, r_extreme)
                    for key, idx in cfg["indices"].items()},
        "series": build_series(cfg, hist, r_mania, r_extreme),
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Gravado: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE)//1024} KB)")

    for key, idx in result["indices"].items():
        w = idx["tfs"]["W"]
        print(f"  {idx['name']}: W={w['index']} ({w['regime']}, {w['valid']})")

    if "--push" in sys.argv:
        git_push()


if __name__ == "__main__":
    main()
