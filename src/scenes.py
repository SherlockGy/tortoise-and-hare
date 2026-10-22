# 龟兔赛跑：分镜与动作编排（所有动作以“幕内拍号”计时，与配乐、旁白同步）
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import skia

from engine import (FPS, H, W, Assets, Renderer, SCALE, clamp01, ease_back, ease_in, ease_io, ease_out, jump, kf,
                    lerp, rnd, seg)
from timeline import CUES, SCENES, TL, TOTAL, voice_spans

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
ORDER = [s[0] for s in SCENES]
SPANS = voice_spans()

# ---------------- 舞台参数 ----------------
GY = 905                 # 角色脚底地面
START_X = 700            # 起跑线
FINISH_X = 1500          # 终点线
TITLE_COLORS = [(72, 126, 80), (212, 82, 66), (206, 146, 42), (66, 126, 178)]

BG_START = dict(u=0.50, v=0.56, scale=1.32)
BG_FOREST = dict(u=0.50, v=0.57, scale=1.50)
BG_OAK = dict(u=0.32, v=0.57, scale=1.30)
BG_FINISH = dict(u=0.50, v=0.56, scale=1.34)
BG_SUNSET = dict(u=0.50, v=0.55, scale=1.30)

HARE_CYCLE = ("hare_run_a", "hare_run_b", "hare_stand")
HARE_SPRINT = ("hare_sprint", "hare_run_b", "hare_run_a")
TORTOISE_CYCLE = ("tortoise_walk_a", "tortoise_walk_b", "tortoise_stand")


# ---------------- 通用小工具 ----------------
def act_pt(R, pose, x, y, u, v, flip=False, scale_mul=1.0):
    w, h = R.A.size(pose)
    s = SCALE[pose.split("_")[0]] * scale_mul
    return x + (u - 0.5) * w * s * (-1 if flip else 1), y - (1 - v) * h * s


def pick(R, name, fallback):
    return name if name in R.A.img else fallback


def bg_point(R, u, v, uc, vc, scale, p=0.85):
    bw = W * scale
    bh = bw * 1024 / 1536
    sx, sy = R.to_screen(960 + (u - uc) * bw, 540 + (v - vc) * bh, p)
    cx, cy, z = R.cam
    return (sx - 960) / z + cx, (sy - 540) / z + cy


def set_cam(R, cam):
    t = R.frame / FPS
    cx, cy, z = cam
    R.cam = (cx + 5 * math.sin(t * 0.43) + 2.5 * math.sin(t * 1.13),
             cy + 4 * math.sin(t * 0.57 + 1), z * (1 + 0.004 * math.sin(t * 0.31)))


def clouds(R, t, ys=(112, 178, 78), speed=13, p=0.9):
    R.layer(p)
    for i, (n, y) in enumerate(zip(["cloud1", "cloud2", "cloud3"], ys)):
        if n not in R.A.img:
            continue
        x = (280 + i * 790 + speed * (1 + 0.4 * i) * t) % 2800 - 450
        R.sprite(n, x, y, 0.36 - 0.055 * i, anchor=(0.5, 0.5), shadow=0.10, boil=False, alpha=0.96)
    R.layer(1.0)


def fg(R, y=1125, h=270, p=1.16, offset=0.0, sway=1.0):
    # 前景草地条：轻微随风左右摆
    R.flush_fx()
    if "fg_grass" not in R.A.img:
        return
    R.layer(p)
    w, hh = R.A.size("fg_grass")
    sc = h / hh
    ww = w * sc
    x = -240 + offset + 6 * math.sin(R.frame / FPS * 1.2) * sway
    while x < W + 100:
        R.sprite("fg_grass", x, y, sc, anchor=(0, 1), shadow=0, boil=False)
        x += ww - 8
    R.layer(1.0)


def fg_flowers(R, y=1140, h=190, p=1.22, offset=0.0):
    if "fg_flowers" not in R.A.img:
        return
    R.layer(p)
    w, hh = R.A.size("fg_flowers")
    sc = h / hh
    ww = w * sc
    x = -300 + offset
    while x < W + 150:
        R.sprite("fg_flowers", x, y, sc, anchor=(0, 1), shadow=0, boil=False)
        x += ww - 10
    R.layer(1.0)


def talking(t, seed=0.0):
    return math.sin(t * 2.3 + seed) + 0.5 * math.sin(t * 0.9 + 1 + seed) > -0.45


def in_span(b, spans):
    return any(b0 <= b < b1 for b0, b1 in spans)


def sprite_h(R, name, height):
    return height / R.A.size(name)[1]


def qmark(R, x, y, b, b0, b1, size=110, color=(98, 168, 222), ch="？", seed=0):
    e = ease_back(seg(b, b0, b0 + 0.5), 2.2)
    a = 1 - seg(b, b1 - 0.4, b1)
    if e <= 0 or a <= 0:
        return
    t = R.frame / FPS
    R.record = False
    R.paper_text(ch, x, y - 14 * e + 6 * math.sin(t * 3 + seed), size, color, rot=8 * math.sin(t * 2.4 + seed),
                 scale=e, alpha=a)
    R.record = True


def burst_text(R, text, x, y, b, b0, b1, size=180, color=(224, 88, 78), rot=-5):
    e = ease_back(seg(b, b0, b0 + 0.35), 2.6)
    a = 1 - seg(b, b1 - 0.25, b1)
    if e <= 0.01 or a <= 0.01:
        return
    R.record = False
    R.paper_text(text, x, y + 10 * math.sin(b * 5), size, color, rot=rot, scale=e, alpha=a, stroke=size * 0.14)
    R.record = True


# ---------------- 行走与动作 ----------------
def walker(R, cyc, b, b0, b1, x0, x1, rate=1.0, h=24, y=GY, flip=None, tilt=3.0, lean=0.04, dust=True, yfun=None,
           step_cb=None, scale_mul=1.0, **kw):
    contact = cyc[2]
    a = pick(R, cyc[0], contact)
    bb = pick(R, cyc[1], a)
    if flip is None:
        flip = x1 < x0
    yf = yfun or (lambda _x: y)
    if b <= b0 or b >= b1:
        x = x0 if b <= b0 else x1
        R.actor(contact, x, yf(x), flip=flip, scale_mul=scale_mul, **kw)
        return x
    n = max(1, round((b1 - b0) * rate))
    ph = (b - b0) / (b1 - b0) * n
    k, f = int(ph), ph - int(ph)
    u = (k + ease_io(f)) / n
    x = lerp(x0, x1, u)
    s = math.sin(math.pi * f)
    land = max(0.0, 1 - f / 0.18) if k > 0 else 0.0
    pose = (a if k % 2 == 0 else bb) if 0.08 < f < 0.92 else contact
    R.actor(pose, x, yf(x), h * s, rot=tilt * math.sin(math.pi * ph) * 0.6 * (-1 if flip else 1),
            sx=1 - 0.03 * s + 0.06 * land, sy=1 + 0.05 * s - 0.07 * land, flip=flip, bend=lean,
            scale_mul=scale_mul, **kw)
    for j in (k, k - 1):
        if j < 1:
            continue
        tb = b0 + j * (b1 - b0) / n
        xj = lerp(x0, x1, j / n)
        if step_cb:
            step_cb(xj, tb, j)
        elif dust:
            R.puffs(xj, yf(xj) + 4, tb * R.spb, b * R.spb, n=3, seed=j * 7 + int(x0) % 97, life=0.55, rise=24,
                    spread=65, size=0.04, drift=-28 if not flip else 28, span=0.04, alpha=0.55)
    return x


