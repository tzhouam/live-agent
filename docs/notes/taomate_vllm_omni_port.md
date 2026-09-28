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

Results (measured locally, 2026-09-28, worktree commits a53367f52 and later, 480x864,
GPUs 1 and 4, five requests, constant 32-token prompt, rank 0 with device syncs):

| Stage | 34-frame phase | 17-frame phase |
| --- | --- | --- |
| audio teacher (per request, 9 graph replays) | 0.35 s (0.78-0.84 eager) | - |
| 3 student forwards, FP8 | 0.67-0.70 s (0.77-0.81 BF16) | 0.42-0.45 s |
| clean-commit forward | 0.24-0.26 s | 0.15-0.17 s |
| video VAE decode, 2 x 480 px tiles | 0.21-0.22 s (0.35-0.37 with 256 px tiles) | 0.10 s |
| phase preparation | 0.01-0.03 s | 0.00 s |

Per request: 4.70 s of GPU time; 4.91-4.97 s of wall time between request ends (client:
4.92-4.95 s between the first chunks of consecutive requests) for 4.958 s of content, so
**real-time factor 0.99-1.00** (was 1.27). Real time is reached with no headroom; the
client needs about one second of playback buffer. Contributions: FP8 -0.4 s, teacher
graphs -0.45 s, 480 px decoder tiles -0.5 s per request (each measured as the stage
difference between runs; not additive-exact).

Findings on the way (all measured locally):

- **Teacher graphs are keyed by the prompt's token count.** The H3 attention treats the
  valid rows of a document as a prefix whose length is a Python int of the forward
  (`max_seqlen_q`), so a fixed text length would need extra rows inside the prefix
  (attended, so not exact). Consequence: every new prompt length captured three graphs
  (first request, later requests with 476 or 478 audio rows) inside the stream, 0.7 s
  each plus 0.5-0.9 s of slow commits while the allocator regrows: 2.1 s before a
  session's first chunk and 2-3 s per prompt update with a new length. Fix: the load-time
  warmup now runs four requests (the three-request audio-latent cycle 198/198/199) and
  captures the graphs of a configured token-count range
  (`taomate_h3_teacher_graph_text_lengths: "8-96"`, about 270 graphs, ~5 MB and ~0.5 s
  each; effect on the stream to be confirmed in the next run, the GPUs were queued).
- **Prompt updates were applied with the first prompt's length.** The step runner pads
  each request's prompt embeddings to the length it recorded (`txt_seq_lens`) and writes
  the padded tensor back into the request state, so a shorter new prompt reached the next
  request zero-padded (rows tagged as text) and a longer one would have been truncated;
  the token tags stayed those of the old prompt. Found because the teacher captured no
  new graph after updates of 28/23/21 tokens. Fix in the TaoMate prompt handler: record
  the new length and tags on the state when the update is applied (CPU test against the
  real `InputBatch`).
- Prompt re-encode on the workers (Qwen3-VL, TP2): 0.13-0.20 s for 21-32 tokens, paid
  inside the phase in which the update arrives.
- Session-close `empty_cache` removed (the next session paid cudaMalloc again for every new
  history size in its first request); slow commits now only follow graph captures.
- Rejected: LingBot-style reuse of the last denoise step's K/V (last student sigma 0.853).
  Remaining fixed costs: VAE decode 0.87 s per request at 480 px tiles; commit forwards
  0.82 s per request.

Confirmation run (measured locally, 09:00, worktree 66e71a2e0): the warmup captured 267
teacher graphs (prompts of 8-96 tokens) in 149-174 s; two live sessions captured nothing;
prompt updates of 28/23/21 tokens changed the content at their real length. Without the
timing instrumentation, ten requests averaged 4.98 s between request starts (range
4.70-5.10 s) for 4.958 s of content; requests that also applied a prompt update took
5.2-5.3 s (re-encode 0.13-0.27 s).

Drift run (measured locally, 10:00, worktree 2df43b386): 100 requests with a different prompt
(3-60 words) every request, no instrumentation: 5.14 s per request on average (5.09 s once
warm, requests 20-100), 20 s of drift over 101 requests, i.e. a client buffer of one second
lasts 5-8 requests at that update rate. Four teacher graphs were captured live for a 3-token
prompt (the range then started at 8 tokens; the config now starts at 1). A first attempt of
this run had every graph disabled by an over-strict kwargs guard from the Codex fixes
(5.66 s per request with the eager teacher); fixed, with a test over the real teacher kwargs.

