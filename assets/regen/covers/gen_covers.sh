#!/bin/bash
# 用 codex CLI 独立生成《龟兔赛跑》封面插画（每种画幅单独生成一张）
# 用法：./gen_covers.sh            生成缺失的封面
#       ./gen_covers.sh cover_4x3  只生成指定的一张（先删掉旧文件）
export PATH=/Users/jgy/.nvm/versions/node/v22.13.0/bin:$PATH
export https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 all_proxy=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 ALL_PROXY=http://127.0.0.1:7897
P=/Users/jgy/Documents/ai-playground/龟兔赛跑
C=$P/assets/regen/covers
RAW=$P/assets/raw
REFS=(-i "$RAW/hare_stand.png" -i "$RAW/hare_sprint.png" -i "$RAW/tortoise_stand.png" -i "$RAW/tortoise_determined.png" -i "$RAW/bg_start.png")
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
ONLY=$1
gen cover_16x9 & gen cover_9x16 & gen cover_4x3 &
wait; echo ALLDONE
