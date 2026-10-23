# 抽几个时间点的成片帧，缩小后拼成一张检查图
import sys
from PIL import Image, ImageDraw
from render import frame


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        raise SystemExit("用法: python3 renderer/snap.py <输出.jpg> <秒> [<秒> ...]")
    out = argv[0]
    ts = [float(x) for x in argv[1:]]
    cols, w, h = 3, 640, 360
    sheet = Image.new("RGB", (w * cols, h * ((len(ts) + cols - 1) // cols)))
    for i, T in enumerate(ts):
        im = frame(T).resize((w, h))
        ImageDraw.Draw(im).text((8, 8), f"{T:.1f}", fill=(255, 0, 0))
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(out)
    print(out, "frames", len(ts))


if __name__ == "__main__":
    main()
