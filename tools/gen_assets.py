# 批量调用 codex CLI 生成《龟兔赛跑》纸艺木偶素材（并发执行，已存在的文件跳过）
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "assets" / "raw"
LOG = "[gen_assets 素材生成]"

# 统一画风：纸艺剪纸 + 毛毡质感的绘本风格
STYLE = (
    "Handcrafted layered paper-cut and felt craft style, like a stop-motion paper puppet film: "
    "cut colored cardstock, felt and watercolor-textured paper pieces stacked in layers with subtle depth, "
    "visible paper fibers, soft deckled cut edges. Warm, gentle storybook palette "
    "(cream, butter yellow, sage and spring green, sky blue, soft coral, lavender). Cozy, friendly, "
    "for young children. Award-winning picture book quality."
)


def cutout_suffix(key="green"):
    hexv = "#00FF00" if key == "green" else "#FF00FF"
    name = "green" if key == "green" else "magenta"
    return (
        " Centered with generous empty margin on all sides, the whole figure fully visible and not cropped, "
        "a thin white paper-cut border around the silhouette, no cast shadow, no ground, no text. "
        f"Background: perfectly flat solid pure {name} ({hexv}) with nothing else on it."
    )


BG_SUFFIX = (
    " Wide landscape composition (3:2), a layered paper diorama with soft depth between layers, "
    "the lower half is open flat ground where characters can stand. "
    "No characters, no animals, no people, no text, no border, no frame."
)

# ---------------- 角色设定 ----------------
HARE = ("a lanky young hare with soft cream-white felt fur, very long upright ears with blush-pink inner ears, "
        "a fluffy round cotton tail, long strong hind legs, big expressive amber eyes, a sky-blue neckerchief "
        "with tiny white polka dots, and a cheerful gap-toothed grin")
TORTOISE = ("a small sturdy tortoise with a domed moss-green felt shell decorated with simple hexagon paper patches, "
            "a warm butter-yellow plastron, a soft sage-green head and sturdy little legs, big gentle dark eyes, "
            "a tiny red knitted neckerchief, and a small white daisy tucked beside the shell")
OWL = ("a plump round owl referee with soft brown and cream felt feathers, big round amber eyes behind tiny round "
       "wire glasses, a little wooden whistle hanging from a red cord around the neck, and a tuft of feathers on top "
       "of the head like a judge's wig")
FOX = ("a small lively red fox with bright orange felt fur, a cream chest and tail tip, a huge fluffy tail, "
       "tufted ears, and a mustard-yellow neckerchief")
HEDGEHOG = ("a round little hedgehog with soft brown paper spines, a cream face and belly, tiny paws, a button nose, "
            "and a lavender scarf")
MOUSE = ("a tiny grey felt mouse with round pink ears, a cream belly, a long thin tail, and a little green acorn cap")
BIRD = ("a small round bluebird with sky-blue felt feathers, a cream belly, a tiny orange beak, and a cheerful eye")


def ch(desc, pose, key="green"):
    return (f"A single character for a children's animated film, made as a handcrafted paper-cut puppet: {desc}. "
            f"{pose} {STYLE}" + cutout_suffix(key))


def ref_ch(desc, pose, key="green", keep="the identical design, face, colors, clothing, proportions and paper-cut felt craft style"):
    return ("Use the attached image as the exact character reference. Generate a NEW image of the SAME character, "
            f"keeping {keep}. New pose: {pose} {STYLE}" + cutout_suffix(key))


def edit(change, key="green"):
    # 精修动作帧：在参考图上只改动局部，保证与原图逐帧对齐
    return ("Edit the attached image to make the next frame of a frame-by-frame animation. Keep EVERYTHING else exactly "
            "the same as the attached image: the same character design, face, colors, clothing, proportions, size, "
            "position in the frame, camera angle, paper-cut felt craft style, white paper border, and the perfectly flat "
            f"solid pure {key} background. Only change this: {change} "
            "No text, no shadow, no ground, nothing else added.")


