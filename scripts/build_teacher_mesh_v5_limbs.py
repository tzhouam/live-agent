#!/usr/bin/env python3
"""Build v5 tailored limb layers without changing v4 artwork or serving defaults.

Generated artwork is cropped and transformed with positive uniform scales.
All anatomical placements/landmarks are artist configuration; source and native
pixel measurements are recorded separately for visual review, not medical norms.
"""
import copy
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend/public/assets/teacher-mesh"
SOURCE = OUT / "source"
ATLAS = "limbs-atlas-v5-fitted.png"
REGIONS = {
    "upper-left": (210, 40, 445, 715),
    "upper-right": (585, 40, 815, 715),
    "forearm-left": (205, 725, 435, 1235),
    "forearm-right": (590, 725, 820, 1235),
    "elbow-left": (195, 1280, 455, 1470),
    "elbow-right": (575, 1280, 835, 1470),
    "open-hand-left": (40, 285, 630, 990),
    "open-hand-right": (640, 285, 1225, 990),
}
BONES = {
    "upper-left": ((320, 105), (306, 670)),
    "upper-right": ((704, 105), (720, 670)),
    "forearm-left": ((298, 775), (350, 1185)),
    "forearm-right": ((725, 775), (665, 1185)),
}
HAND_LANDMARKS = {
    ("relaxed", -1): {"wrist": [282, 31], "main_tip": [356, 324],
                     "middle_mcp": [319, 174], "palm_edges": [[243, 172], [391, 172]]},
    ("relaxed", 1): {"wrist": [748, 37], "main_tip": [666, 324],
                    "middle_mcp": [709, 174], "palm_edges": [[632, 172], [780, 172]]},
    ("open", -1): {"wrist": [414, 411], "main_tip": [451, 951],
                  "middle_mcp": [412, 744], "palm_edges": [[254, 648], [566, 648]]},
    ("open", 1): {"wrist": [841, 411], "main_tip": [806, 951],
                 "middle_mcp": [844, 744], "palm_edges": [[690, 648], [998, 648]]},
    ("point", -1): {"wrist": [321, 741], "main_tip": [294, 1053],
                   "middle_mcp": [322, 882], "palm_edges": [[264, 850], [385, 850]]},
    ("point", 1): {"wrist": [706, 742], "main_tip": [735, 1053],
                  "middle_mcp": [705, 882], "palm_edges": [[638, 850], [762, 850]]},
    ("wave", -1): {"wrist": [307, 1131], "main_tip": [322, 1457],
                  "middle_mcp": [316, 1280], "palm_edges": [[245, 1260], [395, 1260]]},
    ("wave", 1): {"wrist": [715, 1131], "main_tip": [698, 1457],
                 "middle_mcp": [706, 1280], "palm_edges": [[627, 1260], [777, 1260]]},
}

