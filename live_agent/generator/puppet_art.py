"""Natural anime VTuber artwork on the existing CPU puppet rig.

An authored continuous bust and restrained shared transform keep the neckline intact.
Local facial patches, tabletop depth and cached contact shadows complete the scene.
No image service is called at runtime; cached source artwork remains immutable.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

if TYPE_CHECKING:
    from live_agent.generator.puppet import Pose

ASSETS = Path(__file__).parent / "assets" / "vtuber_teacher"


@lru_cache(maxsize=1)
def _artwork():
    rig = json.loads((ASSETS / "rig.json").read_text(encoding="utf-8"))
    with Image.open(ASSETS / rig["atlas"]) as source:
        atlas = source.convert("RGBA")
    if atlas.getchannel("A").getextrema()[0] != 0:
        raise ValueError("VTuber atlas must have transparent padding")
    # Remove isolated edge flecks without modifying the saved original.
    atlas.putalpha(atlas.getchannel("A").filter(ImageFilter.MinFilter(3)))
    busts = tuple(atlas.crop(box) for box in rig["bust_tiles"])
    parts = {name: atlas.crop(part["crop"]) for name, part in rig["parts"].items()}
    if rig.get("sleeves_atlas"):
        with Image.open(ASSETS / rig["sleeves_atlas"]) as source:
            sleeves = source.convert("RGBA")
        sleeves.putalpha(sleeves.getchannel("A").filter(ImageFilter.MinFilter(3)))
        for name in ("upper_arm", "forearm"):
            parts[name] = sleeves.crop(rig["parts"][name]["crop"])
    with Image.open(ASSETS / rig["props_atlas"]) as source:
        props = source.convert("RGBA")
    parts.update({name: props.crop(part["crop"]) for name, part in rig["props"].items()})
    with Image.open(ASSETS / rig["background"]) as source:
        background = source.convert("RGB")
    return rig, busts, parts, background


def _patch_box(box, size):
    return tuple(round(v * size[i % 2]) for i, v in enumerate(box))


def _feather(size):
    mask = Image.new("L", size)
    inset = max(1, round(min(size) * 0.1))
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset, inset, size[0] - inset - 1, size[1] - inset - 1),
        radius=inset * 2, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(0.5, inset / 2)))


def _speech_apertures(patch):
    """Compress the painted aperture while retaining the patch's outer skin edges."""
    w, h = patch.size
    source_top, source_bottom = round(h * 0.32), round(h * 0.68)
    states = []
    for openness in np.linspace(0.35, 1.0, 8):
        top = round(h / 2 - (h / 2 - source_top) * openness)
        bottom = round(h / 2 + (source_bottom - h / 2) * openness)
        mesh = [((0, a, w, b), (0, c, 0, d, w, d, w, c))
                for a, b, c, d in ((0, top, 0, source_top),
                                    (top, bottom, source_top, source_bottom),
                                    (bottom, h, source_bottom, h)) if b > a]
        states.append(patch.transform(patch.size, Image.Transform.MESH, mesh,
                                      Image.Resampling.BICUBIC))
    return tuple(states)


