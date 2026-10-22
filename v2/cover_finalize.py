# 封面后期：把 codex 生成的原图（assets/regen/covers/cover_*.png）按目标画幅等比裁切 + 等比缩放到精确像素
# （不拉伸），再用项目字体 ZCOOL 加上标题“龟兔赛跑”，输出到 covers/
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT/'assets/regen/covers'; OUT = ROOT/'covers'; OUT.mkdir(exist_ok=True)
FT = str(ROOT/'assets/fonts/ZCOOLQingKeHuangYou-Regular.ttf'); FS = str(ROOT/'assets/fonts/ZCOOLKuaiLe-Regular.ttf')
COLS = [(86, 150, 70), (236, 128, 60), (225, 92, 110), (70, 140, 200)]
# 名称: (目标宽, 高, 裁切中心 x 比例, 裁切中心 y 比例, 标题中心 y 比例, 标题字号占短边比例, 标题中心 x 比例)
# 标题放在天空留白处，避开兔子的耳朵和太阳
SPECS = {
    'cover_16x9': (1920, 1080, 0.5, 0.5, 0.125, 0.15, 0.37),
    'cover_9x16': (1080, 1920, 0.5, 0.5, 0.10, 0.125, 0.5),
    'cover_4x3':  (1440, 1080, 0.5, 0.5, 0.115, 0.135, 0.37),
}
if len(sys.argv) > 1:
    for kv in sys.argv[1:]:  # 例：cover_4x3:cy=0.45,ty=0.15
        n, opts = kv.split(':'); s = list(SPECS[n])
        for o in opts.split(','):
            k, v = o.split('='); s[{'cx': 2, 'cy': 3, 'ty': 4, 'fs': 5, 'tx': 6}[k]] = float(v)
        SPECS[n] = tuple(s)

def fit(im, w, h, cx, cy):
    s = max(w/im.width, h/im.height)
    im = im.resize((round(im.width*s), round(im.height*s)), Image.LANCZOS)
    x0 = min(max(0, round(im.width*cx - w/2)), im.width-w); y0 = min(max(0, round(im.height*cy - h/2)), im.height-h)
    return im.crop((x0, y0, x0+w, y0+h))

def glyph(ch, size, col, stroke):
    f = ImageFont.truetype(FT, size); l, t, r, b = f.getbbox(ch, stroke_width=stroke); pad = stroke+30
    im = Image.new('RGBA', (r-l+2*pad, b-t+2*pad)); d = ImageDraw.Draw(im)
    sh = Image.new('RGBA', im.size); ImageDraw.Draw(sh).text((pad-l+8, pad-t+12), ch, font=f, fill=(60, 35, 15, 170), stroke_width=stroke, stroke_fill=(60, 35, 15, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    d.text((pad-l, pad-t), ch, font=f, fill=col, stroke_width=stroke, stroke_fill=(255, 255, 255))
    return im

for name, (w, h, cx, cy, ty, fsz, tx) in SPECS.items():
    src = RAW/f'{name}.png'
    if not src.exists(): print('缺少', src); continue
    im = fit(Image.open(src).convert('RGBA'), w, h, cx, cy)
    short = min(w, h); size = int(short*fsz*(1.0 if w >= h else 1.55)); stroke = max(6, size//14)
    step = size*1.02; y = h*ty
    for i, ch in enumerate('龟兔赛跑'):
        g = glyph(ch, size, COLS[i], stroke).rotate(-4 if i % 2 else 4, Image.BICUBIC, expand=True)
        im.alpha_composite(g, (int(w*tx + (i-1.5)*step - g.width/2), int(y - g.height/2)))
    fsub = ImageFont.truetype(FS, int(size*0.26)); txt = 'The Tortoise and the Hare'
    l, t, r, b = fsub.getbbox(txt, stroke_width=5)
    ImageDraw.Draw(im).text((w*tx-(r-l)/2-l, y+size*0.62), txt, font=fsub, fill=(92, 58, 30), stroke_width=5, stroke_fill=(255, 255, 255))
    im.convert('RGB').save(OUT/f'{name}.png', optimize=True); print(name, im.size)