def extract(name, source=ATLAS):
    region = REGIONS[name]
    pixels = np.array(Image.open(SOURCE / source).convert("RGBA").crop(region))
    alpha = pixels[:, :, 3]
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (alpha > 32).astype(np.uint8), connectivity=8)
    if count < 2:
        raise ValueError(f"Empty authored v5 tile: {name}")
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = cv2.dilate((labels == largest).astype(np.uint8), np.ones((3, 3), np.uint8))
    pixels[:, :, 3] = np.where(keep, alpha, 0)
    cap_crop = None
    if name in BONES:
        # Crop the painted overlap to a round sleeve end. The broad source cut
        # corner otherwise remains visible as a point when the elbow folds.
        a, b = np.array(BONES[name], dtype=float)
        vector = b-a
        length = float(np.linalg.norm(vector))
        direction = vector/length
        yy, xx = np.mgrid[:pixels.shape[0], :pixels.shape[1]]
        dx, dy = xx+region[0]-a[0], yy+region[1]-a[1]
        along = dx*direction[0]+dy*direction[1]
        normal = -dx*direction[1]+dy*direction[0]
        proximal = name.startswith("forearm")
        distance = -along if proximal else along-length
        radius_normal, radius_along = (74, 30) if proximal else (70, 27)
        radius = np.sqrt((normal/radius_normal)**2 + (distance/radius_along)**2)
        feather = np.clip((1-radius)/.16, 0, 1)
        pixels[:, :, 3] = np.where(distance > 0, pixels[:, :, 3]*feather,
                                   pixels[:, :, 3]).astype(np.uint8)
        cap_crop = {"joint": "proximal" if proximal else "distal",
                    "shape": "half ellipse", "normal_radius_source": radius_normal,
                    "along_radius_source": radius_along, "feather_fraction": .16}
    yy, xx = np.where(pixels[:, :, 3] > 16)
    box = [int(xx.min()), int(yy.min()), int(xx.max())+1, int(yy.max())+1]
    image = Image.fromarray(pixels).crop(box)
    alpha_crop = None
    if name.startswith("elbow"):
        data = np.array(image)
        height, width = data.shape[:2]
        yy, xx = np.mgrid[:height, :width]
        radius = np.sqrt(((xx-(width-1)/2)/(width/2))**2 +
                         ((yy-(height-1)/2)/(height/2))**2)
        feather = np.clip((1-radius)/.32, 0, 1)
        data[:, :, 3] = (data[:, :, 3]*feather).astype(np.uint8)
        image = Image.fromarray(data)
        alpha_crop = {"shape": "ellipse", "feather_fraction": .32}
    asset = name+"-v5.png"
    image.save(OUT / asset)
    bounds = [region[0]+box[0], region[1]+box[1],
              region[0]+box[2], region[1]+box[3]]
    meta = {"source": source, "source_region": list(region), "trim_in_region": box,
            "bounds_in_source": bounds, "size": list(image.size), "asset": asset,
            "extraction": "largest painted alpha component; original edge alpha retained"}
    if alpha_crop:
        meta["alpha_crop_configuration"] = alpha_crop
    if cap_crop:
        meta["joint_overlap_alpha_crop_configuration"] = cap_crop
    return image, meta

def normalized(point, meta):
    x0, y0 = meta["bounds_in_source"][:2]
    width, height = meta["size"]
    value = [(point[0]-x0)/width, (point[1]-y0)/height]
    if any(v < 0 or v > 1 for v in value):
        raise ValueError(f"Authored attachment is outside {meta['asset']}: {point}")
    return value

def source_wrist_edges(image, bounds, wrist):
    """Measure the actual painted skin cross-section at the configured wrist."""
    pixels = np.array(image.convert("RGBA"))
    x0, y0 = bounds[:2]
    row = min(pixels.shape[0]-1, max(0, round(wrist[1]-y0)))
    xs = np.where(pixels[row, :, 3] > 128)[0]
    if not len(xs):
        raise ValueError("Configured wrist does not cross painted skin")
    return [[int(xs.min()+x0), int(row+y0)], [int(xs.max()+x0), int(row+y0)]]

