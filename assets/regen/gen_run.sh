#!/bin/bash
# 重新生成兔子奔跑循环帧（Grok Bot 生成，不改动原素材）
export PATH=/Users/jgy/.nvm/versions/node/v22.13.0/bin:$PATH
export https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 all_proxy=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 ALL_PROXY=http://127.0.0.1:7897
R=/Users/jgy/Documents/ai-playground/龟兔赛跑/assets/regen
RAW=/Users/jgy/Documents/ai-playground/龟兔赛跑/assets/raw
STYLE="Handcrafted layered paper-cut and felt craft style, like a stop-motion paper puppet film: cut colored cardstock, felt and watercolor-textured paper pieces stacked in layers with subtle depth, visible paper fibers, soft deckled cut edges. Warm, gentle storybook palette. Cozy, friendly, for young children."
SUF="Strict side view facing RIGHT, the camera at body height. Same scale as the reference: the body length (nose to tail) about 70% of the image width. Centered with generous empty margin on all sides, the whole figure fully visible and not cropped, a thin white paper-cut border around the silhouette, no cast shadow, no ground line, no motion lines, no dust, no text. Background: perfectly flat solid pure green (#00FF00) with nothing else on it."
REF="Use the attached images as the exact character reference: the SAME lanky young hare with cream-white felt fur, very long ears with blush-pink inner ears, fluffy round cotton tail, big amber eyes, sky-blue polka-dot neckerchief, cheerful open-mouth grin. Keep the identical design, face, colors, neckerchief, proportions and paper-cut felt craft style. This is one frame of a smooth 4-frame GALLOP run cycle of a real hare (bounding on all four legs like a real hare, NOT running upright like a human)."
gen() { name=$1; pose=$2
  [ -f "$R/$name.png" ] && return
  prompt="Use your image generation tool to create exactly ONE image from the image prompt below, then copy the resulting PNG file into the current working directory as $name.png. Do not do anything else and do not create any other files.

Image prompt:
$REF Pose for this frame: $pose $STYLE $SUF"
  for a in 1 2; do
    echo "$prompt" | codex exec --skip-git-repo-check -s workspace-write -i "$RAW/hare_stand.png" -i "$RAW/hare_sprint.png" - > "$R/$name.log" 2>&1
    [ -f "$R/$name.png" ] && { echo "$name ok"; return; }
  done; echo "$name FAIL"
}
gen gallop_1 "GATHER: the body is compressed and rounded like a coiled spring, back arched up, the long hind feet have swung forward and are planted on the ground ahead of and outside the front paws, the front paws are behind under the chest just lifting off, head level, ears swept back. Lowest, most compact frame. All four feet roughly at the same ground level." &
gen gallop_2 "PUSH-OFF: the long hind legs are pushing powerfully against the ground behind the body, legs straightening diagonally backward, the body rising and stretching forward at a slight upward angle, front paws lifted and starting to reach forward, ears streaming back." &
gen gallop_3 "FULL FLIGHT: the whole body is fully stretched out horizontally in mid-air, all four feet off the ground, front paws reaching far forward, hind legs extended far back, ears streaming straight back. Longest, flattest frame." &
gen gallop_4 "LANDING: the front paws touch down on the ground first, one ahead of the other, below and slightly ahead of the chest, the body curving downward from hips to head, hind legs swinging forward under the belly (not yet touching), ears back." &
wait
echo ALLDONE