def prop(desc, key="green"):
    return f"A single handcrafted paper-cut prop for a children's animated film: {desc}. {STYLE}" + cutout_suffix(key)


# ---------------- 第一批：基准角色 / 背景 / 道具 ----------------
JOBS = {
    # 角色基准姿势（全部侧面朝右）
    "hare_stand": dict(prompt=ch(HARE, "Full body, standing upright on long hind legs, clear side view facing right with the head turned slightly toward the viewer, one paw on the hip, confident happy grin.")),
    "tortoise_stand": dict(prompt=ch(TORTOISE, "Full body, standing on all four legs, clear side view facing right with the head turned slightly toward the viewer, calm gentle smile.")),
    "owl_stand": dict(prompt=ch(OWL, "Full body, standing upright, three-quarter view facing right, one wing holding the wooden whistle, calm important expression.")),
    "fox_stand": dict(prompt=ch(FOX, "Full body, standing on all four legs, clear side view facing right with the head turned toward the viewer, friendly smile.")),
    "hedgehog_stand": dict(prompt=ch(HEDGEHOG, "Full body, standing upright on little hind legs, three-quarter view facing right, paws clasped hopefully, sweet smile.")),
    "mouse_stand": dict(prompt=ch(MOUSE, "Full body, standing upright on little hind legs, three-quarter view facing right, tiny paws held together, excited smile.")),
    "bird_fly": dict(prompt=ch(BIRD, "Full body in flight, side view facing right, wings raised high in an upstroke, tail spread.")),
    # 背景
    "bg_start": dict(prompt="A sunny forest clearing at the edge of a wide meadow: a broad flat grassy starting area across the lower half, a winding dirt path running from the left toward distant blue hills, a big friendly oak tree at the far right edge, round bushes, wildflowers, butterflies, soft paper clouds and a warm morning sky. The middle of the clearing is open for a starting line and characters. " + STYLE + BG_SUFFIX),
    "bg_forest": dict(prompt="A winding forest path through a friendly paper forest: tall slender trees with layered round canopies on both sides, ferns, mushrooms and wildflowers along the path, dappled golden light spots on the flat open path across the lower half, a few distant hills peeking through, soft sky. The path runs from lower left to the distant center. " + STYLE + BG_SUFFIX),
    "bg_oak": dict(prompt="A peaceful grassy hill under one huge old oak tree with a broad leafy canopy on the left side and a thick trunk, soft shade under the tree, wildflowers and clover, a gentle slope, the right side open with distant hills and a winding path, warm afternoon light. " + STYLE + BG_SUFFIX),
    "bg_finish": dict(prompt="A festive forest finish clearing: a wide flat grassy area in the lower half, a dirt path leading in from the left, colorful paper bunting strung between trees in the background, round bushes and flowers, distant blue hills, bright sky. Leave the center open for a finish line. " + STYLE + BG_SUFFIX),
    "bg_sunset": dict(prompt="A gentle hill at golden sunset with a winding dirt path, a big old oak tree silhouette on the left, warm orange, peach and lavender paper sky, a large soft setting sun near the horizon, distant layered hills, open grassy ground in the lower half, a few tiny fireflies. " + STYLE + BG_SUFFIX),
    # 前景与道具
    "fg_grass": dict(prompt="A long horizontal border strip of paper-cut felt meadow grass: layered sage and spring green blades with tiny butter-yellow and coral wildflowers, spanning the full width of the image along the bottom, about one third of the image height, the top edge is a soft uneven grass line. " + STYLE + " Everything above the strip is perfectly flat solid pure magenta (#FF00FF). No text."),
    "fg_flowers": dict(prompt="A long horizontal border strip of paper-cut felt wildflowers and clover: coral, butter-yellow, lavender and white paper blossoms on spring-green stems, spanning the full width of the image along the bottom, about one quarter of the image height, soft uneven top edge. " + STYLE + " Everything above the strip is perfectly flat solid pure magenta (#FF00FF). No text."),
    "props": dict(prompt="A sheet of separate handcrafted paper-cut props arranged in a loose grid of 2 rows and 4 columns with large empty space between every item, no item touching another: a bunch of orange carrots with green leafy tops, a small gold paper trophy cup with two handles, a round wooden pocket watch with a red cord, a red-and-white checkered racing flag on a short wooden stick, a woven picnic basket, a shiny red apple, a yellow-spotted red mushroom, a small bunch of white daisies. " + STYLE + " Each item has a thin white paper-cut border. Background: perfectly flat solid pure magenta (#FF00FF) with nothing else on it, no text."),
    "start_banner": dict(prompt=prop("two rustic wooden posts connected by a garland of colorful triangular paper bunting, with a blank cream paper banner hanging in the middle, absolutely no letters or writing, front view, wide and low")),
    "finish_banner": dict(prompt=prop("two rustic wooden posts with a long red-and-white checkered paper banner stretched between them, blank with no letters or writing, front view, wide and low")),
    "paper_texture": dict(prompt="A seamless close-up of warm cream handmade watercolor paper texture, subtle fibers and soft grain, flat even lighting, no objects, no text, no border."),
}

