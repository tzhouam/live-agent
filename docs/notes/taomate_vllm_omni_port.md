# TaoMate-H3 in vLLM-Omni (USP4 realtime port)

Status: implementation in progress (2026-09-27). Owner directive: support and optimize
TaoMate-H3 in vLLM-Omni so that it runs in real time under pure Ulysses sequence parallel
on 4 GPUs (USP4). Decision D-026.

## Where the code lives

- Worktree: `/data/zhoutaichang/worldmodel/vllm-omni-taomate`, branch
  `feat/taomate-h3-realtime` of the owner's fork, based on upstream `main` 6715c57b2
  (2026-09-26). Environment: `.venv` in the worktree (vLLM 0.30.0, torch 2.13.0+cu129,
  `fa3_fwd_interface` FA3 kernels).
- New package `vllm_omni/diffusion/models/taomate_h3/` (geometry, packed layouts, LoRA
  hooks, clean AV KV cache, streaming attention, audio teacher, streaming decode,
  pipeline), deploy config `vllm_omni/deploy/taomate_h3_usp4_realtime.yaml`, recipe
  `recipes/TaoLiveAIGC/TaoMate-H3.md`, CPU tests `tests/diffusion/models/taomate_h3/`.
- Upstream touch points: `attention_cls` on the H3 DiT block/model, `_transformer_cls` on
  the H3 pipeline, registry/metadata/pipeline-config/interaction-registry entries, and the
  fragmented-MP4 streaming path now carries an AAC audio track.

## What was ported (and checked against the clone)

| Piece | Source of truth (external/TaoMate-H3 @ 6b2f998) | Check |
| --- | --- | --- |
| Phase geometry (124/119 frames, 12/10/10/5 latents, 40 Hz audio boundaries, RoPE timeline) | `streaming/geometry.py` | exact parity for requests 0..39 and 200 RoPE positions (script, measured locally) |
| Sigma ladders (student (0,16,33,49) of 50, shift 12/3; teacher 10 states) | `denoise_schedule.py`, `teacher.py` | exact parity |
| Clean AV KV retention (first-phase video sink + 2 recent, audio drop every 12 requests) | `streaming/cache.py` | unit test |
| Streaming attention (condition rows attend text; media rows attend text+history+current; commit stages post-a2a K/V) | `streaming/attention_hook.py` | port; end-to-end run |
| Native LoRA (rank 128, 52x4 targets, unmerged) | `inference/lora_checkpoint.py` | unit test on the hook math; QKV rows permuted to vLLM's [Q;K;V] |
| Audio teacher (LoRA off, audio-only documents, tail-40 rollover, milestones 3/6/9) | `teacher.py` | port; audio produced end-to-end |
| Streaming VAE decode (7-latent windows, stride 5, 5-frame blend) | live-agent `taomate_worker/stream_decode.py` | port |

Differences from the release runtime: TP=1 (pure USP) instead of TP2xU2; BF16 base for both
student and teacher (the release runs the student's interior qkv/fc1 as W8A8); teacher and
student share one process and one weight copy; per-phase streaming decode instead of a
one-shot decode.

## Measured so far (4x H200-class, eager BF16, 480x864, one session)

From the WebSocket client of the 2026-09-27 05:24 run (three requests, one prompt update):

| Chunk | Frames | Period |
| --- | --- | --- |
| 1 (cold server) | 34 | 16.9 s |
| 2, 3 (phases 1-2) | 34 | 1.08 s, 1.80 s (prompt update encode) |
| 4 (phase 3) | 17 | 0.68 s |
| 5 (request 2 phase 0: teacher + new prompt) | 34 | 2.30 s |
| 6-8 | 34/34/17 | 0.89 s, 0.90 s, 0.83 s |
| 9 (request 3 phase 0) | 34 | 1.66 s |
| 10-11 | 34/34 | 0.92 s, 0.88 s |

A request therefore takes about 4.3-4.9 s of wall time for 4.958 s of content: real time
with a thin margin in eager mode, before compile, FP8 or teacher overlap. All numbers are
*measured locally*, single session, not a soak.

## Long run (13 requests, constant prompt, eager BF16; measured locally 2026-09-27 05:33)

52 media chunks + trailer for 1552 frames (64.6 s of 24 fps video with 32 kHz AAC audio in
one fragmented-MP4 stream; audio RMS 0.02-0.18 per 5 s, no NaN). Steady state per request:
phase 0 1.68-1.72 s (teacher + phase), phases 1-2 0.86-0.95 s, phase 3 0.53-0.60 s, i.e.
about 4.1 s per 4.958 s request (real-time factor 0.82). The audio-KV drop at request 12
ran without error. First chunk of the cold server: 19.9 s.

With `enforce_eager: false` and the load-time AR warmup (one throwaway request through the
request-mode forward), the first chunk of a fresh session arrived after 2.96 s and a
request took about 4.3-4.4 s; the compiled blocks hit Dynamo's recompile limit (8) during
warmup and partly fell back to eager, so the warmup, not the compile, is the gain.

A QKV LoRA layout bug (the adapter's fused-QKV `lora_b` is already in the merged [Q;K;V]
row order; the port permuted it once more) was found after these runs and fixed in commit
6aa78cd80 of the worktree; the numbers above are timing-only and unaffected by it.

## Stage breakdown (eager BF16, 480x864, rank 0 with device syncs; measured locally 2026-09-27 06:00)

| Stage | 34-frame phase | 17-frame phase |
| --- | --- | --- |
| audio teacher (once per request, 9 forwards) | 0.71-0.82 s | - |
| 3 student forwards | 0.42-0.44 s | 0.27 s |
| clean-commit forward + cache append | 0.15 s (outliers 0.3-0.7 s) | 0.10 s |
| tile-parallel video VAE decode (7-latent windows) | 0.19-0.20 s | 0.09 s |
| audio VAE decode (sliding window) | 0.03 s | 0.03 s |

Per steady-state request: 1.55 + 0.86 + 0.89 + 0.56 = 3.9 s for 4.958 s of content (real-time
factor 0.78). FP8 online linears with regional compile and fixed packed lengths gave the same
4.3 s per request as BF16 eager, so the linears are not the bottleneck; the teacher's nine
short forwards (about 85 ms each, launch-bound) and the per-phase VAE decode are the next
targets (CUDA graphs on the pinned shapes, VAE decode on a side stream).

The Codex review of the port (`docs/codex_reviews.md`, round taomate_port1) found one real
defect (chunk metadata carried the request id instead of the AR session id; fixed) and a
LoRA layout bug was found by inspection before the review (fused-QKV `lora_b` must not be
permuted; fixed). With the fix the persona is stable across a 13-request session.

## Open items

- CUDA graphs for the teacher and student forwards on the pinned shapes (the compile path
  offers no graph mode today); VAE decode overlap on a side stream.
- Parity against the release runtime's audio is not measured (different kernels; the
  release itself is not video-reproducible run to run).
