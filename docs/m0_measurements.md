# M0 measurements: TaoMate-H3 on the local GPUs (2026-09-26)

Status: first local measurements (Phase 2, D-019). Every number in this file is **[measured
locally]** unless it carries another label. Raw data (events, logs, JSON, MP4s) is under
`.cache/m0/` (git-ignored). Scripts are in `scripts/m0/`.

## Setup

| Item | Value |
|---|---|
| Date | 2026-09-26, 05:00-05:55 CST |
| Hardware | GPUs reported by torch as compute capability (9, 0), 139.8 GiB, 132 SMs (nvidia-smi name "NVIDIA L20X"). So they are Hopper/SM90 and the FA3 path runs natively; no FA2/SDPA port (T4) was needed. Driver 570.133.20 |
| GPUs used | canhazgpu IDs 0,1,2,3 (4-GPU runs) and 0-5 (one 6-GPU run). GPU 6 was reserved by the lead for helper models and GPU 7 was held by another user's process, so **no 8-GPU run was possible** |
| TaoMate-H3 | `external/TaoMate-H3` at `6b2f9984acf681e2f387188f5d1f3b26e504315b` (read-only, unmodified; integrated by import, subclassing and runtime wrapping) |
| LoRA | HF `TaoLiveAIGC/TaoMate-H3` sha `7d7a51f3e63972138882ec2f0e4d1d47728110cf` (rank 128, step-3000 EMA) in `.cache/models/TaoMate-H3` |
| Base weights | shared `/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe` (= `refs/main`), read-only. FL2VA complete: 13 transformer shards (62 GB), text_encoder (63 GB), video_vae (9.8 GB), audio_vae (0.6 GB). Four other snapshots also carry a complete FL2VA |
| Environment | `.venvs/taomate-h3` (`scripts/m0/setup_env.sh`): Python 3.11.15, torch 2.9.0+cu128 (vllm 0.11.1 pins it; the README says torch 2.8), vllm 0.11.1, triton 3.5.0, diffusers 0.35.2, transformers 4.57.6 |
| FA3 | Prebuilt Hopper FA3 from HF `kernels-community/flash-attn3` rev `7cb368cf` (kernel `8a730d9`, `torch-stable-abi29-cu128`), exposed as `flash_attn_interface` by a shim. Only a CUDA 13 toolkit exists on the host, so the README's source build of `flash-attention/hopper` was not attempted. A smoke test against SDPA gave max abs diff 0.002 (bf16) |
| ffmpeg | `/usr/local/bin/ffmpeg` has no libx264, which the released CLI rejects. `/usr/bin/ffmpeg` 4.4.2 has it and is used through a PATH shim |
| Canvas / length | 480x864 (portrait, the README benchmark canvas), 10 s (2 requests) for the released path, and 8 requests (39.7 s native) for streaming |

Live-agent HEAD moved during the session because others were committing (`987de17` to `3cd2de1`). The new files in this work are uncommitted.

## Problems hit and fixes (all in our code; the clone is untouched)

1. **ffmpeg without libx264.** `cli._validate_media_tools` failed. Fix: use `/usr/bin/ffmpeg`.
2. **Triton cache race.** On the first 4-GPU worker run, `OSError: [Errno 116] Stale file handle` came from
   `triton/compiler/compiler.py` (4 ranks sharing `~/.triton` on CPFS). Fix: a per-role, per-rank
   `TRITON_CACHE_DIR` under `.cache/triton/`.
3. **Spinning NCCL waits slowed the colocated student about 2.5×.** In the first streaming run, idle ranks waited for
   commands in `broadcast_object_list` on NCCL. A waiting NCCL kernel occupies SMs, so the colocated
   teacher's idle ranks slowed every student chunk. Chunk denoise took 1.1 s instead of 0.44 s, and a request took 9.6 s.
   Fix: send control traffic over a gloo (CPU) group. The next run gave 5.05 s/request.
4. **Chunk transport.** Pickling about 42 MB of frames per chunk through the socket took 0.27 s per chunk and
   competed for the GIL with the rank-0 launch thread. Fix: hand frames over through `/dev/shm` (0.017 s) and make them
   contiguous before saving. The request time fell to 4.0-4.4 s.

## 1. Released path, component profile (4 GPUs, TP2 × Ulysses2)