def turn(R, pose, x, b, b0, b1, from_flip, y=GY, scale_mul=1.0, **kw):
    u = seg(b, b0, b1)
    R.actor(pose, x, y, 8 * math.sin(math.pi * u), sx=max(0.08, abs(1 - 2 * u)),
            flip=from_flip if u < 0.5 else not from_flip, scale_mul=scale_mul, **kw)


def hopper(R, air, ground, b, b0, b1, x, period=1.0, h=50, y=GY, flip=False, dust=True, scale_mul=1.0, **kw):
    if b < b0 or b >= b1:
        R.actor(ground, x, y, flip=flip, scale_mul=scale_mul, **kw)
        return
    f = ((b - b0) / period) % 1
    if f < 0.15:
        e = math.sin(math.pi * f / 0.15)
        R.actor(ground, x, y, sx=1 + 0.05 * e, sy=1 - 0.06 * e, flip=flip, scale_mul=scale_mul, **kw)
    elif f < 0.85:
        u = (f - 0.15) / 0.7
        st = 0.07 * (abs(math.cos(math.pi * u)) - 0.3)
        R.actor(air, x, y, h * math.sin(math.pi * u), sx=1 - st * 0.6, sy=1 + st, flip=flip, scale_mul=scale_mul, **kw)
    else:
        e = math.sin(math.pi * (f - 0.85) / 0.15)
        R.actor(ground, x, y, sx=1 + 0.06 * e, sy=1 - 0.07 * e, flip=flip, scale_mul=scale_mul, **kw)
        if dust:
            t0 = (b0 + (math.floor((b - b0) / period) + 0.85) * period) * R.spb
            R.puffs(x, y + 4, t0, b * R.spb, n=4, seed=int(b0 * 13 + x) % 211, life=0.5, rise=22, spread=100,
                    size=0.045, span=0.03, alpha=0.55)


def skid(R, pose, x, b, b0, y=GY, flip=False, scale_mul=1.0, **kw):
    d = b - b0
    e = math.exp(-max(0.0, d) * 3) * math.cos(max(0.0, d) * 9)
    R.actor(pose, x, y, rot=-7 * e * (-1 if flip else 1), sx=1 + 0.05 * e, sy=1 - 0.05 * e, flip=flip,
            bend=-0.08 * e, scale_mul=scale_mul, **kw)
    R.puffs(x + (60 if not flip else -60), y + 2, b0 * R.spb, b * R.spb, n=6, seed=int(b0 * 7), life=0.8, rise=46,
            spread=150, size=0.06, drift=60 if not flip else -60, span=0.1, alpha=0.65)


def hare_actor(R, b, x, spans=(), base="hare_stand", talk="hare_talk", flip=False, y=GY, seed=0.0, scale_mul=1.0, **kw):
    t = R.frame / FPS
    pose = talk if (in_span(b, spans) and talking(t, seed)) else base
    R.actor(pose, x, y, flip=flip, bend=0.018 * math.sin(t * 2.6) * (-1 if flip else 1), scale_mul=scale_mul, **kw)


def tortoise_actor(R, b, x, spans=(), base="tortoise_stand", talk="tortoise_talk", flip=False, y=GY, seed=1.0,
                   scale_mul=1.0, **kw):
    t = R.frame / FPS
    pose = talk if (in_span(b, spans) and talking(t, seed)) else base
    R.actor(pose, x, y, flip=flip, bend=0.012 * math.sin(t * 1.7), scale_mul=scale_mul, **kw)


def owl_actor(R, b, x, y, spans=(), flip=True, scale_mul=1.0, wingup=None, cheer=None, **kw):
    t = R.frame / FPS
    if wingup is not None and b >= wingup and "owl_wingup" in R.A.img:
        R.actor("owl_wingup", x, y, flip=flip, rot=2 * math.sin(t * 2), scale_mul=scale_mul, **kw)
        return
    if cheer is not None and b >= cheer and "owl_cheer" in R.A.img:
        R.actor("owl_cheer", x, y, lift=10 * abs(math.sin(t * 5)), flip=flip, scale_mul=scale_mul, **kw)
        return
    pose = "owl_talk" if (in_span(b, spans) and talking(t, 3.0)) else "owl_stand"
    R.actor(pose, x, y, flip=flip, bend=0.012 * math.sin(t * 1.4), scale_mul=scale_mul, **kw)


def spectator(R, name, x, y=GY, scale_mul=1.0, b=0.0, t=0.0, cheer=False, flip=False, phase=0.0, shadow=True):
    base = f"{name}_stand"
    air = f"{name}_cheer"
    pose = air if (cheer and air in R.A.img and math.sin(t * 5 + phase) > -0.2) else base
    bob = 5 * abs(math.sin(t * 3.4 + phase)) if cheer else 1.5 * math.sin(t * 1.2 + phase)
    R.actor(pose, x, y, lift=bob, flip=flip, scale_mul=scale_mul, shadow=shadow, rot=1.5 * math.sin(t * 2 + phase))


# ---------------- 赛道装置 ----------------
def checkered_col(R, x, y=GY, w=20, h=76, alpha=1.0):
    # 起跑线：一块竖立的红白格纸带（侧视时就是一条竖线）
    c = R.c
    n = 4
    for i in range(n):
        for j in range(2):
            col = (224, 88, 78) if (i + j) % 2 == 0 else (255, 250, 238)
            c.drawRect(skia.Rect.MakeXYWH(x - w / 2 + j * w / 2, y - h + i * h / n, w / 2, h / n),
                       skia.Paint(AntiAlias=True, Color=skia.Color(*col, int(245 * alpha))))


def wood_post(R, x, y0=GY, top=700, w=20):
    c = R.c
    c.drawRoundRect(skia.Rect.MakeXYWH(x - w / 2 + 4, top + 6, w, y0 - top), w / 2, w / 2,
                    skia.Paint(AntiAlias=True, Color=skia.Color(80, 50, 30, 60), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 6)))
    c.drawRoundRect(skia.Rect.MakeXYWH(x - w / 2, top, w, y0 - top), w / 2, w / 2,
                    skia.Paint(AntiAlias=True, Color=skia.Color(168, 118, 76)))
    c.drawRoundRect(skia.Rect.MakeXYWH(x - w / 2, top + 4, w * 0.28, y0 - top - 8), w * 0.14, w * 0.14,
                    skia.Paint(AntiAlias=True, Color=skia.Color(196, 148, 100, 180)))
    for k in range(3):
        yy = top + 60 + k * 58
        c.drawLine(x - w * 0.3, yy, x + w * 0.3, yy + 5, skia.Paint(AntiAlias=True, StrokeWidth=1.6,
                                                                   Color=skia.Color(130, 86, 52, 150)))
    c.drawRoundRect(skia.Rect.MakeXYWH(x - w * 0.7, top - 10, w * 1.4, 16), 7, 7,
                    skia.Paint(AntiAlias=True, Color=skia.Color(214, 176, 126)))


def gate(R, x, t=0.0, cut_t=None, label="终点", show_ribbon=True):
    left, right = x - 205, x + 205
    wood_post(R, left, top=540)
    wood_post(R, right, top=540)
    c = R.c
    c.drawCircle(left, 526, 9, skia.Paint(AntiAlias=True, Color=skia.Color(224, 88, 78)))
    c.drawCircle(right, 526, 9, skia.Paint(AntiAlias=True, Color=skia.Color(224, 88, 78)))
    # 吊牌：两根纸绳挂在门柱上
    R.record = False
    rope = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3.5,
                      Color=skia.Color(140, 100, 65, 230))
    c.drawLine(left, 540, x - 90, 488, rope)
    c.drawLine(right, 540, x + 90, 488, rope)
    R.paper_card(x, 445, 196, 82, a=1, color=(255, 249, 235), rot=-1.5)
    R.paper_text(label, x, 446, 46, (224, 88, 78), stroke=9, bold=4)
    R.record = True
    if show_ribbon:
        R.ribbon(left + 10, right - 10, 748, t=t, cut_t=cut_t)


