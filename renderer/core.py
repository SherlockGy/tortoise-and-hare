# 渲染核心：精灵缓存、镜头、背景、字幕、缓动（Pillow + NumPy；v4 成片用这套）
import math
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "renderer" / "cache"
W, H, FPS = 1920, 1080, 30
G = 925  # 地面线
FONT_SUB = str(ROOT/'assets/fonts/ZCOOLKuaiLe-Regular.ttf')
FONT_TITLE = str(ROOT/'assets/fonts/ZCOOLQingKeHuangYou-Regular.ttf')

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, t): return a + (b - a) * t
def smooth(t): t = clamp(t); return t*t*(3-2*t)
def ease_out(t): t = clamp(t); return 1-(1-t)**3
def ease_in(t): t = clamp(t); return t**3
def ease_io(t): t = clamp(t); return 4*t**3 if t < .5 else 1-(-2*t+2)**3/2
def back_out(t, s=1.7):
    t = clamp(t); return 1 + (s+1)*(t-1)**3 + s*(t-1)**2
def seg(t, a, b): return clamp((t-a)/(b-a)) if b > a else float(t >= a)
def keys(t, kf, fn=ease_io):
    """kf: [(time, value), ...] 分段缓动插值"""
    if t <= kf[0][0]: return kf[0][1]
    for (t0, v0), (t1, v1) in zip(kf, kf[1:]):
        if t <= t1:
            u = fn(seg(t, t0, t1))
            if isinstance(v0, tuple): return tuple(lerp(a, b, u) for a, b in zip(v0, v1))
            return lerp(v0, v1, u)
    return kf[-1][1]

@lru_cache(maxsize=None)
def base(name):
    return Image.open(CACHE/f'{name}.png').convert('RGBA')

_sc = {}
def sprite(name, scale=1.0, flip=False, rot=0.0, sx=1.0, sy=1.0):
    q = (name, round(scale*sx, 3), round(scale*sy, 3), flip, round(rot, 1))
    im = _sc.get(q)
    if im is not None: return im
    im = base(name)
    w, h = max(1, round(im.width*scale*sx)), max(1, round(im.height*scale*sy))
    if (w, h) != im.size: im = im.resize((w, h), Image.BICUBIC)
    if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if abs(rot) > 0.05: im = im.rotate(rot, Image.BICUBIC, expand=True)
    if len(_sc) > 600: _sc.clear()
    _sc[q] = im
    return im

def paste(frame, im, x, y, alpha=1.0):
    """把 im 左上角贴到 (x,y)，自动裁边"""
    x, y = int(round(x)), int(round(y))
    if alpha < 1.0:
        if alpha <= 0.003: return
        a = im.getchannel('A').point(lambda v: int(v*alpha)); im = im.copy(); im.putalpha(a)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(frame.width, x+im.width), min(frame.height, y+im.height)
    if x1 <= x0 or y1 <= y0: return
    frame.alpha_composite(im, (x0, y0), (x0-x, y0-y, x1-x, y1-y))

class Cam:
    def __init__(self, z=1.0, cx=W/2, cy=H/2): self.z, self.cx, self.cy = z, cx, cy
    def pt(self, x, y): return (x-self.cx)*self.z+W/2, (y-self.cy)*self.z+H/2

def put(frame, cam, name, x, y, scale=1.0, flip=False, rot=0.0, sx=1.0, sy=1.0, alpha=1.0, anchor='bottom', shadow=True, shadow_y=None):
    """世界坐标 (x,y) 为精灵底边中点（anchor='bottom'）或中心（'center'）"""
    z = cam.z if cam else 1.0
    X, Y = cam.pt(x, y) if cam else (x, y)
    if shadow and anchor == 'bottom':
        b = base(name); sw = b.width*scale*sx*0.8
        sy_ = (cam.pt(x, shadow_y)[1] if (cam and shadow_y is not None) else (shadow_y if shadow_y is not None else Y))
        lift = 0 if shadow_y is None else max(0, (shadow_y - y))
        k = clamp(1 - lift/260, 0.35, 1)
        shp = sprite('shadow', sw*z*k/400, sy=0.6)
        paste(frame, shp, X-shp.width/2, sy_-shp.height/2-2, alpha*0.72*k)
    im = sprite(name, scale*z, flip, rot, sx, sy)
    if anchor == 'bottom':
        # 旋转后近似保持底部中点
        paste(frame, im, X-im.width/2, Y-im.height + (im.height - base(name).height*scale*z*sy)/2 if abs(rot) > 0.05 else Y-im.height, alpha)
    else:
        paste(frame, im, X-im.width/2, Y-im.height/2, alpha)

