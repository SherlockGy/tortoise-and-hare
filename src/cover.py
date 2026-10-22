# 封面生成：用片中同一套纸艺素材合成横版（16:9）与竖版（9:16）封面
import math
import sys
from pathlib import Path

import numpy as np
import skia
from PIL import Image

from engine import BG_SAMP, CUT, FONT_TF, Assets, Renderer, SAMP

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
LOG = "[cover 封面生成]"
TITLE_COLORS = [(72, 126, 80), (212, 82, 66), (206, 146, 42), (66, 126, 178)]


class CoverCanvas:
    def __init__(self, R, w, h):
        self.R, self.w, self.h = R, w, h
        self.arr = np.zeros((h, w, 4), np.uint8)
        self.surface = skia.Surface(self.arr, colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
        R.c = self.surface.getCanvas()
        R.frame = 5
        R.tint = None
        R.cam = (960.0, 540.0, 1.0)
        R.space = None
        R.record = False
        R.c.clear(skia.Color(30, 24, 20))

    def bg(self, name, scale_w, cx_u, cy_v):
        im = self.R.A.img[name]
        bw = scale_w
        bh = bw * im.height() / im.width()
        x0, y0 = self.w / 2 - cx_u * bw, self.h / 2 - cy_v * bh
        self.R.c.drawImageRect(im, skia.Rect.MakeXYWH(x0, y0, bw, bh), BG_SAMP, skia.Paint(AntiAlias=True))

    def grass(self, y, h):
        im = self.R.A.img["fg_grass"]
        w = h * im.width() / im.height()
        x = -60
        while x < self.w:
            self.R.c.drawImageRect(im, skia.Rect.MakeXYWH(x, y, w, h), SAMP, skia.Paint(AntiAlias=True))
            x += w - 4

    def banner(self, text, cx, cy, size, color=(105, 66, 42)):
        c = self.R.c
        font = skia.Font(FONT_TF, size)
        tw = font.measureText(text)
        rect = skia.Rect.MakeLTRB(cx - tw / 2 - size * 0.8, cy - size * 0.95, cx + tw / 2 + size * 0.8, cy + size * 0.6)
        c.save()
        c.rotate(-1.2, cx, cy)
        c.drawRoundRect(rect.makeOffset(8, 10), size * 0.5, size * 0.5,
                        skia.Paint(AntiAlias=True, Color=skia.Color(60, 35, 15, 80),
                                   MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 10)))
        c.drawRoundRect(rect, size * 0.5, size * 0.5, skia.Paint(AntiAlias=True, Color=skia.Color(253, 247, 233)))
        c.drawRoundRect(rect.makeInset(size * 0.15, size * 0.15), size * 0.38, size * 0.38,
                        skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=size * 0.05,
                                   Color=skia.Color(225, 196, 160), PathEffect=skia.DashPathEffect.Make([size * 0.2, size * 0.14], 0)))
        self.R.record = False
        self.R.paper_text(text, cx, cy, size, color, stroke=7, bold=3)
        self.R.record = False
        c.restore()

    def title(self, cx, cy, size, gap):
        for i, ch in enumerate("龟兔赛跑"):
            self.R.paper_text(ch, cx + (i - 1.5) * gap, cy + [6, -8, 4, -6][i], size, TITLE_COLORS[i],
                              stroke=size * 0.075, bold=size * 0.05, rot=[-6, 4, -4, 6][i])

    def finish(self, path):
        # 与成片一致的纸纹 + 暗角
        tex = Image.open(CUT / "paper_texture.png").convert("RGB").resize((self.w, self.h), Image.LANCZOS)
        a = np.asarray(tex).astype(np.float32)
        a = a / a.reshape(-1, 3).mean(0)
        a = np.clip(1 + (a - 1) * 1.1, 0, 1.0)
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        r = np.sqrt((xx - self.w / 2) ** 2 + (yy - self.h * 0.52) ** 2) / (0.65 * math.hypot(self.w, self.h))
        vig = 1 - 0.42 * np.clip((r - 0.55) / 0.45, 0, 1) ** 1.5
        m = a * vig[..., None]
        rgb = self.arr[..., :3].astype(np.float32) * m[..., ::-1]
        self.arr[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        im = Image.fromarray(self.arr[..., [2, 1, 0]].copy())
        im.save(path.with_suffix(".png"))
        im.save(path.with_suffix(".jpg"), quality=93)
        print(f"{LOG} 输出 {path.with_suffix('.png')} / .jpg", flush=True)


def horizontal(R):
    C = CoverCanvas(R, 1920, 1080)
    C.bg("bg_start", 1920 * 1.38, 0.50, 0.56)
    # 起点彩带与纸片
    C.grass(1080 - 215, 235)
    R.actor("hare_stand", 690, 1000, flip=True, scale_mul=0.96, blink=False)
    R.actor("tortoise_stand", 1250, 1000, scale_mul=1.16, blink=False)
    R.actor("fox_stand", 1570, 1000, flip=True, scale_mul=0.78, blink=False)
    R.actor("mouse_stand", 1710, 1000, flip=True, scale_mul=0.82, blink=False)
    # 速度线
    R.speed_lines(560, 760, 0.8, direction=-1, n=7, length=180, alpha=0.55, seed=4)
    C.title(960, 175, 205, 222)
    C.banner("不怕慢，只怕站", 960, 375, 60)
    R.record = False
    R.paper_text("根据伊索寓言改编", 960, 465, 34, (120, 92, 66), stroke=5, bold=2, alpha=0.95)
    C.finish(OUT / "cover_16x9")


def vertical(R):
    C = CoverCanvas(R, 1080, 1920)
    C.bg("bg_start", 1080 * 2.82, 0.48, 0.52)
    C.grass(1920 - 265, 275)
    R.actor("hare_stand", 330, 1500, flip=True, scale_mul=1.25, blink=False)
    R.actor("tortoise_stand", 790, 1700, scale_mul=1.35, blink=False)
    R.actor("mouse_stand", 955, 1640, flip=True, scale_mul=0.66, blink=False)
    R.speed_lines(230, 1240, 0.8, direction=-1, n=6, length=150, alpha=0.5, seed=7)
    C.title(540, 300, 200, 218)
    C.banner("不怕慢，只怕站", 540, 510, 56)
    R.record = False
    R.paper_text("根据伊索寓言改编", 540, 600, 34, (120, 92, 66), stroke=5, bold=2, alpha=0.95)
    C.finish(OUT / "cover_9x16")


def main():
    R = Renderer(Assets())
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "h"):
        horizontal(R)
    if which in ("all", "v"):
        vertical(R)


if __name__ == "__main__":
    main()
