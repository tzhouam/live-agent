# Custom browser teacher — teacher-mesh-v1

This is a custom PixiJS mesh avatar, **not a Live2D/Cubism model**. It preserves the
adult teacher's brown low ponytail, silver glasses, navy jacket and sage bow while
adding authored hair, eye, fabric and accessory detail. PixiJS **8.22.0** [pinned
dependency version] is served locally from `../../vendor/pixi/`, with its MIT
license and download provenance alongside the module.

`source/` preserves the original four generated source images [measured asset
count] and their exact built-in imagegen prompts in `prompts-v1.json`. The active
earlier artwork refinement adds `reference-v2.png`, `body-atlas-v2.png`,
`face-atlas-v2.png` and exact prompts in `prompts-v2.json`; the authored pointing
and waving hand source remains `hands-atlas-v1.png`. All revisions are retained.
The earlier adult-proportion repair adds `body-atlas-v3.png`, `face-atlas-v3.png`
and `arms-atlas-v3.png`, with exact built-in imagegen prompts in
`source/prompts-v3.json` and individual prompt text files. The separate sleeve
atlas replaces the rejected bulky, pre-bent sleeves in the first new assembly.

The current frontend loads `rig-v7.json`, with `asset_revision: 7` [asset revision].
Wire model
identity remains `teacher-mesh-v1` and manifest `version: 1` [format version], so
asset refinement does not change session negotiation. Run
`python3 scripts/build_teacher_mesh_assets.py` from the repository root to
rebuild the current revision; `--revision 1` through `--revision 6` explicitly rebuild earlier
assets instead. The script records crop/trim provenance in the matching manifest
and copies the existing authored classroom. It does not repaint source images.
Rebuild only intentionally and inspect the assembled result and animation.

The inherited v4 head uses one intact painting: hair, eyes, nose and glasses keep their
shared source coordinates instead of independently fitted feature tiles. Registered
half/closed eyelids and soft/A/O mouth patches use the same source scale and common
head transform. Opaque state selection prevents ghost irises/lips. Exact prompts,
source hashes and rejected intermediate artwork are preserved in `source/prompts-v4.json`.
`scripts/build_teacher_mesh_v4.py` registers expression edits against unchanged artwork;
`scripts/build_teacher_mesh_v4_limbs.py` crops the torso, sleeve sections and distinct
left/right hand poses. Extraction, source anchors, native scales and overlap masks
are retained in the manifest. Uniform rigid upper/forearm transforms avoid the old
inverted elbow mesh. Painted elbow cloth closes their overlap, and upper arms stay
above the torso when crossing it. Geometry and motion limits are artist configuration,
not anatomical measurements.

V5 preserves every registered head-layer specification and expression setting. It
replaces the sleeve artwork with fitted caps, a gradual forearm taper and rounded
painted joint-overlap extraction. Configured upper/forearm reach and wrist paths are
checked in both resting and raised poses. Palm/wrist landmarks normalize hand scale;
new cupped open palms retain naturally shorter curled fingers. The wave attaches at
its painted wrist crease. `scripts/build_teacher_mesh_v5.py` and
`scripts/build_teacher_mesh_v5_limbs.py` record the parent manifest, source anchors,
uniform scales and alpha masks. Exact prompts and source hashes, including rejected
intermediate artwork, are in `source/prompts-v5.json`. A seated reference's foreshortening
is not treated as anatomical ground truth for all gestures.

V6 follows the owner's explicit clarification that arms remained too short and hands
too small. `scripts/build_teacher_mesh_v6.py` and `scripts/build_teacher_mesh_v6_limbs.py`
reuse the unchanged painted assets, increasing actual shoulder-to-wrist reach and
calibrated palm/finger sizes. The head and torso keep their original sizes and move
up together; resting elbows/wrists and wrist flex leave space for larger hands on
the desk. The manifest records all layout targets, source scales, parent hash and
reused limb hashes. No new raster artwork, provider or dependency is introduced.

