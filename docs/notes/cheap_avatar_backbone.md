# Cheap avatar backbones: replacing TaoMate-H3 with skeleton/rig control

Research note (not authoritative). Date: 2026-10-04. Question from the owner: find ways to
replace TaoMate-H3 with simpler models such as skeleton control, so the live agent can run at
super-cheap expenses. This note surveys options, grounds them in the actual `Generator`
contract, and states the cost, latency and research consequences. Nothing here has been
measured locally; every external claim is *cited* (with URL and access date), *estimate*, or
*unverified*. Per goal.md, the backbone may not be silently replaced: adopting any option here
needs a `docs/decision_log.md` entry.

## 1. What the replacement must satisfy (from the code, this repo)

The system already treats the generator as a swappable backend (three implementations:
`mock`, `taomate_h3`, vLLM-Omni WS). A cheap replacement "only" has to implement
`live_agent/generator/base.py`:

- `submit(request_index, prompt)` / `chunks()` / `reset()` / `timings`;
- emit `Chunk` objects: ~24 fps frames `np.uint8 [T,H,W,3]` in the 34/34/34/17 layout plus
  32 kHz float PCM, `n_frames/fps` = chunk duration (`live_agent/types.py`);
- `RequestTiming` fields become: `t_teacher_*` = TTS synthesis, `t_first_chunk` = first
  composited chunk. Λ (the lock lead time, `timeline.py`) collapses to TTS + compositing.

Everything downstream — JIT lock scheduler, orchestrator loops, browser transport (JPEG
frames + PCM per chunk), presentation acks, VLM judge on presented frames, MP4 recorder,
ASR speech check, E2 harness — is generator-agnostic and keeps working unchanged.
`MockGenerator` already renders placeholder frames with PIL, so server-side frame
compositing has precedent in-tree.

One component becomes **required** that TaoMate-H3 provided implicitly: the voice. Speech
currently comes out of the generator itself (joint audio-video). A skeleton/puppet stack
needs an external TTS (this was already classified as class-D-adjacent engineering in
A3/D-005 and is the A0 baseline design, D-004/D-009).

## 2. Option survey

### Tier 0 — rigged/puppet avatar + TTS (the "skeleton control" the owner named)

A rigged 2D or 3D character animated by bone/blendshape control: predefined animation
clips per capability action, audio-driven mouth. This is the VTuber stack, and it is the
only tier that is effectively free to run.

Rendering can live on either side:

- **Server-side sprite compositor** (cheapest, keeps the contract): pre-rendered body
  loops per action + a small mouth overlay set driven by audio energy/visemes, pasted
  together with numpy/PIL at 480p/24 fps inside the generator process. No GPU, no
  renderer dependency; extends the existing mock-rendering machinery. Visual ceiling: a
  2D cartoon puppet (PNGTuber-plus style). This is the smallest change to this repo.
- **Browser-side VRM render** (best quality per dollar): render the avatar in the existing
  frontend canvas with three.js. Costs nothing on the server; uses the viewer's GPU.
  Key building blocks, all *cited*:
  - `@pixiv/three-vrm` — MIT-licensed VRM loader for three.js; `expressionManager` applies
    the standardized VRM viseme presets (`aa/ih/ou/ee/oh`) and emotion expressions
    (github.com/pixiv/three-vrm, pixiv.github.io/three-vrm, accessed 2026-10-04).
  - `@pixiv/three-vrm-animation` (v3.5.5) — plays `.vrma` glTF-based humanoid animation
    clips on a VRM with retargeting; loader plugin + AnimationMixer (npmjs.com/package/
    @pixiv/three-vrm-animation, accessed 2026-10-04). Actions become VRMA clips: capability
    intent → clip id.
  - Cost: the transport changes direction — the server would send (clip id, viseme track,
    audio) instead of frames, and QC/recording evidence must be captured client-side
    (canvas capture / MediaRecorder). Presentation acks already exist. This is a larger
    refactor and changes the "QC evidence = painted frames" semantics, so it should be a
    deliberate protocol decision, not a quick swap.
- **Server-side 3D render** (headless Godot/Chrome + three-vrm): *not recommended*.
  Godot `--headless` renders nothing (logic only); real offscreen rendering needs a GPU
  surface (Xvfb/EGL/Vulkan). Headless-Chrome WebGL via SwiftShader measured ~3.2–3.5 fps in
  one community benchmark vs dramatically faster on a real GPU (PLN/Tidal GitLab data
  point, via web search 2026-10-04; single secondary source — treat as indicative).
  Software 3D rasterization is 10–50× below a modest GPU [estimate]. It reintroduces a
  rendering dependency for no cost win over the sprite path.

