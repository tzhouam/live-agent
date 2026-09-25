# TaoMate and TaoMate-H3: a deep dive for building a live persona agent

Compiled on 2026-09-25. This was a read-only study: I ran nothing on a GPU and downloaded no weights. The one hardware query was `nvidia-smi --query-gpu`, and it reports 8× L20X with compute capability 8.9.

This document supersedes and refines `taomate_h3_assessment.md`. Where the two disagree, trust this one, because it is based on reading the code.

## Sources and commit hashes

| Source | Revision |
|---|---|
| Paper, arXiv 2607.24359v1 (27 Jul 2026). HTML at https://arxiv.org/html/2607.24359 and the PDF (9 pages, no supplementary material) | v1 |
| Project page https://taoliveaigc.github.io/TaoMate/ | fetched 2026-09-25 |
| `external/TaoMate-H3` | `6b2f9984acf681e2f387188f5d1f3b26e504315b` (2026-09-23) |
| `external/TaoMate` (the LTX-2.3 paper model and its interactive demo) | `136d89083f13c6d3eceb7cfe8a0ef4ac2ea0bfdd` (2026-09-08) |
| HF `TaoLiveAIGC/TaoMate-H3` (API sha) | `7d7a51f3e63972138882ec2f0e4d1d47728110cf`. `config.json` = `{"rank":128,"alpha":128.0,"weight_source":"generator_ema","optimizer_step":3000}` |
| `external/vllm-omni` | local HEAD `7b4dc7633`; fetched `origin/main` `3bd5ac968` (2026-09-25) |

Paths below are relative to `external/TaoMate-H3/src/taomate_h3/` (**H3:**), to `external/TaoMate/` (**TM:**) or to `external/vllm-omni/` (**VO:**).

**The single most important point.** There are two different systems:
- **TaoMate** (paper and repo) is LTX-2.3-based. It has learned persistent memory, an interactive demo, and claims real-time speed.
- **TaoMate-H3** is a 3-step LoRA plus a streaming runtime on MiniMax H3. It has **none** of the paper's learned memory. It is **not real-time** on the validated hardware, and its audio comes from a separate pre-pass with the base model.

---

## 1. The TaoMate paper (arXiv 2607.24359)

### Architecture
- **Backbone.** "The causal generator is initialized from a distilled LTX-2.3 checkpoint and optimized against a frozen bidirectional teacher using three denoising steps per block" (§4.1). Table 1 lists it at 22.1B parameters (the LTX-2.3 base is 22B).
- **Memory modules.** "Residual memory attention is inserted every four transformer layers, giving 12 memory-enabled layers in the 48-layer backbone. The video branch receives 48 tokens formed by the visual anchor and dynamic video state, while the audio branch receives 64 dynamic-state tokens; together with the modality encoders and video FiLM, these branches add approximately 97.8M trainable parameters" (§4.1).
  - Note that the 48 video tokens are **anchor plus dynamic state together**, not 48 dynamic tokens.
  - In code, pooling gives 24 anchor + 24 EMA tokens at 512×768, which is 48 in total (TM `taomate/runtime_support/learned_memory.py:192-209,550-563`).
- **Memory state.** M_t = (a^v, a^a, m^v_t, m^a_t, κ_t, π_t) (§3.2, Eq. 2). "The visual anchor a^v and audio reference a^a retain canonical evidence from the initial block."
  - The anchor is formed from the **first generated block**. It is not a user image.
- **Update rule.** Anchor-regularized EMA: E(m,a,s;β,λ) = (1−λ)[(1−β)m+βs]+λa (Eq. 4).
  - The video rate is gated by cosine agreement with the anchor (Eq. 5). Audio is ungated.
  - Hyperparameters: (β_v,λ_v)=(0.15,0.20), (β_a,λ_a)=(0.10,0.10), (τ,T_g,g_min)=(0.05,0.10,0.10), appearance (β_c,λ_c)=(0.03,0.60) (§4.1).
