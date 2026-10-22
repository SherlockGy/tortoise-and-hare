# 动作帧对齐：codex 精修保持了原画布构图，按原画布坐标把动作帧映射到基准姿势的裁切坐标
# 并输出洋葱皮叠图（基准=蓝、动作帧=红）供人工核对
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
CUT = ROOT / "assets" / "cut"
LOG = "[align 动作帧对齐]"

# 动作帧 -> 基准姿势（基准必须已在 cut/meta.json 中）
FRAMES = {
    "hare_run_a": "hare_stand", "hare_run_b": "hare_run_a", "hare_blink": "hare_stand",
    "hare_talk": "hare_stand", "hare_taunt": "hare_stand", "hare_eat": "hare_stand",
    "hare_sad": "hare_stand", "hare_cheer": "hare_stand", "hare_wake": "hare_stand",
    "hare_sleep": "hare_stand", "hare_snore": "hare_stand", "hare_sprint": "hare_run_a",
    "tortoise_walk_a": "tortoise_stand", "tortoise_walk_b": "tortoise_stand", "tortoise_blink": "tortoise_stand",
    "tortoise_talk": "tortoise_stand", "tortoise_look_up": "tortoise_stand", "tortoise_determined": "tortoise_stand",
    "tortoise_tired": "tortoise_stand", "tortoise_cross": "tortoise_stand", "tortoise_cheer": "tortoise_stand",
    "tortoise_nod": "tortoise_stand", "tortoise_look_back": "tortoise_stand",
    "owl_talk": "owl_stand", "owl_wingup": "owl_stand", "owl_blink": "owl_stand", "owl_cheer": "owl_stand",
    "fox_cheer": "fox_stand", "hedgehog_cheer": "hedgehog_stand", "mouse_cheer": "mouse_stand",
}


def main():
    meta = json.loads((CUT / "meta.json").read_text(encoding="utf-8"))
    res, tiles = {}, []
    for name, base in FRAMES.items():
        if name not in meta or base not in meta:
            print(f"{LOG}[{name}] 缺少素材，跳过")
            continue
        fm, bm = meta[name], meta[base]
        # 原图尺寸不同时按宽度比例换算（codex 输出构图居中一致）
        s = bm["raw"][0] / fm["raw"][0]
        oy = (bm["raw"][1] - fm["raw"][1] * s) / 2
        dx = fm["crop"][0] * s - bm["crop"][0]
        dy = fm["crop"][1] * s + oy - bm["crop"][1]
        res[name] = dict(base=base, s=round(s, 4), dx=round(dx, 1), dy=round(dy, 1))
        print(f"{LOG}[{name}] -> {base} s={s:.3f} dx={dx:.0f} dy={dy:.0f}")

        if name == base:
            continue
        b = np.asarray(Image.open(CUT / f"{base}.png").convert("RGBA"))[..., 3]
        f = Image.open(CUT / f"{name}.png").convert("RGBA")
        f = f.resize((round(f.width * s), round(f.height * s)))
        fa = np.asarray(f)[..., 3]
        H = max(b.shape[0], int(dy) + fa.shape[0]) + 10
        W = max(b.shape[1], int(dx) + fa.shape[1]) + 10
        ox, oy2 = max(0, -int(dx)), max(0, -int(dy))
        canvas = np.full((H + oy2, W + ox, 3), 255, np.uint8)
        canvas[oy2:oy2 + b.shape[0], ox:ox + b.shape[1], 2] = np.where(b > 128, 120, 255).astype(np.uint8)
        ys, xs = int(dy) + oy2, int(dx) + ox
        reg = canvas[ys:ys + fa.shape[0], xs:xs + fa.shape[1]]
        reg[..., 0] = np.where(fa[:reg.shape[0], :reg.shape[1]] > 128, 120, reg[..., 0])
        im = Image.fromarray(canvas)
        im.thumbnail((440, 480))
        tiles.append((name, im))
    (CUT / "align.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    out = ROOT / "out"
    out.mkdir(parents=True, exist_ok=True)
    for k in range(0, len(tiles), 12):
        sheet = Image.new("RGB", (1920, 1440), "white")
        d = ImageDraw.Draw(sheet)
        for i, (n, im) in enumerate(tiles[k:k + 12]):
            x, y = (i % 4) * 480, (i // 4) * 480
            sheet.paste(im, (x + 20, y + 10))
            d.text((x + 24, y + 452), n, fill="black")
        sheet.save(out / f"onion_{k // 12}.png")


if __name__ == "__main__":
    main()
