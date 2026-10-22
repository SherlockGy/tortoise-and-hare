# 第三方内容声明

本项目除源码外，还包含或使用了以下第三方内容。

## GeneralUser GS 音色库

- 文件：`assets/sf/GeneralUser-GS.sf2`（**本代码包未附带**，约 31 MB；成片配乐已渲染为 `assets/music/music.m4a`。如需用 `src/music.py` 重新生成配乐，请从作者主页获取音色库及其许可证放到 `assets/sf/`）
- 作者：S. Christian Collins
- 来源：https://www.schristiancollins.com/generaluser
- 许可证：GeneralUser GS License v2.0；本代码包未附带音色库及许可证，重新生成配乐前请从作者主页获取。
  - 允许用于个人或商业的音乐创作。
  - 允许在软件项目中重新打包。
  - 作者要求不要直接链接到他的下载文件；请通过作者主页获取。

## 字体

- 文件：`assets/fonts/ZCOOLKuaiLe-Regular.ttf`
- 字体：ZCOOL KuaiLe（站酷快乐体）
- 来源：Google Fonts / https://github.com/google/fonts/tree/main/ofl/zcoolkuaile
- 许可证：SIL Open Font License 1.1，全文见 `assets/fonts/OFL-zcoolkuaile.txt`。
- 文件：`assets/fonts/ZCOOLQingKeHuangYou-Regular.ttf`（站酷庆科黄油体），v2 起用于片头标题与弹出大字，同样为 SIL Open Font License 1.1，全文见 `assets/fonts/OFL-zcoolqingkehuangyou.txt`。

## AI 生成的图像

- 文件：`assets/raw/` 和 `assets/cut/` 下的全部图片；`covers/` 下的封面成品见下文 v2 新增条目。
- 生成方式：OpenAI codex CLI 的图像生成功能；提示词见 `src/gen_assets.py`。
- 角色、背景、动作帧和道具均为本片重新生成，没有沿用参考仓库的图像素材。
- v2 新增：`assets/regen/gallop_1~4.png`（兔子四足奔跑循环帧）与 `assets/regen/ribbon*.png`（终点红丝带）以及 `assets/regen/covers/cover_*.png`（封面插画，`covers/` 为加标题后的成品）同样由 codex CLI 生成，脚本见 `assets/regen/gen_run.sh`、`gen_ribbon.sh`、`covers/gen_covers.sh`；`*_cut.png` 为抠图结果。
- 使用条款以 OpenAI 的服务条款为准。

## AI 合成的旁白

- 文件：`assets/voice/*.wav`
- 生成方式：MiniMax 语音合成接口（模型 `speech-2.8-hd`，系统音色 `Chinese (Mandarin)_Gentle_Senior`）。
- 文稿见 `src/narration.py`；使用条款以 MiniMax 的服务条款为准。

## 参考实现

- 渲染管线参考并改编自：
  - https://github.com/SherlockGy/little-horse
  - https://github.com/SherlockGy/three-little-pigs
- 参考仓库未附明确的开源许可证；本项目只借鉴了其“程序化纸偶渲染 + codex 素材 + MiniMax 旁白”的工程思路与部分通用算法结构，分镜、角色、场景、旁白、配乐和全部图像素材均为本片重新创作。
- 如果后续公开分发，请自行确认参考仓库的授权条件。

## 故事

《龟兔赛跑》出自伊索寓言，属于公版故事。本片旁白为重新改编的儿童版文本。
