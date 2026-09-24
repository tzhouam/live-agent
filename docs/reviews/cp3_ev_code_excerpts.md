# Code excerpts from vllm-omni @ 7b4dc7633bde8642f0c05f77bd018751541df404 (extracted by the author with sed -n; line numbers are real)

## vllm_omni/diffusion/interaction/registry.py:17-28
```python
   17  STRUCTURED_HANDLER_REGISTRY: dict[str, dict[str, type[InteractionHandler]]] = {
   18      # Pipeline class name -> modality -> handler class.
   19      "HeliosPipeline": {
   20          "prompt": PromptInteractionHandler,
   21      },
   22      "HeliosPyramidPipeline": {
   23          "prompt": PromptInteractionHandler,
   24      },
   25      "LingBotWorldCausalDMDPipeline": {
   26          "camera": SE3DeltaCameraHandler,
   27      },
   28  }
```

## vllm_omni/diffusion/interaction/coordinator.py:55-125
```python
   55      def needs_chunk_media(self) -> bool:
   56          """Whether any registered handler needs chunk media/latent counts + fps."""
   57          return any(handler.needs_chunk_media for handler in self._handlers.values())
   58  
   59      def get_handler(self, modality: str) -> InteractionHandler:
   60          handler = self._handlers.get(modality)
   61          if handler is None:
   62              raise ValueError(
   63                  f"interaction modality {modality!r} is not supported by pipeline {self.model_class_name!r}"
   64              )
   65          return handler
   66  
   67      def enqueue(
   68          self,
   69          state: StepRequestState,
   70          *,
   71          modality: str,
   72          event_id: str,
   73          received_at: float,
   74          payload: InteractionPayload,
   75          transition_chunks: int | None,
   76      ) -> None:
   77          """Fan out enqueue to handlers in stable order (prompt first)."""
   78          handler = self.get_handler(modality)
   79          handler.enqueue(
   80              state,
   81              event_id=event_id,
   82              received_at=received_at,
   83              payload=payload,
   84              transition_chunks=transition_chunks,
   85          )
   86  
   87      def enqueue_parts(
   88          self,
   89          state: StepRequestState,
   90          *,
   91          parts: list[tuple[str, InteractionPayload]],
   92          event_id: str,
   93          received_at: float,
   94          transition_chunks: int | None,
   95      ) -> None:
   96          """Ensure every modality is supported and every payload validates, then enqueue.
   97  
   98          Composite events must not partially mutate queues when a later track is
   99          unsupported or carries an invalid payload.
  100          """
  101          if not parts:
  102              raise ValueError("interaction event requires prompt and/or multi_modal_data")
  103  
  104          # Reconcile rank-local samples so USP/SP shards share one arrival time.
  105          received_at = synchronized_monotonic_time(received_at)
  106  
  107          handlers = [(self.get_handler(modality), payload) for modality, payload in parts]
  108          for handler, payload in handlers:
  109              handler.validate_payload(
  110                  state,
  111                  event_id=event_id,
  112                  payload=payload,
  113                  transition_chunks=transition_chunks,
  114              )
  115          for (modality, payload), (handler, _) in zip(parts, handlers, strict=True):
  116              del handler
  117              self.enqueue(
  118                  state,
  119                  modality=modality,
  120                  event_id=event_id,
  121                  received_at=received_at,
  122                  payload=payload,
  123                  transition_chunks=transition_chunks,
  124              )
  125  
```

## vllm_omni/entrypoints/openai/serving_video_output_stream.py:140-180
```python
  140                      websocket,
  141                      request_id,
  142                      stop_event,
  143                      send_lock,
  144                      progress,
  145                      interaction_payloads_by_id,
  146                  )
  147              )
  148              async for chunk, metadata in self._stream_video_bytes(request, request_id, output_format, progress):
  149                  if stop_event.is_set():
  150                      stopped = True
  151                      break
  152                  async with send_lock:
  153                      metadata["transport_chunk_index"] = chunks_sent
  154                      await websocket.send_json(metadata)
  155                      await websocket.send_bytes(chunk)
  156                  chunks_sent += 1
  157                  progress.touch()
  158  
  159              async with send_lock:
  160                  await websocket.send_json(
  161                      {
  162                          "type": "session.done",
  163                          "request_id": request_id,
  164                          "chunks": chunks_sent,
  165                          "stopped": stopped or stop_event.is_set(),
  166                      }
  167                  )
  168          except WebSocketDisconnect:
  169              logger.info("Streaming video output: client disconnected")
  170              if request_id is not None:
  171                  await self._abort_request(request_id)
  172          except Exception as e:
  173              if stop_event.is_set():
  174                  try:
  175                      async with send_lock:
  176                          await websocket.send_json(
  177                              {
  178                                  "type": "session.done",
  179                                  "request_id": request_id,
  180                                  "chunks": chunks_sent,
```

