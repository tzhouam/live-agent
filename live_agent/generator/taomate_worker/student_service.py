"""Streaming TaoMate-H3 student (torchrun entry, role ``student``).

Wraps the released runtime from the read-only clone without editing it:

* ``H3Runtime`` (runtime/direct.py) loads FL2VA + LoRA + W8A8/FA3 acceleration exactly as
  ``runner.run_direct`` does; the text encoder is offloaded right after load because the
  teacher ships encoded prompts (T1: no precompiled prompt list, runner.py:293/299-323).
* ``LiveStreamingRuntime`` subclasses ``H3StreamingRuntime`` and intercepts
  ``_renorm_clean_video_rows`` (called once per chunk with the final clean latents, before
  the sigma-0 KV commit) to decode and emit that chunk immediately (T3).
* ``InMemoryTeacher`` replaces ``ExternalBase10TeacherArtifact``: it serves the milestones
  received from the teacher service instead of ``/dev/shm/request_XX.pt`` files and drops
  the prompt/seed-list checks of base10_teacher.py:158-179 (T2).

The runtime's own check that the published audio equals the teacher's clean latent
(streaming/runtime.py:739-743) stays active and is reported per request.
"""

from __future__ import annotations

import argparse
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

from . import protocol as P
from .common import set_triton_cache, Cancelled, CommandLoop, gather_memory, rank_info
from .stream_decode import StreamingAudioDecoder, StreamingVideoDecoder, samples_at_frame

_VIDEO_NOISE_REQUEST_STRIDE = 1_000_003  # runner.py:27


class InMemoryTeacher:
    """Duck-typed stand-in for ExternalBase10TeacherArtifact (inference/base10_teacher.py)."""

    def __init__(self) -> None:
        self.requests: dict[int, dict[str, Any]] = {}

    def put(self, local_index: int, payload: dict[str, Any]) -> None:
        self.requests[local_index] = payload
        for stale in [k for k in self.requests if k < local_index - 1]:
            del self.requests[stale]

    def audio_noise_seed(self, request_index: int) -> int:
        return int(self.requests[request_index]["audio_noise_seed"])

    def load_request(self, torch: Any, *, request_index: int, audio_latent_count: int,
                     device: Any) -> dict[str, Any]:
        payload = self.requests.get(request_index)
        if payload is None:
            raise RuntimeError(f"no teacher milestones for local request {request_index}")
        if int(payload["audio_latent_count"]) != int(audio_latent_count):
            raise RuntimeError(
                f"teacher produced {payload['audio_latent_count']} audio latents, "
                f"student expects {audio_latent_count}"
            )
        milestones = {
            index: value.to(device=device, dtype=torch.float32)
            for index, value in enumerate(payload["milestones"])
        }
        receipt = {
            "mode": "base10_fl2va_tail40_rollover",
            "source": "resident_teacher_service",
            "audio_noise_seed": self.audio_noise_seed(request_index),
            "teacher_receipt": dict(payload.get("receipt") or {}),
        }
        return {"milestones": milestones, "receipt": receipt}