def start_gate(R, x=START_X, t=0.0):
    checkered_col(R, x, h=84, w=22)
    # 起点牌：插在地上的一块小木牌
    sx = x
    wood_post(R, sx, top=742, w=14)
    R.record = False
    R.paper_card(sx, 716, 126, 58, a=1, color=(255, 249, 235), rot=1.2)
    R.paper_text("起点", sx, 717, 34, (104, 158, 104), stroke=6, bold=3)
    R.record = True


def finish_gate(R, x=FINISH_X, t=0.0, cut_t=None, show_ribbon=True):
    gate(R, x, t=t, cut_t=cut_t, label="终点", show_ribbon=show_ribbon)


def course_map(R, a):
    # 比赛路线小地图：起点的树 → 蜿蜒小路 → 终点的旗
    if a <= 0.01:
        return
    R.screen()
    R.record = False
    R.paper_card(960, 470, 1000, 390, a=a, color=(253, 247, 233), rot=-0.6)
    R.paper_text("比赛路线", 960, 330, 62, (105, 66, 42), stroke=10, alpha=a)
    c = R.c
    c.save()
    c.translate(960, 480)
    c.scale(0.92 + 0.08 * ease_back(a, 1.6), 0.92 + 0.08 * ease_back(a, 1.6))
    c.translate(-960, -480)
    p = skia.Path()
    p.moveTo(560, 560)
    p.cubicTo(720, 430, 860, 640, 1010, 515)
    p.cubicTo(1140, 410, 1260, 600, 1400, 500)
    c.drawPath(p, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=11,
                             Color=skia.Color(210, 180, 142, int(255 * a)),
                             PathEffect=skia.DashPathEffect.Make([16, 14], 0)))
    c.drawRect(skia.Rect.MakeXYWH(520, 540, 12, 52), skia.Paint(AntiAlias=True, Color=skia.Color(150, 105, 65, int(255 * a))))
    c.drawCircle(526, 530, 40, skia.Paint(AntiAlias=True, Color=skia.Color(120, 178, 116, int(255 * a))))
    c.drawCircle(500, 546, 26, skia.Paint(AntiAlias=True, Color=skia.Color(142, 194, 128, int(255 * a))))
    c.drawRect(skia.Rect.MakeXYWH(1390, 432, 8, 100), skia.Paint(AntiAlias=True, Color=skia.Color(150, 105, 65, int(255 * a))))
    fp = skia.Path()
    fp.moveTo(1398, 436)
    fp.lineTo(1470, 456)
    fp.lineTo(1398, 480)
    fp.close()
    c.drawPath(fp, skia.Paint(AntiAlias=True, Color=skia.Color(224, 88, 78, int(255 * a))))
    c.drawCircle(560, 560, 19, skia.Paint(AntiAlias=True, Color=skia.Color(232, 176, 96, int(255 * a))))
    c.drawCircle(1400, 500, 19, skia.Paint(AntiAlias=True, Color=skia.Color(116, 166, 108, int(255 * a))))
    R.paper_text("兔", 560, 559, 22, (255, 252, 244), stroke=0, alpha=a)
    R.paper_text("龟", 1400, 499, 22, (255, 252, 244), stroke=0, alpha=a)
    c.restore()
    R.paper_text("谁也不许抄近路", 960, 612, 34, (150, 105, 65), stroke=6, alpha=a * 0.95)
    R.record = True


def moral_cards(R, b, b0, b1, t):
    a = ease_io(seg(b, b0, b0 + 0.8)) * (1 - ease_io(seg(b, b1 - 0.8, b1)))
    if a <= 0.01:
        return
    R.screen()
    c = R.c
    # 一张铺满画面的绘本纸页，把实景压住，变成“讲道理”的一页
    c.drawRect(skia.Rect.MakeLTRB(-10, -10, W + 10, H + 10),
               skia.Paint(AntiAlias=True, Color=skia.Color(248, 239, 221, int(250 * a))))
    c.drawRoundRect(skia.Rect.MakeLTRB(70, 55, W - 70, H - 55), 34, 34,
                    skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3,
                               Color=skia.Color(210, 180, 142, int(180 * a)),
                               PathEffect=skia.DashPathEffect.Make([12, 9], 0)))
    for cx, actor, label, color, scl, sub in ((470, "hare_stand", "快", (224, 120, 92), 0.55, "跑得快"),
                                              (1450, "tortoise_stand", "不停", (104, 158, 104), 0.80, "一直走")):
        R.record = False
        R.paper_card(cx, 400, 620, 520, a=a, rot=-1.4 if cx < 960 else 1.4)
        R.paper_text(label, cx, 222, 96, color, stroke=14, bold=5, alpha=a)
        R.record = True
        R.actor(actor, cx, 620, scale_mul=scl, alpha=a, shadow=False, blink=False)
        R.record = False
        R.paper_text(sub, cx, 600, 44, (105, 66, 42), stroke=8, alpha=a)
        R.record = True


# ================= 片头 =================
def sc_title(R, b, t, S):
    C = CUES["title"]
    set_cam(R, kf(b, [(0, (760, 640, 1.24)), (6, (960, 650, 1.22)), (9, (1080, 640, 1.18)),
                      (12, (980, 610, 1.08)), (24, (980, 595, 1.03))]))
    R.bg("bg_start", **BG_START)
    clouds(R, t)
    R.bird(t, 1.2, 170)
    r0, r1 = C["run"]
    if b < r1:
        x = walker(R, HARE_CYCLE, b, r0, r1, 140, 1210, rate=2.3, h=30, lean=0.06)
        R.speed_lines(x - 90, GY - 250, t, direction=1, n=6, alpha=0.8, seed=3)
    else:
        R.actor("hare_stand", 1210, GY, flip=True, rot=1.5 * math.sin(t * 1.4))
    w0, w1 = C["walk"]
    if b >= w0:
        walker(R, TORTOISE_CYCLE, b, w0, min(w1, 20.0), 470, 760, rate=0.75, h=4, tilt=1.0, lean=0.01, dust=False)
    else:
        R.actor("tortoise_stand", 470, GY)
    fg(R, y=1130, h=215)
    R.screen()
    R.sun_rays(980, 205, 150, 520, n=18, alpha=0.30, rot=t * 0.12)
    for i, ch in enumerate("龟兔赛跑"):
        e = ease_back(seg(b, -0.6 + i * 0.36, 0.3 + i * 0.36), 2.4)
        if e <= 0:
            continue
        R.paper_text(ch, 980 + (i - 1.5) * 210, 190 + 8 * math.sin(t * 2.1 + i * 1.3), 180, TITLE_COLORS[i],
                     stroke=14, bold=9, rot=[-6, 4, -4, 6][i] * (0.4 + 0.6 * (1 - e)) + 2 * math.sin(t * 1.6 + i), scale=e)
    sub = ease_back(seg(b, 4.0, 5.0), 2.0)
    if sub > 0:
        R.paper_text("根据伊索寓言改编", 760, 345, 40, (120, 92, 66), stroke=5, bold=2, scale=sub, alpha=0.92)
    vs = ease_back(seg(b, C["vs"], C["vs"] + 0.5), 2.4)
    if vs > 0:
        R.paper_text("VS", 985, 600 + 6 * math.sin(t * 3), 105, (224, 88, 78), rot=-6, scale=vs, stroke=10, bold=5)


