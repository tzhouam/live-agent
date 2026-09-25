# Google's long-form agentic video suite (Co-Director, CANVAS, A²RD, VQQA): evidence notes and what transfers to a live agent

Compiled 2026-09-25. This was a read-only pass. No GPU jobs were run and no repos were modified.

**Sources read (full text, arXiv HTML v1, fetched 2026-09-25):**
- Blog: "Automating coherent long-form video generation", Yale Song and Yiwen Song, Google Research, 2026-09-24.
  https://research.google/blog/coherent-long-form-video-generation/
- Co-Director: arXiv 2604.24842v1 (27 Apr 2026). https://arxiv.org/html/2604.24842
- CANVAS: arXiv 2604.13452v1 (15 Apr 2026). https://arxiv.org/html/2604.13452
- A²RD: arXiv 2605.06924v1 (7 May 2026). https://arxiv.org/html/2605.06924
- VQQA: arXiv 2603.12310v1 (12 Mar 2026). https://arxiv.org/html/2603.12310

All four HTML full texts, appendices included, were accessible. Figures were not viewed (images only),
so any claim that exists only inside a figure is marked **unverified**. The papers' code releases and
project pages were not checked. Where these notes say "derived", the value was computed from numbers in
the paper and was not stated there. Quotations are verbatim from the HTML.

Status labels, as in the other notes in this folder:
- **verified**: stated in the paper or blog text.
- **derived**: my arithmetic from stated numbers.
- **unverified**: not found, or only visible in a figure.
- **proposal**: my own design suggestion for the live agent. None of the papers supports it.

---

## 0. The blog in one paragraph

The blog presents the four papers as "a suite of frameworks" that "translate high-level human creative
specification into execution by automating repetitive orchestration tasks, from multi-model prompting
and shot chaining to closed-loop visual refinement". The suite is "Built as an orchestration layer on top
of Gemini and Veo" and "decouples creative synthesis from consistency by modeling quality as a
test-time objective". The pillars are:
1. **Co-Director**: global creative planning by a multi-armed bandit (MAB). The blog says it will
   appear at COLM 2026.
2. **CANVAS**: a world-state storyboard with persistent visual memory. The blog says it will appear
   at EMNLP 2026.
3. **A²RD**: segment-by-segment autoregressive video with a multimodal memory and switching between
   extrapolation and interpolation.
4. **VQQA**: closed-loop prompt optimisation using VLM questions as "semantic gradients".

For future work, the blog says "we are exploring how to integrate human-in-the-loop workflows".
Nothing in the blog is real-time or streaming.

The blog's benchmark summary contains one discrepancy with the papers. The blog says LVBench-C "contains 120
text-only scenarios". The A²RD paper says 120 in its text, but Table 1 lists "125 / 5200" and the
per-length split is 50 + 50 + 25 = 125 (see §3.4).

---

## 1. Co-Director: Agentic Generative Video Storytelling (arXiv 2604.24842)

Authors: Yale Song, Yiwen Song, et al. (all Google Inc.; last author Tomas Pfister; corresponding author yalesong@google.com). Project page:
https://co-director-agent.github.io/ (not opened).

### 1.1 Architecture (§3.1, Fig. 1)
The paper frames video storytelling "as a global optimization problem" with "hierarchical
parameterization: a multi-armed bandit globally identifies promising creative directions, while a local
multimodal self-refinement loop mitigates identity drift" (Abstract).

| Agent | Inputs | Outputs | Notes |
|---|---|---|---|
| Orchestrator Φ_orch | user prompt p_user, reference visuals I_ref | structured constraints p̂_user (brand, product, demographics); annotated references Î_ref (captions + semantic roles such as product, logo, protagonist); per-iteration context Θ^(t) = (p̂_user, Î_ref, θ^(t)) | "manages the global state and execution flow of all sub-agents"; runs the MAB for T iterations |
| Pre-Production Φ_pre | Θ | Creative Brief B ("deep research", cultural and environmental context), then Storyline L (scene-by-scene script), then Visual Assets V (generated only for entities not in the references; characters get "multi-angle reference collages"), then Storyboard S = {s_0..s_{N-1}} | each scene s_i has "semantic descriptors (actions, environment), camera kinematics (scale, movements), temporal constraints, and entity presence flags linked to V", plus global audio directives |
| Production Φ_prod: Keyframe Agent Φ_frame | s_i, V, θ | k_i (first-frame image) | Eq. 1: "establishes a visual prior by generating first-frame images to condition downstream synthesis" |
| Production: Video Agent Φ_video | s_i, k_i, θ | clip c_i | Eq. 2: an I2V diffusion model conditioned on the keyframe |
| Production: Audio Agent Φ_audio | S, θ | global track A | Eq. 3: global voice-over and music via TTS and text-to-audio, "Rather than per-scene generation" |
| Post-Production Φ_post | S, C, A | final video F | Eq. 4: concatenation plus audio multiplexing |
| MLLM Judge | F^(t), p_user, I_ref | aggregate quality score, factored reward R^(t) | App. K prompt |

**Models (§5 Implementation Details, verified):** "Gemini 3 Pro …, Nano Banana Pro …, Veo 3.1 …,
Gemini 2.5 Pro TTS …, and Lyria 2". The MLLM judge used for GenAd-Bench is Gemini 3 Pro (§4).

**Training:** none. Everything is prompting and orchestration over frozen API models. The paper does not
use the phrase "training-free"; this is inferred from the method description, which contains no
training step. The Hillclimbing split (App. D.3) is used for "iterative system optimization", meaning
prompt and design iteration, not weight training.

### 1.2 State/memory
There is no persistent memory module. State consists of the artefacts B, L, V, S, K, C, A and the
bandit's arm statistics. Cross-shot identity comes from (a) the Visual Assets V (multi-angle reference
collages), (b) keyframe conditioning, and (c) the joint keyframe critique described below.

### 1.3 Planning and optimisation
- **Local self-refinement (§3.2):** "feedback descent". Two loops:
  - Storyline: an LLM scores "hook quality, narrative cohesion, product integration, emotional
    engagement, and prompt adherence" and rewrites the prompt. The storyline is regenerated if the
    score is below τ_L.
  - Keyframes: "An MLLM evaluates the keyframe sequence K … jointly rather than individually". If the
    score is below τ_K, it "indexes problematic keyframes" so that Φ_frame can "selectively regenerate
    flagged keyframes while preserving accepted ones".
  - Each loop is capped at 3 retries (§5). The paper does not report the numeric values of τ_L and τ_K
    (**unverified**).
