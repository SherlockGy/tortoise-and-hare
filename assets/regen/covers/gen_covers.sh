#!/bin/bash
# 用 Codex CLI 独立生成《龟兔赛跑》封面插画（每种画幅单独生成一张，无标题）
# 用法：./gen_covers.sh            生成缺失的封面
#       ./gen_covers.sh cover_4x3  只生成指定的一张（先删掉旧文件）
# 参考图默认用仓库里已有的 assets/cut。最初生成时附的是未提交的绿底原图 assets/raw。
# 若本地另有原图，可 REF_DIR=/path/to/assets/raw ./gen_covers.sh
# 生成后运行：python3 renderer/cover.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
C="$ROOT/assets/regen/covers"
REF="${REF_DIR:-$ROOT/assets/cut}"
REFS=(-i "$REF/hare_stand.png" -i "$REF/hare_sprint.png" -i "$REF/tortoise_stand.png" -i "$REF/tortoise_determined.png" -i "$REF/bg_start.png")
cd "$C"
gen() { name=$1; shift
  [ -n "$ONLY" ] && [ "$ONLY" != "$name" ] && return
  [ -f "$C/$name.png" ] && return
  prompt="Use your image generation tool to create exactly ONE image from the image prompt below, then copy the resulting PNG file into the current working directory as $name.png. Do not do anything else and do not create any other files.

Image prompt:
$(cat "$C/prompt_common.txt") $(cat "$C/prompt_$name.txt")"
  for a in 1 2; do
    echo "$prompt" | codex exec --skip-git-repo-check -s workspace-write "${REFS[@]}" - > "$C/$name.log" 2>&1
    [ -f "$C/$name.png" ] && { echo "$name ok"; return; }
  done; echo "$name FAIL"
}
ONLY=${1:-}
gen cover_16x9 & gen cover_9x16 & gen cover_4x3 &
wait; echo ALLDONE