- **Conditioning.** h̃ = h + MemAttn(RMSNorm(h), u_{t−1}) for each modality, plus a reference-aware FiLM on video (§3.3, Eq. 6).
  - "Memory K/V remain outside the active cache, so fixed token counts keep the additional cost independent of generated duration."
  - "Both pathways are residual and initialized as identity mappings."
- **Active context.** "At a prompt transition, the active context retains the initial visual reference and at most two recent non-anchor blocks. Only completed blocks update the persistent memory, and local RoPE coordinates restart for each prompt-conditioned segment" (§4.1).
  - The code does not match this. The TM code keeps absolute RoPE on the persistent-cache path (see §3).
- **Training** (§3.4, §4.1):
  - Method: DMD on causal self-rollouts, plus video PCM with weight 0.03 from step 400.
  - Teacher classifier-free guidance: 3.0 for video, 5.0 for audio.
  - Rollout horizons: 5 or 10 blocks, with probability 0.8 / 0.2.
  - Student-prefix substitution happens with probability 0.1. Reused history is re-noised with σ~U(0,0.15). The anchor is kept clean.
  - Data: 6,139 synthetic LTX-2.3 teacher trajectories of up to 241 frames at 768×512, 24 fps.
- **Stage-parallel execution** (§3.5): "every pipeline rank is assigned one denoising stage and maintains an independent video–audio KV cache… Tasks satisfying b+k=d therefore form an anti-diagonal wavefront… the final stage continuously retires clean blocks."
  - With 3 denoising steps this means 3 stages, which gives the 3 GPUs.
  - The text says "the prefix consists of the initial reference sink and up to recent blocks". **The number is missing from both the HTML and the PDF.** §4.1 says "at most two".
- **Block size.** The paper never gives frames per block. The code gives it: 3 latent frames = 24 px frames ≈ 1 s per block (the first block is 4 latents), 5 blocks per ~5 s window (TM `taomate/inference/runtime.py:46-53`).
- **Prompt format.** "every prompt specifies the action, transcript, subject appearance, scene, camera, and voice for one short segment. The subject, scene, camera, and voice descriptions remain consistent across the sequence, while the action and spoken content evolve" (§4.1).
  - Speech is generated jointly from the transcript in the prompt. There is no audio input or TTS (§3.1: "autoregressive audio-video generation from a temporally ordered sequence of text prompts").
- **Throughput and latency:**
  - Single device (RTX PRO 5000 72GB): "130.3±1.3 seconds per 1,441-frame output… 11.1 generated frames per second" (§4.1).
  - DiT FPS: 16.32 (Table 1).
  - Stage-parallel: "TaoMate reaches 35.0 output FPS on three GPUs… the complete 1,441-frame generation pipeline finishes in approximately 41.2 seconds" (§4.3, Table 2).
  - **The GPU type for the 35 FPS result is not stated.** Table 2 is headed "Multi-GPU end-to-end inference throughput". Latency to first frame is not reported.
- **Metrics** (Table 1, 768×512, 60 s Mandarin and English single-presenter scripts):
  - TaoMate: LipSync 5.918, Desync 0.000, Align 5.00, Express 4.00, Long Consistency 0.9755, Color Δ 0.00260, DiT FPS 16.32.
  - Best baselines: LiveAvatar 5.396 / 0.9619 / 0.00541 / 4.529 FPS; OmniForcing 1.590 / 0.3404 / 0.02060 / 8.14.
  - Metrics come from VABench. Color Δ and Long Consistency definitions are "in the supplementary", which is not public.
  - **The project page shows different TaoMate numbers:** LipSync 5.773, Long Consistency 0.9520, Color Δ 0.00483.
- **Ablation** (Table 3; Long Cons. / Color Δ / Face Cons.):

  | Configuration | Long Cons. | Color Δ | Face Cons. |
  |---|---|---|---|
  | No memory | 0.9614 | 0.00380 | 0.9955 |
  | + memory | 0.9653 | 0.00316 | 0.9956 |
  | + FiLM | 0.9620 | 0.00347 | 0.9947 |
  | + gate | 0.9676 | 0.00276 | 0.9962 |

  These are small effects. The memory mostly stabilizes colour, not identity.