- **Global MAB (§3.3):**
  - "a single 'pull' corresponds to a full pipeline execution, the 'arms' are creative directions θ,
    and the 'reward' is the terminal video evaluation score."
  - Arms: θ = (θ_cs, θ_nm, θ_aa), all categorical:
    - Creative Strategy: Informational, Transformational or Comparative.
    - Narrative Mode: Analytical, Vignette or Narrative Drama.
    - Aesthetic Archetype: Clarity/Energy, Cinematic Premium, Minimalist Focus or Kinetic Grit. Each
      archetype bundles lighting, camera motion and audio style.
  - This gives 3 × 3 × 4 = 36 joint configurations, which App. F describes as "10 independent parameters".
  - Injection: "orchestrator Φ_orch centrally synthesizes θ^(t) into agent-specific instructions,
    dynamically injecting them into placeholders within the agents' system prompts."
  - Reward: the MLLM judge returns (1) an aggregate quality score, used only "to select the best video
    across T executions", and (2) "dimension-specific strategic efficacy scores", which form the
    factored reward R^(t) = (r_cs, r_nm, r_aa) ∈ [0,100]³.
  - The judge prompt (App. K) scores five execution criteria at 0–20 each: Coherence, Visual Quality,
    Engagement, Prompt Adherence, and Logical & Physical Consistency. It then scores three
    "Strategic Efficacy" values at 0–100 each, and these "must be directionally consistent with the
    execution scores". The judge also has to "Identify the Root Cause: Determine if the failure
    happened in the script (Storyline), the static frames (Image Gen), or the motion (Video Gen)".
  - Policy: UCB1. The paper "uses the disentangled scalars from R^(t) to independently update the
    expected value of each selected arm", which it claims "analytically bypasses the credit assignment
    problem".
  - Warm start: "an LLM analyzes the user's demographic and product domain to initialize the expected
    values of the arms".
  - Budget: T = 4 pulls (§5).

### 1.4 Results (verified)
- **GenAd-Bench** (the paper's own benchmark, §4): 50 fictional brands × 4 products × 2 demographics
  (stereotypical and unconventional) = 400 scenarios, split into 200 hill-climbing and 200 validation
  scenarios. All results are on validation. Assets were built with Gemini 3 Pro and Nano Banana Pro, and
  about 15% of product images were regenerated after manual checks. The judge is Gemini 3 Pro, scoring
  VAF, DA, MA and VQ on a 0–100 scale.
- **Table 1 averages:**

  | Method | Avg |
  |---|---|
  | Creatify | 22.1 |
  | HeyGen | 46.7 |
  | Kling 3.0 Omni | 58.4 |
  | Veo 3.1 | 63.6 |
  | Wan 2.6 | 65.0 |
  | LTX-2.3 | 33.6 |
  | AniMaker | 62.2 |
  | MovieAgent | 65.3 |
  | Base Agentic Pipeline (T=1) | 68.5 |
  | Random Search (T=4) | 75.7 |
  | **Co-Director (T=4)** | **81.4** (VAF 82.1, DA 91.4, MA 82.0, VQ 70.2) |

  The blog's "peak quality score of 81.4" is this value.
- **Human study (Table 2/3):** 50 scenarios, 5 raters each.
  - MLLM–human agreement: Krippendorff's α of 0.469–0.592 across the four dimensions. The human–human
    ceiling is 0.578–0.641.
  - VQ correlates weakly with humans (Pearson r = 0.345).
  - MOS: Co-Director 3.96, Veo 3.1 3.71, Kling 3.0 Omni 3.59, Wan 2.6 3.48, MovieAgent 3.22,
    AniMaker 3.07.
- **Ablations (Table 4, T=4, average score):**

  | Variant | Avg |
  |---|---|
  | Full | 79.0 |
  | Cold start | 77.3 |
  | Scalar reward instead of factored | 76.4 ("reduces VAF by 5.0 points") |
  | No storyline refinement | 74.0 |
  | No keyframe refinement | 71.5 (VAF −9.8) |
  | Neither refinement loop | 69.4 |
  | No MAB | 68.2 |
  | Nothing | 67.2 |

  These numbers differ from Table 1's 81.4. The paper does not explain why; it may be a different
  subset or run (**unverified**).
- **ViStoryBench-Lite (App. C, Table 5):** Co-Director has the best style consistency (cross 0.499,
  self 0.743), the best character consistency (cross 0.499, self 0.593) and the best average prompt
  alignment (3.166). It trails on Inception Score (10.900) and OCCM (66.215).
- **Video length:** "Final videos feature 4 shots totaling 12 seconds" (§5).
- **Compute, latency, cost:** not reported as wall-clock time or dollars. App. F reasons only in terms of
  pipeline executions: an exhaustive search "would require 36 discrete, end-to-end video generation
  pipelines per prompt", and T=4 is "sufficient". Per-video latency and cost are **unverified**.

### 1.5 Limitations, and real-time status
- There is no dedicated Limitations section in the HTML. Searches for "limitation", "latency" and
  "cost" found none.
- The only acknowledged issues are that "minor anatomical artifacts, such as occasional left-right hand
  confusion" remain (App. C), and that MLLM VQ scoring is a "strict physical quality gate rather than a
  direct mirror of subjective human perception" (§5.2).
- **Not real-time or interactive.** The only occurrence of "real-time" refers to humans "viewing
  real-time playback" during evaluation (§5.2). Each bandit pull renders a complete video before any
  reward is available.

---

## 2. CANVAS: Continuity-Aware Narratives via Visual Agentic Storyboarding (arXiv 2604.13452)

Authors: Ishani Mondal (University of Maryland), Yiwen Song, Mihir Parmar, Palash Goyal, Jordan
Boyd-Graber, Tomas Pfister and Yale Song. The output is a **storyboard (keyframe images), not video**.
Video appears only in App. A.8.

### 2.1 Architecture (§3, Algorithm 1)
"a training-free multi-agent framework that models storyboard generation as explicit world-state
tracking through global planning, memory-guided retrieval, and sequential memory updates" (§1
contributions).
- **Input:** shot descriptions S = {s_1..s_T}, plus canonical character images. When a benchmark does
  not provide them, these images "are first generated from their textual descriptions" (§4).
- **Output:** frames I = {I_1..I_T}.
- **Stage 1, Global Story Planning (§3.1):** produces P = (C, L, O). Details in §2.2.
- **Stage 2, Sequential Generation with Memory (§3.2):** for each shot t:
  1. retrieve the anchor set A_t;
  2. generate N candidates;
  3. select one with the QA-based selector;
  4. update memory.
- **Models:** "We implement CANVAS using Gemini-3-pro-image as the backbone image generation model"
  (§4).
  - The LLM/VLM used for planning, QA scoring and anchor extraction is **not named** in the text I read
    (**unverified**). The blog only says CANVAS is "Built as an orchestration layer on top of Gemini".
  - The evaluation judges (ContinuityEval) are Gemini-2.5-Flash, with GPT-5 as an independent check
    (Table 15).
  - HardContinuityBench was generated with GPT-5.2.
- **Training:** none ("training-free").

### 2.2 Memory/state: exact structures
**Global continuity plan P = (C, L, O)** (§3.1, prompts in Tables 20–24):
- **Character appearance:** "C(c,t) → k", the appearance state k for character c at shot t. The planner
  prompt (Table 22) returns JSON `{"character": ..., "appearance_timeline": {"Scene_1_Shot_1":
  "blue_curator_jacket", ..., "Scene_2_Shot_2": "not_present", ...}}`. Its rules are to reuse the
  identifier while clothing is unchanged, to create a new state only on an explicit story change, and
  to mark `not_present` when the character is absent.
- **Location:** "L(s_t) → l". Shots are clustered by location. The Table 20 prompt returns
  `{"locations": {"museum_gallery": [shots...]}, "shots": {"<shot>": {"location_id": ...,
  "continuity_mode": "fresh_location" | "location_reappearance" | "previous_frame_continuation"}}}`.
- **Object state:** "O(o,t) → state". The Table 23 prompt returns `{"prop": ..., "state_timeline":
  {"<shot>": {"state": "inside_display_case" | "carried" | "not_visible" | "missing_from_gallery" | ...,
  "carrier": <character|null>}}}`.
