# Backbone Verification: LingBot-World 2.0 in vLLM-Omni

> Deliverable for goal.md §4. It is based on the audit in `docs/notes/backbone_lingbot_world_vllm_omni.md`
> (reproduced below), with the independent checks Claude made on 2026-09-25 listed first.
> Inspected implementation: upstream `vllm-project/vllm-omni` `main` @ `7b4dc7633bde8642f0c05f77bd018751541df404`
> (2026-09-24), a read-only clone at `external/vllm-omni`. No GPU job was run, so **every latency number here is
> upstream-reported (class B) or derived**, never measured locally.

## Clarifications after Codex CP2 (2026-09-25)

- **Scope of "camera-only".** This conclusion comes from reading the code, not from running it. It covers mid-session
  `session.interaction` messages on the public stepwise WS path. Other ways to steer the camera also exist:
  request-scoped `camera_action_script` / `action_path`, and prompt switching on the deprecated tick path (latent
  output). The upstream benchmark sends prompt updates, which contradicts the registry, so **one real WS prompt-update
  attempt is part of M0** before `interaction_failed` is treated as observed.
- **Event ack ≠ visible compliance.** The `started/active/completed_event_ids` fields in chunk metadata show when a
  control was *applied* to a chunk. They say nothing about whether the rendered content complies.
- **The "≈0.6–1.15 s" camera figure** in §0 and §8 below is a derived *earliest chunk-delivery estimate*. It is not
  time-to-visible-compliance, because it leaves out client playback queueing, the network and visual inertia. It also
  assumes the upstream PR #7749 stack on 4×H200 (compiled, streaming decoder, selective FP8, KV-skip; some options
  experimental).
- **Reclassifications.**
  - WS *rewind / snapshot / branch*: moved from C to "C/D, feasibility unknown". Snapshotting paged KV together with
    the streaming-decoder and encoder state has no existing design.
  - Class D now covers only **native** LingBot lip, face and audio conditioning. A speaking persona built from an
    external TTS plus an audio-driven avatar is engineering (C) *outside* the backbone.
- **Cancel vs redirect.** `session.stop` and disconnect cancel the rollout. What is missing is *redirecting* an
  in-flight chunk while keeping the session. A new control can only take effect at the next chunk boundary.

---

## Independent spot-checks (Claude, 2026-09-25)

| Claim from the audit | Check | Result |
|---|---|---|
| LingBot registers only the `camera` interaction modality | Read `vllm_omni/diffusion/interaction/registry.py:17-28` | Confirmed: `"LingBotWorldCausalDMDPipeline": {"camera": SE3DeltaCameraHandler}`. Only the Helios pipelines register `prompt` |
| An unsupported modality fails | Read `vllm_omni/diffusion/interaction/coordinator.py:59-65,107` | Confirmed: `get_handler` raises `ValueError("interaction modality ... is not supported")`. `enqueue_parts` resolves all handlers before enqueueing |
| The WS server returns `interaction_failed` | Read `vllm_omni/entrypoints/openai/serving_video_output_stream.py:461-477` | Confirmed: an exception from `submit_interaction_async` sends `code="interaction_failed"`. The ValueError propagating through `submit_interaction_async` to this handler was **not executed** |
| The upstream benchmark sends prompt updates | `benchmarks/lingbot_world/benchmark_lingbot_world_realtime.py:199-200` fires `workload.prompt_updates` | Confirmed that the code exists. It contradicts the registry. Unexecuted |
| Recipe facts (checkpoint, license, 480x832, `max_num_seqs=1`, single replica, no stateful streaming VAE in the tick example) | Read `recipes/Robbyant/LingBot-World-2.0.md` in full | Confirmed |
| Local GPU identity | `nvidia-smi --query-gpu=name,compute_cap,memory.total,power.limit` and `nvidia-smi -q` | NVML reports **"NVIDIA L20X", architecture "Ada Lovelace", compute capability 8.9**, device ID 0x26BA10DE, **143,771 MiB, 700 W**. The memory and power figures match an H200 SXM, and an upstream PR author says "L20X" is an H200 BIOS mislabel. The architecture and compute capability do not match H200 (9.0). **Identity unresolved.** It matters because kernel selection (FA3, FP8 paths) depends on the reported capability |
| Prior local runs of LingBot v2 on this hardware | Read-only look at `/data/zhoutaichang/feature/lingbot-world-v2-quality/logs/*.log` (official `generate.py`, 2026-09-11) | Those runs report `FA2 False FA3 False` (an SDPA fallback) and end in tracebacks. **No usable timing.** This is evidence that the software stack on this machine is not turnkey |

**Smallest experiment that resolves the latency question (M0 in the proposal):**
`gpu run --gpus 1 --timeout 1h --note "live-agent M0" -- vllm serve robbyant/lingbot-world-v2-14b-causal-fast-diffusers --omni --deploy-config vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`,
then `benchmarks/lingbot_world/benchmark_lingbot_world_realtime.py --num-chunks 16`. Repeat with 4 GPUs and
`benchmarks/lingbot_world/configs/usp4_compiled.yaml`. In the same reservation, record `torch.cuda.get_device_capability()`.

---


- Audit date: 2026-09-25. Read-only: no GPU jobs were run and no weights were downloaded.
- Repo: `/data/zhoutaichang/live-agent/external/vllm-omni`, upstream `main` @ `7b4dc7633bde8642f0c05f77bd018751541df404` (2026-09-24).
  All `path:line` references below are relative to this checkout and this commit.
