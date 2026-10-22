# v2 分幕画面：每个函数输入幕内秒数 t，返回一帧 RGBA
import math, random
from core import *
from timeline import TL

HS = 1.15   # 奔跑兔子相对缩放
STRIDE = 350  # 奔跑每圈前进像素（与 HS 匹配，避免“滑步”）
TSTRIDE = 80  # 乌龟每圈前进像素

# ---------- 小工具 ----------
def tort_idle(f, cam, x, t, name='tortoise_stand', flip=False, y=G, scale=1.0, ph=0.0):
    sx, sy = breathe(t, 0.012, 0.4, ph)
    if name == 'tortoise_stand' and blink_on(t, 3.7, ph): name = 'tortoise_blink'
    put(f, cam, name, x, y, scale=scale, flip=flip, sx=sx, sy=sy, shadow_y=y)

def hare_idle(f, cam, x, t, name='hare_stand', flip=False, y=G, scale=1.0, ph=0.0, land=None, rot=0.0):
    sx, sy = breathe(t, 0.014, 0.5, ph)
    if land is not None and 0 <= t-land < 0.3:  # 落地压扁回弹
        u = (t-land)/0.3; k = math.sin(u*math.pi)*(1-u)
        sy *= 1-0.12*k; sx *= 1+0.07*k
    if name == 'hare_stand' and blink_on(t, 3.1, ph+1.3): name = 'hare_blink'
    put(f, cam, name, x, y, scale=scale, flip=flip, sx=sx, sy=sy, rot=rot, shadow_y=y)

def hop_y(t, t0, dur, h):
    u = seg(t, t0, t0+dur); return -h*4*u*(1-u)

def stand_any(f, cam, name, x, t, flip=False, y=G, scale=1.0, ph=0.0, amp=0.012):
    sx, sy = breathe(t, amp, 0.45, ph)
    put(f, cam, name, x, y, scale=scale, flip=flip, sx=sx, sy=sy, shadow_y=y)

def dust(f, cam, t, emit_fn, t0, t1, every=0.11, life=0.6, size=34, seed=1):
    """emit_fn(te)->(x,y,vx) 世界坐标；在 [t0,t1] 内周期性扬起纸屑尘土"""
    d = ImageDraw.Draw(f, 'RGBA')
    k0 = int(max(t0, t-life)/every)
    for k in range(k0, int(min(t, t1)/every)+1):
        te = k*every
        if te < t0 or te > t1 or te > t: continue
        a = t-te
        if a > life: continue
        x, y, vx = emit_fn(te)
        r = random.Random(k*31+seed)
        x += vx*a + r.uniform(-10, 10); y += -40*a - r.uniform(0, 12)
        X, Y = cam.pt(x, y) if cam else (x, y)
        z = cam.z if cam else 1
        rad = (size*0.35 + size*a/life)*z*(0.8+0.4*r.random())
        al = int(150*(1-a/life)**1.5)
        d.ellipse((X-rad, Y-rad*0.7, X+rad, Y+rad*0.7), fill=(226, 204, 166, int(al*0.7)))

def speed_lines(f, t, n=14, speed=2600, seed=3, y0=380, y1=900, alpha=110):
    d = ImageDraw.Draw(f, 'RGBA'); r = random.Random(seed)
    for i in range(n):
        y = r.uniform(y0, y1); L = r.uniform(120, 320); ph = r.random()
        x = W + 400 - ((t*speed*r.uniform(0.8, 1.2) + ph*(W+800)) % (W+800))
        d.rounded_rectangle((x, y, x+L, y+5), 3, fill=(255, 255, 255, alpha))

def leaves(f, t, n=7, seed=5, cam=None, alpha=1.0):
    r = random.Random(seed)
    for i in range(n):
        nm = f'leaf{1+i%4}'; sp = r.uniform(60, 110); ph = r.random(); x0 = r.uniform(0, W)
        y = ((t*sp + ph*1300) % 1300) - 120
        x = x0 + 70*math.sin(t*1.3+i) + t*25
        x = x % (W+100) - 50
        im = sprite(nm, 1.6, rot=(t*60*(1 if i % 2 else -1)+i*40) % 360)
        paste(f, im, x-im.width/2, y-im.height/2, alpha)

def sweat(f, cam, x, y, t, t0, t1):
    d = ImageDraw.Draw(f, 'RGBA')
    for k in range(int(t0/0.7), int(min(t, t1)/0.7)+1):
        te = k*0.7; a = t-te
        if te < t0 or a < 0 or a > 0.6: continue
        px, py = x + 40 + (k % 2)*25, y + 160*a*a + 40*a
        X, Y = cam.pt(px, py) if cam else (px, py); z = cam.z if cam else 1
        al = int(230*(1-a/0.6)); r_ = 9*z
        d.ellipse((X-r_, Y-r_, X+r_, Y+r_), fill=(120, 190, 240, al))
        d.polygon([(X-r_*0.8, Y-r_*0.4), (X+r_*0.8, Y-r_*0.4), (X, Y-r_*2.2)], fill=(120, 190, 240, al))

def pop_text(f, txt, cx, cy, t, t0, t1=None, size=150, font=FONT_TITLE, fill=(214, 74, 52), stroke=10):
    if t < t0: return
    a = 1.0 if t1 is None else 1-seg(t, t1, t1+0.35)
    if a <= 0: return
    sc = back_out(seg(t, t0, t0+0.45), 2.2)
    im = text_img(txt, size, font, fill, stroke, (255, 255, 255), True)
    draw_center(f, im, cx, cy, max(0.01, sc), a)