- **Background planning:** a "Future Prop and Geometry Aware Background Planning" prompt (Table 21)
  returns `background_props`, `must_appear`, `must_not_appear`, `carried_props` and `reasoning`. It
  explicitly reasons about "Which props are likely to appear in the background due to upcoming story
  events". This means **the planner uses the future of the script**.

**Visual memory M** (§3.2): "M = (M_c, M_l, M_f). Here M_c stores character appearance anchor images,
M_l stores background anchor images associated with locations, and M_f stores previously generated
frame images." A prop memory M_o(o, O(o,t)) is also introduced in §3.2 and Algorithm 4, although the
tuple definition omits it. Keys:
- M_c is keyed by (character, appearance-state). Algorithm 2 distinguishes M_c^canonical(c,k) from
  M_c^recent(c).
- M_l is keyed by location_id.
- M_o is keyed by (object, state).
- M_f is an append-only frame list.

**Anchor retrieval** (§3.2 and Algorithm 2):
- **Continuation.** "If the shot directly continues the previous scene without structural changes":
  A_t = {I_{t-1}} ∪ {M_c}. Whether a shot continues the previous one is itself decided by an LLM
  ("Previous-Frame Continuation Decision", Table 24), which returns `continuity_mode`, `same_location`,
  `requires_spatial_continuity`, `spatial_dependencies` and `reasoning`.
- **Revisit with a new viewpoint:** A_t = {M_l(L(s_t))} ∪ {M_c(c, C(c,t))}.
- **First appearance of a location:** "generation proceeds using only the relevant character anchors".
- **Character anchor choice (Algorithm 2 step 4).** If the appearance state changed from the previous
  shot, use the canonical anchor M_c^canonical(c,k). Otherwise use the most recent anchor, falling back
  to the canonical one.
- **Props (step 6).** If the prop appeared before, add M_o(o).
- **Prompt Π_t** is built from s_t, A_t, C(c,t), O(o,t) and the background reasoning.

**Initialisation.** Canonical character anchors are generated or provided up front. The API-call
formula counts "C … characters requiring canonical initialization". Location anchors are created lazily
from the first frame that shows the location: "the resulting frame I_1* initializes the gallery and
character anchors in memory".

**Update** (§3.2 and Algorithm 4). After selection, "a VLM-based extractor" identifies visible entities
and "produces clean visual anchors". It writes:
- M_c(c, C(c,t)) ← character anchor, only if the character is "clearly visible";
- M_l(L(s_t)) ← background anchor, "if the visual structure of a location changes due to an object state
  transition" in §3.2 (Algorithm 4 writes it unconditionally);
- M_o(o, O(o,t)) ← prop anchor;
- M_f ← M_f ∪ {I_t*}.

### 2.3 Candidate selection (Algorithm 3, Table 26)
- The generator produces N candidates.
- A VLM scores each one on Shot Alignment, Character Appearance Consistency, Background Continuity and
  Prop State Correctness, each on a 1–5 scale.
- The overall score is score_i = (S_align + S_char + S_bg + S_prop)/4, and the argmax is selected.
- "Performance saturates at N = 3" (§6).

### 2.4 Results (verified)
- **Benchmarks:**
  - ViStoryBench-Lite: 20 stories.
  - ST-Bench: 30 stories, derived from StoryMem.
  - HardContinuityBench: **5 stories** (Table 8). It has an average gap of 5.6 shots between location
    reappearances (versus 1.4 and 2.3 for the other two) and 3.6 prop-state transitions per story. The
    Limitations section concedes that "the dataset size of HardContinuityBench is small".
- **Headline claim (Abstract):** "improving background continuity by 21.6%, character consistency by
  9.6% and props consistency by 7.6%" over the best baseline. The §5 text gives other figures: "6–9%
  gains in consecutive and 12–14% improvements in non-consecutive scene consistency". On
  HardContinuityBench it gives "+8.9% for consecutive backgrounds, +14.0% for long-range scene
  reappearances, and +11.8% for character consistency". The paper does not reconcile the two sets of
  numbers.
- **Table 2 (ContinuityEval, 1–5, Gemini-2.5-Flash judge) on HardContinuityBench.** Columns are
  BG-consecutive / BG-non-consecutive / Prop / Char-avg:

  | Method | BG-consec | BG-non-consec | Prop | Char-avg |
  |---|---|---|---|---|
  | CANVAS | 4.88 | 4.88 | 4.19 | 4.91 |
  | Gemini-CT | 4.48 | 3.83 | 4.06 | 4.39 |
  | Story-Iter | 3.65 | 3.65 | 2.56 | 4.29 |
  | Story2Board | 3.33 | 3.33 | 2.23 | 4.06 |
  | AutoStudio | 3.05 | 3.18 | 2.90 | 3.42 |

  - ViStoryBench: CANVAS 4.83 / 4.83 / 4.88 / 4.30.
  - ST-Bench: CANVAS 4.94 / 4.73 / 4.73 / 4.24.
  - ContinuityEval shows "0.74 Fleiss' κ" agreement with humans.
- **Table 3, ViStoryBench-Lite standard metrics:**

  | Metric | CANVAS | Best other |
  |---|---|---|
  | CSD cross | 0.49 | Story-Iter 0.48 |
  | CIDS cross | 0.61 | Story-Iter 0.60 |
  | Prompt alignment | 3.60 | Gemini-CT 3.61 |
  | Aesthetic | 5.60 | — |

- **Human study:** 240 pairs and 15 annotators. Win-rates reach "90.9% for background and prop
  consistency" versus AutoStudio, and "68.3% against our strongest baseline".
- **Ablations (Tables 4–5):**
  - Removing canonical character anchors drops Char-avg from 4.24 to 2.59.
  - Removing background reuse drops consecutive BG from 4.94 to 2.12.
  - Removing location grouping drops consecutive BG to 2.45.
  - Removing future planning drops non-consecutive BG from 4.73 to 4.11 and Prop from 4.73 to 3.55.
  - Removing prop-state updates drops Prop to 3.76.
- **Downstream video (App. A.8, Table 17):** keyframes were fed to Veo-3.1-preview I2V and "concatenated
  to produce videos of approximately 1.5 minutes". FilMaster average (Gemini-2.5-Flash judge):
  CANVAS + Veo 4.03, Gemini-CT + Veo 3.33, StoryIter + Veo 3.13.
- **Compute (App. A.3):** "the total number of API calls is approximately 1 + C + S(1 + 3K)", where C is
  the number of characters, S the number of shots and K the candidates per shot. The paper also says
  "the runtime of all pipelines is dominated by API latency". CANVAS runs on CPU-only orchestration.
  Wall-clock time and dollars are **not reported**.

### 2.5 Limitations (verbatim summary of the "Limitations" section) and real-time status
The section lists four limitations:
1. "computationally expensive when producing multiple candidate shots for QA-based selection";
2. "does not yet fully model fine-grained physical interactions or complex motion dynamics";
3. it "assumes that narrative entities … can be reliably extracted from text";
4. HardContinuityBench is small.

For future work the paper names "interactive human-in-the-loop visual storytelling". **Not real-time.**
It is a batch pipeline: the plan uses the whole script, including future shots.

---

## 3. A²RD: Agentic Autoregressive Diffusion for Long Video Consistency (arXiv 2605.06924)

Authors: Do Xuan Long (NUS, Google Cloud AI Research intern), Yale Song, Min-Yen Kan, Tomas Pfister and
Long T. Le. Project page: http://dxlong2000.github.io/AARD (not opened).

