# 对 assets/regen 下 codex 生成的纯绿底原图抠图，输出 *_cut.png
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
import numpy as np
from PIL import Image
from prep import key_alpha, to_rgba, crop
REGEN = ROOT/'assets/regen'
for f in sorted(REGEN.glob('*.png')):
    if f.stem.endswith('_cut') or f.name.startswith('._'): continue
    im = np.asarray(Image.open(f).convert('RGB')).astype(np.float32)
    rgb, a = key_alpha(im, 'green'); r = crop(to_rgba(rgb, a))
    Image.fromarray(r).save(REGEN/f'{f.stem}_cut.png'); print(f.stem, r.shape)
