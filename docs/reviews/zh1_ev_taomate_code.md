# TaoMate-H3 code excerpts @ 6b2f9984acf681e2f387188f5d1f3b26e504315b

## config.py:15-40
```python
   15  class DirectPolicy:
   16      """The validated direct streaming contract.
   17  
   18      These values are deliberately not command-line options. Changing one of
   19      them creates a different inference method and must be evaluated separately.
   20      """
   21  
   22      request_seconds: int = 5
   23      chunk_group_counts: tuple[int, ...] = (2, 2, 2, 1)
   24      precision: str = "bf16_with_interior_fc1_qkv_w8a8"
   25      attention_backend: str = "flash_attn_3"
   26      persistent_kv: str = "clean_audio_video"
   27      video_kv_retention: str = "first_video_sink_plus_recent_2_chunks"
   28      audio_kv_retention: str = "match_video"
   29      audio_kv_reset_window_requests: int = 12
   30      prompt_scope: str = "current_request"
   31      rope: str = "split_temporal_spatial"
   32      audio_guidance: str = "fl2va_tail40_rollover"
   33      audio_guidance_state_numbers: tuple[int, ...] = (3, 6, 9)
   34      stage3_target_state_indices: tuple[int, ...] = (16, 33, 49)
   35      prefix_normalization: str = "affine_to_first_stream_chunk"
   36      canonical_continuation_geometry: bool = True
   37      publication: str = "one_shot_audio_video_vae"
   38  
   39      def to_dict(self) -> dict[str, Any]:
   40          return asdict(self)
```

## config.py:80-134
```python
   80  def load_prompt_json(path: Path) -> tuple[tuple[str, ...], tuple[int, ...] | None]:
   81      try:
   82          payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
   83      except (OSError, UnicodeError, json.JSONDecodeError) as exc:
   84          raise ValueError(f"cannot read prompt JSON: {exc}") from exc
   85      prompts = payload.get("prompts") if isinstance(payload, Mapping) else None
   86      if not isinstance(prompts, list) or not prompts:
   87          raise ValueError('prompt JSON must contain {"prompts": ["...", "..."]}')
   88      normalized: list[str] = []
   89      for index, prompt in enumerate(prompts):
   90          if not isinstance(prompt, str) or not prompt.strip():
   91              raise ValueError(f"prompt JSON item {index} must be a non-empty string")
   92          normalized.append(prompt.strip())
   93      raw_seeds = payload.get("seeds")
   94      if raw_seeds is None:
   95          seeds = None
   96      elif (
   97          not isinstance(raw_seeds, list)
   98          or len(raw_seeds) != len(normalized)
   99          or any(type(seed) is not int or seed < 0 for seed in raw_seeds)
  100      ):
  101          raise ValueError("prompt JSON seeds must be one non-negative integer per prompt")
  102      else:
  103          seeds = tuple(raw_seeds)
  104      return tuple(normalized), seeds
  105  
  106  
  107  def resolve_prompts(
  108      *,
  109      prompt: str | None,
  110      prompt_json: Path | None,
  111      duration_seconds: int | None,
  112  ) -> tuple[tuple[str, ...], int, tuple[int, ...] | None]:
  113      if (prompt is None) == (prompt_json is None):
  114          raise ValueError("choose exactly one of --prompt or --prompt-json")
  115      if prompt_json is not None:
  116          supplied, seeds = load_prompt_json(prompt_json)
  117      else:
  118          supplied, seeds = (str(prompt).strip(),), None
  119      if any(not item for item in supplied):
  120          raise ValueError("prompt must not be empty")
  121      if duration_seconds is None:
  122          duration_seconds = (
  123              len(supplied) * SEGMENT_SECONDS if prompt_json is not None else SEGMENT_SECONDS
  124          )
  125      if duration_seconds <= 0 or duration_seconds % SEGMENT_SECONDS:
  126          raise ValueError("duration must be a positive multiple of 5 seconds")
  127      request_count = duration_seconds // SEGMENT_SECONDS
  128      if prompt_json is not None:
  129          if len(supplied) != request_count:
  130              raise ValueError("prompt JSON count must equal duration divided by 5 seconds")
  131          prompts = supplied
  132      else:
  133          prompts = supplied * request_count
  134      return prompts, duration_seconds, seeds
```

## streaming/geometry.py:170-202
```python
  170          }
  171  
  172  
  173  def direct_5s_plan() -> StreamPlan:
  174      """Return the validated four-chunk plan for one five-second request."""
  175  
  176      native_frame_count = 124
  177      phases: list[StreamPhase] = []
  178      frame_stop = 0
  179      video_stop = 0
  180      for index, groups in enumerate((2, 2, 2, 1)):
  181          frame_start = frame_stop
  182          video_start = video_stop
  183          frame_stop += groups * VIDEO_GROUP_FRAMES
  184          video_stop += groups * VIDEO_GROUP_LATENTS
  185          if index == 0:
  186              frame_stop += VIDEO_PREFIX_FRAMES
  187              video_stop += VIDEO_PREFIX_LATENTS
  188          phases.append(
  189              StreamPhase(
  190                  index=index,
  191                  group_count=groups,
  192                  frame_start=frame_start,
  193                  frame_stop=frame_stop,
  194                  video_latent_start=video_start,
  195                  video_latent_stop=video_stop,
  196                  audio_latent_start=_audio_latent_boundary(frame_start),
  197                  audio_latent_stop=_audio_latent_boundary(frame_stop),
  198              )
  199          )
  200      return StreamPlan(native_frame_count=native_frame_count, phases=tuple(phases))
  201  
  202  
```

