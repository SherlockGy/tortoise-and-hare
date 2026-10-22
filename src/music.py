# 龟兔赛跑配乐与音效：用 GeneralUser GS 采样音色演奏，程序编曲 + 程序合成音效
# 配器刻意不用金属打击乐（钟琴、铃、三角铁、钢片琴、木琴等）
import random
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import tinysoundfont as tsf
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

from timeline import CUES, TL, TOTAL, beat_time, voice_spans

ROOT = Path(__file__).resolve().parent.parent
SF2 = ROOT / "assets" / "sf" / "GeneralUser-GS.sf2"
OUT = ROOT / "out" / "music.wav"
VOICE_DIR = ROOT / "assets" / "voice"
SR = 44100
LOG = "[music 配乐生成]"
rng = random.Random(11)

# 声部：GM 音色号、音量、声像(-1 左 ~ 1 右)、混响发送量
PARTS = {
    "flute": dict(prog=73, vol=0.68, pan=0.22, rev=0.34),
    "piccolo": dict(prog=72, vol=0.38, pan=0.30, rev=0.30),
    "clarinet": dict(prog=71, vol=0.72, pan=-0.22, rev=0.32),
    "oboe": dict(prog=68, vol=0.60, pan=0.14, rev=0.32),
    "bassoon": dict(prog=70, vol=0.82, pan=-0.10, rev=0.28),
    "horn": dict(prog=60, vol=0.50, pan=-0.32, rev=0.42),
    "trumpet": dict(prog=56, vol=0.48, pan=0.18, rev=0.34),
    "trombone": dict(prog=57, vol=0.52, pan=0.06, rev=0.30),
    "strings": dict(prog=48, vol=0.46, pan=0.0, rev=0.46),
    "trem": dict(prog=44, vol=0.42, pan=0.0, rev=0.46),
    "pizz": dict(prog=45, vol=0.78, pan=-0.14, rev=0.28),
    "bass": dict(prog=45, vol=0.80, pan=0.0, rev=0.22),
    "harp": dict(prog=46, vol=0.66, pan=0.34, rev=0.46),
    "guitar": dict(prog=24, vol=0.42, pan=-0.38, rev=0.30),
    "accordion": dict(prog=21, vol=0.38, pan=-0.18, rev=0.30),
    "timpani": dict(prog=47, vol=0.58, pan=0.0, rev=0.36),
    "cello": dict(prog=42, vol=0.58, pan=-0.16, rev=0.38),
    "viola": dict(prog=41, vol=0.46, pan=0.12, rev=0.40),
}

NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
DUR = {"w": 4, "h": 2, "q": 1, "e": 0.5, "s": 0.25, "t": 0.125}
TOKEN = re.compile(r"^(\[[^\]]+\]|r|[A-G][#b]?-?\d)([whqest])?(\.)?(?::([\d.]+))?$")

CHORDS = {
    "F": "F A C", "C": "C E G", "C7": "C E G Bb", "Dm": "D F A", "Gm": "G Bb D", "Bb": "Bb D F",
    "Am": "A C E", "A7": "A C# E G", "D7": "D F# A C", "Gm7": "G Bb D F", "E7": "E G# B D",
    "Fmaj7": "F A C E", "Dm7": "D F A C", "Am7": "A C E G", "Bb6": "Bb D F G", "Csus4": "C F G",
}


def midi(name):
    m = re.match(r"^([A-G])([#b]?)(-?\d)$", name)
    n = NOTE_BASE[m.group(1)] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)
    return n + (int(m.group(3)) + 1) * 12


def pc(name):
    return midi(name + "4") % 12


def chord_pcs(ch):
    return [pc(x) for x in CHORDS[ch].split()]


def voicing(ch, low, count=3):
    pcs, out, k = chord_pcs(ch), [], low
    while len(out) < count:
        if k % 12 in pcs:
            out.append(k)
        k += 1
    return out


def root(ch, octave):
    return pc(CHORDS[ch].split()[0]) + (octave + 1) * 12


def fifth(ch, octave):
    p = chord_pcs(ch)[2]
    r = root(ch, octave)
    v = p + (octave + 1) * 12
    return v if v > r else v + 12