# ---------------- 第二批：动作帧（参考基准图） ----------------
JOBS_REF = {
    # 兔子
    "hare_run_a": dict(ref="hare_stand", prompt=ref_ch(HARE, "Full body, sprinting to the right on two long hind legs: the near leg kicked back, the far leg stretched forward, arms swinging, ears blown back, body leaning forward, big joyful open-mouth grin.")),
    "hare_blink": dict(ref="hare_stand", prompt=edit("the hare's eyes are gently closed in a happy blink (curved closed eyelids), everything else identical.")),
    "hare_talk": dict(ref="hare_stand", prompt=edit("the hare is talking boastfully: mouth open as if speaking, one paw lifted and gesturing outward, eyebrows raised. Legs unchanged.")),
    "hare_taunt": dict(ref="hare_stand", prompt=edit("the hare is laughing unkindly: head tipped back, eyes squeezed shut, mouth wide open in a big laugh, one paw pointing forward and down at something small. Legs unchanged.")),
    "hare_eat": dict(ref="hare_stand", prompt=edit("the hare is lounging comfortably and nibbling a bright orange carrot held in both paws, cheeks full, eyes half closed with delight, legs stretched out. Keep the same size and position.")),
    "hare_wake": dict(ref="hare_stand", prompt=ref_ch(HARE, "Full body, sitting bolt upright in alarm: ears straight up, eyes wide open, mouth open in a gasp, paws raised. Keep the same character design, colors and scale.")),
    "hare_sad": dict(ref="hare_stand", prompt=edit("the hare is ashamed and sad: head hanging low, ears drooping down, eyes looking down, small frown, shoulders slumped. Legs unchanged.")),
    "hare_cheer": dict(ref="hare_stand", prompt=edit("the hare is celebrating: both arms thrown up high, eyes closed in a huge happy smile, one hind leg kicked up. Everything else identical.")),
    # 乌龟
    "tortoise_walk_a": dict(ref="tortoise_stand", prompt=edit("the tortoise is mid-step walking slowly to the right: the near front leg lifted and reaching forward, the near hind leg pushed back, head stretched a little forward. Everything else identical.")),
    "tortoise_blink": dict(ref="tortoise_stand", prompt=edit("the tortoise's eyes are gently closed in a calm blink, everything else identical.")),
    "tortoise_talk": dict(ref="tortoise_stand", prompt=edit("the tortoise is speaking calmly: mouth open a little, head raised politely, kind eyebrows. Legs unchanged.")),
    "tortoise_look_up": dict(ref="tortoise_stand", prompt=edit("the tortoise looks up and to the right at someone much taller: neck stretched up, head tilted up, eyes looking upward, patient expression. Legs unchanged.")),
    "tortoise_determined": dict(ref="tortoise_stand", prompt=edit("the tortoise looks determined: head lowered and pushed forward, eyebrows angled down, mouth set in a firm little line, eyes focused ahead. Legs unchanged.")),
    "tortoise_tired": dict(ref="tortoise_stand", prompt=edit("the tortoise is tired but still going: eyes half closed, two little paper sweat drops beside the head, mouth open panting, legs still planted. Everything else identical.")),
    "tortoise_cross": dict(ref="tortoise_stand", prompt=edit("the tortoise stretches its neck as far forward as possible, eyes squeezed shut with effort, front feet reaching forward, about to cross a line. Everything else identical.")),
    "tortoise_cheer": dict(ref="tortoise_stand", prompt=edit("the tortoise is overjoyed: head raised high, eyes closed in a happy smile, mouth open, front legs lifted slightly off the ground. Everything else identical.")),
    "tortoise_nod": dict(ref="tortoise_stand", prompt=edit("the tortoise nods kindly: head dipped down a little, eyes closed in a warm smile. Legs unchanged.")),
    # 猫头鹰
    "owl_talk": dict(ref="owl_stand", prompt=edit("the owl is speaking formally: beak open, one wing raised for emphasis, eyebrows raised. Everything else identical.")),
    "owl_wingup": dict(ref="owl_stand", prompt=edit("the owl raises one wing high above its head like a starter's flag, beak wide open mid-shout, chest puffed out. Everything else identical.")),
    "owl_blink": dict(ref="owl_stand", prompt=edit("the owl's eyes are closed in a slow blink behind the little round glasses, everything else identical.")),
    "owl_cheer": dict(ref="owl_stand", prompt=edit("the owl is cheering: both wings thrown up high, eyes closed in a delighted smile, little feathers fluffed. Everything else identical.")),
    # 观众
    "fox_cheer": dict(ref="fox_stand", prompt=edit("the fox is cheering: front paws lifted off the ground, mouth open in a happy shout, tail high. Everything else identical.")),
    "hedgehog_cheer": dict(ref="hedgehog_stand", prompt=edit("the hedgehog is cheering: both little paws raised high, eyes closed in a happy smile, bouncing on tiptoe. Everything else identical.")),
    "mouse_cheer": dict(ref="mouse_stand", prompt=edit("the mouse is cheering: both tiny paws thrown up, mouth open in a squeak of joy, tail curled up. Everything else identical.")),
}