Command (3 repetitions in one reservation):

```bash
gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "live-agent M0: TaoMate-H3 released baseline 4GPU 480p 10s x3" -- \
  bash scripts/m0/run_baseline_reps.sh r4_480p 3
python3 scripts/m0/summarize_released.py .cache/m0/runs/r4_480p_rep*
```

`profile_released.py` runs the same two torchrun stages as `python -m taomate_h3` (cli.py:219-229),
with `examples/prompts_10s.json` and seed 8301. It adds synchronized timestamp hooks through
`profile_entry.py`. rep1 is the first run in fresh Triton caches, so it includes JIT compilation.

| Component | rep1 | rep2 | rep3 | Note |
|---|---|---|---|---|
| Teacher process, spawn → exit (s) | 75.7 | 74.5 | 77.5 | whole stage 1 |
| Teacher model load: text encoder + BF16 DiT (s) | 36.3 | 36.3 | 38.9 | one-time |
| Teacher text encode, request 0 / 1 (s) | 5.25 / 0.060 | 3.63 / 0.058 | 2.97 / 0.059 | request 0 includes warm-up |
| Teacher text-encoder offload to CPU (s) | 13.4 | 12.2 | 10.9 | removed in the streaming adapter |
| **Audio teacher, request 0 / 1 (s)** (10-state, 9 forwards) | 2.80 / **0.653** | 4.07 / **0.684** | 6.51 / **0.677** | |
| Student process, spawn → exit (s) | 154.8 | 136.3 | 139.1 | whole stage 2 |
| Student model load + LoRA + acceleration (s) | 47.0 | 50.8 | 49.5 | of which LoRA 0.8-1.3 |
| Student text encode, request 0 / 1 (s) | 1.72 / 0.057 | 0.77 / 0.061 | 1.69 / 0.060 | |
| Student text offload (s) | 12.7 | 12.4 | 13.6 | |
| **Student request 0 / 1, 4 chunks (s)** | 12.71 / **2.49** | 7.45 / **2.96** | 8.10 / **2.50** | request 0 = cold (JIT, allocator) |
| First final chunk latent (from request start) (s) | 10.12 | 4.78 | 5.45 | README, 8×H20: 6.148 s [cited] |
| Pure DiT CUDA time, 24 noisy + 8 clean forwards (s) | 10.26 | 6.82 | 7.12 | README, 8×H20: 14.81 s [cited] |
| VAE load and setup before the first decode (s) | 45.1 | 33.1 | 33.6 | one-time |
| Video VAE decode, 243 frames, one-shot (wall / CUDA-active s) | 9.36 / 4.90 | 6.42 / 2.55 | 6.04 / 2.42 | temporal-window DP |
| H.264 encode, video only (s) | 1.72 | 1.84 | 1.83 | |
| Audio VAE decode, 10 s (s) | 2.19 | 1.87 | 3.10 | includes the host→GPU move |
| AAC mux (s) / strict validate (s) | 1.23 / 1.93 | 1.26 / 2.07 | 1.19 / 2.03 | |
| Peak allocated per GPU: student / its DiT interval (GiB) | 42.4 / 36.6 | same | same | README DiT peak: 31.37 GiB [cited] |
| Peak allocated per GPU, teacher (GiB) | 55.3 | 55.3 | 55.3 | |
| nvidia-smi peak used per GPU (GiB) | 57.1 | 57.1 | 57.1 | all 4 GPUs |

Per-chunk timing in the warm request 1 (mean of 3 runs):
- Denoise, 3 noisy forwards: 0.44 s for a 10-latent chunk and 0.34 s for the 5-latent chunk.
- Clean-KV commit: usually 0.15-0.19 s, with occasional outliers of 0.64-0.87 s.

Across the 3 runs, the released video latents of the same seed are **not reproducible**: relative L2 difference 0.31-0.37 between runs. Teacher milestones do not have this problem.

## 2. Streaming adapter (T1 + T2 + T3), 8 mid-session requests

Command:

```bash
gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "live-agent M0: ..." -- \
  .venvs/taomate-h3/bin/python scripts/m0/validate_streaming.py --tag s4_coloc_v3 --colocate --student-devices 0,1,2,3
gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "..." -- bash scripts/m0/run_stream_reps.sh   # rep2, rep3, sequential
gpu run --gpu-ids 0,1,2,3,4,5 --timeout 1h --note "..." -- .venvs/taomate-h3/bin/python \
  scripts/m0/validate_streaming.py --tag s6_dedicated --student-devices 0,1,2,3 --teacher-devices 4,5
python3 scripts/m0/summarize_streaming.py .cache/m0/stream/<runs>
```

**Workload.** 8 different prompts (`scripts/m0/prompts_session_40s.json`: same presenter, a new action and line each
time), submitted one at a time.

**Warm-up.** One throw-away request runs before the session, followed by `reset()`.

**Lock policy.**
- Requests 1-5 are pipelined: request k+1 is locked when request k's first chunk arrives.
- Requests 6-7 are idle: each is locked 0.5 s after the previous request finishes, which measures Λ_idle.

**Topology.**
- Colocated: the teacher is a second torchrun group on the student's 4 GPUs (TP2×U2).
- Dedicated: the teacher runs on GPUs 4-5 with TP2 × Ulysses 1. This was not a validated upstream topology, but it ran.

| Run | Teacher | Teacher s/req | Student s/req, pipelined 1-5 (mean / max) | Period s/req | Lock→first chunk, pipelined (s) | **Λ_idle** (lock→first chunk) (s) | Student start→first chunk (s) | Idle chunk denoise / decode / transport (s) | Min startup buffer, no stall (s) |
|---|---|---|---|---|---|---|---|---|---|
| s4_coloc_v1 (NCCL waits, pickled frames) | colocated, lookahead | 2.06 | 9.62 / 10.42 | 9.62 | 9.87 | 4.03, 5.09 | 2.34 | 1.11 / 0.51 / 0.277 | 39.8 |
| s4_coloc_v2 (gloo control) | colocated, lookahead | 1.22 | 5.05 / 5.57 | 5.06 | 5.42 | 1.85, 1.80 | 1.10 | 0.42 / 0.25 / 0.265 | 3.56 |
| **s4_coloc_v3** (+ /dev/shm) | colocated, lookahead | 1.21 | **4.22 / 4.55** | 4.10* | 4.38 | **1.54, 1.56** | 0.82 | 0.41 / 0.26 / 0.018 | 0.69 |
| s4_coloc_rep2 | colocated, lookahead | 1.25 | 4.41 / 4.98 | 4.35* | 4.54 | 1.53, 1.51 | 0.79 | 0.42 / 0.24 / 0.017 | 0.03 |
| s4_coloc_rep3 | colocated, lookahead | 1.12 | 4.03 / 4.39 | 3.80* | 4.13 | 1.55, 1.54 | 0.79 | 0.41 / 0.24 / 0.016 | 0.57 |
| s4_coloc_seq | colocated, **sequential** | 0.73 | 3.56 / 3.84 | 4.31* | 4.47 | 1.51, 1.51 | 0.80 | 0.42 / 0.24 / 0.015 | 0.19 |
| **s6_dedicated** | GPUs 4-5, lookahead | 0.69 | **3.55 / 3.82** | **3.55** | 3.62 | **1.53, 1.50** | 0.82 | 0.42 / 0.26 / 0.017 | **0.00** |

`*` marks a period reconstructed from lock policy and per-request deltas; ±0.1 s [estimate]. The s6 run has exact absolute timestamps.

**Definitions.**
- **Period.** The mean time between completions of pipelined requests, teacher included. Real time needs a period below 119/24 = **4.958 s**, the native media per request. Frames are native 24 fps without the released 124+119n→120n time warp.
- **Min startup buffer.** The smallest playback delay after the first chunk that avoids any stall, given where each chunk sits on the playback timeline.

**Common to all runs.**
- Chunks: 34/34/34/17 frames per request.
- `audio == teacher`: True in every request. This is the runtime's own check `torch.equal(published audio, teacher clean latent)` (streaming/runtime.py:739-743).
- Streamed audio compared with a one-shot audio VAE decode of the same latents: SNR 62-63 dB, max abs diff ≤ 0.007.
- Frames emitted: 952, plus 5 held back until `flush()`.
- Startup cost:
  - Processes → both ready: 128-141 s. Student load 95-102 s, with the VAE on the GPU; teacher load 37-39 s.
  - Warm-up request: 16-19 s after the first run (31 s in v1).
