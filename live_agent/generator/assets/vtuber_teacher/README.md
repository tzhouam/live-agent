# Natural VTuber teacher artwork

Original adult teacher artwork authored with the built-in imagegen tool. These are
2D sprite assets with a softly realistic 3D anime visual style, not an actual VRM,
Live2D or 3D model. They replace the D-049 appearance rejected by the owner.

- `atlas-v2.png`: continuous head/neck/torso bust expressions and isolated hands;
  repairs exposed shoulder-edge skin slivers with matching fabric. Its original
  sleeve tiles are retained as historical source art.
- `sleeve-atlas-v3.png`: replacement upper-arm/forearm sprites authored with built-in
  imagegen for the D-052 proportions correction. Only its lower sleeve tiles are
  consumed; the existing face, hands, classroom and props retain their sources.
- `atlas.png`: preserved initial atlas before the shoulder repair.
- `classroom.png`: matching quiet classroom with soft window light and an empty desk.
- `props.png`: props reused from `../anime_teacher/props.png`; authoring provenance
  and the original prompts are recorded in `prompts.json`.
- `prompts.json` and `repair-prompt.txt`: exact built-in imagegen authoring and repair
  prompts. `proportions-prompt.txt` records the exact sleeve edit and its source/output
  provenance. `rig.json` records active filenames, crop/attachment coordinates and
  desk depth in the portrait coordinate system (configuration: 480 × 864).

The renderer uses adult head/shoulder proportions, a continuous collar attachment,
restrained shared bust/joint movement, feathered facial patches, an audio-driven
deformable mouth aperture and independent smiles/blinks. Tabletop and front-lip
occlusion and prop/hand contact shadows blend the character into the scene; staged
arm lifts keep hands on camera through gesture transitions. Runtime uses these local
assets with the existing CPU puppet RGB/PCM streaming contract; no image service,
MiniMax or GPU renderer is needed.

Historical D-050 pose, transition, facial and animated previews are in
`.cache/puppet-refinement/natural-*`. A render-only sample measured 240 frames at
480 × 864 in 3.278549 s, or 73.2 fps [measured locally; excludes TTS, encoding and
transport]; see `natural-measurement.json`. Generator/backend regression verification
passed 44 tests [measured locally], including smile/blink independence, gesture
transition bounds and Edge worker responsiveness. A short fresh-service HTTPS
Chromium check received 16 video chunks, reported the Mandarin wave reply's speech
onset as heard, and recorded zero WebSocket/page/server session errors [measured
locally]; evidence is `service-natural-check.json` and `service-natural-*.png` in the
preview directory. These checks do not establish sustained latency, physical-device
audio/video sync, user acceptance or learning efficacy.

D-052 corrects the body/arm proportions after the owner's visual feedback. The bust
sits higher relative to the tabletop, revealing the torso down to the waist; the
longer arm chains reach the desk through a continuous elbow and cuff. Each sleeve's
authored joint axis is fitted with a uniform scale and rotation, preserving its
fabric proportions. A rounded cap from the authored fabric blends the elbow join.
Upper arms that move inward across the chest render over the torso, behind the
tabletop and forearms, keeping the moving arm connected through the bend.
Animation controls are recalculated for the changed shoulder and limb geometry.
Coordinates in `rig.json` are configuration targets, not anatomical measurements.

The preliminary before/after views are `.cache/puppet-proportions/before.png` and
`repaired-joints.png`. The final generator module passed 21 tests [measured locally],
including complete transformed sprite/held-prop bounds across 6,171 sampled poses
(17 animations × 121 times × 3 phases [measured locally]) and mug, book and globe
contact checks. The sweep caught transition clipping that joint-only checks missed.
The final pose montage and wave/drink/presentation transition sheets were inspected
locally; review is saved in `.cache/puppet-proportions/artwork-review.json`. Staged
browser verification passed 14 board-on/off layouts across 7 viewports, with 12 H.264
chunks and no overflow or page/console/request errors [measured locally]; evidence
is `browser-staging/report.json` in the same directory. Desktop, tablet and phone
screenshots received an independent qualitative visual check with no blocking
defects. Final private HTTPS verification received 12 real video chunks across
desktop/tablet/phone layouts, displayed an actual wave and reported no stretching,
overflow, page or protocol errors [measured through private HTTPS]. Its final native
teacher/wave and classroom screenshots were inspected; evidence is `live/report.json`
and `live/*.png` in the same directory. The service loaded the final artwork under
its supervisor, retaining the adopted bridge; `service-refresh.json` records that
refresh. This correction does not establish the owner's aesthetic approval or
change the sprite renderer into a 3D avatar rig.