Caveat from the peer session live-agent-bb (measured locally with the FL2VA tokenizer): the
live agent's persona prompts are 345-360 tokens, above `taomate_h3_pad_text_tokens: 256` and
outside the graph range of the two-GPU config, so they run unpinned with lazy captures. All
two-GPU numbers here are for 3-60 word prompts. For persona prompts use a pad of at least
the longest prompt (e.g. 448) and a graph range around the real lengths (e.g. "300-430");
the two-GPU request period at that length is not measured yet and will be somewhat higher
(about 320 more text rows per phase document). On four GPUs (USP4 demo server, eager BF16,
hold-for-prompt on) the peer measured 330-405-token persona prompts with an update on almost
every request at a median of 4.29 s and a maximum of 4.53 s between requests' first chunks
(n=54, real-time factor about 0.86; log `taomate-live-skill/runs/usp4_demo2/events.jsonl`).

Two-GPU persona-length measurement (peer session live-agent-bb, measured locally 11:47-11:51 on
live-agent-13's USP2 server: FP8, teacher graphs, pad 512, graph range 320-420, hold off):
330-405-token prompts, 17 updates over 44 requests, median 5.26 s (min 5.15, max 5.35) between
requests' first chunks, **real-time factor 1.06**, about 0.3 s of drift per request. The sibling
session's own 100-request run on that server (332-340-token prompts, an update every request, AdaLN
cache off, encoder graphs): 5.31 s per request mean, 5.33 s warm, 37 s of drift over 101 requests,
real-time factor 1.07, no live captures. The extra
text rows (about 320 per phase document, plus about 100 pad rows with pad 512) cost the 6% that
short prompts had left. Next lever under test: the LoRA hooks' launch overhead (about 100
hooked linears, 3-4 launches each, per forward); if a no-LoRA timing run shows 0.06 s or more
per phase, the student gets a second FP8 weight set with the LoRA merged in.

FP8 merge check (measured locally on CPU, 22 target linears across blocks 0/12/25/37/49 and the
token refiner, scratchpad `fp8_merge_check.py`): the LoRA delta is 0.2-1.2% of the base weight
norm (median entry ratio 0.2-0.8%), below the e4m3 relative step (about 6-12%), so on an
identical quantization grid the delta would be erased entrywise (peer session's caution). The
merged tensor's amax differs from the base amax by about that ratio, which shifts the grid and
dithers the rounding: the projection of Q(W+D)-Q(W) onto D is 1.01-1.05 |D| on every target
(delta preserved in expectation) with orthogonal requantization noise of about 2.6 |D|. Total
relative error against the BF16 student is 0.0265 either way (Q(W)+D or Q(W+D)). A merged FP8
student weight set is therefore unbiased but not exact; it is only worth its 8 GB per rank if
the LoRA hooks' launch cost (two launches per target after the addmm fusion, 208 targets) is
measurable, which the queued no-LoRA timing run decides. Lever ownership agreed with the
sibling session live-agent-13 (same worktree): it owns the prompt re-encode, text buckets,
device timing, persona runs and student graphs; this session owns the LoRA/FP8 path and the
frame transport.

No-LoRA timing run (measured locally 12:05-12:10, GPUs 0,1, same config, base H3 without the
adapter): 3 student forwards 0.62 s per 34-frame phase (0.67-0.70 with the pre-fusion hooks),
commit 0.23 s (0.25), 4.70 s wall per request against 4.95 s. The LoRA path cost about 0.25 s
per request before the sibling's addmm fusion, so an estimated 0.12-0.18 s remains that only a
merged FP8 student weight set could recover (unbiased but not exact, see above). That is about
half of the persona-length deficit (0.35 s per request); the other half needs the frame transport
or the student forwards themselves. Note on the sibling's new device-time field: start/end CUDA
events on one stream span GPU idle gaps as well, so gpu == wall (as measured) does not separate
device time from launch overhead; a profiler trace or an unsynchronized CPU launch timer is needed.

Persona-length state after the sibling's text buckets and encoder graphs (its measurement, 12:30,
31 requests, 332-340 tokens, update every request): 5.05 s per request, real-time factor 1.02;
re-encode 0.048 s per update from the graph. The remaining gap is dominated by 0.045 s per phase
(0.18 s per request) between the end of a phase and the next preparation. Root cause found by
code reading: in step execution the worker packs each phase's 42 MB of uint8 frames into a fresh
POSIX shared-memory segment on the step thread (`vllm_omni/diffusion/ipc.py`, `_array_to_shm`:
segment creation, first-touch page faults, memcpy). A background packing thread with a side-stream
D2H path exists (`diffusion_worker.py` `_async_output_loop`) but both its creation and
`_return_result` are gated on `not step_execution`, and the engine awaits `OUTPUT_READY` futures
only for finished requests, not for streamed chunks. Scoped fix (this session's lever, not
implemented): (1) create the packing thread in step mode too and let `_return_result` take the
async path for chunk-bearing `BatchRunnerOutput`s; (2) executor: propagate per-request
`async_output_id`s as `execute_model_batch` already does; (3) engine chunk streaming: await the
chunk's future before emitting it, and drop pending ids on abort. Expected gain 0.15-0.18 s per
request (estimate), enough for real-time factor 1.0 at persona length; risk is in ordering and
abort handling of shared infrastructure, and it needs GPU validation.

