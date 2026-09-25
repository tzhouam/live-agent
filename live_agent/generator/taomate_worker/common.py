"""Shared torchrun-side helpers for the TaoMate-H3 teacher and student services."""

from __future__ import annotations

import os
import queue
import threading
import time
from datetime import timedelta
from typing import Any

from . import protocol as P

TP_SIZE = 2


def set_triton_cache(role: str) -> None:
    """Per-role/per-rank Triton cache: a shared cache on the CPFS home directory raced
    across ranks ("OSError: [Errno 116] Stale file handle")."""

    rank = os.environ.get("RANK", "0")
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    os.environ["TRITON_CACHE_DIR"] = os.path.join(repo, ".cache", "triton", f"{role}-rank{rank}")


def rank_info() -> tuple[int, int, int]:
    world = int(os.environ.get("WORLD_SIZE", "1"))
    rank = int(os.environ.get("RANK", "0"))
    local = int(os.environ.get("LOCAL_RANK", str(rank)))
    return rank, world, local


def init_distributed() -> tuple[int, int, Any]:
    import torch

    rank, world, local = rank_info()
    torch.cuda.set_device(local)
    if not torch.distributed.is_initialized():
        torch.distributed.init_process_group(
            backend="nccl", init_method="env://", timeout=timedelta(hours=6)
        )
    return rank, world, torch.device("cuda", local)


def parallel_context(rank: int, world: int) -> Any:
    """TP2 x Ulysses(world/2), same group layout as taomate_h3.teacher._parallel_context."""

    import torch

    from taomate_h3.distributed import ParallelContext

    if world % TP_SIZE:
        raise ValueError("world size must be a multiple of the TP size 2")
    ulysses = world // TP_SIZE
    tp_groups = [
        torch.distributed.new_group(ranks=[u * TP_SIZE + t for t in range(TP_SIZE)], backend="nccl")
        for u in range(ulysses)
    ]
    ulysses_groups = [
        torch.distributed.new_group(ranks=[u * TP_SIZE + t for u in range(ulysses)], backend="nccl")
        for t in range(TP_SIZE)
    ]
    return ParallelContext(
        tp_world_size=TP_SIZE,
        tp_rank=rank % TP_SIZE,
        ulysses_world_size=ulysses,
        ulysses_rank=rank // TP_SIZE,
        tp_group=tp_groups[rank // TP_SIZE],
        ulysses_group=ulysses_groups[rank % TP_SIZE],
    )


def memory_gib() -> dict[str, float]:
    import torch

    return {
        "allocated_gib": torch.cuda.memory_allocated() / 2**30,
        "reserved_gib": torch.cuda.memory_reserved() / 2**30,
        "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
        "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30,
    }


def gather_memory() -> list[dict[str, float]]:
    import torch

    rank, world, _ = rank_info()
    local = {"rank": rank, **memory_gib()}
    gathered: list[Any] = [None] * world
    torch.distributed.all_gather_object(gathered, local)
    return gathered


class Cancelled(Exception):
    """The in-flight request belongs to a session that has been reset."""


class CommandLoop:
    """Rank 0 reads commands from the adapter; every command is broadcast to all ranks.

    A background reader thread (rank 0) drains the socket so that a ``reset`` arriving
    mid-request is seen immediately (``cancel_requested``). A background sender thread
    keeps large chunk messages from stalling the collective schedule.
    """

    def __init__(self, role: str) -> None:
        self.role = role
        self.rank, self.world, _ = rank_info()
        self.channel: P.Channel | None = None
        self.inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self.outbox: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self.latest_session = 0
        self.current_session = 0
        self._threads: list[threading.Thread] = []
        self.group: Any = None  # gloo group for control traffic (see setup_groups)

    def setup_groups(self) -> None:
        """Collective: create a CPU (gloo) group for commands and cancel flags.

        Idle ranks wait for the next command inside ``broadcast_object_list``. On an NCCL
        group that wait is a spinning GPU kernel; with the teacher colocated on the
        student's GPUs this made every student chunk ~2.5x slower (first 4-GPU validation,
        2026-09-26). Waiting on gloo keeps idle ranks off the GPU."""

        import torch

        self.group = torch.distributed.new_group(backend="gloo")

    # ------------------------------------------------------------------ rank 0 I/O
    def connect(self, **hello: Any) -> None:
        if self.rank != 0:
            return
        self.channel = P.connect_from_env(self.role)
        self.channel.send({"type": P.HELLO, "role": self.role, "pid": os.getpid(),
                           "world_size": self.world, "t": time.time(), **hello})
        for target in (self._reader, self._sender):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)

    def _reader(self) -> None:
        assert self.channel is not None
        while True:
            try:
                message = self.channel.recv()
            except (EOFError, OSError):
                self.inbox.put({"type": P.SHUTDOWN, "reason": "adapter connection closed"})
                return
            if message.get("type") == P.RESET:
                self.latest_session = max(self.latest_session, int(message["session"]))
            self.inbox.put(message)

    def _sender(self) -> None:
        assert self.channel is not None
        while True:
            message = self.outbox.get()
            if message is None:
                return
            try:
                if message.get("type") == P.CHUNK:
                    message = P.to_shm(message)
                self.channel.send(message)
            except (EOFError, OSError):
                return

    def send(self, message: dict[str, Any]) -> None:
        """Queue a message to the adapter (rank 0 only; no-op elsewhere)."""

        if self.rank == 0:
            message.setdefault("role", self.role)
            self.outbox.put(message)

    def flush(self, timeout: float = 30.0) -> None:
        if self.rank != 0:
            return
        deadline = time.time() + timeout
        while not self.outbox.empty() and time.time() < deadline:
            time.sleep(0.01)

    # ------------------------------------------------------------------ collectives
    def next_command(self) -> dict[str, Any]:
        import torch

        payload: list[Any] = [None]
        if self.rank == 0:
            while True:
                message = self.inbox.get()
                kind = message.get("type")
                if kind in (P.TEACH, P.GENERATE) and int(message.get("session", 0)) < self.latest_session:
                    continue  # stale command from a session that has been reset
                break
            payload[0] = message
        torch.distributed.broadcast_object_list(payload, src=0, group=self.group)
        message = payload[0]
        if message.get("type") == P.RESET:
            self.current_session = int(message["session"])
        return message

    def cancel_requested(self) -> bool:
        """Collective: True on every rank if rank 0 has seen a newer session."""

        import torch

        flag = torch.zeros(1, dtype=torch.int32, device="cpu" if self.group is not None else "cuda")
        if self.rank == 0 and self.latest_session > self.current_session:
            flag.fill_(1)
        torch.distributed.broadcast(flag, src=0, group=self.group)
        return bool(flag.item())


__all__ = [
    "Cancelled",
    "CommandLoop",
    "TP_SIZE",
    "gather_memory",
    "init_distributed",
    "memory_gib",
    "parallel_context",
    "rank_info",
    "set_triton_cache",
]