- **Longest duration:**
  - Fig. 1: "remains stable over 1,000 seconds".
  - Project page: ">30 min uninterrupted single generation" (a 30-minute narration demo).
  - The evaluation itself uses 60 s.
- **Limitations.** The paper has **no limitations section**. Limitations I infer:
  - The anchor is the first generated block, so there is no user-supplied identity.
  - There is no voice reference.
  - Validation covers single-presenter, static-camera scripts only.
  - The benchmark and the supplementary material are not public.

---

## 2. TaoMate-H3 code (commit 6b2f998)

### Entry point and CLI
- `python -m taomate_h3` → `cli.main`. Arguments, all required unless a default is given:
  - `--prompt` or `--prompt-json`, mutually exclusive (cli.py:29-44)
  - `--duration`, a multiple of 5
  - `--resolution`, default 768x1376; short edge 480, 768 or 1088
  - `--gpus {4,8}` (cli.py:52)
  - `--devices`, `--model-root`, `--adapter`, `--seed` (default 8301), `--output`
- **Prompt JSON schema:** `{"prompts": [str,...], "seeds": [int,...]?}`. You need exactly one prompt per 5 s (config.py:80-134).
- The example prompts follow MiniMax H3's own "integrated_multimodal_description / overall_soundscape / non_diegetic_music" format. Speech goes inline as `<d>[Chinese] …</d>` (examples/prompts_10s.json).
- **Process flow** (cli.py:219-229):
  1. A torchrun job (`taomate_h3.teacher`) generates **audio guidance** for **all** prompts into a directory under `/dev/shm`.
  2. A second torchrun job (`taomate_h3.worker` → `runner.run_direct`) generates the video.

### Block and chunk structure
- A **request** is 5 s (`DirectPolicy.request_seconds=5`, config.py:22). Each request is split into **4 chunks** with `chunk_group_counts=(2,2,2,1)` groups of 17 frames (config.py:23; streaming/geometry.py:173-200).
  - **Request 0:** 39 + 34 + 34 + 17 = 124 native frames. That is 12 + 10 + 10 + 5 = 37 video latents; the first chunk carries a 5-frame / 2-latent prefix.
  - **Later requests:** 119 frames (35 latents) (geometry.py:30-84).
  - Audio latents are 40 Hz (geometry.py:9). A request has 207 audio latents, or 198/199 in steady state.
- **Published timing.** Native frames (124 + 119·(n−1)) are time-compressed to exactly 24 fps × duration by ffmpeg `setpts` and `atempo` (inference/media_timing.py:8-41; runner.py:158-235).
  - For 10 s this means 243 native frames become 240 published frames, a warp of about 1.2%.
- **3-step schedule.** The 50-point shifted ladder is sampled at `DISTILLED_STATE_INDICES=(0,16,33,49)` (denoise_schedule.py:7), with shift 12 for video and 3 for audio (model/pipeline.py:394-403).
  - Computed sigmas: video [1, 0.9612, 0.8533, 0]; audio [1, 0.8609, 0.5926, 0].
  - Each step is a single positive branch with **no CFG** (model/denoise.py:271-351).
  - Each chunk gets 3 noisy forwards plus 1 clean (σ=0) forward that commits KV (streaming/runtime.py:663-702).
  - The README's "24 generation forwards and eight clean-KV updates" for 10 s matches: 2 requests × 4 chunks.

### State that carries across chunks and requests (what is actually implemented)
- **`CleanAVKVCache`** holds dense BF16 K/V for the 50 main layers and **only clean media tokens** (streaming/cache.py:77-204). Text is not cached.
  - The retention rule is `retain_sink_and_recent_commits`: once 3 or more chunks exist, **chunk 0 of the whole session is kept as a video-only sink** and the **2 most recent chunks** keep full A/V (cache.py:206-219; called at runtime.py:714).
  - Policy strings: `video_kv_retention="first_video_sink_plus_recent_2_chunks"` (config.py:27).
