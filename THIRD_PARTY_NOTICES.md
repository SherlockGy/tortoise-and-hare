# 第三方内容声明

本项目除源码外，还包含或使用了以下第三方内容。

## GeneralUser GS 音色库

- 文件：`assets/sf/GeneralUser-GS.sf2`（**本仓库未附带**。成片配乐已渲染为 `assets/music/music.m4a`，AAC、44100 Hz、双声道，时长与时间轴一致。如需用 `tools/music.py` 重新生成配乐，请从作者主页获取音色库及其许可证，放到 `assets/sf/`）
- 作者：S. Christian Collins
- 来源：https://www.schristiancollins.com/generaluser
- 许可证：GeneralUser GS License v2.0；本仓库未附带音色库及许可证全文，重新生成配乐前请从作者主页获取。
  - 允许用于个人或商业的音乐创作。
  - 允许在软件项目中重新打包。
  - 作者要求不要直接链接到他的下载文件；请通过作者主页获取。

## 字体

- 文件：`assets/fonts/ZCOOLKuaiLe-Regular.ttf`
- 字体：ZCOOL KuaiLe（站酷快乐体）
- 来源：Google Fonts / https://github.com/google/fonts/tree/main/ofl/zcoolkuaile
- 许可证：SIL Open Font License 1.1，全文见 `assets/fonts/OFL-zcoolkuaile.txt`。
- 用途：烧录字幕，以及封面上的英文副标题。
- 文件：`assets/fonts/ZCOOLQingKeHuangYou-Regular.ttf`（站酷庆科黄油体）
- 来源：Google Fonts / https://github.com/google/fonts/tree/main/ofl/zcoolqingkehuangyou
- 许可证：SIL Open Font License 1.1，全文见 `assets/fonts/OFL-zcoolqingkehuangyou.txt`。
- 用途：片头标题、弹出大字，以及 `covers/` 里的中文标题。

## AI 生成的图像

- 已入库：`assets/cut/` 下的抠图；`assets/regen/gallop_*.png`、`assets/regen/ribbon*.png` 及其 `*_cut.png`；`assets/regen/covers/cover_*.png`（无标题原图）；`covers/cover_*.png`（裁切并加上标题后的成品）。
- **未入库**：`assets/raw/`。那是抠图前的绿底或品红底原图，由 `tools/gen_assets.py` 调用 Codex CLI 写出，再由 `tools/key_raw.py` 抠进 `assets/cut/`。本仓库没有这些原图，也不能从抠图反推回去。
- 生成方式：OpenAI Codex CLI 的图像生成。角色、背景、道具的提示词在 `tools/gen_assets.py`。
- 角色、背景、动作帧和道具均为本片重新生成，没有沿用参考仓库的图像素材。
- 奔跑帧与红丝带：`assets/regen/gen_run.sh`、`assets/regen/gen_ribbon.sh` 调用 Codex CLI，`tools/key_regen.py` 抠出 `*_cut.png`。脚本默认把 `assets/cut/` 里已有的角色图当作参考；当初生成时用的是未提交的 `assets/raw/`。
- 封面：`assets/regen/covers/gen_covers.sh` 与同目录的 `prompt_*.txt` 生成无标题原图，`renderer/cover.py` 等比裁切、缩放到精确像素并叠上标题，写入 `covers/`。
- 使用条款以 OpenAI 的服务条款为准。

## AI 合成的旁白

- 文件：`assets/voice/*.wav` 与 `assets/voice/voice.json`（43 句的文本和时长）。
- 生成方式：MiniMax 语音合成接口（模型 `speech-2.8-hd`，系统音色 `Chinese (Mandarin)_Gentle_Senior`）。脚本是 `tools/narration.py`，请求封装在 `tools/minimax.py`。
- 画面渲染只读 `voice.json`，用来烧录字幕。wav 由 `tools/music.py` 在重新混音时铺进配乐；成片直接使用已经混好的 `assets/music/music.m4a`。
- 使用条款以 MiniMax 的服务条款为准。

## 参考实现

- 工程思路参考并改编自：
  - https://github.com/SherlockGy/little-horse
  - https://github.com/SherlockGy/three-little-pigs
- 参考仓库未附明确的开源许可证。本项目借鉴了“程序化纸偶渲染 + Codex 素材 + MiniMax 旁白”的做法。当前仓库里的画面是 Pillow 逐帧合成，不包含更早一次尝试用的 Skia 渲染器。分镜、角色、场景、旁白、配乐和全部图像素材均为本片重新创作。
- 如果后续公开分发，请自行确认参考仓库的授权条件。

## 故事

《龟兔赛跑》出自伊索寓言，属于公版故事。本片旁白为重新改编的儿童版文本。