# ================= 相遇 =================
def sc_meet(R, b, t, S):
    C = CUES["meet"]
    set_cam(R, kf(b, [(0, (1030, 630, 1.12)), (8, (980, 640, 1.18)), (18, (900, 660, 1.28)),
                      (28, (980, 640, 1.22)), (40, (1220, 620, 1.12))]))
    R.bg("bg_start", **BG_START)
    clouds(R, t)
    R.bird(t, 2.0, 190)
    R.butterfly("butterfly", t, 1500, 560, ax=130, ay=32, ph=0.6, scale=0.20)

    for k, (nm, x, ph, sc) in enumerate((("mouse", 1360, 0.0, 0.85), ("hedgehog", 1480, 2.1, 1.0), ("fox", 1620, 4.2, 1.0))):
        if b >= 12 + k * 2.5:
            spectator(R, nm, x, y=GY - 20, scale_mul=sc, t=t, cheer=False, flip=False, phase=ph)

    w0, w1 = C["walk"]
    if b < w1:
        walker(R, TORTOISE_CYCLE, b, w0, w1, 470, 800, rate=0.62, h=3, tilt=0.8, lean=0.01, dust=False)
    else:
        R.actor("tortoise_stand", 800, GY)

    h0, h1 = C["hop"]
    if b < 4.0:
        R.actor("hare_stand", 1220, GY, flip=True, rot=2 * math.sin(t * 1.4))
    elif b < h1:
        hopper(R, "hare_cheer", "hare_stand", b, h0, h1, 1130, period=2.0, h=42, flip=True)
    elif b < C["taunt"]:
        walker(R, HARE_CYCLE, b, h1, C["taunt"], 1130, 980, rate=2.0, h=22, flip=True, dust=False)
    elif b < 20.6:
        R.actor("hare_taunt" if talking(t, 1.0) else "hare_talk", 980, GY, flip=True,
                bend=-0.06 - 0.02 * abs(math.sin(t * 4)), rot=-2 + 1.5 * math.sin(t * 5))
    elif b < C["look_up"]:
        R.actor("hare_talk", 980, GY, flip=True, bend=-0.03)
    else:
        R.actor("hare_talk", 980, GY, flip=True, bend=0.01)

    if b >= C["look_up"] and b < C["talk"] + 0.4:
        R.actor("tortoise_look_up", 800, GY, rot=-1.5)
    elif b >= C["talk"] and b < C["nod"]:
        tortoise_actor(R, b, 800, spans=[(C["talk"], C["nod"])], base="tortoise_look_up", talk="tortoise_talk")
    elif b >= C["nod"]:
        e = math.sin(math.pi * seg(b, C["nod"], C["nod"] + 1.2))
        R.actor("tortoise_nod" if e > 0.2 else "tortoise_determined", 800, GY, rot=1.5 * math.sin(t * 2))
    qmark(R, 1100, GY - 520, b, C["nod"], C["nod"] + 2.0, size=90, ch="？", color=(98, 168, 222))
    fg(R, y=1130, h=225)


# ================= 集合、宣布规则 =================
def sc_challenge(R, b, t, S):
    C = CUES["challenge"]
    set_cam(R, kf(b, [(0, (920, 620, 1.12)), (9, (780, 650, 1.18)), (16.6, (960, 640, 1.14)),
                      (27, (960, 650, 1.16)), (36, (940, 670, 1.30))]))
    R.bg("bg_start", **BG_START)
    clouds(R, t)
    R.bird(t, 3.0, 160)
    start_gate(R, START_X, t)
    st = sprite_h(R, "tree_stump", 150) if "tree_stump" in R.A.img else 0
    if st:
        R.sprite("tree_stump", 400, GY + 4, st, shadow=0.25)
    owl_y = GY - 146 if st else GY
    owl_actor(R, b, 400, owl_y, spans=[(9.0, 15.8), (27.0, 30.0)], flip=True, wingup=C["wingup"], scale_mul=0.95)
    for k, (nm, x, ph, sc) in enumerate((("mouse", 1290, 0.0, 0.9), ("fox", 1430, 1.6, 0.95),
                                         ("hedgehog", 1580, 3.2, 0.9))):
        appear = C["gather"][0] + k * 0.9
        if b >= appear:
            u = ease_back(seg(b, appear, appear + 0.6), 1.8)
            spectator(R, nm, lerp(x + 160, x, u), y=GY - 8, scale_mul=sc * u, t=t, cheer=False, phase=ph)
    if "bird_fly" in R.A.img:
        R.sprite("bird_fly", 1030, 430, 0.10, sy=0.6 + 0.4 * abs(math.cos(t * 7)), anchor=(0.5, 1), shadow=0.1, boil=False)

    tortoise_actor(R, b, 800, spans=[], base="tortoise_determined", flip=False, scale_mul=1.0)
    if b < 27:
        hare_actor(R, b, 1100, spans=[], base="hare_stand", flip=True)
    else:
        e = ease_io(seg(b, 27, 29.5))
        R.actor("hare_stand", 1100, GY, flip=True, sy=1 - 0.08 * e, sx=1 + 0.04 * e, bend=0.10 * e)
    fg(R, y=1135, h=210)
    course_map(R, ease_io(seg(b, 16.6, 17.6)) * (1 - ease_io(seg(b, 25.4, 26.2))))
    if b >= 27:
        R.screen()
        p = 1 - seg(b, 27, 33)
        if p > 0:
            R.c.drawRect(skia.Rect.MakeLTRB(0, 0, W, H), skia.Paint(Color=skia.Color(30, 24, 20, int(70 * p))))


# ================= 起跑 =================
def sc_start(R, b, t, S):
    C = CUES["start"]
    set_cam(R, kf(b, [(0, (420, 790, 2.15)), (3.0, (440, 780, 2.05)), (4.2, (760, 690, 1.35)),
                      (6.5, (980, 660, 1.20)), (16, (1160, 650, 1.15))], ease=ease_io))
    R.bg("bg_start", **BG_START)
    clouds(R, t)
    start_gate(R, START_X, t)
    st = sprite_h(R, "tree_stump", 150) if "tree_stump" in R.A.img else 0
    if st:
        R.sprite("tree_stump", 400, GY + 4, st, shadow=0.25)
    owl_y = GY - 146 if st else GY
    owl_actor(R, b, 400, owl_y, spans=[], flip=True, wingup=0.0, scale_mul=0.95)

    if b < 4.2:
        R.actor("tortoise_stand", 640, GY, rot=0.6)
        R.actor("hare_stand", 860, GY, flip=True, sy=0.94 + 0.01 * math.sin(t * 18), sx=1.03, bend=0.06)
    else:
        x = walker(R, HARE_SPRINT, b, 4.2, 13.5, 860, 2400, rate=2.4, h=34, lean=0.08, dust=True)
        R.speed_lines(x - 80, GY - 270, t, direction=1, n=8, alpha=0.9, seed=6)
        walker(R, TORTOISE_CYCLE, b, 4.2, 16, 640, 900, rate=0.9, h=4, tilt=1.0, lean=0.01, dust=False)
    burst_text(R, "跑！", 960, 420, b, 3.9, 6.2, size=210, color=(224, 88, 78), rot=-8)
    fg(R, y=1130, h=210)


