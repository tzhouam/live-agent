#!/usr/bin/env python3
"""Register a repainted modest torso while retaining the v6 face and limbs.

Only largest-component alpha cleanup and uniform texture registration are used.
The original generated PNG and exact edit prompt remain versioned in source/.
Sizes and placement are authored staging configuration, not anthropometry.
"""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/assets/teacher-mesh'
SOURCE = OUT / 'source'


def build():
    source = SOURCE / 'torso-modest-v7.png'
    rgba = np.array(Image.open(source).convert('RGBA'))
    alpha = rgba[:, :, 3].copy()
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (alpha > 32).astype(np.uint8), connectivity=8)
    if count <= 1:
        raise ValueError('Empty torso artwork')
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = cv2.dilate((labels == component).astype(np.uint8),
                      np.ones((3, 3), np.uint8), iterations=1)
    rgba[:, :, 3] = np.where(keep, alpha, 0)
    ys, xs = np.where(rgba[:, :, 3] > 16)
    box = [int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1]
    tile = Image.fromarray(rgba).crop(box)
    tile.save(OUT / 'body-v7.png')

    parent = OUT / 'rig-v6.json'
    rig = json.loads(parent.read_text())
    body = next(layer for layer in rig['layers'] if layer['id'] == 'body')
    width = body['rect'][2]
    body.update(asset='body-v7.png',
                rect=[body['rect'][0], body['rect'][1], width,
                      width*tile.height/tile.width])
    rig['asset_revision'] = 7
    rig['description'] = ('Custom adult anime teacher with a repainted modest, narrower '
                          'torso, intact registered face and retained longer v6 arms '
                          'and enlarged hands; not Live2D/Cubism.')
    rig['extraction']['body'] = {
        'source': source.name, 'bounds_in_source': box,
        'size': list(tile.size), 'asset': 'body-v7.png',
        'extraction': 'largest authored alpha component; original edge alpha retained',
        'runtime_uniform_scale_configuration': width/tile.width,
    }
    rig['torso_revision'] = {
        'parent_manifest': parent.name,
        'parent_manifest_sha256': hashlib.sha256(parent.read_bytes()).hexdigest(),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_prompt': 'source/prompts-v7.json',
        'artwork_changes': 'torso only; less chest projection and narrower ribcage',
        'face_and_limb_configuration': 'unchanged from v6',
    }
    (OUT / 'rig-v7.json').write_text(json.dumps(rig, indent=2)+'\n')
    print('Built repainted torso model:', OUT / 'rig-v7.json')


if __name__ == '__main__':
    build()