## vllm_omni/entrypoints/openai/serving_video_output_stream.py:455-480
```python
  455                  send_lock=send_lock,
  456              )
  457              return
  458  
  459          interaction_payloads_by_id[event_id] = normalized
  460  
  461          try:
  462              await self._engine_client.submit_interaction_async(
  463                  request_id,
  464                  interaction=normalized,
  465              )
  466          except Exception:
  467              logger.exception("Failed to apply interaction for request %s", request_id, exc_info=True)
  468              interaction_payloads_by_id.pop(event_id, None)
  469              await self._send_error(
  470                  websocket,
  471                  "Failed to apply interaction",
  472                  code="interaction_failed",
  473                  request_id=request_id,
  474                  event_id=event_id,
  475                  send_lock=send_lock,
  476              )
  477              return
  478  
  479          try:
  480              async with send_lock:
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:745-800
```python
  745          latent_height = self._ar_height // spatial
  746          latent_width = self._ar_width // spatial
  747          tokens_per_frame = (latent_height // patch_height) * (latent_width // patch_width)
  748          total_window_frames = (
  749              int(self.transformer.config.local_attn_size)
  750              if int(self.transformer.config.local_attn_size) != -1
  751              else int(self.transformer.config.sliding_window_num_frames)
  752          )
  753          sink_frames = int(self.transformer.config.sink_size)
  754          recent_window_frames = total_window_frames - sink_frames
  755          if recent_window_frames <= 0:
  756              raise ValueError("LingBot AR-Diffusion cache needs a positive recent window after reserving sink frames.")
  757          condition_latent_frames = int(self.transformer.config.num_frames_per_block)
  758          condition_channels = self.vae_scale_factor_temporal + int(self.transformer.config.out_channels)
  759          element_size = torch.empty((), dtype=self.transformer.dtype).element_size()
  760          condition_bytes_per_session = (
  761              condition_channels * condition_latent_frames * latent_height * latent_width * element_size
  762          )
  763          # Each layer retains scale and shift for the rank-local camera tokens
  764          # across all forwards of a block, including between scheduler calls.
  765          camera_tokens = tokens_per_frame * condition_latent_frames
  766          sp_size = int(self.od_config.parallel_config.ulysses_degree)
  767          camera_bytes_per_session = (
  768              2
  769              * int(self.transformer.config.num_layers)
  770              * ((camera_tokens + sp_size - 1) // sp_size)
  771              * int(self.transformer.config.num_attention_heads)
  772              * int(self.transformer.config.attention_head_dim)
  773              * element_size
  774          )
  775          return ARDiffusionKVCacheSpec(
  776              num_layers=int(self.transformer.config.num_layers),
  777              num_kv_heads=int(self.transformer.blocks[0].self_attn.num_sp_heads),
  778              head_size=int(self.transformer.config.attention_head_dim),
  779              tokens_per_frame=tokens_per_frame,
  780              frames_per_block=int(self.transformer.config.num_frames_per_block),
  781              window_frames=recent_window_frames,
  782              sink_frames=sink_frames,
  783              kv_branches=(ARDiffusionKVBranchSpec(self._AR_BRANCH, 0),),
  784              session_capacity=2,
  785              cross_attention=(
  786                  ARDiffusionCrossAttentionKVSpec(
  787                      self._AR_TEXT_CACHE,
  788                      _MAX_SEQUENCE_LENGTH,
  789                      # Cross-attention keeps every local head on every rank rather than sharding heads across
  790                      # the Ulysses group, so the text pool holds that many heads, not the self-attention share.
  791                      num_kv_heads=int(self.transformer.blocks[0].cross_attn.num_local_heads),
  792                  ),
  793              ),
  794              model_owned_state_bytes_per_session=(
  795                  condition_bytes_per_session
  796                  + camera_bytes_per_session
  797                  + 2 * self._condition_encoder_cache_bytes()  # Committed and in-flight histories.
  798                  + self._streaming_decode_bytes_per_session()
  799              ),
  800          )
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:1880-1940
```python
 1880          if (inputs.height, inputs.width) != (self._ar_height, self._ar_width):
 1881              raise ValueError(
 1882                  "LingBot AR-Diffusion request resolution must match the "
 1883                  f"fixed cache geometry {self._ar_height}x{self._ar_width}."
 1884              )
 1885          block_frames = int(self.transformer.config.num_frames_per_block)
 1886          total_chunks = inputs.num_latent_frames // block_frames
 1887          if inputs.camera_action_script is not None and len(inputs.camera_action_script) != total_chunks:
 1888              raise ValueError(
 1889                  "camera_action_script must contain one action list per generated chunk; "
 1890                  f"got {len(inputs.camera_action_script)} chunks for {total_chunks} requested chunks."
 1891              )
 1892          dtype = self.transformer.dtype
 1893          prompt_embeds = self.encode_prompt(
 1894              inputs.prompt,
 1895              max_sequence_length=inputs.max_sequence_length,
 1896              dtype=dtype,
 1897          )
 1898          camera_trajectory_cache = None
 1899          camera_embedding_cache = None
 1900          if inputs.camera_trajectory is not None:
 1901              available_frames = int(inputs.camera_trajectory.poses.shape[0])
 1902              if available_frames < inputs.num_frames:
 1903                  raise ValueError(
 1904                      "camera trajectory frames must be at least num_frames; "
 1905                      f"got camera_frames={available_frames}, num_frames={inputs.num_frames}."
 1906                  )
 1907              truncated = CameraTrajectory(
 1908                  poses=inputs.camera_trajectory.poses[: inputs.num_frames],
 1909                  intrinsics=inputs.camera_trajectory.intrinsics[: inputs.num_frames],
 1910              )
 1911              camera_trajectory_cache = interpolate_camera_trajectory(truncated, inputs.num_latent_frames)
 1912              # Embed the whole trajectory once, exactly as request mode does, and
 1913              # slice it per block in ``_prepare_next_chunk``. Embedding each chunk
 1914              # on its own would normalize that block's framewise translations by
 1915              # its own largest step, so a slow block would be conditioned as
 1916              # full-speed motion and drift from offline replay of the same path.
 1917              camera_embedding_cache, _ = self._prepare_camera(inputs, dtype=dtype)
 1918          state.prompt_embeds = prompt_embeds
 1919          state.chunk_index = 0
 1920          state.step_index = 0
 1921          state.step_in_chunk = 0
 1922          state.total_chunks = total_chunks
 1923          state.chunk_num_steps = len(LINGBOT_DMD_TIMESTEPS)
 1924          state.extra = {
 1925              "inputs": inputs,
 1926              "schedule": _build_shifted_flow_schedule(flow_shift=inputs.flow_shift),
 1927              "dtype": dtype,
 1928              "block_frames": block_frames,
 1929              "camera_pitch": 0.0,
 1930              "camera_tail": None,
 1931              "camera_action_script": inputs.camera_action_script,
 1932              "camera_trajectory_cache": camera_trajectory_cache,
 1933              "camera_embedding_cache": camera_embedding_cache,
 1934          }
 1935          self._ar_text_caches(prompt_embeds, invalidate=False)
 1936          self._ar_sessions[state.request_id] = _LingBotARSessionState()
 1937          return state
 1938  
 1939      def _prepare_next_chunk(self, state: StepRequestState) -> None:
 1940          extra = state.extra
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:1950-2060
```python
 1950              start_frame=start_frame,
 1951              session_state=session_state,
 1952              dtype=extra["dtype"],
 1953          )
 1954          previous = extra.get("camera_tail")
 1955  
 1956          if extra.get("camera_action_script") is not None:
 1957              if (
 1958                  (camera_session := state.interaction_sessions.get("camera"))
 1959                  and isinstance(camera_session, CameraSession)
 1960                  and camera_session.has_received_input
 1961              ):
 1962                  raise ValueError("Cannot use mid-generation camera interaction together with camera_action_script; ")
 1963              chunk_actions = extra["camera_action_script"][state.chunk_index]
 1964              action_trajectory, camera_pitch = integrate_lingbot_camera_actions(
 1965                  chunk_actions,
 1966                  width=inputs.width,
 1967                  height=inputs.height,
 1968                  initial_pose=(previous.poses[-1] if previous is not None else None),
 1969                  initial_pitch=float(extra.get("camera_pitch", 0.0)),
 1970              )
 1971              extra["camera_pitch"] = camera_pitch
 1972              media_frames = self._chunk_media_frame_count(state, block_frames=block_frames)
 1973              chunk_inputs = replace(
 1974                  inputs,
 1975                  camera_trajectory=action_trajectory,
 1976                  camera_actions=chunk_actions,
 1977                  num_frames=media_frames,
 1978                  num_latent_frames=block_frames,
 1979              )
 1980              camera, camera_tail = self._prepare_camera(
 1981                  chunk_inputs,
 1982                  dtype=extra["dtype"],
 1983                  previous=previous,
 1984              )
 1985          elif extra.get("camera_embedding_cache") is not None:
 1986              if (
 1987                  (camera_session := state.interaction_sessions.get("camera"))
 1988                  and isinstance(camera_session, CameraSession)
 1989                  and camera_session.has_received_input
 1990              ):
 1991                  raise ValueError("Cannot use mid-generation camera interaction together with camera_embedding_cache; ")
 1992              trajectory = extra["camera_trajectory_cache"]
 1993              camera = extra["camera_embedding_cache"][:, :, start_frame:stop_frame]
 1994              camera_tail = CameraTrajectory(
 1995                  poses=trajectory.poses[stop_frame - 1 : stop_frame].clone(),
 1996                  intrinsics=trajectory.intrinsics[stop_frame - 1 : stop_frame].clone(),
 1997              )
 1998          elif self._interaction_coordinator is not None and self._interaction_coordinator.has_modality("camera"):
 1999              # Poses come from the latest boundary apply: ``prepare_encode`` for
 2000              # chunk 0, the diffusion runner for later chunks. This method only
 2001              # digests them — it does not apply interactions itself.
 2002              camera_session = state.interaction_sessions.get("camera")
 2003              if not isinstance(camera_session, CameraSession) or camera_session.last_absolute_poses is None:
 2004                  raise RuntimeError(
 2005                      "LingBot camera interaction requires apply_interaction_at_chunk_boundary before prepare_next_chunk."
 2006                  )
 2007              absolute_poses = camera_session.last_absolute_poses
 2008              media_frames = self._chunk_media_frame_count(state, block_frames=block_frames)
 2009              num_latent_frames = block_frames
 2010              if int(absolute_poses.shape[0]) != num_latent_frames:
 2011                  raise ValueError(
 2012                      "camera interaction must produce exactly one pose per latent frame; "
 2013                      f"got {int(absolute_poses.shape[0])}, expected {num_latent_frames}."
 2014                  )
 2015              action_trajectory = camera_trajectory_from_absolute_pose(
 2016                  absolute_poses,
 2017                  width=inputs.width,
 2018                  height=inputs.height,
 2019              )
 2020              chunk_inputs = replace(
 2021                  inputs,
 2022                  camera_trajectory=action_trajectory,
 2023                  camera_actions=None,
 2024                  num_frames=media_frames,
 2025                  num_latent_frames=num_latent_frames,
 2026              )
 2027              camera, camera_tail = self._prepare_camera(
 2028                  chunk_inputs,
 2029                  dtype=extra["dtype"],
 2030                  previous=previous,
 2031                  latent_aligned=True,
 2032              )
 2033          else:
 2034              raise RuntimeError("LingBot step execution is missing a camera trajectory or action script.")
 2035          if camera.shape[2:] != condition.shape[2:]:
 2036              raise RuntimeError(
 2037                  "folded camera and image condition must share latent frame/height/width geometry; "
 2038                  f"got camera={tuple(camera.shape)}, condition={tuple(condition.shape)}."
 2039              )
 2040          generator = getattr(state.sampling, "generator", None)
 2041          if not isinstance(generator, torch.Generator):
 2042              raise ValueError("LingBot World requires the runner-provided torch.Generator.")
 2043          extra["condition"] = condition
 2044          extra["camera"] = camera
 2045          # One camera-modulation cache per block: the four probes and the
 2046          # commit below are separate scheduler steps, so the block runner
 2047          # cannot open the reuse window around them the way generate_block
 2048          # does around its own loop. Holding the cache here makes the window
 2049          # span exactly this block, per request.
 2050          extra["camera_cache"] = CameraModulationCache()
 2051          extra["camera_tail"] = camera_tail
 2052          extra["start_frame"] = start_frame
 2053          extra["ar_cross_attention"] = self._ar_text_caches(
 2054              cast(torch.Tensor, state.prompt_embeds),
 2055              invalidate=False,
 2056          )
 2057          state.latents = randn_tensor(
 2058              (
 2059                  1,
 2060                  self.transformer.config.out_channels,
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:2180-2200
```python
 2180              stage_durations=self.stage_durations if hasattr(self, "stage_durations") else None,
 2181              chunk_index=completed_chunk_index,
 2182              total_chunks=state.total_chunks,
 2183              finished=state.request_denoise_completed,
 2184          )
 2185  
 2186      def _chunk_media_frame_count(self, state: StepRequestState, *, block_frames: int) -> int:
 2187          """Pixel frames this chunk will emit when decoded.
 2188  
 2189          Independent (non-streaming) decode restarts causal expansion every block,
 2190          so each chunk is ``(block_frames - 1) * temporal + 1`` frames.
 2191          Streaming decode expands only the session's opening latent to one frame and every later latent to the full
 2192          temporal factor, so chunk 0 matches the independent count and later chunks are ``block_frames * temporal``.
 2193          """
 2194          decode_state = self._streaming_decode_states.get(state.request_id)
 2195          if decode_state is not None and decode_state.started:
 2196              return block_frames * self.vae_scale_factor_temporal
 2197          return (block_frames - 1) * self.vae_scale_factor_temporal + 1
 2198  
 2199      def peek_chunk_media(self, state: StepRequestState) -> ChunkMediaSpec:
 2200          """Expose this chunk's decoded media extent and latent step count."""
```

## vllm_omni/deploy/lingbot_world_v2_stepwise.yaml:1-50
```python
    1  # LingBot-World 2.0 stepwise deploy: single diffusion stage for WS /v1/realtime/video.
    2  #
    3  # One AsyncOmni request is one rollout: prepare_encode runs once, then every
    4  # four DMD steps stream one AR block. Step execution keeps AR-Diffusion paged KV
    5  # on ARDiffusionModelRunner, so this stage must stay at max_num_seqs=1.
    6  #
    7  # The cache geometry is fixed at load time, so ar_diffusion_height/width must
    8  # match the height/width a client asks for.
    9  
   10  pipeline: lingbot_world
   11  async_chunk: false
   12  distributed_executor_backend: mp
   13  dtype: bfloat16
   14  
   15  stages:
   16    - stage_id: 0
   17      devices: "0"
   18      max_num_seqs: 1
   19      enforce_eager: true
   20      model_class_name: LingBotWorldCausalDMDPipeline
   21      # LingBot runs on the AR-Diffusion engine (engine-level paged KV cache).
   22      engine_backend: vllm_omni.experimental.ar_diffusion.engine.ARDiffusionEngine
   23      # One request, many streamed chunks. streaming_output implies step_execution,
   24      # but both are stated here so the topology is readable on its own.
   25      step_execution: true
   26      streaming_output: true
   27      # num_inference_steps is for the step scheduler, not the pipeline: it sizes a
   28      # request's step budget before the pipeline is reached, so a served request
   29      # does not have to carry it. The pipeline itself pins the causal-fast
   30      # checkpoint's four-step DMD schedule and rejects any other count.
   31      default_sampling_params:
   32        num_inference_steps: 4
   33        output_type: pil
   34        extra_args:
   35          flow_shift: 5.0
   36      model_config:
   37        # Multi-rank width sharding changes floating-point numerics at shard borders.
   38        # Set false for full-frame VAE decode while keeping DiT sequence parallelism.
   39        lingbot_vae_spatial_sharding: true
   40        ar_diffusion_height: 480
   41        ar_diffusion_width: 832
   42        ar_diffusion_kv_config:
   43          gpu_memory_fraction: 0.6
   44          warmup_cudagraph: true
```