# ================= 一骑绝尘 =================
def sc_sprint(R, b, t, S):
    C = CUES["sprint"]
    set_cam(R, kf(b, [(0, (700, 650, 1.16)), (3, (1150, 650, 1.16)), (6, (1500, 650, 1.14)),
                      (9, (1580, 650, 1.12)), (9.7, (1250, 700, 1.55)), (18, (900, 680, 1.30)),
                      (24, (1300, 660, 1.22)), (32, (1250, 650, 1.12))]))
    R.bg("bg_forest", **BG_FOREST)
    clouds(R, t)
    R.bird(t, 2.0, 160)
    if b < 9.0:
        x = walker(R, HARE_SPRINT, b, 0, 9.0, 620, 1700, rate=2.3, h=34, lean=0.08)
        R.speed_lines(x - 80, GY - 260, t, direction=1, n=9, alpha=0.9, seed=11)
    elif b < 18.9:
        walker(R, TORTOISE_CYCLE, b, 9.0, 18.9, 620, 820, rate=0.65, h=3, tilt=0.8, lean=0.01, dust=False)
        if b > 12:
            R.sweat(*act_pt(R, "tortoise_stand", 810, GY, 0.85, 0.55), t, seed=3)
        R.actor("tortoise_stand", 380, GY, scale_mul=0.55)
    elif b < 27:
        R.actor("hare_taunt", 1370, GY, flip=True, rot=2 * math.sin(t * 3), bend=-0.03)
        R.progress(0.86, 0.10, alpha=ease_io(seg(b, 18.9, 19.6)) * (1 - seg(b, 26, 27)), t=t)
        qmark(R, 1170, GY - 470, b, 19.2, 24.5, size=84, ch="慢", color=(224, 168, 64))
        R.actor("tortoise_stand", 820, GY)
    else:
        walker(R, HARE_SPRINT, b, 27, 31, 1370, 2350, rate=2.2, h=28, lean=0.08)
        walker(R, TORTOISE_CYCLE, b, 27, 32, 820, 880, rate=0.65, h=3, tilt=0.8, lean=0.01, dust=False)
        R.progress(0.93, 0.13, alpha=1 - seg(b, 30.5, 32), t=t)
    fg(R, y=1135, h=220)


# ================= 得意忘形 =================
def sc_taunt(R, b, t, S):
    C = CUES["taunt"]
    set_cam(R, kf(b, [(0, (800, 670, 1.20)), (6, (950, 690, 1.30)), (10.5, (1000, 710, 1.35)),
                      (17, (1050, 720, 1.40)), (24, (1060, 730, 1.42))]))
    R.bg("bg_oak", **BG_OAK)
    clouds(R, t)
    R.bird(t, 5.0, 150)
    R.butterfly("butterfly", t, 700, 520, ax=90, ay=24, ph=1.0, scale=0.16)
    # 远处慢慢爬的乌龟
    if b > 17.2:
        R.actor("tortoise_walk_a" if int(t * 2) % 2 else "tortoise_walk_b", 450 + 5 * math.sin(t), GY - 45,
                scale_mul=0.35, flip=False)
    else:
        R.actor("tortoise_stand", 450, GY - 45, scale_mul=0.35, flip=False)
    # 野餐毯先铺在树下
    if "blanket" in R.A.img:
        R.sprite("blanket", 1080, GY + 2, sprite_h(R, "blanket", 260), rot=-3, anchor=(0.5, 0.7), shadow=0.25)
    if b < C["stop"]:
        walker(R, HARE_CYCLE, b, 0, C["stop"], 800, 1050, rate=2.0, h=26, lean=0.05)
    elif b < 4.0:
        skid(R, "hare_stand", 1050, b, C["stop"])
    elif b < C["lie"]:
        R.actor("hare_taunt" if talking(t, 1.0) else "hare_talk", 1050, GY, flip=False,
                bend=-0.04, rot=1.8 * math.sin(t * 2.2))
    else:
        # 往毯子上一躺
        if b < C["lie"] + 1.2:
            R.puffs(1060, GY - 20, C["lie"] * R.spb, b * R.spb, n=5, seed=9, life=0.7, rise=40, spread=160,
                    size=0.06, span=0.06, alpha=0.6)
        if "hare_lie" in R.A.img:
            R.sprite("hare_lie", 1060, GY - 2, sprite_h(R, "hare_lie", 178), anchor=(0.5, 1.0), shadow=0.28,
                     boil=True, rot=-1 + 0.4 * math.sin(t * 1.4))
        else:
            R.actor("hare_sleep", 1010, GY, rot=74, scale_mul=0.74, shadow=False)
        # 啃胡萝卜：一根慢慢变短的胡萝卜
        if "carrot" in R.A.img and b < 18.5:
            bite = max(0.45, 1 - 0.06 * max(0, b - 10.5))
            R.sprite("carrot", 985, GY - 72, sprite_h(R, "carrot", 72) * bite, anchor=(0.5, 0.5), rot=108,
                     shadow=0.1, boil=False)
        if 12.5 <= b < 18:
            a = ease_io(seg(b, 12.5, 13.2)) * (1 - ease_io(seg(b, 17.2, 18)))
            R.record = False
            R.paper_card(1350, 470, 260, 190, a=a, rot=4)
            R.sprite("trophy", 1350, 527, sprite_h(R, "trophy", 100), anchor=(0.5, 0.5), shadow=0.15, boil=False, alpha=a)
            R.paper_text("第一？", 1350, 585, 30, (150, 105, 65), stroke=5, alpha=a)
            R.record = True
        R.zzz(830, GY - 150, b, 17.5, 24)
    if "basket" in R.A.img:
        R.sprite("basket", 1260, GY + 6, sprite_h(R, "basket", 120), rot=-2, shadow=0.2)
    fg(R, y=1130, h=225)


# ================= 午睡 =================
def sc_nap(R, b, t, S):
    C = CUES["nap"]
    set_cam(R, kf(b, [(0, (900, 710, 1.32)), (6.9, (960, 715, 1.40)), (13, (1000, 720, 1.45)),
                      (19.2, (1000, 700, 1.38)), (26, (1100, 700, 1.32)), (32, (1250, 690, 1.22))]))
    R.bg("bg_oak", **BG_OAK)
    clouds(R, t, speed=9)
    R.bird(t, 6.0, 150)
    R.leaves(900, 260, 4 * R.spb, t, n=7, seed=4, life=5.0, speed=200, scale=0.055, span=12)
    if "blanket" in R.A.img:
        R.sprite("blanket", 1080, GY + 4, sprite_h(R, "blanket", 300), rot=-3, anchor=(0.5, 0.7), shadow=0.25)
    # 侧躺的兔子：优先使用专门生成的躺姿，否则用躺倒的睡姿图
    if "hare_lie" in R.A.img:
        R.sprite("hare_lie", 1070, GY - 2, sprite_h(R, "hare_lie", 178), anchor=(0.5, 1.0), shadow=0.28, boil=True,
                 sy=1 + 0.008 * math.sin(t * 2.2))
        head_x, head_y = 830, GY - 90
    else:
        R.actor("hare_sleep", 1010, GY, rot=74, scale_mul=0.74, shadow=False)
        head_x, head_y = 900, GY - 110
    if b >= C["snore"]:
        # 鼻子边的小纸泡，表示打呼
        u = (b - C["snore"]) % 3.2 / 3.2
        a = math.sin(math.pi * u) * 0.85
        R.record = False
        R.paper_card(920 - 20 * u, head_y - 70 - 60 * u, 34 + 26 * u, 24 + 16 * u, a=a, color=(214, 236, 246), rot=8)
        R.record = True
    R.zzz(head_x, head_y + 20, b, 2.0, 30, alpha=1.0)
    if 9.5 <= b < 14.5:
        R.butterfly("butterfly", t, 920, head_y - 40, ax=10, ay=4, ph=0.2, scale=0.15)
    o0, o1 = C["overtake"]
    if b >= o0:
        walker(R, TORTOISE_CYCLE, b, o0, o1, 200, 1250, rate=0.7, h=3, tilt=0.8, lean=0.01, dust=False)
    fg(R, y=1135, h=215)
    if 8 < b < 18 and "trophy" in R.A.img:
        a = ease_io(seg(b, 8, 8.8)) * (1 - ease_io(seg(b, 17.2, 18)))
        if a > 0:
            R.record = False
            R.paper_card(980, 360, 230, 175, a=a, rot=-4)
            R.sprite("trophy", 980, 420, sprite_h(R, "trophy", 90), anchor=(0.5, 0.5), shadow=0.15, boil=False, alpha=a)
            R.record = True


