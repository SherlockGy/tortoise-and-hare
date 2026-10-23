# 旁白文稿与合成：每句单独合成，记录时长，供时间轴、字幕与混音使用
import json
import sys
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from minimax import tts

ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = ROOT / "assets" / "voice"
VOICE_ID = "Chinese (Mandarin)_Gentle_Senior"   # 温柔学姐：温暖、清楚、适合睡前故事
SPEED = 0.9
LOG = "[narration 旁白合成]"

# 每幕旁白（按出现顺序）
LINES = {
    "title": ["森林里，住着一只跑得飞快的兔子，和一只慢慢吞吞的乌龟。",
              "有一天，他们要比一比，到底谁跑得更快。"],
    "meet": ["兔子在草地上蹦来蹦去，看见乌龟正一步一步地爬。",
             "兔子哈哈大笑：乌龟，你走得这么慢，也敢和我赛跑吗？",
             "乌龟抬起头，不紧不慢地说：",
             "比一比，不就知道了？"],
    "challenge": ["这话传遍了森林，小动物们都跑来围观。",
                  "猫头鹰裁判站在老树桩上，推了推眼镜：",
                  "从森林这头，跑到山脚下的终点线，谁也不许抄近路。",
                  "准备好了吗？"],
    "start": ["各就各位——",
              "预备——跑！",
              "兔子像一阵风，嗖地冲了出去。"],
    "sprint": ["兔子跑得真快呀，一转眼就没了影子。",
               "乌龟呢？他一步一步，稳稳地往前爬。",
               "兔子回头一看，乌龟还离得远呢。"],
    "taunt": ["兔子心想：我跑得这么快，就算睡一觉，也来得及。",
              "他往草地上一躺，啃起了胡萝卜。",
              "乌龟还早着呢，我先歇一会儿。"],
    "nap": ["太阳暖洋洋的，风轻轻的。",
            "兔子的眼皮越来越重，越来越重……",
            "呼——呼——他睡着了。",
            "就在这时，乌龟一步一步，从他身边爬了过去。"],
    "pass": ["乌龟没有停下来，也没有回头。",
             "一步，又一步。汗珠掉在土里，他也不歇。",
             "小动物们屏住呼吸，悄悄地为他加油。"],
    "wake": ["兔子一觉醒来，伸了个懒腰。",
             "他往山脚下一看——乌龟已经快到终点了！",
             "兔子吓了一跳，撒开腿就追。"],
    "chase": ["风在耳边呼呼地响，兔子跑得比刚才还快。",
              "乌龟听到了身后的脚步声，咬紧牙，继续往前爬。",
              "终点就在前面，红丝带在风里飘呀飘。"],
    "finish": ["乌龟伸出脖子，向前一扑——",
               "红丝带落了下来！",
               "乌龟先到了！森林里响起一片欢呼。",
               "兔子气喘吁吁地赶到，低下了头。"],
    "moral": ["兔子小声说：我跑得比你快，可是我输了。",
              "乌龟笑着说：你只是跑得快，我是一直没有停。",
              "兔子点点头：下次，我一定跑完全程，再休息。",
              "小朋友，跑得快，不如走得稳；",
              "不怕慢，只怕站。坚持下去，就会到达终点。"],
    "finale": ["从那以后，兔子和乌龟成了好朋友。",
               "他们常常一起，在山坡上看夕阳。"],
}


def wav_dur(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def synth_all(voice=VOICE_ID, out_dir=VOICE_DIR):
    out_dir.mkdir(parents=True, exist_ok=True)
    items = [(sc, i, txt) for sc, ls in LINES.items() for i, txt in enumerate(ls)]

    def one(it):
        sc, i, txt = it
        p = out_dir / f"{sc}_{i}.wav"
        if not p.exists():
            tts(txt, p, voice, speed=SPEED)
        return sc, i, txt, wav_dur(p)

    meta = {}
    with ThreadPoolExecutor(1) as ex:
        for sc, i, txt, d in ex.map(one, items):
            meta.setdefault(sc, []).append(dict(i=i, text=txt, dur=round(d, 3)))
            print(f"{LOG}[{sc}_{i}] {d:.2f}s {txt}", flush=True)
    for sc in meta:
        meta[sc].sort(key=lambda m: m["i"])
    (out_dir / "voice.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "samples":
        d = ROOT / "out" / "voice_samples"
        d.mkdir(parents=True, exist_ok=True)
        text = "森林里，住着一只跑得飞快的兔子，和一只慢慢吞吞的乌龟。"
        for vid, nm in [("Chinese (Mandarin)_Gentle_Senior", "温柔学姐"), ("Chinese (Mandarin)_Warm_Bestie", "温暖闺蜜"),
                        ("Chinese (Mandarin)_Gentleman", "温润男声"), ("Chinese (Mandarin)_Kind-hearted_Elder", "花甲奶奶")]:
            tts(text, d / f"{nm}.wav", vid, speed=SPEED)
            print(f"{LOG} 样本 {nm} 完成")
    else:
        synth_all()
