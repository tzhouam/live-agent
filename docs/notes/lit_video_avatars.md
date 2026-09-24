# Literature review: real-time video generation, interactive world models, controllable generation, streaming avatars, joint audio-video

*Research note (supporting material, not authoritative). Compiled 2026-09-25.*
*Scope: areas (a) to (e) of the live-agent proposal. The LingBot-World 2.0 / vLLM-Omni backbone is covered in depth in
[`backbone_lingbot_world_vllm_omni.md`](backbone_lingbot_world_vllm_omni.md). MiniMax H3 as a reference agent is covered in
[`reference_agent_and_minimax_h3.md`](reference_agent_and_minimax_h3.md).*
*BibTeX: [`bib_video_avatars.bib`](bib_video_avatars.bib). Keys are given in brackets like `[yin2024causvid]`.*

**How to read the numbers.** Every speed, latency or hardware figure below is **cited**: copied from the paper abstract, paper body,
official README or vendor page named next to it. None was measured locally. Our hardware (8x L20X, see `docs/PROJECT.md` A1) is
different from the H100/H800/H200 setups most papers report, so no figure transfers directly. "Vendor claim" marks figures from
product pages or blogs that have no paper, code or independent benchmark behind them. "Unverified" marks items I could not confirm from a
primary source.

**Verification method.** All 103 arXiv IDs cited here were resolved through the arXiv export API (title, authors, v1 date) on
2026-09-25. Licenses were read from the GitHub license API or Hugging Face model-card metadata the same day. Performance details not in
the abstracts come from the arXiv HTML full text, where stated.

---

## 1. Synthesis

### 1.1 What is effectively solved (as of Sep 2026)

1. **Turning a bidirectional video DiT into a real-time causal streamer is now a standard recipe.** The recipe:
   (i) start from a bidirectional DiT, usually from the Wan2.1/2.2 family;
   (ii) initialize a causal (block- or frame-autoregressive) student, first via ODE-trajectory distillation (CausVid
   `[yin2024causvid]`), later via a causal teacher (Causal Forcing `[zhu2026causalforcing]`) or causal consistency distillation
   (Causal Forcing++ `[zhao2026causalforcingpp]`);
   (iii) close the train/test gap by training on the model's own rollouts with a distribution-matching (DMD) or adversarial loss
   (Self Forcing `[huang2025selfforcing]`, APT2/AAPT `[lin2025aapt]`, Self-Forcing++ `[cui2025selfforcingpp]`);
   (iv) run inference with a rolling KV cache plus an *attention sink* (LongLive `[yang2025longlive]`, Rolling Forcing `[liu2025rollingforcing]`).
   Several full-stack open recipes exist: minWM `[zhao2026minwm]`, SolarWM `[huang2026solarwm]`, AlayaWorld `[alayaworld2026alayaworld]`.
   *Cited envelope:* a 1.3B model at 480p reaches about 16 to 21 FPS on one H100, with about 0.8 s to the first chunk (Self Forcing, LongLive).
   An 8B model reaches 24 FPS at 736x416 on one H100 (AAPT). At 14B, real time needs multi-GPU pipelines. Helios `[yuan2026helios]`
   claims 14B at 19.5 FPS on one H100, but its code is not yet released.
2. **Minute- to hour-scale stability without collapse** is claimed by many systems. Examples: Self-Forcing++ (4 min 15 s), LongLive
   (240 s), LiveAvatar (>10,000 s), Visko Orbis (hour scale), LingBot-World 2.0 ("unbounded"). Most claims are demonstrated on
   curated prompts. Independent benchmarks disagree: WorldRoamBench `[xu2026worldroambench]` (10+ models) and WBench `[ying2026wbench]`
   (20 models) both report that *no* model is strong on action following, visual stability, physics and memory at the same time.
3. **Audio-driven talking avatars at real-time rates.** Lip-synced talking-head and upper-body streaming now runs at 25 to 45 FPS
   using multi-GPU 14B models:
   LiveAvatar `[huang2025liveavatar]` (45 FPS, TTFF 1.21 s, 5xH800);
   SoulX-FlashTalk `[shen2025soulxflashtalk]` (32 FPS, 0.87 s start-up, 8xH800);
   TalkingMachines `[low2025talkingmachines]` (18B, 512x512, 2 NFE, 1 to 2 H100 plus a VAE GPU).
   Small models run on a single consumer GPU:
   SoulX-FlashHead Lite (96 FPS, RTX 4090) `[yu2026soulxflashhead]`;
   AvatarForcing (34 ms/frame, 1.3B) `[cui2026avatarforcing]`;
   Ditto `[li2024ditto]`;
   LivePortrait (12.8 ms/frame, RTX 4090) `[guo2024liveportrait]`.
4. **Offline joint audio-video generation is solved at product quality.** Closed systems: Veo 3/3.1, Sora 2, Seedance 2.0, Wan 2.6.
   Open weights: LTX-2 `[hacohen2026ltx2]`, Ovi `[low2025ovi]`, MOVA `[openmoss2026mova]`, MiniMax H3 (about 33B tensor elements on
   Hugging Face), DreamX-Creator `[zhu2026dreamxcreator]`. All produce clips of at most about 15 to 20 s. None stream.

### 1.2 What remains unresolved (candidate research gaps)

| Gap | Evidence | Why it matters for a live agent |
|---|---|---|
| **G1. Instruction-to-visual latency is not measured.** | Papers report throughput (FPS) and time-to-first-frame. None of those reviewed reports how long it takes for a *mid-stream* text instruction ("wave", "it starts raining") to become visible and compliant. LongLive shows the trade-off qualitatively: keeping the whole KV cache "adapts to new prompts after a delay", and discarding it causes abrupt jumps. Echo-Forcing `[wu2026echoforcing]` names "delayed response to new prompts" as a failure mode but measures VBench scores. The lower bound is set by the chunk size (e.g. 3 latent frames ≈ 12 video frames ≈ 0.5 s at 24 FPS for Wan-VAE-based chunk AR; *estimate*) plus how long the cache keeps pulling toward the old prompt. | The core UX metric of a "live" persona. It is also a clean, defensible measurement contribution. |
| **G2. Character-level control inside world models is nascent.** | Most real-time world models control **camera or ego-motion only**: Matrix-Game 2.0/3.0, WorldPlay, GameCraft, Voyager, SolarWM. Matrix-Game 2.0 *removes* text input. Character or NPC control is emerging: LingBot-World 2.0 adds combat actions and text-driven events. AlayaWorld has combat and spell casting. HelloWorld `[ouyang2026helloworld]` has button-triggered wave/nod/greet toward the camera (not real-time). ReactiveGWM `[wang2026reactivegwm]` steers NPC strategy (Street Fighter only). WanToFight `[hu2026wantofight]` covers two-player combat. CustomX `[wang2025customx]` directs a character in natural language (not real-time). EchoWM `[zhang2026echowm]` learns third-person camera-character dynamics with audio. **None combines lip-synced speech and facial expression with scene-level world control.** | Our persona must speak, gesture and act *inside* a scene it can change. Today that requires two disjoint model families: avatar models for the face and world models for the scene. |
| **G3. The persona's long-horizon identity under large motion and scene change is untested.** | Avatar models keep identity with reference sinks and identity tokens (StreamAvatar Reference Sink + RAPR; X-Streamer global identity reference; LPM multi-granularity references). They do so mostly in static framing. World models measure *scene* memory (FOV retrieval, patch memory) and seldom subject identity. Matrix-Game 3.5 `[qian2026matrixgame35]` is the first to name a "static-dynamic disentangled" representation for subject identity. Vidu S2 reports degradation beyond 90 s with dance motion. | A persona that walks, turns and changes outfit must stay recognisable for hours. |
| **G4. The LLM's episodic memory is not linked to the visual state.** | Conversational memory lives in the LLM context (e.g. X-Streamer's Thinker: 8K tokens ≈ 10 min). Visual memory lives in KV caches or frame banks (WorldMem `[xiao2025worldmem]`, Context-as-Memory `[yu2025contextasmemory]`, WorldPlay, RAD `[chen2025rad]`, SSM world models `[po2025ssmworldmodel]`). No system writes "what the persona looked like, wore, held, or where it was" into long-term memory and re-injects it across sessions. The closest mechanism is Vidu S2's dynamic reference update `[zhang2026vidus2]`. | "Remember the red scarf I gave you yesterday" needs cross-session visual grounding. |
| **G5. End-to-end systems trade resolution for latency.** | Fully unified duplex models run at low resolution: X-Streamer at 256x256 on 2xA100; Wan-Streamer at 192p with about 200 ms model-side latency; MIDAS at 384x640. High-fidelity systems are cascaded (LLM, then TTS, then audio-driven video) and pay start-up latency of about 0.9 to 1.3 s. | We need a design point between these. For a research demo, a cascade plus a streaming video backbone is the realistic choice. |
| **G6. Streaming joint audio-video is only emerging.** | Hallo-Live `[li2026hallolive]` (distilled from Ovi; 20.38 FPS, 0.94 s, 2xH200). Starchild-1 (vendor claim). EchoWM (world plus audio; no speed figure). Wan-Streamer (192p). | Needed if speech and non-speech sound (laughing, footsteps, ambience) should come from the same model as the visuals. |
| **G7. Evaluation.** | There is no benchmark for *live agents* covering lip sync, instruction-compliance latency, identity drift over hours, cross-session memory recall and interruption handling together. The pieces exist: LPM-Bench (conversational performance), GenBench (LiveAvatar), HelloWorldBench (social actions), WBench and WorldRoamBench (world models). | A benchmark or protocol is itself a publishable contribution. |