# ================= 超越 =================
def sc_pass(R, b, t, S):
    C = CUES["pass"]
    set_cam(R, kf(b, [(0, (500, 780, 1.55)), (7, (800, 790, 1.55)), (15.8, (1180, 770, 1.38)),
                      (21, (1450, 740, 1.25)), (24, (1550, 720, 1.18))]))
    R.bg("bg_forest", **BG_FOREST)
    clouds(R, t)
    R.bird(t, 9.0, 150)
    if b > 4:
        spectator(R, "mouse", 330, y=GY - 10, scale_mul=0.8, t=t, cheer=False, phase=0.3)
    if b > 8:
        spectator(R, "hedgehog", 1710, y=GY - 10, scale_mul=0.85, t=t, cheer=False, phase=1.2)
    if b > 11:
        spectator(R, "fox", 250, y=GY - 10, scale_mul=0.9, t=t, cheer=False, phase=2.0, flip=True)
    x = walker(R, TORTOISE_CYCLE, b, 0, C["exit"], 520, 1600, rate=0.72, h=3, tilt=0.8, lean=0.01, dust=False,
               step_cb=lambda xj, tb, j: R.prints(xj - 100, xj, GY + 4, t, alpha=0.5, n=3))
    if b > 7:
        R.sweat(*act_pt(R, "tortoise_stand", x, GY, 0.86, 0.55), t, seed=7)
    if b >= C["cheer"]:
        R.actor("mouse_cheer", 330, GY - 10, scale_mul=0.8, lift=10 * abs(math.sin(t * 5)))
        R.actor("hedgehog_cheer", 1710, GY - 10, scale_mul=0.85, lift=8 * abs(math.sin(t * 4.5)))
        R.actor("fox_cheer", 250, GY - 10, scale_mul=0.9, lift=10 * abs(math.sin(t * 4.0)), flip=True)
    fg(R, y=1130, h=220)
    if b > 18:
        R.screen()
        R.record = False
        R.paper_text("终点在前", 960, 140, 40, (255, 252, 244), stroke=7, alpha=0.9 * seg(b, 18, 19))
        R.record = True


# ================= 惊醒 =================
def sc_wake(R, b, t, S):
    C = CUES["wake"]
    set_cam(R, kf(b, [(0, (950, 710, 1.4)), (4, (980, 710, 1.38)), (8, (980, 700, 1.35)),
                      (10, (1000, 690, 1.32)), (11, (1660, 700, 1.12)), (14, (1500, 690, 1.18)),
                      (18, (1100, 680, 1.3)), (24, (1050, 660, 1.2)), (32, (1700, 650, 1.1))]))
    R.bg("bg_oak", **BG_OAK)
    clouds(R, t)
    if "finish_banner" in R.A.img:
        R.sprite("finish_banner", 1740, 880, 0.22, anchor=(0.5, 1), shadow=0.15)
    R.actor("tortoise_stand", 1670 + 30 * seg(b, 8, 32), 880, scale_mul=0.40, flip=False)
    if b < 8:
        if "hare_lie" in R.A.img:
            R.sprite("hare_lie", 1070, GY - 2, sprite_h(R, "hare_lie", 178), anchor=(0.5, 1.0), shadow=0.28, boil=True)
        else:
            R.actor("hare_sleep", 1010, GY, rot=74, scale_mul=0.74, shadow=False)
        R.zzz(820, GY - 170, b, 0.5, 7)
    elif b < 10:
        e = math.sin(math.pi * seg(b, 8, 10))
        R.actor("hare_sleep", 1010, GY, rot=74 - 30 * e, sy=1 + 0.10 * e, sx=1 - 0.04 * e, scale_mul=0.74, shadow=False)
        R.zzz(900, GY - 150, b, 0.5, 7, alpha=1 - e)
    elif b < 11:
        R.actor("hare_wake", 1050, GY, scale_mul=1.0)
    elif b < 18:
        R.actor("hare_wake", 1050, GY, lift=8 * abs(math.sin(t * 10)), rot=3 * math.sin(t * 12))
        qmark(R, 1170, GY - 540, b, 11.2, 18, size=120, ch="！", color=(224, 88, 78))
        R.sweat(*act_pt(R, "hare_wake", 1050, GY, 0.86, 0.52), t, seed=11)
    else:
        if b < C["bolt"]:
            R.actor("hare_wake", 1050, GY, lift=6 * abs(math.sin(t * 8)), rot=2 * math.sin(t * 10))
            qmark(R, 1150, GY - 520, b, 18.2, 23.5, size=86, ch="！", color=(224, 88, 78))
        else:
            x = walker(R, HARE_SPRINT, b, C["bolt"], 32, 1050, 2350, rate=2.4, h=30, lean=0.09)
            R.speed_lines(x - 90, GY - 250, t, direction=1, n=8, alpha=0.9, seed=17)
    fg(R, y=1135, h=215)


# ================= 追赶 =================
def sc_chase(R, b, t, S):
    C = CUES["chase"]
    set_cam(R, kf(b, [(0, (700, 660, 1.08)), (5, (900, 660, 1.06)), (11, (1150, 700, 1.24)),
                      (17, (1200, 700, 1.26)), (21.8, (1100, 680, 1.20)), (28, (1250, 700, 1.24)),
                      (36, (1400, 710, 1.34))]))
    R.bg("bg_forest", **BG_FOREST)
    clouds(R, t, speed=20)
    R.bird(t, 3.0, 160)
    R.bird(t, 5.0, 240)
    if b > 20:
        finish_gate(R, FINISH_X, t=t, cut_t=None)
    tx = lerp(1280, 1460, seg(b, 11, 30))
    if b < 11:
        walker(R, TORTOISE_CYCLE, b, 0, 11, 1280, 1300, rate=0.7, h=3, tilt=0.8, lean=0.01, dust=False)
    elif b < 21.8:
        if b < 17 and "tortoise_look_back" in R.A.img:
            R.actor("tortoise_look_back", tx, GY, rot=-1.5)
        else:
            R.actor("tortoise_determined", tx, GY, rot=1.0)
        R.sweat(*act_pt(R, "tortoise_stand", tx, GY, 0.86, 0.55), t, seed=11)
    else:
        walker(R, TORTOISE_CYCLE, b, 21.8, 35.5, tx, 1470, rate=0.9, h=4, tilt=0.8, lean=0.01, dust=False)
    if b < 12:
        x = walker(R, HARE_SPRINT, b, 0, 12, 300, 800, rate=2.5, h=32, lean=0.09)
        R.speed_lines(x - 90, GY - 260, t, direction=1, n=10, alpha=0.9, seed=21)
    elif b < 21.8:
        x = lerp(800, 900, seg(b, 12, 21.8))
        R.actor("hare_sprint" if "hare_sprint" in R.A.img else "hare_run_a", x, GY, bend=0.09)
        R.speed_lines(x - 90, GY - 260, t, direction=1, n=5, alpha=0.55, seed=22)
    else:
        x = walker(R, HARE_SPRINT, b, 21.8, 35.5, 900, 1150, rate=2.6, h=30, lean=0.09)
        R.speed_lines(x - 90, GY - 260, t, direction=1, n=10, alpha=0.9, seed=23)
    if 4 < b < 34:
        ha = 0.55 + 0.18 * seg(b, 4, 30)
        ta = 0.78 + 0.14 * seg(b, 4, 30)
        R.progress(ha, ta, alpha=ease_io(seg(b, 4, 5)) * (1 - seg(b, 33, 34)), t=t)
    fg(R, y=1130, h=225)


