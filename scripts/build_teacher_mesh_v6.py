#!/usr/bin/env python3
"""Build longer arms/larger hands with unchanged registered teacher artwork.

All size/placement values are authored staging configuration. The intact head
and torso move together so enlarged limbs fit the existing classroom desk.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/assets/teacher-mesh'


def build():
    from build_teacher_mesh_v6_limbs import build_limbs
    limbs = build_limbs()
    parent = OUT / 'rig-v5.json'
    rig = json.loads(parent.read_text())
    translation = limbs['layout_configuration']['head_body_translation']
    layers = copy.deepcopy(rig['layers'])
    for layer in layers:
        if layer['group'] in ('head', 'body'):
            layer['rect'][0] += translation[0]
            layer['rect'][1] += translation[1]
    pivot = [value+translation[index] for index, value in enumerate(rig['head_pivot'])]
    rig.update(
        asset_revision=6,
        description='Custom adult anime teacher with longer connected arms, larger consistently calibrated hands and intact registered facial artwork; not Live2D/Cubism.',
        layers=layers, head_pivot=pivot,
        arms=limbs['arms'], arm_segments=limbs['arm_segments'], hands=limbs['hands'],
        extraction={**rig['extraction'], **limbs['extraction']},
        layout_configuration=limbs['layout_configuration'],
        artwork_parent=limbs['provenance'],
    )
    (OUT / 'rig-v6.json').write_text(json.dumps(rig, indent=2)+'\n')
    print('Built longer-arm/larger-hand staging model:', OUT / 'rig-v6.json')


if __name__ == '__main__':
    build()
