# 对 assets/regen 下 Codex 生成的纯绿底原图抠图，输出 *_cut.png
# 只处理该目录顶层 PNG，不进入 covers/。已是 *_cut.png 的文件会跳过。
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import numpy as np
from PIL import Image
from key_raw import key_alpha, to_rgba, crop

REGEN = ROOT / "assets" / "regen"


def main():
    found = False
    for f in sorted(REGEN.glob("*.png")):
        if f.stem.endswith("_cut") or f.name.startswith("._"):
            continue
        found = True
        im = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
        rgb, a = key_alpha(im, "green")
        r = crop(to_rgba(rgb, a))
        Image.fromarray(r).save(REGEN / f"{f.stem}_cut.png")
        print(f.stem, r.shape)
    if not found:
        print(f"{REGEN} 下没有需要抠的绿底 PNG（*_cut.png 会跳过）")


if __name__ == "__main__":
    main()