# ================= 冲线 =================
def sc_finish(R, b, t, S):
    C = CUES["finish"]
    set_cam(R, kf(b, [(0, (1200, 680, 1.30)), (6.5, (1450, 730, 1.46)), (10, (1400, 700, 1.36)),
                      (15, (1300, 670, 1.22)), (23, (1200, 670, 1.20)), (30, (1400, 660, 1.14)),
                      (40, (1450, 640, 1.06))]))
    R.bg("bg_finish", **BG_FINISH)
    clouds(R, t)
    R.bird(t, 2.0, 170)
    finish_gate(R, FINISH_X, t=t, show_ribbon=False)
    for k, (nm, x, ph) in enumerate((("mouse", 1640, 0.2), ("fox", 1800, 1.4), ("hedgehog", 1910, 2.7))):
        spectator(R, nm, x, y=GY - 6, scale_mul=0.8, t=t, cheer=b > C["cut"], phase=ph)
    st = sprite_h(R, "tree_stump", 150) if "tree_stump" in R.A.img else 0
    if st:
        R.sprite("tree_stump", 640, GY + 4, st, shadow=0.25)
    owl_y = GY - 146 if st else GY
    owl_actor(R, b, 640, owl_y, spans=[(C["trophy"], C["trophy"] + 4)], flip=True, cheer=C["cut"], scale_mul=0.9)
    if b > C["trophy"] and "trophy" in R.A.img:
        R.sprite("trophy", 780, GY - 120, sprite_h(R, "trophy", 120), anchor=(0.5, 1), shadow=0.2)
    if b < C["cross"]:
        walker(R, TORTOISE_CYCLE, b, 0, C["cross"], 1300, 1470, rate=0.8, h=3, tilt=0.6, lean=0.01, dust=False)
    elif b < C["cross"] + 1.0:
        R.actor("tortoise_cross", 1470, GY, rot=-2, sy=1 + 0.02 * math.sin(t * 10))
    else:
        R.actor("tortoise_cheer", 1540, GY, lift=16 * abs(math.sin(t * 4)), rot=2 * math.sin(t * 3))
    if b < C["arrive"]:
        walker(R, HARE_SPRINT, b, 14, C["arrive"], -260, 1180, rate=2.2, h=26, lean=0.08)
    elif b < C["arrive"] + 1.6:
        skid(R, "hare_stand", 1180, b, C["arrive"])
    else:
        R.actor("hare_sad", 1180, GY, sy=1 - 0.02 * math.sin(t * 8), bend=0.06)
        R.sweat(*act_pt(R, "hare_sad", 1180, GY, 0.82, 0.58), t, seed=13)
    R.ribbon(FINISH_X - 195, FINISH_X + 195, 748, t=t,
             cut_t=None if b < C["cut"] else C["cut"] * R.spb)
    fg(R, y=1130, h=215)
    if b >= C["cut"]:
        R.confetti(t, C["cut"] * R.spb, n=110, seed=5, life=4.5)
    if b > C["trophy"] + 2 and b < 34:
        R.screen()
        R.record = False
        a = ease_io(seg(b, C["trophy"] + 2, C["trophy"] + 2.8)) * (1 - seg(b, 33, 34))
        R.paper_text("乌龟赢了！", 1470, 300, 78, (224, 88, 78), stroke=12, alpha=a, rot=-4)
        R.record = True


# ================= 道理 =================
def sc_moral(R, b, t, S):
    C = CUES["moral"]
    R.tint = [1.03, 0, 0, 0, 0.02, 0, 0.98, 0, 0, 0.0, 0, 0, 0.92, 0, 0, 0, 0, 0, 1, 0]
    set_cam(R, kf(b, [(0, (1250, 690, 1.30)), (8.6, (1300, 700, 1.38)), (17, (1280, 690, 1.34)),
                      (25.5, (960, 620, 1.06)), (31, (960, 590, 1.02)), (44, (960, 570, 0.98))]))
    R.bg("bg_finish", **BG_FINISH)
    clouds(R, t)
    for nm, x, ph in (("fox", 1840, 0.4), ("hedgehog", 1950, 2.0), ("mouse", 700, 1.0)):
        spectator(R, nm, x, y=GY - 6, scale_mul=0.75, t=t, cheer=False, phase=ph)
    if b < C["answer"]:
        R.actor("hare_sad", 1120, GY, flip=False, bend=0.05, rot=1.2 * math.sin(t * 1.4))
    elif b < C["nod"]:
        R.actor("hare_sad", 1120, GY, flip=False, bend=0.04)
    elif b < C["cards"]:
        e = math.sin(math.pi * seg(b, C["nod"], C["nod"] + 1.6))
        R.actor("hare_stand", 1120, GY, flip=False, bend=-0.03 * e, rot=1.5 * math.sin(t * 1.3))
    else:
        R.actor("hare_stand", 1120, GY, flip=False, rot=1.2 * math.sin(t * 1.2))
    if b < C["answer"]:
        R.actor("tortoise_stand", 1450, GY, flip=True)
    elif b < C["nod"]:
        tortoise_actor(R, b, 1450, spans=[(C["answer"], C["nod"])], base="tortoise_stand", talk="tortoise_talk", flip=True)
    else:
        R.actor("tortoise_nod", 1450, GY, flip=True)
    fg(R, y=1130, h=210)
    moral_cards(R, b, C["cards"], 40.5, t)
    if b > C["wide"]:
        R.screen()
        R.record = False
        a = ease_io(seg(b, C["wide"], C["wide"] + 1.0))
        c = R.c
        c.drawRoundRect(skia.Rect.MakeXYWH(360, 760, 1200, 54), 27, 27,
                        skia.Paint(AntiAlias=True, Color=skia.Color(255, 249, 235, int(235 * a))))
        p = skia.Path()
        p.moveTo(400, 787)
        p.lineTo(1520, 787)
        c.drawPath(p, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=4,
                                 Color=skia.Color(210, 180, 142, int(255 * a)),
                                 PathEffect=skia.DashPathEffect.Make([14, 11], 0)))
        c.drawCircle(400, 787, 16, skia.Paint(AntiAlias=True, Color=skia.Color(232, 176, 96, int(255 * a))))
        c.drawCircle(1520, 787, 16, skia.Paint(AntiAlias=True, Color=skia.Color(116, 166, 108, int(255 * a))))
        R.paper_text("不怕慢", 700, 787, 30, (105, 66, 42), stroke=0, alpha=a)
        R.paper_text("只怕站", 1180, 787, 30, (105, 66, 42), stroke=0, alpha=a)
        R.record = True