## streaming/cache.py:200-222
```python
  200  
  201          self._commit_token_counts.append(token_count)
  202          self._commit_token_tags.append(self._staged_tags)
  203          self._block_index += 1
  204          self._clear_staging()
  205  
  206      def retain_sink_and_recent_commits(self) -> None:
  207          """Keep the first chunk's video sink and the most recent clean chunks."""
  208  
  209          if self.clean_commit_active:
  210              raise RuntimeError("cannot trim persistent KV during an active clean commit")
  211          block_count = len(self._commit_token_counts)
  212          # As soon as three clean chunks exist, age chunk zero to a video-only
  213          # sink and keep chunks one and two as the two complete AV recents.
  214          if block_count <= 2:
  215              return
  216  
  217          recent_start = max(1, block_count - 2)
  218          selection = [(0, True)] + [(index, False) for index in range(recent_start, block_count)]
  219          self._retain_commit_rows(selection)
  220  
  221      def drop_audio_history(self) -> int:
  222          """Remove audio rows while preserving every retained video row."""
```

## streaming/attention_hook.py:38-52
```python
   38  
   39  class H3StreamingAttentionHook:
   40      """Condition current media on text, persistent clean AV KV, and current KV."""
   41  
   42      def __init__(self, cache: CleanAVKVCache, *, backend: str = "flash_attn_3") -> None:
   43          if backend != "flash_attn_3":
   44              raise ValueError("the accelerated direct runtime requires FlashAttention-3")
   45          try:
   46              from flash_attn_interface import flash_attn_func
   47          except ImportError as exc:
   48              raise RuntimeError("FlashAttention-3 kernels are required") from exc
   49          self.cache = cache
   50          self._flash_attention = flash_attn_func
   51          self.kernel_calls = 0
   52          self.query_tokens = 0
```

## streaming/runtime.py:335-362
```python
  335          .view(-1, int(rows.shape[-1]))
  336      )
  337  
  338  
  339  def _base_audio_teacher_step_callback(
  340      teacher: dict[str, Any],
  341      *,
  342      phase: StreamPhase,
  343      total_audio_latents: int,
  344  ) -> Callable[[int, Any, Any], None]:
  345      """Inject the request-wide Base10 milestone used by one Stage3 loop."""
  346  
  347      milestones = teacher["milestones"]
  348  
  349      def on_step(step_index: int, video_rows: Any, audio_rows: Any) -> None:
  350          milestone = milestones.get(step_index)
  351          if milestone is not None:
  352              teacher_rows = _teacher_phase_audio_rows(
  353                  milestone,
  354                  phase=phase,
  355                  total_audio_latents=total_audio_latents,
  356              )
  357              audio_rows.copy_(teacher_rows)
  358  
  359      return on_step
  360  
  361  
  362  @contextmanager
```

## streaming/runtime.py:445-465
```python
  445              self._cache.clear()
  446              self._cache = None
  447          self._canonical_transport_video_rows = None
  448          self._canonical_transport_audio_rows = None
  449          self._prefix_renorm_video_anchor = None
  450  
  451      def _renorm_clean_video_rows(self, rows: Any) -> Any:
  452          """Match generated blocks to persistent block-zero statistics."""
  453  
  454          current = rows.detach().float()
  455          mean = current.mean(dim=0, keepdim=True)
  456          std = current.std(dim=0, keepdim=True, unbiased=False).clamp_min(1e-6)
  457          if self._prefix_renorm_video_anchor is None:
  458              self._prefix_renorm_video_anchor = (mean, std)
  459              return rows
  460          anchor_mean, anchor_std = self._prefix_renorm_video_anchor
  461          normalized = (current - mean).div(std).mul(anchor_std).add(anchor_mean)
  462          return normalized.to(dtype=rows.dtype)
  463  
  464      def dit_timing_receipt(self) -> dict[str, float | int]:
  465          """Return synchronized Transformer-only CUDA time across all ranks."""
```

## streaming/runtime.py:600-625
```python
  600                  request_index=request_index,
  601                  audio_latent_count=total_audio_latents,
  602                  device=cuda_device,
  603              )
  604  
  605              with H3StreamingSession(
  606                  active_plan,
  607                  cache=cache,
  608              ) as session:
  609                  for phase in phases:
  610                      branch = _build_phase_branch(
  611                          positive=positive,
  612                          phase=phase,
  613                          latent_h=latent_h,
  614                          latent_w=latent_w,
  615                          model=model,
  616                          device=cuda_device,
  617                          text_token_tags=text_token_tags,
  618                          media_time_origin=media_time_origin,
  619                          video_latent_offset=self._video_latent_offset,
  620                          audio_latent_offset=self._audio_latent_offset,
  621                      )
  622                      position_capture["phases"].append(
  623                          {
  624                              "phase_index": phase.index,
  625                              **dict(branch._taomate_h3_position_capture),
```