class Score:
    def __init__(self):
        self.ev = defaultdict(list)

    def note(self, part, t, dur, key, vel, human=True):
        if human:
            t += rng.uniform(-0.006, 0.006)
            vel = max(1, min(127, int(vel + rng.uniform(-4, 4))))
        self.ev[part].append((max(0.0, t), 1, "on", key, vel))
        self.ev[part].append((max(0.0, t + dur), 0, "off", key, 0))

    def cc(self, part, t, ctrl, val):
        self.ev[part].append((t, 0, "cc", ctrl, int(val)))

    def cc_ramp(self, part, t0, t1, ctrl, v0, v1, steps=24):
        for i in range(steps + 1):
            a = i / steps
            self.cc(part, t0 + (t1 - t0) * a, ctrl, v0 + (v1 - v0) * a)

    def bend(self, part, t0, t1, semis_from, semis_to, rng_semis=12, steps=40):
        self.ev[part].append((t0 - 0.001, 0, "pbr", rng_semis, 0))
        for i in range(steps + 1):
            a = i / steps
            s = semis_from + (semis_to - semis_from) * a
            self.ev[part].append((t0 + (t1 - t0) * a, 0, "pb", int(8192 + s / rng_semis * 8191), 0))

    def seq(self, part, scene, beat, text, vel=85, legato=0.92, transpose=0):
        bpm = TL[scene]["bpm"]
        for tok in text.split():
            m = TOKEN.match(tok)
            if not m:
                raise ValueError(f"无法解析音符: {tok}")
            pitch, d, dot, num = m.groups()
            dur = float(num) if num else DUR[d or "q"] * (1.5 if dot else 1)
            if pitch != "r":
                keys = [midi(x.strip()) for x in pitch.strip("[]").split(",")] if pitch.startswith("[") else [midi(pitch)]
                t = beat_time(scene, beat)
                for k in keys:
                    self.note(part, t, dur * 60 / bpm * legato, k + transpose, vel)
            beat += dur
        return beat

    def at(self, scene, beat):
        return beat_time(scene, beat)

    def oompah(self, bass, chord_part, scene, beat, chords, vel=68, bass_oct=2, low=53, bpb=4):
        bpm = TL[scene]["bpm"]
        spb = 60 / bpm
        for ch, n in chords:
            for i in range(int(n)):
                b = beat + i
                t = beat_time(scene, b)
                pos = round(b) % bpb
                if pos == 0:
                    self.note(bass, t, spb * 0.78, root(ch, bass_oct), vel + 8)
                elif bpb == 4 and pos == 2:
                    self.note(bass, t, spb * 0.78, fifth(ch, bass_oct), vel + 2)
                else:
                    for k in voicing(ch, low):
                        self.note(chord_part, t, spb * 0.42, k, vel - 8)
            beat += n
        return beat

    def arp(self, part, scene, beat, chords, vel=58, low=53, step=0.5, pattern=(0, 1, 2, 3, 2, 1, 0, 1)):
        bpm = TL[scene]["bpm"]
        for ch, n in chords:
            notes = voicing(ch, low, 4)
            for i in range(int(n / step)):
                k = notes[pattern[i % len(pattern)] % len(notes)]
                self.note(part, beat_time(scene, beat + i * step), step * 60 / bpm * 1.6, k, vel)
            beat += n
        return beat

    def pad(self, part, scene, beat, chords, vel=52, low=53, count=3):
        bpm = TL[scene]["bpm"]
        for ch, n in chords:
            for k in voicing(ch, low, count):
                self.note(part, beat_time(scene, beat), n * 60 / bpm * 0.98, k, vel, human=False)
            beat += n
        return beat

    def gliss(self, part, scene, beat, start, end, beats, vel=68, scale=(0, 2, 4, 5, 7, 9, 11), tonic=5):
        keys = [k for k in range(min(start, end), max(start, end) + 1) if (k - tonic) % 12 in scale]
        if start > end:
            keys = keys[::-1]
        bpm = TL[scene]["bpm"]
        step = beats / len(keys)
        for i, k in enumerate(keys):
            self.note(part, beat_time(scene, beat + i * step), max(step * 60 / bpm * 3, 0.15), k, vel, human=False)


# ---------------- 主题素材 ----------------
# 兔子：轻快、跳跃、爱炫耀（F 大调）
HARE_A = ["C5e F5e A5e G5e F5q C5q", "D5e G5e Bb5e A5e G5q D5q",
          "C5e F5e A5e C6e Bb5q A5q", "G5e F5e E5e D5e C5h"]
HARE_B = ["F5e A5e C6e A5e F5q C5q", "D5e F5e Bb5e F5e D5h",
          "C5e E5e G5e Bb5e A5q G5q", "F5h C5q rq"]
HARE_TEASE = ["F5s F5s r F5s F5s r F5e G5e F5q", "Bb5s Bb5s r Bb5s Bb5s r Bb5e C6e Bb5q"]
# 乌龟：沉稳、温暖、一步一个脚印
TORTOISE_A = ["F3q A3q C4q A3q", "G3q Bb3q D4q Bb3q", "F3q A3q C4q F4q", "C3h F3h"]
TORTOISE_B = ["Bb2q D3q F3q D3q", "C3q E3q G3q E3q", "F3q A3q C4q A3q", "F3w"]
TORTOISE_END = ["Bb3h C4h", "F3w"]
# 午睡与温柔段落
NAP_A = ["A4h C5q D5q", "C5h A4h", "Bb4h D5q C5q", "A4w"]
MORAL_A = ["A4h C5q D5q", "C5h A4h", "Bb4q A4q G4q F4q", "F4w"]
# 结尾圆舞曲（3/4）
WALTZ = ["F5q A5q C6q", "Bb5h A5q", "G5q F5q E5q", "F5h.",
         "D5q F5q Bb5q", "A5h G5q", "F5q E5q D5q", "C5h.",
         "F5q A5q C6q", "D6h C6q", "Bb5q A5q G5q", "A5h.",
         "G5q Bb5q D6q", "C6h A5q", "G5q F5q E5q", "F5h."]
WALTZ_C = ["F", "Bb", "C7", "F", "Dm", "Gm", "C7", "F", "F", "Bb", "C7", "F", "Gm", "C7", "C7", "F"]


def melody(S, part, scene, beat, bars, vel=88, transpose=0, legato=0.92):
    for bar in bars:
        beat = S.seq(part, scene, beat, bar, vel, legato, transpose)
    return beat