- **Audio KV reset.** Audio history is dropped every 12 requests, i.e. every 60 s (config.py:29; runtime.py:584-588).
- **Prefix renormalization.** Each clean chunk's video latents get a per-channel affine fix to the mean/std of the **first chunk** (runtime.py:451-462, 675-678; `prefix_normalization="affine_to_first_stream_chunk"`).
  - This is the only anchor-like statistic. It is parameter-free.
- **Attention hook.**
  - Media queries attend to [current text/condition K/V] + [persistent clean A/V K/V] + [current media K/V].
  - Condition queries attend only to the condition (streaming/attention_hook.py:179-216).
  - It uses dense FA3 with `causal=False`.
- **RoPE is global and absolute.**
  - Video and audio positions continue on one timeline (runtime.py:209-234).
  - The current prompt's text positions are right-aligned just before the request's media origin (runtime.py:155-163).
  - There is no local restart.
  - The sink keeps its original positions. K is cached after RoPE, because RoPE is applied before the hook (model/layers.py:400-430).
- **Not implemented in H3:** anchor/memory tokens, MemAttn, FiLM, the gated EMA, and stage-parallel execution. grep finds no memory module anywhere in `src/`.
  - **TaoMate-H3 is "sink + 2-recent rolling clean KV + first-chunk colour renorm".**

### Audio: it is **not** generated by the streaming student
- `teacher.py` loads **base MiniMax H3 FL2VA in BF16 without the LoRA** (`transformer_load_w8a8_policy=None`, teacher.py:420-427).
- It runs a **10-state, 9-forward audio-only** denoise per 5 s request, with an empty video (teacher.py:352-381).
  - From request 1 onwards it conditions on the **previous request's last 40 audio latents (1 s)** as a frozen prefix (`tail40_rollover`, teacher.py:255-273, 295-300, 333-343).
  - It saves the milestones at states (3, 6, 9) to `request_XX.pt` (teacher.py:461-472).
- The streaming student then **overwrites its audio rows** with those milestones after each of its 3 steps (runtime.py:339-359, 657-673).
  - It **asserts the published audio equals the teacher's clean latent** (runtime.py:739-743).
  - Milestones are validated against the prompt text and seed (inference/base10_teacher.py:158-179).
- **Consequence.** Speech and voice come from base H3 audio-only generation. The 3-step student produces video conditioned on that audio through joint attention. This is the README's "integrated audio guidance".
  - The README says the benchmark "excludes the command's internal audio preparation", so the teacher pass is **not in** the 17.29 s first-playable number.

### Mid-stream prompt injection: none today
- **There is no server, queue, socket or callback.** grep for queue, socket, asyncio and http finds nothing.
- All prompts are fixed up front in three places:
  1. **Text encoding.** `runtime.precompute_text_prompts(config.prompts)` encodes every prompt, then offloads the Qwen3-VL text encoder to CPU (runner.py:293; runtime/direct.py:239-262; model/pipeline.py:101-104).
  2. **Audio teacher.** It is precomputed for all prompts in a separate process before the worker starts (cli.py:223-229).
  3. **The loop where the next prompt is consumed** is `runner.py:299-323`:
     ```python
     for request_index, (text_features, request_seed) in enumerate(zip(precomputed, config.request_seeds, strict=True)):
         ... runtime.generate_latents(..., precomputed_text=text_features, denoise_loop=streaming.run)
     ```
     Inside it, `H3StreamingRuntime.run` (streaming/runtime.py:482-834) builds each chunk's branch from the same `positive` at runtime.py:609-621.