def fireflies(f, t, n=16, seed=9, alpha=1.0):
    d = ImageDraw.Draw(f, 'RGBA'); r = random.Random(seed)
    for i in range(n):
        x = r.uniform(100, W-100) + 40*math.sin(t*0.5+i); y = r.uniform(450, 880) + 25*math.sin(t*0.8+i*2)
        a = (0.5+0.5*math.sin(t*2.2+i*1.7))*alpha
        for rad, al in ((16, 40), (8, 90), (4, 230)):
            d.ellipse((x-rad, y-rad, x+rad, y+rad), fill=(255, 236, 140, int(al*a)))

def blend(a, b, u):
    if u <= 0: return a
    if u >= 1: return b
    return Image.blend(a, b, u)

def shots(t, lst, xf=0.3):
    """lst=[(起点, fn(t_local)), ...]；镜头之间交叉淡化"""
    idx = max(i for i, (s, _) in enumerate(lst) if t >= s or i == 0)
    s, fn = lst[idx]
    cur = fn(t-s)
    if idx > 0 and t-s < xf:
        ps, pfn = lst[idx-1]
        return blend(pfn(t-ps), cur, smooth((t-s)/xf))
    return cur

# ---------- 1 片头 ----------
def title(t):
    cam = Cam(lerp(1.0, 1.06, smooth(t/15)), 960, 560)
    f = bg('bg_start', cam)
    # 乌龟慢慢爬到左侧
    tx = keys(t, [(0.0, 400), (9.8, 640)], fn=lambda u: u)
    if t < 9.8: walk_t(f, cam, tx, (tx-400)/TSTRIDE*1.6)
    else: tort_idle(f, cam, 640, t)
    # 兔子：一阵风跑过，再从右边跑回来停下
    if 0.2 <= t < 3.6:
        x = lerp(-300, 2350, (t-0.2)/3.4)
        dust(f, cam, t, lambda te: (lerp(-300, 2350, (te-0.2)/3.4)-80, G, -60), 0.2, 3.6)
        gallop(f, cam, x, (x+300)/STRIDE, HS)
    elif 4.6 <= t < 6.2:
        u = (t-4.6)/1.6; x = lerp(2250, 1330, ease_out(u))
        gallop(f, cam, x, (2250-x)/STRIDE, HS, flip=True)
    elif t >= 6.2:
        hare_idle(f, cam, 1330, t, flip=True, land=6.2)
    fg(f, 'fg_flowers', 0)
    # 标题字逐个弹出
    cols = [(86, 150, 70), (236, 128, 60), (225, 92, 110), (70, 140, 200)]
    a = 1-seg(t, 12.6, 13.4)
    for i, ch in enumerate('龟兔赛跑'):
        t0 = 0.45+0.16*i
        if t < t0 or a <= 0: continue
        sc = back_out(seg(t, t0, t0+0.5), 2.4)
        im = text_img(ch, 190, FONT_TITLE, cols[i], 12, (255, 255, 255), True)
        bob = 6*math.sin(t*2.2+i*0.9)
        draw_center(f, im, 960+(i-1.5)*205, 190+bob, max(0.01, sc), a, rot=(-4 if i % 2 else 4)*(1-seg(t, t0, t0+0.6)))
    # VS
    if t >= 9.9:
        al = 1-seg(t, 13.0, 13.6)
        sc = back_out(seg(t, 9.9, 10.4), 2.6)
        draw_center(f, text_img('VS', 150, FONT_TITLE, (230, 70, 50), 10, (255, 255, 255), True), 965, 640, max(0.01, sc), al, rot=6*math.sin(t*3))
    return f

# ---------- 2 相遇 ----------
HOPS = [(0.3, 1150, 1330), (1.25, 1330, 1470), (2.2, 1470, 1260), (3.15, 1260, 1420), (4.1, 1420, 1240), (5.05, 1240, 1320)]
def meet(t):
    cam = Cam(1.18, 960, 620)
    f = bg('bg_start', cam)
    # 乌龟
    if t < 12.0:
        tx = lerp(430, 620, t/12.0); walk_t(f, cam, tx, t/1.2)
    elif t < 13.0: tort_idle(f, cam, 600, t)
    elif t < 16.1: tort_idle(f, cam, 600, t, 'tortoise_look_up')
    elif t < 18.5:
        nod = 4*math.sin((t-16.1)*math.pi*2.2)
        put(f, cam, 'tortoise_talk', 600, G+min(0, nod)*0.5, shadow_y=G)
    elif t < 20.0: tort_idle(f, cam, 600, t, 'tortoise_nod')
    else: tort_idle(f, cam, 600, t, 'tortoise_determined')
    # 兔子：先蹦来蹦去
    x, y, flip, done = 1150, G, False, True
    for (t0, a, b) in HOPS:
        if t0 <= t < t0+0.95:
            u = seg(t, t0, t0+0.75); x = lerp(a, b, ease_io(u)); y = G+hop_y(t, t0, 0.75, 120); flip = b < a; done = False
            if t > t0+0.75:
                x = b; y = G; land = t0+0.75
                hare_idle(f, cam, x, t, flip=flip, land=land)
            else:
                rot = (-6 if not flip else 6)*math.sin(u*math.pi)
                put(f, cam, 'hare_cheer' if 0.15 < u < 0.85 else 'hare_stand', x, y, flip=flip, rot=rot, shadow_y=G)
            break
    else:
        if t < 0.3: hare_idle(f, cam, 1150, t)
        elif t < 6.2: hare_idle(f, cam, 1320, t, flip=True)
        elif t < 8.8:
            put(f, cam, 'hare_taunt', 1320, G, flip=True, rot=2.0*math.sin(t*14), shadow_y=G)
        elif t < 12.5:
            bob = abs(math.sin(t*5))*6
            put(f, cam, 'hare_talk', 1320, G-bob*0.4, flip=True, shadow_y=G)
        elif 19.2 <= t < 21.0:
            put(f, cam, 'hare_talk', 1320, G, flip=True, shadow_y=G)
        else: hare_idle(f, cam, 1320, t, flip=True)
    fg(f, 'fg_flowers', 300)
    return f