# ---------------- 音效（非金属） ----------------
class Sfx:
    def __init__(self, n):
        self.buf = np.zeros((n, 2), np.float32)
        self.nrng = np.random.default_rng(7)

    def add(self, t, sig, gain=1.0, pan=0.0):
        i = int(t * SR)
        if i < 0 or i >= len(self.buf):
            return
        if sig.ndim == 1:
            sig = np.stack([sig * (1 - max(0, pan)), sig * (1 + min(0, pan))], 1)
        j = min(len(self.buf), i + len(sig))
        if j > i:
            self.buf[i:j] += sig[: j - i] * gain

    def step(self, t, gain=0.10, low=False):
        # 兔子：轻快的纸片脚步；乌龟：低低的闷响
        n = int((0.16 if not low else 0.24) * SR)
        x = np.arange(n) / SR
        if low:
            y = np.sin(2 * np.pi * 92 * x * (1 - 0.25 * x)) * np.exp(-x / 0.06)
            y += 0.5 * sosfilt(butter(2, [80, 500], "bandpass", fs=SR, output="sos"),
                               self.nrng.standard_normal(n)) * np.exp(-x / 0.035)
        else:
            y = sosfilt(butter(2, [900, 4200], "bandpass", fs=SR, output="sos"),
                        self.nrng.standard_normal(n)) * np.exp(-x / 0.022)
            y += 0.5 * np.sin(2 * np.pi * 220 * x) * np.exp(-x / 0.03)
        self.add(t, (y / (np.abs(y).max() + 1e-9)).astype(np.float32), gain, 0.1 if not low else -0.1)

    def whoosh(self, t0, t1, gain=0.16, f0=420, f1=2400):
        n = int((t1 - t0) * SR)
        if n <= 0:
            return
        noise = self.nrng.standard_normal(n)
        y = np.zeros(n)
        blk = 1024
        for s0 in range(0, n, blk):
            fc = f0 + (f1 - f0) * s0 / n
            seg_ = sosfilt(butter(2, [fc * 0.7, fc * 1.4], "bandpass", fs=SR, output="sos"),
                           noise[max(0, s0 - 256):s0 + blk])
            y[s0:s0 + blk] = seg_[-(min(blk, n - s0)):]
        env = np.sin(np.pi * np.arange(n) / n)
        self.add(t0, (y * env / (np.abs(y).max() + 1e-9)).astype(np.float32), gain)

    def snore(self, t, dur=1.6, gain=0.16):
        # 呼——呼——：低频气流 + 轻微哨音
        n = int(dur * SR)
        x = np.arange(n) / SR
        breath = sosfilt(butter(2, [120, 900], "bandpass", fs=SR, output="sos"), self.nrng.standard_normal(n))
        env = np.exp(-((x - dur * 0.3) / (dur * 0.18)) ** 2) + 0.75 * np.exp(-((x - dur * 0.75) / (dur * 0.16)) ** 2)
        whistle = 0.08 * np.sin(2 * np.pi * (170 + 15 * np.sin(2 * np.pi * 1.2 * x)) * x) * env
        y = breath * env + whistle
        self.add(t, (y / (np.abs(y).max() + 1e-9)).astype(np.float32), gain, 0.0)

    def cheer(self, t, dur=3.2, gain=0.22):
        # 森林动物欢呼：密集纸拍手 + 人群气声 + 一声口哨
        n = int(dur * SR)
        x = np.arange(n) / SR
        bed = sosfilt(butter(2, [350, 2600], "bandpass", fs=SR, output="sos"), self.nrng.standard_normal(n))
        bed *= np.minimum(1, x / 0.25) * np.minimum(1, (dur - x) / 0.6) * 0.40
        y = bed
        for i in range(int(dur * 11)):
            c = self.nrng.uniform(0.02, dur - 0.12)
            m = (x > c) & (x < c + 0.055)
            y[m] += self.nrng.uniform(0.5, 1.0) * sosfilt(butter(2, [900, 5500], "bandpass", fs=SR, output="sos"),
                                                         self.nrng.standard_normal(m.sum())) * np.exp(-(x[m] - c) / 0.012)
        wh = 0.18 * np.sin(2 * np.pi * (1200 + 500 * x / dur) * x) * np.exp(-((x - dur * 0.55) / 0.22) ** 2)
        y += wh
        self.add(t, (y / (np.abs(y).max() + 1e-9)).astype(np.float32), gain, 0.0)

    def whistle(self, t, gain=0.18):
        # 猫头鹰的木头哨子
        n = int(0.65 * SR)
        x = np.arange(n) / SR
        f = 1900 - 550 * x / x[-1] + 50 * np.sin(2 * np.pi * 26 * x)
        y = np.sin(2 * np.pi * f * x) * np.exp(-x / 0.22)
        y += 0.3 * sosfilt(butter(2, [1400, 4000], "bandpass", fs=SR, output="sos"),
                           self.nrng.standard_normal(n)) * np.exp(-x / 0.08)
        self.add(t, (y / (np.abs(y).max() + 1e-9)).astype(np.float32), gain)

    def tick(self, t, gain=0.06):
        n = int(0.06 * SR)
        x = np.arange(n) / SR
        y = np.sin(2 * np.pi * 1800 * x) * np.exp(-x / 0.008) + 0.5 * np.sin(2 * np.pi * 3200 * x) * np.exp(-x / 0.004)
        self.add(t, (y / (np.abs(y).max() + 1e-9)).astype(np.float32), gain, 0.2)

    def snap(self, t, gain=0.20):
        # 红丝带断开：纸片撕裂
        n = int(0.35 * SR)
        x = np.arange(n) / SR
        y = sosfilt(butter(2, [1200, 8000], "bandpass", fs=SR, output="sos"),
                    self.nrng.standard_normal(n)) * np.exp(-x / 0.05)
        self.add(t, (y / (np.abs(y).max() + 1e-9)).astype(np.float32), gain, 0.0)

    def chirp(self, t, gain=0.05, seed=0):
        n = int(0.22 * SR)
        x = np.arange(n) / SR
        f0 = 2200 + 500 * ((seed % 5) / 5)
        f = f0 + 900 * x / x[-1] + 120 * np.sin(2 * np.pi * 18 * x)
        y = np.sin(2 * np.pi * f * x) * np.sin(np.pi * x / x[-1]) ** 2
        self.add(t, y.astype(np.float32), gain, 0.4 * (1 if seed % 2 else -1))

    def breeze(self, t0, t1, gain=0.035):
        n = int((t1 - t0) * SR)
        if n <= 0:
            return
        x = np.arange(n) / SR
        y = sosfilt(butter(2, [200, 1400], "bandpass", fs=SR, output="sos"), self.nrng.standard_normal(n))
        y *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.12 * x + 0.5)
        env = np.minimum(1, x / 1.2) * np.minimum(1, (x[-1] - x) / 1.2)
        self.add(t0, (y * env / (np.abs(y).max() + 1e-9)).astype(np.float32), gain, 0.0)

    def heartbeat(self, t, gain=0.10):
        for k, dt in enumerate((0.0, 0.17)):
            n = int(0.18 * SR)
            x = np.arange(n) / SR
            y = np.sin(2 * np.pi * (68 - 10 * k) * x) * np.exp(-x / 0.05)
            self.add(t + dt, (y / (np.abs(y).max() + 1e-9)).astype(np.float32), gain * (1 - 0.3 * k))


