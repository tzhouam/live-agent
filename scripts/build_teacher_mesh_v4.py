#!/usr/bin/env python3
"""Register generated expression edits to one intact painted teacher head.

Source coordinates and placement are artist configuration. Alignment residuals
are measured from stable artwork features, not a claim of human likeness.
This crops/aligns generated art; it does not synthesize replacement artwork.
"""
import json
import hashlib
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/assets/teacher-mesh'
SOURCE = OUT / 'source'
HEAD_SCALE = .18
HEAD_ORIGIN = [128.4, 193]
PATCHES = {
    'lids-half': ('head-soft-v4.png', [310, 505, 930, 715],
                  [(470, 618, 129, 76), (744, 590, 128, 79)]),
    'lids': ('head-blink-v4.png', [310, 505, 930, 715],
             [(470, 618, 129, 76), (744, 590, 128, 79)]),
    'mouth-soft': ('head-soft-v4.png', [480, 770, 755, 925], [(619, 844, 133, 73)]),
    'mouth-a': ('head-mouth-a-v4.png', [480, 770, 755, 925], [(619, 844, 133, 73)]),
    'mouth-o': ('head-mouth-o-v4.png', [480, 770, 755, 925], [(619, 844, 133, 73)]),
}


def aligned_edit(reference, source):
    """Estimate a similarity transform using unchanged opaque artwork."""
    cv2.setRNGSeed(0)
    height, width = reference.shape[:2]
    mask = np.where(reference[:, :, 3] > 220, 255, 0).astype(np.uint8)
    mask[500:720, 310:925] = 0
    mask[760:930, 480:760] = 0
    sift = cv2.SIFT_create(nfeatures=5000)
    a, ad = sift.detectAndCompute(cv2.cvtColor(reference, cv2.COLOR_RGBA2GRAY), mask)
    b, bd = sift.detectAndCompute(cv2.cvtColor(source, cv2.COLOR_RGBA2GRAY), None)
    matches = cv2.BFMatcher().knnMatch(bd, ad, k=2)
    good = [m for m, n in matches if m.distance < .70 * n.distance]
    if len(good) < 30:
        raise ValueError('Expression artwork has too few stable registration features')
    src = np.float32([b[m.queryIdx].pt for m in good])
    dst = np.float32([a[m.trainIdx].pt for m in good])
    transform, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                                   ransacReprojThreshold=2)
    if transform is None or int(inliers.sum()) < 30:
        raise ValueError('Expression artwork does not register to the intact head')
    residual = np.linalg.norm(cv2.transform(src[:, None, :], transform)[:, 0] - dst, axis=1)
    registered = cv2.warpAffine(source, transform, (width, height), flags=cv2.INTER_LANCZOS4)
    return registered, {'source_size': list(source.shape[1::-1]),
                        'similarity_transform': transform.tolist(),
                        'inlier_features_measured': int(inliers.sum()),
                        'median_error_source_pixels_measured': float(np.median(residual[inliers[:, 0] > 0]))}


