# TaoMate-H3 as a candidate base model: evidence and fit

Compiled 2026-09-25 in response to the owner's question. Web sources were accessed 2026-09-25. Nothing was run
locally, so every number below is **[cited]** from the source named in its row, or is marked **[estimate]**.

## What it is (verified)

| Claim | Source | Status |
|---|---|---|
| TaoMate-H3 = MiniMax H3 (FL2VA) + a **3-step LoRA** (rank 128, α 128, step-3000 EMA) + TaoLive's own streaming runtime (`python -m taomate_h3`) | github.com/TaoLiveAIGC/TaoMate-H3; huggingface.co/TaoLiveAIGC/TaoMate-H3 | cited |
| Released 2026-09-08. **Only T2AV is available now.** FL2AV is promised "before 26/10/15"; Ref2AV is TBD | same | cited |
| Prompting: one prompt per **5-second block**, given as a single prompt or a JSON list. **No interactive, WebSocket or mid-stream API is documented** | same | cited |
| Generates speech, sound and video on one timeline (joint audio-video). No documented control of voice identity | same | cited |
| 8×H20 96 GB (TP2 × Ulysses4), 480×864, 10 s output: first playable video **17.29 s**; DiT time **14.81 s**; first final chunk latent **6.15 s**; peak memory 31.4 GiB. Longest tested output: **10 s** | same | cited |
| Requires Hopper/SM90, CUDA 12.8, PyTorch 2.8. Single node only. **No vLLM, vLLM-Omni or SGLang support mentioned** | same | cited |
| License: **MiniMax H3 Community License**. It excludes the EU, UK, Republic of Korea and the US as territories; commercial use above $20M revenue needs separate authorization; "MiniMax H3" attribution is required; outputs may not be used to train other models | same; `docs/notes/reference_agent_and_minimax_h3.md` | cited |

**Do not conflate it with the TaoMate paper** (arXiv 2607.24359, 2026-07-27). The paper's headline numbers are
"35 FPS on 3 GPUs, > 30 min". Those numbers are for a **22.1B LTX-2.3-initialized** model at 768×512, not H3.
That model's memory design:
- an immutable visual anchor;
- a fixed-capacity compressed audio/video state (48 video + 64 audio tokens);
- per-segment prompts carrying action, transcript, appearance, scene, camera and voice.

These numbers must not be attributed to TaoMate-H3.

## Local state (read-only check, 2026-09-25)

- **Weights.** The shared `/data/models/hub/models--MiniMaxAI--MiniMax-H3` (272 GB) has FL2VA and Ref2VA, each with
  `text_encoder/` and `transformer/`. Completeness was not hashed. The copy under `/data/zhoutaichang/worldmodel`
  is incomplete. The FastH3 4-step and lightx2v Turbo LoRAs are also present.
- **vLLM-Omni `7b4dc76` supports H3 as a clip model**: step execution, chunked decode, continuation, LoRA, FastH3.
  - It has **no interaction-registry entry** for H3.
  - It has **no causal streaming path** of the TaoMate kind, and there is no TaoMate code.
- **GPU risk.** TaoMate-H3 requires SM90, but NVML reports the local cards as compute capability 8.9 (D-008).

## Fit for the live-agent goal

| Need | TaoMate-H3 | LingBot-World 2.0 (current backbone) |
|---|---|---|
| Visible speaking persona, lip sync, voice | **Native** (joint audio-video) | None (class D) |
| Character behaviour by instruction | Per-block text: action and transcript | Camera only mid-stream; prompts need C1 |
| Camera / world control | Text only; no pose control | SE(3) camera, verified in code |
| Control granularity | 5 s block | 0.75 s chunk (12 frames @ 16 fps) |
| Mid-stream API | None documented (JSON script up front) | WS `session.interaction` |
| Real-time evidence | Slower than real time on 8×H20 (14.8 s DiT for 10 s) | ≈0.55 s per 0.75 s chunk on 4×H200 (upstream) |
| Identity across a session | H3 T2AV has no reference image until FL2AV/Ref2AV | First-frame image |
| Relation to the reference agent | Same H3 family as the owner-described stack | Different family |

## Estimates (not measured)

- **Compute.** H200 has about 6.7× the dense BF16 compute of H20 (≈989 vs ≈148 TFLOPS, vendor specs). If TaoMate-H3
  is compute-bound, a 5 s block might take about 1–2 s on 8×H200-class GPUs. That would be real time, but it is an
  unverified extrapolation.
- **Instruction-to-visual latency with 5 s blocks.** TVC ≈ A + U(0, 5 s) + (L+1) × 5 s + I, i.e. **≈ 6–11 s** even
  on fast hardware. That is about 3–5× LingBot's illustrative ≈ 2 s.
- **Barge-in.** Speech is generated inside the block, so the persona cannot be cut off mid-block without discarding
  the block's audio.

## Smallest experiments to settle it

1. Inside a `gpu run` reservation: `torch.cuda.get_device_capability()`. SM90 or not decides whether TaoMate-H3's
   kernels can run at all.
2. `gpu run --gpus 8 --timeout 1h -- python -m taomate_h3 …` for a T2AV 10 s run. Measure time to first playable,
   RTF, and memory, and compare with the model card.
3. A per-block prompt-switch test: block 1 "talking", block 2 "waves and says X". Judge onset and compliance on the
   output, and check voice and identity continuity across blocks.
4. After FL2AV is released (announced for ≤ 2026-10-15): check reference-image identity preservation over ≥ 60 s.