- **Chunk-level prompt swaps are structurally possible,** because the text is not cached in the KV and the branch is rebuilt per chunk. But the audio milestones are per 5 s request, so a **practical** change can only happen at a 5 s request boundary unless the teacher is also chunked.
- **How hard is it to add an injection API? Moderate.** Required changes:
  - (a) Replace the `for` loop with a blocking pop from a rank-0 queue, then `broadcast_object_list` to all 8 ranks. The pattern already exists in `runtime.broadcast`.
  - (b) Keep the text encoder resident, or encode on another device, instead of `_offload_text`. Encode each new prompt when it arrives.
  - (c) Make the audio teacher incremental and resident. It needs its own BF16 base-model copy and the previous 40-latent tail. It must run one request ahead of the student, which is also where the lookahead latency comes from.
  - (d) Drop the assertions that tie prompt, seed and index to a precomputed list (base10_teacher.py:177; runner.py:134-150).
  - (e) Stream output per request or per chunk instead of `_publish` (see below).
  - `H3StreamingRuntime` already holds all cross-request state (`_cache`, offsets, transport rows), so it can be reused unchanged.

### Output
- **Publication is one-shot.** All latents are concatenated, then one video VAE decode, one audio VAE decode on rank 0, one H.264+AAC mux, and a strict ffprobe/decode check (runner.py:124-263, 327-334).
- **There is no chunk streaming output in the repo.**
- The "first playable video" row in the README comes from a "matched first-chunk publication benchmark" that is **not included** in the code.
- **Timing instrumentation that does exist:**
  - CUDA events around each noisy and clean DiT forward (runtime.py:644-653, 696-702; `dit_timing_receipt` 464-480).
  - Wall timers for model load, adapter load, text precompute, stage3 generation, decode and publish.
  - Everything is written to `result.json` and `latent_streaming.json` (runner.py:335-373).

### Parallelism and kernels
- Parallel layout is **TP2 × Ulysses{2,4}** for 4 or 8 GPUs, single node (config.py:151-182; runtime/direct.py:169-189). Both the teacher and the student use the same layout (teacher.py:188-212).
- **Precision:** BF16, plus **INT8 W8A8** on interior `qkv` and `fc1` through vLLM's `cutlass_scaled_mm` / `scaled_int8_quant` (config.py:24; inference/w8a8.py; cli.py:131-146). There is **no fp8**.
- The LoRA stays **unmerged**, as BF16 side buffers with a fused row-reduce (inference/lora_checkpoint.py:172ff, 261-311; acceleration.py:39-40). It targets `qkv_proj`, `out_proj`, `fc1` and `fc2` on 2 refiner blocks + 50 main blocks (lora_checkpoint.py:13-26).
- **Hard SM90 dependency.** FlashAttention-3 (`flash_attn_interface`, built from `flash-attention/hopper`) is used by the streaming hook, which refuses any other backend (attention_hook.py:43-48; layers.py:39-48; cli.py:130,145-146; config.py:25).
- Other kernels: Triton fusions with inline PTX (sm89-compatible PTX ops). The bit-exact video-VAE kernels are gated to capability {90, 100, 103} and fall back on other GPUs (inference/fused_kernels.py:858-870).
- **What fails on sm89 (our L20X)?**
  - FA3 does not run on SM 8.9; vLLM falls back to FA2 there (web sources; not tested here). The FA3 import or kernel launch would fail, and `cli._validate_acceleration_runtime` / `H3StreamingAttentionHook` raise.
  - The fix is small in principle: the hook is plain non-causal dense attention over concatenated K/V, so FA2's `flash_attn_func` or SDPA is a drop-in replacement, applied in both `attention_hook.py` and `layers.py`.
  - vLLM's int8 CUTLASS kernels have sm89 variants (believed; unverified).
  - Performance on L20X is unknown.
  - Memory: peak DiT 31.37 GiB per GPU at 480p (README), and each L20X has 141 GB.

### Inputs
- T2AV only. There is no reference image, first frame or voice reference. The README says "TaoMate-H3 FL2AV … will be released before 26/10/15; Ref2AV TBD".
- Voice is controlled only through prompt text; the example uses "clear, practical, medium-paced Mandarin voice".

### Measured and claimed latency (README; 8×H20, TP2×Ulysses4, 480×864, 10 s, seed 8301)