# ---------- 3 集合 ----------
def owl_on_stump(f, cam, x, t, pose='owl_stand', flip=False, y=G+10):
    put(f, cam, 'tree_stump', x, y, shadow_y=y)
    sx, sy = breathe(t, 0.015, 0.5, 0.7)
    if pose == 'owl_stand' and blink_on(t, 2.9, 0.4): pose = 'owl_blink'
    put(f, cam, pose, x+5, y-140, flip=flip, sx=sx, sy=sy, shadow=False)

CROWD = [('fox', 1420, 0.6), ('hedgehog', 1610, 1.2), ('mouse', 1770, 1.8)]
def crowd(f, cam, t, cheer_spans, y=G-45, scale=0.95, xs=None, enter=True, flip=True):
    for i, (nm, x, t0) in enumerate(CROWD):
        if xs: x = xs[i]
        if enter:
            if t < t0: continue
            u = seg(t, t0, t0+2.0)
            xx = lerp(2150, x, ease_out(u)); yy = y + (hop_y((t-t0) % 0.5, 0, 0.5, 40) if u < 1 else 0)
        else: xx, yy = x, y
        ch = any(a <= t < b for a, b in cheer_spans)
        if ch:
            k = int((t*4+i) % 2); yy += hop_y((t+i*0.13) % 0.5, 0, 0.5, 26)
            put(f, cam, f'{nm}_cheer' if k == 0 else f'{nm}_stand', xx, yy, scale=scale, flip=flip, shadow_y=y)
        else:
            stand_any(f, cam, f'{nm}_stand', xx, t, flip=flip, y=yy, scale=scale, ph=i*0.3)

def course_card(f, t, t0, t1):
    """猫头鹰讲路线的小地图：虚线路线逐点画出，最后一个点正好落在终点旗杆底部"""
    if t < t0: return
    a = 1-seg(t, t1, t1+0.4); sc = back_out(seg(t, t0, t0+0.45), 1.6)
    if a <= 0: return
    card = Image.new('RGBA', (760, 230))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((6, 6, 754, 224), 30, fill=(255, 250, 236, 245), outline=(224, 196, 150), width=4)
    S, E = (150, 170), (632, 150)          # 起点、终点（= 旗杆底部）
    def P(u): return (lerp(S[0], E[0], u), lerp(S[1], E[1], u) - 55*math.sin(u*math.pi*1.4)*(1-u*0.25))
    # 按弧长等距取点，保证最后一点就是 E
    pts = [P(i/400) for i in range(401)]
    L = [0.0]
    for p, q in zip(pts, pts[1:]): L.append(L[-1]+math.dist(p, q))
    n = 26; dots = []
    for k in range(n+1):
        target = L[-1]*k/n; j = min(range(len(L)), key=lambda i: abs(L[i]-target)); dots.append(pts[j])
    dots[-1] = E
    prog = seg(t, t0+0.3, t0+2.5)
    for k, (x, y) in enumerate(dots):
        if k > prog*n + 1e-6: break
        r = 7 if k in (0, n) else 5
        d.ellipse((x-r, y-r, x+r, y+r), fill=(196, 130, 80))
    flag = sprite('flag', 1.4)
    fa = np.asarray(flag.getchannel('A')); ys, xs = np.nonzero(fa > 128)
    bx = int(xs[ys >= ys.max()-2].mean()); by = int(ys.max())
    card.alpha_composite(flag, (int(E[0]-bx), int(E[1]-by)))
    card.alpha_composite(sprite('gallop_3', 0.33), (int(S[0]-120), int(S[1]-95)))
    card.alpha_composite(sprite('tortoise_walk_a', 0.24), (int(S[0]-125), int(S[1]-40)))
    lab = text_img('起点', 34); card.alpha_composite(lab, (int(S[0]-lab.width/2), int(S[1]+8)))
    lab = text_img('终点', 34); card.alpha_composite(lab, (int(E[0]+18), int(E[1]-8)))
    draw_center(f, card, 960, 200, max(0.01, sc), a)

def challenge(t):
    cam = Cam(1.0, lerp(930, 990, smooth(t/20)), 560)
    f = bg('bg_start', cam)
    pose = 'owl_stand'
    if 5.2 <= t < 8.3 or 9.6 <= t < 14.9: pose = 'owl_talk'
    elif 8.3 <= t < 9.6: pose = 'owl_blink'
    elif t >= 15.5: pose = 'owl_wingup'
    owl_on_stump(f, cam, 300, t, pose)
    crowd(f, cam, t, [(3.6, 5.0), (17.0, 20.9)])
    tort_idle(f, cam, 760, t, 'tortoise_determined' if t > 15.5 else 'tortoise_stand', flip=t < 15.5)
    if t < 15.5: hare_idle(f, cam, 1080, t, flip=True)
    else: hare_idle(f, cam, 1080, t, 'hare_talk' if t < 17.5 else 'hare_stand')
    fg(f, 'fg_grass', 500)
    course_card(f, t, 9.6, 14.9)
    return f