# ---------- 背景 ----------
BG_Y = dict(bg_start=181, bg_forest=265, bg_oak=223, bg_finish=195, bg_sunset=237, paper_texture=180)  # 让地面线 G 落在原画的开阔草地/小路上
def bg(name, cam=None):
    im = base(name)  # 2150x1434 RGBA
    ox, oy = (im.width-W)/2, BG_Y.get(name, 300)
    c = cam or Cam()
    hw, hh = W/2/c.z, H/2/c.z
    x0, y0 = ox + c.cx - hw, oy + c.cy - hh
    x0c = clamp(x0, 0, im.width-2*hw); y0c = clamp(y0, 0, im.height-2*hh)
    # 关键：镜头越界时修正镜头本身（而不是只夹住背景），保证道具/角色与背景同步移动
    c.cx += x0c-x0; c.cy += y0c-y0; x0, y0 = x0c, y0c
    box = (x0, y0, x0+2*hw, y0+2*hh)
    if abs(c.z-1) < 1e-4 and abs(x0-round(x0)) < 1e-3 and abs(y0-round(y0)) < 1e-3:
        return im.crop(tuple(int(round(v)) for v in box)).copy()
    return im.resize((W, H), Image.BILINEAR, box=box)

@lru_cache(maxsize=4)
def strip(name):
    im = base(name); y0 = BG_Y.get(name, 300)
    a = im.crop((0, y0, im.width, y0+H))
    s = Image.new('RGBA', (a.width*2, H)); s.paste(a, (0, 0)); s.paste(a.transpose(Image.FLIP_LEFT_RIGHT), (a.width, 0))
    return s

def bg_scroll(name, off):
    s = strip(name); off = off % s.width
    f = Image.new('RGBA', (W, H)); x = -int(off)
    while x < W:
        f.paste(s, (x, 0)); x += s.width
    return f

def fg(frame, name='fg_grass', off=0.0, y=None, alpha=1.0):
    im = base(name); y = H-175 if y is None else y
    t = Image.new('RGBA', (im.width*2, im.height)); t.paste(im, (0, 0)); t.paste(im.transpose(Image.FLIP_LEFT_RIGHT), (im.width, 0))
    off = off % t.width; x = -off
    while x < W:
        paste(frame, t, x, y, alpha); x += t.width

