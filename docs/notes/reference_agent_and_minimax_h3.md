# Reference live agent (twitch.tv/sylar_nv) and MiniMax H3: evidence notes

Compiled 2026-09-25 (local, UTC+8). Web accesses were made 2026-09-24 17:25–17:40 UTC.
This was a read-only pass: no repos were modified, no GPU jobs were run and no model weights
were loaded. Safetensors *headers* were parsed for tensor shapes only.

Status labels:
- **verified**: seen directly in a primary source (official page, API response, local file).
- **observed**: seen directly in public VOD media or chat replay. This is behaviour only; nothing
  about the implementation follows from it.
- **secondary**: reported by a third party and not checked against a primary source.
- **unverified**: an owner or hearsay claim with no public evidence found.

---

## Part 1: Reference live agent `sylar_nv`

### 1.1 Provenance claim
- The project owner says the agent was built by a friend and is "based purely on MiniMax H3".
  **Unverified.** Nothing public (channel description, panels, socials, titles) names the model or
  the builder. One chat-replay line from a viewer asks "你是啥模型" ("what model are you?"). The
  answer was not checked because it would need ASR of the audio.
- Some observations fit an H3-based video path but do not prove one:
  - The VOD source rendition is 960x544 at 24 fps. The upstream vLLM-Omni H3 recipe lists 960x544 at 24 fps as a native H3
    long-video shape, and H3 is fixed at 24 fps.
  - The earliest VOD thumbnails show a counter of the form "第 1698 段 · 13 秒" ("segment 1698 · 13 s").
    That fits sequential generation in clips of about 13 s. H3's default clip limit is 4–15 s.
  - Other 24 fps generators could produce the same features.

### 1.2 What was accessible and what was blocked

| Source | Result | Access time (UTC) |
|---|---|---|
| `https://www.twitch.tv/sylar_nv/about` (WebFetch) | Page shell only, content rendered by JS. No text extracted | 2026-09-24 ~17:30 |
| `https://www.twitch.tv/sylar_nv/videos` (WebFetch) | Page shell only, content rendered by JS | ~17:38 |
| Twitch public GQL `gql.twitch.tv/gql` with the public web Client-ID (curl, anonymous) | **Accessible**: user, VOD list, VOD chat replay, VOD playback token. `channel.socialMedias` failed with `IntegrityCheckFailed` | 17:30–17:33 |
| VOD HLS (`usher.ttvnw.net` → CloudFront `index-dvr.m3u8`, anonymous) | **Accessible**. 2 short excerpts (150 s + 80 s) downloaded from VOD 2881733191 for frame/audio inspection. Stored only in the session scratchpad, not in the repo | ~17:31–17:33 |
| twitchtracker.com/sylar_nv | HTTP 403 | ~17:36 |
| streamscharts.com/channels/sylar_nv | HTTP 403 | ~17:38 |
| sullygnome.com/channel/sylar_nv | HTTP 403 | ~17:38 |
| Web search `"sylar_nv" twitch` | No relevant hits. No media coverage, GitHub or X posts found | ~17:36 |
| Live stream | Offline at the time of access (`stream: null`) | 17:30 |

### 1.3 Public metadata (Twitch GQL, verified, 2026-09-24 17:30 UTC)
- login/display `sylar_nv`, user id `1542050203`. Account created **2026-09-18T19:19:12Z**.
- Followers: **4**. Not an affiliate or partner. Description: null. Panels: none. Stream title: empty.
  Category: none. Schedule: none. Clips: 0.
- Last broadcast id `316483758833` has `startedAt` 2026-09-23T10:31:30Z. The matching VOD 2881733191 has
  `createdAt` 07:34:48Z. The two timestamps disagree, and both are recorded here as returned.
- **43 archived VODs** (2026-09-18 → 2026-09-23), about **27.8 h** in total. Lengths range from 89 s to 17,572 s
  (about 4.9 h). View counts are 0–89. The top VOD is 2881733191 (10,597 s, 89 views).
  None of the VODs has a title or category.

