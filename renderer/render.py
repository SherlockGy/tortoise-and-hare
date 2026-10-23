# 渲染：多进程分段渲染 -> 拼接 -> 混入配乐（配乐文件里已含旁白和音效）
import sys, os, subprocess
from multiprocessing import Pool
from core import *
from scenes import ORDER, fn_of
from timeline import TL, TOTAL, voice_spans
XF = 0.4
SPANS = voice_spans()
VIG = None

def vignette():
    global VIG
    if VIG is None:
        m = Image.new('L', (W//4, H//4), 0); d = ImageDraw.Draw(m)
        d.ellipse((-W//8+20, -H//8+10, W//4+W//8-20, H//4+H//8-10), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(40)).resize((W, H))
        a = m.point(lambda v: int((255-v)*0.28))
        VIG = Image.new('RGBA', (W, H), (40, 25, 10, 0)); VIG.putalpha(a)
    return VIG

def scene_at(T):
    idx = 0
    for i, n in enumerate(ORDER):
        if T >= TL[n]['start']: idx = i
    return idx

def frame(T):
    i = scene_at(T); n = ORDER[i]; t = T - TL[n]['start']
    f = fn_of(n)(t)
    if i > 0 and t < XF:
        p = ORDER[i-1]; pf = fn_of(p)(T - TL[p]['start'])
        f = Image.blend(pf, f, smooth(t/XF))
    f.alpha_composite(vignette())
    # 字幕
    for s in SPANS:
        a0, a1 = s['t0']-0.12, s['t1']+0.3
        if a0 <= T <= a1:
            al = min(seg(T, a0, a0+0.15), 1-seg(T, a1-0.15, a1))
            im = subtitle_img(s['text']); paste(f, im, W/2-im.width/2, 1078-im.height-18 + (1-al)*8, al)
    # 片头淡入 / 片尾淡出
    k = min(seg(T, 0, 0.35), 1-seg(T, TOTAL-1.6, TOTAL-0.1))
    if k < 1:
        f = Image.blend(Image.new('RGBA', (W, H), (0, 0, 0, 255)), f, max(0, k))
    return f.convert('RGB')

def render_chunk(args):
    k, f0, f1, out = args
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-g', '60', out], stdin=subprocess.PIPE)
    for n in range(f0, f1):
        p.stdin.write(frame(n/FPS).tobytes())
    p.stdin.close(); p.wait()
    return k

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else str(ROOT/'out/chunks')
    os.makedirs(out, exist_ok=True)
    N = int(round(TOTAL*FPS))
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    b = int(sys.argv[3]) if len(sys.argv) > 3 else N
    procs = int(os.environ.get('PROCS', '6'))
    step = 300
    jobs = [(k, f0, min(b, f0+step), f'{os.path.abspath(out)}/chunk_{k:03d}.mp4') for k, f0 in enumerate(range(a, b, step))]
    with Pool(procs) as pool:
        for k in pool.imap_unordered(render_chunk, jobs):
            print('done', k, '/', len(jobs), flush=True)
    with open(f'{out}/list.txt', 'w') as fh:
        for j in jobs: fh.write(f"file '{j[3]}'\n")
    print('frames', b-a)
    # 拼接分段并混入配乐（配乐已含旁白、音效与闪避）
    final = sys.argv[4] if len(sys.argv) > 4 else str(ROOT/'out/龟兔赛跑.mp4')
    os.makedirs(os.path.dirname(final), exist_ok=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{out}/list.txt',
                    '-ss', f'{a/FPS:.3f}', '-t', f'{(b-a)/FPS:.3f}', '-i', str(ROOT/'assets/music/music.m4a'),
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', final], check=True)
    print('输出', final)
