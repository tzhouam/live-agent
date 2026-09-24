You are GPT-6 Sol acting as the INDEPENDENT REVIEWER for this project (see AGENTS.md). Checkpoint 1 of 4: project understanding, requirements, and assumptions. Reviewed revision: git commit ef3a0f3 of this repo.

Read `goal.md` (the owner's brief), `docs/PROJECT.md` (our provisional spec), `CLAUDE.md`, `AGENTS.md`, `AGENT.md`.

Additional initial observations by the author (Claude), for you to challenge:
- Upstream vLLM-Omni main cloned read-only at `external/vllm-omni`, commit 7b4dc7633bde (2026-09-24). It contains `vllm_omni/diffusion/models/lingbot_world/`, `vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`, `recipes/Robbyant/LingBot-World-2.0.md`, `docs/design/feature/realtime_ar_diffusion.md`, `docs/serving/streaming_video_output_api.md`, `examples/online_serving/streaming_video_generation/`, `benchmarks/lingbot_world/`. Detailed analysis is in progress (not yet available to you).
- Hardware: 8x NVIDIA L20X (~140 GB each), shared, scheduled via canhazgpu.
- A local copy of "MiniMax H3" appears at /data/zhoutaichang/worldmodel/MiniMax-H3/FL2VA (subfolders transformer, video_vae, audio_vae, processor incl. camera .npy files) — suggesting it may be a joint audio+video model with camera conditioning. Unverified.
- Codex CLI 0.156.0; `codex exec -m gpt-6-sol` verified via session rollout recording "model":"gpt-6-sol". The Codex MCP server failed to connect in the Claude session; the CLI is used instead.

Please critique:
1. Does docs/PROJECT.md faithfully capture goal.md? List any requirement missed, weakened, or distorted.
2. Are the assumptions / open questions the right ones? What material assumptions are missing (e.g., about the demo scenario, audience, persona, speech, safety, hardware, what "real-time" means)?
3. Is the instruction-file structure (single spec + thin pointers) sound, and are the files consistent?
4. Is the Codex review procedure auditable enough? What should be recorded that isn't?
5. What early risks or framing errors should be fixed before the literature review and architecture work proceed? In particular, challenge the working hypothesis framing and the scoping of the demo.
Output a numbered list of findings, each tagged blocking/major/minor with suggested fix. Be concise and concrete. Do not edit files.