### 3.1 Architecture (§3, Fig. 4)
The paper describes A²RD as "an Agentic Auto-Regressive Diffusion architecture that decouples creative
synthesis from consistency enforcement … a closed-loop process that synthesizes and self-improves video
segment-by-segment through a Retrieve–Synthesize–Refine–Update cycle". It is **training-free** (§1).
- **Input:** user context P; storyline S = {S_1..S_N}, "provided or planned from P"; optional reference
  images R^u.
- **The basic unit is a "segment"**, "a flexible unit that can span one or more scenes or shots".
- **Components:** any TI2V model, plus an MLLM and a TI2I model.
  - Main instantiation (§5.1): "Gemini 3 Flash … as the MLLM, Nano Banana 2 … as the TI2I model, and
    Veo 3.1 … as the TI2V model".
  - Also tested with open TI2V models: LTX-Video 0.9.8 (13B) and Wan 2.2 (5B), at 704×480 with 30
    denoising steps. Wan 2.2 runs only in always-extrapolate mode because it "does not support
    interpolation" (§6.2).
- **Per-segment loop (§3.2):**
  1. choose the mode;
  2. Retrieve;
  3. Synthesize and self-improve the boundary frame(s);
  4. Synthesize and self-improve the video segment;
  5. Update memory.
- **A²RD-Par (§3.4):** boundary frames are made autoregressively with frame self-improvement, then
  "All video segments are then synthesized in parallel, with no video self-improvement applied".

### 3.2 MVMem: Multimodal Video Memory (§3.1): exact schema
"M := {M_1..M_N} ∪ R ∪ D". Here R is the set of global reference frames and D is the prompt database.
Each segment memory is M_j := {T_j, F_j, V_j}:
- **Textual States T_j:**
  1. "Visual Arcs that track entity and environment features and their temporal evolution, recording
     elements' Identity, Identity Changes, and Motion";
  2. "Spatial Relations that capture subject-relation-object triplets from the begin frame to ground
     geometric layouts";
  3. "Camera states that record viewport trajectories".

  Extraction is hierarchical. First, T^F_j (Identity and Spatial Relations) comes from the begin frame.
  Then "missing elements, Identity Changes, Motions, and Camera dynamics" are added from the full
  segment.
- **Frames:** global references R, each "indexed by a generated caption", and segment keyframes F_j =
  {F_j^begin, F_j^end}, "indexed by S_j".
- **Videos V_j:** the stored segments, indexed by S_j, used "for cross-segment smooth transitions and
  motion continuity".
- **Prompt DB D = {(P, P*, Q, ℓ)}:** original prompt, refined prompt, rubric scores, and ℓ ∈ {pos, neg}.
  Entries are indexed by "a semantic embedding Emb(P, Q)". An entry is labelled 'pos' if all rubric
  scores improve and 'neg' if all worsen. D is "seeded with a few prior cases and updated online".
- **Initialisation (long-term references):**
  1. Planning: MLLM_plan^bg, MLLM_plan^ent and MLLM_cap produce prompts and captions for the
     environments and entities, including their "implicitly implied" appearances (Eq. 1).
  2. Dependencies: an MLLM builds a dependency DAG G (for example, an entity depends on its
     environment), which is split into weakly connected components and topologically sorted.
  3. Synthesis: TI2I renders each reference conditioned on its dependencies, with components rendered
     in parallel.
- **Retrieval (Eq. 3–4):**
  - S_j^rel = MLLM_retr^scenes(S, k, S_j), the top-k "most narratively relevant previous segments".
    Their T_n form T_j^rel, and their begin/end frames plus the relevant global references form F_j^rel.
  - V_j^rel = MLLM_retr^cont({V_<j}, S_j), "the immediate temporally contiguous segment (if any)".
  - R_j^rel = MLLM_retr^ref(R, P_R, S_j).
  - All retrieval is done by MLLM prompting over captions and indices. There is no vector search except
    in MAPO's prompt DB.
  - "For efficiency, we pre-compute Equations 2 and 3 and Equation 4 … over all segments at once"
    (§5.1). This pre-computation **reads the whole storyline**.
  - Context is capped: "cap the maximum window size at 100 for operations involving S and image lists".

### 3.3 Extrapolation vs interpolation (Eq. 2, §B.2.1)
- mode_i = **extrapolation** "if C(S_i) ∧ S_{i+1} is spatio-temporally continuous with S_i", and
  **interpolation** otherwise.
- C(S_i) means "S_i does not transition to a new established environment". "Both conditions are
  inferred by MLLM_mode(S)", an MLLM call over the storyline that needs the **next** segment's text.
- Interpolation applies "when S_i is a multi-shot context whose shots span different environments, or
  when S_{i+1} jumps to a new environment".
- In the B.2.1 example, interpolation was chosen because the next scene is a known, established
  environment, and extrapolation because the next environment was "unknown" and the action continues.
- The MLLM agrees with human experts more than 85% of the time. Errors are "mostly … determining
  extrapolation as interpolation" and are "largely benign".
- **End-frame rule (Eq. 5).** F_i^begin := F_{i−1}^end for i>1. For interpolation, F_i^end is either
  synthesised by TI2I from the next segment's frame prompt and references, or retrieved. Retrieval
  applies when the segment resumes a non-adjacent segment t: shot-end frames K_t are extracted from V_t
  and MLLM_retr^img picks the one that "best continues into S_{i+1}" (the example is returning to a car
  chase after intervening scenes, App. B.2.3). For extrapolation, F_i^end = ∅.
- **Ablation (Fig. 5 table):**

  | Variant | Narrative | Char | Env |
  |---|---|---|---|
  | Adaptive (full A²RD) | 0.8987 | 0.7353 | 0.8368 |
  | Always extrapolate | 0.8278 | 0.7112 | 0.8136 |
  | Always interpolate | 0.7094 | 0.7400 | 0.8499 |

  Always interpolating gives the best consistency but "over-constrain[s] the generation".

### 3.4 HITS: hierarchical test-time self-improvement, and MAPO (§3.3)
- **Frame level:**
  - Extract T^F with an MLLM, then verify with an **8-metric rubric** (1–10) in three groups: (i)
    Entity Consistency, Environment Consistency, Narrative Progression and Spatial Logicalness; (ii)
    Entity State and Environment State; (iii) Instruction Following and Physical Plausibility (Eq. 7).
  - The MLLM then chooses **Edit** ("targets a single issue only") or **Regenerate** (the prompt is
    re-optimised by MAPO).
  - The final frame is the argmax over all candidates from all iterations (Eq. 8).
- **Video level:**
  - Extract T_i, then verify with a **10-metric rubric**: (i) Inter Entity, Inter Environment, Inter
    Motion and Camera consistency; (ii) Intra Entity and Intra Environment; (iii) Instruction
    Following, Physical Plausibility, Narrative Progression and Frame Fit (Eq. 9).
  - If F^end exists, only the prompt is optimised. In extrapolation mode, the system "co-optimizes both
    F_i^end and P_i sequentially": it extracts F^end from V_i, self-improves it with Edit only, re-runs
    MAPO, and re-synthesises.
  - The final video is the argmax over candidates from all iterations (Eq. 10).
- **MAPO:**
  - Retrieve the top-k positive and negative cases by cosine similarity over (Q, P) embeddings.
  - "contrasts the positive and negative cases to derive refinement guidelines, reasons over Q to
    identify root causes of failures, and applies targeted edits".
  - Label the new case and add it online.
