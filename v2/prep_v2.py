# 预缩放素材到成片显示尺寸（v2）
import json
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw
ROOT = Path(__file__).resolve().parent.parent
CUT = ROOT/'assets/cut'; OUT = ROOT/'v2/cache'; OUT.mkdir(exist_ok=True)
HARE = 0.29
SC = {}
for p in CUT.glob('*.png'):
    n = p.stem
    if n.startswith('hare'): SC[n] = HARE
    elif n.startswith('tortoise'): SC[n] = 0.33
    elif n.startswith('owl'): SC[n] = 270/1264
    elif n.startswith('fox'): SC[n] = 230/1112
    elif n.startswith('hedgehog'): SC[n] = 190/1173
    elif n.startswith('mouse'): SC[n] = 150/1105
SC.update(tree_stump=330/1428, blanket=520/1416, finish_banner=640/1746, start_banner=600/1640,
          trophy=150/331, carrot=90/436, stopwatch=0.15, bird_fly=120/986, bird_fly2=120/1081,
          butterfly=0.06, leaf1=0.07, leaf2=0.07, leaf3=0.07, leaf4=0.07, star=0.08, cloud1=0.3, cloud2=0.3, cloud3=0.3,
          mushroom=0.12, daisies=0.12, apple=0.1, flag=0.15, basket=0.15, watch=0.15)
meta = {}
for p in sorted(CUT.glob('*.png')):
    n = p.stem
    im = Image.open(p)
    if n.startswith('bg_') or n == 'paper_texture':
        im = im.convert('RGB')
        im = im.resize((round(im.width*1.4), round(im.height*1.4)), Image.LANCZOS)  # 2150x1434
        im.save(OUT/f'{n}.png'); continue
    if n in ('fg_grass', 'fg_flowers'):
        s = 1920/im.width*1.0
        im = im.resize((1920, round(im.height*s)), Image.LANCZOS); im.save(OUT/f'{n}.png'); continue
    s = SC.get(n, 0.15)
    im = im.resize((max(1, round(im.width*s)), max(1, round(im.height*s))), Image.LANCZOS)
    im.save(OUT/f'{n}.png'); meta[n] = im.size
# 新生成的兔子奔跑循环（4 帧），按领巾/耳朵面积统一比例
GS = {1: 1.0, 2: 1.0, 3: 1.12, 4: 1.0}
for i in range(1, 5):
    im = Image.open(ROOT/f'assets/regen/gallop_{i}_cut.png')
    s = HARE*0.85*GS[i]
    im = im.resize((round(im.width*s), round(im.height*s)), Image.LANCZOS)
    im.save(OUT/f'gallop_{i}.png'); meta[f'gallop_{i}'] = im.size
# 软阴影
sh = Image.new('L', (400, 100), 0); ImageDraw.Draw(sh).ellipse((20, 20, 380, 80), fill=150)
sh = sh.filter(ImageFilter.GaussianBlur(12))
img = Image.new('RGBA', (400, 100), (60, 50, 30, 0)); img.putalpha(sh); img.save(OUT/'shadow.png')
json.dump(meta, open(OUT/'meta.json', 'w'), indent=1)
print(json.dumps(meta))
# 终点红丝带（codex 生成）：整条 + 断开的一半
for n, size in (('ribbon', (600, 30)), ('ribbon_half', (250, 30))):
    im = Image.open(ROOT/f'assets/regen/{n}_cut.png').convert('RGBA').resize(size, Image.LANCZOS)
    im.save(OUT/f'{n}.png'); meta[n] = im.size
json.dump(meta, open(OUT/'meta.json', 'w'), indent=1)
