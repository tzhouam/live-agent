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