- Memory: student peak 51.1 GiB per GPU, including the resident video VAE; teacher 55.2 GiB per GPU. Colocated this is about 106 GiB of 139.8 GiB.
- Sample MP4s:
  - `.cache/m0/stream/s4_coloc_v3-20260926T053444/session.mp4`
  - `.cache/m0/stream/s6_dedicated-20260926T054734/session.mp4`
  - Both are 39.67 s, 480x864 h264 + AAC 32 kHz. A frame check shows a consistent presenter, with the prompted actions such as a raised palm and a wave visible.

**Composition of Λ_idle ≈ 1.5 s.**
- Teacher: text 0.06 s + audio teacher 0.63 s ≈ 0.70 s.
- Dispatch: < 0.03 s.
- Student chunk 0: denoise 0.44 s + VAE decode 0.28 s + transport 0.02 s + branch build about 0.08 s ≈ 0.82 s.

**Parity with the released path** (`scripts/m0/parity_check.py`, prompts_10s, same seed):
- Teacher milestones (states 3/6/9) and the student's published audio latents are **bitwise identical** to the released run for both requests.
- Video latents differ with relative L2 0.39-0.42. This is in the same range as the run-to-run variation of the released path itself (0.31-0.37). So there is no bitwise video parity, and no evidence of a systematic deviation.

## 3. What this decides (proposal §6.4 / §11)

- **Generator throughput is real time at 480p on 4 local Hopper GPUs** with the streaming adapter.
  - With a dedicated 2-GPU teacher: period 3.55 s against 4.958 s of media, about 1.40× real time, and no startup buffer needed.
  - Colocated on the same 4 GPUs: period 3.8-4.35 s (about 1.14-1.30×). The worst single request was 4.98 s (rep2), so the colocated margin is thin.
- **Teacher lookahead (T2).**
  - Dedicated GPUs: the lookahead hides the teacher completely (period = student time).
  - Colocated: lookahead overlaps the teacher with the student's chunk 1. That chunk's denoise rises from 0.44 s to about 1.0-1.3 s, so the gain over the sequential teacher is small (period 3.8-4.35 s vs 4.31 s).
- **Λ_idle (lock → first chunk ready at the adapter) ≈ 1.5 s** in every warm configuration. Under pipelined just-in-time locking, lock → first chunk is 3.6-4.5 s, because request k+1 waits for request k to finish (KV dependency).
- **Scope of the claim.** These results qualify only the *generator + adapter* part of M1. They do not cover:
  - a client playback path, where σ and jitter are unmeasured;
  - 30-minute soak tests;
  - GPU contention from the LLM/ASR/VLM services;
  - 768p or 1080p.
- **Comparison with the README.** The README's H20 numbers (DiT 14.8 s per 10 s) [cited] are about 2× slower than local runs. The earlier proposal inference "not real time" [estimate, based on H20] does not hold for this hardware.

## 4. Open gaps

- No 8-GPU run: GPUs 6 and 7 were unavailable. The 4-vs-8 comparison is open.
- No repetition at 768p or 1080p, and no 60 s run on the released path. The audio-KV reset every 12 requests (60 s) has not been exercised in streaming (8 requests max).
- The released path's video latents are not deterministic for a fixed seed (cause not investigated; candidates are FA3/NCCL/atomic nondeterminism amplified by the 3-step sampler). This limits exact parity testing.
- Request 0 of a process costs 7-13 s without warm-up. The adapter's `warmup_prompt` hides this behind start-up.
- Colocated chunk-1 contention (teacher k+1 overlapping student k) is the main source of variance. A dedicated teacher or a lower-priority CUDA stream for the teacher are the options.
- fMP4 per-chunk encoding (`Chunk.encoded`) is not implemented. Chunks carry raw uint8 frames and float32 audio.
- VAE windows: each chunk emits exactly its own 34/34/34/17 final frames (VAE windows [5i, 5i+7) complete inside each chunk). Only the 5-frame blend tail of the newest window is held, and it is emitted by `flush()` at session end. At the last chunk of a request, the audio decode has only about 8 latents (0.2 s) of right context. The 62-63 dB SNR against the one-shot decode includes this effect.