# ================= 圆舞曲结尾 =================
WARM = [1.04, 0, 0, 0, 0.03, 0, 0.97, 0, 0, 0.0, 0, 0, 0.88, 0, 0, 0, 0, 0, 1, 0]


def sc_finale(R, b, t, S):
    C = CUES["finale"]
    R.tint = WARM
    set_cam(R, kf(b, [(0, (1150, 620, 1.18)), (10, (1000, 600, 1.10)), (15, (920, 590, 1.08)),
                      (30, (960, 570, 1.02)), (60, (1050, 545, 0.96))]))
    R.bg("bg_sunset", **BG_SUNSET)
    R.fireflies(t, n=22, seed=3, alpha=ease_io(seg(b, 4, 20)), area=(0, 300, 1920, 850))
    R.leaves(700, 400, 2 * R.spb, t, n=6, seed=8, life=6.0, speed=120, scale=0.05, span=20)
    R.actor("hare_stand", 790, GY, flip=False, scale_mul=0.92, rot=1.2 * math.sin(t * 1.1))
    R.actor("tortoise_stand", 1000, GY, flip=False, scale_mul=0.92)
    g0, g1 = C["gather"]
    if b > g0:
        u = ease_out(seg(b, g0, g0 + 2))
        R.actor("fox_stand", lerp(1520, 1300, u), GY, flip=True, scale_mul=0.78)
        R.actor("mouse_stand", lerp(1640, 1480, u), GY, flip=True, scale_mul=0.82)
        R.actor("hedgehog_stand", lerp(1760, 1650, u), GY, flip=True, scale_mul=0.78)
    if b > g0 + 2:
        R.actor("owl_stand", 620, GY, flip=False, scale_mul=0.75)
    fg(R, y=1135, h=205)
    R.screen()
    c = R.c
    for i in range(14):
        ph = (t * 0.05 + i / 14) % 1
        x = 200 + 1600 * rnd(i, 4)
        y = 700 + 180 * math.sin(t * 0.4 + i)
        c.drawCircle(x, y, 2 + 2 * rnd(i, 5), skia.Paint(AntiAlias=True,
                                                        Color=skia.Color(255, 238, 180, int(70 * (0.5 + 0.5 * math.sin(ph * 6 + i))))))
    e = ease_back(seg(b, C["end_text"], C["end_text"] + 1.2), 2.2)
    if e > 0:
        R.paper_text("完", 960, 300 + 8 * math.sin(t * 2), 220, (246, 196, 82), rot=-4, scale=e, stroke=24)


# 幕名 "pass" 是 Python 关键字，用显式顺序表映射
SCENE_FUN = dict(zip(ORDER, [sc_title, sc_meet, sc_challenge, sc_start, sc_sprint, sc_taunt, sc_nap, sc_pass,
                             sc_wake, sc_chase, sc_finish, sc_moral, sc_finale]))
CUT_IN = set()
HALF = 0.32


def draw_scene(R, name, t):
    S = TL[name]
    lt = max(0.0, t - S["start"])
    b = lt * S["bpm"] / 60
    R.cam, R.shake, R.tint, R.wind = (960.0, 540.0, 1.0), (0.0, 0.0), None, 0.0
    R.spb = 60 / S["bpm"]
    R.scene_name = name
    SCENE_FUN[name](R, b, lt, S)


def scene_at(t):
    idx = 0
    for i, n in enumerate(ORDER):
        if TL[n]["start"] <= t:
            idx = i
    return idx


def draw_caption(R, t):
    if os.environ.get("CLEAN"):
        return
    R.tint = None
    for sp in SPANS:
        if sp["t0"] - 0.2 <= t <= sp["t1"] + 0.5:
            R.caption(sp["text"], t, sp["t0"] - 0.2, sp["t1"] + 0.5, 60.0)


def render_frame(R, f):
    t = f / FPS
    R.begin(f)
    i = scene_at(t)
    name = ORDER[i]
    start = TL[name]["start"]
    old = None
    if i > 0 and t - start < HALF and name not in CUT_IN:
        old, p = ORDER[i - 1], (t - (start - HALF)) / (2 * HALF)
    elif i + 1 < len(ORDER) and TL[ORDER[i + 1]]["start"] - t < HALF and ORDER[i + 1] not in CUT_IN:
        nxt = ORDER[i + 1]
        old, name, p = name, nxt, (t - (TL[nxt]["start"] - HALF)) / (2 * HALF)
    draw_scene(R, name, t)
    if old:
        xe = lerp(W + 80, -80, ease_io(p))
        c = R.c
        c.restoreToCount(1)
        c.save()
        clip = R.torn_clip(xe, seed=i)
        c.clipPath(clip, skia.ClipOp.kIntersect, True)
        R.base = c.getSaveCount()
        draw_scene(R, old, t)
        R.base = 1
        c.restoreToCount(1)
        c.save()
        edge = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=14,
                          Color=skia.Color(255, 251, 240), StrokeJoin=skia.Paint.kRound_Join)
        sh = skia.Paint(edge)
        sh.setColor(skia.Color(40, 25, 10, 90))
        sh.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 8))
        c.translate(6, 0)
        c.drawPath(clip, sh)
        c.translate(-6, 0)
        c.drawPath(clip, edge)
    draw_caption(R, t)
    fb = seg(t, TOTAL - 2.6, TOTAL - 0.8)
    R.post(fb)
    return R.arr


_R = None
LOG = "[render 视频渲染]"


def _init():
    global _R
    _R = Renderer(Assets())


def _render_range(args):
    k, f0, f1, path = args
    if _R is None:
        _init()
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-threads", "2", "-pix_fmt", "yuv420p", str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(render_frame(_R, f).tobytes())
    p.stdin.close()
    p.wait()
    return k


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    argv = sys.argv[1:]
    if argv and argv[0] == "still":
        _init()
        for s in argv[1:]:
            t = float(s)
            arr = render_frame(_R, int(round(t * FPS)))
            skia.Image.fromarray(arr.copy(), colorType=skia.kBGRA_8888_ColorType).save(str(OUT / f"still_{t:07.2f}.png"), skia.kPNG)
        return
    t0 = float(argv[0]) if len(argv) > 0 else 0.0
    t1 = float(argv[1]) if len(argv) > 1 else TOTAL
    workers = 6
    f0, f1 = int(t0 * FPS), int(t1 * FPS)
    segdir = OUT / "seg"
    segdir.mkdir(parents=True, exist_ok=True)
    for old in segdir.glob("seg_*.mp4"):
        old.unlink()
    n = max(1, min(workers * 3, (f1 - f0) // 24))
    bounds = [f0 + (f1 - f0) * i // n for i in range(n + 1)]
    jobs = [(i, bounds[i], bounds[i + 1], segdir / f"seg_{i:03d}.mp4") for i in range(n)]
    st = time.time()
    with ProcessPoolExecutor(workers, initializer=_init) as ex:
        for k in ex.map(_render_range, jobs):
            print(f"{LOG} 片段 {k + 1}/{n} 完成，用时 {time.time() - st:.0f}s", flush=True)
    lst = segdir / "list.txt"
    lst.write_text("".join(f"file '{j[3].as_posix()}'\n" for j in jobs), encoding="utf-8")
    out = OUT / ("tortoise_and_hare.mp4" if (t0 == 0 and t1 == TOTAL) else f"preview_{t0:.0f}_{t1:.0f}.mp4")
    music = OUT / "music.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-ss", f"{t0}",
                    "-i", str(music), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(f"{LOG} 输出 {out}")


if __name__ == "__main__":
    main()