def build_limbs():
    parent = json.loads((OUT / "rig-v4.json").read_text())
    arms = copy.deepcopy(parent["arms"])
    arms.update(shoulders=[[365, 411], [115, 411]],
                elbows=[[391, 565], [89, 565]], forearm_length=110, rest_angle=-.955)
    upper_length = float(np.hypot(26, 154))
    paths = {
        "wave": ([332, 462], 10, .30),
        "think": ([306, 445], 10, -.014),
        "point": ([330, 462], 5, .30),
    }
    arms["gesture_paths"] = {
        name: {"target": target, "outward_offset": outward, "min_duration": 3.5,
               "hand_shape_mode": "opaque", "hand_rotation_offset": rotation,
               "hand_shape_start": .6, "hand_shape_end": .8}
        for name, (target, outward, rotation) in paths.items()
    }
    segments, extraction = [], {}
    for side, suffix in [(-1, "left"), (1, "right")]:
        for bone in ("upper", "forearm"):
            name = bone+"-"+suffix
            image, meta = extract(name)
            source_length = float(np.linalg.norm(np.array(BONES[name][1])-BONES[name][0]))
            native_length = upper_length if bone == "upper" else arms["forearm_length"]
            native_scale = native_length/source_length
            segments.append({"id": name, "side": side, "bone": bone, "asset": meta["asset"],
                             "size": [v*native_scale for v in image.size],
                             "anchors": [normalized(point, meta) for point in BONES[name]]})
            meta.update(bone_anchors_source_configuration=[list(p) for p in BONES[name]],
                        runtime_uniform_scale_configuration=native_scale,
                        bone_length_source_pixels_measured=source_length,
                        bone_length_native_configuration=native_length)
            extraction[name] = meta
        name = "elbow-"+suffix
        image, meta = extract(name)
        scale = 34/image.width
        segments.append({"id": name, "side": side, "bone": "elbow", "asset": meta["asset"],
                         "size": [34, image.height*scale], "anchor": [.5, .5], "rotation": 0})
        meta["runtime_uniform_scale_configuration"] = scale
        extraction[name] = meta

    hands = {}
    for shape in ("relaxed", "open", "point", "wave"):
        sides = {}
        for side, suffix in [(-1, "left"), (1, "right")]:
            name = shape+"-hand-"+suffix
            if shape == "open":
                image, meta = extract(name, "open-hands-v5.png")
            else:
                meta = copy.deepcopy(parent["extraction"][name])
                image = Image.open(OUT / meta["asset"])
            landmarks = copy.deepcopy(HAND_LANDMARKS[(shape, side)])
            wrist, tip = np.array(landmarks["wrist"]), np.array(landmarks["main_tip"])
            source_reach = float(np.linalg.norm(tip-wrist))
            # Extended fingers use common projected reach; the cupped open hand
            # uses palm length because curled fingers shorten that projection.
            if shape == "open":
                palm_length = float(np.linalg.norm(np.array(landmarks["middle_mcp"])-wrist))
                scale = 32.5/palm_length
                native_reach = source_reach*scale
            else:
                native_reach = 66
                scale = native_reach/source_reach
            landmarks["wrist_edges"] = source_wrist_edges(
                image, meta["bounds_in_source"], landmarks["wrist"])
            axis = math.atan2(float(tip[0]-wrist[0]), float(tip[1]-wrist[1]))
            spec = {"asset": meta["asset"], "size": [v*scale for v in image.size],
                    "anchor": normalized(landmarks["wrist"], meta),
                    "rotation_offset": axis, "rest_rotation": 0, "skin_mask": None,
                    "contact_shadow": shape == "relaxed",
                    "anatomical_scale_uniform_configuration": scale,
                    "wrist_tip_length_native_configuration": native_reach}
            sides[str(side)] = spec
            meta.update(landmarks_source_configuration=landmarks,
                        wrist_tip_length_source_pixels_measured=source_reach,
                        wrist_tip_length_native_configuration=native_reach,
                        runtime_uniform_scale_configuration=scale,
                        calibration=("configured wrist-to-middle-MCP palm length; curled fingers retain their shorter projected reach"
                                     if shape == "open" else
                                     "common configured projected wrist-to-main-fingertip reach; source aspect retained"))
            extraction[name] = meta
        hands[shape] = {**sides["1"], "sides": sides}
    result = {"arms": arms, "arm_segments": segments, "hands": hands, "extraction": extraction}
    (OUT / "v5-limbs-registration.json").write_text(json.dumps(result, indent=2)+"\n")
    return result

if __name__ == "__main__":
    result = build_limbs()
    print(json.dumps({"arms": result["arms"],
                      "segments": [{"id": x["id"], "size": x["size"]} for x in result["arm_segments"]],
                      "hands": {key: {s: value["size"] for s, value in h["sides"].items()}
                                for key, h in result["hands"].items()}}, indent=2))
