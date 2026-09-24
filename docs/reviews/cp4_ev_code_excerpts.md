# Additional code excerpts, vllm-omni @ 7b4dc7633bde8642f0c05f77bd018751541df404

## vllm_omni/diffusion/interaction/modality_handlers/camera.py:40-50
```python
   40      """Canonical absolute camera pose used by the shared timeline.
   41  
   42      Coordinates follow Unity semantics: ``+X`` right, ``+Y`` up,
   43      ``+Z`` forward. Session start is the identity transform;
   44      ``target`` poses are relative to that origin.
   45      """
   46  
   47      translation: Vec3 = (0.0, 0.0, 0.0)
   48      rotation: Quat = _IDENTITY_QUAT
   49  
   50      @classmethod
```

## vllm_omni/diffusion/interaction/modality_handlers/camera.py:100-112
```python
  100      # Since a camera session is not lazily initialized, use this field to mark that a client enqueue is ever received.
  101      has_received_input: bool = False
  102  
  103  
  104  class SE3DeltaCameraHandler(InteractionHandler):
  105      """Generic camera timeline that samples absolute poses per frame.
  106  
  107      * ``mode=target``: lerp toward an absolute pose (relative to session start).
  108      * ``mode=velocity``: hold a structural SE3 delta until replaced.
  109  
  110      ``received_at`` is resolved on the media grid (``num_media_frames``/``fps``), then mapped onto latent steps.
  111      Later integration and ``last_absolute_poses`` aligns with ``num_latent_frames``.
  112      """
```

## vllm_omni/diffusion/interaction/modality_handlers/camera.py:255-360
```python
  255          fps: float,
  256          num_latent_frames: int,
  257          boundary_at: float,
  258      ) -> tuple[list[CameraPose], list[str], list[str], list[str]]:
  259          """Sample absolute poses for this chunk under target/velocity semantics."""
  260          num_media_frames = max(int(num_media_frames), 1)
  261          num_latent_frames = max(int(num_latent_frames), 1)
  262          pending = list(session.pending_events)
  263          session.pending_events.clear()
  264  
  265          by_latent: dict[int, list[QueuedCameraEvent]] = {}
  266          for event in pending:
  267              media_frame = resolve_event_frame_offset(
  268                  received_at=event.received_at,
  269                  previous_boundary_at=session.last_boundary_at,
  270                  num_frames=num_media_frames,
  271                  fps=fps,
  272              )
  273              latent_idx = _media_frame_to_latent(
  274                  media_frame,
  275                  num_media_frames=num_media_frames,
  276                  num_latent_frames=num_latent_frames,
  277              )
  278              by_latent.setdefault(latent_idx, []).append(event)
  279          for events in by_latent.values():
  280              events.sort(key=lambda item: item.received_at)
  281  
  282          started: list[str] = []
  283          completed: list[str] = []
  284          seen_completed: set[str] = set()
  285          poses: list[CameraPose] = []
  286  
  287          def _mark_completed(event_id: str) -> None:
  288              if event_id not in seen_completed:
  289                  seen_completed.add(event_id)
  290                  completed.append(event_id)
  291  
  292          for latent_idx in range(num_latent_frames):
  293              for event in by_latent.get(latent_idx, []):
  294                  started.append(event.event_id)
  295                  cancelled_id = self._activate_event(session, event)
  296                  if cancelled_id is not None:
  297                      _mark_completed(cancelled_id)
  298              just_completed = self._step_one_frame(session, num_latent_frames)
  299              poses.append(session.current_pose.clone())
  300              if just_completed is not None:
  301                  _mark_completed(just_completed)
  302  
  303          active: list[str] = []
  304          if session.active_event is not None:
  305              active.append(session.active_event.event_id)
  306  
  307          session.last_boundary_at = boundary_at
  308          return poses, started, active, completed
  309  
  310      def _activate_event(self, session: CameraSession, event: QueuedCameraEvent) -> str | None:
  311          """Activate ``event``, returning the event_id cancelled by this replacement if any."""
  312          cancelled_id: str | None = None
  313          if session.active_event is not None and session.active_event.event_id != event.event_id:
  314              cancelled_id = session.active_event.event_id
  315  
  316          event.elapsed_transition_chunks = 0.0
  317          event.elapsed_transition_frames = 0
  318          session.active_event = event
  319          if event.mode == "target":
  320              session.target_source = session.current_pose.clone()
  321          else:
  322              session.target_source = None
  323          return cancelled_id
  324  
  325      def _clear_active_target(self, session: CameraSession) -> str:
  326          """Snap to the target pose, clear the active target track, and return its event_id."""
  327          assert session.active_event is not None and session.active_event.mode == "target"
  328          event = session.active_event
  329          event_id = event.event_id
  330          session.current_pose = event.pose.clone()
  331          session.active_event = None
  332          session.target_source = None
  333          return event_id
  334  
  335      def _step_one_frame(self, session: CameraSession, total_num_frames_this_chunk: int) -> str | None:
  336          """Advance the active camera command by one frame."""
  337          event = session.active_event
  338          if event is None:
  339              return None
  340  
  341          if event.mode == "target":
  342              duration = event.transition_chunks
  343              source = session.target_source or session.current_pose
  344              target = event.pose
  345              if duration <= 0:
  346                  return self._clear_active_target(session)
  347  
  348              total_frames = max(1, int(round(duration * float(total_num_frames_this_chunk))))
  349              event.elapsed_transition_frames += 1
  350              event.elapsed_transition_chunks = event.elapsed_transition_frames / float(total_num_frames_this_chunk)
  351              alpha = min(1.0, event.elapsed_transition_frames / float(total_frames))
  352              session.current_pose = _lerp_pose(source, target, alpha)
  353              if event.elapsed_transition_frames >= total_frames:
  354                  return self._clear_active_target(session)
  355              return None
  356  
  357          # Velocity: apply the held structural SE3 delta once per frame.
  358          session.current_pose = _compose_pose(session.current_pose, event.pose)
  359          return None
  360  
```

## serving_video_output_stream.py:10-30 and 75-92 (ping semantics)
```python
   10              "interaction": {
   11                  "event_id": "...",
   12                  "event": {"prompt": "..."},
   13                  "transition_chunks": (optional, integer),
   14              },
   15          }
   16          {"type": "session.stop"}
   17          {"type": "session.ping"}  # optional; refreshes stall clock
   18  
   19      Server -> Client:
   20          {"type": "video.start", "request_id": "...", "config": {...}, "format": "m4s"}
   21          {"type": "video.chunk_metadata", ...}
   22          <binary frame: fragmented MP4 bytes>
   23          {"type": "session.interaction.queued", "request_id": "...", "event_id": "..."}
   24          {"type": "session.done", ...}
   25          {"type": "session.pong"}  # reply to session.ping
   26          {"type": "error", "message": "..."}
   27  """
   28  
   29  from __future__ import annotations
   30  
   75  _MAX_CONTROL_MESSAGE_SIZE = 128 * 1024
   76  
   77  
   78  class _SessionProgress:
   79      """Tracks last server-side progress for stall-timeout enforcement."""
   80  
   81      def __init__(self) -> None:
   82          self._last_at = time.monotonic()
   83  
   84      def touch(self) -> None:
   85          self._last_at = time.monotonic()
   86  
   87      def stalled_for(self, stall_timeout: float) -> bool:
   88          return time.monotonic() - self._last_at > stall_timeout
   89  
   90  
   91  class OmniStreamingVideoOutputHandler:
   92      """Handles `/v1/realtime/video` sessions for generated video output."""
```