# ---------- 4 起跑 ----------
def start(t):
    cam = Cam(1.1, 880, 640)
    f = bg('bg_start', cam)
    put(f, cam, 'start_banner', 850, G-30, scale=1.55, shadow=False)
    owl_on_stump(f, cam, 230, t, 'owl_wingup' if 1.7 <= t < 3.6 else ('owl_cheer' if t >= 3.6 else 'owl_talk'))
    # 乌龟
    if t < 2.8: tort_idle(f, cam, 620, t, 'tortoise_determined')
    else:
        tx = 620 + 55*(t-2.8); walk_t(f, cam, tx, (tx-620)/TSTRIDE)
    # 兔子：蓄力 -> 冲出去
    T0 = 2.6
    if t < 1.8: hare_idle(f, cam, 1060, t)
    elif t < T0:
        u = seg(t, 1.8, 2.0); sx, sy = 1+0.04*math.sin(t*30)*u, 1-0.05*u
        put(f, cam, 'gallop_1', 1060, G, scale=HS, sx=sx, sy=sy, shadow_y=G)
    else:
        dt = t-T0
        xf = lambda d: 1060 + (900*d*d if d < 0.8 else 576 + 1440*(d-0.8))
        x = xf(dt)
        dust(f, cam, t, lambda te: (xf(te-T0)-90, G, -80), T0, T0+1.4, 0.07, 0.7, 44)
        gallop(f, cam, x, (x-1060)/STRIDE + 0.25, HS)
    fg(f, 'fg_flowers', 900)
    pop_text(f, '预备', 960, 260, t, 1.8, 2.55, 120, fill=(236, 150, 50))
    pop_text(f, '跑！', 960, 260, t, 2.6, 4.2, 170)
    return f

# ---------- 5 飞奔 ----------
def sprint(t):
    def a(tl):  # 跟拍兔子
        f = bg_pan('bg_forest', 180*tl)
        ex = 0 if tl < 3.3 else 900*(tl-3.3)**1.6
        x = 820 + ex
        speed_lines(f, tl, 10, 2400, alpha=70)
        dust(f, None, tl, lambda te: (820 + (0 if te < 3.3 else 900*(te-3.3)**1.6) - 110, G, -600), 0, 4.6, 0.09, 0.45, 26)
        gallop(f, None, x, tl/0.36, HS*1.2)
        fg(f, 'fg_grass', 1300*tl)
        return f
    def b(tl):  # 跟拍乌龟
        f = bg_pan('bg_forest', 300 + 40*tl)
        walk_t(f, None, 860, tl/1.1)
        fg(f, 'fg_grass', 600 + 150*tl)
        return f
    def c(tl):  # 兔子回头看，乌龟在远处
        cam = Cam(lerp(1.0, 1.06, smooth(tl/6)), 960, 560)
        f = bg('bg_forest', cam)
        tx = 800 + 6*tl
        walk_t(f, cam, tx, tl/1.1, scale=0.38, y=650)
        if tl < 1.3: hare_idle(f, cam, 1380, tl+3, flip=True)
        elif tl < 3.6: put(f, cam, 'hare_taunt', 1380, G, flip=True, rot=1.6*math.sin(tl*13), shadow_y=G)
        else: hare_idle(f, cam, 1380, tl, flip=True)
        fg(f, 'fg_grass', 200)
        return f
    return shots(t, [(0, a), (4.4, b), (8.5, c)], 0.3)

# ---------- 6 得意 ----------
def thought(f, cam, x, y, t, t0, t1):
    if t < t0: return
    a = 1-seg(t, t1, t1+0.35)
    if a <= 0: return
    sc = back_out(seg(t, t0, t0+0.4), 1.8)
    X, Y = cam.pt(x, y)
    im = Image.new('RGBA', (340, 300)); d = ImageDraw.Draw(im)
    d.ellipse((40, 10, 330, 200), fill=(255, 252, 240, 245), outline=(224, 196, 150), width=4)
    d.ellipse((40, 205, 80, 240), fill=(255, 252, 240, 245), outline=(224, 196, 150), width=3)
    d.ellipse((15, 250, 38, 272), fill=(255, 252, 240, 245), outline=(224, 196, 150), width=3)
    im.alpha_composite(sprite('carrot', 1.0, rot=-20), (90, 50))
    z = text_img('Zzz', 64, FONT_TITLE, (110, 120, 200))
    im.alpha_composite(z, (180, 50+int(6*math.sin(t*3))))
    paste(f, im.resize((max(1, int(340*sc)), max(1, int(300*sc)))), X-40*sc, Y-300*sc, a)

def taunt(t):
    cam = Cam(1.15, 1000, 640)
    f = bg('bg_oak', cam)
    if t >= 5.4:
        sc = back_out(seg(t, 5.4, 5.75), 1.5)
        put(f, cam, 'blanket', 1000, G+40, scale=max(0.01, sc), shadow=False)
    if t < 1.3:
        u = seg(t, 0, 1.3); x = lerp(-250, 1000, ease_out(u))
        gallop(f, cam, x, (x+250)/STRIDE, HS)
    elif t < 5.6:
        if 3.4 <= t < 5.2: put(f, cam, 'hare_taunt', 1000, G, rot=1.5*math.sin(t*12), shadow_y=G)
        else: hare_idle(f, cam, 1000, t, land=1.3)
    else:
        m = math.sin(t*2*math.pi*2.6)
        u = seg(t, 5.6, 5.85)
        put(f, cam, 'hare_eat', 1000, G+8, sy=(1+0.012*m)*(0.9+0.1*u), sx=1-0.006*m, rot=1.2*m*(1-seg(t, 11.5, 12.8)), shadow=False)
    thought(f, cam, 1110, G-470, t, 1.6, 5.3)
    fg(f, 'fg_flowers', 1200)
    return f

# ---------- 7 午睡 ----------
def snooze(f, cam, x, y, t, t0, seed=0):
    if t < t0: return
    for k in range(int((t-t0)/1.1)+1):
        a = t-t0-k*1.1
        if a < 0 or a > 3.0: continue
        px = x + 30*math.sin(a*2+k) + a*25; py = y - a*70
        X, Y = cam.pt(px, py)
        im = text_img('Z', int(36+a*14), FONT_TITLE, (100, 110, 190), 4)
        paste(f, im, X-im.width/2, Y-im.height/2, min(1, a*3)*(1-seg(a, 2.2, 3.0)))