- Classes: **A** = present in the code I inspected (read, not executed, unless noted). **B** = reported upstream
  (paper, model card, or PR body) but not checked locally. **C** = needs engineering work. **D** = needs new training or research.
- Where a finding comes only from reading the code and I did not run anything, it is marked *(code-read, not executed)*.

---

## 0. TL;DR for the live-agent proposal

LingBot-World 2.0 in vLLM-Omni is an **image-conditioned, camera-controlled world model**. It streams fragmented-MP4
chunks of 12 frames (9 for the first chunk) at 480x832. The only control you can change mid-session over the
public WebSocket is **structural SE(3) camera motion**.

- **Mid-session text prompt changes do not work on the public stepwise path.** The interaction registry registers
  only `camera` for `LingBotWorldCausalDMDPipeline` (`vllm_omni/diffusion/interaction/registry.py:25-27`). A
  `session.interaction` that carries `event.prompt` reaches `InteractionCoordinator.get_handler("prompt")`, which
  raises (`vllm_omni/diffusion/interaction/coordinator.py:59-65`). The WS server then answers with
  `interaction_failed` (`serving_video_output_stream.py:466-477`). Prompt switching exists only on the deprecated
  in-process "tick" path, and that path outputs latents only (`pipeline.py:1531-1535`).
- There is **no character, avatar, body, face, or lip control and no audio**. Upstream says character actions
  (attacking, archery, spell-casting) come from *chunk-wise text prompts* (arXiv 2607.07534). The vLLM-Omni stepwise
  server cannot express those today because it has no prompt interaction for this pipeline.
- **Memory is a sink plus a rolling window**, not long-term memory. The checkpoint config has `sink_size=9` and
  `sliding_window_num_frames=18` latent frames. That is the first 3 chunks plus the most recent 3 chunks
  (~36 px frames ≈ 2.25 s at 16 fps). The paper itself says regions that leave the window are "regenerated rather
  than recalled".