### 1.3 What is reusable for our project

- **Backbone family alignment.** Wan `[teamwan2025wan]` is the shared base. LingBot-World 2.0 ships Wan-style checkpoints (its README's task name is `i2v-A14B`). Wan is also the
  base of most open avatar models: TalkingMachines (Wan2.1 I2V), MultiTalk and InfiniteTalk (Wan2.1), SoulX-FlashTalk (InfiniteTalk/Wan
  plus the Self-Forcing codebase), LiveAvatar (Wan2.2-S2V-14B), Wan-S2V, Wan-Animate. Audio-injection modules (L-RoPE audio binding in
  MultiTalk, LoRA audio injection in OmniAvatar, S2V audio blocks) are therefore *candidates* for porting onto a LingBot-World
  checkpoint. Porting feasibility is **unverified**. It depends on whether LingBot 2.0 kept the Wan block layout (see the backbone note).
- **Streaming and serving tricks with released code:**
  rolling KV cache plus attention sink (LongLive, Rolling Forcing; Apache-2.0 and Tencent license respectively);
  KV-recache on prompt switch (LongLive);
  training-free hierarchical memory with scene recall and difference-aware decay (Echo-Forcing);
  Timestep-forcing Pipeline Parallelism, one GPU per denoising step (LiveAvatar, Apache-2.0);
  DiT/VAE disaggregation on separate GPUs (TalkingMachines; also the "8+1 GPU" layout of Matrix-Game 3.0);
  camera-aware memory retrieval (Context-as-Memory, WorldPlay, Matrix-Game 3.x).
- **Instruction-to-behavior planners:** MLLM "director" blueprints (Kling-Avatar `[ding2025klingavatar]`, OmniHuman-1.5 `[jiang2025omnihuman15]`);
  "Visual Thought Plan" (Ex-Omni-2D `[zhang2026exomni2d]`);
  LLM tool calls injecting semantic motion control into a streaming animator (EchoAvatar `[chen2026echoavatar]`, 3D);
  pilot/director agent harness (LingBot-World 2.0);
  time-localized prompt attention masks for button-triggered actions (HelloWorld). The last is training-free and could localize a
  gesture instruction to a chunk window.
- **Data:** Sekai2 `[he2026sekai2]` (2,826 h with camera trajectories and revisits), SolarWM-Data (1.43M clips), MIDAS's 20k-hour
  dialogue set (not released), VividHead (782 h, FlashHead).

### 1.4 Where a defensible contribution may exist

1. **A character-centric live world model.** Condition a real-time world backbone such as LingBot-World 2.0 on (a) the persona's
   speech audio for lip sync and co-speech gesture, and (b) LLM-emitted discrete behavior tokens or text events that are
   time-localized to chunk windows. Keep camera/scene control. Differentiation: G2 says no published system unifies avatar-grade
   facial performance with world-model scene control. HelloWorld, ReactiveGWM and LingBot-2.0's action set are the nearest
   neighbours. Each covers one slice.
2. **Measure and reduce instruction-to-visual latency (G1).** Define "time-to-visible-compliance" (TVC): the time from instruction
   arrival until a VLM judge or an action classifier detects compliance. Report it next to FPS and TTFF. Then propose mechanisms and
   compare them against LongLive KV-recache and Echo-Forcing decay: partial cache re-encoding, prompt-conditioned sink tokens,
   frame-wise 1 to 2 step AR (Causal Forcing++ reports 50% lower first-frame latency than chunk-wise 4-step), or speculative
   pre-rendering of likely next behaviors. Cheap to run, easy to reproduce, and fills a clear gap.
3. **Episodic visual memory tied to agent memory (G3+G4).** Store persona and scene state snapshots (reference frames, identity
   embeddings, prop and outfit descriptors) as first-class memory items keyed by dialogue events. Re-inject them as dynamic references
   (Vidu-S2-style) or as KV "scene recall frames" (Echo-Forcing-style) when the LLM retrieves the event. Evaluate cross-session recall
   and identity drift over at least 1 h. This connects our memory workstream (`bib_memory_eval.bib`) to the video workstream.
4. **Live-agent benchmark/protocol (G7).** Combine LPM-Bench-style conversational metrics, WBench-style multi-turn interaction turns,
   TVC (item 2) and hour-scale identity drift (ArcFace similarity over time).

Risks to state honestly: our hardware is L20X, not H100/H800, so every cited real-time figure must be re-measured. LingBot-World 2.0
weights are **CC BY-NC-SA 4.0** (non-commercial, share-alike), which is acceptable for research but limits any product path. Tencent
Hunyuan licenses (HY-WorldPlay, GameCraft, Voyager, HunyuanVideo-Avatar) exclude the EU, UK and South Korea.

---

## 2. Comparison matrix

Legend. **Mid-stream text**: can a text prompt or event be changed during a running stream (Y = demonstrated in the paper or official
page; N = not supported or not shown; ? = unclear). **Ctrl**: C = camera/ego-motion, A = character actions, K = keyboard/mouse,
Au = audio, P = pose/skeleton, T = text. Speed is **cited** from the named source.

### 2.1 Streaming / autoregressive video generation (area a)

| System | Date (v1) | Base / size | Mid-stream text | Memory / consistency | Speed & HW (cited) | Open / license | Relevance |
|---|---|---|---|---|---|---|---|
| Diffusion Forcing `[chen2024diffusionforcing]` | 2024-07 | research scale | n/a | per-token noise levels; rollout past training horizon | n/a | code | foundational (per-frame noise) |
| StreamingT2V `[henschel2024streamingt2v]` | 2024-03 | SVD-era | N | CAM short-term + appearance-preservation long-term | offline | code | early AR long video |
| CausVid `[yin2024causvid]` | 2024-12 | causal DiT, 4-step DMD | Y ("dynamic prompting", zero-shot) | KV cache | 9.4 FPS, 1 GPU | code | origin of distill-to-causal recipe |
| MAGI-1 `[sandai2025magi]` | 2025-05 | 24B, chunk AR | Y (chunk-wise prompting) | constant peak cost; 4M-token context | "real-time" deployment claimed; no FPS in abstract | Apache-2.0 | scalable chunk AR |
| SkyReels-V2 `[chen2025skyreelsv2]` | 2025-04 | diffusion forcing | ? | non-decreasing noise schedule | offline | custom (Skywork) | base for Matrix-Game 2.0 |
| FramePack `[zhang2025framepack]` | 2025-04 | fine-tunes existing VDMs | N | importance-based context packing; anti-drift sampling | consumer GPU (README) | Apache-2.0 | fixed-cost long context |
| Self Forcing `[huang2025selfforcing]` | 2025-06 | Wan2.1 1.3B | inherits | rolling KV cache | ~16 FPS H100 / ~10 FPS 4090, ~0.8 s initial latency, 480p (project page) | Apache-2.0 | de-facto base recipe |
| APT2 / AAPT `[lin2025aapt]` | 2025-06 | 8B, 1 NFE, adversarial | interactive controls | KV cache; student forcing | 24 FPS 736x416 on 1xH100; 1280x720 on 8xH100, up to 1 min | not released | shows 1-NFE is viable |
| StreamDiT `[kodaira2025streamdit]` | 2025-07 | 4B, moving buffer | Y (interactive) | window attention | 16 FPS 512p on 1 GPU | not located | buffer-based alternative |
| LongLive `[yang2025longlive]` | 2025-09 | 1.3B (Self-Forcing base) | **Y, KV-recache** | short window + frame sink | 20.7 FPS on 1xH100; up to 240 s; INT8 | Apache-2.0 | **prompt switching reference** |
| Rolling Forcing `[liu2025rollingforcing]` | 2025-09 | Wan2.1 1.3B | ? | joint denoising window + attention sink | 16 FPS 1 GPU (README) | Tencent custom | error-accumulation fix |
| Self-Forcing++ `[cui2025selfforcingpp]` | 2025-10 | Wan-based | N | self-rollout segment supervision | up to 4 min 15 s | code (no SPDX license) | long horizon |
| RAD `[chen2025rad]` | 2025-11 | DiT + LSTM | N | recurrent global memory + local attention | n/a | project page | memory architecture |
| Resampling Forcing `[guo2025resamplingforcing]` | 2025-12 | from scratch, teacher-free | N | history routing (top-k) | n/a | project page | teacher-free alternative |
| Causal Forcing / ++ `[zhu2026causalforcing]` `[zhao2026causalforcingpp]` | 2026-02 / 05 | Wan 1.3B etc. | inherits | — | ++: frame-wise 2-step, first-frame latency −50% vs chunk 4-step | Apache-2.0 | **lowest-latency distillation** |
| Helios `[yuan2026helios]` | 2026-03 | 14B AR | ? | drift-simulating training; compressed history | 19.5 FPS on 1xH100 | "plan to release" (unverified) | 14B on one GPU if reproducible |
| Echo-Forcing `[wu2026echoforcing]` | 2026-05 | training-free on AR models | **Y** (smooth/hard cuts, recall) | hierarchical temporal memory, scene recall frames, difference-aware decay | bounded cache | code (no license) | **prompt switch + recall** |
| Visko Orbis 1.0 `[gao2026viskoorbis]` | 2026-07 | distilled chunk streamer + streaming upscaler | **Y** ("visible in real time") | bounded multi-scale memory; hour scale | 4K 24 FPS "optimized GPU serving engine" (HW unstated) | no code | strongest claim, least reproducible |

### 2.2 Interactive world models (area b)

| System | Date | Ctrl | Mid-stream text / events | Character control | Memory | Speed & HW (cited) | Open / license |
|---|---|---|---|---|---|---|---|
| GameNGen `[valevski2024gamengen]` | 2024-08 | K | N | player (DOOM) | 64-frame context | 20 FPS, 1 TPU | no |
| DIAMOND `[alonso2024diamond]` | 2024-05 | K | N | player (Atari, CS:GO) | short context | playable | MIT |
| Oasis `[decart2024oasis]` | 2024-10 | K | N | player (Minecraft) | short context | 20 FPS (live demo) | Oasis 500M weights, MIT |
| Genie 2 `[deepmind2024genie2]` | 2024-12 | K | N | agent avatar | "up to a minute" | distilled real-time variant at lower quality | closed |
| Genie 3 `[deepmind2025genie3]` / Project Genie `[google2026projectgenie]` | 2025-08 / 2026-01 | K, C | **Y, promptable world events** | limited ("constrained agent action") | consistent "a few minutes"; memory ~1 min back | 720p 24 FPS (vendor) | closed; Ultra (US) access |
| Matrix-Game `[zhang2025matrixgame]` | 2025-06 | K | N | Minecraft player | — | offline, 17B | MIT |
| Matrix-Game 2.0 `[he2025matrixgame2]` | 2025-08 | K (mouse/keyboard) | **N (text input removed)** | ego | 6-frame KV window; no explicit memory (stated limitation) | 25 FPS 352x640 on 1xH100, 1.8B | MIT |
| Hunyuan-GameCraft `[li2025gamecraft]` | 2025-06 | K→camera space | N | ego | hybrid history condition | distilled "real-time" (no FPS) | Tencent license |
| Voyager `[huang2025voyager]` | 2025-06 | C (trajectory) | N | none | RGB-D world cache (point cloud) | offline | Tencent license |
| Yan `[ye2025yan]` | 2025-08 | K | Y (text editing during interaction) | game character | KV shift-window | 1080P/60FPS simulation module | not located |
| Mirage / Magica `[dynamicslab2025mirage]` | 2025 | K | Y ("change to cyberpunk city") | player | ? | browser demo (vendor) | closed |
| WorldPlay / HY-World 1.5 `[sun2025worldplay]` | 2025-12 | K + dual action | **Y (text-triggered events)** | ego | reconstituted context memory + temporal reframing | 720p 24 FPS on 8xH800; ~30 s horizon (stated limitation) | Tencent HY-WorldPlay license |
| CustomX `[wang2025customx]` | 2025-12 | T (NL directs character) + 3DGS scene | Y | **Y, open-ended actions** | conditional AR | offline | project page |
| LingBot-World `[robbyantteam2026advancingopensourceworldmodels]` | 2026-01 | K, C | ? (see backbone note) | ego | minute-level "long-term memory" | <1 s latency at 16 FPS | Apache-2.0 |
| Matrix-Game 3.0 `[wang2026matrixgame3]` | 2026-04 | K + mouse | no evidence | ego + actions | camera-aware memory retrieval; residual self-correction | up to 40 FPS 720p, 5B, 8 DiT GPUs + 1 VAE GPU | Apache-2.0 weights (HF) |
| ReactiveGWM `[wang2026reactivegwm]` | 2026-05 | K + NPC strategy prompts | Y (NPC strategy) | **player + NPC** | — | n/a | project page |
| minWM `[zhao2026minwm]` | 2026-05 | C | inherits | ego | — | recipe for Wan2.1-1.3B, HY1.5-8B | Apache-2.0 |
| DreamForge-World 0.1 `[ayupov2026dreamforgeworld]` | 2026-06 | K+mouse | **Y (mid-stream reprompting)** | ego | "not memory-complete" | 14 to 15 FPS 480p on 1xRTX 4090 | project page |
| AlayaWorld `[alayaworld2026alayaworld]` | 2026-07 | K | ? | **Y (combat, spells, summoning)** | — | "real-time" | open framework |
| LingBot-World 2.0 `[gao2026infiniteworldsversatileinteractions]` | 2026-07 | K, C, actions | **Y (text-driven events; director agent)** | **Y (attack, archery, spells, shooting; pilot agent)** | causal pretraining, "unbounded horizon"; README uses local attention 18 + sink 6 | paper: 720p @ 60 FPS (distilled); README examples: 480p on 8 GPUs (14B) / 4 GPUs (1.3B) | **CC BY-NC-SA 4.0** |
| WanToFight `[hu2026wantofight]` | 2026-07 | K (2 players) | N | **2 characters** | rolling KV | 30 FPS 512x384 on 1xRTX 5090, 1.3B | project page |
| HelloWorld `[ouyang2026helloworld]` | 2026-08 | C + button | Y (time-localized prompt masks) | **social reactions** (wave, nod, greet) | — | not stated | code (LTX-2 license) |
| EchoWM `[zhang2026echowm]` | 2026-08 | 6-DoF trajectory | ? | 3rd-person camera-character dynamics | AR post-training | 720p + audio; speed not stated | not located |
| Matrix-Game 3.5 `[qian2026matrixgame35]` | 2026-08 | C | "prompt-driven world generation" | subject identity via static-dynamic split | patch memory + tiled PRoPE | "real-time", minute-long | project page |
| SolarWM `[huang2026solarwm]` | 2026-09 | C (metric camera) | ? | ego | trained on 5 s, rolls out minutes to hours | real-time claimed; 4 models 5B to 33B (Wan2.2, LTX-2.5, MiniMax-H3) | Apache-2.0 code; data released |
| Odyssey-2 / Starchild-1 `[odyssey2026starchild]` | 2025-11 / 2026 | K, speech, text | Y (vendor) | ? | ? | "~50 ms" start (secondary source) | closed API |

### 2.3 Avatars / digital humans (area d)

| System | Date | Ctrl | Beyond lip sync? | Identity / long-horizon | Speed & HW (cited) | Open / license |
|---|---|---|---|---|---|---|
| EMO `[tian2024emo]` | 2024-02 | Au | expressions, singing | — | offline | no |
| Hallo / 2 / 3 `[xu2024hallo]` `[cui2024hallo2]` `[cui2024hallo3]` | 2024 | Au (+T labels in Hallo2) | expression labels | patch-drop aug (Hallo2); identity ref net (Hallo3) | offline; Hallo2 up to tens of minutes, 4K | MIT (hallo3) |
| LivePortrait `[guo2024liveportrait]` | 2024-07 | driving video / keypoints | retargeting (eyes, lips) | implicit keypoints | 12.8 ms/frame, RTX 4090 | MIT code (check third-party deps) |
| Ditto `[li2024ditto]` | 2024-11 | Au + motion-space control | gaze/pose control | motion space | "real-time, low first-frame delay" | Apache-2.0 |
| OmniHuman-1 / 1.5 `[lin2025omnihuman]` `[jiang2025omnihuman15]` | 2025-02 / 08 | Au, video, T | **1.5: MLLM-planned semantic actions** | pseudo-last-frame | offline | closed (ByteDance product) |
| FantasyTalking `[wang2025fantasytalking]` | 2025-04 | Au | motion-intensity control | face cross-attention | offline | Apache-2.0 |
| HunyuanVideo-Avatar `[chen2025hunyuanvideoavatar]` | 2025-05 | Au + emotion ref | emotion, multi-character | character image injection | offline | Tencent license |
| MultiTalk `[kong2025multitalk]` | 2025-05 | Au (multi-stream) + T | text instruction following preserved | L-RoPE binding | offline | Apache-2.0 |
| TalkingMachines `[low2025talkingmachines]` | 2025-06 | Au (+audio LLM) | FaceTime-style calls | sparse causal attention | 512x512, 2 NFE; 1 to 2 H100 + 1 VAE GPU | not released |
| OmniAvatar `[gan2025omniavatar]` | 2025-06 | Au + T | text-controlled body/scene | LoRA keeps base prompt control | offline | Apache-2.0 |
| StableAvatar `[tu2025stableavatar]` | 2025-08 | Au | — | time-step-aware audio adapter | offline, infinite length | MIT |
| InfiniteTalk `[yang2025infinitetalk]` | 2025-08 | Au (dubbing) | full-body sync | context frames, keyframe refs | offline streaming generator | Apache-2.0 |
| Wan-S2V `[gao2025wans2v]` | 2025-08 | Au + T | cinematic body/camera | — | offline | Apache-2.0 (Wan2.2) |
| MIDAS `[chen2025midas]` | 2025-08 | Au, pose, T | pose + text conditioning | 64x DC-AE; up to 4 min (1 h with ID fine-tune) | 384x640, 480 ms chunks, Qwen2.5-3B + 0.5B head | not released |
| Kling-Avatar `[ding2025klingavatar]` | 2025-09 | multimodal instructions | **MLLM director blueprint** | keyframe-guided parallel sub-clips | up to 1080p 48 fps (offline) | closed |
| X-Streamer `[xie2025xstreamer]` | 2025-09 | speech/text/video in | end-to-end duplex chat | global identity ref; 8K dialog context | 25 FPS 256x256 on 2xA100 | not released |
| LiveAvatar `[huang2025liveavatar]` | 2025-12 | Au | — | lossy conditioning; >10,000 s | 45 FPS, TTFF 1.21 s, 5xH800; FP8 on 48 GB (README) | Apache-2.0 (Wan2.2-S2V base) |
| StreamAvatar `[sun2025streamavatar]` | 2025-12 | Au (talk + listen) | **gestures, listening** | Reference Sink + RAPR + consistency discriminator | "real-time" (no figure in abstract) | project page (CVPR 2026) |
| SoulX-FlashTalk `[shen2025soulxflashtalk]` | 2025-12 | Au | — | bidirectional in-chunk + retrospective self-correction | 32 FPS, 0.87 s start-up, 8xH800 | Apache-2.0 |
| SoulX-FlashHead `[yu2026soulxflashhead]` | 2026-02 | Au | head only | oracle-guided distillation | Lite: 96 FPS on 1xRTX 4090, 1.3B | Apache-2.0 |
| Tavus Phoenix-4 `[tavus2026phoenix4]` | 2026-02 | Au + emotion states | 10+ emotions, active listening (head/face) | "long term memory module" | 1080p 40 FPS; sub-600 ms end-to-end (vendor) | closed |
| AvatarForcing `[cui2026avatarforcing]` | 2026-03 | Au + T | — | dual-anchor temporal forcing | 34 ms/frame, 1.3B, 1-step | project page |
| LPM 1.0 `[zeng2026lpm]` | 2026-04 | Au (duplex) + **T motion prompts** | **listening, 5,000+ motion descriptors, 78 emotions** | multi-granularity identity refs | "real-time" at 480p (no FPS stated) | not released |
| Hallo-Live `[li2026hallolive]` | 2026-04 | T → joint AV | speech + video | preference-guided DMD | 20.38 FPS, 0.94 s, 2xH200 | not located |
| LongCat-Video-Avatar 1.5 `[longcat2026longcatavatar15]` | 2026-05 | Au | multi-person, object handling | RLHF, 8 NFE | offline | MIT |
| EchoAvatar `[chen2026echoavatar]` | 2026-05 | Au stream + **LLM tool calls** | full-body 3D motion | streaming tokenizer | real-time (3D) | code released (page) |
| Wan-Streamer v0.1 `[huang2026wanstreamer]` | 2026-06 | full duplex AV+text | turn-taking, interruptions, listening | block-causal | 192p; ~200 ms model-side, ~550 ms total incl. 350 ms network; 2-GPU serving | not released |
| Super Star `[jiang2026superstar]` | 2026 (arXiv 2608.24909) | streaming speech | online co-speech gestures | self-evolving loop | low latency (no figure in abstract) | project page |
| Ex-Omni-2D `[zhang2026exomni2d]` | 2026-08 | omni dialogue | **Visual Thought Plan** (scene/emotion/motion) | prefix streaming | 400x720, 4-step on 4 GPUs | not located |
| Decoupled Self-Forcing `[an2026decoupledselfforcing]` | 2026-09 | Au + motion captions | motion captions | motion-space AR + renderer | 15.4 FPS, 1.3 s latency | not located |
| Vidu S2-Avatar `[zhang2026vidus2]` | 2026-09 | voice instructions + **dynamic references** | **dancing, outfit/object/background swap mid-stream** | background stabilization | 720p 25 to 42 FPS (HW unstated) | demo only |
| NVIDIA Audio2Face-3D `[nvidia2025audio2face]` | 2025-08 | Au → 3D blendshapes | face only (3D rig) | n/a | real-time | networks/SDK open-sourced |
| D-ID V4 `[did2026v4]` / HeyGen LiveAvatar `[heygen2025liveavatar]` | 2026 / 2025 | text/LLM → TTS → avatar | lip sync, expressions (vendor) | — | D-ID: <500 ms turn, <120 ms core model (vendor); HeyGen: no figure | closed |

### 2.4 Joint audio-video (area e)

| System | Date | Arch | Duration / res | Streaming? | Open / license |
|---|---|---|---|---|---|
| Veo 3 / 3.1 `[deepmind2025veo]` | 2025-05 / 10 | undisclosed | short clips, up to 4K (3.1 upscaling, secondary source) | N | closed API |
| Sora 2 `[openai2025sora2card]` | 2025-09 | undisclosed | short clips | N | closed app/API |
| JavisDiT / ++ `[liu2025javisdit]` `[liu2026javisditpp]` | 2025-03 / 2026-02 | DiT + HiST-Sypo; ++: MS-MoE, TA-RoPE, AV-DPO on Wan2.1-1.3B | short | N | Apache-2.0 |
| UniVerse-1 `[wang2025universe1]` | 2025-09 | stitching of experts (video + music) | short | N | Apache-2.0 |
| Ovi `[low2025ovi]` | 2025-09 | twin DiT, blockwise bidirectional cross-attention | ~5 s class | N (Hallo-Live distils it) | Apache-2.0 |
| Wan 2.5 / 2.6 `[alibaba2025wan26]` | 2025-09 / 12 | undisclosed | up to ~15 s (secondary) | N | API; Wan 2.5 weights **not located** (third-party claims conflict) |
| LTX-2 `[hacohen2026ltx2]` | 2026-01 | asymmetric dual stream 14B video + 5B audio | up to 4K/50 fps claimed (secondary) | N | LTX community license |
| MOVA `[openmoss2026mova]` | 2026-02 | MoE 32B total / 18B active | IT2VA | N | Apache-2.0 |
| SkyReels-V4 `[chen2026skyreelsv4]` | 2026-02 | dual-stream MMDiT + MLLM encoder | 1080p 32 FPS 15 s | N | not checked |
| Seedance 2.0 `[seedance2026seedance2]` | 2026-02 (report 04) | unified; "Fast" variant | 4 to 15 s, 480p/720p | N | closed |
| MiniMax H3 `[minimax2026h3blogvideo]` | 2026-07 | "H3-Omni Transformer"; ~33B tensor elements (HF metadata) | 4 to 15 s, 24 FPS, 768p default, 2K via regenerate; 32 kHz stereo | N | open weights, MiniMax H3 Community License |
| DreamX-Creator `[zhu2026dreamxcreator]` | 2026-08 | 7B, gated cross-modal attention; AR 1-step 2K refiner | 2K | refiner is chunk-AR | released (per abstract) |
| Hallo-Live `[li2026hallolive]` | 2026-04 | async dual stream, from Ovi | streaming | **Y** 20.38 FPS / 0.94 s on 2xH200 | not located |
| EchoWM `[zhang2026echowm]` | 2026-08 | world model + audio (sound, music, speech) | 720p long-horizon | AR | not located |

### 2.5 Controllable generation primitives (area c)

| Method | Date | Signal | Notes | Open |
|---|---|---|---|---|
| MotionCtrl `[wang2023motionctrl]` | 2023-12 | camera poses + object trajectories | separate camera/object modules | code |
| CameraCtrl `[he2024cameractrl]` | 2024-04 | Plücker camera embedding | plug-in module; later used widely (Plücker cues in Matrix-Game 3.0) | code |
| DragNUWA `[yin2023dragnuwa]` | 2023-08 | text + image + trajectory | multiscale trajectory fusion | code |
| Tora `[zhang2024tora]` | 2024-07 | trajectories into DiT | motion patches | code |
| Motion Prompting `[geng2024motionprompting]` | 2024-12 | sparse/dense point tracks | "motion prompt expansion" from high-level requests | project page |
| Animate Anyone `[hu2023animateanyone]` | 2023-11 | pose skeleton + ReferenceNet | pose-driven character animation | (Animate Anyone 2 etc.) |
| MimicMotion `[zhang2024mimicmotion]` | 2024-06 | confidence-aware pose | progressive latent fusion for length | code |
| Wan-Animate `[cheng2025wananimate]` | 2025-09 | skeleton + implicit face features | animation and replacement; relighting LoRA | open (Wan2.2) |
| History Guidance / DFoT `[song2025historyguidance]` | 2025-02 | variable-length history | guidance over history; long rollouts | code |

---

## 3. Per-system notes

Format: *Approach · Capabilities/control · Memory/consistency · Speed/HW (cited) · Availability/license · Limitations · Relevance · URL.*

### 3.1 Streaming / AR video

**Diffusion Forcing** `[chen2024diffusionforcing]`, 2024-07. Trains a causal model to denoise tokens with *independent per-token noise
levels*. This combines next-token variable-length rollout with full-sequence guidance. Foundational for every "forcing" method and
for SkyReels-V2/MAGI-1-style non-decreasing noise schedules. Research scale (not a product model). The follow-up DFoT/History
Guidance `[song2025historyguidance]` adds guidance over variable-length history. https://arxiv.org/abs/2407.01392

**StreamingT2V** `[henschel2024streamingt2v]`, 2024-03. Chunk AR with a conditional attention module (short-term memory) and an
appearance-preservation module (long-term anchor from the first chunk). Offline, but an early "memory anchor" design that
foreshadows attention sinks. https://arxiv.org/abs/2403.14773

**CausVid** `[yin2024causvid]`, 2024-12 (CVPR 2025). Adapts a bidirectional DiT to causal generation. DMD-distils 50 steps into 4.
Initializes the student from teacher ODE trajectories. Uses asymmetric distillation (bidirectional teacher, causal student).
9.4 FPS on one GPU with KV caching (cited). Zero-shot "dynamic prompting". Limitation: exposure bias on long rollouts, which later
Self Forcing addresses. https://arxiv.org/abs/2412.07772

**MAGI-1** `[sandai2025magi]`, 2025-05. 24B chunk-AR model with monotonically increasing per-chunk noise. Chunk-wise prompting
enables narrative control. Constant peak inference cost regardless of length. Apache-2.0 (verified). The abstract claims "real-time,
memory-efficient deployment" without an FPS figure, so treat as unverified for real time. https://arxiv.org/abs/2505.13211

**SkyReels-V2** `[chen2025skyreelsv2]`, 2025-04. Film-oriented model. Diffusion forcing with non-decreasing noise schedules for
infinite-length extension, plus a shot-aware captioner. Its I2V-1.3B checkpoint is the base of Matrix-Game 2.0. Skywork custom
license. https://arxiv.org/abs/2504.13074

**FramePack** `[zhang2025framepack]`, 2025-04. Compresses history by frame importance so that context length is constant. Adds
anti-drift sampling (early endpoints, inverted order). Apache-2.0. Useful as a fixed-memory context mechanism. It is not a causal
real-time model. https://arxiv.org/abs/2504.12626

**Self Forcing** `[huang2025selfforcing]`, 2025-06 (NeurIPS 2025 spotlight). Trains on the model's own KV-cached AR rollouts with a
video-level (DMD) loss, using stochastic gradient truncation. Rolling KV cache for extrapolation. About 16 FPS on H100 and about
10 FPS on RTX 4090, with about 0.8 s initial latency at 480p (project page, cited). Apache-2.0 code on Wan2.1-1.3B. This is the
*de-facto starting codebase* for LongLive, SoulX-FlashTalk and others. Limitation: quality decays beyond the training horizon
(about 5 s), which motivated the ++ work. https://arxiv.org/abs/2506.08009

**APT2 / AAPT** `[lin2025aapt]`, 2025-06 (NeurIPS 2025, ByteDance Seed). Adversarial post-training produces a 1-NFE-per-latent-frame
AR generator with student-forcing training. 8B model: 24 FPS at 736x416 on 1xH100, or 1280x720 on 8xH100, up to 1 min (cited).
Shows interactive pose-controlled virtual human and camera-controlled world exploration. Weights not released. Relevance: a
1-NFE design minimizes instruction-to-visual latency. https://arxiv.org/abs/2506.09350

**StreamDiT** `[kodaira2025streamdit]`, 2025-07 (CVPR 2026). Flow matching with a moving frame buffer and mixed partitioning. Multistep
distillation cuts NFEs to the number of buffer chunks. 4B model, 16 FPS at 512p on one GPU (cited). Supports interactive and
video-to-video streaming. https://arxiv.org/abs/2507.03745

**LongLive** `[yang2025longlive]`, 2025-09 (NVlabs). Frame-level AR model. **KV-recache** refreshes cached states with the new prompt
at a switch. Trained with "streaming long tuning" (train long, test long). Uses a short window plus a frame-level attention sink.
Fine-tunes 1.3B to minute length in 32 GPU-days. 20.7 FPS on 1xH100, up to 240 s, INT8 supported (cited). Apache-2.0. **The most
directly reusable mechanism for mid-stream instruction changes.** The paper states the trade-off explicitly: keeping the full KV cache
delays adaptation, and dropping it causes discontinuity. https://arxiv.org/abs/2509.22622

**Rolling Forcing** `[liu2025rollingforcing]`, 2025-09 (ICLR 2026, TencentARC). Joint denoising of a window with increasing noise
levels, which relaxes strict per-frame causality. Attention sink on the initial frames. Few-step distillation over long windows.
16 FPS on a single GPU, minute-long videos (README, cited). Tencent custom license. https://arxiv.org/abs/2509.25161

**Self-Forcing++** `[cui2025selfforcingpp]`, 2025-10. The teacher corrects segments sampled from the student's own long rollouts.
Reaches 4 min 15 s, which is 99.9% of the base model's positional-embedding span and more than 50x CausVid (cited). The repo has no
SPDX license. Shows that long horizons are limited by the positional-embedding span, not only by drift.
https://arxiv.org/abs/2510.02283

**Resampling Forcing** `[guo2025resamplingforcing]`, 2025-12. Teacher-free end-to-end AR training by self-resampling degraded
history. "History routing" retrieves the top-k relevant history frames without extra parameters. Relevant if we ever pretrain
causally instead of distilling. https://arxiv.org/abs/2512.15702

**RAD** `[chen2025rad]`, 2025-11 (ECCV 2026). Adds an LSTM after attention in each DiT layer as fixed-budget global memory, with
overlapping sliding-window full attention. Evaluated on Memory Maze and Minecraft. Complements the SSM world model of Po et al.
`[po2025ssmworldmodel]`. https://arxiv.org/abs/2511.12940

**Causal Forcing / Causal Forcing++** `[zhu2026causalforcing]` (ICML 2026), `[zhao2026causalforcingpp]` 2026-05 (THU-ML/ShengShu).
Proves that ODE-initializing a causal student from a *bidirectional* teacher violates frame-level injectivity, and uses an AR
teacher instead. Reports +19.3% Dynamic Degree and +16.7% instruction following over Self Forcing (cited). ++ uses causal consistency
distillation to reach *frame-wise 1 to 2 step* AR, with 50% lower first-frame latency than chunk-wise 4-step, and extends to
Genie-3-style action-conditioned world models (cited). Apache-2.0. **Most relevant for reducing response granularity (G1).**
https://arxiv.org/abs/2602.02214 , https://arxiv.org/abs/2605.15141

**Helios** `[yuan2026helios]`, 2026-03 (PKU). 14B AR diffusion model. Claims 19.5 FPS on one H100 *without* KV cache, sparse
attention or quantization. Instead it heavily compresses history and noisy context and simulates drift during training. Supports T2V,
I2V and V2V. The code is "planned", so the claim is **not yet reproducible**. If it holds, it matters for fitting 14B on one L20X.
https://arxiv.org/abs/2603.04379

**Echo-Forcing** `[wu2026echoforcing]`, 2026-05. Training-free memory for AR models. Hierarchical temporal memory separates anchors,
compressed history and the recent window. Scene Recall Frames support long-term recall. Difference-aware decay forgets tokens that
conflict with a new prompt. Supports smooth transitions, hard cuts and recall of earlier scenes under a bounded cache. Code released
(no license file). Directly relevant to G1 and G4. https://arxiv.org/abs/2605.16003

**Visko Orbis 1.0** `[gao2026viskoorbis]`, 2026-07. "Live Model": a chunk-wise distilled streamer plus a streaming upscaler. Prompt
changes are "visible in real time". Bounded multi-scale memory. Hour-scale rollouts. **4K at 24 FPS** with an unspecified GPU serving
engine (cited). No code or hardware disclosure, so this is **marketing-grade evidence** despite the arXiv report.
https://arxiv.org/abs/2607.26694

### 3.2 Interactive world models

**Genie / Genie 2 / Genie 3** `[bruce2024genie]` `[deepmind2024genie2]` `[deepmind2025genie3]`. Genie (2024-02) is an 11B latent-action
model trained from unlabelled video. Genie 2 (2024-12) is an AR latent diffusion model that stays consistent "up to a minute"; its
distilled variant runs in real time at lower quality (blog). Genie 3 (2025-08) runs at 720p and 24 FPS in real time, stays
consistent for "a few minutes" with memory reaching back about 1 minute, and has **promptable world events** (weather, new objects,
characters). DeepMind lists its limitations: constrained agent action space, weak multi-agent interaction, unreliable text, and only
minutes of interaction. Closed. Available as Project Genie to US Google AI Ultra subscribers since 2026-01-29. No paper, so all
numbers are vendor claims. Relevance: the reference point for "promptable events". https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/

**GameNGen** `[valevski2024gamengen]`, 2024-08 (ICLR 2025). DOOM simulated by a diffusion model at 20 FPS on one TPU. Noise
augmentation on the context keeps rollouts stable. https://arxiv.org/abs/2408.14837 .
**DIAMOND** `[alonso2024diamond]`, 2024-05. Diffusion world model for RL (Atari 100k HNS 1.46) and a playable CS:GO. MIT.
https://arxiv.org/abs/2405.12399 .
**Cosmos** `[nvidia2025cosmos]` (2025-01) is NVIDIA's open physical-AI world foundation model platform. It is not real-time or
interactive in the sense used here and is listed only as background.
**Oasis** `[decart2024oasis]`, 2024-10. Decart/Etched Minecraft model running at 20 FPS live. Open "Oasis 500M" weights (MIT).
Short memory (objects vanish). https://oasis-model.github.io/

**Matrix-Game 1/2/3/3.5** (Skywork). v1 `[zhang2025matrixgame]` (2025-06): 17B, Minecraft, offline, MIT. **v2** `[he2025matrixgame2]`
(2025-08): 1.8B on SkyReels-V2-I2V-1.3B, 3-step AR distillation, 25 FPS at 352x640 on 1xH100 (cited). Keyboard/mouse action
injection. It **removes all language input**, and its limitations section admits it has no explicit memory. MIT. **v3**
`[wang2026matrixgame3]` (2026-04): Wan2.2-TI2V-5B, camera-aware memory retrieval with Plücker cues, prediction-residual
self-correction, up to 40 FPS at 720p with 8 DiT GPUs + 1 VAE GPU (cited). A 2x14B variant exists. Apache-2.0 weights on HF.
**v3.5** `[qian2026matrixgame35]` (2026-08): parameter-free patch memory with tiled PRoPE, and a static/dynamic disentangled world
representation that keeps *subject identity*. Mentions "prompt-driven world generation". https://arxiv.org/abs/2508.13009 ,
https://arxiv.org/abs/2604.08995 , https://arxiv.org/abs/2608.29910

**Hunyuan-GameCraft** `[li2025gamecraft]`, 2025-06. Maps keyboard/mouse into a shared camera space. Hybrid history conditioning.
Distilled for real time (no FPS in abstract). Trained on more than 1M recordings from 100+ AAA games. Tencent license.
**HunyuanWorld-Voyager** `[huang2025voyager]`, 2025-06: RGB-D video diffusion along a user camera path with a point-cloud world
cache. Explicit 3D memory but offline. https://arxiv.org/abs/2506.17201 , https://arxiv.org/abs/2506.04225

**WorldPlay / HY-World 1.5** `[sun2025worldplay]`, 2025-12. Dual action representation. *Reconstituted Context Memory* retrieves by
FOV overlap and camera distance, and *temporal reframing* re-assigns RoPE positions so that old but important frames count as
"recent". *Context Forcing* aligns memory context between teacher and student during distillation. 720p 24 FPS on **8xH800**. Supports
text-triggered world events. Stated limits: about 30 s generations, limited action types, no multi-agent support. Tencent HY-WorldPlay
license (excludes EU/UK/KR). https://arxiv.org/abs/2512.14614

**Yan** `[ye2025yan]`, 2025-08 (Tencent). Three modules. (1) "AAA-level simulation": a highly compressed 3D-VAE plus KV-cache
shift-window denoising, claimed at **1080P/60FPS** (cited). (2) Multi-modal generation that injects game knowledge through
hierarchical captions. (3) Text-driven editing during interaction, where mechanics simulation is decoupled from rendering. Weights not
located. https://arxiv.org/abs/2508.08601

**Mirage / Magica** `[dynamicslab2025mirage]` (Dynamics Lab, 2025). Real-time "UGC game engine" in which a text console changes the
world live ("change to cyberpunk city"). Browser demos. No paper, so vendor claims only.

**CustomX** `[wang2025customx]`, 2025-12 (ECCV 2026). The user supplies a 3DGS scene and a character, then directs the character in
natural language (locomotion through object interaction). Conditional AR video. Not real-time. Evidence that NL character direction
inside a world is learnable. https://arxiv.org/abs/2512.17796

**LingBot-World / 2.0** `[robbyantteam2026advancingopensourceworldmodels]` `[gao2026infiniteworldsversatileinteractions]`. Covered in
depth in the backbone note. Facts relevant here: v1 (2026-01) reports <1 s latency at 16 FPS and minute-level memory, Apache-2.0. v2
(2026-07) reports an "unbounded" horizon via causal pretraining, a distilled real-time variant "sufficient to drive 720p video
streams at 60 fps", **character actions** (attacking, archery, spell-casting, shooting), **text-driven events**, and a *pilot agent*
(plans character behavior) plus a *director agent* (adds environment elements). There is a multiplayer interface and 14B and 1.3B
checkpoints. **License CC BY-NC-SA 4.0.** The released README demonstrates 480x832 runs on 8 GPUs (14B causal-fast) and 4 GPUs (1.3B)
with `local_attn_size 18`, `sink_size 6`. The 720p60 figure is a paper claim not yet reproduced here. **It is the only surveyed
open-weight world model that combines character actions, text events and an agent harness.** Speech and lip sync are absent.
https://arxiv.org/abs/2607.07534

**ReactiveGWM** `[wang2026reactivegwm]`, 2026-05. Player actions enter as an additive bias. NPC strategies (offense, control,
defense) enter through cross-attention modules that transfer zero-shot to other game world models. Street Fighter only.
https://arxiv.org/abs/2605.15256 .
**WanToFight** `[hu2026wantofight]`, 2026-07. Two-player KOF'97 on Wan-1.3B. A Player Association module binds each keyboard stream
to a character identity. 30 FPS at 512x384 on one RTX 5090 (cited). https://arxiv.org/abs/2607.12592 .
**AlayaWorld** `[alayaworld2026alayaworld]`, 2026-07. Full-stack open framework with combat, spell casting and monster summoning.
https://arxiv.org/abs/2607.06291

**HelloWorld** `[ouyang2026helloworld]`, 2026-08 (Alaya Lab). A button press makes an in-world character turn to the viewer, wave, nod
or say a short greeting. Trained by self-distillation on its own synthesized clips that combine social actions and camera motion. At
inference, a *training-free cross-attention mask* confines the interaction prompt to the frames of the press window. This is a neat
mechanism for time-localizing an instruction. Ships HelloWorldBench (400 samples). The repo LICENSE is the LTX-2 Community License, which suggests an LTX-2 base (unverified).
No real-time claim. **Closest prior work to "persona reacts to user inside a world".** https://arxiv.org/abs/2608.05070

**EchoWM** `[zhang2026echowm]`, 2026-08. Omnimodal world model that generates 720p video together with environmental sound, music and
speech. Discrete commands and continuous poses map to a metric 6-DoF trajectory. Third-person camera-character dynamics are learned
without view-specific controllers. AR post-training for long horizons. No speed figure. Relevance: world model plus speech in one
model (G6). https://arxiv.org/abs/2608.23189

**SolarWM** `[huang2026solarwm]`, 2026-09-02. Open data engine: 1.43M clips from 10 datasets, with metric camera, captions and
provenance. Backbone-native adaptation of four 5B to 33B models (Wan2.2, LTX-2.5, **MiniMax-H3**). Three-stage recipe: bidirectional
adaptation, teacher-forced AR initialization, then DMD. Trained on 5 s clips, yet rolls out real-time for "minutes to hours" (cited).
Camera conditioning only. Code Apache-2.0; data and weights released. Relevance: a reproducible recipe for adapting *any* backbone
(including H3) into a causal real-time world model. https://arxiv.org/abs/2609.02886

**DreamForge-World 0.1** `[ayupov2026dreamforgeworld]`, 2026-06. LongLive stack with a Matrix-Game-style residual action path. Supports
mid-stream reprompting. 14 to 15 FPS at 480p on one RTX 4090 (cited). Self-described as "not memory-complete". A useful low-compute
baseline. https://arxiv.org/abs/2606.30292

**Odyssey-2 / Starchild-1** `[odyssey2026starchild]`. Odyssey-2 (2025-11) is an interactive video model with "~50 ms" start (secondary
source). Starchild-1 (2026) claims real-time *audio+video* world simulation that responds to speech, text and actions. Closed API.
No paper, so unverified.

**Benchmarks:** WBench `[ying2026wbench]` has 289 cases and 1,058 turns across navigation, subject action, **event editing** and
perspective switching. It evaluated 20 models and found none strong everywhere. WorldRoamBench `[xu2026worldroambench]` has 1000+ cases
with 10 to 60 s WASD interaction and scene and subject memory probes. Both are directly usable for the world-model side of our
evaluation.

### 3.3 Controllable generation

**CameraCtrl** `[he2024cameractrl]` (Plücker embeddings, plug-in camera module) and **MotionCtrl** `[wang2023motionctrl]` (separate
camera and object motion modules) are the canonical camera-control designs. Plücker-style cues reappear in Matrix-Game 3.0 and
tiled-PRoPE in 3.5. **Trajectory control:** DragNUWA `[yin2023dragnuwa]`, Tora `[zhang2024tora]`, Motion Prompting
`[geng2024motionprompting]`. Motion Prompting's "motion prompt expansion" (turning high-level requests into point tracks) is a
possible interface from LLM instructions to motion. **Pose/skeleton:** Animate Anyone `[hu2023animateanyone]`, MimicMotion
`[zhang2024mimicmotion]`, Wan-Animate `[cheng2025wananimate]`. Pose conditioning is also used interactively by APT2 (virtual human)
and MIDAS. For a live agent, a *pose/gesture token* stream from the LLM, rendered by a pose-conditioned streaming generator, is a
plausible intermediate representation. EchoAvatar and Super Star take this route in 3D. Decoupled Self-Forcing
`[an2026decoupledselfforcing]` does it in a 2D motion space.

### 3.4 Avatars / digital humans

**Offline quality line.** EMO `[tian2024emo]`; Hallo 1/2/3 `[xu2024hallo]` `[cui2024hallo2]` `[cui2024hallo3]` (Hallo2 adds text
expression labels and hour-long 4K; Hallo3 moves to a video DiT with an identity reference network); FantasyTalking
`[wang2025fantasytalking]` (motion-intensity control); HunyuanVideo-Avatar `[chen2025hunyuanvideoavatar]` (emotion reference,
multi-character); MultiTalk `[kong2025multitalk]` (L-RoPE multi-person binding, keeps text instruction following);
OmniAvatar `[gan2025omniavatar]` (LoRA keeps prompt control); StableAvatar `[tu2025stableavatar]`; InfiniteTalk `[yang2025infinitetalk]`;
Wan-S2V `[gao2025wans2v]`; LongCat-Video-Avatar 1.5 `[longcat2026longcatavatar15]` (8 NFE, MIT, claims parity with HeyGen, OmniHuman 1.5
and Kling Avatar 2.0 on its own benchmark). These define quality ceilings and provide Wan-based audio-conditioning modules.
Most are Apache-2.0 or MIT.

**OmniHuman-1 / 1.5** `[lin2025omnihuman]` `[jiang2025omnihuman15]` (ByteDance). 1.5 uses an MLLM to produce structured semantic
conditions, so gestures follow meaning and not only rhythm (a "System 2" planner). It adds a pseudo-last-frame MMDiT. Offline and
closed. The key reference for *instruction-driven behavior beyond lip sync*. **Kling-Avatar** `[ding2025klingavatar]`: an MLLM director
produces a blueprint video, and first-last-frame sub-clips are generated in parallel, up to 1080p/48 fps. Offline, closed.

**TalkingMachines** `[low2025talkingmachines]`, 2025-06 (Character.AI). Wan2.1 I2V adapted to an 18B audio-driven model with a 1.2B
audio module. Asymmetric DMD into a sparse causal student with a 2 NFE and 3-latent-frame chunk. Disaggregates the DiT (1 to 2 H100)
and the VAE decoder (1 H100); the VAE takes about 30% of chunk time (cited). Integrated with an audio LLM for FaceTime-style calls.
Not released. Relevance: a template for cascade serving (audio LLM, then streaming avatar). https://arxiv.org/abs/2506.03099

**MIDAS** `[chen2025midas]`, 2025-08. LLM backbone (Qwen2.5-3B) with a diffusion head (about 0.5B, PixArt-α). Multimodal
conditions: audio, pose, text. 64x DC-AE. 480 ms streaming chunks, 384x640. Up to 4 min without drift, 1 h with identity fine-tuning
(cited). Trained on a 20k-hour dialogue set. Not released. https://arxiv.org/abs/2508.19320

**X-Streamer** `[xie2025xstreamer]`, 2025-09 (project page under byteaigc.github.io). Thinker-Actor design: a frozen GLM-4-Voice Thinker, and an Actor that is a
chunk-wise AR diffusion model cross-attending to the Thinker's hidden states and emitting interleaved text, audio and video. 18B total.
25 FPS at 256x256 on 2xA100. Global identity reference. 8K-token dialogue context (about 10 min) (full text, cited). Talking-head
only. No user-directed gestures. Not released. **The canonical end-to-end digital-human-agent architecture.**
https://arxiv.org/abs/2509.21574

**LiveAvatar** `[huang2025liveavatar]`, 2025-12 (Alibaba Quark; ECCV 2026 spotlight). Built on Wan2.2-S2V-14B. Two-stage causal
few-step distillation. Lossy conditioning suppresses drift beyond 10,000 s. **Timestep-forcing Pipeline Parallelism** (one GPU per
denoising timestep). 45 FPS, TTFF 1.21 s on 5xH800 (cited). The README adds FP8 on 48 GB GPUs and single-GPU offline inference.
Apache-2.0. **Most reusable open real-time 14B avatar system; TPP is directly applicable to serving LingBot-World.**
https://arxiv.org/abs/2512.04677

**SoulX-FlashTalk / FlashHead** `[shen2025soulxflashtalk]` `[yu2026soulxflashhead]` (Soul AI Lab). FlashTalk: 14B built on
InfiniteTalk/Wan and the Self-Forcing codebase. Keeps *bidirectional attention inside chunks*. Multi-step retrospective self-correction.
32 FPS, 0.87 s start-up; README says real time needs 8xH800, with a 4-GPU real-time version later (cited). FlashHead: 1.3B,
oracle-guided distillation, Lite at 96 FPS on an RTX 4090. Both Apache-2.0. https://arxiv.org/abs/2512.23379

**StreamAvatar** `[sun2025streamavatar]`, 2025-12 (CVPR 2026). AR distillation plus adversarial refinement of a human video model.
Reference Sink, reference-anchored positional re-encoding and a consistency-aware discriminator. Generates **talking *and* listening
behavior with coherent gestures**, beyond head and shoulders. https://arxiv.org/abs/2512.22065

**AvatarForcing** `[cui2026avatarforcing]`, 2026-03. One-step local-future sliding-window denoising, dual-anchor temporal forcing,
34 ms/frame with a 1.3B student (cited). https://arxiv.org/abs/2603.14331

**LPM 1.0** `[zeng2026lpm]`, 2026-04. 17B Base LPM (720p) distilled to Online LPM (480p, "real-time", no FPS stated). Full-duplex:
listening video driven by user audio, speaking video driven by TTS audio. **Text prompts control motion**: 22 expression bases, 78
emotions, 5,000+ motion descriptors (full text, cited). Multi-granularity identity references for infinite-length identity stability.
Stated limits: single person, passive listening skew, limb artifacts. Not released. **The closest system to our persona-performance
requirement.** https://arxiv.org/abs/2604.07823

**Hallo-Live** `[li2026hallolive]`, 2026-04. Streaming *joint* audio-video avatar distilled from Ovi. Future-Expanding Attention gives
video blocks short look-ahead phonetic cues. Human-preference-weighted DMD. 20.38 FPS, 0.94 s on 2xH200 (cited).
https://arxiv.org/abs/2604.23632

**EchoAvatar** `[chen2026echoavatar]`, 2026-05 (SIGGRAPH 2026). Streaming 3D full-body motion from speech or music with a **tool-call
interface through which upstream LLMs inject semantic control**. Code released. A good pattern for LLM-to-gesture interfaces.
https://arxiv.org/abs/2605.28272

**Wan-Streamer v0.1** `[huang2026wanstreamer]`, 2026-06 (Alibaba Wan). Single transformer with interleaved text, audio and video
input/output tokens under block-causal attention. No external ASR, TTS or avatar modules. 160 ms units at 25 fps. About 200 ms
model-side and about 550 ms total latency including 350 ms network. **192p proof of concept.** Two-GPU thinker-performer serving.
Learns listening behavior, interruptions and proactive speaking. Not released. https://arxiv.org/abs/2606.25041

**Ex-Omni-2D** `[zhang2026exomni2d]`, 2026-08. An omni dialogue model first writes a *Visual Thought Plan* (scene, emotion, motion),
then emits speech units aligned to video. Streaming student at 400x720, 4 steps on 4 GPUs. A partial fix for late-chunk subject drift.
https://arxiv.org/abs/2608.10720

**Vidu S2** `[zhang2026vidus2]`, 2026-09 (ShengShu). Avatar at real-time 720p, 25 to 42 FPS. Stronger instruction following (e.g.
**dancing**). **Dynamic reference images can be swapped at any moment** (pick up an object, change clothes or background), validated by
an agentic system. Also real-time stream editing. Demo only. Reports degradation beyond 90 s. https://arxiv.org/abs/2609.11638

**Others (brief):** Ditto `[li2024ditto]` (motion-space DiT, real-time, Apache-2.0). LivePortrait `[guo2024liveportrait]` (implicit
keypoints, 12.8 ms/frame). StreamTalk `[zhang2026streamtalk]` (streaming 3D co-speech gesture, 76 FPS). Super Star
`[jiang2026superstar]` (online co-speech gestures for companions with a self-evolving loop). Decoupled Self-Forcing
`[an2026decoupledselfforcing]` (motion-space AR plus renderer, 15.4 FPS at 1.3 s). NVIDIA Audio2Face-3D `[nvidia2025audio2face]`
(3D blendshapes, open-sourced SDK and networks; for a 3D-rig path instead of pixels).

**Commercial (vendor claims, not reproducible):**
- Tavus Phoenix-4 (2026-02): Gaussian-splatting plus diffusion head; 1080p 40 FPS; 10+ emotion states; active listening; sub-600 ms
  end-to-end. The CVI pipeline is perception, then dialogue, then ASR, LLM, TTS, and finally Phoenix rendering.
- D-ID V4 (2026): <500 ms turn, <120 ms core model.
- HeyGen LiveAvatar: no published latency.
- Synthesia 3.0 "Video Agents": enterprise rollout 2026 (secondary sources).
- Soul Machines: autonomous animation "Digital People". Current status unverified.

All are cascades (ASR, LLM, TTS, renderer). None exposes world or scene control. Gestures are limited to a vendor-defined set.

### 3.5 Joint audio-video

**Veo 3 / 3.1** `[deepmind2025veo]` (2025-05 / 10) and **Sora 2** `[openai2025sora2card]` (2025-09-30 system card) established native
dialogue, SFX and ambience with lip sync. Both are closed and architecture-undisclosed. Veo 3 was also shown to be a zero-shot visual
reasoner `[wiedemer2025veozeroshot]`. **Seedance 2.0** `[seedance2026seedance2]`: unified text, image, audio and video inputs; 4 to
15 s at 480p/720p; closed. **Wan 2.5/2.6** `[alibaba2025wan26]`: API products with native audio. Wan 2.6 adds R2V with the reference
character's appearance *and voice*. I found no official weight release for 2.5 or 2.6 (third-party claims conflict), so treat as
closed.

**Open:** Ovi `[low2025ovi]` (twin identical DiTs with blockwise bidirectional cross-attention and scaled RoPE; Apache-2.0). LTX-2
`[hacohen2026ltx2]` (14B video + 5B audio asymmetric dual stream; modality-CFG; LTX community license; LTX-2.5 used by SolarWM and
LTX-2.3 exist). MOVA `[openmoss2026mova]` (32B MoE, 18B active; Apache-2.0). UniVerse-1 `[wang2025universe1]`. JavisDiT/++
`[liu2025javisdit]` `[liu2026javisditpp]`. SkyReels-V4 `[chen2026skyreelsv4]` (1080p 32 FPS 15 s plus inpainting and editing).
DreamX-Creator `[zhu2026dreamxcreator]` (7B plus AR 1-step 2K refiner). **MiniMax H3** `[minimax2026h3blogvideo]` (API
2026-07-31; HF repo created 2026-07-28, public in early August per press). Unified T/I/V/A context, 4 to 15 s at 24 FPS, default
768p, 2K via regenerate, 32 kHz stereo, 11 stable dialogue languages; MiniMax H3 Community License; about 33B tensor elements per
HF metadata; tech report "coming" at blog time. All are offline clip generators. For a live agent they serve as teachers for streaming
distillation (Hallo-Live from Ovi; SolarWM adapts H3 into a causal camera-controlled model) or as offline asset generators.

---

## 4. Items checked and not included / caveats

- "MiniMax Hailuo H3" and "MiniMax H3" refer to the same system. MiniMax H3's internal architecture beyond the blog and model card is
  **unverified** (no tech report located).
- Soul Machines' current operating status and Synthesia Video Agents specs: **unverified** (secondary sources only).
- The Odyssey-2 "~50 ms" and Starchild-1 capabilities come from press or secondary coverage, not a paper.
- Veo 3's joint latent-diffusion architecture description in third-party blogs is **unverified**. Google has not published it.
- The HF model id `character-ai/Ovi` returned an auth error on the HF API. The GitHub repo (Apache-2.0) is verified.
- Super Star: the arXiv ID is 2608.24909, but the API reports its v1 date as 2026-07-22. I cite the ID and the date as returned.