V7 addresses the owner's additional correction that the chest is too wide. Built-in
imagegen repaints only the armless torso with a narrower ribcage and more modest,
straighter blouse drape. `source/torso-modest-v7.png` and `source/prompts-v7.json`
preserve the generated original and exact edit prompt. `scripts/build_teacher_mesh_v7.py`
cleans disconnected alpha fragments and uniformly registers `body-v7.png`; the neck,
collar and shoulder underlaps retain their existing placement. All v6 face, sleeve,
hand, joint and gesture configurations remain unchanged. This is a garment-artwork
correction rather than horizontal compression of the character.

Wave, thinking and raised-index gestures follow connected wrist paths, with a fixed
elbow branch and later opaque hand changes. Short requests reduce lift amplitude;
`min_duration:3.5` seconds [configuration] gives the full authored lift. The head has
restrained tilts/translation and breathing, with audio-clock-driven mouth states.
Independent gaze, hair settling and a distinct smile are not implemented by this
intact-head refinement; smile uses its warm neutral face. The supported gesture IDs are idle,
listening, explaining, presenting, pointing with a finger, smiling, thinking,
nodding, head shaking and waving. Other requested actions follow the existing
capability degradation/refusal path.

Enable locally with `?avatar=mesh`. A successful model load negotiates the mesh
renderer; missing assets, unsupported WebGL or a renderer failure retains the
server-video fallback. The displayed WebGL canvas is separate from the fallback
video canvas. Mesh QC uses bounded timestamped captures of that actual canvas;
missing captures produce UNKNOWN and never substitute server puppet frames.
Teacher captures are separate from the student's opt-in camera analysis. Server
recordings are identified as fallback video; the local check also records the
actual browser avatar and scheduled audio.

For an isolated local preview, run `python3 scripts/teacher_mesh_check.py --serve`
from the repository root and open its printed loopback URL. To produce diagnostic
screenshots, protocol logs and an avatar recording, omit `--serve`. Existing
recorded Mandarin is reused when available; `--speech-wav` selects a PCM16 WAV,
and absence of a speech recording uses clearly labeled synthetic tones. The
fixture does not call teaching providers or read/write saved learner profiles.
Evidence is written under `.cache/teacher-mesh/`. Use `--model` with a local
manifest inside `frontend/public` to stage another artwork revision. The fixture
overlays its own manifest response without changing the classroom defaults;
reports bind the selected source, served manifest and actual loaded rig.

The initial artwork revision's successful browser check is
`.cache/teacher-mesh/acceptance-final/report.json`, with matching runtime/source
hashes, actual canvas captures and `browser-avatar.mp4`. Those measurements
remain historical evidence for that revision. Earlier failed checks are retained.

The earlier refinement used adult almond-shaped eyes, a softer jaw, raised
mouth/neckline placement, larger hands and closer framing. Continuous face/neck
skin extends beneath the transparent clothing collar, with no collar alpha blend.
The wave now rises to shoulder level and thinking has a distinct pose. A separate
visual review accepted the `polish-second` stills with minor slender-finger and
slightly sleepy-eye observations. Subsequent motion review repaired overlapping
hand silhouettes: authored shapes switch during the first/last 0.16 seconds of
the request [configuration bound] with wrist axes/rotation registered. Reviewers
accepted the final face/torso assembly and repaired waving/thinking motion.

Earlier refinement browser acceptance passed with stable runtime/source hashes in
`.cache/teacher-mesh/polish-final/report.json`, including speech-clock continuity,
actual-canvas evidence, interruption/reconnect, fallback and responsive layouts
[measured locally]. Actual spoken-animation and controlled silent gesture
recordings are in that directory. Final frontend verification passed 136 tests
[measured locally; `.cache/teacher-mesh/frontend-polish-final-tests.log`]. A brief
hand-shape switch, slender fingers and subtle collar appearance remain minor
visual limitations.