@lru_cache(maxsize=4)
def _scaled_art(w, h):
    rig, busts, parts, backdrop = _artwork()
    sx, sy = w / 480, h / 864

    def size(dimensions):
        return max(1, round(dimensions[0] * sx)), max(1, round(dimensions[1] * sy))

    bust_size = size(rig["bust_size"])
    busts = tuple(bust.resize(bust_size, Image.Resampling.LANCZOS) for bust in busts)
    boxes = {name: _patch_box(rig[name + "_patch"], bust_size)
             for name in ("eyes", "mouth", "brow")}
    masks = {name: _feather((box[2] - box[0], box[3] - box[1]))
             for name, box in boxes.items()}
    mouth_states = _speech_apertures(busts[2].crop(boxes["mouth"]))
    if rig.get("expressions_atlas"):
        with Image.open(ASSETS / rig["expressions_atlas"]) as source:
            sheet = source.convert("RGBA")
        reference = np.asarray(busts[0].crop(boxes["mouth"]), dtype=np.float32)
        registered = []
        for tile in rig["expression_tiles"]:
            patch = sheet.crop(tile).resize(mouth_states[0].size, Image.Resampling.LANCZOS)
            pixels = np.asarray(patch, dtype=np.float32).copy()
            # Match skin at the perimeter, leaving authored lips/teeth intact.
            edge = np.zeros(pixels.shape[:2], dtype=bool)
            edge[:2] = edge[-2:] = True
            edge[:, :2] = edge[:, -2:] = True
            pixels[:, :, :3] += reference[edge, :3].mean(axis=0) - pixels[edge, :3].mean(axis=0)
            registered.append(Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)))
        mouth_states = tuple(registered)
    dimensions = {**rig["parts"], **rig["props"]}
    scaled_parts = {name: part.resize(size(dimensions[name]["size"]), Image.Resampling.LANCZOS)
                    for name, part in parts.items()}
    # A textured, rounded elbow cap bridges the two sleeve directions instead of
    # leaving a flat sprite edge at the bend. It uses the same authored fabric.
    sleeve = scaled_parts["forearm"]
    diameter = max(6, round(40 * sx))
    center = (round(sleeve.width * 0.6), round(sleeve.height * 0.3))
    cap = sleeve.crop((center[0] - diameter // 2, center[1] - diameter // 2,
                       center[0] - diameter // 2 + diameter, center[1] - diameter // 2 + diameter))
    mask = Image.new("L", cap.size)
    ImageDraw.Draw(mask).ellipse((1, 1, diameter - 2, diameter - 2), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(0.5, sx)))
    cap.putalpha(Image.fromarray(np.minimum(np.asarray(cap.getchannel("A")), np.asarray(mask))))
    scaled_parts["elbow_cap"] = cap
    backdrop = backdrop.resize((w, h), Image.Resampling.LANCZOS)
    table_y = round(rig["tabletop_y"] * sy)
    front_y = round(rig["foreground_y"] * sy)
    table = backdrop.crop((0, table_y, w, h))
    front = backdrop.crop((0, front_y, w, h))
    shadows = {}
    for name in ("globe", "mug", "book", "pointer", "chalk"):
        sw = max(5, scaled_parts[name].width if name != "pointer" else scaled_parts[name].height)
        sh = max(3, round(10 * sy))
        shadow = Image.new("RGBA", (sw + 12, sh + 8))
        ImageDraw.Draw(shadow).ellipse((5, 3, sw + 6, sh + 4), fill=(65, 44, 25, 66))
        shadows[name] = shadow.filter(ImageFilter.GaussianBlur(max(1, 2 * sx)))
    hand_shadow = Image.new("RGBA", size((40, 14)))
    ImageDraw.Draw(hand_shadow).ellipse((0, 0, hand_shadow.width - 1, hand_shadow.height - 1),
                                       fill=(65, 44, 25, 35))
    shadows["hand"] = hand_shadow.filter(ImageFilter.GaussianBlur(max(1, 2 * sx)))
    return (rig, busts, scaled_parts, backdrop, table, front, table_y, front_y,
            boxes, masks, mouth_states, shadows)


def _joint_placement(part, position, anchor, angle=0.0):
    """Return the transformed sprite and origin before any camera clipping."""
    px, py = part.width * anchor[0], part.height * anchor[1]
    if abs(angle) > 0.01:
        cx, cy = part.width / 2, part.height / 2
        rotated = part.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        a = math.radians(angle)
        px, py = (rotated.width / 2 + (px - cx) * math.cos(a) + (py - cy) * math.sin(a),
                  rotated.height / 2 - (px - cx) * math.sin(a) + (py - cy) * math.cos(a))
        part = rotated
    return part, (round(position[0] - px), round(position[1] - py))


def _paste_joint(image, part, position, anchor, angle=0.0):
    """Place a sprite's joint exactly, including after an expanded rotation."""
    part, origin = _joint_placement(part, position, anchor, angle)
    image.paste(part, origin, part)


def _paste_limb(image, part, start, end, anchors):
    """Fit the authored shoulder/elbow/wrist axis with one uniform scale."""
    a, b = anchors
    source = ((b[0] - a[0]) * part.width, (b[1] - a[1]) * part.height)
    target = (end[0] - start[0], end[1] - start[1])
    scale = math.hypot(*target) / math.hypot(*source)
    dimensions = (max(1, round(part.width * scale)), max(1, round(part.height * scale)))
    if dimensions != part.size:
        part = part.resize(dimensions, Image.Resampling.BICUBIC)
    angle = math.degrees(math.atan2(*target) - math.atan2(*source))
    _paste_joint(image, part, start, a, angle)


def _face(busts, boxes, masks, mouth_states, p):
    bust = busts[0].copy()
    if p.eye_close > 0:
        box = boxes["eyes"]
        patch = Image.blend(busts[0].crop(box), busts[1].crop(box), min(1.0, p.eye_close))
        bust.paste(patch, box[:2], masks["eyes"])
    if p.mouth_open > 0.18:
        box = boxes["mouth"]
        amount = min(1.0, max(0.0, (p.mouth_open - 0.18) / 0.82))
        patch = Image.blend(mouth_states[0], mouth_states[1], amount)
        patch = Image.blend(patch, Image.blend(mouth_states[2], mouth_states[3], amount),
                            min(1.0, max(0.0, p.mouth_round)))
        # Fade the smallest aperture into the resting lips at quiet syllables.
        patch = Image.blend(busts[0].crop(box), patch, min(1.0, amount * 5))
        bust.paste(patch, box[:2], masks["mouth"])
    elif p.smile > 0.4:
        box = boxes["mouth"]
        patch = Image.blend(busts[0].crop(box), mouth_states[4], min(1.0, p.smile))
        bust.paste(patch, box[:2], masks["mouth"])
    elif p.brow > 0.2:
        box = boxes["mouth"]
        patch = Image.blend(busts[0].crop(box), mouth_states[5], min(1.0, p.brow))
        bust.paste(patch, box[:2], masks["mouth"])
    if p.brow > 0.2:
        box = boxes["brow"]
        patch = busts[0].crop(box)
        patch = patch.transform(patch.size, Image.Transform.AFFINE,
                                (1, 0, 0, 0, 1, min(1.5, p.brow)), Image.Resampling.BICUBIC)
        bust.paste(patch, box[:2], masks["brow"])
    return bust


def _motion(rig, p):
    """Common bust/joint transform in authored portrait coordinates."""
    x, y = rig["bust_position"]
    pivot = (x, y + rig["bust_size"][1])
    dx = max(-5.0, min(5.0, p.head_dx * 0.3))
    dy = max(-3.0, min(8.0, p.head_dy * 0.45))
    angle = max(-4.0, min(4.0, -math.degrees(p.head_tilt) * 0.4 - p.head_dx * 0.05))
    a = math.radians(angle)

    def transform(point):
        px, py = point[0] - pivot[0], point[1] - pivot[1]
        return (pivot[0] + dx + px * math.cos(a) + py * math.sin(a),
                pivot[1] + dy - px * math.sin(a) + py * math.cos(a))

    return transform, angle, transform(pivot)


def render_frame(w: int, h: int, p: Pose) -> np.ndarray:
    (rig, busts, parts, backdrop, table, front, table_y, front_y,
     boxes, masks, mouth_states, shadows) = _scaled_art(w, h)
    image = backdrop.copy()
    sx, sy = w / 480, h / 864
    transform, bust_angle, bust_pivot = _motion(rig, p)

    def screen(point):
        return point[0] * sx, point[1] * sy

    arms = []
    front_upper_arms = []
    for i, (side, sh, el, item) in enumerate(((1, p.r_sh, p.r_el, p.item),
                                            (-1, p.l_sh, p.l_el, "book_support" if p.item == "book" else ""))):
        shoulder = rig["shoulders"][i]
        elbow = (shoulder[0] + side * rig["upper_length"] * math.sin(sh),
                 shoulder[1] + rig["upper_length"] * math.cos(sh))
        hand = (elbow[0] + side * rig["forearm_length"] * math.sin(sh + el),
                elbow[1] + rig["forearm_length"] * math.cos(sh + el))
        shoulder, elbow, hand = map(transform, (shoulder, elbow, hand))
        lower_angle = math.degrees(math.atan2((hand[0] - elbow[0]) * sx,
                                              (hand[1] - elbow[1]) * sy))
        # Retain the key light on the window side; only palms are mirrored.
        _paste_limb(image, parts["upper_arm"], screen(shoulder), screen(elbow),
                    rig["limb_anchors"]["upper_arm"])
        # When an elbow moves across the chest, its upper arm must come in
        # front of the torso as well. Blend the depth change near the side so
        # a drink/presentation gesture cannot leave a floating forearm.
        depth = max(0.0, min(1.0, -sh / 0.3))
        if depth:
            upper = parts["upper_arm"]
            if depth < 1:
                upper = upper.copy()
                upper.putalpha(upper.getchannel("A").point(lambda value: round(value * depth)))
            front_upper_arms.append((upper, shoulder, elbow))
        arms.append((side, elbow, hand, lower_angle, item))

    _paste_joint(image, _face(busts, boxes, masks, mouth_states, p), screen(bust_pivot), (0.5, 1), bust_angle)
    for upper, shoulder, elbow in front_upper_arms:
        _paste_limb(image, upper, screen(shoulder), screen(elbow),
                    rig["limb_anchors"]["upper_arm"])
    # The torso stays behind the desk; forearms can rest on its surface.
    image.paste(table, (0, table_y))
    fingers = []
    for side, elbow, hand, lower_angle, item in arms:
        if not item and rig["tabletop_y"] + 20 < hand[1] < rig["foreground_y"] - 20:
            _paste_joint(image, shadows["hand"], screen((hand[0], hand[1] + 20)), (0.5, 0.5))
        _paste_joint(image, parts["elbow_cap"], screen(elbow), (0.5, 0.5))
        _paste_limb(image, parts["forearm"], screen(elbow), screen(hand),
                    rig["limb_anchors"]["forearm"])
        sh = p.r_sh if side > 0 else p.l_sh
        if not item and p.palm_open > 0 and side > 0:
            # Both authored palms share the wrist, despite opposite atlas axes.
            # Crossfade their silhouettes instead of switching at an angle threshold.
            layer = Image.new("RGBA", image.size)
            _paste_joint(layer, parts["relaxed_hand"], screen(hand), (0.5, 0.05), lower_angle)
            opened = Image.new("RGBA", image.size)
            _paste_joint(opened, parts["open_hand"], screen(hand), (0.5, 0.91), lower_angle + 180)
            layer = Image.blend(layer, opened, min(1.0, p.palm_open))
            image.paste(layer, (0, 0), layer.getchannel("A"))
            continue
        palm_name = ("open_hand" if item in ("count", "wave") or (not item and sh < -0.2)
                     else "thumb_hand" if item == "thumb"
                     else "grip_hand" if item or (p.brow > 0.2 and side > 0)
                     else "relaxed_hand")
        palm = parts[palm_name]
        if side < 0:
            palm = palm.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if palm_name == "relaxed_hand":
            _paste_joint(image, palm, screen(hand), (0.5, 0.05), lower_angle)
        else:
            palm_angle = 0 if item == "thumb" else lower_angle + 180
            _paste_joint(image, palm, screen(hand), (0.5, 0.91), palm_angle)
            if item in ("mug", "book", "book_support", "pointer", "chalk"):
                # A small thumb/finger overlay keeps the held object visibly gripped.
                mask = Image.new("L", palm.size)
                x0, x1 = (0.05, 0.4) if side < 0 else (0.6, 0.95)
                ImageDraw.Draw(mask).rounded_rectangle(
                    (round(palm.width * x0), round(palm.height * 0.2),
                     round(palm.width * x1), round(palm.height * 0.65)), radius=2, fill=255)
                overlay = palm.copy()
                alpha = np.minimum(np.asarray(palm.getchannel("A")), np.asarray(mask))
                overlay.putalpha(Image.fromarray(alpha))
                fingers.append((overlay, screen(hand), palm_angle))

    for name, point in rig["prop_positions"].items():
        if name == p.item:
            continue
        _paste_joint(image, shadows[name], screen(point), (0.5, 0.5))
        if name == "pointer":
            _paste_joint(image, parts[name], screen(point), (0.5, 0.5), 90)
        else:
            _paste_joint(image, parts[name], screen(point), (0.5, 1))

    for side, elbow, hand, lower_angle, item in arms:
        position = screen(hand)
        if item == "mug":
            _paste_joint(image, parts["mug"], position, (0.4, 0.88))
        elif item == "book":
            position = screen(((hand[0] + arms[1][2][0]) / 2, (hand[1] + arms[1][2][1]) / 2))
            _paste_joint(image, parts["held_book"], position, (0.5, 0.8))
        elif item == "pointer":
            _paste_joint(image, parts["pointer"], position, (0.5, 0.96), side * 15)
        elif item == "chalk":
            chalk = parts["chalk"]
            chalk = chalk.crop((0, chalk.height * 3 // 4, max(1, chalk.width // 2), chalk.height))
            _paste_joint(image, chalk, position, (0.8, 0.5), side * 50)
    for overlay, position, angle in fingers:
        _paste_joint(image, overlay, position, (0.5, 0.91), angle)
    image.paste(front, (0, front_y))
    return np.asarray(image, dtype=np.uint8)