def _make_runtime_class():
    from taomate_h3.streaming.geometry import canonical_continuation_plan
    from taomate_h3.streaming.runtime import H3StreamingRuntime

    class LiveStreamingRuntime(H3StreamingRuntime):
        def __init__(self, *, teacher: InMemoryTeacher, on_chunk) -> None:
            super().__init__(base10_teacher=teacher)
            self._on_chunk = on_chunk
            self._chunk_counter = 0

        def run(self, **kwargs: Any) -> Any:
            self._chunk_counter = 0
            return super().run(**kwargs)

        def _renorm_clean_video_rows(self, rows: Any) -> Any:
            clean = super()._renorm_clean_video_rows(rows)
            plan = (
                self.plan if self._request_index == 0
                else canonical_continuation_plan(self.plan, request_index=self._request_index)
            )
            phase = plan.phases[self._chunk_counter]
            self._on_chunk(self._request_index, self._chunk_counter, phase, clean)
            self._chunk_counter += 1
            return clean

    return LiveStreamingRuntime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--width", type=int, default=864)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--audio-left-context", type=int, default=48)
    parser.add_argument("--audio-right-context", type=int, default=24)
    args = parser.parse_args(argv)

    t_process = time.time()
    set_triton_cache(P.ROLE_STUDENT)
    loop = CommandLoop(P.ROLE_STUDENT)
    loop.connect()
    rank, world, _ = rank_info()

    import torch

    from taomate_h3.model import denoise as denoise_module
    from taomate_h3.model.geometry import direct_5s_geometry
    from taomate_h3.model.packed_tokens import (
        minimax_h3_unpack_audio_tokens,
        minimax_h3_unpatchify_video_tokens,
    )
    from taomate_h3.runtime import H3Runtime

    t_load = time.time()
    runtime = H3Runtime(
        model_root=args.model_root,
        adapter_root=args.adapter,
        output_root=Path(tempfile.mkdtemp(prefix="la-taomate-student-")),
        ulysses_degree=world // 2,
    )
    loop.setup_groups()
    runtime.pipeline._offload_text()
    decoder = runtime.pipeline._load_output_decoder()
    device = runtime.device
    video_decoder = StreamingVideoDecoder(decoder, device=device, rank=rank,
                                          group=torch.distributed.group.WORLD)
    audio_decoder = (
        StreamingAudioDecoder(decoder, device=device, left=args.audio_left_context,
                              right=args.audio_right_context)
        if rank == 0 else None
    )
    geometry = direct_5s_geometry(width=args.width, height=args.height)
    latent_hw = (geometry.video_latent_h // 2, geometry.video_latent_w // 2)
    torch.cuda.synchronize()
    loop.send({"type": P.READY, "load_s": time.time() - t_load,
               "process_to_ready_s": time.time() - t_process,
               "timings": dict(runtime._timings), "memory": gather_memory()})

    # phase-start clock: patch the denoise loop the streaming runtime imports per call
    clock: dict[str, float] = {"phase_start": 0.0}
    original_loop = denoise_module.minimax_h3_denoise_loop

    def timed_loop(*a: Any, **k: Any) -> Any:
        torch.cuda.synchronize()
        clock["phase_start"] = time.time()
        return original_loop(*a, **k)

    denoise_module.minimax_h3_denoise_loop = timed_loop

    runtime_class = _make_runtime_class()
    teacher = InMemoryTeacher()
    state: dict[str, Any] = {"session": 0, "request_index": -1}

    def on_chunk(local_request: int, chunk_index: int, phase: Any, clean_rows: Any) -> None:
        if loop.cancel_requested():
            raise Cancelled()
        torch.cuda.synchronize()
        t_denoised = time.time()
        latents = minimax_h3_unpatchify_video_tokens(
            clean_rows.float(),
            latent_shape=(phase.video_latent_count, latent_hw[0], latent_hw[1], 24),
            patch_size=(1, 2, 2),
        )
        frame_start, frames = video_decoder.push(latents)
        n_frames = video_decoder.frames_emitted - frame_start
        audio = None
        audio_ctx = None
        s0 = samples_at_frame(frame_start)
        if rank == 0:
            audio, audio_ctx = audio_decoder.decode_range(s0, samples_at_frame(frame_start + n_frames))
        torch.cuda.synchronize()
        t_decoded = time.time()
        loop.send({
            "type": P.CHUNK, "session": state["session"], "request_index": state["request_index"],
            "local_index": local_request, "chunk_index": chunk_index,
            "frame_start": frame_start, "n_frames": n_frames, "fps": 24.0,
            "latent_count": int(phase.video_latent_count), "video": frames, "audio": audio,
            "sample_rate": 32000, "audio_sample_start": s0, "audio_context": audio_ctx,
            "t_phase_start": clock["phase_start"], "t_denoised": t_denoised,
            "t_decoded": t_decoded, "t_ready": time.time(),
        })

    streaming = runtime_class(teacher=teacher, on_chunk=on_chunk)
    session_audio: list[Any] = []

    def reset_all(session: int) -> Any:
        nonlocal streaming
        try:
            streaming.release_retained_state()
        except RuntimeError:
            streaming._running = False
            streaming.release_retained_state()
        streaming = runtime_class(teacher=teacher, on_chunk=on_chunk)
        teacher.requests.clear()
        video_decoder.reset()
        if audio_decoder is not None:
            audio_decoder.reset()
        session_audio.clear()
        state["session"] = session
        torch.cuda.empty_cache()

    while True:
        command = loop.next_command()
        kind = command["type"]
        if kind == P.SHUTDOWN:
            break
        if kind == P.RESET:
            reset_all(int(command["session"]))
            loop.send({"type": "reset_done", "session": int(command["session"])})  # state released
            continue
        if kind == "flush":
            frame_start, frames = video_decoder.flush()
            loop.send({"type": "flushed", "session": state["session"], "frame_start": frame_start,
                       "video": frames})
            continue
        if kind == "full_audio":
            if rank == 0 and session_audio:
                full = torch.cat(session_audio, dim=2)
                loop.send({"type": "full_audio", "session": state["session"],
                           "audio": audio_decoder.decode_full(full)})
            continue
        if kind != P.GENERATE:
            continue
        session = int(command["session"])
        local = int(command["local_index"])
        state["request_index"] = int(command["request_index"])
        try:
            if local != streaming._request_index:
                raise RuntimeError(f"student expected local request {streaming._request_index}, got {local}")
            payload = P.unpack_blob(command["blob"])
            teacher.put(local, payload)
            clean_audio = payload["milestones"][2]
            request_audio = minimax_h3_unpack_audio_tokens(
                clean_audio, audio_t=int(clean_audio.shape[0]), audio_channel=2
            )  # [2, 32, n]
            session_audio.append(request_audio)
            if audio_decoder is not None:
                audio_decoder.append(request_audio)
            torch.cuda.synchronize()
            t_start = time.time()
            loop.send({"type": P.REQUEST_START, "session": session,
                       "request_index": state["request_index"], "t": t_start})
            seed = int(command["seed"])
            video_latents, audio_latents = runtime.generate_latents(
                video_noise_seed=(seed + local * _VIDEO_NOISE_REQUEST_STRIDE) % (2**63),
                audio_noise_seed=teacher.audio_noise_seed(local),
                width=args.width,
                height=args.height,
                precomputed_text=(payload["text_hidden"], payload["text_tags"]),
                denoise_loop=streaming.run,
            )
            execution = streaming.executions[-1]
            exact = bool((execution.audio_teacher or {}).get("published_clean_audio_exact_match"))
            message = {
                "type": P.REQUEST_DONE, "session": session,
                "request_index": state["request_index"], "local_index": local,
                "t": time.time(), "t_start": t_start, "audio_teacher_exact_match": exact,
                "frames_emitted": video_decoder.frames_emitted,
                "published_native_frames": int(execution.published_native_frames),
                "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
            }
            if command.get("return_latents"):
                message["latents"] = {"video": video_latents.numpy(), "audio": audio_latents.numpy()}
            loop.send(message)
        except Cancelled:
            loop.send({"type": "cancelled", "session": session,
                       "request_index": state["request_index"], "t": time.time()})
            reset_all(state["session"])
        except Exception as exc:
            loop.send({"type": P.ERROR, "session": session,
                       "request_index": state["request_index"],
                       "message": f"{type(exc).__name__}: {exc}",
                       "traceback": traceback.format_exc()})
            reset_all(state["session"])
    loop.flush()
    torch.distributed.barrier()
    torch.distributed.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
