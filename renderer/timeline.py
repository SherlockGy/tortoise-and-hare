# 全片时间轴：画面、配乐、旁白共用。按“速度 + 小节数”定义每一幕，动作与旁白都用幕内拍号定位

# (幕名, 每分钟拍数, 每小节拍数, 小节数)
SCENES = [
    ("title", 100, 4, 6),       # 片头：兔子飞奔、乌龟慢爬、标题弹出、VS
    ("meet", 100, 4, 10),       # 相遇：兔子嘲笑乌龟，乌龟淡淡应战
    ("challenge", 104, 4, 9),   # 集合：动物围观、猫头鹰宣布路线和规则
    ("start", 120, 4, 4),       # 起跑：各就各位，预备——跑！
    ("sprint", 132, 4, 8),      # 兔子一骑绝尘，乌龟稳稳向前
    ("taunt", 112, 4, 6),       # 兔子得意：躺下吃胡萝卜，睡一觉也来得及
    ("nap", 92, 4, 8),          # 午睡：兔子睡着，乌龟一步一步超过去
    ("pass", 100, 4, 6),        # 超越：乌龟不停步，小动物悄悄加油
    ("wake", 120, 4, 8),        # 惊醒：兔子发现乌龟快到终点，撒腿就追
    ("chase", 132, 4, 9),       # 追赶：兔子全力冲刺，乌龟咬牙坚持
    ("finish", 120, 4, 10),     # 冲线：红丝带落下，乌龟先到，兔子低头
    ("moral", 92, 4, 11),       # 道理：快不如稳，不怕慢只怕站
    ("finale", 150, 3, 20),     # 圆舞曲结尾：夕阳下成为好朋友
]

# 每幕的旁白入点 voice=[(句序号, 起始拍)] 与关键动作拍点
CUES = {
    "title": dict(voice=[(0, 0.7), (1, 11.0)], run=(0.0, 9.0), walk=(1.5, 16.0), vs=19.5),
    "meet": dict(voice=[(0, 0.8), (1, 10.3), (2, 21.7), (3, 27.0)],
                 walk=(0.0, 22.0), hop=(4.0, 8.0), taunt=10.5, look_up=21.7, talk=22.0, nod=28.0, shrug=32.0),
    "challenge": dict(voice=[(0, 0.9), (1, 9.0), (2, 16.6), (3, 27.0)],
                      gather=(1.5, 4.5), owl_talk=9.0, course=16.6, wingup=28.0, crouch=30.0),
    "start": dict(voice=[(0, 0.4), (1, 3.6), (2, 6.8)], close=0.0, go=3.4, burst=4.2),
    "sprint": dict(voice=[(0, 0.9), (1, 9.7), (2, 18.9)], hare_far=18.9, look_back=20.0, exit=27.0),
    "taunt": dict(voice=[(0, 0.6), (1, 10.5), (2, 17.2)], stop=0.6, lie=10.5, eat=12.0, close_eye=20.0),
    "nap": dict(voice=[(0, 0.8), (1, 6.9), (2, 13.0), (3, 19.2)], sleep=0.0, snore=13.0, overtake=(19.2, 30.0)),
    "pass": dict(voice=[(0, 0.7), (1, 7.0), (2, 15.8)], walk=(0.0, 21.0), cheer=15.8, exit=21.0),
    "wake": dict(voice=[(0, 0.8), (1, 8.0), (2, 18.0)], stretch=4.0, open=8.0, sit=10.0, panic=11.0, bolt=24.0),
    "chase": dict(voice=[(0, 0.4), (1, 11.0), (2, 21.8)], run=(0.0, 12.0), tortoise=(11.0, 22.0), finish_vis=21.8),
    "finish": dict(voice=[(0, 0.6), (1, 8.0), (2, 12.8), (3, 23.6)], cross=6.5, cut=7.0, arrive=22.0, trophy=30.0),
    "moral": dict(voice=[(0, 0.6), (1, 8.6), (2, 16.7), (3, 25.5), (4, 31.0)],
                  talk=0.6, answer=8.6, nod=17.0, cards=25.5, wide=31.0),
    "finale": dict(voice=[(0, 2.5), (1, 15.0)], gather=(4.0, 14.0), sit=15.0, end_text=50.0),
}

TAIL = 1.5  # 片尾留白秒数


def build():
    out, t = {}, 0.0
    for name, bpm, bpb, bars in SCENES:
        dur = bars * bpb * 60.0 / bpm
        out[name] = dict(name=name, start=t, bpm=bpm, bpb=bpb, bars=bars, beats=bars * bpb, dur=dur)
        t += dur
    return out, t


TL, TOTAL_SCENES = build()
TOTAL = TOTAL_SCENES + TAIL


def beat_time(scene, beat):
    # 幕内拍号 -> 全片绝对秒数
    s = TL[scene]
    return s["start"] + beat * 60.0 / s["bpm"]


def voice_spans():
    # 每句旁白的 (幕, 句序号, 文本, 起始拍, 结束拍, 绝对起止秒)，用于字幕与混音
    import json
    from pathlib import Path
    meta = json.loads((Path(__file__).resolve().parent.parent / "assets" / "voice" / "voice.json").read_text(encoding="utf-8"))
    out = []
    for sc, cue in CUES.items():
        bpm = TL[sc]["bpm"]
        for i, b0 in cue["voice"]:
            m = meta[sc][i]
            b1 = b0 + m["dur"] * bpm / 60
            out.append(dict(scene=sc, i=i, text=m["text"], b0=b0, b1=b1, t0=beat_time(sc, b0), t1=beat_time(sc, b0) + m["dur"]))
    return out


if __name__ == "__main__":
    for k, v in TL.items():
        print(f"{k:10s} start={v['start']:7.2f}s dur={v['dur']:6.2f}s beats={v['beats']}")
    print("total", TOTAL)
    spans = voice_spans()
    for a, b in zip(spans, spans[1:] + [None]):
        flag = ""
        if a["b1"] > TL[a["scene"]]["beats"]:
            flag += " !!超出本幕"
        if b and b["scene"] == a["scene"] and b["b0"] < a["b1"] + 0.25:
            flag += " !!与下一句重叠"
        print(f"  {a['scene']}_{a['i']} 拍 {a['b0']:5.1f}-{a['b1']:5.1f}{flag}  {a['text']}")