# ---------------- 第三批：派生动作 ----------------
JOBS_DERIVED = {
    "hare_run_b": dict(ref="hare_run_a", prompt=edit("the legs and arms swap to the opposite phase of the same sprint: the far leg kicked back, the near leg stretched forward, ears blown back the other way. Everything else identical.")),
    "tortoise_walk_b": dict(ref="tortoise_walk_a", prompt=edit("the legs swap to the opposite phase of the same slow walk: the far front leg lifted and reaching forward, the near front leg planted, the near hind leg forward. Everything else identical.")),
    "hare_sprint": dict(ref="hare_run_a", prompt=edit("the hare is sprinting desperately, lower and faster: body stretched almost flat forward, ears pinned back, eyes wide with panic, front paws reaching far ahead, hind legs fully extended back. Everything else identical.")),
    "hare_sleep": dict(ref="hare_stand", prompt=ref_ch(HARE, "Full body, the same hare lying flat on its back on the ground fast asleep: eyes closed, mouth slightly open, ears flopped out to the sides, long legs relaxed and splayed, fluffy tail under the body, peaceful smile.")),
    "bird_fly2": dict(ref="bird_fly", prompt=edit("the bluebird's wings are swept down in the downstroke, the next frame of the same flight. Everything else identical.")),
    # 猫头鹰裁判的秒表（道具拼版已含手表，但这里单独做一个大秒表，画面更清楚）
    "stopwatch": dict(prompt=prop("a round wooden pocket stopwatch with a cream paper face, red second hand, a small red button on top and a red cord, front view")),
    "tortoise_look_back": dict(ref="tortoise_stand", prompt=edit("the tortoise is walking forward but turns its head back over its shoulder to the left, eyes wide with worry, mouth slightly open. Legs unchanged.")),
    "tree_stump": dict(prompt=prop("a friendly old tree stump with a flat top, visible growth rings, a little moss and two small mushrooms at the base, front three-quarter view, wide and low so a small owl can stand on it")),
    "blanket": dict(prompt=prop("a rectangular red-and-white gingham paper picnic blanket seen at a slight angle, flat and empty, softly wavy edges, no objects on it")),
    "hare_snore": dict(ref="hare_sleep", prompt=edit("a small translucent pale-blue paper snore bubble grows from the hare's nose, mouth open wider, eyes still closed, everything else identical.")),
    "hare_lie": dict(ref="hare_stand", prompt=ref_ch(HARE, "The same hare is now LYING ON ITS SIDE ON THE GROUND, fast asleep. The whole body is horizontal and parallel to the ground, not standing: the head rests on the ground on the left side, the long ears are draped forward and lie flat, the torso lies on its side, the legs are folded and relaxed, the fluffy tail is at the right. Eyes closed, peaceful smile, one paw tucked under the cheek. Side view at ground level. Do not keep the standing pose or the arms behind the head. The body must be horizontal.")),
    "nature": dict(prompt="A sheet of separate handcrafted paper-cut nature decorations arranged in a loose grid of 3 rows and 3 columns with large empty space between every item, no item touching another: a fluffy cream paper cloud, a second slightly smaller cream cloud, a third long thin cloud, an orange paper oak leaf, a yellow paper round leaf, a sage-green paper oval leaf, a coral paper maple leaf, a small golden five-pointed paper star, a pink-and-cream paper butterfly with open wings. " + STYLE + " Each item has a thin white paper-cut border. Background: perfectly flat solid pure magenta (#FF00FF) with nothing else on it, no text."),
}