Supplemental delivery artifacts are the [spoken preview](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-delivery/spoken-preview.mp4)
and its [capture/audio-coverage report](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-delivery/report.json).
This recording starts before the first scheduled audio source. Waveform
correlation covers all non-silent source content, excluding trailing source
silence; it does not establish human voice naturalness, audibility or lossless
complete-audio capture. The original `polish-final` acceptance measurements above
remain unchanged. Comparable native canvas views are [earlier artwork](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-final/before-v1.png)
and [refined artwork](/data/zhoutaichang/live-agent/.cache/teacher-mesh/polish-final/after-v2.png).
The [final quality audit](/data/zhoutaichang/live-agent/.cache/teacher-mesh/quality-audit-polish.json)
binds local-preview acceptance, source/runtime hashes, reviewed artifacts and
remaining limits.

The historical adult-proportion refinement passed actual-browser speech, complete
wave/thinking motion, interruption, stale-capture rejection, fallback and device
layouts in `.cache/teacher-mesh/adult-v3-final/report.json`. Independent visual
review accepted the assembled adult silhouette and sampled complete motions.
Actual alpha/skin-mask tests also sweep full hand silhouettes, painted shoulder/
wrist overlap and gesture continuity. The head/shoulder balance is an art-direction
target, not a cited anthropometric standard. Matched native views and the spoken
recording are saved in that directory; the final quality audit binds serving and
validation evidence. Pointed jacket shoulders and brief translucent fingers at
the hand-shape crossfade were recorded as minor limits. The owner's subsequent
rejection exposed larger facial landmark and arm-folding defects; those earlier
bounded geometry checks did not establish visual quality. V4 replaces that assembly.

Historical v4 review and validation are recorded in `docs/implementation.md` (D-064).
Two initial integrated v4 assemblies were also rejected and retained as evidence;
the accepted third assembly and actual spoken canvas were inspected before serving.
Hand/facial state changes remain discrete, without continuous finger articulation
or phoneme matching. The raised index is lecture emphasis, without board-coordinate
targeting. These limits are not inferred successes from viewport-bound tests.

The owner's later arm-ratio rejection prompted the v5 reassessment (D-065). Native
motion review rejected the first v5 elbow/open-palm assembly and the initial short
forearm before accepting the retuned assembly and actual spoken canvas. Current
checks measure painted sleeve widths, palm/wrist scale, complete gesture silhouettes
and clearance above the desk lip, while preserving the v4 face exactly. The actual
HTTPS before/after captures are in `.cache/teacher-mesh/arm-ratio-v5-before/` and
`arm-ratio-v5-after/`; historical default media acceptance and the spoken recording are in
`arm-ratio-v5-delivery-final/`. See the implementation notes for measured results and
their scope. Painted folds rotate with the rigid segments, and hand states still
change between authored poses; no continuous finger or three-dimensional cloth rig
is claimed.

Current v6 motion/spoken reviews are in `.cache/teacher-mesh/arm-hands-v6-first/` and
`arm-hands-v6-staged-full/`. Final default media validation/recording is in
`arm-hands-v6-delivery-final/`; actual HTTPS comparison uses the unchanged served
v5 baseline in `arm-ratio-v5-after/` and matched v6 states in `arm-hands-v6-after/`.

Current v7 torso artwork/motion and spoken reviews are in
`.cache/teacher-mesh/torso-v7-audit/`. Full media validation and actual spoken canvas
recording are in `torso-v7-staged-full/`; actual HTTPS captures and comparisons use
the unchanged v6 baseline in `arm-hands-v6-after/` and current `torso-v7-after/`.
The staged renderer, rig and texture bytes remain unchanged after switching the
manifest default; that narrow URL change is recorded separately in the audit.
See D-066 in the implementation notes for measurements and preserved limitations.

This rig provides limited front-facing deformation and approximate acoustic
mouth shapes. Headless-render timings do not guarantee device-display performance.
No professional Live2D equivalence, human realism or teaching-efficacy result is
claimed. The isolated local classroom now serves this artwork through its
owner-authorized Personal-Agent bridge; the original classroom remains separate.