def build_head():
    reference = np.array(Image.open(SOURCE / 'head-neutral-v4.png').convert('RGBA'))
    Image.fromarray(reference).save(OUT / 'head-neutral-v4.png')
    height, width = reference.shape[:2]
    layers = [{'id': 'face', 'group': 'head', 'asset': 'head-neutral-v4.png',
               'rect': [*HEAD_ORIGIN, width * HEAD_SCALE, height * HEAD_SCALE], 'grid': [2, 2]}]
    provenance = {'face': {'source': 'head-neutral-v4.png', 'size': [width, height],
                           'shared_source_scale_configuration': HEAD_SCALE}}
    for name, (file, box, ellipses) in PATCHES.items():
        registered, evidence = aligned_edit(reference, np.array(Image.open(SOURCE / file).convert('RGBA')))
        x0, y0, x1, y1 = box
        yy, xx = np.mgrid[y0:y1, x0:x1]
        mask = np.zeros((y1-y0, x1-x0), dtype=np.float32)
        for cx, cy, rx, ry in ellipses:
            distance = np.sqrt(((xx-cx)/rx)**2 + ((yy-cy)/ry)**2)
            mask = np.maximum(mask, np.clip((1-distance)/.14, 0, 1))
        patch = registered[y0:y1, x0:x1].copy()
        # Match the unchanged skin immediately around the edited opening.
        ring = (mask > .03) & (mask < .8)
        delta = np.median(reference[y0:y1, x0:x1, :3][ring].astype(float) - patch[:, :, :3][ring], axis=0)
        patch[:, :, :3] = np.clip(patch[:, :, :3].astype(float) + delta, 0, 255).astype(np.uint8)
        patch[:, :, 3] = (patch[:, :, 3].astype(float) * mask).astype(np.uint8)
        Image.fromarray(patch).save(OUT / f'{name}-v4.png')
        layers.append({'id': name, 'group': 'head', 'asset': f'{name}-v4.png',
                       'rect': [HEAD_ORIGIN[0]+x0*HEAD_SCALE, HEAD_ORIGIN[1]+y0*HEAD_SCALE,
                                (x1-x0)*HEAD_SCALE, (y1-y0)*HEAD_SCALE], 'grid': [2, 2]})
        provenance[name] = {'source': file, 'source_region': box,
                            'shared_source_scale_configuration': HEAD_SCALE,
                            'feather_ellipses_source_configuration': ellipses,
                            'skin_border_rgb_offset_measured': delta.tolist(), **evidence}
    return layers, provenance


def build():
    from build_teacher_mesh_v4_limbs import build_limbs
    head, extraction = build_head()
    limbs = build_limbs()
    # Artist-defined side-first lifts. Connected two-bone IK preserves sleeve
    # lengths while keeping the hand away from the bow during lift and return.
    limbs['arms']['gesture_paths'] = {
        'wave': {'target':[332,456], 'outward_offset':10, 'min_duration':3.5,
                 'hand_shape_mode':'opaque', 'hand_rotation_offset':.62,
                 'hand_shape_start':.6, 'hand_shape_end':.8},
        'think': {'target':[300,420], 'outward_offset':10, 'min_duration':3.5,
                  'hand_shape_mode':'opaque', 'hand_rotation_offset':-.2,
                  'hand_shape_start':.6, 'hand_shape_end':.8},
        'point': {'target':[330,455], 'outward_offset':5, 'min_duration':3.5,
                  'hand_shape_mode':'opaque', 'hand_rotation_offset':.7,
                  'hand_shape_start':.6, 'hand_shape_end':.8},
    }
    rig = json.loads((OUT / 'rig-v3.json').read_text())
    rig.update(asset_revision=4, coherent_head=True, arm_depth='over-body',
               expression_states={'mode':'registered-opaque','blink_half_threshold':.15,
                                  'blink_closed_threshold':.75,'mouth_soft_threshold':.04,
                                  'mouth_open_threshold':.36,'mouth_round_threshold':.55},
               description='Custom adult anime teacher with one intact registered head and painted rigid arm sections; not Live2D/Cubism.',
               head_pivot=[240, 389], head_scale=1, neck_mask=None, collar_blend=False, jaw_width=0,
               layers=[head[0], limbs['body'], *head[1:]],
               arm_segments=limbs['arm_segments'], hands=limbs['hands'], arms=limbs['arms'],
               extraction={**extraction, **limbs['extraction']})
    (OUT / 'rig-v4.json').write_text(json.dumps(rig, indent=2)+'\n')
    prompts = {}
    for prompt in sorted(SOURCE.glob('*-v4.prompt.txt')):
        image = prompt.with_name(prompt.name.replace('.prompt.txt', '.png'))
        if not image.is_file():
            raise ValueError(f'Missing generated source for {prompt.name}')
        prompts[image.name] = {'tool':'built-in imagegen', 'prompt':prompt.read_text(),
                              'source_sha256':hashlib.sha256(image.read_bytes()).hexdigest()}
    (SOURCE / 'prompts-v4.json').write_text(json.dumps(prompts, indent=2)+'\n')
    print('Built intact-head/segmented-arm model:', OUT / 'rig-v4.json')


if __name__ == '__main__':
    build()