def run_job(name, spec):
    out = RAW / f"{name}.png"
    if out.exists():
        return name, "skip"
    prompt = (
        "Use your image generation tool to create exactly ONE image from the image prompt below, "
        f"then copy the resulting PNG file into the current working directory as {name}.png. "
        "Do not do anything else and do not create any other files.\n\nImage prompt:\n" + spec["prompt"]
    )
    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "workspace-write"]
    if spec.get("ref"):
        cmd += ["-i", str(RAW / f"{spec['ref']}.png")]
    cmd += ["-"]
    t = time.time()
    r = None
    for attempt in range(2):
        r = subprocess.run(cmd, cwd=RAW, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if out.exists():
            return name, f"ok {time.time() - t:.0f}s"
    return name, "FAIL: " + (r.stdout or "")[-400:] + (r.stderr or "")[-400:]


def main():
    batch = sys.argv[1] if len(sys.argv) > 1 else "a"
    only = set(sys.argv[2:])
    jobs = {"a": JOBS, "b": JOBS_REF, "c": JOBS_DERIVED, "d": {"hare_snore": JOBS_DERIVED["hare_snore"]}}[batch]
    items = [(k, v) for k, v in jobs.items() if not only or k in only]
    RAW.mkdir(parents=True, exist_ok=True)
    workers = int(os.environ.get("GEN_WORKERS", "5"))
    with ThreadPoolExecutor(workers) as ex:
        for name, status in ex.map(lambda kv: run_job(*kv), items):
            print(f"{LOG}[{name}] {status}", flush=True)


if __name__ == "__main__":
    main()