| Metric | Value |
|---|---|
| Pure DiT time | 14.810 s (vs 169.57 s for base H3) |
| First final chunk latent | 6.148 s |
| First playable (includes VAE decode and H.264 of the first chunk, excludes audio preparation) | 17.287 s |
| Peak DiT memory | 31.37 GiB |

- Derived: 240 frames / 14.81 s = **16.2 DiT FPS, which is 0.68× real time**. The validated setup is **slower than real time** even before VAE, text encoding and the audio teacher.
- 32 forwards in 14.81 s is about 0.46 s per forward.

### License
- TaoMate-H3 is under the **MiniMax H3 Community License**. Its Excluded Territories are the EU, UK, Republic of Korea and USA (LICENSE §I.5).
- A NOTICE file records the modifications.
- TaoMate (LTX) is under **Apache-2.0**, but its weights inherit the LTX-2.3, Gemma and other licenses.

---

## 3. TaoMate (LTX-2.3) repo: useful because it has the only interactive loop

Summarized from a code sweep. The key constants and the RoPE comment were re-checked by hand.

- **Granularity.**
  - A window is 121 frames = 16 latents, split into 5 blocks (4+3+3+3+3). Later windows are 15 latents.
  - A block is 3 latents, which is 24 frames or about 1 s. There are at most 12 windows (TM `taomate/inference/runtime.py:46-53`; `streaming_runtime.py:63-70`).
  - Steps are `DENOISING_STEPS=(1000,757,522,0)` snapped to the LTX2 40-step schedule (`taomate/inference/model.py:11-19`).
- **Memory is implemented** in `taomate/runtime_support/learned_memory.py`, matching the paper:
  - EMA plus anchor tether, and the drift gate (lines 149-166, 231-248).
  - Colour and FiLM statistics (430-505).
  - MemAttn every 4th layer (`ltx_causal/transformer/causal_model.py:341-352`).
  - Updates only after the σ=0 commit (`streaming_runtime.py:3506-3507`).
  - The anchor is block 0 (`learned_memory.py:361-367`).
- **KV.** Sink block 0 + 2 recent clean blocks (`taomate/inference/cache.py:58-67`).
  - The persistent cache commits at absolute runtime positions (`streaming_runtime.py:3535-3541` comment). A restart of the local-window RoPE seems to apply only to the window buffer. **Whether this matches the paper's "local RoPE restart" is unverified.**
- **Parallelism in code is 2-rank tensor parallel.** The demo uses 4 GPUs: DiT TP on 0-1; text encoder and VAE on 2; llama-server and Whisper on 3.
  - **No stage-parallel (3-GPU, 35 FPS) code is in the repo.** It uses flex_attention and SDPA with **no FA3**, so it could run on sm89.
- **Interactive demo** (`apps/interactive_avatar/`): FastAPI + SSE, per-block fragmented MP4 over MSE, playback starting after 2 segments are buffered.
  - Flow: user text → Gemma-4-26B-A4B (llama-server) → JSON `{speech, emotion, action, explicit_action}` → one templated prompt per reply → a `pending/<task>.json` file queue polled by the resident worker (`worker.py:82-176`).
  - Prompts are consumed per window at `streaming_runtime.py:4927-4932` (`conditional_dict = prompt_cache[seg_prompt]`).
  - Whisper-tiny transcribes the **avatar's own audio** to detect end of speech and write `asr_stop_control.json`. It is read after every block and rolls back surplus blocks (4751-4805, 5229-5296).
  - There is **no barge-in**: `cancel.requested` is written (`server.py:5763-5766`) but never read by the worker.
  - Continuity across turns is kept by saving and loading the prefix, KV and memory state (`streaming_runtime.py:4828-4890`).
  - When idle, the UI loops a muted clip. No filler generation runs.
- **This demo is the closest existing template for our agent.** It already shows turn-level (not mid-turn) prompt switching with persistent state across turns.

---

## 4. vLLM-Omni as a host for TaoMate-H3

