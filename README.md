# Tortoise and the Hare · 龟兔赛跑（纸艺木偶动画 v4）

<p align="center">
  <img src="covers/cover_16x9.png" width="100%" alt="龟兔赛跑 横版封面">
</p>

一部约 **3 分 56 秒**的中文儿童动画短片，讲伊索寓言《龟兔赛跑》。画面是纸艺剪纸 + 毛毡质感的绘本风格，配温柔女声旁白、字幕和原创管弦配乐。

整部片子**用代码逐帧渲染**，没有用任何动画软件。本仓库是 v2 及之后版本的重制管线（v4 成片：1920×1080 / 30 fps / H.264 + AAC）。

> **[下载 v4 成片](https://github.com/SherlockGy/tortoise-and-hare/releases/download/v4/tortoise-and-hare-v4.mp4)**。视频通过 GitHub Release 发布；按下方步骤可在 `out/龟兔赛跑.mp4` 重新生成成片。

## 亮点

- **自然的兔子奔跑**：用 codex CLI 重新生成了四足奔跑循环（蓄力 → 蹬地 → 腾空 → 落地）四帧，统一比例并按头身质心对齐。前进距离与步频绑定，不会滑步。
- **角色踩在实地上**：每张背景都标定了地面线，角色只走画里真实存在的小路和草地，脚下有接触阴影。
- **镜头与道具同一坐标系**：镜头越出背景边界时修正的是镜头本身，所以终点门、起点横幅、树桩等道具和背景严格同步，不会漂移。
- **跟拍视差**：跑步段背景慢移、前景草地快移，加上速度线和扬尘。
- **素材化的终点丝带**：红丝带用 codex 生成的素材切成竖条沿曲线摆放（简易布料变形）。未断时下垂飘动，被乌龟撞断后两半挂在立柱上自然垂落、来回摆动。
- **音画同步**：画面、配乐、旁白、字幕共用 `src/timeline.py` 的时间轴，动作对齐配乐里的哨声、断带声、鼾声、心跳等音效。

## 封面

三种画幅各自由 **Codex CLI 的图像生成单独绘制**（不是从一张图裁出来，也不是用片中素材拼合）。生成时把项目原有的兔子、乌龟 PNG 和背景作为角色和画风参考。随后 `v2/cover_finalize.py` 按目标比例等比裁切、缩放到精确像素（不拉伸），再用项目字体 ZCOOL 加上标题“龟兔赛跑”。

| 横版 16:9（1920×1080） | 横版 4:3（1440×1080） | 竖版 9:16（1080×1920） |
|---|---|---|
| ![横版封面 16:9](covers/cover_16x9.png) | ![横版封面 4:3](covers/cover_4x3.png) | ![竖版封面 9:16](covers/cover_9x16.png) |

### 重新生成封面

需要本机已安装并登录 [Codex CLI](https://github.com/openai/codex)，且能使用它的图像生成功能。脚本默认读取原始管线的 `assets/raw/` 参考图；如果只有本代码包，可以把脚本里的 `RAW` 改成 `assets/cut`。

```bash
cd assets/regen/covers
# 提示词：prompt_common.txt（通用画风与构图要求）+ prompt_cover_<画幅>.txt（各画幅构图）
./gen_covers.sh                 # 生成缺失的封面原图（三张并行，各自独立生成）
rm cover_4x3.png && ./gen_covers.sh cover_4x3   # 只重画某一张
cd ../../..
python3 v2/cover_finalize.py    # 裁切到精确尺寸 + 加标题 → covers/
# 可微调裁切中心和标题位置，例如：python3 v2/cover_finalize.py cover_4x3:cy=0.45,ty=0.12,tx=0.4
```

脚本里实际执行的命令（每张封面一次）：

```bash
codex exec --skip-git-repo-check -s workspace-write \
  -i assets/raw/hare_stand.png -i assets/raw/hare_sprint.png \
  -i assets/raw/tortoise_stand.png -i assets/raw/tortoise_determined.png \
  -i assets/raw/bg_start.png -   # 提示词从标准输入传入
```

## 目录结构

```
.
├── README.md
├── THIRD_PARTY_NOTICES.md   # 第三方内容、字体/音色库许可证、AI 生成说明
├── requirements.txt         # v2 渲染器依赖
├── pyproject.toml           # 原始管线（含 skia 等）依赖
├── covers/                  # 封面成品：cover_16x9.png / cover_4x3.png / cover_9x16.png（Codex 生成 + 加标题）
├── v2/                      # v2+ 渲染器（成片用这个）
│   ├── core.py              # 精灵缓存、镜头、背景/跟拍背景、字幕、缓动、奔跑/步行循环
│   ├── v2scenes.py          # 13 幕分镜：每个函数输入幕内秒数，返回一帧
│   ├── render.py            # 多进程分段渲染 → 拼接 → 混入配乐
│   ├── prep_v2.py           # 把素材预缩放到成片尺寸，生成 v2/cache/
│   ├── cover_finalize.py    # 封面后期：Codex 原图等比裁切到精确尺寸 + ZCOOL 标题 → covers/
│   ├── key_regen.py         # 对 assets/regen 下的绿底原图抠图
│   └── snap.py              # 调试：抽指定时间点拼成检查图
├── src/                     # 原始管线（时间轴、旁白、配乐、素材生成/抠图、旧版渲染）
│   ├── timeline.py          # ★ 全片时间轴与旁白入点（v2 也用它）
│   ├── prep.py              # 纯色背景抠图算法（key_regen 复用）
│   ├── gen_assets.py        # 用 codex CLI 批量生成素材的提示词与脚本
│   ├── narration.py / minimax.py   # MiniMax 旁白合成（需要自己的 API Key，放 .env，不随包提供）
│   ├── music.py             # 程序化编曲 + 混音（需 GeneralUser GS 音色库）
│   └── engine.py / scenes.py / ...  # v1 旧版 skia 渲染器（仅供参考）
└── assets/
    ├── cut/                 # 抠好的角色、背景、道具 PNG
    ├── regen/               # v2 新生成：gallop_1~4（兔子奔跑）、ribbon / ribbon_half（红丝带）及生成脚本
    │   └── covers/          # Codex 封面原图（无标题）+ gen_covers.sh + 提示词 prompt_*.txt
    ├── fonts/               # ZCOOL 快乐体（字幕）、ZCOOL 庆科黄油体（标题）
    ├── voice/               # 43 句旁白 wav + voice.json（文本与时长）
    └── music/music.m4a      # 成片配乐（已混入旁白、音效，人声处自动压低）
```

## 环境要求

- Python ≥ 3.11（在 3.13 上测试）
- ffmpeg（命令行可用，需带 libx264）
- 内存 ≥ 8 GB，CPU 越多越快（8 核约 2 分钟渲染完整片）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# macOS: brew install ffmpeg    Ubuntu: sudo apt install ffmpeg
```

## 渲染

```bash
# 1) 预缩放素材（只需一次，生成 v2/cache/）
python3 v2/prep_v2.py

# 2) 渲染完整成片 → out/龟兔赛跑.mp4
PROCS=6 python3 v2/render.py

# 只渲染一段（按帧号，30 fps）：例如 2:42–2:52 冲线段
PROCS=4 python3 v2/render.py out/test_chunks 4860 5160 out/test_finish.mp4

# 封面：Codex 原图 → 精确尺寸 + 标题（重新生成原图见上文“重新生成封面”）
python3 v2/cover_finalize.py

# 抽几个时间点（秒）拼成检查图
python3 v2/snap.py out/check.jpg 3 62 137 165.8 200
```

## 管线说明

1. **素材**：`src/gen_assets.py` 调用 codex CLI 生成绿/品红纯色底的角色、背景、道具，`src/prep.py` 抠图得到 `assets/cut/`。v2 新增的奔跑帧和丝带由 `assets/regen/*.sh` 生成，`v2/key_regen.py` 抠图。
2. **旁白**：`src/narration.py` 通过 MiniMax `speech-2.8-hd` 合成 43 句旁白，得到 `assets/voice/`。
3. **时间轴**：`src/timeline.py` 用“每幕速度 + 小节数”定义 13 幕，旁白入点用拍号表示，全片共用。
4. **配乐**：`src/music.py` 用 GeneralUser GS 音色程序编曲、合成音效，铺入旁白并做闪避，得到 `music.wav`。本包附的是它的 AAC 版 `assets/music/music.m4a`。
5. **画面（v2）**：`v2/prep_v2.py` 预缩放素材。`v2/v2scenes.py` 逐幕描述角色位置、动作帧、镜头，以及粒子（扬尘、落叶、Z 字、彩纸、萤火虫）。`v2/core.py` 负责合成、字幕和交叉淡化。`v2/render.py` 用多进程把帧直接管道给 ffmpeg 编码，再拼接并混入配乐。

## 版本记录

- **v2**：重写渲染器；兔子改用四足奔跑循环；重新排版每一幕；字幕放大；跟拍视差。
- **v3**：角色只走画里真实的路面和草地；修正镜头越界导致终点门等道具漂移的问题，冲线段固定机位。
- **v4**：“乌龟已经快到终点了”改为从山坡远眺（终点和乌龟都远且小，之后逐步拉近）；猫头鹰地图的虚线终点正好落在旗杆底部；终点红丝带改用生成的素材，并做了自然的断开、垂落、摆动动画。

## 素材与致谢

- 角色、背景、道具，兔子奔跑帧（`assets/regen/gallop_*`）、红丝带（`assets/regen/ribbon*`）以及三张封面插画（`assets/regen/covers/`）：由 **OpenAI codex CLI** 的图像生成功能生成。
- 旁白：MiniMax 语音合成。
- 字体：ZCOOL 快乐体、ZCOOL 庆科黄油体（SIL OFL 1.1）。
- 音色库：GeneralUser GS（S. Christian Collins，GeneralUser GS License v2.0，本包未附带音色库文件）。
- 故事：伊索寓言《龟兔赛跑》，公版。

详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