# ---------------- 各幕编曲 ----------------
def compose():
    S = Score()
    n = int((TOTAL + 2) * SR)
    fx = Sfx(n)

    def hare(sc, beat, bars=HARE_A, part="flute", vel=88, transpose=0):
        return melody(S, part, sc, beat, bars, vel, transpose)

    def tortoise(sc, beat, bars=TORTOISE_A, part="bassoon", vel=84, transpose=0):
        return melody(S, part, sc, beat, bars, vel, transpose=0, legato=0.72)

    def race_bass(sc, b0, b1, ch=("F", "C"), vel=70):
        b, i = b0, 0
        while b < b1 - 0.01:
            k = root(ch[i % 2], 2)
            S.note("bass", S.at(sc, b), 0.22, k, vel)
            b += 0.5
            i += 1

    def steps(sc, t0, t1, gap=0.5, gain=0.10, low=False):
        t = t0
        while t < t1:
            fx.step(t, gain, low)
            t += gap

    # ===== 片头：明亮的开场 + 兔子的飞奔 + 乌龟的低音 =====
    sc, C = "title", CUES["title"]
    S.seq("strings", sc, 0, "[F3,A3,C4,F4]w", 92)
    S.seq("pizz", sc, 0, "[F2,C3]q [F2,C3]q", 96)
    S.note("timpani", S.at(sc, 0), 0.8, midi("F2"), 88, human=False)
    S.gliss("harp", sc, 0, midi("F3"), midi("F6"), 1.2, vel=62)
    melody(S, "flute", sc, 0.6, HARE_A[:2], 88)
    S.seq("bassoon", sc, 1.2, "F2h A2h", 70, legato=0.8)
    S.seq("cello", sc, 1.2, "C3h F2h", 58, legato=0.9)
    S.pad("strings", sc, 1.0, [("Dm", 4), ("Bb", 4)], vel=30, low=53)
    melody(S, "clarinet", sc, 11.0, ["A4h C5h", "D5h C5h"], 62)
    melody(S, "bassoon", sc, 16.0, TORTOISE_A[:2], 76)
    S.seq("strings", sc, C["vs"], "[F3,A3,C4,F4]q", 108)
    S.note("timpani", S.at(sc, C["vs"]), 0.6, midi("F2"), 96, human=False)
    S.seq("piccolo", sc, C["vs"] + 0.6, "F6s E6s D6s C6s Bb5s A5s G5s F5s", 48, legato=0.5)

    # ===== 相遇：兔子炫耀，乌龟淡淡回应 =====
    sc, C = "meet", CUES["meet"]
    melody(S, "flute", sc, 0, HARE_A, 86)
    S.oompah("bass", "pizz", sc, 0, [("F", 4), ("C7", 4), ("Dm", 4), ("Bb", 4)], vel=62)
    S.arp("guitar", sc, 0, [("F", 4), ("C7", 4), ("Dm", 4), ("Bb", 4)], vel=38, low=57)
    melody(S, "piccolo", sc, C["taunt"], HARE_TEASE * 2, 46, legato=0.45)
    S.seq("bassoon", sc, C["taunt"] + 1, "F2e r F2e r F2q rq", 72, legato=0.4)
    S.seq("strings", sc, C["look_up"], "[D4,F4,A4]h", 44)
    melody(S, "bassoon", sc, C["talk"], TORTOISE_A[:2], 78)
    S.seq("cello", sc, C["talk"], "F2h C3h", 58, legato=0.9)
    melody(S, "clarinet", sc, C["nod"] + 0.4, TORTOISE_A[2:], 76)
    S.pad("strings", sc, C["nod"], [("Bb", 4), ("C7", 4), ("F", 4)], vel=32, low=57)
    S.seq("harp", sc, C["shrug"], "C5e F5e A5e F5e", 58)

    # ===== 集合与规则：小进行曲 =====
    sc, C = "challenge", CUES["challenge"]
    S.oompah("bass", "pizz", sc, 0, [("F", 2), ("C7", 2), ("F", 2), ("C7", 2)], vel=66)
    melody(S, "flute", sc, 0, ["C5e F5e A5e C6e F6q rq", "E6e D6e C6e Bb5e A5q G5q"], 78)
    S.seq("strings", sc, 0, "[F3,A3]e r [C4,E4]e r", 54)
    melody(S, "horn", sc, C["owl_talk"], ["F3h A3h", "C4h A3h"], 52, legato=0.85)
    S.seq("bassoon", sc, C["owl_talk"], "F2q C3q F3q C3q", 72, legato=0.55)
    S.seq("oboe", sc, C["owl_talk"] + 2, "C5q D5q C5q Bb4q", 58)
    S.gliss("harp", sc, C["course"] - 0.4, midi("F4"), midi("F6"), 1.0, vel=54)
    melody(S, "flute", sc, C["course"], ["A5e G5e F5e E5e D5e C5e Bb4e A4e", "G4e A4e Bb4e C5e F5h"], 62)
    S.pad("strings", sc, C["course"], [("Dm", 4), ("Bb", 4), ("C7", 4)], vel=32, low=53)
    for i in range(6):   # 倒计时鼓点
        S.note("timpani", S.at(sc, C["wingup"] + i * 0.5), 0.16, midi("F2"), 70 + i * 5, human=False)
    S.seq("trem", sc, C["wingup"], "[F4,A4,C5]h", 72)
    S.seq("strings", sc, C["wingup"], "[F3,A3,C4]h", 58)
    S.seq("piccolo", sc, C["wingup"] + 2, "F6s E6s F6s G6s A6s G6s F6s E6s", 42, legato=0.5)

    # ===== 起跑：秒表、哨声、爆发 =====
    sc, C = "start", CUES["start"]
    for i in range(6):
        fx.tick(S.at(sc, 0.0) + i * 0.32, 0.05)
    S.seq("pizz", sc, 0, "F2e r F2e r F2e r C3e r", 72, legato=0.5)
    S.seq("strings", sc, 0, "[F3,A3]h", 46)
    fx.whistle(S.at(sc, 3.4), 0.18)
    S.note("timpani", S.at(sc, 4.2), 0.7, midi("F2"), 104, human=False)
    fx.whoosh(S.at(sc, 4.1), S.at(sc, 5.0), gain=0.20, f0=300, f1=3000)
    race_bass(sc, 4.2, 16, vel=76)
    melody(S, "flute", sc, 4.2, HARE_A[:2], 92)
    S.seq("strings", sc, 4.2, "[F3,A3,C4]e [F3,A3,C4]e [G3,Bb3,D4]e [G3,Bb3,D4]e", 58)
    steps(S.at(sc, 4.2), S.at(sc, 9), 0.28, 0.08)
    fx.breeze(S.at(sc, 0), S.at(sc, 8), 0.03)

    # ===== 一骑绝尘：兔子主题 → 乌龟主题 → 回头嘲笑 =====
    sc, C = "sprint", CUES["sprint"]
    race_bass(sc, 0, 9.2, vel=78)
    melody(S, "flute", sc, 0, HARE_A, 94)
    S.oompah("bass", "pizz", sc, 0, [("F", 4), ("C7", 4)], vel=66)
    steps(S.at(sc, 0), S.at(sc, 9), 0.26, 0.075)
    melody(S, "bassoon", sc, 9.7, TORTOISE_A[:2], 78)
    S.seq("cello", sc, 9.7, "F2w C3w", 56, legato=0.95)
    S.arp("harp", sc, 9.7, [("F", 4), ("C7", 4)], vel=38, low=57)
    steps(S.at(sc, 9.7), S.at(sc, 18), 0.55, 0.07, low=True)
    melody(S, "piccolo", sc, C["hare_far"], HARE_TEASE, 50, legato=0.5)
    S.seq("bassoon", sc, C["hare_far"] + 0.5, "F2e r F2e r F2h", 68, legato=0.45)
    S.seq("pizz", sc, C["hare_far"], "C4e F4e", 60)
    S.pad("strings", sc, C["exit"], [("C7", 4)], vel=34, low=55)

    # ===== 得意忘形：懒洋洋的下午 =====
    sc, C = "taunt", CUES["taunt"]
    melody(S, "clarinet", sc, 0, ["A4q. C5e D5q C5q", "A4h F4h", "G4q A4q Bb4q C5q"], 66)
    S.arp("guitar", sc, 0, [("F", 4), ("Dm", 4), ("Bb", 4)], vel=40, low=55, pattern=(0, 1, 2, 1))
    S.oompah("bass", "pizz", sc, 0, [("F", 4), ("Dm", 4), ("Bb", 4)], vel=54)
    melody(S, "piccolo", sc, C["lie"], ["F5s F5s r F5e F5e rq"], 44, legato=0.5)
    S.gliss("harp", sc, C["lie"], midi("C5"), midi("F6"), 0.8, vel=52)
    melody(S, "flute", sc, 12.0, ["C5e A4e F4e A4e C5q rq"], 58)
    S.seq("bassoon", sc, 12.0, "F2e r F2e r F2h", 64, legato=0.45)
    melody(S, "bassoon", sc, C["close_eye"], ["F2q. A2e C3q A2q"], 58, legato=0.6)
    S.seq("pizz", sc, C["close_eye"], "F2e C3e F2e C3e", 52)

    # ===== 午睡：摇篮曲，乌龟从身边走过 =====
    sc, C = "nap", CUES["nap"]
    CH_N = [("F", 4), ("Dm", 4), ("Bb", 4), ("C7", 4), ("F", 4), ("Dm", 4), ("Gm", 4), ("C7", 4)]
    S.pad("strings", sc, 0, CH_N, vel=30, low=55)
    S.arp("harp", sc, 0, CH_N, vel=38, low=53, step=1.0, pattern=(0, 1, 2, 3, 2, 1))
    melody(S, "clarinet", sc, 0, NAP_A, 62, legato=0.95)
    S.seq("cello", sc, 0, "F2w Bb2w C3w F2w", 46, legato=1.0)
    steps(S.at(sc, 0), S.at(sc, 8), 1.2, 0.03, low=True)
    for i, tb in enumerate((2.0, 6.5, 11.0)):
        fx.chirp(S.at(sc, tb), 0.035, seed=i)
    fx.breeze(S.at(sc, 0), S.at(sc, 20), 0.03)
    o0, o1 = C["overtake"]
    melody(S, "bassoon", sc, o0, TORTOISE_A[:2], 68)
    S.seq("cello", sc, o0, "F2w C3w", 48, legato=1.0)
    steps(S.at(sc, o0), S.at(sc, o1), 0.7, 0.065, low=True)
    S.pad("strings", sc, o0, [("Bb", 4), ("C7", 4), ("F", 4)], vel=34, low=55)
    for i in range(3):
        fx.snore(S.at(sc, C["snore"]) + i * 3.1, 1.7, 0.13)

    # ===== 超越：乌龟主题逐渐坚定 =====
    sc, C = "pass", CUES["pass"]
    CH_P = [("F", 4), ("Bb", 4), ("F", 4), ("C7", 4), ("Dm", 4), ("Bb", 4)]
    S.pad("strings", sc, 0, CH_P, vel=36, low=55)
    S.seq("cello", sc, 0, "F3w Bb2w F3w C3w D3w Bb2w", 54, legato=1.0)
    melody(S, "bassoon", sc, 0, TORTOISE_A, 76)
    melody(S, "clarinet", sc, 8, TORTOISE_B[:2], 64)
    S.seq("pizz", sc, 0, "F2e C3e F2e C3e Bb2e F2e Bb2e F2e", 54)
    steps(S.at(sc, 0), S.at(sc, 21), 0.62, 0.07, low=True)
    melody(S, "flute", sc, C["cheer"], ["C6e A5e F5e A5e C6q rq", "D6e C6e Bb5e A5e G5q F5q"], 52)
    S.seq("pizz", sc, C["cheer"], "C4e F4e A4e F4e", 58)
    S.gliss("harp", sc, C["cheer"] + 0.4, midi("F4"), midi("F6"), 0.8, vel=56)
    S.seq("timpani", sc, C["exit"], "F2q C3q", 54, legato=0.8)

    # ===== 惊醒：从摇篮曲到惊慌 =====
    sc, C = "wake", CUES["wake"]
    S.arp("harp", sc, 0, [("F", 4), ("Dm", 4)], vel=32, low=53)
    melody(S, "clarinet", sc, 0, ["A4h C5h", "F4h."], 52)
    for i in range(2):
        fx.snore(S.at(sc, 0) + i * 2.4, 1.5, 0.10)
    S.note("timpani", S.at(sc, C["open"]), 0.7, midi("F2"), 88, human=False)
    S.seq("trem", sc, C["open"], "[C#4,G4,Bb4]h", 82)
    S.seq("strings", sc, C["open"], "[C#3,G3,Bb3]h", 62)
    for i in range(5):
        S.note("timpani", S.at(sc, C["open"] + 0.4 + i * 0.25), 0.12, midi("C2"), 66, human=False)
    melody(S, "piccolo", sc, C["panic"], ["G6s F#6s F6s E6s Eb6s D6s C#6s C6s", "B5s Bb5s A5s Ab5s G5s F#5s F5s E5s"], 44, legato=0.9)
    S.seq("trem", sc, C["panic"], "[D4,F4,Ab4]h", 70)
    S.seq("bass", sc, C["panic"], "D2w Eb2w", 54)
    fx.heartbeat(S.at(sc, C["panic"]), 0.10)
    fx.heartbeat(S.at(sc, C["panic"] + 0.9), 0.10)
    fx.whoosh(S.at(sc, C["bolt"]), S.at(sc, C["bolt"] + 0.8), gain=0.16, f0=300, f1=2600)
    race_bass(sc, 24, 32, vel=74)
    melody(S, "flute", sc, 24, HARE_A[:1], 86)
    steps(S.at(sc, 24), S.at(sc, 32), 0.26, 0.075)

    # ===== 追赶：全片最快的段落 =====
    sc, C = "chase", CUES["chase"]
    race_bass(sc, 0, 36, vel=82)
    S.seq("strings", sc, 0, "[F3,A3,C4]e [F3,A3,C4]e [G3,Bb3,D4]e [G3,Bb3,D4]e", 66)
    melody(S, "horn", sc, 0, ["F3h C3h", "F3h C3h"], 62, legato=0.8)
    for i in range(18):
        S.note("timpani", S.at(sc, i * 2), 0.20, midi("F2"), 72 + (i % 4) * 4, human=False)
    melody(S, "flute", sc, 4, HARE_A[:2], 92)
    melody(S, "bassoon", sc, C["tortoise"][0], TORTOISE_A[:2], 82)
    S.seq("cello", sc, C["tortoise"][0], "F2w C3w", 56, legato=1.0)
    melody(S, "clarinet", sc, 17, ["C5h D5h", "E5h F5h"], 62)
    steps(S.at(sc, 0), S.at(sc, 20), 0.25, 0.075)
    steps(S.at(sc, 11), S.at(sc, 33), 0.62, 0.07, low=True)
    S.seq("trem", sc, 26, "[F4,A4,C5]w [G4,Bb4,D5]w", 58)
    melody(S, "trombone", sc, 28, ["F2h C3h", "F2w"], 60, legato=0.9)
    S.seq("strings", sc, 30, "F4e G4e A4e Bb4e C5e D5e E5e F5e", 72)
    for i in range(8):
        S.note("timpani", S.at(sc, 30 + i * 0.5), 0.12, midi("F2"), 70 + i * 6, human=False)
    fx.heartbeat(S.at(sc, 20), 0.10)
    fx.heartbeat(S.at(sc, 24), 0.11)
    fx.heartbeat(S.at(sc, 28), 0.12)

    # ===== 冲线：红丝带、欢呼、兔子低头 =====
    sc, C = "finish", CUES["finish"]
    for i in range(12):
        S.note("timpani", S.at(sc, i * 0.5), 0.12, midi("F2"), 60 + i * 3, human=False)
    S.seq("strings", sc, 0, "F4e G4e A4e Bb4e C5e D5e E5e F5e", 60)
    S.seq("trem", sc, 0, "[F4,A4,C5]w", 54)
    S.note("timpani", S.at(sc, C["cross"]), 0.9, midi("F2"), 104, human=False)
    fx.snap(S.at(sc, C["cut"]), 0.22)
    S.seq("trumpet", sc, C["cut"], "C5e C5e C5q F5q A5q. G5e F5q C5q", 84)
    S.seq("horn", sc, C["cut"], "[F3,A3,C4]h", 72)
    S.seq("trombone", sc, C["cut"], "F2q C3q F2h", 70)
    fx.cheer(S.at(sc, C["cut"]), 3.4, 0.20)
    S.oompah("bass", "pizz", sc, 8, [("F", 4), ("Bb", 4)], vel=68)
    melody(S, "flute", sc, 9, ["F5q A5q C6q F6q", "E6q D6q C6q A5q"], 84)
    S.seq("harp", sc, 12, "C6e A5e F5e C5e", 60)
    S.seq("strings", sc, 12.8, "[F3,A3,C4]w [D3,F3,A3]w", 50)
    melody(S, "clarinet", sc, 22, ["D5h C5h", "Bb4h A4h", "G4h F4h"], 56)
    S.seq("cello", sc, 22, "D3w Bb2w F2w", 48, legato=1.0)
    melody(S, "bassoon", sc, 30, TORTOISE_END, 66)
    S.pad("strings", sc, 30, [("F", 6), ("Bb", 4)], vel=38, low=55)

    # ===== 道理：温暖、简单、像睡前故事 =====
    sc, C = "moral", CUES["moral"]
    S.pad("strings", sc, 0, [("Dm", 4), ("Bb", 4), ("F", 4), ("C7", 4)], vel=30, low=53)
    melody(S, "clarinet", sc, 0, ["D5h C5h", "Bb4h A4h"], 58)
    melody(S, "cello", sc, 8.6, TORTOISE_A[:2], 60)
    S.seq("bass", sc, 8.6, "F2w C3w", 46)
    melody(S, "flute", sc, 16.7, ["C5q D5q E5q F5q", "G5h F5h"], 56)
    S.pad("strings", sc, 16.7, [("Bb", 4), ("C7", 4)], vel=34, low=55)
    S.gliss("harp", sc, C["cards"], midi("F4"), midi("F6"), 0.8, vel=52)
    S.seq("harp", sc, C["cards"] + 0.4, "F5q A5q C6q F6q", 54)
    S.pad("strings", sc, C["wide"], [("F", 5), ("Bb", 4), ("F", 4)], vel=40, low=53)
    melody(S, "viola", sc, C["wide"], ["A4h C5h", "D5h F5h"], 52)
    S.seq("flute", sc, C["wide"] + 2, "A5h G5h F5h E5h D5w", 50)
    S.seq("bass", sc, C["wide"], "F2w C3w F2w", 52)

    # ===== 圆舞曲结尾 =====
    sc, C = "finale", CUES["finale"]
    melody(S, "accordion", sc, 0, WALTZ, 74)
    melody(S, "flute", sc, 0, WALTZ[:8], 64)
    melody(S, "flute", sc, 24, WALTZ[8:], 74, transpose=12)
    S.oompah("bass", "pizz", sc, 0, [(c, 3) for c in WALTZ_C], vel=60, bpb=3, low=55)
    S.pad("strings", sc, 0, [(c, 3) for c in WALTZ_C[:8]], vel=26, low=60)
    S.pad("strings", sc, 24, [(c, 3) for c in WALTZ_C[8:]], vel=34, low=60)
    S.seq("clarinet", sc, 24, "A4h. A4h. F4h. A4h. G4h. F4h. E4h. A4h.", 54)
    S.arp("harp", sc, 36, [("F", 3), ("Bb", 3), ("F", 6), ("C7", 3), ("F", 6)], vel=56, low=53,
          step=0.5, pattern=(0, 1, 2, 3, 4, 5, 4, 3))
    S.pad("strings", sc, 48, [("F", 6), ("Bb", 3), ("F", 3)], vel=42, low=53, count=4)
    S.seq("flute", sc, 48, "A5h. C6h. F6:6", 54)
    S.seq("bass", sc, 48, "F2h. Bb1h. F1:6", 60)
    S.cc_ramp("strings", S.at(sc, 54), S.at(sc, 60) + 1.2, 11, 127, 24)
    S.cc_ramp("flute", S.at(sc, 54), S.at(sc, 60) + 1.2, 11, 127, 24)

    # ===== 环境音与步点 =====
    for nm in ("title", "meet", "challenge", "start", "sprint", "taunt", "nap", "pass", "wake", "chase", "finish"):
        st = TL[nm]["start"]
        fx.breeze(st, st + TL[nm]["dur"], 0.022)
    for i, tb in enumerate((3.0, 9.0, 16.0, 35.0, 42.0)):
        fx.chirp(TL["meet"]["start"] + tb, 0.035, seed=i)
    fx.cheer(TL["challenge"]["start"] + 4.0, 2.0, 0.07)
    return S, fx, n