- **Budget (§5.1):**
  - "two iterations for frame and two for video refinements".
  - Three frames and three videos are generated per iteration via batch inference, the judges run in
    parallel, and the best candidate is refined.
  - Early stopping when "average frame/video scores ≥ 9/10".
  - "In total, a video segment requires at most 6 videos and 6 images."
  - App. B.5 sets k_v = k_f = 3, meaning one initial generation plus two refinements.
- **Effect (App. B.4):** the frame-judge average rises from 8.741 to 9.407 over two iterations. The
  video-level average rises from 7.928 to 8.493 (Table 10).

### 3.5 Results (verified)
- **Setup:**
  - VBench-Long: 40 prompts, each split by Gemini into 8 continuous segments, giving "approximately
    1-min videos".
  - LVBench-C: 3-min (24 scenes) and 5-min (40 scenes) videos, 20 samples each. Also ten 10-min
    scenarios (§6.4).
  - Segment length is about 7.5 s (**derived**: 1 min / 8 segments and 3 min / 24 scenes).
- **LVBench-C construction (§4):**
  - Three challenge types: evolving character, object and environment states.
  - Split: 3- and 5-min have 50 each (30 character, 10 object, 10 environment); 10-min has 25.
  - The text says "120 text-only scenarios", but the numbers add to 125 and Table 1 says "125 / 5200"
    (inconsistent in the paper).
  - Gap rule: main entities and environments "must be absent for at least n = 10 segments before
    reappearing".
  - Built with Gemini, self-refined, and re-verified by a separate MLLM (Anthropic, 2025).
- **Baselines:** Direct Prompting, Naive-AR, Naive-Par, MovieAgent, ViMax and VideoMemory, all on the same
  Gemini 3 Flash / Nano Banana 2 / Veo 3.1 stack.
- **VBench-Long, 1 min (Table 2):**

  | Method | Narrative coherence | Char | Env | Motion |
  |---|---|---|---|---|
  | A²RD | 0.8987 | 0.7353 | 0.8368 | 0.9935 |
  | A²RD-Par | 0.8082 | 0.6817 | 0.8180 | — |
  | VideoMemory | 0.6717 | 0.5729 | 0.7273 | — |
  | Naive-AR | 0.7466 | — | — | — |

  This is the source of the "20% narrative" and "30% character" headline claims.
- **LVBench-C (Table 3):**
  - 3-min: A²RD narrative 0.9000, Char 0.4262, BG 0.4148; VideoMemory 0.8475, 0.3687, 0.3554.
  - 5-min: A²RD 0.9500, 0.4395, 0.4119; VideoMemory 0.8292, 0.3697, 0.3830.
  - At 5-min, A²RD-Par has a higher Env score (0.4567).
- **MLLM-judge consistency over horizon (§6.3–6.4):**
  - 5-min: character 96.7%, environment 91.8%, object 95.0%.
  - 10-min: character 90.5%, environment 84.0%, object 91.5%.
  - The judge has 80% agreement with manual checks and is "calibrated to flag only clear violations".
- **Human study (Table 4):** 40 VBench-Long samples, 7 evaluators on a 1–5 scale. Averages: A²RD 4.68,
  A²RD-Par 4.29, VideoMemory 3.93. Transition smoothness: A²RD 4.34, best baseline 3.34.
- **Compute-matched best-of-N (Fig. 6):** baselines improve (for example, VideoMemory average consistency
  goes from 0.65 to 0.71) but remain below A²RD (0.73 to 0.78).
- **Open TI2V backbones (Table 5):** narrative/character on LTX go from 0.59/0.50 to 0.79/0.70, and on
  Wan 2.2 from 0.67/0.51 to 0.80/0.69.
- **Latency and cost (App. B.5 and Limitations):**
  - Total latency is Eq. 14. Compared with VideoMemory, A²RD adds about "12 additional MLLM calls, 2
    additional TI2I calls, and 2 additional TI2V calls per segment".
  - Measured call latencies: "under 10 seconds per MLLM call, 30 seconds per TI2I call (Nano Banana),
    and under 120 seconds per TI2V call (Veo 3.1)". The resulting overhead is "under 7.2 minutes per
    segment".
  - MLLM cost is "less than 0.5$ per segment (with less than 10K tokens per call on average; excluding
    costs associated with generating 5 additional videos and 5 additional frames per segment)".
  - A²RD-Par removes the N·k_v·L_V sequential video term, reducing it to about L_V "under ideal
    hardware".

### 3.6 Limitations and real-time status
Stated limitations:
- more compute than the baselines;
- no inter-rater agreement is reported;
- it needs MLLM, TI2I and TI2V models with strong instruction following;
- the rubrics "may not generalize to diverse creative styles";
- "transition smoothness and physical environment consistency remain the most challenging aspects".

Error analysis (App. B.3):
- environment layouts are "visually similar but not physically identical";
- objects are hallucinated;
- "the test-time self-refinement loop with our current budget of two refinement iterations is not
  always sufficient";
- the judge "occasionally fails to detect" small colour shifts.

**Not real-time.** The paper says outright that "this added latency can be non-trivial for standard
real-time LLM applications (e.g., question answering)" and justifies it by comparison with film
production (App. B.5). The model is autoregressive over segments, which is the right shape for
streaming. But mode selection and retrieval are pre-computed over the full storyline, interpolation
needs the next segment's text, and every segment can be regenerated up to 3 times before commit.

---

## 4. VQQA: An Agentic Approach for Video Evaluation and Quality Improvement (arXiv 2603.12310)

Authors: Yiwen Song, Tomas Pfister and Yale Song (Google). Project page: https://yiwen-song.github.io/vqqa/
(not opened).

### 4.1 Architecture (§3.2, Fig. 3)
- **Problem (§3.1):** find p* = argmax_p g(M(p,C), p, C) with a black-box generator M. The unknown
  ground-truth rater g is approximated by f, which returns a score S_f and a rationale R_f.
- **Update rule:** "p_{t+1} = VLM(p_t, R_{f,t})" (Eq. 5). The rationale is the "semantic gradient",
  following TextGrad and Feedback Descent.
- **Agents:**
  - **Question Generation (QG):** "Analyzes the video v, prompt p, and conditions C to dynamically
    generate a set of questions Q across three dimensions: Video-Prompt Alignment, Visual Quality, and
    Condition Fidelity".
    - The alignment prompt (App. F.1) asks for "5 to 10 rating questions" that scale with prompt
      complexity. Every question starts "On a scale of 0-100, how…".
    - The visual-quality prompt asks for "8 to 10" questions that prioritise "physical plausibility…
      object permanence… visual artifacts… motion quality".
    - Condition fidelity adds one call per reference image.
  - **Question Answering (QA):** scores each question on a 0–100 scale against a strict rubric
    ("Be critical. If you see any flaw, your score must reflect that").
  - **Prompt Refinement (PR):** takes the original prompt, the current prompt, the video, the QA pairs
    and optionally the history, and outputs a new prompt plus analysis. Its guiding principle is to
    "Preserve Core Intent … DO NOT change or remove the main subjects, actions, or settings to make
    generation 'easier'". Its strategies are adding detail, negative prompting, simplifying,
    re-weighting and re-ordering.