def bubble(f, cam, x, y, t, t0, period=3.1):
    if t < t0: return
    u = ((t-t0) % period)/period
    r = 30*smooth(u/0.8) if u < 0.8 else 0
    if r < 2: return
    X, Y = cam.pt(x, y); r *= cam.z
    d = ImageDraw.Draw(f, 'RGBA')
    d.ellipse((X-r, Y-r, X+r, Y+r), fill=(200, 230, 255, 120), outline=(150, 190, 240, 200), width=3)
    d.ellipse((X-r*0.5, Y-r*0.6, X-r*0.15, Y-r*0.25), fill=(255, 255, 255, 200))

def sleeping_hare(f, cam, t, mode):
    """mode: eat / doze / lie"""
    if mode == 'lie':
        sx, sy = breathe(t, 0.03, 0.32)
        put(f, cam, 'hare_lie', 1000, G-2, sx=sx, sy=sy, shadow=False)

def nap(t):
    z = keys(t, [(0, 1.18), (11.5, 1.35), (13.0, 1.15)])
    cx = keys(t, [(0, 1000), (11.5, 1000), (13.0, 960)])
    cam = Cam(z, cx, keys(t, [(0, 680), (11.5, 730), (13.0, 680)]))
    f = bg('bg_oak', cam)
    put(f, cam, 'blanket', 1000, G+40, shadow=False)
    if t < 4.3:
        m = math.sin(t*2*math.pi*lerp(2.0, 0.8, t/4.3))
        put(f, cam, 'hare_eat', 1000, G+8, sy=1+0.01*m, rot=0.8*m, shadow=False)
    elif t < 8.3:
        a = blend_pose(f, cam, t, 4.3, 'hare_eat', 'hare_sleep', 1000, G+8, 1000, G+8)
        if t > 4.7:
            nod = math.sin((t-4.3)*1.4)*1.5
            put(f, cam, 'hare_sleep', 1000, G+8, rot=nod, sy=1+0.01*math.sin(t*2), shadow=False)
    else:
        if t < 8.8:
            u = seg(t, 8.3, 8.8)
            put(f, cam, 'hare_sleep', 1000, G+8, alpha=1-u, shadow=False)
            sx, sy = breathe(t, 0.03, 0.32); put(f, cam, 'hare_lie', 1000, G-2, sx=sx, sy=sy, alpha=u, shadow=False)
        else:
            sleeping_hare(f, cam, t, 'lie')
        bubble(f, cam, 830, G-50, t, 8.5)
        snooze(f, cam, 860, G-110, t, 8.6)
    # 乌龟从身边爬过（在兔子前面一层）
    if t >= 11.6:
        tx = lerp(150, 1250, (t-11.6)/9.6)
        walk_t(f, cam, tx, (tx-150)/TSTRIDE*0.9, y=G+55)
    # 午后：蝴蝶与落叶
    bx = 1300 + 260*math.sin(t*0.5); by = 420 + 60*math.sin(t*1.3)
    X, Y = cam.pt(bx, by)
    paste(f, sprite('butterfly', 2.4, sy=0.55+0.45*abs(math.sin(t*9))), X-30, Y-20)
    leaves(f, t, 6, 5)
    fg(f, 'fg_flowers', 1500)
    return f

def blend_pose(f, cam, t, t0, a, b, xa, ya, xb, yb, d=0.4):
    u = seg(t, t0, t0+d)
    if u < 1: put(f, cam, a, xa, ya, alpha=1-u, shadow=False)
    return u

# ---------- 8 超越 ----------
def pass_(t):
    def a(tl):
        f = bg_pan('bg_forest', 80 + 45*tl)
        walk_t(f, None, 860, tl/1.24)
        sweat(f, None, 960, 700, tl, 4.2, 9.5)
        fg(f, 'fg_grass', 900 + 180*tl)
        return f
    def b(tl):
        cam = Cam(1.08, 960, 600)
        f = bg('bg_forest', cam)
        for i, (nm, x) in enumerate([('mouse', 1470), ('hedgehog', 1640), ('fox', 1830)]):
            peek = ease_out(seg(tl, 0.3+i*0.3, 1.0+i*0.3))
            yy = G-50 + (1-peek)*220
            cheer = tl > 1.2 and int((tl*3+i) % 2) == 0
            put(f, cam, f'{nm}_cheer' if cheer else f'{nm}_stand', x, yy+(hop_y((tl+i*0.2) % 0.66, 0, 0.66, 14) if cheer else 0), scale=0.92, flip=True, shadow_y=G-50)
        tx = 640 + 60*tl
        walk_t(f, cam, tx, tl/1.24)
        fg(f, 'fg_grass', 300)
        return f
    return shots(t, [(0, a), (9.2, b)], 0.35)

