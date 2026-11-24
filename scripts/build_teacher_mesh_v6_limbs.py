#!/usr/bin/env python3
"""Stage larger v6 limbs using the unchanged v5 artwork and source landmarks.

Numerical proportions and placement are authored targets, never medical norms.
This builder writes registration JSON only: historical manifests, all PNGs and
the running renderer configuration remain untouched.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend/public/assets/teacher-mesh"
PARENT = OUT / "rig-v5.json"

DEFAULT_CONFIGURATION = {
    "shoulders": [[365, 383], [115, 383]],
    "elbows": [[419, 560], [61, 560]],
    "forearm_length": 130,
    "rest_angle": -1.15,
    "extended_hand_reach": 82,
    "open_palm_mcp_length": 40,
    "relaxed_rest_rotations": {"-1": .50, "1": -.50},
    "head_body_translation": [0, -28],
    "gesture_paths": {
        "wave": {"target": [320, 438], "hand_rotation_offset": .157},
        "think": {"target": [296, 418], "hand_rotation_offset": -.131},
        "point": {"target": [318, 438], "hand_rotation_offset": .164},
    },
}


def _distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def build_limbs(configuration=None):
    config = copy.deepcopy(DEFAULT_CONFIGURATION)
    if configuration:
        config.update(copy.deepcopy(configuration))
    parent = json.loads(PARENT.read_text())
    arms = copy.deepcopy(parent["arms"])
    for key in ("shoulders", "elbows", "forearm_length", "rest_angle"):
        arms[key] = copy.deepcopy(config[key])
    for name, updates in config["gesture_paths"].items():
        arms["gesture_paths"][name].update(updates)

    segments = copy.deepcopy(parent["arm_segments"])
    hands = copy.deepcopy(parent["hands"])
    extraction = {}
    for spec in segments:
        meta = copy.deepcopy(parent["extraction"][spec["id"]])
        side_index = 0 if spec["side"] > 0 else 1
        upper = _distance(arms["shoulders"][side_index], arms["elbows"][side_index])
        if spec["bone"] == "elbow":
            parent_upper = _distance(parent["arms"]["shoulders"][side_index],
                                     parent["arms"]["elbows"][side_index])
            scale = meta["runtime_uniform_scale_configuration"] * upper / parent_upper
            spec["size"] = [dimension*scale for dimension in meta["size"]]
        else:
            native = upper if spec["bone"] == "upper" else arms["forearm_length"]
            source_length = _distance(*meta["bone_anchors_source_configuration"])
            scale = native / source_length
            spec["size"] = [dimension*scale for dimension in meta["size"]]
            meta["bone_length_native_configuration"] = native
        meta["runtime_uniform_scale_configuration"] = scale
        meta["staging_revision_configuration"] = 6
        extraction[spec["id"]] = meta

    for name, group in hands.items():
        for side, spec in group["sides"].items():
            key = name+"-hand-"+("right" if int(side)>0 else "left")
            meta = copy.deepcopy(parent["extraction"][key])
            landmarks = meta["landmarks_source_configuration"]
            source_reach = _distance(landmarks["wrist"], landmarks["main_tip"])
            if name == "open":
                source_palm = _distance(landmarks["wrist"], landmarks["middle_mcp"])
                scale = config["open_palm_mcp_length"]/source_palm
            else:
                scale = config["extended_hand_reach"]/source_reach
            spec["size"] = [dimension*scale for dimension in meta["size"]]
            spec["anatomical_scale_uniform_configuration"] = scale
            spec["wrist_tip_length_native_configuration"] = source_reach*scale
            if name == "relaxed":
                spec["rest_rotation"] = config["relaxed_rest_rotations"][side]
            meta.update(runtime_uniform_scale_configuration=scale,
                        wrist_tip_length_native_configuration=source_reach*scale,
                        staging_revision_configuration=6)
            extraction[key] = meta
        # Keep the base specification consistent with the authored right side;
        # both runtime sides still resolve their distinct unmirrored PNGs.
        group.update(copy.deepcopy(group["sides"]["1"]))

    assets = {spec["asset"] for spec in segments}
    assets.update(spec["asset"] for group in hands.values() for spec in group["sides"].values())
    provenance = {
        "parent_manifest": PARENT.name,
        "parent_manifest_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(),
        "reused_asset_sha256": {asset: hashlib.sha256((OUT/asset).read_bytes()).hexdigest()
                                for asset in sorted(assets)},
        "artwork_changes": False,
    }
    result = {"arms": arms, "arm_segments": segments, "hands": hands,
              "extraction": extraction, "layout_configuration": config,
              "provenance": provenance}
    (OUT / "v6-limbs-registration.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


if __name__ == "__main__":
    result = build_limbs()
    print(json.dumps({"configuration": result["layout_configuration"],
                      "upper_length_measured_from_configuration":
                      _distance(result["arms"]["shoulders"][0], result["arms"]["elbows"][0]),
                      "provenance": result["provenance"]}, indent=2))
