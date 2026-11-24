#!/usr/bin/env python3
"""Build the arm-proportion revision while preserving the registered v4 face.

Placement and anatomical targets are authored configuration. Generated source
art, exact prompts and measured extraction coordinates are saved separately.
Historical manifests and runtime tiles are never overwritten by this builder.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/assets/teacher-mesh'
SOURCE = OUT / 'source'


def build():
    from build_teacher_mesh_v5_limbs import build_limbs
    limbs = build_limbs()
    parent = OUT / 'rig-v4.json'
    rig = json.loads(parent.read_text())
    rig.update(
        asset_revision=5,
        description='Custom adult anime teacher with a registered intact head, tapered tailored sleeves and consistently scaled hands; not Live2D/Cubism.',
        arm_segments=limbs['arm_segments'], hands=limbs['hands'], arms=limbs['arms'],
        extraction={**rig['extraction'], **limbs['extraction']},
        artwork_parent={'asset_revision':4,
                        'manifest_sha256':hashlib.sha256(parent.read_bytes()).hexdigest(),
                        'retained_head_assets':[layer['asset'] for layer in rig['layers']
                                                if layer['group']=='head']},
    )
    if 'body' in limbs:
        rig['layers'] = [limbs['body'] if layer['id'] == 'body' else layer
                         for layer in rig['layers']]
    (OUT / 'rig-v5.json').write_text(json.dumps(rig, indent=2)+'\n')
    prompts = {}
    for prompt in sorted(SOURCE.glob('*v5*.prompt.txt')):
        source = prompt.with_name(prompt.name.replace('.prompt.txt', '.png'))
        if not source.is_file():
            raise ValueError(f'Missing generated source for {prompt.name}')
        prompts[source.name] = {'tool':'built-in imagegen', 'prompt':prompt.read_text(),
                               'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    (SOURCE / 'prompts-v5.json').write_text(json.dumps(prompts, indent=2)+'\n')
    print('Built proportional-arm model:', OUT / 'rig-v5.json')


if __name__ == '__main__':
    build()