# ---------- 9 惊醒 ----------
def wake(t):
    def a(tl):
        cam = Cam(1.22, 1000, 680)
        f = bg('bg_oak', cam)
        put(f, cam, 'blanket', 1000, G+40, shadow=False)
        if tl < 0.7:
            sleeping_hare(f, cam, tl, 'lie'); snooze(f, cam, 860, G-110, tl+3, 0)
        elif tl < 1.2:
            u = seg(tl, 0.7, 1.2)
            put(f, cam, 'hare_lie', 1000, G-2, alpha=1-u, shadow=False)
            put(f, cam, 'hare_cheer', 1000, G+8, alpha=u, shadow=False)
        elif tl < 3.5:
            s = smooth(seg(tl, 1.2, 2.3))*(1-smooth(seg(tl, 2.8, 3.5)))
            put(f, cam, 'hare_cheer', 1000, G+8, sy=1+0.07*s, sx=1-0.03*s, rot=3*math.sin(tl*2)*s, shadow=False)
        else:
            hare_idle(f, cam, 1000, tl, y=G+8, land=3.5)
        fg(f, 'fg_flowers', 1500)
        return f
    def b(tl):  # 兔子望向山脚：乌龟和终点都还在很远的山路上（远小）
        z = keys(tl, [(0, 1.22), (1.6, 1.4)]); cx = keys(tl, [(0, 1000), (1.6, 1330)])
        cam = Cam(z, cx, keys(tl, [(0, 680), (1.6, 700)]))
        f = bg('bg_oak', cam)
        # 远处山路上的终点门（很小）和乌龟（更小），固定在背景上
        put(f, cam, 'finish_banner', 1700, 670, scale=0.13, shadow=False)
        tx = 1668 + 4*tl
        walk_t(f, cam, tx, tl/1.24, scale=0.09, y=742)
        X, Y = cam.pt(tx, 728)
        k = smooth(seg(tl, 1.4, 1.9))
        if k > 0:
            dr = ImageDraw.Draw(f, 'RGBA'); r = (34 + 3*math.sin(tl*6))*cam.z
            dr.ellipse((X-r, Y-r, X+r, Y+r), outline=(255, 255, 255, int(200*k)), width=4)
        put(f, cam, 'blanket', 1000, G+40, shadow=False)
        hare_idle(f, cam, 1000, tl+5, y=G+8)
        fg(f, 'fg_flowers', 1500)
        return f
    def c(tl):
        T = tl + 7.8
        cam = Cam(1.22, 1000, 680)
        f = bg('bg_oak', cam)
        put(f, cam, 'blanket', 1000, G+40, shadow=False)
        if T < 10.9:
            sh = 8*math.sin(T*55)*math.exp(-(T-7.8)*1.2)
            put(f, cam, 'hare_wake', 1000+sh, G+8, sy=1+0.05*math.exp(-(T-7.8)*5), shadow=False)
            pop_text(f, '！', 1000+cam.z*0+120*cam.z, 250, T, 7.9, 10.6, 150)
        elif T < 12.0:
            put(f, cam, 'gallop_1', 1000, G+8, scale=HS, sx=1+0.03*math.sin(T*40), sy=0.95, shadow=False)
        else:
            dt = T-12.0
            xf = lambda d: 1000 + (1000*d*d if d < 0.7 else 490 + 1400*(d-0.7))
            x = xf(dt)
            dust(f, cam, T, lambda te: (xf(te-12.0)-90, G, -80), 12.0, 13.2, 0.07, 0.7, 44)
            gallop(f, cam, x, (x-1000)/STRIDE + 0.25, HS)
            leaves(f, T*2.5, 5, 11)
        fg(f, 'fg_flowers', 1500)
        return f
    def d(tl):  # 跟拍兔子追赶
        f = bg_pan('bg_oak', 300*tl)
        x = lerp(-200, 820, ease_out(seg(tl, 0, 0.9)))
        speed_lines(f, tl, 12, 2600, alpha=70)
        dust(f, None, tl, lambda te: (lerp(-200, 820, ease_out(seg(te, 0, 0.9)))-110, G, -700), 0, 3.5, 0.09, 0.45, 26)
        gallop(f, None, x, tl/0.34, HS*1.2)
        fg(f, 'fg_grass', 1800*tl)
        return f
    return shots(t, [(0, a), (5.0, b), (7.8, c), (13.4, d)], 0.3)

# ---------- 10 追赶 ----------
def _chain(f, cam, name, pts_ang, flip=False):
    """把丝带素材切成竖条，沿曲线逐条摆放（类似布条的网格变形）"""
    im = base(name)
    if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    n = len(pts_ang); sw = im.width / n
    for i, (x, y, ang) in enumerate(pts_ang):
        x0 = int(i*sw); x1 = min(im.width, int((i+1)*sw)+2)
        sl = im.crop((x0, 0, x1, im.height))
        z = cam.z
        sl = sl.resize((max(1, round(sl.width*z)), max(1, round(sl.height*z))), Image.BILINEAR)
        sl = sl.rotate(-math.degrees(ang), Image.BICUBIC, expand=True)
        X, Y = cam.pt(x, y)
        paste(f, sl, X-sl.width/2, Y-sl.height/2)

def ribbon(f, cam, t, x0, x1, y, broken_at=None, push=0.0):
    """终点红丝带：未断时轻轻下垂并随风飘；断开后两半挂在立柱上自然垂落、来回摆动"""
    N = 30
    if broken_at is None or t < broken_at:
        L = x1-x0; out = []
        def Y(u): return y + 10*math.sin(u*math.pi) + 4*math.sin(t*3.2 + u*7)*math.sin(u*math.pi) + push*math.exp(-((u-0.5)/0.12)**2)
        for i in range(N):
            u = (i+0.5)/N; du = 0.5/N
            ang = math.atan2(Y(u+du)-Y(u-du), L*2*du)
            out.append((x0+L*u, Y(u), ang))
        _chain(f, cam, 'ribbon', out)
    else:
        a = t-broken_at
        L = base('ribbon_half').width
        swing = math.radians(64*(1-math.exp(-a*3.2)) + 16*math.exp(-a*1.4)*math.sin(a*7.5))
        for side in (-1, 1):
            px = x0 if side < 0 else x1
            out = []; cx, cy = px, y; ds = L/N
            for i in range(N):
                u = (i+0.5)/N
                # 越靠近断口越下垂，末端有一点随风抖动
                th = swing*(0.55+0.45*u) + math.radians(7*math.sin(t*6.5+u*5)*u*math.exp(-a*0.25))
                dx, dy = math.cos(th)*ds, math.sin(th)*ds
                mx, my = cx + (-side)*dx/2, cy + dy/2
                out.append((mx, my, th if side < 0 else -th))
                cx += (-side)*dx; cy += dy
            _chain(f, cam, 'ribbon_half', out, flip=(side > 0))