# ---------- 文字 ----------
@lru_cache(maxsize=256)
def text_img(txt, size, font=FONT_SUB, fill=(92, 58, 30), stroke=0, stroke_fill=(255, 255, 255), shadow=False):
    f = ImageFont.truetype(font, size)
    l, t, r, b = f.getbbox(txt, stroke_width=stroke)
    pad = 12 + stroke
    im = Image.new('RGBA', (r-l+2*pad, b-t+2*pad))
    d = ImageDraw.Draw(im)
    if shadow:
        sh = Image.new('RGBA', im.size); ImageDraw.Draw(sh).text((pad-l+5, pad-t+7), txt, font=f, fill=(70, 40, 20, 140), stroke_width=stroke, stroke_fill=(70, 40, 20, 140))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
    d.text((pad-l, pad-t), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return im

@lru_cache(maxsize=128)
def subtitle_img(txt):
    t = text_img(txt, 46, FONT_SUB, (88, 54, 28))
    w, h = t.width+56, 78
    im = Image.new('RGBA', (w, h))
    sh = Image.new('L', (w, h)); ImageDraw.Draw(sh).rounded_rectangle((6, 8, w-6, h-2), 34, fill=90)
    shadow = Image.new('RGBA', (w, h), (60, 40, 20, 0)); shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(5)))
    im.alpha_composite(shadow)
    ImageDraw.Draw(im).rounded_rectangle((4, 2, w-4, h-8), 34, fill=(255, 250, 236, 236), outline=(224, 196, 150, 255), width=3)
    im.alpha_composite(t, ((w-t.width)//2, (h-8-t.height)//2))
    return im

def draw_center(frame, im, cx, cy, scale=1.0, alpha=1.0, rot=0):
    if scale != 1.0 or rot:
        im = im.resize((max(1, int(im.width*scale)), max(1, int(im.height*scale))), Image.BICUBIC)
        if rot: im = im.rotate(rot, Image.BICUBIC, expand=True)
    paste(frame, im, cx-im.width/2, cy-im.height/2, alpha)

# ---------- 角色动作 ----------
GALLOP = [('gallop_1', 0, 0.0), ('gallop_2', -14, -4.0), ('gallop_3', -62, 0.0), ('gallop_4', -10, 4.0)]
def gallop(frame, cam, x, ph, scale=1.0, flip=False, alpha=1.0, y=G):
    """兔子 4 帧奔跑循环：蓄力-蹬地-腾空-落地，带身体起伏与轻微俯仰。ph 以“圈”为单位"""
    ph = ph % 1.0
    i = int(ph*4) % 4
    name, dy, rot = GALLOP[i]
    u = (ph*4) % 1.0
    # 在帧内部做连续的上下浮动，避免硬切
    arc = [0, -8, -66, -24][i]*0.0
    dy2 = dy + math.sin(u*math.pi) * [ -6, -10, -6, 6][i]
    # 统一以身体中心水平对齐：各帧质心相对底边中点的偏移
    cxo = GX[name]*scale
    put(frame, cam, name, x - (cxo if not flip else -cxo), y + dy2*scale, scale=scale, flip=flip, rot=(-rot if flip else rot), alpha=alpha, shadow_y=y)

def _centroid_offsets():
    missing = [n for n, _, _ in GALLOP if not (CACHE / f"{n}.png").exists()]
    if missing:
        raise SystemExit(
            f"缺少预缩放缓存 {CACHE}（{', '.join(missing)}）。请先运行: python3 renderer/prep.py"
        )
    out = {}
    for n, _, _ in GALLOP:
        a = np.asarray(base(n).getchannel('A')).astype(np.float32)
        xs = (a.sum(0)*np.arange(a.shape[1])).sum()/a.sum()
        # 用头部（上方 45%）质心对齐，头部轨迹更稳
        out[n] = 0.0
        top = a[: int(a.shape[0]*0.5)]
        hx = (top.sum(0)*np.arange(a.shape[1])).sum()/max(1, top.sum())
        out[n] = (0.6*xs + 0.4*hx) - a.shape[1]/2
    return out
GX = _centroid_offsets()

def walk_t(frame, cam, x, ph, scale=1.0, flip=False, y=G, alpha=1.0, alt=None):
    """乌龟走路：a - 站 - b - 站 四拍循环，带轻微上下起伏。ph 以“圈”为单位"""
    ph = ph % 1.0
    seq = ['tortoise_walk_a', alt or 'tortoise_stand', 'tortoise_walk_b', alt or 'tortoise_stand']
    i = int(ph*4) % 4
    bob = -abs(math.sin(ph*2*math.pi))*5
    put(frame, cam, seq[i], x, y+bob*scale, scale=scale, flip=flip, alpha=alpha, shadow_y=y)

def breathe(t, amp=0.012, f=0.45, ph=0.0):
    s = math.sin((t*f+ph)*2*math.pi)
    return 1-amp*0.4*s, 1+amp*s  # sx, sy

def blink_on(t, every=3.3, ph=0.0, dur=0.13):
    return ((t+ph) % every) < dur

# ---------- 跟拍背景：放大后单张平移（不再镜像拼接，避免对称接缝） ----------
PAN_Y = dict(bg_forest=640, bg_oak=600, bg_start=640, bg_finish=640)
@lru_cache(maxsize=3)
def pan_src(name):
    im = Image.open(ROOT/f'assets/cut/{name}.png').convert('RGBA')
    return im.resize((round(im.width*1.8), round(im.height*1.8)), Image.LANCZOS)

def bg_pan(name, off):
    im = pan_src(name)
    x0 = clamp(off, 0, im.width-W); y0 = PAN_Y.get(name, 620)
    if abs(x0-round(x0)) < 1e-3: return im.crop((int(x0), y0, int(x0)+W, y0+H))
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0+W, y0+H))
