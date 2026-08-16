#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EQC Capital Rotation — LAYOUT B: snapshot + seta curta (1 semana), sem rasto
completo. Muito menos linhas cruzadas que a v1 (RRG classico com 10 semanas
de rasto) -- mostra so onde cada indice esta agora e para onde se moveu
na ultima semana.
"""

import json
import math
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

BG        = (5, 15, 30)
GOLD      = (201, 168, 76)
WHITE     = (255, 255, 255)
BLUE_GREY = (136, 153, 187)
GREEN     = (61, 186, 94)
RED       = (224, 82, 82)
DIVIDER   = (14, 32, 53)
FOOTER    = (102, 136, 170)

SIZE = 1080
EQC_WEBSITE = "www.eqc.investments"
FOLDER   = os.path.dirname(os.path.abspath(__file__))
DATAFILE = os.path.join(FOLDER, "data", "rs_rotation.json")
OUTDIR   = os.path.join(FOLDER, "assets", "cards")
ARROW_WEEKS = 2  # 2 pontos de rasto = 1 segmento = ultima semana (era 3 = 2 semanas)


def find_font(names):
    for d in ["C:/Windows/Fonts/", "/usr/share/fonts/truetype/google-fonts/",
              "/usr/share/fonts/truetype/liberation/", "/usr/share/fonts/truetype/dejavu/"]:
        for name in names:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None


POPPINS_BOLD   = find_font(["Poppins-Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"])
POPPINS_MEDIUM = find_font(["Poppins-Medium.ttf", "arial.ttf", "DejaVuSans.ttf"])
POPPINS_LIGHT  = find_font(["Poppins-Light.ttf", "arial.ttf", "DejaVuSans.ttf"])
MONO           = find_font(["LiberationMono-Regular.ttf", "cour.ttf", "DejaVuSansMono.ttf"])


def f(path, size):
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def centered_x(draw, text, font, y, color):
    w = draw.textlength(text, font=font)
    draw.text(((SIZE - w) / 2, y), text, fill=color, font=font)


def draw_line(draw, y, margin=60):
    draw.line([(margin, y), (SIZE - margin, y)], fill=DIVIDER, width=1)


def gold_bracket(draw, x, y, size=36, thick=2, flip_x=False, flip_y=False):
    sx = x + size if flip_x else x
    ex = x if flip_x else x + size
    draw.line([(sx, y), (ex, y)], fill=GOLD, width=thick)
    ax = x + size if flip_x else x
    sy = y + size if flip_y else y
    ey = y if flip_y else y + size
    draw.line([(ax, sy), (ax, ey)], fill=GOLD, width=thick)


def blend(bg, col, amt):
    return tuple(int(b + (c - b) * amt) for b, c in zip(bg, col))


def draw_arrowhead(d, x0, y0, x1, y1, color, size=13):
    """Triangulo solido na ponta — muito mais claro que duas linhas finas."""
    ang = math.atan2(y1 - y0, x1 - x0)
    left_a  = ang + math.pi - 2.6
    right_a = ang + math.pi + 2.6
    tip = (x1 + 3 * math.cos(ang), y1 + 3 * math.sin(ang))
    p1 = (x1 + size * math.cos(left_a), y1 + size * math.sin(left_a))
    p2 = (x1 + size * math.cos(right_a), y1 + size * math.sin(right_a))
    d.polygon([tip, p1, p2], fill=color)


def dashed_line(d, pts, color, width=2, dash=7, gap=6):
    """Desenha uma polilinha tracejada ao longo dos segmentos pts."""
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len < 1e-6:
            continue
        ux, uy = (x1 - x0) / seg_len, (y1 - y0) / seg_len
        pos = 0.0
        on = True
        while pos < seg_len:
            step = dash if on else gap
            nxt = min(pos + step, seg_len)
            if on:
                d.line([(x0 + ux * pos, y0 + uy * pos), (x0 + ux * nxt, y0 + uy * nxt)], fill=color, width=width)
            pos = nxt
            on = not on


def generate(data: dict, output_path: str):
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)

    m = 28
    gold_bracket(d, m, m)
    gold_bracket(d, SIZE - m - 36, m, flip_x=True)
    gold_bracket(d, m, SIZE - m - 36, flip_y=True)
    gold_bracket(d, SIZE - m - 36, SIZE - m - 36, flip_x=True, flip_y=True)

    y = 64
    centered_x(d, "EVOLUTION QUANTUM CAPITAL", f(POPPINS_LIGHT, 18), y, BLUE_GREY)
    y += 32
    centered_x(d, "CAPITAL ROTATION", f(POPPINS_MEDIUM, 26), y, GOLD)
    y += 34
    bench_label = data["benchmark"]["label"]
    weeks_shown = ARROW_WEEKS - 1
    week_label = "last week" if weeks_shown == 1 else f"last {weeks_shown} weeks"
    sub = f"vs {bench_label}  ·  current position  ·  arrow = {week_label}"
    centered_x(d, sub, f(POPPINS_LIGHT, 16), y, BLUE_GREY)
    y += 28
    draw_line(d, y)

    components = data["components"]
    AXIS_HALF = 12.0
    x_min, x_max = 100 - AXIS_HALF, 100 + AXIS_HALF
    y_min, y_max = 100 - AXIS_HALF, 100 + AXIS_HALF

    clipped = []
    for c in components:
        pts_raw = c["trail"][-ARROW_WEEKS:]
        xs = [p["x"] for p in pts_raw]; ys = [p["y"] for p in pts_raw]
        if min(xs) < x_min or max(xs) > x_max or min(ys) < y_min or max(ys) > y_max:
            clipped.append(c["label"])

    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    plot_top = y + 40
    plot_size = 700
    plot_left = (SIZE - plot_size) // 2
    plot_bottom = plot_top + plot_size
    plot_right = plot_left + plot_size

    def px(x): return plot_left + (x - x_min) / (x_max - x_min) * plot_size
    def py(v): return plot_bottom - (v - y_min) / (y_max - y_min) * plot_size

    cx100, cy100 = px(100), py(100)
    d.rectangle([cx100, plot_top, plot_right, cy100], fill=blend(BG, GREEN, 0.10))
    d.rectangle([cx100, cy100, plot_right, plot_bottom], fill=blend(BG, GOLD, 0.09))
    d.rectangle([plot_left, cy100, cx100, plot_bottom], fill=blend(BG, RED, 0.09))
    d.rectangle([plot_left, plot_top, cx100, cy100], fill=blend(BG, (85, 200, 224), 0.09))
    d.rectangle([plot_left, plot_top, plot_right, plot_bottom], outline=DIVIDER, width=1)
    d.line([(cx100, plot_top), (cx100, plot_bottom)], fill=GOLD, width=1)
    d.line([(plot_left, cy100), (plot_right, cy100)], fill=GOLD, width=1)

    qfont = f(POPPINS_LIGHT, 15)
    d.text((plot_right - 100, plot_top + 10), "LEADING", fill=blend(BLUE_GREY, GREEN, 0.6), font=qfont)
    d.text((plot_right - 118, plot_bottom - 28), "WEAKENING", fill=blend(BLUE_GREY, GOLD, 0.6), font=qfont)
    d.text((plot_left + 10, plot_bottom - 28), "LAGGING", fill=blend(BLUE_GREY, RED, 0.6), font=qfont)
    d.text((plot_left + 10, plot_top + 10), "IMPROVING", fill=blend(BLUE_GREY, (85, 200, 224), 0.6), font=qfont)

    label_font = f(POPPINS_MEDIUM, 16)
    placed = []

    def place_label(lx, ly, text, color):
        w = d.textlength(text, font=label_font)
        h = 18
        candidates = [(lx + 14, ly - h / 2), (lx + 14, ly - h - 12), (lx + 14, ly + 12),
                      (lx - w - 14, ly - h / 2), (lx + 14, ly - h - 26), (lx + 14, ly + 26)]
        for cxp, cyp in candidates:
            box = (cxp, cyp, cxp + w, cyp + h)
            if all(box[2] < ob[0] or box[0] > ob[2] or box[3] < ob[1] or box[1] > ob[3] for ob in placed):
                placed.append(box); d.text((cxp, cyp), text, fill=color, font=label_font); return
        cxp, cyp = candidates[-1]
        placed.append((cxp, cyp, cxp + w, cyp + h)); d.text((cxp, cyp), text, fill=color, font=label_font)

    for c in components:
        color = tuple(int(c["color"][i:i+2], 16) for i in (1, 3, 5))
        pts_raw = c["trail"][-ARROW_WEEKS:]
        pts = [(px(clamp(p["x"], x_min, x_max)), py(clamp(p["y"], y_min, y_max))) for p in pts_raw]
        if len(pts) >= 2:
            dashed_line(d, pts, color, width=2)
            draw_arrowhead(d, pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1], color)
        lx, ly = pts[-1]
        r = 7
        d.ellipse([lx - r, ly - r, lx + r, ly + r], fill=color, outline=WHITE, width=2)
        place_label(lx, ly, c["label"], color)

    y2 = plot_bottom + 22
    draw_line(d, y2)

    foot_y = SIZE - 96 if clipped else SIZE - 78
    fy = foot_y + 8
    if clipped:
        note = f"axis ±{AXIS_HALF:.0f} pts — out of range: {', '.join(clipped)}"
        centered_x(d, note, f(POPPINS_LIGHT, 13), fy, blend(BLUE_GREY, GOLD, 0.4))
        fy += 22
    centered_x(d, "RULE-BASED  ·  NON-DISCRETIONARY  ·  EQC", f(POPPINS_LIGHT, 15), fy, FOOTER)
    fy += 26
    centered_x(d, f"@EvolutionQC  ·  {EQC_WEBSITE}", f(MONO, 13), fy, FOOTER)

    img.save(output_path, "PNG")
    return output_path


if __name__ == "__main__":
    with open(DATAFILE, encoding="utf-8") as fh:
        data = json.load(fh)
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"rotation_graph_{datetime.now().strftime('%Y-%m-%d')}.png")
    generate(data, out)
    print("saved:", out)
