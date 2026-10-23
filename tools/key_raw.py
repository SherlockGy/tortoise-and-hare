# 素材预处理：把 assets/raw 里的纯色背景原图抠图、裁边、拆分道具拼版，写入 assets/cut/
# assets/raw 没有放进仓库。渲染成片用的是已经提交的 assets/cut/，不必运行本脚本。
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "assets" / "raw"
CUT = ROOT / "assets" / "cut"
LOG = "[prep 素材预处理]"

MAGENTA = {"fg_grass", "fg_flowers", "props", "nature"}
PROP_NAMES = ["carrot", "trophy", "watch", "flag", "basket", "apple", "mushroom", "daisies"]
NATURE_NAMES = ["cloud1", "cloud2", "cloud3", "leaf1", "leaf2", "leaf3", "leaf4", "star", "butterfly"]


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def key_alpha(rgb, key):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    k = g - np.maximum(r, b) if key == "green" else np.minimum(r, b) - g
    strong = k > 70
    lab, _ = ndimage.label(strong)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bg = np.isin(lab, border[border > 0])
    bg |= k > 190
    band = ndimage.binary_dilation(bg, iterations=4)

    alpha = np.ones(k.shape, np.float32)
    soft = 1 - smoothstep(25, 150, k)
    alpha[band] = soft[band]
    alpha[bg] = np.minimum(alpha[bg], 0.0)

    out = rgb.copy()
    edge = band & (alpha > 0)
    if key == "green":
        out[..., 1] = np.where(edge, np.minimum(g, np.maximum(r, b) + 8), g)
    else:
        lim = g + 8
        out[..., 0] = np.where(edge, np.minimum(r, lim), r)
        out[..., 2] = np.where(edge, np.minimum(b, lim), b)
    return out, alpha


def to_rgba(rgb, alpha):
    a = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    return np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), a])


def crop(rgba, pad=6, info=None):
    ys, xs = np.nonzero(rgba[..., 3] > 8)
    if len(ys) == 0:
        return rgba
    y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + pad + 1)
    if info is not None:
        info.update(crop=[int(x0), int(y0)], raw=[int(rgba.shape[1]), int(rgba.shape[0])])
    return rgba[y0:y1, x0:x1]


def split_sheet(rgba, names, min_area=1500):
    lab, cnt = ndimage.label(rgba[..., 3] > 40)
    objs = ndimage.find_objects(lab)
    items = []
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        area = (lab[sl] == i + 1).sum()
        if area < min_area:
            continue
        cy, cx = (sl[0].start + sl[0].stop) / 2, (sl[1].start + sl[1].stop) / 2
        items.append((cy, cx, i + 1, sl, area))
    items.sort(key=lambda t: (round(t[0] / 220), t[1]))
    print(f"{LOG} 拼版拆出 {len(items)} 个（期望 {len(names)} 个）")
    out = {}
    for nm, (cy, cx, idx, sl, area) in zip(names, items):
        sub = rgba[sl].copy()
        sub[..., 3] = np.where(lab[sl] == idx, sub[..., 3], 0)
        sub = crop(sub)
        out[nm] = sub
    return out


def main():
    if not RAW.is_dir() or not any(RAW.glob("*.png")):
        raise SystemExit(
            "缺少 assets/raw 里的绿底/品红底原图。这些原图没有放进仓库。\n"
            "重新生成：安装并登录 Codex CLI 后运行 python3 tools/gen_assets.py，"
            "它会把原图写到 assets/raw/，然后再运行本脚本抠图到 assets/cut/。\n"
            "渲染成片不需要这一步，直接使用已提交的 assets/cut/。"
        )
    CUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for f in sorted(RAW.glob("*.png")):
        name = f.stem
        im = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
        if name.startswith("bg_") or name == "paper_texture":
            Image.fromarray(im.astype(np.uint8)).save(CUT / f"{name}.png")
            meta[name] = dict(w=im.shape[1], h=im.shape[0])
            continue
        key = "magenta" if name in MAGENTA else "green"
        rgb, alpha = key_alpha(im, key)
        rgba = to_rgba(rgb, alpha)

        if name in ("props", "nature"):
            pieces = split_sheet(rgba, PROP_NAMES if name == "props" else NATURE_NAMES)
            for nm, sub in pieces.items():
                Image.fromarray(sub).save(CUT / f"{nm}.png")
                meta[nm] = dict(w=sub.shape[1], h=sub.shape[0])
                print(f"{LOG}[{nm}] {sub.shape[1]}x{sub.shape[0]}")
            continue

        info = {}
        rgba = crop(rgba, info=info)
        Image.fromarray(rgba).save(CUT / f"{name}.png")
        meta[name] = dict(w=rgba.shape[1], h=rgba.shape[0], **info)
        print(f"{LOG}[{name}] {rgba.shape[1]}x{rgba.shape[0]}")
    (CUT / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