def render_part(name, spec, events, n, sfbytes):
    syn = tsf.Synth(samplerate=SR)
    sfid = syn.sfload(sfbytes)
    syn.program_select(0, sfid, spec.get("bank", 0), spec["prog"], spec.get("drums", False))
    out = np.zeros((n, 2), np.float32)
    pos = 0
    for t, _, kind, a, b in sorted(events, key=lambda e: (e[0], e[1])):
        s = min(n, int(t * SR))
        if s > pos:
            out[pos:s] = np.frombuffer(syn.generate_simple(s - pos), np.float32).reshape(-1, 2)
            pos = s
        if kind == "on":
            syn.noteon(0, a, b)
        elif kind == "off":
            syn.noteoff(0, a)
        elif kind == "cc":
            syn.control_change(0, a, b)
        elif kind == "pb":
            syn.pitchbend(0, a)
        elif kind == "pbr":
            syn.pitchbend_range(0, a)
    if pos < n:
        out[pos:] = np.frombuffer(syn.generate_simple(n - pos), np.float32).reshape(-1, 2)
    return out


def reverb_ir(seconds=2.4):
    m = int(seconds * SR)
    g = np.random.default_rng(19)
    x = np.arange(m) / SR
    ir = np.zeros((m, 2))
    lp = butter(1, 5000, "lowpass", fs=SR, output="sos")
    for c in range(2):
        noise = sosfilt(lp, g.standard_normal(m))
        ir[:, c] = noise * np.exp(-x * 6.9 / 1.9)
    ir[: int(0.022 * SR)] = 0
    return ir / np.sqrt((ir ** 2).sum(0))