Sweep result, with parts re-checked. Local HEAD is 7b4dc76; origin/main 3bd5ac9 adds only request-cancellation hooks to minimax_h3.

- **What exists in `vllm_omni/diffusion/models/minimax_h3/`:**
  - `lora.py`: LightX2V Turbo LoRA only. It requires a filename regex and Diffusers-PEFT keys.
  - `fasth3.py`: FastH3, a 4-step DMD2 fused at load.
  - `continuation.py`: Ref2VA windowed continuation that re-encodes a latent tail. It supports per-window prompts fixed ahead of time and has no KV.
  - `temporal_chunks.py` / `chunked_decode.py`: chunked **VAE decode** after full denoise.
  - `pipeline_minimax_h3.py`: pinned `base_schedule` sigma positions and the `audio_mode=lock_source` locked audio rows.
- **What does not exist:**
  - No TaoMate references.
  - No persistent KV in the H3 transformer.
  - No `SupportsInteractionApply` or `SupportsARDiffusionPipeline` implementation for H3. Only LingBot-World, Helios and DreamZero have them (verified by grep).
  - The `/v1/realtime/video` WebSocket (`session.interaction`) and `experimental/ar_diffusion` (sink+window paged KV) exist but cannot drive H3.
- **Missing pieces to serve TaoMate-H3 as a session:**
  1. A loader for TaoMate's native-key LoRA (`blocks.N.attn.qkv_proj.lora_a/b`, rank/alpha from its own config).
  2. A 3-step FL2VA schedule, (0,16,33,49) with shift 12/3.
  3. Persistent clean A/V KV with sink + 2 recent and a σ=0 commit pass, under Ulysses×TP.
  4. Chunk-level streaming with 39/34/34/17-frame chunks. These are off H3's 17n+5 decode grid, so decode needs a streaming VAE cache.
  5. `SupportsInteractionApply`, or the AR tick prompt path, for mid-stream prompts.
  6. A resident base-model audio teacher (a LoRA-off BF16 pass, 10 steps, 40-latent rollover) feeding locked audio rows.
  7. A parity test against the reference runtime.
- **Rough estimate:** porting to vLLM-Omni is much more work than adding a queue to the TaoMate-H3 runtime itself.

---

## 5. Implications for a live persona agent on TaoMate-H3

- **Control granularity.**
  - Effective: 5 s (one request). This is bound by the per-request audio teacher and the prompt/seed contract.
  - Structural minimum: one chunk (0.7–1.6 s), only if the teacher is re-engineered to be per-chunk.
- **Instruction-to-screen latency** is at least the time to finish the current request, plus the audio-teacher pass for the next request, plus the DiT time for its first chunk, plus VAE and mux.
  - On 8×H20 the DiT alone runs at 0.68× real time, so a queue builds without end. Real time needs faster GPUs or fewer tokens.
- **Memory and identity.** Only a first-chunk KV sink + 2-recent + colour renorm, with absolute RoPE.
  - There is no evidence of stability beyond the 60 s example. The audio KV reset every 60 s hints at drift.
  - Long-session identity would need the TaoMate learned-memory design, which is not ported to H3, or the upcoming FL2AV.
- **Barge-in.** Audio for a whole 5 s request is precomputed, so interruption means discarding the request. The TaoMate demo's rollback-after-block pattern could be adapted at chunk granularity.
- **Hardware.** Local L20X (sm89) cannot run the FA3 path as shipped. It needs an FA2/SDPA swap in 2 files and then fresh validation.

---

## Evidence table

