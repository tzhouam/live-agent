"""CPU tests for the TaoMate-H3 adapter protocol (fake workers), plus opt-in GPU tests.

The fake teacher/student speak the real wire protocol over the adapter's
``multiprocessing.connection`` listener, so these tests cover the queueing, lookahead,
session/reset and error paths of ``TaoMateH3Generator`` without torch or GPUs.

GPU test: set ``LA_TAOMATE_GPU_TEST=1`` and run inside a canhazgpu reservation of >= 4 GPUs.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from multiprocessing.connection import Client
from pathlib import Path

import numpy as np
import pytest

from live_agent.generator.taomate_h3 import TaoMateH3Generator, WorkerError, split_devices
from live_agent.generator.taomate_worker import protocol as P

LAYOUT = (34, 34, 34, 17)


class FakeWorker(threading.Thread):
    """Speaks the worker side of the protocol; records every command it receives."""

    def __init__(self, gen: TaoMateH3Generator, role: str, *, delay: float = 0.0,
                 fail_on: int | None = None) -> None:
        super().__init__(daemon=True)
        self.gen, self.role, self.delay, self.fail_on = gen, role, delay, fail_on
        self.received: list[dict] = []
        self.events: list[tuple[str, int, float]] = []
        self.session = 0

    def run(self) -> None:
        conn = Client(self.gen.address, authkey=self.gen.authkey)
        conn.send({"type": P.HELLO, "role": self.role, "pid": 0, "world_size": 1})
        conn.send({"type": P.READY, "role": self.role, "load_s": 0.0})
        while True:
            try:
                msg = conn.recv()
            except EOFError:
                return
            self.received.append(msg)
            kind = msg["type"]
            if kind == P.SHUTDOWN:
                conn.close()
                return
            if kind == P.RESET:
                self.session = msg["session"]
                continue
            if msg.get("session", 0) < self.session:
                continue
            k = msg["request_index"]
            if self.fail_on == k:
                conn.send({"type": P.ERROR, "role": self.role, "session": msg["session"],
                           "request_index": k, "message": "boom"})
                continue
            if kind == P.TEACH:
                t0 = time.time()
                self.events.append(("teach_start", k, t0))
                time.sleep(self.delay)
                conn.send({"type": P.TEACHER_DONE, "role": self.role, "session": msg["session"],
                           "request_index": k, "local_index": msg["local_index"],
                           "t_start": t0, "t_text_done": t0, "t_done": time.time(),
                           "audio_latent_count": 199, "blob": f"blob-{k}".encode()})
            elif kind == P.GENERATE:
                assert msg["blob"] == f"blob-{k}".encode()
                t0 = time.time()
                self.events.append(("generate_start", k, t0))
                conn.send({"type": P.REQUEST_START, "session": msg["session"],
                           "request_index": k, "t": t0})
                frame = 0
                for ci, n in enumerate(LAYOUT):
                    time.sleep(self.delay / 4)
                    conn.send({
                        "type": P.CHUNK, "session": msg["session"], "request_index": k,
                        "local_index": msg["local_index"], "chunk_index": ci,
                        "frame_start": frame, "n_frames": n, "fps": 24.0,
                        "video": np.full((n, 4, 4, 3), k, np.uint8),
                        "audio": np.zeros((n * 4000 // 3, 2), np.float32), "sample_rate": 32000,
                        "t_phase_start": t0, "t_denoised": time.time(), "t_decoded": time.time(),
                        "t_ready": time.time(),
                    })
                    frame += n
                self.events.append(("generate_done", k, time.time()))
                conn.send({"type": P.REQUEST_DONE, "session": msg["session"], "request_index": k,
                           "local_index": msg["local_index"], "t": time.time(),
                           "audio_teacher_exact_match": True, "frames_emitted": frame})


async def _start(gen: TaoMateH3Generator, **kw) -> tuple[FakeWorker, FakeWorker]:
    task = asyncio.create_task(gen.start())
    while gen.address is None:
        await asyncio.sleep(0.01)
    teacher = FakeWorker(gen, P.ROLE_TEACHER, delay=kw.get("teacher_delay", 0.0),
                         fail_on=kw.get("teacher_fail_on"))
    student = FakeWorker(gen, P.ROLE_STUDENT, delay=kw.get("student_delay", 0.0),
                         fail_on=kw.get("student_fail_on"))
    teacher.start()
    student.start()
    await asyncio.wait_for(task, 10)
    return teacher, student


async def _collect(gen: TaoMateH3Generator, n: int, timeout: float = 10.0) -> list:
    out = []

    async def run():
        async for chunk in gen.chunks():
            out.append(chunk)
            if len(out) == n:
                return

    await asyncio.wait_for(run(), timeout)
    return out


def _gen(**kw) -> TaoMateH3Generator:
    return TaoMateH3Generator(launch=False, student_devices="0,1,2,3", **kw)


def test_split_devices():
    assert split_devices("0,1,2,3,4,5") == ("0,1,2,3", "4,5")
    assert split_devices("0,1,2,3") == ("0,1,2,3", None)
    assert split_devices("0,1,2,3,4,5,6,7") == ("0,1,2,3,4,5,6,7", None)
    with pytest.raises(ValueError):
        split_devices("0,1")


def test_blob_roundtrip():
    value = {"a": np.arange(3), "b": "x"}
    back = P.unpack_blob(P.pack_blob(value))
    assert back["b"] == "x" and back["a"].tolist() == [0, 1, 2]


def test_shm_handoff_roundtrip():
    video = np.random.randint(0, 255, (34, 128, 128, 3), dtype=np.uint8)  # > 1 MiB
    small = np.zeros((10, 2), np.float32)
    message = P.to_shm({"type": P.CHUNK, "video": video, "audio": small})
    assert isinstance(message["video"], dict) and message["audio"] is small
    path = message["video"]["shm"]
    back = P.from_shm(message["video"])
    assert np.array_equal(back, video) and not os.path.exists(path)


def test_mid_session_prompts_stream_in_order():
    async def main():
        gen = _gen()
        teacher, student = await _start(gen)
        prompts = [f"prompt {k}" for k in range(3)]
        chunks = []
        for k, prompt in enumerate(prompts):  # submitted one at a time, mid-session
            await gen.submit(k, prompt)
            chunks += await _collect(gen, 4)
        await gen.close()
        return gen, teacher, student, chunks, prompts

    gen, teacher, student, chunks, prompts = asyncio.run(main())
    assert [(c.request_index, c.chunk_index) for c in chunks] == [
        (k, i) for k in range(3) for i in range(4)
    ]
    assert [c.meta["prompt"] for c in chunks[::4]] == prompts
    assert all(c.video.shape[0] == c.n_frames for c in chunks)
    teach = [m for m in teacher.received if m["type"] == P.TEACH]
    generate = [m for m in student.received if m["type"] == P.GENERATE]
    assert [m["prompt"] for m in teach] == prompts == [m["prompt"] for m in generate]
    assert [m["local_index"] for m in generate] == [0, 1, 2]
    for timing in gen.timings:
        assert timing.t_teacher_start is not None and timing.t_teacher_done is not None
        assert timing.t_student_start is not None and timing.t_done is not None
        assert timing.lead_s is not None and timing.lead_s >= 0
    assert all(gen.request_extras[k]["audio_teacher_exact_match"] for k in range(3))


def test_submit_must_be_in_order():
    async def main():
        gen = _gen()
        await _start(gen)
        with pytest.raises(ValueError):
            await gen.submit(1, "x")
        await gen.submit(0, "x")
        with pytest.raises(ValueError):
            await gen.submit(0, "x")
        await gen.close()

    asyncio.run(main())


@pytest.mark.parametrize("lookahead", [True, False])
def test_teacher_lookahead(lookahead):
    async def main():
        gen = _gen(lookahead=lookahead)
        teacher, student = await _start(gen, student_delay=0.4)
        await gen.submit(0, "a")
        await gen.submit(1, "b")
        await _collect(gen, 8)
        await gen.close()
        return teacher, student

    teacher, student = asyncio.run(main())
    teach1 = next(t for name, k, t in teacher.events if name == "teach_start" and k == 1)
    gen0_done = next(t for name, k, t in student.events if name == "generate_done" and k == 0)
    if lookahead:
        assert teach1 < gen0_done  # teacher k=1 overlaps student k=0
    else:
        assert teach1 >= gen0_done - 0.05  # sequential: teacher waits for the student


def test_reset_starts_new_session_and_drops_stale_chunks():
    async def main():
        gen = _gen()
        teacher, student = await _start(gen, student_delay=0.4)
        await gen.submit(0, "old")
        first = await _collect(gen, 1)
        await gen.reset()
        await gen.submit(1, "new")
        rest = await _collect(gen, 4)
        await gen.close()
        return gen, teacher, student, first, rest

    gen, teacher, student, first, rest = asyncio.run(main())
    assert first[0].request_index == 0
    assert [c.request_index for c in rest] == [1, 1, 1, 1]  # no stale session-0 chunks
    assert all(c.meta["session"] == 1 for c in rest)
    generate = [m for m in student.received if m["type"] == P.GENERATE]
    assert generate[-1]["local_index"] == 0 and generate[-1]["session"] == 1
    assert any(m["type"] == P.RESET for m in teacher.received)
    assert gen.next_request_index == 2


def test_worker_error_surfaces_in_chunks():
    async def main():
        gen = _gen()
        await _start(gen, student_fail_on=0)
        await gen.submit(0, "x")
        with pytest.raises(WorkerError):
            await _collect(gen, 1)
        await gen.close()

    asyncio.run(main())


# ----------------------------------------------------------------------------- torch-only


def test_streaming_video_windows_match_one_shot_decode():
    """Streaming window schedule == bundled klvae.decode_temporal on a fake linear decoder."""

    torch = pytest.importorskip("torch")
    vae_dir = Path(
        "/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/"
        "42ed227ee7df40d41602854ae760620d6eb651fe/FL2VA/video_vae"
    )
    if not (vae_dir / "klvae.py").exists():
        pytest.skip("H3 video VAE code not available")
    from live_agent.generator.taomate_worker import stream_decode as sd

    class Fake:
        tokens_chunk_size, token_overlap, token_drop = 5, 2, 3
        frame_pre_padding, frame_overlap, vae_ratio_t, clip_length = 3, 5, 4, 17
        isolated_first_frame = isolated_last_frame = False
        training = False

        def _adaptive_decode(self, z):  # deterministic, position-dependent fake decoder
            frames = z.repeat_interleave(4, dim=2)[:, :3]
            ramp = torch.arange(frames.shape[2], dtype=frames.dtype).view(1, 1, -1, 1, 1)
            return frames + 0.01 * ramp

        def blend(self, a, b, blend_extent, dim):
            n = min(a.shape[dim], b.shape[dim], blend_extent)
            w = torch.arange(n, dtype=b.dtype) / n
            shape = [1] * b.ndim
            shape[dim] = n
            w = w.view(shape)
            b = b.clone()
            b[:, :, :n] = a[:, :, -n:] * (1 - w) + b[:, :, :n] * w
            return b

    # one-shot reference: the real klvae.decode_temporal (non-streaming branch), loaded as a
    # package the same way taomate_h3.model.components does
    import sys

    clone = Path(__file__).resolve().parents[1] / "external" / "TaoMate-H3" / "src"
    if str(clone) not in sys.path:
        sys.path.insert(0, str(clone))
    try:
        from taomate_h3.model.components import _component_package

        klvae = _component_package(vae_dir, "klvae.py")
    except Exception as exc:  # e.g. diffusers missing in this interpreter
        pytest.skip(f"cannot import bundled klvae: {exc}")

    fake = Fake()
    fake._decode_temporal_pad_frames = lambda z, p: klvae.AutoencoderKL._decode_temporal_pad_frames(fake, z, p)
    torch.manual_seed(0)
    latents = torch.randn(1, 24, 37 + 35 * 2, 2, 2)
    klvae._resolve_temporal_stream_cat = lambda: False
    reference = klvae.AutoencoderKL.decode_temporal(fake, latents)

    dec = object.__new__(sd.StreamingVideoDecoder)
    dec.torch, dec.device, dec.rank, dec.model = torch, torch.device("cpu"), 0, fake
    dec._reverse_normalize = lambda x: x.float()
    dec.reset()
    streamed, sizes = [], []
    chunk_latents = [12, 10, 10, 5] + [10, 10, 10, 5] * 2
    start = 0
    for n in chunk_latents:
        out = dec.advance(latents[:, :, start : start + n])
        start += n
        sizes.append(0 if out is None else out.shape[2])
        if out is not None:
            streamed.append(out)
    streamed.append(dec.overlap)  # final flush
    streamed = torch.cat(streamed, dim=2)
    assert sizes == [34, 34, 34, 17] * 3
    assert streamed.shape == reference.shape == (1, 3, 124 + 119 * 2, 2, 2)
    assert torch.allclose(streamed, reference, atol=1e-6)


# ----------------------------------------------------------------------------- GPU (opt-in)


@pytest.mark.skipif(os.environ.get("LA_TAOMATE_GPU_TEST") != "1",
                    reason="set LA_TAOMATE_GPU_TEST=1 inside a >=4 GPU canhazgpu reservation")
def test_gpu_two_requests():
    async def main():
        gen = TaoMateH3Generator(return_latents=False)
        await gen.start()
        try:
            chunks = []
            for k, prompt in enumerate(["A presenter waves.", "A presenter nods."]):
                await gen.submit(k, prompt)
                chunks += await _collect(gen, 4, timeout=600)
            return gen, chunks
        finally:
            await gen.close()

    gen, chunks = asyncio.run(main())
    assert [c.n_frames for c in chunks] == [34, 34, 34, 17] * 2
    assert all(gen.request_extras[k]["audio_teacher_exact_match"] for k in range(2))