Implemented (worktree ede67f3e9, GPU validation queued): `step_async_output` in `model_config`.
The worker creates its background packing thread in step execution too and, before replying to a
stepwise RPC, swaps every media-bearing chunk result for a shallow copy without media carrying an
`async_output_id`; the original is packed on the thread and delivered as `OUTPUT_READY`, which the
engine's step streaming already awaits per item. The reply stays synchronous (scheduler bookkeeping
unchanged); aborted requests drop the placeholder's pending output. Unit-tested (detachment,
knob); expected gain 0.15-0.18 s per request. First GPU run (13:52) failed at the first chunk:
"Unexpected response type for execute_step: AsyncDiffusionOutput" -- in step execution the
executor dequeued replies straight from the worker result queue (its result pump ran only in
request mode), so the packing thread's OUTPUT_READY message landed where the stepwise envelope
was expected; that is why the worker gate existed. Fixed in 7bf16aeb3: the executor starts its
pumps and reads synchronous replies from the pump buffer whenever asynchronous outputs can appear
(request mode, or step execution with the knob); validation re-queued, deploy config keeps the
knob off until it passes. The sibling's launch-time split (its measurement,
12 requests at persona length): 34-frame student forwards are GPU-bound (0.68-0.71 s wall,
0.41-0.43 s host issue), the 17-frame forwards and the commit forwards are launch-bound; student
CUDA graphs would save only 0.15-0.2 s and are not pursued; the LoRA delta is about 15-20 ms of
device time per forward (0.2-0.3 s per request), so the merged FP8 student set is worth more than
first estimated.

Status (session ffe817, 2026-09-28 14:25): **real time on two GPUs for the persona workload**
(measured locally, 30 requests, 332-340-token prompts with a new prompt every request, all
levers on incl. the twin's `step_async_output`): 4.87 s per 4.958 s request (max 4.99),
real-time factor 0.98, 1.0 s gained over 30 requests. The 100-request confirmation on the same
server averaged 4.99 s (factor 1.007): it gained 0.7 s over the first 50 requests and lost 5.7 s
over the next 50 while the shared host's load average was 35; the device-bound stages were
unchanged and only host-side parts grew (frame fetch/packing +0.04 s per phase, launch +0.02 s),
so the margin is real on a quiet host and gone under CPU contention from other users' jobs.
Short prompts: 4.78 s (factor 0.96, twin's measurement). Contributions this round at persona
length: text-encoder graphs (re-encode 0.15-0.27 -> 0.048 s), 64-token text buckets (-0.26 s),
fused LoRA hooks + AdaLN cache off (with the buckets), host preparation overlapped with the
decode (noise-level), `step_async_output` (-0.18 s: inter-phase gap and the following phase's
host side). Measured and dropped: student CUDA graphs (device-bound forwards), decode on a
second stream (no gain). Margin is 2%; the remaining device-time lever if more margin is wanted
is the LoRA delta (0.2-0.3 s per request, a merged FP8 student weight set, twin's item).

## Quality finding: the 480 px decoder tile (2026-09-28/29)

The owner reported blurred, low-quality video from the two-GPU server. Frames extracted from the
captured streams (PyAV) and reviewed independently by a second model show a uniform 16 px
lattice over the whole frame, deformed faces and smeared texture in every run that used
`taomate_h3_vae_decoder_tile_size: 480`, from the first chunk on, while the eager BF16 baseline
and the release runtime are clean. Four isolation runs on one persona prompt (measured locally):
BF16 without the tile clean; BF16 with the tile lattice; per-channel FP8 (50 blocks, boundary
projections in BF16) without the tile clean and sharp; the same with the tile lattice. The
lattice has the VAE's 16 px stride: the checkpoint's decoder cannot be tiled at 480 px (its own
256 px tiles are correct; `klvae.py` `split_tiles` itself is sound, the mechanism is deeper in
the decoder and was not traced). Fix: the deploy config drops the tile knob and uses per-channel
FP8 (worktree ef8dc3f8b, factory builder 843551b6b). Consequence: every two-GPU real-time figure
of D-036 (4.87-5.05 s per request) was measured on the broken decode; with the correct decode the
VAE costs 0.36 s per 34-frame phase again and a persona-length request takes about 5.4 s
(real-time factor 1.09). D-036 is therefore back to "not met for persona prompts"; the next lever
must be a correct VAE speedup. Comparison page: https://claude.ai/artifact/Q8C5SAv4Ricd5EYbREokht