| Claim | Evidence | Status |
|---|---|---|
| TaoMate: 22.1B, LTX-2.3 distilled init, 3 steps per block | paper §4.1, Table 1 | verified (paper) |
| 12 memory layers of 48; 48 video tokens (anchor + state), 64 audio; +97.8M params | paper §4.1 | verified (paper) |
| Memory EMA / anchor / gate hyperparameters | paper §4.1; TM learned_memory.py:149-166,231-248 | verified (paper + code sweep) |
| 35.0 FPS on 3 GPUs, 41.2 s for 1,441 frames; GPU type not stated | paper §4.3, Table 2 | verified (paper); GPU type unverified |
| 11.1 FPS single RTX PRO 5000 (130.3 s / 1,441 frames); DiT FPS 16.32 | paper §4.1, Table 1 | verified (paper) |
| Stage-parallel code is in the TaoMate repo | TM sweep: only TP2 code found | **not found** |
| Paper metrics vs project page differ (5.918 vs 5.773 LipSync, etc.) | paper Table 1; project page | verified |
| >30 min single generation | project page | claimed, unverified |
| Prefix size in §3.5 is missing ("up to recent blocks") | arXiv HTML + PDF | verified (typo) |
| Local RoPE restart per segment | paper §4.1; TM code uses absolute positions for the persistent cache | contradicted/unclear |
| TM block = 3 latents ≈ 1 s; window = 5 blocks ≈ 5 s | TM runtime.py:46-53 | verified |
| TM demo: file queue, per-window prompt, no barge-in, MSE fMP4 per block | TM worker.py:82-176; streaming_runtime.py:4927-4932; server.py:5763-5766 | verified (sweep + spot check) |
| H3: one prompt per 5 s; JSON `{"prompts":[..],"seeds":[..]}` | H3 config.py:80-134 | verified |
| H3: 4 chunks per request (2,2,2,1)×17 frames; request 0 = 124 frames | H3 config.py:23; streaming/geometry.py:173-200 | verified |
| H3: 3-step sigmas at indices (0,16,33,49), shift 12/3, no CFG | H3 denoise_schedule.py:7; model/pipeline.py:394-403 | verified |
| H3 KV: first-chunk video sink + 2 recent AV chunks; text not cached | H3 streaming/cache.py:206-219; attention_hook.py:179-216 | verified |
| H3 audio KV dropped every 12 requests | H3 config.py:29; streaming/runtime.py:584-588 | verified |
| H3 has no learned memory / anchor tokens / FiLM | grep of H3 src | verified (absence) |
| H3 audio = base-H3 10-step audio-only teacher, 40-latent rollover; student audio overwritten and asserted equal | H3 teacher.py:255-381; streaming/runtime.py:339-359,739-743 | verified |
| H3 prompts consumed at runner.py:299; text precomputed and encoder offloaded | H3 runner.py:293-323; model/pipeline.py:101-104 | verified |
| No server/queue/socket in H3 | grep | verified (absence) |
| H3 output is one-shot MP4 at end | H3 runner.py:124-263 | verified |
| FA3 required; hook rejects other backends | H3 attention_hook.py:43-48; cli.py:130-146 | verified |
| INT8 W8A8 (not fp8) via vLLM CUTLASS | H3 inference/w8a8.py; acceleration.py | verified |
| FA3 unsupported on SM 8.9 | web (vLLM/FA issue summaries) | unverified locally |
| Local GPUs are L20X, cc 8.9 | `nvidia-smi` | verified |
| DiT 14.81 s, first chunk latent 6.148 s, first playable 17.29 s, 31.37 GiB (8×H20, 480p, 10 s) | H3 README | claimed; not reproduced |
| First-playable excludes audio teacher | H3 README ("excludes the command's internal audio preparation") | verified (text) |
| FL2AV before 2026-10-15; Ref2AV TBD | H3 README | claimed |
| LoRA rank 128 / alpha 128, step 3000 EMA, native (non-PEFT) keys | HF config.json; H3 lora_checkpoint.py:13-26 | verified |
| vLLM-Omni H3: no persistent KV, no interaction or AR-session implementation, LoRA loader incompatible | VO minimax_h3/ (lora.py:38,103); grep of interfaces | verified (sweep + grep) |
| origin/main 3bd5ac9 adds only request cancellation to minimax_h3 | VO git diff (sweep) | verified (sweep) |
| H3 license excludes EU/UK/KR/US | H3 LICENSE §I.5 | verified |