Proof the whole loop works cheaply, end to end: **Open-LLM-VTuber** (MIT) — self-hosted,
offline-capable AI VTuber with Live2D/VRM avatars, hands-free voice with an LLM, local or
online ASR/TTS, interruptible (github.com/t41372/Open-LLM-VTuber, open-llm-vtuber.github.io,
accessed 2026-10-04). It is the reference architecture for Tier 0.

**Animation asset licensing** (*cited*): Mixamo animations are royalty-free for commercial
use inside a project, no attribution, no standalone redistribution of raw assets (Adobe
Mixamo FAQ/Terms via web search 2026-10-04; re-verify on mixamo.com before product use).
Mixamo has no seated-lectern-with-props clips, so the teacher persona's prop actions
(drink, point at board, chalk) would be custom keyframed; props attach to hand bones.
2D-rig alternatives: **Live2D Cubism SDK** is free only under ¥10 M annual revenue
(threshold cited from the SDK terms via web search 2026-10-04); **Inochi2D** is BSD-2-Clause
with the open-source Inochi Creator authoring tool; **Iki** is a new MIT 2D web puppet
engine. For zero license risk, VRM (three-vrm MIT + a permissively licensed model) or
Inochi2D are the clean choices; the VRM model itself must be chosen/commissioned with its
own license in mind.

### Tier 0 voice (external TTS, mandatory component)

- **Piper** — CPU-only ONNX TTS; "real time or faster on a Raspberry Pi 4" for many
  voices (cited: rhasspy/piper docs via web search 2026-10-04); ships a pre-trained
  Mandarin voice `zh_CN-huayan-medium` (22.05 kHz) (cited: rhasspy.github.io/piper-samples,
  accessed 2026-10-04). Zero GPU, zero network. Quality: serviceable, slightly robotic
  [estimate; unverified by ear].
- **edge-tts** (PyPI) — free access to Microsoft Edge neural voices; excellent zh-CN
  voices (XiaoxiaoNeural, YunxiNeural, …), 74 languages/322 voices (cited: pypi.org/project/
  edge-tts and edge-tts.com, accessed 2026-10-04). Risks: undocumented reverse-engineered
  endpoint, occasional 403/rate limits, no SLA, cloud-dependent. Good dev/demo default;
  not a production dependency.
- **CosyVoice2** — Apache-2.0, streaming-first, ~150 ms first-packet latency (cited via
  web search 2026-10-04; re-check the repo before relying on the number). **GPT-SoVITS** —
  MIT code, ~5 s reference-audio voice cloning, strong Mandarin, offline-first.
  **IndexTTS-2/2.5** — streaming, runs on 8 GB+ VRAM consumer GPUs (cited via web search
  2026-10-04). Any of these gives the persona a consistent, cloneable voice on the
  *existing* helper GPU — no new hardware beyond what the responder LLM already uses.

### Tier 0 lip sync (audio → mouth)

- The mouth can be driven by the same PCM the viewer hears, so A/V sync is correct *by
  construction* (compare: D-044 measured the H3 model's lips leading by ~45 ms and needed a
  per-viewer offset; a puppet needs none).
- Simplest robust method: energy/formant buckets → 3–5 mouth sprites or VRM visemes;
  language-agnostic, implementable in numpy (server) or WebAudio (browser). No external
  dependency, no license risk. [implementation note]
- **Rhubarb Lip Sync** — offline CLI, phoneme → Preston-Blair visemes with timing output
  (JSON/TSV/SRT); primarily English, Mandarin accuracy and commercial terms *unverified*.
- **wawa-lipsync** — open-source JavaScript library doing real-time in-browser audio
  analysis → viseme weights, used with three.js stacks (existence cited via web search
  2026-10-04; repository and license *unverified* — check before adoption).

### Tier 1 — cheap neural talking head (one consumer GPU)

**LivePortrait**: ~12.8 ms/frame (~78 fps model inference) on an RTX 4090 (cited:
arxiv.org/abs/2407.03168v2, accessed 2026-10-04); FasterLivePortrait TensorRT port reaches
30+ fps on an RTX 3090 (community-cited). Models are tiny (≤ 55 M params). **Blocker: the
official code and weights are non-commercial use only** (cited from the repo license via
web search 2026-10-04), and it animates from a driving video/keypoints rather than audio,
so it needs a second lip-sync model on top. Most academic talking-head repos (Wav2Lip,
SadTalker, EchoMimic families) carry NC or research-only clauses or unverified terms —
each must be cleared individually before any product use. This tier is per-GPU ~2 orders
of magnitude cheaper than H3 but is still a GPU dependency with licensing friction;
recommend skipping unless photorealism is a hard requirement.

## 3. Cost and latency comparison

Numbers for the current stack are *measured locally* (README, `docs/implementation.md`,
D-021, D-041); numbers for the replacements are *cited* or *estimate* as marked.