- Done 2026-09-27 (D-028): the live demo runs on this port through `VllmOmniH3Generator`
  (`scripts/run_live.sh omni`) with the just-in-time prompt hold
  (`taomate_h3_hold_for_prompt`, vllm-omni commits 6747a4042, 78a90e04e, 68d8106a7).

## Two GPUs (USP2): baseline and levers (2026-09-28)

Owner directive: "further optimize the model, so that we can have real time inference in 2
H200". Decision D-036. Config under test: `devices "0,1"`, `sequence_parallel_size 2`,
`ulysses_degree 2`, `text_encoder_tp_size 2`, `vae_patch_parallel_size 2`, eager BF16,
load-time warmup; 100.7 GB per rank after load.

Baseline (measured locally, 5 requests, constant prompt, rank 0 with device syncs):

| Stage | 34-frame phase | 17-frame phase |
| --- | --- | --- |
| audio teacher (per request, 9 forwards) | 0.78-0.84 s | - |
| 3 student forwards | 0.77-0.81 s | 0.43 s |
| clean-commit forward | 0.29-0.32 s | 0.16 s |
| video VAE decode (2 tiles) | 0.35-0.37 s | 0.18 s |
| audio VAE decode | 0.03 s | 0.03 s |

Per request 2.29 + 1.55 + 1.59 + 0.86 = **6.3 s per 4.958 s** (real-time factor 1.27; client
period 6.4 s). Not real time. Versus USP4: DiT forwards 1.9x per rank, VAE 1.8x, teacher
unchanged (launch-bound).

Estimate of the gap (from the breakdown): the request must lose at least 1.4 s, 1.9 s for a
margin like USP4's. Levers implemented in the worktree (commit after 37edffce8):

- **Teacher CUDA graphs** (`taomate_h3_teacher_cuda_graph`, new `taomate_h3/cuda_graph.py`):
  the nine teacher forwards are captured once per document shape and replayed; the
  teacher's timestep vector is a fixed three-slot tensor (no `torch.unique` sync) and the
  sequence-parallel embedding uses precomputed row selections (`LocalEmbedPlan`, no
  boolean-mask sync). Estimate: 0.8 s -> 0.2-0.3 s per request. Guarded: sync-debug probe
  before the first capture, all-reduce agreement on success, eager fallback.
- **FP8 online linears** (`quantization: fp8`) at USP2, where the GEMMs are about 60% of a
  student forward (estimate). Gave nothing at USP4 (attention and overhead dominated there).
- Not offered: LingBot-style reuse of the last denoise step's K/V for the commit. TaoMate's
  last student forward runs at sigma 0.853 (ladder 1.0, 0.961, 0.853, 0; from
  `schedule.py`), so its K/V is far from clean; the commit forward stays.
- Remaining fixed cost: VAE decode 1.26 s per request (7-latent windows, stride 5: 14
  latents decoded per 10 new ones, exact parity with the release's incremental decode).

Status: code and CPU tests done (`tests/diffusion/models/taomate_h3/test_taomate_h3_cuda_graph.py`,
28 tests pass), `vllm_omni/deploy/taomate_h3_usp2_realtime.yaml` written; the optimized
USP2 run is **not measured yet** because the shared GPUs were queued (FCFS with partial
allocation: releasing the baseline server's two cards would have parked them in a queued
job waiting hours for the rest), and swapping the server inside the reservation was not
permitted. Next: start the FP8 + graph server with `--wait`, capture five requests, record
the stage breakdown here and in the recipe; then decide on further levers (VAE decode on a
side stream, text-encoder cost per prompt update at TP2).