def confetti(f, t, t0, n=110, seed=7):
    if t < t0: return
    d = ImageDraw.Draw(f, 'RGBA'); r = random.Random(seed)
    cols = [(236, 92, 80), (250, 196, 60), (90, 180, 110), (90, 150, 230), (230, 130, 200), (255, 255, 255)]
    for i in range(n):
        x0 = r.uniform(0, W); v = r.uniform(180, 320); dl = r.uniform(0, 1.2); c = cols[i % len(cols)]
        a = t-t0-dl
        if a < 0: continue
        y = -30 + v*a; x = x0 + 50*math.sin(a*2+i)
        if y > H+30: continue
        ang = a*4+i; s = 9; w = abs(math.cos(ang*1.7))*s+2
        al = int(255*(1-seg(t, t0+9, t0+10.5)))
        d.polygon([(x+math.cos(ang)*w, y+math.sin(ang)*w), (x-math.sin(ang)*s, y+math.cos(ang)*s), (x-math.cos(ang)*w, y-math.sin(ang)*w), (x+math.sin(ang)*s, y-math.cos(ang)*s)], fill=c+(al,))

BX = 1450
POST_L, POST_R = BX-292, BX+292
def chase(t):
    def a(tl):
        f = bg_pan('bg_forest', 160*tl)
        speed_lines(f, tl, 16, 3200, alpha=85)
        dust(f, None, tl, lambda te: (840-110, G, -900), 0, 5.4, 0.08, 0.4, 26)
        gallop(f, None, 840 + 25*math.sin(tl*1.3), tl/0.32, HS*1.2)
        fg(f, 'fg_grass', 2100*tl)
        return f
    def b(tl):
        f = bg_pan('bg_forest', 500 + 60*tl)
        hx = lerp(-300, 260, smooth(seg(tl, 1.2, 4.9)))
        if hx > -280: gallop(f, None, hx, tl/0.32, HS*0.92, y=G-35)
        walk_t(f, None, 1150, tl/1.24)
        sweat(f, None, 1250, 700, tl, 0.5, 5)
        fg(f, 'fg_grass', 1200 + 240*tl)
        return f
    def c(tl):
        cam = Cam(1.08, 1150, 610)
        f = bg('bg_finish', cam)
        put(f, cam, 'finish_banner', BX, G-10, scale=1.0, shadow=False)
        tx = 700 + 60*tl
        walk_t(f, cam, tx, tl/1.24)
        ribbon(f, cam, tl, POST_L, POST_R, G-70)
        fg(f, 'fg_grass', 700)
        return f
    return shots(t, [(0, a), (5.0, b), (9.9, c)], 0.3)

# ---------- 11 冲线 ----------
def finish(t):
    cam = Cam(1.08, 1150, 610)
    f = bg('bg_finish', cam)
    put(f, cam, 'finish_banner', BX, G-10, shadow=False)
    ch = [(3.6, 11.0)]
    crowd(f, cam, t, ch, y=G-70, scale=0.85, xs=[420, 560, 680], enter=False, flip=False)
    owl_on_stump(f, cam, 1960, t, 'owl_cheer' if 3.6 <= t < 11 else 'owl_stand', flip=True)
    # 乌龟冲线
    if t < 6.4:
        tx = keys(t, [(0, 1090), (3.5, 1310), (5.0, 1380)], fn=lambda u: ease_out(u) if u > 0 else u)
        if t < 3.4: tx = lerp(1090, 1300, t/3.4)
        put(f, cam, 'tortoise_cross', tx, G+2*math.sin(t*6), sy=1+0.015*math.sin(t*9), shadow_y=G)
    else:
        hy = hop_y((t-6.4) % 0.7, 0, 0.7, 30) if t < 11 else 0
        put(f, cam, 'tortoise_cheer', 1380, G+hy, sy=1+0.02*math.sin(t*5), shadow_y=G)
    ribbon(f, cam, t, POST_L, POST_R, G-70, broken_at=3.5, push=18*smooth(seg(t, 2.6, 3.5)))
    # 奖杯
    if t >= 7.2:
        sc = back_out(seg(t, 7.2, 7.7), 2)
        X, Y = cam.pt(1385, G-330+8*math.sin(t*2.5))
        im = sprite('trophy', 1.0*cam.z*max(0.01, sc)); paste(f, im, X-im.width/2, Y-im.height/2)
        for k in range(5):
            ang = t*1.5+k*1.256; rr = 120*cam.z
            st = sprite('star', 1.6+0.5*math.sin(t*4+k)); paste(f, st, X+rr*math.cos(ang)-st.width/2, Y+rr*0.6*math.sin(ang)-st.height/2, 0.9*sc if sc < 1 else 0.9)
    # 兔子赶到
    if t >= 11.6:
        if t < 13.1:
            u = seg(t, 11.6, 13.1); x = lerp(-250, 860, ease_out(u))
            gallop(f, cam, x, (x+250)/STRIDE, HS)
        else:
            pant = math.sin(t*2*math.pi*2.4)
            put(f, cam, 'hare_sad', 860, G, sy=1+0.02*pant, sx=1-0.01*pant, shadow_y=G)
    confetti(f, t, 3.5)
    fg(f, 'fg_grass', 700)
    return f

