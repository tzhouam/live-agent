"""Wire protocol between ``TaoMateH3Generator`` (main process) and the TaoMate-H3 workers.

Topology
--------
The adapter owns a ``multiprocessing.connection.Listener`` on 127.0.0.1 (random port,
random authkey) and launches two torchrun process groups:

* **teacher** (``teacher_service``): base MiniMax H3 FL2VA in BF16 without the LoRA plus the
  resident Qwen3-VL text encoder. For every locked prompt it encodes the text and runs the
  10-state/9-forward audio-only teacher (tail40 rollover), exactly as
  ``taomate_h3.teacher._generate_request`` does.
* **student** (``student_service``): the released TaoMate-H3 streaming runtime (W8A8 + LoRA,
  FA3, persistent clean A/V KV) plus streaming video/audio VAE decoders.

Only rank 0 of each group holds a socket; it relays every command to the other ranks with
``torch.distributed.broadcast_object_list``. Messages are plain ``dict`` objects pickled by
``multiprocessing.connection`` (trusted local peers only; the authkey is HMAC-checked).

Message flow (``→`` adapter to worker, ``←`` worker to adapter)
----------------------------------------------------------------
Both roles::

    ← hello   {role, pid, world_size, devices}
    ← ready   {role, load_s, memory}            model loaded; commands accepted
    → reset   {session}                         drop all state; later commands carry session
    ← reset_done {session}                      (both roles) state released for that session
    → shutdown {}
    ← error   {role, session, request_index, message}

Teacher::

    → teach   {session, request_index, local_index, prompt, seed}
    ← teacher_done {session, request_index, local_index, t_start, t_text_done, t_done,
                    audio_latent_count, blob}

``blob`` is an opaque pickle (torch tensors: text hidden/tags, three float32 milestones) that
the adapter forwards unchanged, so the adapter itself never needs torch.

Student::

    → generate {session, request_index, local_index, prompt, seed, blob, return_latents}
    ← request_start {session, request_index, t}
    ← chunk   {session, request_index, chunk_index, frame_start, n_frames, fps,
               video uint8[T,H,W,3], audio float32[S,2], sample_rate, audio_sample_start,
               t_phase_start, t_denoised, t_decoded, t_ready}
    ← request_done {session, request_index, t, audio_teacher_exact_match, frames_emitted,
                    latents?}

Sessions: ``reset`` increments the session id. Workers drop queued commands whose
``session`` is older than the newest session they have seen, and the student aborts an
in-flight request at the next chunk boundary. The adapter ignores stale replies.

Times ``t*`` are ``time.time()`` epoch seconds on the (single) host; the adapter maps
them to its monotonic clock.
"""

from __future__ import annotations

import os
import pickle
import threading
from multiprocessing.connection import Client, Connection
from typing import Any

ENV_ADDRESS = "LA_TAOMATE_ADDR"
ENV_AUTHKEY = "LA_TAOMATE_AUTHKEY"
ENV_ROLE = "LA_TAOMATE_ROLE"

ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"

# message types
HELLO = "hello"
READY = "ready"
RESET = "reset"
SHUTDOWN = "shutdown"
ERROR = "error"
TEACH = "teach"
TEACHER_DONE = "teacher_done"
GENERATE = "generate"
REQUEST_START = "request_start"
CHUNK = "chunk"
REQUEST_DONE = "request_done"


class Channel:
    """Thread-safe send wrapper around a ``multiprocessing.connection.Connection``."""

    def __init__(self, conn: Connection) -> None:
        self.conn = conn
        self._lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> None:
        with self._lock:
            self.conn.send(message)

    def recv(self) -> dict[str, Any]:
        return self.conn.recv()

    def close(self) -> None:
        try:
            self.conn.close()
        except OSError:
            pass


def parse_address(value: str) -> tuple[str, int]:
    host, port = value.rsplit(":", 1)
    return host, int(port)


def connect_from_env(role: str) -> Channel:
    """Worker rank 0: connect back to the adapter and say hello."""

    address = parse_address(os.environ[ENV_ADDRESS])
    authkey = bytes.fromhex(os.environ[ENV_AUTHKEY])
    channel = Channel(Client(address, authkey=authkey))
    return channel


SHM_DIR = "/dev/shm"
SHM_MIN_BYTES = 1 << 20


def to_shm(message: dict[str, Any], keys: tuple[str, ...] = ("video", "audio")) -> dict[str, Any]:
    """Worker side: move large numpy payloads to /dev/shm files; the message carries
    ``{"shm": path}`` instead. Pickling 40 MB frames through the socket cost ~0.3 s/chunk
    in the first validation run; a /dev/shm handoff is a single memcpy on each side."""

    import uuid

    import numpy as np

    for key in keys:
        value = message.get(key)
        if isinstance(value, np.ndarray) and value.nbytes >= SHM_MIN_BYTES:
            path = os.path.join(SHM_DIR, f"la-taomate-{os.getpid()}-{uuid.uuid4().hex[:12]}.npy")
            np.save(path, value, allow_pickle=False)
            message[key] = {"shm": path}
    return message


def discard_shm(message: dict[str, Any], keys: tuple[str, ...] = ("video", "audio")) -> None:
    """Adapter side: delete the payload files of a message that will not be loaded (stale
    session, error, shutdown) so private media never lingers in /dev/shm."""

    for key in keys:
        value = message.get(key)
        if isinstance(value, dict) and "shm" in value:
            try:
                os.unlink(value["shm"])
            except OSError:
                pass


def sweep_shm(pids: list[int]) -> int:
    """Remove payload files left by the given worker processes (shutdown)."""
    import glob

    n = 0
    for pid in pids:
        for path in glob.glob(os.path.join(SHM_DIR, f"la-taomate-{pid}-*.npy")):
            try:
                os.unlink(path)
                n += 1
            except OSError:
                pass
    return n


def sweep_dead_shm() -> int:
    """Remove payload files whose writer process no longer exists (rank processes are not all
    known to the adapter; after shutdown every writer is dead, and live sessions are untouched)."""
    import glob
    import re as _re

    n = 0
    for path in glob.glob(os.path.join(SHM_DIR, "la-taomate-*-*.npy")):
        m = _re.search(r"la-taomate-(\d+)-", os.path.basename(path))
        if not m:
            continue
        try:
            os.kill(int(m.group(1)), 0)
            continue  # writer alive
        except ProcessLookupError:
            pass
        except PermissionError:
            continue  # another user's live process
        try:
            os.unlink(path)
            n += 1
        except OSError:
            pass
    return n


def from_shm(value: Any) -> Any:
    """Adapter side: load (and delete) a payload written by ``to_shm``."""

    if isinstance(value, dict) and "shm" in value:
        import numpy as np

        path = value["shm"]
        try:
            return np.load(path, allow_pickle=False)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    return value


def pack_blob(value: Any) -> bytes:
    return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)


def unpack_blob(blob: bytes) -> Any:
    return pickle.loads(blob)


__all__ = [
    "CHUNK",
    "Channel",
    "ENV_ADDRESS",
    "ENV_AUTHKEY",
    "ENV_ROLE",
    "ERROR",
    "GENERATE",
    "HELLO",
    "READY",
    "REQUEST_DONE",
    "REQUEST_START",
    "RESET",
    "ROLE_STUDENT",
    "ROLE_TEACHER",
    "SHUTDOWN",
    "TEACH",
    "TEACHER_DONE",
    "connect_from_env",
    "from_shm",
    "to_shm",
    "pack_blob",
    "parse_address",
    "unpack_blob",
]