- **Global Selection (§3.2.2):** a Global VLM Rater scores every candidate (the initial video plus T
  refined ones) against the **original** prompt p_0 ("On a scale of 0-100, how well does this video
  match 'original prompt'… Respond with only a number"), and the argmax is returned (Eq. 6).
- **Stopping rule:** stop when the running max S*_t ≥ γ (e.g. 100), or when Δ(S*_t, S*_{t−k}) ≤ ε over a
  patience window k.
- **Models (App. C.1):**
  - VLMs: gemini-3-pro-preview and gemini-3-flash-preview (Vertex AI), gpt-4o-2024-08-06,
    gpt-5.1-2025-11-13 and gpt-5.2-2025-12-11.
  - Generators:
    - CogVideoX-5B (50 steps, **41 frames**, CFG 6.0);
    - CogVideoX-5B-I2V (49 frames);
    - Veo 3.1 (veo-3.1-generate-preview, default parameters). "Generations that triggered safety
      filters were replaced with blank videos".
  - Temperature is 0.0 for all agents (App. C.3).
- **Training:** none ("black-box", "without task-specific fine-tuning").
- **Iterations:** 4 optimisation rounds are reported. §4.3.2 says "the majority of performance gains are
  captured within the first four rounds". With k=3 the loop converges in 3.80–4.22 iterations over a
  10-step horizon (Fig. 4b). But App. B reports "an average of T = 1.245 optimization rounds" on
  T2V-CompBench under the stopping rule (capped at 4), and §4.2.3 reports 1.6 on VBench-I2V. These use
  different horizons and stopping settings; the paper does not reconcile them explicitly.

### 4.2 State/memory
The only state is the per-prompt optimisation history (past prompts, QA pairs and scores), passed to
the PR agent as "Historical Context (Optional)". There is no cross-prompt memory.

### 4.3 Results (verified)

| Benchmark | Generator | VQQA | Vanilla | Best baseline |
|---|---|---|---|---|
| T2V-CompBench avg (Table 1) | CogVideoX-5B | **53.46** (Gemini-3-Pro); 51.30 (GPT-4o) | 41.89 (+11.57 abs) | BoN-VQAScore 48.70; VPO 48.55 |
| VBench2 total (Table 2) | CogVideoX-5B | **50.41** (Gemini-3-Pro); 48.18 (GPT-4o) | 41.98 (+8.43) | BoN-VQAScore 46.95 |
| VBench-I2V avg (Table 3) | CogVideoX-5B-I2V | **97.86** | 96.62 (+1.24) | BoN Gemini-3-Pro 97.63 |
| T2V-CompBench avg (Table 5) | Veo 3.1 | **61.81** | 55.93 (+5.88) | BoN-VQAScore 59.51 |

- Best-of-N uses N=5, and VQQA uses 4 rounds.
- **Flaw-detection quality (Table 4, VideoFeedback2 test split):** VQQA precision 99.28, Q-Recall 96.55,
  E2E-Recall 82.08. Direct VLM analysis gets E2E-Recall 70.18.
- **Ablations:**
  - Selecting the last iteration instead of using the global rater loses 1.02 points (Fig. 5).
  - Selecting by average QA score loses 1.86 points.
  - Putting the global score into the PR agent's context hurts (53.11 vs 53.77 averaged over two VLMs,
    Table 6), so the paper decouples "the granular feedback loop … from the global score".
- **Cost (App. B, Table 7):**
  - VLM calls per prompt: at most (5+k)T+1, where k is the number of reference images. The breakdown is
    QG 2+k, QA 1 and PR 1 per iteration, plus T+1 global-rater calls.
  - The expected number is about 7.23 calls on T2V-CompBench, "comparable to a standard Best-of-5".
  - This does **not** count the T extra video generations. Wall-clock latency is **not reported**.
- **Video length:** CogVideoX 41 or 49 frames. Seconds and fps are not stated (**unverified**). Veo
  length is "default parameters" (duration **unverified**).

### 4.4 Limitations and real-time status
From App. A:
- "cannot rectify fundamental architectural flaws, synthesize out-of-distribution concepts, or entirely
  eliminate noisy semantic gradients from VLM hallucinations";
- "the iterative multi-agent loop requires sequential generation and querying, resulting in higher
  inference latency than parallelizable methods like Best-of-N".

**Not real-time.** Each iteration regenerates the whole clip, and the final pick is made after the fact
across all candidates.

---

## 5. Cross-paper comparison

| | Co-Director | CANVAS | A²RD | VQQA |
|---|---|---|---|---|
| Output | 12 s ad (4 shots) + audio | keyframe storyboard (video only in App. A.8, ~1.5 min) | 1–10 min video, ~7.5 s segments (derived) | single clip |
| Optimisation variable | categorical creative arms θ (plus local prompt rewrites) | frame choice among N candidates | frames and prompts per segment (Edit/Regenerate + MAPO) | text prompt |
| Selection | best of T=4 by aggregate judge score | argmax QA score, N=3 | argmax rubric over ≤3 iterations × 3 candidates | argmax Global Score vs p_0 |
| Memory | none persistent (assets + bandit stats) | P=(C,L,O) plan + M=(M_c,M_l,M_o,M_f) image anchors | MVMem: textual states + frames + videos + global refs + prompt DB | per-prompt history |
| Needs future script? | yes (full storyboard) | yes (future-prop planning, location clustering) | yes (mode needs S_{i+1}; retrieval pre-computed over all S) | no (single prompt) |
| Regenerates content before commit? | yes (whole video per pull) | yes (N candidates/shot) | yes (≤6 videos + 6 images/segment) | yes (T+1 videos) |
| Backbones | Gemini 3 Pro, Nano Banana Pro, Veo 3.1, Gemini 2.5 Pro TTS, Lyria 2 | Gemini-3-pro-image (planner VLM unnamed) | Gemini 3 Flash, Nano Banana 2, Veo 3.1 (also LTX 0.9.8, Wan 2.2) | Gemini-3-Pro/GPT-4o VLM; CogVideoX-5B(-I2V), Veo 3.1 |
| Trained? | no | no | no | no |
| Reported latency | none | "dominated by API latency" | <10 s MLLM, 30 s TI2I, <120 s TI2V; <7.2 min overhead/segment | ~7.23 VLM calls/prompt (no wall-clock) |
| Real-time / streaming / interactive | no | no (HITL is future work) | no (explicitly "non-trivial for … real-time") | no |

---

## 6. Transfer to a real-time interactive live persona agent

Assumed target: a streaming generator producing 5 s blocks. User instructions can arrive mid-stream,
each block has a hard deadline (it must be ready before the previous one finishes playing), and a block
cannot be changed once it has been shown. Everything in this section is **proposal** unless it quotes
the papers.

### 6.1 What breaks when the four methods are used as written
1. **Latency of the refinement loops.**
   - A²RD's own numbers are <10 s per MLLM call, 30 s per TI2I call and <120 s per TI2V call, for
     "under 7.2 minutes per segment" of overhead. The budget per 5 s block is roughly 5 s end to end.
   - A single A²RD MLLM verification already consumes a whole block's budget.
   - VQQA's roughly 7 VLM calls plus 1–4 regenerations, CANVAS's 1+3K calls per shot, and Co-Director's
     T=4 full-pipeline pulls are all too slow by one to three orders of magnitude.