# ---------- 12 道理 ----------
def card(w, h, inner_fn=None):
    im = Image.new('RGBA', (w, h))
    sh = Image.new('L', (w, h)); ImageDraw.Draw(sh).rounded_rectangle((14, 20, w-8, h-4), 28, fill=80)
    s = Image.new('RGBA', (w, h), (80, 60, 30, 0)); s.putalpha(sh.filter(ImageFilter.GaussianBlur(8))); im.alpha_composite(s)
    ImageDraw.Draw(im).rounded_rectangle((6, 6, w-14, h-16), 28, fill=(255, 252, 244, 255), outline=(230, 206, 160), width=4)
    return im

def moral(t):
    def a(tl):
        cam = Cam(lerp(1.25, 1.32, smooth(tl/16)), 1140, 670)
        f = bg('bg_finish', cam)
        if tl < 10.8: put(f, cam, 'hare_sad', 950, G, sy=1+0.01*math.sin(tl*2), shadow_y=G)
        elif tl < 14.0:
            nod = max(0, math.sin((tl-10.8)*5))*5 if tl < 12 else 0
            put(f, cam, 'hare_talk', 950, G+nod*0.6, shadow_y=G)
        else: hare_idle(f, cam, 950, tl)
        if 5.5 <= tl < 10.4:
            put(f, cam, 'tortoise_talk', 1330, G+min(0, 3*math.sin(tl*4)), flip=True, shadow_y=G)
        elif 10.4 <= tl < 12.0: tort_idle(f, cam, 1330, tl, 'tortoise_nod', flip=True)
        else: tort_idle(f, cam, 1330, tl, flip=True)
        fg(f, 'fg_flowers', 400)
        return f
    def b(tl):
        f = bg('paper_texture')
        T = tl + 16.3
        for i, (cx, t0, lab, col) in enumerate([(640, 16.6, '跑得快', (226, 106, 80)), (1280, 17.2, '一直走', (86, 150, 70))]):
            if T < t0: continue
            sc = back_out(seg(T, t0, t0+0.45), 1.6)
            c = card(470, 400)
            if i == 0:
                ph = T/0.36; n, dy, rot = GALLOP[int(ph*4) % 4]
                im = sprite(n, HS*0.95); c.alpha_composite(im, (235-im.width//2 - int(GX[n]), 260-im.height+int(dy)))
            else:
                ph = T/1.1; seq = ['tortoise_walk_a', 'tortoise_stand', 'tortoise_walk_b', 'tortoise_stand']
                im = sprite(seq[int(ph*4) % 4], 0.95); c.alpha_composite(im, (235-im.width//2, 265-im.height))
            tx = text_img(lab, 64, FONT_TITLE, col); c.alpha_composite(tx, (235-tx.width//2, 280))
            draw_center(f, c, cx, 420, max(0.01, sc))
        # 不怕慢，只怕站
        if T >= 20.2:
            for i, ch in enumerate('不怕慢，只怕站'):
                t0 = 20.2 + i*0.12
                if T < t0: continue
                s = back_out(seg(T, t0, t0+0.4), 2)
                im = text_img(ch, 92, FONT_TITLE, (200, 90, 50) if i > 3 else (86, 130, 70), 8, (255, 255, 255), True)
                draw_center(f, im, 960 + (i-3)*104, 780, max(0.01, s))
        return f
    return shots(t, [(0, a), (16.3, b)], 0.45)

# ---------- 13 结尾 ----------
def finale(t):
    cam = Cam(lerp(1.0, 1.08, smooth(t/24)), 960, 600)
    f = bg('bg_sunset', cam)
    fr = [('owl', 380, 4.0), ('fox', 560, 5.0), ('hedgehog', 1400, 6.0), ('mouse', 1530, 6.8)]
    for i, (nm, x, t0) in enumerate(fr):
        if t < t0: continue
        u = seg(t, t0, t0+1.8); left = x < 960
        xx = lerp(-200 if left else 2150, x, ease_out(u)); yy = G-55 + (hop_y((t-t0) % 0.45, 0, 0.45, 30) if u < 1 else 0)
        pose = f'{nm}_stand'
        if blink_on(t, 3.0, i) and nm == 'owl': pose = 'owl_blink'
        if 15.5 < t < 17.5 and int((t*3+i) % 2) == 0: pose = f'{nm}_cheer'
        put(f, cam, pose, xx, yy, scale=0.85, flip=not left, sy=1+0.01*math.sin(t*2+i), shadow_y=G-55)
    if t < 5.0:
        tx = lerp(650, 1100, t/5.0); walk_t(f, cam, tx, (tx-650)/TSTRIDE)
    else: tort_idle(f, cam, 1100, t, 'tortoise_stand' if not 15.5 < t < 18 else 'tortoise_cheer')
    # 兔子轻轻蹦着陪乌龟走
    if t < 5.0:
        hx = lerp(420, 860, t/5.0); hy = hop_y(t % 0.8, 0, 0.62, 34)
        put(f, cam, 'hare_stand', hx, G+hy, rot=-3*math.sin((t % 0.8)/0.62*math.pi), shadow_y=G)
    else:
        hare_idle(f, cam, 860, t, 'hare_stand' if not 15.5 < t < 18 else 'hare_cheer', land=5.0)
    fireflies(f, t, 18, alpha=smooth(seg(t, 6, 10)))
    fg(f, 'fg_flowers', 200)
    pop_text(f, '完', 960, 230, t, 13.5, None, 170, fill=(236, 120, 60))
    return f

SCENES = dict(title=title, meet=meet, challenge=challenge, start=start, sprint=sprint, taunt=taunt, nap=nap,
              pass_=pass_, wake=wake, chase=chase, finish=finish, moral=moral, finale=finale)
ORDER = ['title', 'meet', 'challenge', 'start', 'sprint', 'taunt', 'nap', 'pass', 'wake', 'chase', 'finish', 'moral', 'finale']
def fn_of(name): return SCENES['pass_' if name == 'pass' else name]
