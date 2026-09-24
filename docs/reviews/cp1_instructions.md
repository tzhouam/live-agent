You are GPT-6 Sol acting as the INDEPENDENT REVIEWER for the "live-agent" research project. Checkpoint 1 of 4: project understanding, requirements, and assumptions. Reviewed revision: git commit ef3a0f3 (files inlined below). Do not edit any files.

Additional initial observations by the author (Claude), for you to challenge:
- Upstream vLLM-Omni main cloned read-only at external/vllm-omni, commit 7b4dc7633bde (2026-09-24). Its recipe recipes/Robbyant/LingBot-World-2.0.md states: only checkpoint robbyant/lingbot-world-v2-14b-causal-fast-diffusers is supported (CC BY-NC-SA, non-commercial); 4 DMD steps; validated on H200/B200 at 480x832; public realtime path is `WS /v1/realtime/video` (stepwise, one request per rollout, one fMP4 chunk per AR block of 3 latent frames = 12 raw frames); mid-session control is structural SE3 camera (`session.interaction`, target/velocity modes); prompt switching is validated in the (deprecated) tick path; max_num_seqs=1, single replica; stateful streaming VAE decode not implemented (seams possible). A detailed code-level analysis is in progress.
- Hardware: 8x NVIDIA L20X (~140 GB each), shared, scheduled via canhazgpu (no guaranteed allocation).
- A local copy of "MiniMax H3" is at /data/zhoutaichang/worldmodel/MiniMax-H3/FL2VA (subfolders transformer, video_vae, audio_vae, processor with camera .npy files) — possibly a joint audio+video model with camera conditioning. Unverified; provenance and license unknown.
- Codex CLI 0.156.0; `codex exec -m gpt-6-sol` verified via the session rollout recording "model":"gpt-6-sol". The Codex MCP server failed to connect; the CLI is used. The shell sandbox cannot start on this host, so material is inlined.
- A prior attempt of this checkpoint failed because the reviewer could not read files; its provisional findings were: (a) test the working hypothesis against competing approaches rather than selecting an architecture early; (b) define an explicit acceptance scenario and measurable "real-time"; (c) model/hardware feasibility unverified; (d) record full audit metadata per review. You may confirm, refine, or reject these.

Critique:
1. Does docs/PROJECT.md faithfully capture goal.md? List any requirement missed, weakened, or distorted.
2. Are the assumptions / open questions the right ones? Which material assumptions are missing?
3. Is the instruction-file structure (single spec + thin pointers) sound and consistent?
4. Is the review procedure auditable enough?
5. Early risks or framing errors to fix before literature and architecture work (working hypothesis framing; demo scoping; the fact that LingBot-World is a camera-controlled world model rather than an avatar model).
Output a numbered list of findings, each tagged blocking/major/minor with a concrete suggested fix. Be concise.