2. **Select-after-generate needs unshown candidates.**
   - All four pick an argmax over several fully rendered candidates: VQQA's Global Selection, A²RD's
     Eq. 8/10, CANVAS's N=3, and Co-Director's best of T.
   - In streaming, the first candidate is effectively committed at its deadline. Selection is only
     possible if the generator runs at least N× real-time, or if candidates are drafted speculatively
     ahead of time.
   - VQQA's Global Selection, which judges candidates against p_0 after the fact, cannot be applied to
     content that has already been shown.
3. **Non-causal planning.** Several mechanisms assume the future is known, but in a live session the
   next user turn is unknown:
   - CANVAS's "Future Prop and Geometry Aware Background Planning" and its location clustering read the
     whole script;
   - A²RD's mode rule needs S_{i+1}, and its retrieval is pre-computed "over all segments at once";
   - Co-Director's storyboard is global.
4. **Interpolation needs a target end frame.** Generating one takes about 30 s with TI2I, and it assumes
   a planned next beat. Live streaming is essentially the extrapolation case, which is where A²RD says
   drift risk is highest "for entities and environments not visible in the begin frame".
5. **Bandit reward granularity.** Co-Director's pull is a whole video, and its reward arrives only after
   the full render. A live session gives one trajectory with no do-overs.
6. **The judge is API-hosted and not deterministic in latency.** The papers use Gemini, GPT and Veo
   APIs. None reports tail latency.
7. **Mid-stream user instructions are not modelled.** None of the papers handles an interruption or a
   correction during generation. CANVAS and the blog list human-in-the-loop only as future work.

### 6.2 What transfers, and how (proposals)
Summary: **use these methods on a slow, asynchronous path that corrects future blocks, never the shown
ones.** Keep the fast path to one generator call per block, conditioned on a compact state ledger.

- **World-state ledger (from CANVAS P=(C,L,O) and A²RD textual states).** This transfers most directly.
  - Keep persona appearance-state ids (for example `outfit=blue_hoodie`), a location or set id, and
    prop states with `carrier`. Use the same JSON shapes as CANVAS Tables 22–23.
  - Add A²RD's Visual Arcs (Identity, Identity Changes, Motion), spatial triplets and camera state.
  - Compose the prompt for block b+1 from the ledger. This is cheap text work, and it fixes the failure
    A²RD describes in App. B.2.4, where a detail such as "Racing Bib 402" is dropped from the prompt.
  - Change the ledger only on explicit events: a user instruction or an agent decision. This mirrors
    CANVAS's rule of a new state "only if the story explicitly changes".
- **Anchor retrieval rules (CANVAS Algorithm 2).** These map onto conditioning choices for the next
  block:
  - continuation, which is the normal live case: previous frame or latent state plus the character
    anchor;
  - reappearance after a scene or set change: the stored location anchor plus the character anchor for
    the current appearance state;
  - fresh: character anchors only.

  The continuation decision (CANVAS Table 24) could be made by a small, fast classifier instead of an
  LLM call. Whether our backbone accepts reference images or anchors at all has to be checked against
  the backbone notes (`backbone_lingbot_world_vllm_omni.md`); it is not assumed here.
- **Memory update after each block (CANVAS Algorithm 4, A²RD Update).**
  - Run it asynchronously on the block that was just shown: extract anchors and textual states, and
    refresh `M_c` (recent) and `M_l`.
  - Guard against drift feeding back into memory. CANVAS already distinguishes canonical anchors from
    recent ones, and its ablation shows canonical anchors matter most (Char-avg drops from 4.24 to 2.59
    without them). The proposal is to always keep a canonical persona anchor and never overwrite it from
    generated content.
- **Rubric verification as a monitor, not a gate (A²RD HITS, VQQA QG/QA).**
  - Turn each user instruction into VQQA-style "On a scale of 0-100, how…" questions (instruction
    compliance) plus a fixed persona-consistency rubric (A²RD's Inter Entity, Environment, Camera and
    Motion items).
  - Run the check on shown blocks in the background.
  - Low scores trigger a **forward-only semantic-gradient step**: the PR agent edits the prompt or
    ledger for the next block. It keeps VQQA's "Preserve Core Intent" constraint and its finding that
    the holistic score should stay out of the refinement context.
  - Expect a lag of one to two blocks before a correction takes effect (VLM latency of seconds). This
    needs to be measured, not assumed.
- **Edit vs Regenerate (A²RD).** In live streaming, "regenerate" is not available for shown content.
  "Edit" becomes a small, local correction applied to the next block, for example restoring a missing
  accessory. A²RD's observation that Edit "targets a single issue only" suggests fixing one violation
  per block.
- **MAPO prompt DB (A²RD).** This transfers well across sessions and is part of long-term memory. Store
  (control prompt, refined prompt, rubric scores, pos/neg) for the persona and backbone. Retrieve by
  embedding when a similar failure recurs, so that corrections become one-shot lookups instead of
  multi-call reasoning.
- **Hierarchical parameterisation (Co-Director).** Represent the persona's "style" as a small set of
  categorical axes, for example tone, energy and camera or framing preset. Inject them centrally into
  every sub-agent's system prompt. This keeps the planner, dialogue writer and generator-prompt composer
  consistent, which is the paper's "semantic collision" argument.
  - Run a bandit **across sessions or segments**, not within one render. Use a factored reward from an
    async judge and/or user engagement signals.
  - Warm-start the bandit from user-profile memory, following the paper's "LLM-driven warm start".
- **Speculative lookahead (A²RD-Par idea, adapted).** While block b plays, draft block b+1's prompt and
  optionally a target keyframe. Discard the draft if a user instruction arrives. A²RD-Par itself
  pre-renders every segment in parallel, which assumes a known script and does not fit live use as-is.
- **Evaluation assets that transfer.**
  - The ContinuityEval prompts (CANVAS Tables 6–7, 1–5 rubrics for face, clothing and background).
  - The A²RD §6.3 consistency ratio: flag only "unexplained and obvious" inconsistencies per segment,
    with 80% human agreement.
  - The LVBench-C "gap rule": the entity must be absent for at least 10 segments before reappearing.

  All three can be reused offline to score recorded live sessions, for example whether the persona's
  outfit or set is correct after a long gap.

### 6.3 Open questions to measure (not answered by the papers)
- Per-call latency and variance of a local VLM judge on one 5 s block, compared with the block period.
- Whether the backbone supports first-frame, end-frame or reference conditioning. This decides whether
  CANVAS/A²RD-style anchors or interpolation can be used at all.
- How much drift the forward-only correction leaves compared with A²RD's regenerate-before-commit. A²RD
  reports 96.7% character consistency over 5 min only *with* regeneration.

---

## 7. Evidence table