- **Performance on this machine class (reported by upstream PR authors, not measured by me):** on 4xH200 with
  Ulysses SP=4, compiled, 4 DMD steps, 480x832, the steady cadence is **~549 ms per 12-frame chunk**
  (≈21.9 frames/s produced) and time to first chunk (TTFC) is **~1.07 s** (PR #7749, 2026-09-24). On 2xH200 the
  cadence is ~892–896 ms per chunk. On 1 GPU, eager, it is ~3241 ms per chunk (PR #7645, older head).
- **Instruction-to-visible camera response is at least one chunk boundary away.** An event is applied at the next
  AR-block boundary, so the latency is about 1–2 chunk intervals plus transport and client buffer:
  ≈0.55–1.1 s on 4xH200 before buffering *(derived, not measured)*.

---

## 1. Checkpoints, pipeline classes, variants, hardware, parallelism

| Item | Value | Evidence |
|---|---|---|
| Supported checkpoint (only one) | `robbyant/lingbot-world-v2-14b-causal-fast-diffusers` | `recipes/Robbyant/LingBot-World-2.0.md:8,277`; `tests/e2e/online_serving/test_lingbot_world_v2_stepwise.py:33` |
| Pipeline class | `LingBotWorldCausalDMDPipeline` (nn.Module + SupportImageInput, SupportsStepExecution, InteractionMixin …) | `vllm_omni/diffusion/models/lingbot_world/pipeline.py:571-592` |
| Transformer class | `CausalLingBotWorldTransformer3DModel` | `.../lingbot_world/transformer.py:805-843` |
| Stage topology registration | `LINGBOT_WORLD_PIPELINE` (model_type `lingbot_world`, 1 diffusion stage, final output `video`, **no default deploy config**) | `vllm_omni/model_executor/models/lingbot_world/pipeline.py:1-37` |
| Pre/post-process hooks | `get_lingbot_world_pre_process_func`, `get_lingbot_world_post_process_func` | `vllm_omni/diffusion/registry.py:666,738`; `pipeline.py:395-568` |
| Variant supported | Only the **causal-fast (DMD-distilled)** variant, pinned to 4 steps with timesteps (1000, 750, 500, 250); any other step count is rejected | `pipeline.py:111`, `pipeline.py:1007-1014` |
| Variants not supported | causal-pretrain, bidirectional, 1.3B, Cache-DiT, TeaCache, SP other than Ulysses, PP/CFG/VAE-parallel, HSDP | `recipes/.../LingBot-World-2.0.md:277,290-292`; `pipeline.py:245-280` |
| Architecture (local checkpoint config) | 40 layers, 40 heads x 128, ffn 13824, in_ch 36 (= 16 noise + 4 mask + 16 image latents), out 16, patch (1,2,2), text_dim 4096 (UMT5), `sink_size 9`, `num_frames_per_block 3`, `sliding_window_num_frames 18`, `local_attn_size -1` | `/data/models/hub/models--robbyant--lingbot-world-v2-14b-causal-fast-diffusers/snapshots/59cccf49…/transformer/config.json` |
| Official README uses a different sink | Official `generate.py` example passes `--local_attn_size 18 --sink_size 6` (vs 9 in the diffusers config) | same snapshot `README.md` (Inference section). Consequence not verified. |
| Execution modes | (a) offline request mode (whole trajectory → MP4); (b) **stepwise streaming** (one request = whole rollout, 1 chunk per AR block); (c) deprecated "tick" mode (1 block per `generate()`, latent output) | `recipes/.../LingBot-World-2.0.md:17-32` |
| Deploy config for streaming | `vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`: 1 stage, `devices "0"`, `max_num_seqs 1`, `enforce_eager true`, `engine_backend ARDiffusionEngine`, `step_execution/streaming_output true`, `ar_diffusion_height 480`/`width 832`, `gpu_memory_fraction 0.6`, `warmup_cudagraph true` | `vllm_omni/deploy/lingbot_world_v2_stepwise.yaml:10-44` |
| Realtime topology | `benchmarks/lingbot_world/configs/usp4_compiled.yaml`: 4 GPUs, Ulysses SP=4, TP=1, `enforce_eager false` | `benchmarks/lingbot_world/README.md:47-69` |
| Parallelism accepted | pure Ulysses (`sequence_parallel_size == ulysses_degree`, ring=allgather=1, `ulysses_mode="strict"`, no a2a permute); TP=1/2 validated; online FP8 linears (experimental) | `pipeline.py:245-280`; recipe `:218-255,259-269` |
| Hardware validated (recipe) | NVIDIA H200 and B200; no AMD, Ascend, or Intel support is claimed | recipe `:11,292` |
| Resolution cap | `height*width <= 480*832`, divisible by 16; the served resolution must equal the load-time `ar_diffusion_height/width` | `pipeline.py:114,1000-1005,1880-1884` |
| Concurrency | `max_num_seqs` must be 1; a single replica only (no session-affine routing); KV spec `session_capacity=2` resident sessions | `docs/design/feature/realtime_ar_diffusion.md:161-176`; `pipeline.py:784` |
| License | Checkpoint: **CC BY-NC-SA 4.0 (non-commercial)**. vLLM-Omni integration: Apache-2.0 | recipe `:14-15`; local model card front-matter `license: cc-by-nc-sa-4.0` |

**Local weights (read-only listing, nothing downloaded):**

- `/data/models/hub/models--robbyant--lingbot-world-v2-14b-causal-fast-diffusers` is a complete snapshot
  `59cccf49…`, 81 GB (transformer 8 shards, UMT5 text encoder, Wan VAE).
- `/data/models/lingbot-world-v2-1.3b-causal-fast-diffusers` (18 GB) and `/data/models/lingbot-world-v2-1.3b-causal-fast`
  (6.4 GB). vLLM-Omni does not claim support for the 1.3B model.
- `/data/models/hub/models--robbyant--lingbot-world-fast-diffusers` (81 GB) is the v1 LingBot-World-Fast
  (Apache-2.0), which vLLM-Omni does not use.
- The `models--robbyant--lingbot-world-v2-14b-causal-fast` hub dir contains only refs (1.5 KB), not weights.
- Access: the shared `/data/models` belongs to the machine, not to `/data/zhoutaichang`. Confirm you may use it.

**Machine GPUs** (`nvidia-smi --query-gpu=name,memory.total`): 8 x "NVIDIA L20X", 143771 MiB each. PR #7749's author
says that on their node this NVML string is a BIOS mislabel of **H200**, and PR #7645 reports the same string. That
PR was probably measured on this machine or a sibling. **I have not verified which GPU these cards are.**

## 2. Inputs and conditioning (formats and where they are parsed)

| Input | Format | Where parsed |
|---|---|---|
| First frame (required) | Exactly one image: PIL, tensor `[3,H,W]`/`[1,3,H,W]`, or path, ≤ 4096x4096 source px. WS: `image_reference` (`http(s)` or `data:` URL) | `pipeline.py:403-429` (pre-process), `:922-930`, `:957-970`; WS `serving_video_output_stream.py:558-560,609-626` |
| Image usage | VAE-encoded **only at chunk 0**. Later blocks feed zero pixel frames to a stateful causal encoder, and once the encoder reaches a fixed point it stops running. You **cannot re-condition on a new image mid-session.** | `pipeline.py:1139-1181,1218-1232` |
| Text prompt | Non-empty string, UMT5, `max_sequence_length` must be exactly 512, LRU cache of 4 encodes; cross-attn K/V cached per session | `pipeline.py:115-119,917-918,1033-1039,1465-1508,1334-1376` |
| Negative prompt | Rejected on `session.interaction`; start-time negative prompt is passed through but LingBot is CFG-free (4-step DMD) *(code-read)* | `serving_video_output_stream.py:401-407,553-554` |
| Camera trajectory (offline / `action_path`) | Directory with `poses.npy` `[F,4,4]` (C2W) and `intrinsics.npy` `[F,4]` (fx,fy,cx,cy at an 832x480 reference), 1..4096 frames. Served only from a trusted root (`model_config.lingbot_action_root` / `VLLM_OMNI_LINGBOT_ACTION_ROOT`) | `camera.py:22,46-84,165-228`; `pipeline.py:489-519` |
| Camera action script (request-scoped) | `extra_params.camera_action_script`: list with one entry per chunk, each entry `[[keys],[keys],[keys]]` (3 latent frames), keys from `w a s d i j k l` | `actions.py:26-31,94-117`; `pipeline.py:479-487,1887-1891` |
| Keys → pose | Integrated in fp64: move 0.05 per latent frame, pitch 4°, yaw 6°, pitch clamp 85°, focal 500 px (the SGLang adapter constants) | `actions.py:275-339` |
| Mid-session camera (public) | `session.interaction` → `event.multi_modal_data.camera = {mode: "target"|"velocity", data: {translation:[x,y,z], rotation:[qx,qy,qz,qw]}}`, Unity frame (+X right, +Y up, +Z forward). `data.actions` (WASD) is rejected | `interaction/modality_handlers/camera.py:104-195,390-393`; `docs/serving/streaming_video_output_api.md:86-113` |
| Camera → model | Poses become first-relative framewise deltas, then a 6-ch Plücker embedding `[origin_xyz, dir_xyz]`, pixel-unshuffled x8 to the latent grid (`6*8*8` channels), then patch embed and per-layer `cam_injector` modulation | `camera.py:392-493`; `pipeline.py:537-543,1255-1332`; `transformer.py:587-614,905-924` |
| Tick-path controls (deprecated) | Opaque `ARDiffusionControlInput(track, schema, data)` with schemas `lingbot.camera_actions.v1` (3 frames of keys) / `lingbot.camera_trajectory.v1` | `pipeline.py:434-478`; recipe `:209-214` |
| Other | `flow_shift` (default 5.0), `seed`, `fps` (MP4 label only; the checkpoint declares no fps) | `pipeline.py:952-955`; `benchmarks/lingbot_world/README.md:90-111` |

## 3. Can prompt / camera / actions change mid-session?

| Control | Public stepwise WS path | Deprecated tick path | Evidence |
|---|---|---|---|
| Camera (SE3 target/velocity) | **Yes (A)**. Queued, then applied at the next chunk boundary. Velocity is held until replaced. Target lerps over `transition_chunks` (default 1). Events map to latent frames by arrival time within the chunk | Yes (keys or trajectory per tick) | `camera.py:197-359`; `diffusion_model_runner.py:1427-1431`; `pipeline.py:1998-2032` |
| Camera script + live interaction | **Mutually exclusive.** If `camera_action_script` or `action_path` was given, any live camera event raises | n/a | `pipeline.py:1956-1962,1985-1991` |
| Text prompt | **No (C).** `prompt` is not registered for LingBot, so `get_handler` raises and the server reports `interaction_failed`. The pipeline also encodes the prompt once in `prepare_encode` and calls `_ar_text_caches(..., invalidate=False)` for every chunk, so registering `PromptInteractionHandler` alone would not refresh cross-attn K/V *(code-read, not executed)* | **Yes (A, latent-only)**. `ar_diffusion_tick.prompt` is re-encoded (LRU-cached) and session text K/V is invalidated when the prompt key changes | `registry.py:17-28`; `coordinator.py:59-65,107`; `pipeline.py:1893-1897,1935,2053-2056`; tick: `pipeline.py:1437-1463,1538,1570-1574,1623-1628` |
| Upstream benchmark sends prompt updates | `benchmarks/lingbot_world/workload.py:145-165` builds `session.interaction` with `event.prompt`; by the analysis above this would fail for LingBot. **This contradicts the registry and has not been run.** | – | `benchmarks/lingbot_world/README.md:164-192` |
| Image / reference | No | No | `pipeline.py:1166-1172` |
| Character actions / events | **Not exposed.** Upstream implements them as chunk-wise captions (needs prompt switching). Space (jump) / P (glide) / U/O/F/G event keys from the paper are not in vLLM-Omni's key set | – | `actions.py:29`; arXiv 2607.07534 |

Is the prompt re-encoded per chunk? On the tick path, `encode_prompt` is called on every tick but hits the
4-entry cache, and text K/V is rebuilt only when the (prompt, len, dtype) key changes (`pipeline.py:1455-1463`).
On the stepwise path the prompt is encoded once per request (`pipeline.py:1893`).

## 4. Streaming mechanics

| Aspect | Value | Evidence |
|---|---|---|
| AR block | 3 latent frames; 4 DMD probe forwards + 1 clean-KV commit forward per block (last-step KV reuse is experimental and skips the commit) | `transformer.py:841`; `pipeline.py:2078-2153`; `dmd_block.py`; recipe `:56-74` |
| Pixel frames per chunk | Chunk 0 = 9 frames. Later chunks = 12 frames with the session-owned streaming Wan decoder. Without it, every chunk is 9 frames with seams | `pipeline.py:2186-2197,1806-1840` |
| num_frames constraint | `(num_frames-1) % 4 == 0` and latent frames % 3 == 0, i.e. `9 + 12k`. Chunks = `((num_frames-1)//4+1)//3` | `pipeline.py:1016-1031`; recipe `:49-54,152-154` |
| Session length | Fixed up front by `num_frames` in `session.start` (`total_chunks` at `pipeline.py:1886,1922`). There is **no API to extend** a session. No hard cap in code (`num_frames` ≤ int64; temporal RoPE extended on the fly `transformer.py:1091-1099`, PR #6838; KV metadata bounded PR #7498). Longest upstream-validated run in PRs: 40 chunks (477 frames) | `protocol/videos.py:162`; PR #7645 |
| KV cache | Runner-owned paged AR-Diffusion KV (`ar_diffusion_kv`, not the generic `paged_scheduler`); chunk-window eviction with protected sink | `experimental/ar_diffusion/kv_cache/config.py:34-61`, `manager.py:208-331,620`; `docs/design/feature/diffusion_paged_kv_cache.md:153-156,295` |
| Window | Sink 9 latent frames (first 3 chunks) + recent 9 latent frames (3 chunks). The key count grows until chunk 6 | `pipeline.py:748-782`; `benchmarks/lingbot_world/README.md:113-124` |
| Memory accounting | `required = scratch + pages + cross-attn + model-owned state` (condition, camera modulation, 2x encoder histories, streaming decoder ≈1801 MiB at 832x480 bf16). Upstream reports a two-session KV requirement of 57.1 GiB (PR #5491, H200) | `pipeline.py:85-92,794-800`; design doc `:111-159` |
| Scheduling | Stepwise: the scheduler groups a block's steps into one runner call (`supports_chunk_step_grouping`). Interactions are applied only at chunk boundaries | `pipeline.py:582-585`; `experimental/ar_diffusion/runner.py:346-430`; PR #7648 |
| Session state | `session_id == request_id` on the stepwise path. State: paged KV, text K/V, encoder cache, camera tail/pitch, streaming decoder cache | `pipeline.py:173-193,1936,2141-2177`; `runner.py:294-310` |

## 5. Interrupt, cancel, reset, resume

| Operation | Stepwise WS (public) | Tick / Python API | Evidence |
|---|---|---|---|
| Cancel | `session.stop` → `engine.abort(request_id)` → session done `stopped:true`. A client disconnect also aborts. Stall timeout 60 s, start timeout 10 s | – | `serving_video_output_stream.py:71-75,168-171,273-281,307-310` |
| KV release on cancel | Scheduler-finished/aborted request ids close the session KV | – | `runner.py:294-310` |
| Reset (restart at chunk 0) | **Not exposed** over WS (C) | `ARDiffusionSession.reset()` / `ARDiffusionSessionManager.reset_session()`; runner `reset_session`; `extra_args["reset"]` | `experimental/ar_diffusion/session.py:468-516,565-576`; `runner.py:49-58,228-234`; `pipeline.py:885-891` |
| Failure semantics | Forward exception → session KV released (fail-closed); no retry of the same chunk; tick sessions go to FAILED and need reset/close | same | `runner.py:258-292`; design doc `:80-109` |
| Resume / rewind / branch / checkpoint | **None** (C). No KV snapshot, rewind, or fork API | none | design doc non-goals `:211-222` |
| Eviction | LRU across resident sessions (capacity from memory, cap 2) | same | `runner.py:236-246` |
| Pause | None. The client can only stop pulling, which triggers the stall timeout | – | – |

## 6. What controls camera, what controls character, what controls scene

- **Camera / ego-viewpoint**: WASD/IJKL/SE3 only change the *camera trajectory* embedded as Plücker rays
  (`camera.py:425-493`). The code has no notion of a subject. The PR #7198 test prompt shows how a third-person
  character is produced *via text only* ("Third-person view from behind the officer … look-input is the only
  camera motion"), so any apparent character locomotion is the model's interpretation of camera motion plus the
  prompt. It is not a separate control.
- **Scene content**: Set by the first-frame image and the text prompt at start. On the public path it is fixed for
  the session, because the prompt cannot change (see §3).
- **Character / avatar / body / face / lips**: **No control of any kind** in the vLLM-Omni integration
  (verified: no such inputs in `_parse_request` `pipeline.py:893-1055`; the registry has only camera). Upstream
  (arXiv 2607.07534) claims character actions (combat, archery, spell-casting, shooting), jump/glide keys, and a
  "pilot agent" that plans character behavior. The actions go through **chunk-wise prompts**, and there is no
  identity or face control → B for game-style actions, **D for a persona avatar** (identity-preserving face, lip,
  and gesture control).

## 7. Audio

None. The pipeline outputs video frames and latents only (`pipeline.py:2159-2173`). The WS encoder produces an m4s
fMP4 video stream (`serving_video_output_stream.py:504-509`). No audio is mentioned in the LingBot-World or
LingBot-World 2.0 model cards, or in the upstream paper summaries I fetched. Speech and lip-sync would need a
separate TTS model plus a new audio-conditioned video model or adapter → **D**.

## 8. Latency, throughput, memory

All numbers below were **reported by upstream authors** in PR bodies or docs. **I measured none of them.**
The chunk length is 12 frames, and the RTF basis must be stated.

| Setup | TTFC | Steady per-chunk | Source (date) |
|---|---|---|---|
| 1 GPU ("L20X"=H200?), eager, stepwise WS | 2712–2726 ms | 3240.8–3241.8 ms (RTF@12 ≈ 3.24) | PR #7645 body (2026-09-21) |
| 4 GPU USP4 compiled, same PR head | 1541–1558 ms | 1354.9–1363.1 ms (RTF@12 ≈ 1.36; 0/33 chunks met 1 s) | PR #7645; README `benchmarks/lingbot_world/README.md:97-102` |
| 4xH200 USP4 after #7648 alone | – | 916–920 ms median (RTF@12 0.94) | PR #7648 (2026-09-21) |
| 4xH200 #7648 + #7651 (VAE width shard) | – | 721 ms median, p99 906 (RTF@16 0.99) | PR #7648 |
| 4xH200 latest main + decoder/RGB (+ FP8 selective, KV skip) | 1072–1082 ms | **548.68 ms** mean (chunks 6–38) | PR #7749 (2026-09-24) |
| 2xH200 full stack | – | ~892–896 ms | PR #7749 |
| Known issue | first chunk sometimes 5.5–7.5 s with contiguous KV gather default on | – | PR #7749 |
| SP scaling (81-frame offline request, H200) | – | AR-block GPU median 2397 / 1345 / 725 ms for SP1/2/4. Peak alloc 69.3/69.7/59.6 GiB | PR #6841 (2026-09-11) |
| Condition encode | 178 ms/block before the fixed point, which is reached by block 11 | `pipeline.py:1159-1161` |
| Streaming decoder state | ≈1801 MiB/session at 832x480 bf16 | `pipeline.py:85-92` |

**Upstream model claims (B):** 720p @ 60 fps for the distilled real-time variant, hour-level generation, "1.3B on a
single GPU" (arXiv 2607.07534 / model card). The paper summary I retrieved contains no hardware-specific FPS or
latency table. LingBot-World v1: "<1 s latency at 16 fps" (arXiv 2601.20540). **None of this is reproduced in
vLLM-Omni.** The best vLLM-Omni number is 480x832 at ≈22 produced frames/s on 4xH200.

**Derived instruction-to-visible latency (camera), not measured:**

- An event received during chunk N's generation is applied at the boundary after chunk N (`diffusion_model_runner.py:1427-1431`).
- Chunk N+1 then takes one interval T to generate, then the muxed bytes need about +45 ms (PR #7648 note).
- So latency ≈ (0..T) wait + T + delivery + client playback buffer. With T≈549 ms that is **≈0.6–1.15 s + buffer**
  (4xH200). With T≈3.24 s on 1 GPU it is **≈3.3–6.5 s**.
- Within a chunk, the event's arrival time selects the latent frame it starts at (`types.py:108-129`, `camera.py:265-278`).

## 9. Serving interface

- **Offline**: `Omni(...).generate(...)`, then `export_to_video` MP4 (`examples/offline_inference/diffusion/lingbot_world_v2.py:260-277`).
  Tick-mode in-process example writes latent `.pt` plus JSON per chunk
  (`examples/offline_inference/diffusion/lingbot_world_v2_realtime.py`; recipe `:76-110`).
- **Online**: `vllm serve robbyant/lingbot-world-v2-14b-causal-fast-diffusers --omni --deploy-config vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`
  (recipe `:121-134`); endpoint `WS /v1/realtime/video` (`api_server.py:1715`).
- **Protocol** (`serving_video_output_stream.py:1-27`; `docs/serving/streaming_video_output_api.md:32-50`):
  - Client → server: `session.start` {model, prompt, image_reference, width, height, num_frames, fps, seed, format:"m4s", extra_params{flow_shift, camera_action_script | action_path, video_codec_options}},
    `session.interaction` {interaction:{event_id, event:{prompt?, multi_modal_data?}, transition_chunks?}}, `session.ping`, `session.stop`.
  - Server → client: `video.start`; `video.chunk_metadata` {generation_chunk_index, num_frames, byte_length, started/active/completed_event_ids, transport_chunk_index} **followed by one binary fMP4 (m4s) frame**;
    `session.interaction.queued`; `session.pong`; `session.done`; `error`.
  - Only `m4s` is accepted. The default codec is `ultrafast`/`zerolatency` (`:257-261,500-509`).
- Deprecated tick transport is internal Python only (no HTTP).
- SGLang (external, B) offers a different WS API: `/v1/realtime_video/generate`, MessagePack, WebP/JPEG/raw frames,
  and prompt switching (SGLang cookbook). This is a possible alternative backend.

## 10. Integration points for an external controller (LLM planner) and what is missing

**Available (A):**

1. A controller can hold the WS and push SE3 `velocity`/`target` camera events with its own `event_id`s.
2. Per-chunk metadata echoes `started/active/completed_event_ids`, which gives closed-loop acknowledgement of when
   an instruction took effect.
3. `session.stop` for cancel.
4. `transition_chunks` for smoothing camera targets.
5. The Python-level `ARDiffusionSessionManager` for tick sessions, with prompt switching, reset, and close,
   latent output only.

**Missing:**

| Gap | Class | Smallest experiment to resolve |
|---|---|---|
| Mid-session prompt on stepwise path (register `prompt` handler + invalidate text K/V per chunk when the embed changes; embed lerp would need K/V rebuild per chunk) | C | On 1 GPU with the existing stepwise yaml: send one `session.interaction {event.prompt}` at chunk 3 of a 7-chunk session. Confirm `interaction_failed`. Then patch the registry to add `PromptInteractionHandler`, call `_ar_text_caches(state.prompt_embeds, invalidate=True)` when the prompt version changes, and check that chunk 4+ changes (CLIP-score vs both prompts). |
| Whether prompt switching causes character actions (per the paper's chunk-wise captions) with this checkpoint | B→D | Tick-path script (`lingbot_world_v2_realtime.py`) with a prompt event "the character swings a sword", decode latents offline, and inspect / VLM-judge. No server change is needed. |
| Session extension (open-ended length) / reset / rewind over WS | C | Add `session.reset` mapped to `runner.reset_session` and a "continue" that bumps `total_chunks`. Test that a 200-chunk session holds cadence and memory (log `torch.cuda.max_memory_allocated`). |
| Long-term memory beyond sink+window (revisit consistency, persona identity) | D | Loop-closure test: forward 10 chunks, backward 10 chunks, then compare the returned view to the original with LPIPS/DINO similarity. Expect a failure, as the paper admits. |
| Character / avatar / face / lip / gesture control | D | None possible without new conditioning. Probe the prompt-only persona with a talking-head prompt and measure identity drift (ArcFace cosine vs frame 0) over 40 chunks. |
| Audio / TTS / lip-sync | D | Out of scope for this backbone. Pair it with a separate audio-driven avatar model. |
| Reference-image re-conditioning mid-session (scene cut / new persona) | C/D | Engineering: close the session and start a new one with a new image (cost = TTFC ≈1.1 s on 4xH200). Research: inject a new condition into a running KV. |
| Resolution > 480x832 / 720p | C/D | The recipe restricts to ≤480x832 (`pipeline.py:1004-1005`). 720p would need a new `ar_diffusion_height/width` plus quality validation. The checkpoint's 720p ability is unverified. |
| Real-time on 1 GPU | C | Reproduce the benchmark: `gpu run --gpus 1 -- vllm serve … single_gpu_eager.yaml`, then `benchmark_lingbot_world_realtime.py --num-chunks 16`. The expected ~3.2 s/chunk means RTF > 3. Then try compile + FP8. |
| Verify reported 4-GPU cadence on this machine | B→A | `gpu run --gpus 4 --timeout 1h -- vllm serve … usp4_compiled.yaml` + benchmark `--num-chunks 40 --warmup-sessions 1 --sessions 3 --target-fps 12`. |
| Server-side per-chunk timestamps for instruction-to-pixel latency | C | Add a monotonic timestamp to the chunk metadata. Measure event-send → first chunk whose `started_event_ids` contains the event. |
| Multi-replica / multi-user | C | Needs session-affine routing (design doc `:170-172`). |

---

## Evidence table

| # | Claim | Evidence | Date | Class |
|---|---|---|---|---|
| 1 | Only `robbyant/lingbot-world-v2-14b-causal-fast-diffusers` is supported | `recipes/Robbyant/LingBot-World-2.0.md:8,277` | 2026-09-24 (HEAD) | A |
| 2 | Pipeline class `LingBotWorldCausalDMDPipeline`, 4 fixed DMD steps (1000/750/500/250) | `pipeline.py:111,571-592,1007-1014` | HEAD | A |
| 3 | LingBot-World v2 first landed in vLLM-Omni via tick sessions | PR #5491, merged 2026-08-16 (commit 3875f8ded) | 2026-08-16 | A |
| 4 | Stepwise streaming execution added | PR #6844, merged 2026-09-07 (5cd925631) | 2026-09-07 | A |
| 5 | Ulysses SP added; SP4 AR-block GPU median 725 ms (H200) | PR #6841, merged 2026-09-11 | 2026-09-11 | A (code) / B (numbers) |
| 6 | Camera SE3 interaction for streaming | PR #7198, merged 2026-09-20 (e36babd48) | 2026-09-20 | A |
| 7 | Interaction framework (prompt, then camera) refactor | PR #6294 (2026-09-07); midway prompt frontend PR #4652 (2026-07-27) | – | A |
| 8 | Registry: LingBot → `camera` only; Helios → `prompt` | `vllm_omni/diffusion/interaction/registry.py:17-28` | HEAD | A |
| 9 | Unsupported modality raises ValueError | `coordinator.py:59-65` | HEAD | A |
| 10 | Prompt event to LingBot on WS → `interaction_failed` | `serving_video_output_stream.py:461-477` + #8/#9 | HEAD | A (code-read, not executed) |
| 11 | Stepwise path encodes the prompt once and never invalidates text K/V | `pipeline.py:1893-1897,1935,2053-2056` | HEAD | A |
| 12 | Tick path supports prompt switching with K/V invalidation, latent output only | `pipeline.py:1437-1463,1531-1539` | HEAD | A |
| 13 | Image used only at chunk 0 | `pipeline.py:1166-1172,1218-1231` | HEAD | A |
| 14 | Keys WASD/IJKL only; 0.05 move, 4° pitch, 6° yaw | `actions.py:28-29,275-339` | HEAD | A |
| 15 | SE3 camera target/velocity semantics, applied at chunk boundary | `interaction/modality_handlers/camera.py:104-359`; `diffusion_model_runner.py:1427-1431` | HEAD | A |
| 16 | Camera script and live camera are mutually exclusive | `pipeline.py:1956-1962,1985-1991` | HEAD | A |
| 17 | Chunk = 3 latent frames = 12 px frames (9 for the first) | `pipeline.py:2186-2197`; `transformer.py:841` | HEAD | A |
| 18 | Sink 9 + window 18 latent frames | local `transformer/config.json`; `pipeline.py:748-782` | snapshot 59cccf49 | A |
| 19 | Official README uses `--sink_size 6 --local_attn_size 18` | local model card README | 2026-07-09 | B |
| 20 | Resolution ≤ 480x832, fixed at load | `pipeline.py:1004-1005,1880-1884`; yaml `:40-41` | HEAD | A |
| 21 | `max_num_seqs=1`, single replica, 2 resident sessions | design doc `:161-176`; `pipeline.py:784` | HEAD | A |
| 22 | WS cancel via `session.stop`/disconnect; no reset/rewind over WS | `serving_video_output_stream.py:168-171,307-310`; design doc `:211-222` | HEAD | A |
| 23 | Reset/close exist for tick sessions (Python) | `experimental/ar_diffusion/session.py:468-516`; `runner.py:228-234` | HEAD | A |
| 24 | Output = fMP4 (m4s) video chunks; no audio | `serving_video_output_stream.py:257-261,500-545`; `pipeline.py:2159-2173` | HEAD | A |
| 25 | 1-GPU eager ≈3241 ms/chunk; USP4 compiled ≈1359 ms/chunk (older head) | PR #7645 body; `benchmarks/lingbot_world/README.md:97-102` | 2026-09-21 | B (upstream-measured) |
| 26 | 4xH200 latest ≈549 ms/chunk, TTFC ≈1.07 s; 2xH200 ≈892–896 ms | PR #7749 body (ba3d48e1c) | 2026-09-24 | B (upstream-measured) |
| 27 | 4xH200 721 ms median with #7648+#7651 | PR #7648 body | 2026-09-21 | B |
| 28 | Two-session KV requirement 57.1 GiB (H200) | PR #5491 body | 2026-08-16 | B |
| 29 | "L20X" NVML string = H200 BIOS mislabel on the PR author's node | PR #7749 body; local `nvidia-smi` shows 8x L20X 143771 MiB | 2026-09-24 / 2026-09-25 | B (unverified here) |
| 30 | Streaming decoder ≈1801 MiB/session | `pipeline.py:85-92` | HEAD | A (comment-reported) |
| 31 | Paper: LingBot-World 2.0 "Infinite Worlds with Versatile Interactions", arXiv 2607.07534 v1 | https://arxiv.org/abs/2607.07534 | 2026-07-08 | B |
| 32 | Claims 720p@60fps distilled, hour-level horizon, 14B + 1.3B single-GPU | arXiv 2607.07534; local model card | 2026-07 | B |
| 33 | Character actions / events via chunk-wise prompts; Space jump, P glide; VLM Director/Pilot agents | arXiv 2607.07534 (HTML v1) | 2026-07-08 | B |
| 34 | Paper admits no true memory: revisited regions regenerated | arXiv 2607.07534 (HTML v1) | 2026-07-08 | B |
| 35 | v1 paper "Advancing Open-source World Models", arXiv 2601.20540; <1 s latency, 16 fps, minute-level | https://arxiv.org/abs/2601.20540; local v1 model card | 2026-01-28 | B |
| 36 | v1 checkpoints: base-cam, base-act, fast (Apache-2.0) | local `models--robbyant--lingbot-world-fast-diffusers` README | 2026-01-29 | B |
| 37 | v2 GitHub: robbyant/lingbot-world-v2, CC BY-NC-SA 4.0; 14B causal-fast/pretrain/bid, 1.3B causal-fast (2026-09-10) | https://github.com/robbyant/lingbot-world-v2 | 2026-09 | B |
| 38 | HF model `robbyant/lingbot-world-v2-14b-causal-fast-diffusers`, CC BY-NC-SA 4.0 | https://huggingface.co/robbyant/lingbot-world-v2-14b-causal-fast-diffusers ; local snapshot 59cccf49 | 2026-07-09 | A (weights present locally) |
| 39 | SGLang LingBot-World 2.0 cookbook: 8 GPU Ulysses-8, WS MessagePack, prompt switching | https://docs.sglang.io/cookbook/diffusion/LingBot-World/LingBot-World-2.0 | fetched 2026-09-25 | B |
| 40 | Upstream benchmark sends prompt updates although LingBot has no prompt handler | `benchmarks/lingbot_world/workload.py:145-165` vs `registry.py:25-27` | HEAD | C (inconsistency; unexecuted) |
| 41 | Persona avatar / face / lip / gesture control | none found | – | D |
| 42 | Audio / speech | none found | – | D |

## Capability classification summary

- **A (in code):**
  - image+text-conditioned start, 480x832
  - streamed fMP4 chunks over `WS /v1/realtime/video`
  - live SE3 camera (target/velocity)
  - request-scoped WASD/IJKL script
  - pose/intrinsics trajectory replay
  - sink+rolling-window paged KV
  - stop/abort, and event acknowledgement via chunk metadata
  - Ulysses SP, TP 1/2, online FP8
  - tick-path prompt switching, reset, and close (Python, latents only)
- **B (upstream-reported, not verified here):**
  - cadence numbers (≈549 ms/chunk on 4xH200, ≈3.2 s on 1 GPU)
  - 720p@60 fps, hour-level horizon
  - character actions via chunk-wise prompts; director/pilot agents
  - H200 identity of the local "L20X" cards
- **C (engineering):**
  - prompt interaction on the stepwise path (with text-K/V invalidation)
  - WS reset / extend / rewind / snapshot
  - image re-conditioning by session restart
  - multi-replica routing
  - per-chunk server timestamps
  - >480x832 resolution
- **D (training/research):**
  - persona avatar identity, face, lip-sync, gesture control
  - audio
  - long-term memory beyond the ~6-chunk window
  - reliable character-behavior control with this checkpoint
