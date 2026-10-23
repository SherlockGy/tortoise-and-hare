#!/bin/bash
# 用 Codex CLI 生成终点红丝带的绿底原图。
# 参考图默认用仓库里已有的 assets/cut/finish_banner.png。最初生成时附的是未提交的 assets/raw。
# 若本地另有原图，可 REF_DIR=/path/to/assets/raw ./gen_ribbon.sh
# 生成后运行：python3 tools/key_regen.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
R="$ROOT/assets/regen"
REF="${REF_DIR:-$ROOT/assets/cut}"
cd "$R"
STYLE="Handcrafted layered paper-cut and felt craft style, like a stop-motion paper puppet film: cut colored cardstock, felt and watercolor-textured paper pieces with visible paper fibers and soft deckled cut edges. Warm, gentle storybook palette. For young children."
gen() { name=$1; desc=$2
  [ -f "$R/$name.png" ] && return
  prompt="Use your image generation tool to create exactly ONE image from the image prompt below, then copy the resulting PNG file into the current working directory as $name.png. Do not do anything else and do not create any other files.

Image prompt:
Use the attached image only as a STYLE reference (same paper-cut felt craft look and colors). A single handcrafted prop for a children's animated film: $desc $STYLE A thin white paper-cut border around the silhouette, no cast shadow, no ground, no posts, no text, no letters. Background: perfectly flat solid pure green (#00FF00) with nothing else on it."
  for a in 1 2; do
    echo "$prompt" | codex exec --skip-git-repo-check -s workspace-write -i "$REF/finish_banner.png" - > "$R/$name.log" 2>&1
    [ -f "$R/$name.png" ] && { echo "$name ok"; return; }
  done; echo "$name FAIL"
}
gen ribbon "one long straight horizontal finish-line ribbon tape made of glossy red felt-paper with a thin darker red edge stitch line along both long edges, perfectly straight and level, uniform narrow width, spanning about 90% of the image width, its height only about one fifteenth of its length, seen flat from the front, centered." &
gen ribbon_half "one torn half of a red finish-line ribbon tape made of glossy red felt-paper with a thin darker red edge stitch line along both long edges, perfectly straight and horizontal, uniform narrow width, the LEFT end cut straight and clean, the RIGHT end torn with a small ragged frayed paper edge, spanning about 85% of the image width, its height only about one fifteenth of its length, seen flat from the front, centered." &
wait; echo ALLDONE