| | TaoMate-H3 (full/omni) | Tier 0 server sprites | Tier 0 browser VRM | Tier 1 LivePortrait |
|---|---|---|---|---|
| Persona hardware | 6 (or 4) × H200-class [measured]; ~$15–25/hr at $2.5–4/GPU/hr [estimate, cloud listings vary] | 0 GPUs; ~1 CPU core [estimate] | 0 server GPUs (viewer's GPU renders) [by construction] | 1 consumer GPU [cited speed class] |
| Start-up | ~6 min (omni, 4×87 GiB) [measured]; 1228 s (USP2) [measured, D-041] | < 5 s [estimate] | < 5 s [estimate] | ~10 s [estimate] |
| Instruction → first audio | 2.2–3.6 s [measured, server check] | responder + TTS first chunk: Piper ≲0.3 s, CosyVoice2 ≈0.15 s [cited], edge-tts ≈0.3–0.8 s [estimate] → overall ≈1–3 s [estimate] | same as server sprites [estimate] | similar + render [estimate] |
| Action visible (TVC) | verdict 7.7–8.2 s after instruction [measured]; repair lands ~2 requests later [measured] | next frame after lock (~40 ms) — deterministic clip [by construction] | same [by construction] | depends on driving pipeline [estimate] |
| Lip sync | model-internal; measured lips lead ~45 ms, needs per-viewer offset (D-044) [measured] | by construction (mouth driven by played PCM) | by construction | needs separate lip model |
| Novel actions / scenes | open-ended within prompt limits | bounded by the clip library; anything else degrades/refuses (manifest already models this) | same | bounded by driving video |
| Look | photoreal persona | 2D puppet (server) / full 3D VTuber (browser) | full 3D VTuber | photoreal-ish from one photo |

## 4. Research consequences (must be recorded, not slipped in)

1. **This is the A0 baseline becoming a deployment path.** D-004/D-009 already define A0 =
   LLM + TTS + talking-head avatar sharing the responder, memory and evaluation substrate
   with A1/A2. A skeleton-controlled teacher is A0 with rig control instead of a neural
   talking head. That is a feature for E2: A0-skeleton vs A2-H3 on the same
   director/memory/eval stack measures exactly what the expensive generator buys
   (RQ4 in both directions).
2. **Action compliance becomes true by construction.** With deterministic clips, the VLM
   action judge and forward repair are redundant on this path (the clip either played or
   the request was dropped — both already logged). The closed-loop claim (A2) remains
   meaningful only where the generator is unreliable, i.e. on H3. Keep the judge runnable
   as monitoring so logs stay comparable across arms.
3. **The prompt compiler and canon machinery are H3-specific.** A puppet generator maps
   `BlockScript.action` (intent) → clip id and `transcript` → TTS; canon, `<d>` formatting,
   soundscape and scene guards are not consumed. BlockScript stays the internal IR.
4. **Erasure/reset/barge-in get cheaper**: no KV state to purge (reset = drop the queue);
   barge-in can switch on the next frame instead of freezing 2.6–3.5 s [measured for H3].

## 5. Recommended path (if the owner adopts this)

1. **`live_agent/generator/puppet.py`** (server-side sprite compositor, Tier 0):
   config maps capability intents → body-loop clips; TTS client (Piper for CPU-only,
   edge-tts for quality dev, CosyVoice2 on the helper GPU for production-quality Mandarin);
   energy-based mouth overlay; emits the standard `Chunk` stream. Register as
   `--generator puppet` next to `mock`/`taomate_h3`. No other component changes.
2. Optional phase 2: browser-side VRM render (three-vrm + VRMA + wawa-lipsync/energy
   visemes) for a full 3D look — but treat it as a protocol change (client-side QC
   evidence and recording), decided in the decision log first.
3. Before product use, clear: VRM model / sprite asset license, wawa-lipsync license,
   Rhubarb terms (if used), edge-tts acceptability (unofficial endpoint), Mixamo terms
   re-read on mixamo.com. All currently *unverified* except where cited.
4. Decision-log entry (owner approval) covering: which tier, the A0 promotion framing, and
   the judge/repair disposition on the puppet path.

## 6. Open questions

- Mandarin lip-sync quality of Rhubarb / wawa-lipsync on TTS audio (needs a measured check
  once a TTS is chosen; the energy fallback is the floor).
- Piper huayan voice acceptability for a teacher persona (subjective; needs an owner listen).
- Whether the browser-render variant's client-side evidence (canvas captures) satisfies
  the E2 adjudication protocol without weakening it — design review needed.
- VRM/asset sourcing: permissively licensed teacher avatar with lectern props, or
  commissioned sprites; cost not surveyed here.
