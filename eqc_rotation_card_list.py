#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EQC Capital Rotation — LAYOUT C: lista/tabela agrupada por quadrante,
sem grafico XY nenhum. Cada linha = 1 indice, seta a mostrar a direccao
das ultimas 3 semanas, agrupado por LEADING/IMPROVING/WEAKENING/LAGGING.
"""

import json
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
CYAN      = (85, 200, 224)

SIZE_W, SIZE_H = 1080, 1350
EQC_WEBSITE = "www.eqc.investments"
FOLDER   = os.path.dirname(os.path.abspath(__file__))
DATAFILE = os.path.join(FOLDER, "data", "rs_rotation.json")
OUTDIR   = os.path.join(FOLDER, "assets", "cards")

QUAD_ORDER = [
    ("LEADING",   GREEN,     "lidera — força e a acelerar"),
    ("IMPROVING", CYAN,      "a recuperar força"),
    ("WEAKENING", GOLD,      "ainda forte, mas a perder fôlego"),
    ("LAGGING",   RED,       "fraco — sem força relativa"),
    ("NEUTRAL",   BLUE_GREY, "à volta da base — sem sinal claro"),
]


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


def centered_x(draw, text, font, y, color, w_total=SIZE_W):
    w = draw.textlength(text, font=font)
    draw.text(((w_total - w) / 2, y), text, fill=color, font=font)


def draw_line(draw, y, margin=60):
    draw.line([(margin, y), (SIZE_W - margin, y)], fill=DIVIDER, width=1)


def gold_bracket(draw, x, y, size=36, thick=2, flip_x=False, flip_y=False):
    sx = x + size if flip_x else x
    ex = x if flip_x else x + size
    draw.line([(sx, y), (ex, y)], fill=GOLD, width=thick)
    ax = x + size if flip_x else x
    sy = y + size if flip_y else y
    ey = y if flip_y else y + size
    draw.line([(ax, sy), (ax, ey)], fill=GOLD, width=thick)


def draw_direction_arrow(d, cx, cy, dx, dy, color, length=26, head=11):
    """Seta clara: haste + triangulo solido na ponta (nao depende de glifo)."""
    import math
    flat = abs(dx) < 1e-6 and abs(dy) < 1e-6
    ang = 0.0 if flat else math.atan2(-dy, dx)  # -dy: y cresce para baixo no ecran
    half = length / 2
    x0, y0 = cx - half * math.cos(ang), cy - half * math.sin(ang)
    x1, y1 = cx + half * math.cos(ang), cy + half * math.sin(ang)
    d.line([(x0, y0), (x1, y1)], fill=color, width=4)
    left_a  = ang + math.pi - 2.6
    right_a = ang + math.pi + 2.6
    tip = (x1 + 3 * math.cos(ang), y1 + 3 * math.sin(ang))
    p1 = (x1 + head * math.cos(left_a), y1 + head * math.sin(left_a))
    p2 = (x1 + head * math.cos(right_a), y1 + head * math.sin(right_a))
    d.polygon([tip, p1, p2], fill=color)


def compute_height(data: dict):
    components = data["components"]
    by_quad = {k: 0 for k, _, _ in QUAD_ORDER}
    for c in components:
        by_quad[c["current"]["quadrant"]] += 1
    h = 230  # header + margens
    for qkey, _, _ in QUAD_ORDER:
        n = by_quad.get(qkey, 0)
        if n == 0:
            continue
        h += 40 + n * 58 + 14
    h += 110  # footer
    return max(h, 500)


def generate(data: dict, output_path: str):
    size_h = compute_height(data)
    img = Image.new("RGB", (SIZE_W, size_h), BG)
    d = ImageDraw.Draw(img)

    m = 28
    gold_bracket(d, m, m)
    gold_bracket(d, SIZE_W - m - 36, m, flip_x=True)
    gold_bracket(d, m, size_h - m - 36, flip_y=True)
    gold_bracket(d, SIZE_W - m - 36, size_h - m - 36, flip_x=True, flip_y=True)

    y = 64
    centered_x(d, "EVOLUTION QUANTUM CAPITAL", f(POPPINS_LIGHT, 18), y, BLUE_GREY)
    y += 32
    centered_x(d, "CAPITAL ROTATION", f(POPPINS_MEDIUM, 26), y, GOLD)
    y += 34
    bench_label = data["benchmark"]["label"]
    centered_x(d, f"vs {bench_label}  ·  rotação semanal", f(POPPINS_LIGHT, 16), y, BLUE_GREY)
    y += 30
    draw_line(d, y)
    y += 26

    components = data["components"]
    by_quad = {k: [] for k, _, _ in QUAD_ORDER}
    for c in components:
        by_quad[c["current"]["quadrant"]].append(c)

    name_font  = f(POPPINS_MEDIUM, 24)
    sub_font   = f(POPPINS_LIGHT, 15)
    val_font   = f(MONO, 15)

    left = 90
    right = SIZE_W - 90

    for qkey, qcolor, qdesc in QUAD_ORDER:
        rows = by_quad.get(qkey, [])
        if not rows:
            continue
        # cabecalho do quadrante
        d.ellipse([left, y + 6, left + 10, y + 16], fill=qcolor)
        d.text((left + 22, y), qkey, fill=qcolor, font=f(POPPINS_MEDIUM, 20))
        d.text((left + 22 + d.textlength(qkey, font=f(POPPINS_MEDIUM, 20)) + 14, y + 3),
               qdesc, fill=BLUE_GREY, font=sub_font)
        y += 40

        for c in rows:
            color = tuple(int(c["color"][i:i+2], 16) for i in (1, 3, 5))
            trail3 = c["trail"][-3:]
            dx = trail3[-1]["x"] - trail3[0]["x"]
            dy = trail3[-1]["y"] - trail3[0]["y"]

            d.ellipse([left + 4, y + 6, left + 20, y + 22], fill=color)
            d.text((left + 34, y), c["label"], fill=WHITE, font=name_font)

            cur = c["current"]
            valtext = f"x {cur['x']:6.2f}   y {cur['y']:6.2f}"
            d.text((left + 34, y + 32), valtext, fill=BLUE_GREY, font=val_font)

            gcolor = GREEN if (dx >= 0 and dy >= 0) else (RED if (dx < 0 and dy < 0) else GOLD)
            arrow_cx, arrow_cy = right - 130, y + 18
            draw_direction_arrow(d, arrow_cx, arrow_cy, dx, dy, gcolor)
            d.text((right - 80, y + 8), f"{dx:+.1f} / {dy:+.1f}", fill=BLUE_GREY, font=val_font)

            y += 58

        y += 14

    y += 6
    draw_line(d, y)

    foot_y = size_h - 78
    fy = foot_y + 8
    centered_x(d, "RULE-BASED  ·  NON-DISCRETIONARY  ·  EQC", f(POPPINS_LIGHT, 15), fy, FOOTER)
    fy += 26
    centered_x(d, f"@EvolutionQC  ·  {EQC_WEBSITE}", f(MONO, 13), fy, FOOTER)

    img.save(output_path, "PNG")
    return output_path


if __name__ == "__main__":
    with open(DATAFILE, encoding="utf-8") as fh:
        data = json.load(fh)
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"rotation_list_{datetime.now().strftime('%Y-%m-%d')}.png")
    generate(data, out)
    print("saved:", out)
