# 生成 SRT 字幕：与旁白逐句同步
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from timeline import voice_spans

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "tortoise_and_hare.srt"


def ts(t):
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    lines = []
    for i, sp in enumerate(voice_spans(), 1):
        lines.append(str(i))
        lines.append(f"{ts(sp['t0'])} --> {ts(sp['t1'])}")
        lines.append(sp["text"])
        lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT, len(lines))


if __name__ == "__main__":
    main()
