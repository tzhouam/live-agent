#!/usr/bin/env python3
"""Extract v4 authored garments and register rigid painted limb segments.

All placement/bone values are artist configuration, not measured anatomy.
Only alpha-connected crops and uniform scales are used; no limb artwork is
redrawn, mirrored, or stretched. Source images and prompts remain versioned.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend/public/assets/teacher-mesh"
SOURCE = OUT / "source"

GARMENTS = {
    "body": ("torso-clean-shoulders-v4.png", (170, 130, 1090, 1190)),
    "upper-left": ("limbs-slim-atlas-v4.png", (535, 35, 755, 620)),
    "upper-right": ("limbs-slim-atlas-v4.png", (800, 35, 1015, 620)),
    "forearm-left": ("limbs-slim-atlas-v4.png", (535, 630, 770, 1100)),
    "forearm-right": ("limbs-slim-atlas-v4.png", (800, 630, 1010, 1100)),
    "elbow-left": ("limbs-slim-atlas-v4.png", (550, 1220, 755, 1360)),
    "elbow-right": ("limbs-slim-atlas-v4.png", (800, 1220, 1000, 1360)),
}
HAND_ROWS = {
    "relaxed": (0, 340), "open": (340, 705),
    "point": (705, 1070), "wave": (1070, 1510),
}
# Authored source joints in atlas pixels. These follow visible shoulder caps,
# elbow overlap fabric, and cuff opening; normalized anchors derive from crops.
BONES = {
    "upper-left": ((635, 130), (659, 568)),
    "upper-right": ((910, 130), (894, 568)),
    "forearm-left": ((645, 682), (679, 1041)),
    "forearm-right": ((901, 682), (899, 1041)),
}
WRISTS = {
    ("relaxed", -1): (282, 31), ("relaxed", 1): (748, 37),
    ("open", -1): (317, 371), ("open", 1): (708, 373),
    ("point", -1): (321, 741), ("point", 1): (706, 742),
    ("wave", -1): (307, 1110), ("wave", 1): (715, 1110),
}
# Local source finger axis relative to image-down, derived from the centerline.
AXES = {
    ("relaxed", -1): .24, ("relaxed", 1): -.27,
    ("open", -1): .03, ("open", 1): -.06,
    ("point", -1): -.08, ("point", 1): .10,
    ("wave", -1): .08, ("wave", 1): -.05,
}

def extract(name, source, region):
    image = np.array(Image.open(SOURCE / source).convert("RGBA").crop(region))
    alpha = image[:, :, 3]
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (alpha > 32).astype(np.uint8), connectivity=8)
    if count <= 1:
        raise ValueError(f"Empty authored tile: {name}")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = cv2.dilate((labels == component).astype(np.uint8),
                      np.ones((3, 3), np.uint8), iterations=1)
    image[:, :, 3] = np.where(keep, alpha, 0)
    ys, xs = np.where(image[:, :, 3] > 16)
    if not len(xs):
        raise ValueError(f"Empty alpha: {name}")
    box = (int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1)
    result = Image.fromarray(image).crop(box)
    if name.startswith("elbow"):
        # Use the filled cloth interior, excluding the authored outer pad rim.
        # A soft elliptical alpha crop blends its original fabric into both
        # neighboring painted sleeves rather than showing an armor-plate edge.
        pixels = np.array(result)
        hh, ww = pixels.shape[:2]
        yy, xx = np.mgrid[:hh, :ww]
        radius = np.sqrt(((xx-(ww-1)/2)/(ww/2))**2 +
                         ((yy-(hh-1)/2)/(hh/2))**2)
        feather = np.clip((1-radius)/.32, 0, 1)
        pixels[:, :, 3] = (pixels[:, :, 3]*feather).astype(np.uint8)
        result = Image.fromarray(pixels)
    asset = f"{name}-v4.png"
    result.save(OUT / asset)
    bounds = (region[0]+box[0], region[1]+box[1],
              region[0]+box[2], region[1]+box[3])
    meta = {"source": source, "source_region": list(region),
            "trim_in_region": list(box), "bounds_in_source": list(bounds),
            "size": list(result.size), "asset": asset,
            "extraction": "largest authored alpha component; original edge alpha retained"}
    if name.startswith("elbow"):
        meta["extraction"] += "; filled cloth interior with soft elliptical alpha crop"
        meta["alpha_crop_configuration"] = {"shape": "ellipse", "feather_fraction": .32}
    return result, meta

def normalized(point, meta):
    x0, y0, _, _ = meta["bounds_in_source"]
    width, height = meta["size"]
    return [(point[0]-x0)/width, (point[1]-y0)/height]

def build_limbs():
    tiles, provenance = {}, {}
    for name, (source, region) in GARMENTS.items():
        tiles[name], provenance[name] = extract(name, source, region)
    for shape, (top, bottom) in HAND_ROWS.items():
        for side, (left, right) in [(-1, (105, 475)), (1, (550, 910))]:
            name = f"{shape}-hand-{'right' if side > 0 else 'left'}"
            tiles[name], provenance[name] = extract(
                name, "hands-atlas-v4.png", (left, top, right, bottom))

    # Short corrected collar starts just below the intact head's chin. Its V
    # closes beneath the painted clavicles, avoiding an exposed neck gap.
    bw, bh = tiles["body"].size
    body_scale = 300 / bw
    body = {"id": "body", "group": "body", "asset": "body-v4.png",
            "rect": [90, 369, 300, bh*body_scale], "grid": [2, 2]}
    segments = []
    for side, suffix in [(-1, "left"), (1, "right")]:
        for bone in ("upper", "forearm"):
            name = f"{bone}-{suffix}"
            meta = provenance[name]
            source_length = float(np.linalg.norm(np.array(BONES[name][1])-BONES[name][0]))
            native_length = float(np.hypot(7, 137)) if bone == "upper" else 112
            native_scale = native_length/source_length
            segments.append({"id": name, "side": side, "bone": bone,
                             "asset": meta["asset"],
                             "size": [value*native_scale for value in meta["size"]],
                             "anchors": [normalized(p, meta) for p in BONES[name]]})
            meta["bone_anchors_source_configuration"] = [list(p) for p in BONES[name]]
            meta["runtime_uniform_scale_configuration"] = native_scale
        name = f"elbow-{suffix}"
        ew, eh = tiles[name].size
        scale = 44 / ew
        segments.append({"id": name, "side": side, "bone": "elbow",
                         "asset": provenance[name]["asset"], "size": [44, eh*scale],
                         "anchor": [.5, .5], "rotation": 0})
    hands = {}
    for shape in HAND_ROWS:
        sides = {}
        for side, suffix in [(-1, "left"), (1, "right")]:
            name = f"{shape}-hand-{suffix}"
            meta = provenance[name]
            w, h = meta["size"]
            target_height = {"relaxed": 58, "open": 73, "point": 75, "wave": 78}[shape]
            scale = target_height / h
            sides[str(side)] = {"asset": meta["asset"], "size": [w*scale, h*scale],
                                "anchor": normalized(WRISTS[(shape, side)], meta),
                                "rotation_offset": AXES[(shape, side)],
                                "skin_mask": None,
                                "contact_shadow": shape == "relaxed"}
            if shape == "relaxed":
                sides[str(side)]["rest_rotation"] = 0
            meta["wrist_anchor_source_configuration"] = list(WRISTS[(shape, side)])
            meta["finger_axis_radians_configuration"] = AXES[(shape, side)]
        hands[shape] = {**sides["1"], "sides": sides}
    arms = {"shoulders": [[374, 411], [106, 411]],
            "elbows": [[381, 548], [99, 548]], "forearm_length": 112,
            "rest_angle": -.75, "explain_angle": -1.55,
            "present_angle": -1.30, "point_angle": .25,
            "wave_upper_angle": .32, "wave_angle": -2.88,
            "think_upper_angle": -.42, "think_angle": -2.94}
    result = {"body": body, "arm_segments": segments, "hands": hands,
              "arms": arms, "extraction": provenance}
    (OUT / "v4-limbs-registration.json").write_text(json.dumps(result, indent=2)+"\n")
    return result

if __name__ == "__main__":
    result = build_limbs()
    print(json.dumps({"body": result["body"], "arms": result["arms"],
                      "segments": len(result["arm_segments"]),
                      "hands": list(result["hands"])}, indent=2))