| # | Claim | Source |
|---|---|---|
| 1 | The suite is an orchestration layer on Gemini + Veo; quality is a "test-time objective" | Blog, intro paragraphs |
| 2 | LVBench-C described as 120 scenarios in the blog | Blog, "Key results & benchmarks" |
| 3 | Future direction: human-in-the-loop workflows | Blog, "Future directions" |
| 4 | Co-Director agents Φ_orch, Φ_pre (B, L, V, S), Φ_prod (frame, video, audio), Φ_post; Eq. 1–4 | 2604.24842 §3.1, Fig. 1 |
| 5 | Local feedback-descent refinement of storyline and keyframes; thresholds τ_L, τ_K; joint keyframe critique | 2604.24842 §3.2 |
| 6 | MAB arms θ=(θ_cs 3, θ_nm 3, θ_aa 4); pull = full pipeline; UCB1; factored reward R∈[0,100]³; LLM warm start | 2604.24842 §3.3; App. F |
| 7 | Judge prompt: five 0–20 execution criteria + three 0–100 strategic efficacy scores + fault attribution | 2604.24842 App. K |
| 8 | Models: Gemini 3 Pro, Nano Banana Pro, Veo 3.1, Gemini 2.5 Pro TTS, Lyria 2; T=4; 3 retries; 4 shots / 12 s | 2604.24842 §5 Implementation Details |
| 9 | GenAd-Bench: 50 brands × 4 products × 2 demographics = 400; 200/200 split | 2604.24842 §4, App. D |
| 10 | GenAd-Bench avg 81.4 vs Random Search 75.7, base 68.5, Veo 3.1 63.6, MovieAgent 65.3 | 2604.24842 Table 1 |
| 11 | MOS 3.96 vs Veo 3.1 3.71; MLLM–human α 0.469–0.592 | 2604.24842 Tables 2–3 |
| 12 | Scalar reward reduces VAF by 5.0; no keyframe refinement VAF −9.8 | 2604.24842 §5.3, Table 4 |
| 13 | No Limitations section and no latency/cost figures in Co-Director | 2604.24842 full HTML (searched) |
| 14 | CANVAS is training-free; P=(C,L,O); M=(M_c,M_l,M_f) plus M_o | 2604.13452 §1, §3.1, §3.2, Alg. 4 |
| 15 | Anchor retrieval rules (continuation / revisit / fresh; canonical vs recent anchors) | 2604.13452 §3.2, Alg. 2, Table 24 |
| 16 | QA selector: four 1–5 scores averaged; N=3 saturates | 2604.13452 Alg. 3, Table 26, §6 |
| 17 | Planner JSON schemas (appearance_timeline, state_timeline with carrier, continuity_mode) | 2604.13452 Tables 20–24 |
| 18 | Backbone Gemini-3-pro-image; judges Gemini-2.5-Flash and GPT-5; HardContinuityBench made with GPT-5.2 | 2604.13452 §4, Table 15 |
| 19 | HardContinuityBench has 5 stories, average reappearance gap 5.6 shots | 2604.13452 Table 8, App. A.1 |
| 20 | Abstract +21.6% / 9.6% / 7.6%; text 6–9% / 12–14% | 2604.13452 Abstract, §5 |
| 21 | Ablation: no canonical anchor Char-avg 4.24→2.59; no background reuse BG 4.94→2.12 | 2604.13452 Tables 4–5 |
| 22 | API calls ≈ 1 + C + S(1+3K); runtime dominated by API latency | 2604.13452 App. A.3 |
| 23 | Keyframes → Veo-3.1-preview I2V, ~1.5 min video, FilMaster avg 4.03 | 2604.13452 App. A.8, Table 17 |
| 24 | CANVAS limitations (cost of candidates, motion dynamics, entity extraction, small benchmark) | 2604.13452 "Limitations" |
| 25 | A²RD Retrieve–Synthesize–Refine–Update; training-free | 2605.06924 Abstract, §1, §3 |
| 26 | MVMem schema {T_j, F_j, V_j} ∪ R ∪ D; textual states = visual arcs, spatial triplets, camera | 2605.06924 §3.1 |
| 27 | Reference init via planning, dependency DAG and topological TI2I synthesis | 2605.06924 §3.1, Eq. 1 |
| 28 | Mode rule (Eq. 2) inferred by MLLM_mode(S); >85% human agreement | 2605.06924 §3.2, App. B.2.1 |
| 29 | End-frame rule, including retrieval of shot-end frames for non-adjacent resumption | 2605.06924 Eq. 5, App. B.2.3 |
| 30 | HITS: 8-metric frame rubric, 10-metric video rubric, Edit/Regenerate, argmax over candidates | 2605.06924 §3.3, Eq. 7–10 |
| 31 | MAPO prompt DB (P, P*, Q, ℓ), embedding retrieval, online pos/neg labelling | 2605.06924 §3.3 |
| 32 | Models Gemini 3 Flash, Nano Banana 2, Veo 3.1; 2+2 refinement iterations; 3 candidates; stop at ≥9/10; ≤6 videos + 6 images per segment | 2605.06924 §5.1 |
| 33 | VBench-Long: narrative 0.8987, char 0.7353, env 0.8368, motion 0.9935 | 2605.06924 Table 2 |
| 34 | LVBench-C 3-min / 5-min results | 2605.06924 Table 3 |
| 35 | 5-min consistency 96.7 / 91.8 / 95.0%; 10-min 90.5 / 84.0 / 91.5% | 2605.06924 §6.3–6.4 |
| 36 | Human average 4.68 vs VideoMemory 3.93 | 2605.06924 Table 4 |
| 37 | Latency <10 s / 30 s / <120 s per call; <7.2 min per segment; "non-trivial for … real-time"; <$0.5 MLLM per segment | 2605.06924 App. B.5, Limitations |
| 38 | Always-interpolate over-constrains; always-extrapolate reduces consistency | 2605.06924 §6.1 |
| 39 | LVBench-C: text says 120, counts give 125; gap rule n=10 | 2605.06924 §4, Table 1 |
| 40 | A²RD limitations and error analysis (environment layout, colour shifts, 2 iterations not always enough) | 2605.06924 Limitations, App. B.3 |
| 41 | VQQA QG/QA/PR agents; semantic gradient update p_{t+1}=VLM(p_t, R_f,t) | 2603.12310 §3.1.2, §3.2.1 |
| 42 | QG gives 5–10 alignment and 8–10 quality questions, 0–100 scale; PR must "Preserve Core Intent" | 2603.12310 App. F.1–F.3 |
| 43 | Global Selection vs original prompt p_0; stopping rule (γ, k, ε) | 2603.12310 §3.2.2, Eq. 6–8 |
| 44 | T2V-CompBench 53.46 (+11.57), VBench2 50.41 (+8.43), VBench-I2V 97.86 (+1.24), Veo 3.1 61.81 (+5.88) | 2603.12310 Tables 1, 2, 3, 5 |
| 45 | Flaw E2E-Recall 82.08 vs 70.18 | 2603.12310 Table 4 |
| 46 | Global selection ablation −1.02 (last-iter) / −1.86 (average QA); GS-in-loop hurts | 2603.12310 §4.4.2–4.4.3, Table 6 |
| 47 | VLM calls ≤(5+k)T+1, about 7.23 expected; T=1.245 average; 1.6 on I2V; 3.80–4.22 with k=3 over 10 steps | 2603.12310 App. B, §4.2.3, §4.3.2 |
| 48 | Models, versions, temperature 0, CogVideoX 41/49 frames | 2603.12310 App. C.1–C.3 |
| 49 | VQQA limitations: bounded by foundation models; sequential latency | 2603.12310 App. A |
| 50 | Transfer design in §6.2 | **proposal** (not from the papers) |

### Unverified or not found
- Co-Director thresholds τ_L and τ_K, per-video wall-clock time and cost.
- The LLM/VLM behind CANVAS's planner, selector and extractor.
- VQQA wall-clock latency and clip durations in seconds.
- Anything shown only in figures (Fig. 2 MAB curve values, CANVAS Fig. 3/8 per-baseline win-rates beyond
  those quoted, and A²RD Fig. 5–7 plots).
- Code availability. Co-Director claims it will "open-source our implementation"; the repos were not
  checked.