### 1.4 Publicly observable behaviour (observed; VOD media plus chat replay)
Visual format changed over the week, based on VOD preview thumbnails:
- **Sep 18–19**: a science-explainer format voted on by chat. An overlay offers two questions, for example
  "!A 杯边水面为什么弯了?" ("!A why does the water surface curve at the cup's edge?") and
  "!B 冷杯子为什么会出汗?" ("!B why does a cold cup sweat?"), with vote counts and a segment counter "第 N 段 · 13 秒" ("segment N · 13 s").
  Chat replay shows the operator sending `!A`, `!B` and `!customized prompt`.
- **Sep 20**: one thumbnail shows a bearded man in a cap in a room, framed like a webcam.
- **Sep 21–23**: a persistent persona. A young woman in a green Hanfu-style robe sits reading at a desk in a
  classical Chinese study. The desk holds a teapot, pastries, an incense burner, a book labelled "CUDA" and
  a sketched portrait on the wall, with a lotus pond seen through the window.
  An overlay reads "互动指南 / 默认静读 · !ask 点播互动" ("Interaction guide / silent reading by default · !ask for on-request interaction"), with example commands
  (!ask 今天读到什么故事? / 给我讲讲 CUDA / 翻一页书 / 点点头 / 挥挥手 / 喝口茶 / 吃一口龙须酥; that is,
  what story did you read today? / tell me about CUDA / turn a page / nod / wave / have a sip of tea / eat a piece of dragon's-beard candy).

Behaviour seen in VOD 2881733191 (offsets are chat-replay `contentOffsetSeconds`):
- **Idle mode**: silent reading with small natural motions such as page turns and a steaming incense burner.
  Audio is near the ambient floor, about −52 dBFS RMS.
- **Responds to chat instructions**:
  - An operator message "喝口茶" ("have a sip of tea") at 5227 s was followed by a viewer's "!ask 喝口茶" at 5229 s.
    The persona is seen lifting a teacup and drinking at about 5244–5246 s, which is roughly **15–20 s** after
    the message. A second drink appears at about 5270 s.
  - Loud vocal audio (−15 to −12 dBFS) starts at about 5288 s. The candidate trigger is a viewer's "唱首歌吧"
    ("sing a song") at 5252 s, but the link to any one message was **not** confirmed because no ASR was run.
  - Within the 150 s talking excerpt (5380–5530 s), speech is nearly continuous, with 1–2 s pauses and lip
    motion consistent with speech.
- **Other requests seen in chat replay**:
  - Physical actions: close or open the window, stand up, wave, nod, cry, shake your head.
  - Content: tell a story, sing a (love / break-up / English) song, explain CUDA or RDMA.
  - Scene edits: change clothes, background or the view outside the window.
  - Identity questions: who are you, what model are you.
  - Some viewers posted inappropriate or sexualised requests. The system's handling of them was not
    examined.
  - A viewer remarked that the singing had become electronic ("上电音了").
  - Whether each request was honoured was **not** systematically checked.
- **Visual consistency**: identity, costume and set stay stable across a 150 s talking excerpt.
  One discontinuity was seen at about 5280–5288 s, where the background switches to a bookshelf, the framing
  changes and then the scene returns. This looks like a clip-boundary or scene-regeneration artefact, but the
  cause is unknown.
- **Memory of viewers**: no evidence either way. It would require ASR of the responses and repeat-visitor
  probes.
- **Audio/stream spec**: H.264 960x544 at 24 fps and AAC 48 kHz stereo. This is the Twitch transcode; the
  source quality was capped at FULL_HD for anonymous viewers.

### 1.5 What a fair quantitative comparison would need
1. **Recorded VODs with exact timing**: VOD download works anonymously today, but retention is limited
   (Twitch deletes archives after a few days for non-affiliates). Snapshot the VODs now. Align chat
   offsets to the video PTS with a known marker, because chat offsets and video time were not validated here.
2. **Controlled prompt script**: a fixed set of instructions (actions, Q&A, songs, scene edits, repeat-viewer
   memory probes, adversarial or unsafe requests), sent at scheduled times from a dedicated test account,
   ideally with the operator's consent.
3. **Operator cooperation**: confirm the model stack (e.g. whether it is really H3 alone; which TTS and LLM
   are used, if any), the hardware, the resolution and steps, and whether clips are pre-generated or queued.
   Without this, only black-box latency and quality can be compared.
4. **Metrics** that apply to both systems:
   - instruction-to-onset latency, measured with ASR and action detection on the video;
   - instruction success rate, judged by humans or a VLM;
   - lip-sync, measured with SyncNet-style scores;
   - identity drift over hours, measured with face-embedding similarity;
   - audio quality;
   - uptime and rate of stalls or discontinuities;
   - accuracy on viewer-memory probes.
5. **Ethics**: the operator's consent before publishing analysis of their stream, and viewer handles
   anonymised. This note records no viewer identities.

---

## Part 2: MiniMax H3

### 2.1 What it is (verified from official sources)
- MiniMax H3 is an **open-weight, omni-modal joint video and audio generation model**, a diffusion transformer.
  It is **not an LLM** and it is **not marketed as a world model**. MiniMax describes it as "a general-purpose,
  omni-modal generative system" that understands text, image, video and audio context and generates
  "video with native stereo audio at resolutions up to 2K and durations of up to 15 seconds".
- **Announced 2026-07-31** in the MiniMax blog post "MiniMax H3: An Open Model Breaking the Boundaries
  Between Tasks and Modalities". It is the successor to Hailuo 01 and Hailuo 02.
  - The weights were published to Hugging Face on about **2026-08-03**, according to secondary sources.
  - The HF API reports the repo `createdAt` as 2026-07-28T10:45Z and `lastModified` as 2026-08-13.
  - The HF API reports `gated: false`. The vLLM-Omni recipe says access approval is required, which conflicts.
- **License**: the "MiniMax H3 Community License Agreement". It is not OSI-approved.
  - The Applicable Territory **excludes the EU, UK, Republic of Korea and USA**.
  - Commercial products above **$20M yearly revenue** need a separate written authorization.
  - Commercial user interfaces must display "MiniMax H3".
  - Outputs may not be used to improve other AI models.
  - This is a relevant constraint for a US, EU, UK or Korean deployment of the proposal.
- **Size and architecture** (model card and GitHub README):
  - H3-Omni-Transformer: a 33B dense single-stream DiT (about 13B of it in AdaLN branches) with 3D MM-RoPE.
  - Text/multimodal encoder: Qwen3-VL-32B (layer-50 output).
  - VisualVAE: causal, 16x spatial and 4x temporal compression, 24 channels.
  - Stereo AudioVAE: 40 Hz latent rate.
- **Tasks**: T2VA (text), FL2VA (first/last keyframe), and Ref2VA (up to 9 images, 3 videos and 3 audios as
  references). There are two task-specific checkpoint partitions.
- **Output**: 24 fps, 4–15 s by default, a short side of 768 px (up to 2K via "In-context Regeneration";
  the 2K regenerator is reported not open-sourced, secondary source) and 32 kHz stereo audio.
  Aspect ratios are 21:9, 16:9, 4:3, 1:1, 3:4 and 9:16. The card lists 11 languages.
- **Streaming or real-time**: there is **no official claim** of streaming, real-time or camera control.
  Camera control exists only through third-party adapters (SolarWM, below).
- **Latency and hardware**: there are no official numbers. Community vLLM-Omni measurements, all offline and
  none real-time:
  - 4x H200, 1344x768, 124 frames (about 5.2 s), 50 steps: 85.5 s median.
  - 4x B300, FL2VA 209 frames at 1248x768: about 87 s.
  - 4x MI300X, 209 frames: about 267–287 s end to end.
  - 2x RTX 5090 with offload, 124 frames: 8 min 38 s.
  - About 134 GiB of BF16 per partition.
  - Few-step adapters exist: FastH3, a 4-step DMD2 student, and LightX2V Turbo LoRAs.

### 2.2 Local checkpoint inspection (verified, read-only)
Path: `/data/zhoutaichang/worldmodel/MiniMax-H3/FL2VA/`

| Component | Local size (`du -sh`) | Evidence | Estimated params |
|---|---|---|---|
| transformer (`MiniMaxH3DiTModel`) | **4.9 G: only shard 1 of 13 present** | index `total_size` = 66,280,430,144 B. Config: hidden 5376, 50 layers, 56 heads × 128 (attention inner dim 7168), FFN 14336 (fc1 is 28672, gated), adaLN 2688→96768, 2 token-refiner layers, `text_dim` 5120, video latent 24, audio latent 32, patch (1,2,2) | Per block about 645.5M (adaLN 260M, qkv 116M, out 38.5M, MLP 231M), so 50 × 645.5M ≈ 32.3B, plus 0.77B refiner. That gives **≈33.1B**, consistent with 66.3 GB of mostly-bf16 weights and the card's "33B / 13B AdaLN" |
| video_vae (`AutoencoderKLLegacy`, remote code) | 9.8 G | fp32, 2.604B params (from the header). Causal 3D-conv encoder, 36-layer ViT decoder. `vae_ratio` 16, `vae_ratio_t` 4, `vae_clip_length` 17, 24 channels | ≈2.6B |
| audio_vae (DAC encoder + BigVGAN decoder) | 578 M | fp32, 0.151B params. Sample rate 32 kHz, 2 channels. Encoder rates 2·4·4·5·5 = 800, giving a **40 Hz** latent | ≈0.15B |
| processor / tokenizer | 11 M each | `Qwen3VLProcessor`, `Qwen2TokenizerFast` | – |
| text_encoder | **absent locally** | `model_index.json` names `MiniMaxH3Qwen3VLHFEncoder`, and `text_dim` 5120 fits Qwen3-VL-32B | ≈32–33B (not measured locally) |

`model_index.json`:
- `_class_name` is `MiniMaxH3Pipeline`.
- Partition `fl2va`, tasks `["t2va","fl2va"]`.
- Sigma shift scales: video 12.0, audio 3.0.

**The local FL2VA copy is incomplete.** 12 of the 13 DiT shards and the text encoder are missing, so this
directory cannot run inference as-is.

### 2.3 Inputs and outputs, as used locally (`/data/zhoutaichang/worldmodel/H3-Demo/`)
- Plan files: `h3-{control,final,speed,stream-30s,test}-plan.json`.
  - Each entry has `key`, `num_frames`, `fps: 24.0`, `caption`, `image`, `camera` and `prompt`, plus sha256 values.
  - Horizons are 240 frames (10 s), 720 frames (30 s) and 2880 frames (120 s).
- Inputs:
  - One keyframe, `cases/source.image.png`, 1344x768 RGB.
  - A text prompt, `cases/source.prompt.txt`, describing a forward walk beside a wheat field.
  - A camera track, `cases/*.camera.npy`: a **float64 array of shape `[N, 4, 4]`, one 4x4 pose per output frame**.
    - Frame 0 is `diag(-1,-1,1,1)`, and later frames carry metric translation.
    - The SolarWM recipe defines these as camera-to-world matrices in OpenCV axes with metric translation,
      rebased to frame 0, with the rebased translation kept under 20 m.
    - There is no audio input in these plans.
- Base H3 output: an MP4 with H.264 video at 24 fps and 32 kHz stereo AAC.
  SolarWM-H3 output: **video only**. The audio branch is fed encoded silence and its output is discarded.
- Frame grid:
  - 17n+5 video frames map to 5n+2 video latents; audio latents are at 40 Hz.
  - The VAE temporal clip is 17 frames.
  - The SolarWM Stage-2 chunk is 5 latent frames, i.e. 17 pixel frames, about 0.71 s at 24 fps.

### 2.4 Chunking and streaming support
- **Upstream vLLM-Omni main** (`/data/zhoutaichang/live-agent/external/vllm-omni`, commit `7b4dc7633`,
  2026-09-25) **already contains MiniMax-H3 support**: `vllm_omni/diffusion/models/minimax_h3/`, the `MiniMaxH3Pipeline`,
  and the recipe `recipes/MiniMaxAI/MiniMax-H3.md`. It includes:
  - a temporal-chunk VAE decode with a frames-only callback (`temporal_chunks.py`, `chunked_decode.py`; PR #7017);
  - streamed-video encoding on the worker (PR #7018) and streaming fMP4 output;
  - long-video latent continuation up to 300 s (`long_video=true`, `continuation.py`);
  - `audio_mode=lock_source`, which drives generation with a given soundtrack;
  - FastH3 (4-step) and Turbo LoRA adapters;
  - an AR-diffusion session with streaming VAE decode (PR #6533, generic).

  These are chunked or offline generation paths. None is documented as real-time.
- **SolarWM-H3 camera-controlled world-model integration**: **not in upstream main**. It exists only as
  **uncommitted working-tree changes** in `/data/zhoutaichang/worldmodel/vllm-omni`:
  - The branch is `feat/solarwm-h3-experimental`. HEAD is `e284d907` (2026-09-13), which is an
    upstream-main commit and an ancestor of `7b4dc76`, 273 commits behind it. The branch has no commits of its own.
  - Untracked files:
    - `vllm_omni/experimental/world_models/solarwm_h3/{camera,pipeline_solarwm_h3,sgf,weights}.py`
    - `vllm_omni/diffusion/models/minimax_h3/camera_prope.py`
    - `vllm_omni/model_extras/solarwm_h3.py`
    - `recipes/SolarWM/SolarWM-H3.md`
    - `tests/experimental/world_models/solarwm_h3/*`
  - Modified files: `minimax_h3_transformer.py` (+94 lines), `registry.py`, `model_metadata.py`,
    `model_extras/registry.py` and the docs.
  - Behaviour per the recipe:
    - Adapter weights: `junchaoh-cs/SolarWM-H3-33B`.
    - **Stage0.5** is a bidirectional adapter producing a fixed 158 frames with 29 Euler steps, run with TP=2.
    - **Stage2** is a causal "self-gradient-forcing" student. Each chunk is 5 latent frames (17 frames) from
      4 denoiser evaluations, with a KV cache over the last 5 chunks (about 31 GiB bf16). Any length N ≥ 22 poses
      is accepted, including the 2880-frame, 2-minute demo.
    - Validated on an L20X 140 GiB; Stage2 can run on 1 GPU.
    - The recipe states "Speed is not a goal of this integration".
    - The adapter is a rank-384 LoRA folded into the weights at load time.
  - Other related branches on origin: `codex-minimax-h3-vendor-callback`, `perf/minimax-h3-adaln-cache-offload`,
    `perf/minimax-h3-lossless-hot-path`.

### 2.5 Implications for the proposal (analysis, not evidence)
- H3 gives joint video, audio and speech with lip-synced stereo from a single 33B DiT. That is attractive for a
  persona, but it runs offline at tens of seconds or more per 5 s clip on 4 high-end GPUs. A live agent built
  on "pure H3" must therefore pre-generate or queue clips, or use few-step or causal students (FastH3,
  SGF-style chunking). The roughly 15–20 s action latency seen on sylar_nv fits such a design but does not confirm it.
- The license territory exclusion matters for deployment location.

---

## Evidence table

| Claim | Source | Access date | Status |
|---|---|---|---|
| sylar_nv is "based purely on MiniMax H3", built by the owner's friend | project owner (verbal) | 2026-09-25 | unverified |
| Channel created 2026-09-18T19:19Z, 4 followers, no description/panels/schedule, not affiliate | Twitch GQL `user(login:"sylar_nv")` | 2026-09-24 17:30 UTC | verified |
| 43 VODs, 2026-09-18 to 09-23, ≈27.8 h total, max 89 views | Twitch GQL `videos(first:100)` | 2026-09-24 17:31 UTC | verified |
| Offline at access time | Twitch GQL `stream: null` | 2026-09-24 17:30 UTC | verified |
| VOD rendition 960x544 at 24 fps, AAC 48 kHz stereo | usher master playlist + ffprobe, VOD 2881733191 | 2026-09-24 17:31 UTC | verified |
| Persona format (classical study, `!ask` overlay, idle reading) | VOD 2881733191 frames at 5220–5530 s; thumbnails of VODs 2879089351, 2880014406, 2880966445, 2881093241 | 2026-09-24 17:32 UTC | observed |
| Early A/B chat-vote explainer format with "第N段 · 13秒" counter | thumbnails of VODs 2877689483, 2878248559; chat replay `!A`/`!B` | 2026-09-24 17:34 UTC | observed |
| Performs requested tea-drinking about 15–20 s after the chat message | VOD 2881733191 chat offsets 5227/5229 vs frames at about 5244 s | 2026-09-24 17:33 UTC | observed (single sample; offset alignment unvalidated) |
| Continuous speech with lip motion during talking mode | VOD 2881733191, 5380–5530 s; audio RMS | 2026-09-24 17:31 UTC | observed (content not transcribed) |
| Viewer memory | – | – | gap (not assessable) |
| twitchtracker / streamscharts / sullygnome stats | respective URLs | 2026-09-24 17:36–17:38 UTC | blocked (HTTP 403) |
| No media coverage or socials found | WebSearch `"sylar_nv" twitch` | 2026-09-24 17:36 UTC | verified (absence in search) |
| H3 announced 2026-07-31; omni-modal video + native stereo audio, ≤15 s, 2K | https://www.minimax.io/blog/minimax-h3 | 2026-09-24 | verified |
| H3 is 33B DiT (~13B AdaLN), Qwen3-VL-32B encoder, VAE 16x/4x/24ch, AudioVAE 40 Hz; T2VA/FL2VA/Ref2VA; 24 fps, 4–15 s, 32 kHz stereo | https://huggingface.co/MiniMaxAI/MiniMax-H3 ; https://github.com/MiniMax-AI/MiniMax-H3 | 2026-09-24 | verified |
| HF repo createdAt 2026-07-28, lastModified 2026-08-13, gated false, license tag `minimax-h3-community-license-agreement` | https://huggingface.co/api/models/MiniMaxAI/MiniMax-H3 | 2026-09-24 | verified |
| Weights published about 2026-08-03 | https://aiweekly.co/alerts/minimax-posts-h3-a-33b-omni-modal-video-model-to-hugging-face ; MarkTechPost 2026-08-01 | 2026-09-24 | secondary |
| License excludes EU/UK/Korea/USA; >$20M revenue needs authorization; "MiniMax H3" attribution; no training other models on outputs | https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE | 2026-09-24 | verified |
| No official streaming/real-time/camera-control claim | H3 blog, model card, GitHub README | 2026-09-24 | verified (absence) |
| 2K regenerator / Context-IR not open-sourced | aiweekly (above) | 2026-09-24 | secondary |
| Local DiT ≈33.1B params (66.28 GB index; per-layer shapes) | `/data/zhoutaichang/worldmodel/MiniMax-H3/FL2VA/transformer/{config.json,model.safetensors.index.json}` and shard-1 header | 2026-09-25 | verified (computed) |
| Local copy incomplete (1/13 DiT shards, no text_encoder) | `ls`/`du -sh` of the same dir | 2026-09-25 | verified |
| Video VAE 2.6B fp32; audio VAE 0.15B fp32, 32 kHz stereo, 40 Hz | `video_vae/source/config.json`, `audio_vae/{config.json,metadata.json}` + headers | 2026-09-25 | verified |
| Camera input = float64 `[N,4,4]` per-frame c2w; 24 fps; 240/720/2880 frames; 1344x768 keyframe | `/data/zhoutaichang/worldmodel/H3-Demo/{*.json,cases/}`; SolarWM recipe | 2026-09-25 | verified |
| H3 support + chunked decode/long-video continuation in upstream vLLM-Omni main 7b4dc76 | `/data/zhoutaichang/live-agent/external/vllm-omni/{vllm_omni/diffusion/models/minimax_h3/,recipes/MiniMaxAI/MiniMax-H3.md}` | 2026-09-25 | verified |
| Community H3 latencies (H200 85.5 s / B300 87 s / MI300X ~270 s / 2x5090 8m38s) | same recipe | 2026-09-25 | secondary (community measurements) |
| SolarWM-H3 integration only as uncommitted changes on `feat/solarwm-h3-experimental` (HEAD e284d907) | `git -C /data/zhoutaichang/worldmodel/vllm-omni status/log` | 2026-09-25 | verified |
| SolarWM paper (arXiv 2609.02886, 2026-09-02) builds on H3, Wan2.2, LTX-2.5 | https://arxiv.org/abs/2609.02886 | 2026-09-24 | verified |