def main():
    S, fx, n = compose()
    sfbytes = SF2.read_bytes()
    dry = np.zeros((n, 2), np.float32)
    send = np.zeros((n, 2), np.float32)
    for name, evs in S.ev.items():
        spec = PARTS[name]
        y = render_part(name, spec, evs, n, sfbytes)
        p = spec["pan"]
        y[:, 0] *= np.sqrt((1 - p) / 2) * 1.414
        y[:, 1] *= np.sqrt((1 + p) / 2) * 1.414
        y *= spec["vol"]
        dry += y
        send += y * spec["rev"]
        print(f"{LOG}[{name}] 事件数={len(evs)}", flush=True)
    ir = reverb_ir()
    wet = np.stack([fftconvolve(send[:, c], ir[:, c])[:n] for c in range(2)], 1).astype(np.float32)
    mix = dry + wet * 0.9 + fx.buf
    mix = sosfilt(butter(2, 35, "highpass", fs=SR, output="sos"), mix, axis=0)

    # 母带：归一化 + 软限幅
    mix = mix / (np.percentile(np.abs(mix), 99.95) + 1e-9) * 0.7
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    mix *= 10 ** (-1.5 / 20) / max(1e-9, np.abs(mix).max())

    # 旁白：按时间点铺入；有人声时背景音乐自动压低约 8 dB
    voice = np.zeros(len(mix), np.float32)
    mark = np.zeros(len(mix), np.float32)
    for sp in voice_spans():
        sr_v, v = wavfile.read(VOICE_DIR / f"{sp['scene']}_{sp['i']}.wav")
        v = v.astype(np.float32)
        if v.ndim > 1:
            v = v.mean(1)
        if np.abs(v).max() > 2:
            v /= 32768.0
        if sr_v != SR:
            v = np.interp(np.arange(int(len(v) * SR / sr_v)) * sr_v / SR, np.arange(len(v)), v).astype(np.float32)
        i0 = int(sp["t0"] * SR)
        j = min(len(voice), i0 + len(v))
        voice[i0:j] += v[: j - i0]
        mark[max(0, i0 - int(0.25 * SR)):min(len(mix), j + int(0.45 * SR))] = 1
    k = int(0.2 * SR)
    env = 1 - 0.60 * np.convolve(mark, np.ones(k) / k, mode="same")
    voice = sosfilt(butter(2, 80, "highpass", fs=SR, output="sos"), voice)
    voice *= 0.86 / (np.percentile(np.abs(voice[np.abs(voice) > 1e-4]), 99.9) + 1e-9)
    mix = mix * env[:, None] * 0.92 + voice[:, None] * 0.98
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    mix *= 10 ** (-1.0 / 20) / max(1e-9, np.abs(mix).max())
    fade = int(1.2 * SR)
    end = int(TOTAL * SR)
    mix[end - fade:end] *= np.linspace(1, 0, fade)[:, None]
    mix[end:] = 0
    mix = mix[:end]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(OUT, SR, (mix * 32767).astype(np.int16))
    print(f"{LOG} 输出 {OUT}，时长 {len(mix) / SR:.1f}s")


if __name__ == "__main__":
    main()