## streaming/runtime.py:735-745
```python
  735              if joined_video.shape != request_video_rows.shape:
  736                  raise RuntimeError("reassembled streaming video rows changed request shape")
  737              if joined_audio.shape != initial_audio.shape:
  738                  raise RuntimeError("reassembled streaming audio rows changed request shape")
  739              final_teacher = audio_teacher["milestones"][2]
  740              if not torch.equal(joined_audio, final_teacher):
  741                  raise RuntimeError(
  742                      "published streaming audio differs from Base teacher clean latent"
  743                  )
  744              audio_teacher_receipt = dict(audio_teacher["receipt"])
  745              audio_teacher_receipt["published_clean_audio_exact_match"] = True
```

## runner.py:285-330
```python
  285          },
  286      )
  287      runtime = H3Runtime(
  288          model_root=config.model_root,
  289          adapter_root=config.adapter,
  290          output_root=config.output_dir,
  291          ulysses_degree=config.ulysses_degree,
  292      )
  293      precomputed = runtime.precompute_text_prompts(config.prompts)
  294      video_segments: list[Any] = []
  295      audio_segments: list[Any] = []
  296      streaming = H3StreamingRuntime(base10_teacher=teacher)
  297      runtime.reset_dit_peak_memory()
  298      noise_contract: list[dict[str, int]] = []
  299      for request_index, (text_features, request_seed) in enumerate(
  300          zip(precomputed, config.request_seeds, strict=True)
  301      ):
  302          video_noise_seed = (
  303              request_seed + request_index * _VIDEO_NOISE_REQUEST_STRIDE
  304          ) % (2**63)
  305          audio_noise_seed = teacher.audio_noise_seed(request_index)
  306          video_latents, audio_latents = runtime.generate_latents(
  307              video_noise_seed=video_noise_seed,
  308              audio_noise_seed=audio_noise_seed,
  309              width=config.width,
  310              height=config.height,
  311              precomputed_text=text_features,
  312              denoise_loop=streaming.run,
  313          )
  314          video_segments.append(video_latents)
  315          audio_segments.append(audio_latents)
  316          noise_contract.append(
  317              {
  318                  "request_index": request_index,
  319                  "authored_seed": request_seed,
  320                  "video_noise_seed": video_noise_seed,
  321                  "audio_noise_seed": audio_noise_seed,
  322              }
  323          )
  324      dit_timing = streaming.dit_timing_receipt()
  325      dit_memory = runtime.dit_peak_memory_receipt()
  326      streaming.release_retained_state()
  327      publication_started = time.perf_counter()
  328      publication = _publish(
  329          runtime=runtime,
  330          config=config,
```

## cli.py:125-150
```python
  125  def _validate_acceleration_runtime() -> None:
  126      """Fail before torchrun when a required GPU acceleration module is absent."""
  127  
  128      try:
  129          vllm_ops = importlib.import_module("vllm._custom_ops")
  130          flash_attn = importlib.import_module("flash_attn_interface")
  131          importlib.import_module("triton")
  132      except ImportError as exc:
  133          raise ValueError(f"accelerated runtime dependency is unavailable: {exc}") from exc
  134      if not all(
  135          callable(getattr(vllm_ops, name, None))
  136          for name in ("scaled_int8_quant", "cutlass_scaled_mm")
  137      ):
  138          raise ValueError("vLLM CUTLASS W8A8 operations are unavailable")
  139      if not callable(getattr(flash_attn, "flash_attn_func", None)):
  140          raise ValueError("FlashAttention-3 interface is unavailable")
  141  
  142  
  143  def _validate_output(output: Path) -> None:
  144      if output.exists():
  145          if not output.is_dir() or any(output.iterdir()):
  146              raise ValueError("--output must be a new or empty directory")
  147  
  148  
  149  def _prepare_output(config: DirectRunConfig) -> Path:
  150      output = config.output_dir
```

## cli.py:215-232
```python
  215          _validate_input_paths(config)
  216      except (OSError, ValueError) as exc:
  217          parser.error(str(exc))
  218      print("Powered by MiniMax H3.", flush=True)
  219      with TemporaryDirectory(prefix="taomate-h3-audio-", dir="/dev/shm") as temporary:
  220          temporary_root = Path(temporary)
  221          audio_guidance_dir = temporary_root / "guidance"
  222          print("Preparing audio guidance...", flush=True)
  223          launch_audio_guidance(
  224              config,
  225              output_dir=audio_guidance_dir,
  226          )
  227          config_path = _prepare_output(config)
  228          print("Generating audio and video...", flush=True)
  229          launch(config, config_path, audio_guidance_dir)
  230      return 0
  231  
  232  
```
