You are GPT-6 Sol, the INDEPENDENT REVIEWER for the "live-agent" project (AGENTS.md rules: read-only; numbered findings tagged blocking/major/minor, each with evidence or the check that would settle it). Review round "taomate_port2": the two-GPU (USP2) real-time optimization of the TaoMate-H3 port in vLLM-Omni (round taomate_port1 reviewed the port itself).

Context. TaoMate-H3 streams five-second T2VA requests as four causal phases; per request the base model ("audio teacher", LoRA disabled) runs nine audio-only forwards over [text | 80 reference audio rows | 396-414 target audio rows | pad]. On two H200-class GPUs (pure Ulysses sequence parallel, TP=1) eager BF16 measured 6.3 s of wall time per 4.958 s request. The optimization added (a) FP8 online linears (upstream vLLM quantization config, not inlined), (b) CUDA-graph replay of the teacher forwards (`cuda_graph.py`, keyed by kwargs structure and a `variant`; static input clones + copy_; sync-debug probe before the first capture; rank agreement by all_reduce MIN; permanent eager fallback on failure; shared memory pool; LRU), with the teacher's timestep vector rewritten as a fixed three-slot tensor and the sequence-parallel embedding replaced by precomputed row selections (`transformer.py` `LocalEmbedPlan`, installed through a contextvar), (c) a 480 px video-VAE decoder tile so two tiles map to the two ranks, (d) a load-time warmup of four requests plus capture of the teacher graphs for a configured range of prompt token counts (`taomate_h3_teacher_graph_text_lengths`), because the graph is keyed by the prompt's token count (the H3 attention uses the valid-row prefix length as a Python int), (e) a fix to the prompt interaction handler (`taomate_h3_prompt.py`): the step runner pads a request's prompt embeddings to the length it recorded in `state.txt_seq_lens` and writes them back into the state, so an updated prompt of another length reached the next request zero-padded or truncated with stale token tags. Measured after (a)-(c): 4.70 s of GPU time and 4.91-4.97 s of wall time per request (real-time factor 0.99-1.00), teacher 0.35 s per request from replays. Real time with ~1% headroom.

Please challenge specifically, quoting file:line of the inlined code:
1. CUDA-graph correctness (`cuda_graph.py`, `audio_teacher.py`, `transformer.py`): is every tensor the captured kernels read either a kwarg (copied on replay) or kept alive (`keep_alive`, the `LocalEmbedPlan` cached per shape and span)? Can two different documents share a key while differing in something the signature does not see (values of `token_tags`, `inverse_indices`, positions, `rope_table`, LoRA on/off, AdaLN cache state)? Is `copy_into` skipping same-`data_ptr` tensors safe? Are the outputs cloned before any other replay can overwrite the shared pool? Warmups on a side stream then capture: any missing stream synchronization? The probe with `set_sync_debug_mode("error")` runs once per process: can a later shape synchronize (e.g. `torch.unique`, `.item()`, boolean-mask indexing) and corrupt a capture silently? Rank agreement: any path where one rank captures and the other raises before `_agree`, or where `_agree` itself runs inside a failed capture?
2. Teacher fixed-slot timesteps (`attach_teacher_timestep_slots`, `teacher_forward_kwargs`) versus the branch's `fill_timesteps`: rows of text, padding, reference audio, target audio; the duplicate slot values at the first step; the AdaLN modality index `inverse_indices * modality_num + token_tags.clamp(min=0)`; the exact-projection cache bypass during capture (is the eager path still using the cache, and does bypassing it change numerics?).
3. `LocalEmbedPlan` versus the upstream `_embed` mask logic: sequence-parallel span from the forward context, the fingerprint check (`plan.fingerprint[3:]` equality, span mismatch -> upstream path), `text_local_indices` when the local span cuts the text, `index_add_` with `[: n]` truncation. The plan cache is keyed by (seq_len, text_len, audio rows, reference rows, span) -- anything else that can differ between two documents with the same key (positions? media time origin? RoPE times) and would make a resident graph replay wrong?
4. Load-time warmup and range capture (`pipeline.py` `ar_diffusion_warmup_requests`, `_warm_teacher_shapes`, `_precapture_teacher_graphs`, `warm_shapes`): are the shapes it captures exactly those the live stream uses (first request 207 audio latents without reference; later 198/198/199 with 80 reference rows; pinned seq_len from `pinned_teacher_seq_len`)? Does warming inside the first denoise step of the warmup session run under the same forward context/span as live teacher runs? Memory and time cost of ~270 resident graphs (static clones + shared pool) and the `max_entries` LRU interaction (eviction order vs. usage).
5. Prompt updates (`taomate_h3_prompt.py`, `pipeline.py` `_prepare_next_chunk`): is recording `txt_seq_lens`/tags at apply time sufficient given the runner's `_prepare_request_prompt_field` (pads to max of recorded lengths, writes back, may truncate)? Any ordering where the write-back happens before `apply_at_chunk_boundary` (update applied mid-request, request boundary later)? Tags: `state.extra["text_tags"]` consumed at request start, fallback to all-ones; is that the release's behaviour for text-encoder tag 0 rows? What happens for a prompt longer than `taomate_h3_pad_text_tokens` (256): unpinned documents, graph miss, warning once?
6. Timing instrumentation: `period`/`prepare` fields, `torch.accelerator.synchronize()` only under `taomate_h3_log_timings`; anything that changes behaviour when logging is off.
7. Real-time claim: with 4.91-4.97 s of wall time per 4.958 s request and a per-update re-encode of 0.13-0.20 s, what buffer/backpressure does the client need, and which of the remaining costs (commit forward 0.82 s/request, VAE decode 0.87 s/request, student forwards 2.7 s/request) is the best next lever without changing the generated content? Comment on the LingBot `reuse_last_step_kv` rejection (last student sigma 0.853).
Be concrete and concise; list checks I can run locally to settle each open question.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/cuda_graph.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""CUDA-graph replay of fixed-shape TaoMate-H3 DiT forwards.

TaoMate's audio teacher runs nine short forwards per five-second request over
a few hundred packed rows. At that size the DiT is launch-bound: the GPU
finishes each block long before the Python launch path of the next one, so
the nine forwards cost about 85 ms each in eager mode although the device
work is a fraction of that. Replaying a captured graph removes the launch
path entirely.

``GraphedForward`` wraps the DiT's keyword-only ``forward``. Calls are keyed
by the *structure* of their kwargs (tensor shapes/dtypes and every non-tensor
value); the first call of a key captures a graph on static copies of the
tensors and later calls copy the live tensors into those buffers and replay.
Values that only change per request (prompt embeddings, RoPE table, row
positions) are therefore ordinary inputs and never force a re-capture; only
a new document *shape* does (a prompt with another token count, the first
request's longer audio, a reference tail present or not).

Graph capture forbids host synchronization inside the captured region, so the
wrapper (a) bypasses the exact AdaLN projection cache during capture (its
key is a host-side digest of the timestep embedding; the graph then contains
the projections themselves, which are cheap for the three teacher timestep
rows), and (b) validates the very first capture with
``torch.cuda.set_sync_debug_mode("error")`` before capturing, so a
synchronizing operator fails loudly on every rank at the same program point
instead of leaving peers waiting in a collective. Any failure disables the
wrapper for the rest of the process (agreed across the sequence-parallel
group when one is given) and the caller falls back to eager execution.
"""

from __future__ import annotations

import dataclasses
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
from vllm.logger import init_logger

logger = init_logger(__name__)

_PRIMITIVES = (int, float, bool, str, bytes, type(None))


def kwargs_signature(value: Any) -> Any:
    """A hashable description of ``value`` in which tensors count by shape and dtype only."""
    if isinstance(value, torch.Tensor):
        return ("tensor", tuple(value.shape), str(value.dtype), value.device.type)
    if isinstance(value, dict):
        return ("dict", tuple((str(key), kwargs_signature(value[key])) for key in sorted(value, key=str)))
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(kwargs_signature(item) for item in value))
    if isinstance(value, _PRIMITIVES):
        return ("value", type(value).__name__, value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (
            type(value).__qualname__,
            tuple((field.name, kwargs_signature(getattr(value, field.name))) for field in dataclasses.fields(value)),
        )
    return ("repr", type(value).__qualname__, repr(value))


def clone_static(value: Any) -> Any:
    """Deep-copy the tensors of a kwargs tree into fresh contiguous buffers."""
    if isinstance(value, torch.Tensor):
        return value.detach().clone(memory_format=torch.contiguous_format)
    if isinstance(value, dict):
        return {key: clone_static(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(clone_static(item) for item in value)
    if isinstance(value, list):
        return [clone_static(item) for item in value]
    return value


def copy_into(static: Any, current: Any) -> int:
    """Copy the tensors of ``current`` into the matching buffers of ``static``.

    Returns the number of tensors copied. The trees must share one signature.
    """
    if isinstance(static, torch.Tensor):
        if not isinstance(current, torch.Tensor) or static.shape != current.shape or static.dtype != current.dtype:
            raise ValueError("graph input differs in shape or dtype from the captured buffer")
        if static.data_ptr() != current.data_ptr():
            static.copy_(current)
        return 1
    if isinstance(static, dict):
        if not isinstance(current, dict) or static.keys() != current.keys():
            raise ValueError("graph input keys differ from the captured kwargs")
        return sum(copy_into(static[key], current[key]) for key in static)
    if isinstance(static, (list, tuple)):
        if not isinstance(current, (list, tuple)) or len(static) != len(current):
            raise ValueError("graph input sequence differs from the captured kwargs")
        return sum(copy_into(s, c) for s, c in zip(static, current, strict=True))
    return 0


@dataclass
class _Entry:
    graph: Any
    static_kwargs: dict[str, Any]
    outputs: Any
    # Objects whose tensors the captured kernels read by address although
    # they are not among the kwargs (for example an embedding plan installed
    # through a context variable). The entry owns a reference so the memory
    # cannot be freed and reused while the graph is resident.
    keep_alive: tuple[Any, ...] = ()
    replays: int = 0


@contextmanager
def _sync_debug_mode(mode: str) -> Iterator[None]:
    previous = torch.cuda.get_sync_debug_mode()
    torch.cuda.set_sync_debug_mode(mode)
    try:
        yield
    finally:
        torch.cuda.set_sync_debug_mode(previous)


@contextmanager
def _adaln_cache_bypassed(module: nn.Module) -> Iterator[None]:
    """Turn the host-keyed AdaLN projection cache off for the duration."""
    cache = getattr(module, "adaln_cache", None)
    if cache is None or not hasattr(cache, "max_bytes"):
        yield
        return
    previous = cache.max_bytes
    cache.max_bytes = 0
    try:
        yield
    finally:
        cache.max_bytes = previous


class GraphedForward:
    """Capture-and-replay wrapper around a keyword-only ``nn.Module`` forward."""

    def __init__(
        self,
        module: nn.Module,
        *,
        device: torch.device,
        max_entries: int = 16,
        warmup_iters: int = 2,
        group: torch.distributed.ProcessGroup | None = None,
        name: str = "taomate_h3",
        enabled: bool = True,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.module = module
        self.device = torch.device(device)
        self.max_entries = int(max_entries)
        self.warmup_iters = int(warmup_iters)
        self.group = group
        self.name = name
        self.enabled = bool(enabled) and self.device.type == "cuda"
        self._entries: OrderedDict[Any, _Entry] = OrderedDict()
        self._pool: Any = None
        self._probe_pending = True
        self.captures = 0
        self.replays = 0
        self.evictions = 0
        self.eager_calls = 0
        self.disabled_reason: str | None = None

    # -- public --------------------------------------------------------------

    def __call__(self, *, variant: Any = None, keep_alive: tuple[Any, ...] = (), **kwargs: Any) -> Any:
        """Run ``module(**kwargs)``, by replay when a graph of this shape exists.

        ``variant`` distinguishes module states the kwargs do not show (for
        example whether the LoRA hooks are enabled, or which embedding plan is
        installed); ``keep_alive`` holds every object outside ``kwargs`` whose
        tensors the forward reads, so a resident graph keeps them allocated.
        Returned tensors are clones, so the caller may hold them across the
        next call.
        """
        if not self.enabled:
            self.eager_calls += 1
            return self.module(**kwargs)
        key = (kwargs_signature(variant), kwargs_signature(kwargs))
        entry = self._entries.get(key)
        if entry is None:
            entry = self._capture(key, kwargs, keep_alive, variant)
            if entry is None:
                self.eager_calls += 1
                return self.module(**kwargs)
        else:
            copy_into(entry.static_kwargs, kwargs)
            self._entries.move_to_end(key)
        entry.graph.replay()
        entry.replays += 1
        self.replays += 1
        return _clone_outputs(entry.outputs)

    @property
    def num_graphs(self) -> int:
        return len(self._entries)

    def stats(self) -> dict[str, int]:
        return {
            "graphs": len(self._entries),
            "captures": self.captures,
            "replays": self.replays,
            "evictions": self.evictions,
            "eager_calls": self.eager_calls,
        }

    def disable(self, reason: str) -> None:
        if self.enabled:
            logger.warning("%s CUDA graphs disabled: %s", self.name, reason)
        self.enabled = False
        self.disabled_reason = reason
        self._entries.clear()

    # -- capture -------------------------------------------------------------

    def _capture(
        self, key: Any, kwargs: dict[str, Any], keep_alive: tuple[Any, ...] = (), variant: Any = None
    ) -> _Entry | None:
        failure: str | None = None
        static: dict[str, Any] = {}
        graph: Any = None
        outputs: Any = None
        try:
            static = clone_static(kwargs)
            with _adaln_cache_bypassed(self.module):
                if self._probe_pending:
                    # A synchronizing operator raises here on every rank at
                    # the same point, before any capture starts.
                    with _sync_debug_mode("error"):
                        self.module(**static)
                    self._probe_pending = False
                side = torch.cuda.Stream(device=self.device)
                side.wait_stream(torch.cuda.current_stream(self.device))
                # The first capture warms lazy kernel/library state for the
                # whole process; later shapes need a single warm forward.
                warmups = self.warmup_iters if self.captures == 0 else min(self.warmup_iters, 1)
                with torch.cuda.stream(side):
                    for _ in range(warmups):
                        self.module(**static)
                torch.cuda.current_stream(self.device).wait_stream(side)
                graph = torch.cuda.CUDAGraph()
                with torch.cuda.graph(graph, pool=self._pool):
                    outputs = self.module(**static)
                if self._pool is None:
                    self._pool = graph.pool()
        except Exception as exc:  # noqa: BLE001 - any capture failure means eager from now on
            failure = f"{type(exc).__name__}: {exc}"
        ok = self._agree(failure is None)
        if not ok:
            del graph, outputs, static
            self.disable(failure or "a peer rank failed to capture")
            return None
        if len(self._entries) >= self.max_entries:
            _, evicted = self._entries.popitem(last=False)
            del evicted
            self.evictions += 1
        entry = _Entry(graph=graph, static_kwargs=static, outputs=outputs, keep_alive=tuple(keep_alive))
        self._entries[key] = entry
        self.captures += 1
        logger.info("%s CUDA graph captured for %s (%d resident)", self.name, variant, len(self._entries))
        return entry

    def _agree(self, ok: bool) -> bool:
        group = self.group
        if group is None or torch.distributed.get_world_size(group) <= 1:
            return ok
        flag = torch.tensor([1 if ok else 0], dtype=torch.int32, device=self.device)
        torch.distributed.all_reduce(flag, op=torch.distributed.ReduceOp.MIN, group=group)
        return bool(int(flag.item()))


def _clone_outputs(outputs: Any) -> Any:
    if isinstance(outputs, torch.Tensor):
        return outputs.clone()
    if isinstance(outputs, tuple):
        return tuple(_clone_outputs(item) for item in outputs)
    if isinstance(outputs, list):
        return [_clone_outputs(item) for item in outputs]
    if isinstance(outputs, dict):
        return {key: _clone_outputs(item) for key, item in outputs.items()}
    return outputs


ForwardFn = Callable[..., Any]

__all__ = ["GraphedForward", "clone_static", "copy_into", "kwargs_signature"]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/transformer.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""MiniMax-H3 DiT with TaoMate streaming attention in the 50 main blocks."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch
from vllm.logger import init_logger

from vllm_omni.diffusion.models.minimax_h3.minimax_h3_transformer import MiniMaxH3DiTModel

from .attention import TaoMateH3StreamingAttention

if TYPE_CHECKING:
    from vllm.model_executor.layers.quantization.base_config import QuantizationConfig

    from vllm_omni.diffusion.data import OmniDiffusionConfig

logger = init_logger(__name__)

_EMBED_PARAMETERS = frozenset(
    {
        "x",
        "audio_x",
        "text_embeddings_selected",
        "unique_timesteps",
        "img_pos",
        "audio_pos",
        "text_pos",
        "refiner_cu_seqlens",
        "refiner_max_seqlen",
        "seq_len",
        "device",
        "local_span",
        "num_requests",
    }
)


@dataclass(frozen=True)
class LocalEmbedPlan:
    """Precomputed row selections of the sequence-parallel embedding step.

    The upstream embedding narrows the packed rows to this rank's slice with
    boolean masks, which is a host synchronization per forward and cannot be
    captured in a CUDA graph. The plan holds the same selections as fixed
    index tensors for one document layout (positions and local span), so a
    forward that runs with the plan installed performs no data-dependent
    indexing. ``fingerprint`` identifies the layout the plan was built for.
    """

    seq_len: int
    local_span: tuple[int, int]
    fingerprint: tuple[int, ...]
    img_global_pos: torch.Tensor
    audio_global_pos: torch.Tensor
    img_local_pos: torch.Tensor
    audio_local_pos: torch.Tensor
    text_local_pos: torch.Tensor
    text_local_indices: torch.Tensor | None

    @staticmethod
    def build(
        *,
        img_pos: torch.Tensor,
        audio_pos: torch.Tensor,
        text_pos: torch.Tensor,
        seq_len: int,
        local_span: tuple[int, int],
        device: torch.device,
    ) -> LocalEmbedPlan:
        """Mirror the upstream mask logic once, on the host, for one layout."""
        img = img_pos.detach().to("cpu", torch.long).view(-1)
        audio = audio_pos.detach().to("cpu", torch.long).view(-1)
        text = text_pos.detach().to("cpu", torch.long).view(-1)
        local_start, local_len = int(local_span[0]), int(local_span[1])
        local_end = local_start + local_len
        fingerprint = (int(seq_len), local_start, local_len, int(img.numel()), int(audio.numel()), int(text.numel()))
        if local_len != int(seq_len):
            img_mask = (img >= local_start) & (img < local_end)
            audio_mask = (audio >= local_start) & (audio < local_end)
            text_mask = (text >= local_start) & (text < local_end)
            img_global = img[img_mask]
            audio_global = audio[audio_mask]
            img_local = img_global - local_start
            audio_local = audio_global - local_start
            text_local = text[text_mask] - local_start
            text_indices: torch.Tensor | None = torch.nonzero(text_mask, as_tuple=False).view(-1)
        else:
            img_global = img_local = img
            audio_global = audio_local = audio
            text_local = text
            text_indices = None
        return LocalEmbedPlan(
            seq_len=int(seq_len),
            local_span=(local_start, local_len),
            fingerprint=fingerprint,
            img_global_pos=img_global.to(device),
            audio_global_pos=audio_global.to(device),
            img_local_pos=img_local.to(device),
            audio_local_pos=audio_local.to(device),
            text_local_pos=text_local.to(device),
            text_local_indices=None if text_indices is None else text_indices.to(device),
        )


_LOCAL_EMBED_PLAN: ContextVar[LocalEmbedPlan | None] = ContextVar("taomate_h3_local_embed_plan", default=None)


@contextmanager
def local_embed_plan(plan: LocalEmbedPlan | None) -> Iterator[None]:
    """Install ``plan`` for the forwards run inside the block."""
    token = _LOCAL_EMBED_PLAN.set(plan)
    try:
        yield
    finally:
        _LOCAL_EMBED_PLAN.reset(token)


class TaoMateH3DiTModel(MiniMaxH3DiTModel):
    """Checkpoint-compatible H3 DiT whose block attention can stream over clean KV.

    The token refiner keeps the upstream attention: TaoMate never caches text
    K/V, and prompt refinement runs on replicated rows before sequence
    parallel sharding.
    """

    def __init__(
        self,
        od_config: OmniDiffusionConfig,
        quant_config: QuantizationConfig | None = None,
        *,
        diffusers_weights: bool | None = None,
    ) -> None:
        super().__init__(
            od_config,
            quant_config,
            diffusers_weights=diffusers_weights,
            attention_cls=TaoMateH3StreamingAttention,
        )
        for index, block in enumerate(self.blocks):
            block.attn.layer_name = f"blocks.{index}.attn"
        # The graph-safe embedding below re-implements the upstream method; if
        # upstream changes its contract the plan path is switched off rather
        # than trusted.
        parameters = set(inspect.signature(MiniMaxH3DiTModel._embed).parameters) - {"self"}
        self.local_embed_plan_supported = parameters == _EMBED_PARAMETERS
        if not self.local_embed_plan_supported:
            logger.warning(
                "TaoMate-H3: MiniMaxH3DiTModel._embed signature changed; graph-safe embedding plans are disabled"
            )

    @property
    def streaming_local_heads(self) -> int:
        """Heads per rank after the Ulysses all-to-all (the persistent KV head count)."""
        return int(self.blocks[0].attn.num_sp_heads)

    def plan_local_embed(
        self,
        *,
        img_pos: torch.Tensor,
        audio_pos: torch.Tensor,
        text_pos: torch.Tensor,
        seq_len: int,
        device: torch.device,
    ) -> LocalEmbedPlan | None:
        """Build the embedding plan of one layout for this rank, or ``None`` if unsupported."""
        if not self.local_embed_plan_supported:
            return None
        return LocalEmbedPlan.build(
            img_pos=img_pos,
            audio_pos=audio_pos,
            text_pos=text_pos,
            seq_len=int(seq_len),
            local_span=self._rope_local_span(int(seq_len)),
            device=device,
        )

    def _embed(  # type: ignore[override]
        self,
        *,
        x: torch.Tensor,
        audio_x: torch.Tensor,
        text_embeddings_selected: torch.Tensor,
        unique_timesteps: torch.Tensor,
        img_pos: torch.Tensor,
        audio_pos: torch.Tensor,
        text_pos: torch.Tensor,
        refiner_cu_seqlens: torch.Tensor,
        refiner_max_seqlen: int,
        seq_len: int,
        device: torch.device,
        local_span: tuple[int, int],
        num_requests: int = 1,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        plan = _LOCAL_EMBED_PLAN.get()
        if plan is None or not self.local_embed_plan_supported:
            return super()._embed(
                x=x,
                audio_x=audio_x,
                text_embeddings_selected=text_embeddings_selected,
                unique_timesteps=unique_timesteps,
                img_pos=img_pos,
                audio_pos=audio_pos,
                text_pos=text_pos,
                refiner_cu_seqlens=refiner_cu_seqlens,
                refiner_max_seqlen=refiner_max_seqlen,
                seq_len=seq_len,
                device=device,
                local_span=local_span,
                num_requests=num_requests,
            )
        local_start, local_len = int(local_span[0]), int(local_span[1])
        expected = (
            int(seq_len),
            local_start,
            local_len,
            int(img_pos.numel()),
            int(audio_pos.numel()),
            int(text_pos.numel()),
        )
        if plan.fingerprint[3:] != expected[3:]:
            raise RuntimeError(
                f"TaoMate-H3 local embedding plan {plan.fingerprint} does not describe this document {expected}"
            )
        if plan.fingerprint[:3] != expected[:3]:
            # The rank's row span is resolved from the forward context; a plan
            # built under another context is not wrong, only unusable here.
            # Take the upstream path (graph capture then fails loudly and the
            # teacher falls back to eager execution).
            if not getattr(self, "_taomate_span_warned", False):
                self._taomate_span_warned = True
                logger.warning(
                    "TaoMate-H3 local embedding plan span %s differs from the forward span %s; using the upstream "
                    "embedding",
                    plan.fingerprint[:3],
                    expected[:3],
                )
            return super()._embed(
                x=x,
                audio_x=audio_x,
                text_embeddings_selected=text_embeddings_selected,
                unique_timesteps=unique_timesteps,
                img_pos=img_pos,
                audio_pos=audio_pos,
                text_pos=text_pos,
                refiner_cu_seqlens=refiner_cu_seqlens,
                refiner_max_seqlen=refiner_max_seqlen,
                seq_len=seq_len,
                device=device,
                local_span=local_span,
                num_requests=num_requests,
            )
        # Same arithmetic as the upstream method, with the plan's fixed
        # selections in place of boolean-mask indexing.
        x_rows = x.view(-1, x.shape[-1]).index_select(0, plan.img_global_pos).to(torch.float32)
        video_embed, _ = self.video_patch_proj(x_rows)
        audio_rows = audio_x.view(-1, audio_x.shape[-1]).index_select(0, plan.audio_global_pos).to(torch.float32)
        audio_embed, _ = self.audio_patch_proj(audio_rows)

        text_rows = text_embeddings_selected.to(device=device, dtype=torch.bfloat16)
        text_embed, _ = self.condition_proj(text_rows)
        text_embed = self.token_refiner(
            text_embed,
            cu_seqlens=refiner_cu_seqlens,
            max_seqlen=refiner_max_seqlen,
            num_requests=num_requests,
        )
        if plan.text_local_indices is not None:
            text_embed = text_embed.index_select(0, plan.text_local_indices)

        embeddings = torch.zeros((local_len, self.hidden_size), device=device, dtype=torch.bfloat16)
        embeddings.index_add_(0, plan.text_local_pos, text_embed.to(torch.bfloat16)[: plan.text_local_pos.shape[0]])
        embeddings.index_add_(0, plan.img_local_pos, video_embed.to(torch.bfloat16)[: plan.img_local_pos.shape[0]])
        embeddings.index_add_(0, plan.audio_local_pos, audio_embed.to(torch.bfloat16)[: plan.audio_local_pos.shape[0]])
        t_emb = self.time_embedder(unique_timesteps)
        return embeddings, t_emb


EntryClass = TaoMateH3DiTModel

__all__ = ["LocalEmbedPlan", "TaoMateH3DiTModel", "local_embed_plan"]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/audio_teacher.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""TaoMate-H3 audio teacher: base-H3 audio guidance for one five-second request.

TaoMate-H3 does not publish the LoRA student's audio. For every request the
*base* MiniMax-H3 model (LoRA disabled) runs an audio-only ten-state schedule
(nine forwards) over ``[text | 1 s clean reference tail | new audio noise]``
and the student's audio rows are overwritten with the teacher's states 3, 6 and
9 after its three denoise steps. The reference tail ("tail-40 rollover") is the
last forty latents per channel of the previous request's clean audio, so
speech continues seamlessly across requests.

The released implementation runs this teacher as a separate BF16 process on
its own GPUs. Here it shares the resident weights with the student: the LoRA
is a switchable hook set, so disabling it for nine forwards yields the base
model exactly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import torch
import torch.nn as nn

from vllm_omni.diffusion.models.minimax_h3.denoise_loop import MiniMaxH3DenoiseBranch

from .cuda_graph import GraphedForward
from .geometry import REQUEST_AUDIO_LATENTS, REQUEST_VIDEO_LATENTS, CanvasGeometry, StreamPlan, request_plan
from .lora import TaoMateLoRAAdapter
from .packed import taomate_audio_only_frozen_prefix_packed_layout, taomate_audio_only_packed_layout
from .schedule import TEACHER_STATE_NUMBERS, euler_eta0_update_, teacher_sigmas
from .transformer import LocalEmbedPlan, local_embed_plan

ROLLOVER_LATENTS_PER_CHANNEL = 40
AUDIO_ROW_WIDTH = 32
VIDEO_ROW_WIDTH = 96


def official_request_noise(
    *,
    seed: int,
    canvas: CanvasGeometry,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Draw the official standalone request noise in the release's generator order.

    Returns ``(video [1, 24, 37, lh, lw], audio rows [2 * 207, 32])`` drawn from one
    CPU generator: video first, then audio. The teacher and the student both use
    the audio draw; the video draw is part of the audio identity even when the
    caller discards it.
    """
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    video = torch.randn(
        1,
        24,
        REQUEST_VIDEO_LATENTS,
        canvas.latent_h,
        canvas.latent_w,
        generator=generator,
        dtype=torch.float32,
        device="cpu",
    )
    audio = torch.randn(
        2 * REQUEST_AUDIO_LATENTS, AUDIO_ROW_WIDTH, generator=generator, dtype=torch.float32, device="cpu"
    )
    return video, audio


@dataclass
class TeacherResult:
    """Milestones of one request: clean audio rows at teacher states 3, 6 and 9."""

    milestones: list[torch.Tensor]
    audio_latent_count: int
    forwards: int

    @property
    def clean(self) -> torch.Tensor:
        return self.milestones[-1]


class TaoMateAudioTeacher:
    """Runs the base-model audio schedule on the shared DiT."""

    def __init__(
        self,
        transformer: nn.Module,
        *,
        lora: TaoMateLoRAAdapter | None,
        device: torch.device,
        graph: GraphedForward | None = None,
    ) -> None:
        self.transformer = transformer
        self.lora = lora
        self.device = device
        # Optional CUDA-graph replay of the nine fixed-shape forwards.
        self.graph = graph
        self.sigmas_video, self.sigmas_audio = teacher_sigmas()
        self.forwards = 0
        # One embedding plan per document shape. A captured graph reads the
        # plan's index tensors by address, so the plan of a shape must stay
        # the same object for as long as the process serves that shape.
        self._embed_plans: dict[tuple[int, ...], LocalEmbedPlan | None] = {}

    def build_branch(
        self,
        *,
        text_embeddings: torch.Tensor,
        text_tags: torch.Tensor,
        canvas: CanvasGeometry,
        audio_latent_count: int,
        previous_audio_latent_count: int | None,
        seq_len: int | None = None,
    ) -> MiniMaxH3DenoiseBranch:
        text_len = int(text_embeddings.shape[0])
        if previous_audio_latent_count is None:
            packed = taomate_audio_only_packed_layout(
                text_len=text_len,
                audio_t=audio_latent_count,
                latent_h=canvas.latent_h,
                latent_w=canvas.latent_w,
                seq_len=seq_len,
            )
        else:
            packed = taomate_audio_only_frozen_prefix_packed_layout(
                text_len=text_len,
                ref_audio_t=ROLLOVER_LATENTS_PER_CHANNEL,
                audio_t=audio_latent_count,
                latent_h=canvas.latent_h,
                latent_w=canvas.latent_w,
                reference_time_start=text_len + previous_audio_latent_count - ROLLOVER_LATENTS_PER_CHANNEL,
                target_time_start=text_len + previous_audio_latent_count,
                seq_len=seq_len,
            )
        tags = packed["token_tags"].clone()
        tags[packed["text_pos"].view(-1)] = text_tags.detach().to("cpu", torch.long)
        branch = MiniMaxH3DenoiseBranch(
            packed=packed,
            text_embeddings=text_embeddings,
            token_tags=tags,
            device=self.device,
        )
        branch.prepare_rope_table(self.transformer)
        attach_teacher_timestep_slots(branch)
        branch.taomate_embed_plan = self._embed_plan_for(branch, text_pos=packed["text_pos"])
        return branch

    def _embed_plan_for(self, branch: MiniMaxH3DenoiseBranch, *, text_pos: torch.Tensor) -> LocalEmbedPlan | None:
        plan_local = getattr(self.transformer, "plan_local_embed", None)
        if not callable(plan_local):
            return None
        # The rank's row span comes from the forward context, so the same
        # document can need different plans inside and outside a runner step.
        span_of = getattr(self.transformer, "_rope_local_span", None)
        span = tuple(span_of(int(branch.seq_len))) if callable(span_of) else (0, int(branch.seq_len))
        shape = (
            int(branch.seq_len),
            int(branch.text_len),
            int(branch.audio_pos.numel()),
            int((~branch.audio_update_mask).sum()),
            *span,
        )
        if shape not in self._embed_plans:
            self._embed_plans[shape] = plan_local(
                img_pos=branch.img_pos,
                audio_pos=branch.audio_pos,
                text_pos=text_pos,
                seq_len=branch.seq_len,
                device=self.device,
            )
        return self._embed_plans[shape]

    # Requests whose teacher documents cover every shape a session visits: the
    # first request (207 audio latents, no reference) and the three-request
    # cycle of later requests (198, 198, 199 latents with a reference tail).
    WARM_REQUEST_INDICES = (0, 1, 2, 3)

    @torch.inference_mode()
    def warm_shapes(
        self,
        *,
        text_embeddings: torch.Tensor,
        text_tags: torch.Tensor,
        canvas: CanvasGeometry,
        seq_len_for: Callable[[bool], int | None],
    ) -> int:
        """Capture the teacher graphs of every document shape a session of this prompt uses.

        One forward per warm request index (a replay when the shape's graph
        already exists) with zero audio rows; the content is irrelevant, only
        the shapes are. Returns the number of graphs captured. Without an
        enabled graph nothing runs.
        """
        graph = self.graph
        if graph is None or not graph.enabled:
            return 0
        captures_before = graph.captures
        video_rows = torch.empty((0, VIDEO_ROW_WIDTH), dtype=torch.float32, device=self.device)
        seen: set[tuple[int, int | None]] = set()
        for index in self.WARM_REQUEST_INDICES:
            plan = request_plan(index)
            previous = None if index == 0 else request_plan(index - 1).audio_latent_count
            key = (plan.audio_latent_count, None if previous is None else ROLLOVER_LATENTS_PER_CHANNEL)
            if key in seen:
                continue
            seen.add(key)
            branch = self.build_branch(
                text_embeddings=text_embeddings,
                text_tags=text_tags,
                canvas=canvas,
                audio_latent_count=plan.audio_latent_count,
                previous_audio_latent_count=previous,
                seq_len=seq_len_for(previous is not None),
            )
            audio_rows = torch.zeros(
                (int(branch.audio_pos.numel()), AUDIO_ROW_WIDTH), dtype=torch.float32, device=self.device
            )
            embed_plan: LocalEmbedPlan | None = getattr(branch, "taomate_embed_plan", None)
            lora_scope = self.lora.disabled() if self.lora is not None else _NullScope()
            with lora_scope, local_embed_plan(embed_plan):
                forward_kwargs = teacher_forward_kwargs(
                    branch, video_rows=video_rows, audio_rows=audio_rows, t_video=0.0, t_audio=0.0
                )
                self._forward(forward_kwargs, plan=embed_plan)
            if not graph.enabled:
                break
        return graph.captures - captures_before

    @torch.inference_mode()
    def run_request(
        self,
        *,
        text_embeddings: torch.Tensor,
        text_tags: torch.Tensor,
        canvas: CanvasGeometry,
        plan: StreamPlan,
        audio_seed: int,
        previous_clean: torch.Tensor | None,
        previous_audio_latent_count: int | None,
        seq_len: int | None = None,
    ) -> TeacherResult:
        """Generate the request's audio milestones with the LoRA disabled."""
        active_audio_latents = plan.audio_latent_count
        transport_prefix = REQUEST_AUDIO_LATENTS - active_audio_latents
        _, official_audio = official_request_noise(seed=audio_seed, canvas=canvas)
        target_noise = (
            official_audio.view(2, REQUEST_AUDIO_LATENTS, AUDIO_ROW_WIDTH)[:, transport_prefix:]
            .contiguous()
            .view(2 * active_audio_latents, AUDIO_ROW_WIDTH)
        )
        if previous_clean is None:
            reference = None
            initial_audio = target_noise
        else:
            if previous_audio_latent_count is None:
                raise ValueError("previous_audio_latent_count is required with previous_clean")
            reference = (
                previous_clean.detach()
                .to(device="cpu", dtype=torch.float32)
                .view(2, int(previous_audio_latent_count), AUDIO_ROW_WIDTH)[:, -ROLLOVER_LATENTS_PER_CHANNEL:]
                .contiguous()
                .view(2 * ROLLOVER_LATENTS_PER_CHANNEL, AUDIO_ROW_WIDTH)
            )
            initial_audio = torch.cat((reference, target_noise), dim=0)
        branch = self.build_branch(
            text_embeddings=text_embeddings,
            text_tags=text_tags,
            canvas=canvas,
            audio_latent_count=active_audio_latents,
            previous_audio_latent_count=None if previous_clean is None else previous_audio_latent_count,
            seq_len=seq_len,
        )
        audio_rows = initial_audio.to(device=self.device, dtype=torch.float32)
        target = branch.audio_update_mask_dev
        ref_rows = int((~branch.audio_update_mask).sum())
        video_rows = torch.empty((0, VIDEO_ROW_WIDTH), dtype=torch.float32, device=self.device)
        captured: dict[int, torch.Tensor] = {}
        steps = len(self.sigmas_video) - 1
        lora_scope = self.lora.disabled() if self.lora is not None else _NullScope()
        plan: LocalEmbedPlan | None = getattr(branch, "taomate_embed_plan", None)
        with lora_scope, local_embed_plan(plan):
            for step in range(steps):
                s_v = self.sigmas_video[step]
                s_a, s_a_next = self.sigmas_audio[step], self.sigmas_audio[step + 1]
                t_v, t_a = 1.0 - s_v, 1.0 - s_a
                forward_kwargs = teacher_forward_kwargs(
                    branch,
                    video_rows=video_rows,
                    audio_rows=audio_rows,
                    t_video=t_v,
                    t_audio=t_a,
                )
                _, velocity_audio = self._forward(forward_kwargs, plan=plan)
                self.forwards += 1
                velocity_target = velocity_audio.float()[target]
                target_rows = audio_rows[ref_rows:]
                euler_eta0_update_(target_rows, velocity_target, sigma_curr=s_a, sigma_next=s_a_next)
                state_number = step + 1
                if state_number in TEACHER_STATE_NUMBERS:
                    captured[state_number] = target_rows.detach().clone()
        milestones = [captured[number] for number in TEACHER_STATE_NUMBERS]
        return TeacherResult(milestones=milestones, audio_latent_count=active_audio_latents, forwards=steps)

    def _forward(self, forward_kwargs: dict, *, plan: LocalEmbedPlan | None) -> tuple[torch.Tensor, torch.Tensor]:
        graph = self.graph
        if graph is None or not graph.enabled:
            return self.transformer(**forward_kwargs)
        # The graph is captured with the LoRA hooks disabled and this
        # document's embedding plan installed; both are part of its identity.
        variant = ("teacher", "lora_off", None if plan is None else plan.fingerprint)
        return graph(variant=variant, keep_alive=() if plan is None else (plan,), **forward_kwargs)


# Timestep slots of a teacher document: every row's AdaLN timestep is one of
# three values, so ``unique_timesteps`` is written as a fixed three-row vector
# and ``inverse_indices`` as a constant slot map. This replaces the per-forward
# ``torch.unique`` (a host synchronization) and keeps the timestep tensors at
# one shape for CUDA-graph replay. Duplicate slot values (both timesteps are 0
# at the first step) are harmless: the DiT gathers per row, uniqueness is not
# required.
TEACHER_SLOT_TEXT = 0  # text and padding rows: the video timestep
TEACHER_SLOT_REFERENCE = 1  # clean reference audio rows: timestep 1
TEACHER_SLOT_TARGET = 2  # denoised audio rows: the audio timestep


def attach_teacher_timestep_slots(branch: MiniMaxH3DenoiseBranch) -> torch.Tensor:
    """Store the branch's constant slot map (``branch.taomate_inverse_indices``)."""
    inverse = torch.full((branch.seq_len,), TEACHER_SLOT_TEXT, dtype=torch.long)
    audio_pos = branch.audio_pos.view(-1).to(torch.long)
    update = branch.audio_update_mask.view(-1).to(torch.bool)
    inverse[audio_pos[~update]] = TEACHER_SLOT_REFERENCE
    inverse[audio_pos[update]] = TEACHER_SLOT_TARGET
    if branch.img_pos.numel():
        raise ValueError("teacher documents carry no video rows")
    branch.taomate_inverse_indices = inverse.to(branch.device)
    return branch.taomate_inverse_indices


def teacher_forward_kwargs(
    branch: MiniMaxH3DenoiseBranch,
    *,
    video_rows: torch.Tensor,
    audio_rows: torch.Tensor,
    t_video: float,
    t_audio: float,
) -> dict:
    """The branch's forward kwargs with fixed-slot timesteps (no host sync)."""
    inverse = getattr(branch, "taomate_inverse_indices", None)
    if inverse is None:
        inverse = attach_teacher_timestep_slots(branch)
    x = branch.x_base.clone()
    if video_rows.shape[0]:
        x[0].index_copy_(0, branch.img_pos_dev, video_rows)
    audio_x = branch.audio_x_base.clone()
    audio_x[0].index_copy_(0, branch.audio_pos_dev, audio_rows)
    unique = torch.tensor([float(t_video), 1.0, float(t_audio)], dtype=torch.float32, device=branch.device)
    return {
        **branch.static_kwargs,
        "x": x,
        "audio_x": audio_x,
        "unique_timesteps": unique,
        "inverse_indices": inverse,
    }


class _NullScope:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


__all__ = [
    "ROLLOVER_LATENTS_PER_CHANNEL",
    "TaoMateAudioTeacher",
    "TeacherResult",
    "attach_teacher_timestep_slots",
    "official_request_noise",
    "teacher_forward_kwargs",
]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/interaction/modality_handlers/taomate_h3_prompt.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""Prompt interaction handler for TaoMate-H3 streaming sessions.

TaoMate-H3 encodes one prompt per five-second request and applies it to the
whole request (the audio teacher and all four phases), so a prompt update is a
hard switch that takes effect at the next request boundary. Prompt lengths
differ between updates, which rules out the generic handler's embedding
interpolation; this subclass forces an immediate transition.

The step runner pads every request's prompt embeddings to the length it
recorded for the request (``txt_seq_lens``) and writes the padded tensor back
into the request state. A new prompt with another token count would therefore
reach the next request zero-padded to the old length (or truncated to it), and
with the old prompt's token tags. The handler keeps the recorded length and
the tags in step with the prompt it applies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import torch
from typing_extensions import override

from vllm_omni.diffusion.interaction.modality_handlers.prompt import (
    PromptInteractionHandler,
    PromptSession,
    QueuedPromptEvent,
)
from vllm_omni.diffusion.interaction.types import InteractionChunkMetadata, InteractionPayload
from vllm_omni.diffusion.worker.utils import StepRequestState


@dataclass(kw_only=True)
class TaoMateQueuedPromptEvent(QueuedPromptEvent):
    """A queued prompt with the text encoder's per-token tags (0/1) of the new prompt."""

    target_text_tags: torch.Tensor | None = None


def sync_prompt_length(state: StepRequestState, *, text_tags: torch.Tensor | None) -> int:
    """Record the current prompt embeddings' row count and tags on the request state.

    Returns the number of text rows. The runner then pads to this length (a
    no-op) instead of the previous prompt's length.
    """
    embeds = state.prompt_embeds
    if embeds is None:
        raise RuntimeError("sync_prompt_length needs prompt embeddings on the request state")
    rows = int(embeds.shape[-2])
    state.prompt_embeds_mask = None
    state.txt_seq_lens = [rows]
    if text_tags is not None and text_tags.ndim == 1 and int(text_tags.shape[0]) == rows:
        state.extra["text_tags"] = text_tags.detach()
    else:
        # The pipeline treats every row as a plain text token when no tags fit.
        state.extra.pop("text_tags", None)
    return rows


class TaoMateH3PromptInteractionHandler(PromptInteractionHandler):
    modality: ClassVar[str] = "prompt"

    @classmethod
    @override
    def from_pipeline(cls, pipeline: Any) -> TaoMateH3PromptInteractionHandler:
        # The H3 DiT keeps mixed parameter dtypes and exposes no ``dtype``; the
        # text encoder returns BF16 hidden states regardless.
        return cls(encode_prompt=pipeline.encode_prompt, device=pipeline.device, dtype=torch.bfloat16)

    @override
    def enqueue(
        self,
        state: StepRequestState,
        *,
        event_id: str,
        received_at: float,
        payload: InteractionPayload,
        transition_chunks: int | None,
    ) -> None:
        """Encode the new prompt now (with its tags); it applies at the next request boundary."""
        del transition_chunks
        self.validate_payload(state, event_id=event_id, payload=payload, transition_chunks=0)
        prompt = payload.get("prompt")
        assert isinstance(prompt, str)
        encoded = self._encode_prompt(
            prompt=prompt,
            negative_prompt=None,
            do_classifier_free_guidance=False,
            num_videos_per_prompt=state.sampling.num_outputs_per_prompt,
            max_sequence_length=state.sampling.max_sequence_length,
            device=self._device,
            dtype=self._dtype,
        )
        target = encoded[0]
        tags = encoded[1] if len(encoded) > 1 and isinstance(encoded[1], torch.Tensor) else None
        session = state.interaction_sessions.setdefault("prompt", PromptSession())
        assert isinstance(session, PromptSession)
        with session.lock:
            # Chunk-level last-write-wins: replace any prior pending event.
            session.pending_event = TaoMateQueuedPromptEvent(
                event_id=event_id,
                received_at=received_at,
                transition_chunks=0,
                prompt=prompt,
                target_prompt_embeds=target,
                target_text_tags=tags,
            )

    @override
    def apply_at_chunk_boundary(
        self,
        state: StepRequestState,
        *,
        boundary_at: float,
        **kwargs: Any,
    ) -> InteractionChunkMetadata | None:
        metadata = super().apply_at_chunk_boundary(state, boundary_at=boundary_at, **kwargs)
        session = state.interaction_sessions.get("prompt")
        active = getattr(session, "active_event", None)
        embeds = state.prompt_embeds
        if (
            isinstance(active, TaoMateQueuedPromptEvent)
            and embeds is not None
            and embeds is active.target_prompt_embeds
        ):
            # The sharp transition just installed this event's embeddings.
            sync_prompt_length(state, text_tags=active.target_text_tags)
        return metadata


__all__ = ["TaoMateH3PromptInteractionHandler", "TaoMateQueuedPromptEvent", "sync_prompt_length"]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/pipeline.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""TaoMate-H3: realtime streaming MiniMax-H3 with the TaoMate LoRA.

TaoMate-H3 (``TaoLiveAIGC/TaoMate-H3``) is a rank-128 LoRA over MiniMax-H3 that
turns the bidirectional five-second T2VA model into a causal streamer: each
request is generated as four phases of 34/34/34/17 frames, every phase runs
three denoise steps conditioned on the clean (sigma = 0) keys and values of
earlier phases, and the base model provides the audio. This pipeline hosts that
contract on vLLM-Omni's AR-Diffusion runtime (LingBot-World's realtime path):

* one AR chunk = one TaoMate phase (``chunk_num_steps = 3``) with the clean-KV
  commit and the incremental VAE decode in ``post_decode``;
* the persistent clean audio/video KV is model-owned (``CleanAVKVCache``) and
  read by ``TaoMateH3StreamingAttention`` after the Ulysses all-to-all;
* the prompt of the *next* request may change at any chunk boundary through
  the streaming ``session.interaction`` API (TaoMate's just-in-time lock);
* the LoRA stays unmerged so the resident BF16 weights also serve the LoRA-free
  audio teacher.

The pipeline reuses the upstream MiniMax-H3 pipeline for component loading
(DiT, Qwen3-VL text encoder with tensor parallel, VAEs) and only differs in
the DiT attention class and the execution contract. Serving topology: pure
Ulysses sequence parallelism (``tensor_parallel_size == 1``).
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, ClassVar, cast

import numpy as np
import torch
from vllm.logger import init_logger

from vllm_omni.diffusion.data import DiffusionOutput, OmniDiffusionConfig
from vllm_omni.diffusion.interaction.mixin import InteractionMixin
from vllm_omni.diffusion.interaction.types import ChunkMediaSpec
from vllm_omni.diffusion.models.interface import SupportsStepExecution
from vllm_omni.diffusion.models.minimax_h3.denoise_loop import MiniMaxH3DenoiseBranch
from vllm_omni.diffusion.models.minimax_h3.packed_tokens import (
    minimax_h3_patchify_video_latent,
    minimax_h3_unpack_audio_tokens,
    minimax_h3_unpatchify_video_tokens,
)
from vllm_omni.diffusion.models.minimax_h3.pipeline_minimax_h3 import MiniMaxH3Pipeline
from vllm_omni.diffusion.request import OmniDiffusionRequest
from vllm_omni.diffusion.worker.input_batch import InputBatch
from vllm_omni.diffusion.worker.request_batch import DiffusionRequestBatch
from vllm_omni.diffusion.worker.utils import StepRequestState
from vllm_omni.errors import OmniClientError
from vllm_omni.experimental.ar_diffusion.capability import ARDiffusionKVBranchSpec, ARDiffusionKVCacheSpec
from vllm_omni.experimental.ar_diffusion.kv_cache.state import ARDiffusionKVState
from vllm_omni.experimental.ar_diffusion.tick_protocol import ARDiffusionChunkMetadata
from vllm_omni.inputs.data import OmniDiffusionSamplingParams
from vllm_omni.model_executor.models.minimax_h3.conditioning import MiniMaxH3EncoderMediaInput
from vllm_omni.model_executor.models.minimax_h3.encoder_processing import PreparedEncoderInputs

from .attention import StreamContext, StreamMode, _ulysses_state, stream_context
from .audio_teacher import (
    ROLLOVER_LATENTS_PER_CHANNEL,
    TaoMateAudioTeacher,
    TeacherResult,
    official_request_noise,
)
from .cuda_graph import GraphedForward
from .geometry import (
    AUDIO_SAMPLE_RATE,
    PHASE_GROUP_COUNTS,
    REQUEST_AUDIO_LATENTS,
    REQUEST_NATIVE_FRAMES,
    REQUEST_VIDEO_LATENTS,
    STEADY_NATIVE_FRAMES,
    VIDEO_FPS,
    CanvasGeometry,
    StreamPhase,
    StreamPlan,
    phases_for_frames,
    request_plan,
)
from .kv_cache import CleanAVKVCache, KVContract
from .lora import TaoMateLoRAAdapter, is_taomate_lora_dir
from .packed import taomate_phase_packed_layout
from .schedule import euler_eta0_update_, student_sigmas
from .stream_decode import StreamingAudioDecoder, StreamingVideoDecoder, samples_at_frame
from .transformer import TaoMateH3DiTModel

logger = init_logger(__name__)

NUM_PHASES = len(PHASE_GROUP_COUNTS)
# Largest per-phase audio latent count over the first and the steady-state
# request geometries (audio boundaries are rounded on the global timeline).
_MAX_PHASE_AUDIO_LATENTS = tuple(
    max(request_plan(index).phases[phase].audio_latent_count for index in range(0, 8)) for phase in range(NUM_PHASES)
)
STUDENT_STEPS = 3
DEFAULT_SEED = 8301
DEFAULT_HEIGHT = 864
DEFAULT_WIDTH = 480
DEFAULT_AUDIO_KV_RESET_REQUESTS = 12
# Ten minutes of 24 fps video when a session does not name a frame budget: the
# WebSocket client ends the session by disconnecting.
DEFAULT_SESSION_FRAMES = 10 * 60 * VIDEO_FPS
_VIDEO_NOISE_REQUEST_STRIDE = 1_000_003
_VIDEO_ROW_WIDTH = 96
_AUDIO_ROW_WIDTH = 32
_AR_BRANCH = "main"


def _prompt_version(state: StepRequestState) -> int:
    """Count of prompt updates applied to this stream (bumped by the prompt interaction handler)."""
    session = state.interaction_sessions.get("prompt")
    return int(getattr(session, "version", 0) or 0)


def _validate_parallel_config(od_config: OmniDiffusionConfig) -> None:
    parallel = od_config.parallel_config
    tp = int(getattr(parallel, "tensor_parallel_size", 1) or 1)
    if tp != 1:
        raise ValueError(
            "TaoMate-H3 runs with pure Ulysses sequence parallelism; set tensor_parallel_size=1 "
            f"(got {tp}). The native LoRA is replicated per rank and the clean KV is sharded by heads."
        )
    ulysses = int(getattr(parallel, "ulysses_degree", 1) or 1)
    sp = int(getattr(parallel, "sequence_parallel_size", 1) or 1)
    ring = int(getattr(parallel, "ring_degree", 1) or 1)
    allgather = int(getattr(parallel, "allgather_degree", 1) or 1)
    if ring != 1 or allgather != 1 or sp != ulysses:
        raise ValueError(
            "TaoMate-H3 requires sequence_parallel_size == ulysses_degree with ring_degree=1 and "
            f"allgather_degree=1 (got sp={sp}, ulysses={ulysses}, ring={ring}, allgather={allgather})."
        )
    if str(getattr(parallel, "ulysses_mode", "strict") or "strict") != "strict":
        raise ValueError("TaoMate-H3 supports ulysses_mode='strict' only.")
    if bool(getattr(parallel, "ulysses_a2a_permute", False)):
        raise ValueError("TaoMate-H3 does not support ulysses_a2a_permute.")
    if int(getattr(parallel, "cfg_parallel_size", 1) or 1) != 1:
        raise ValueError("TaoMate-H3 is CFG-distilled; cfg_parallel_size must be 1.")
    if int(getattr(parallel, "pipeline_parallel_size", 1) or 1) != 1:
        raise ValueError("TaoMate-H3 does not support pipeline parallelism.")


@dataclass
class _RequestState:
    """One five-second request of a session."""

    index: int
    plan: StreamPlan
    text_embeddings: torch.Tensor
    text_tags: torch.Tensor
    video_rows: torch.Tensor  # initial noise rows of the request's active video latents
    audio_rows: torch.Tensor  # initial noise rows [2 * active_audio, 32]
    audio_seed: int
    video_seed: int
    frame_rows: int
    teacher: TeacherResult | None = None
    teacher_seconds: float = 0.0

    @property
    def text_len(self) -> int:
        return int(self.text_embeddings.shape[0])

    def phase_video_rows(self, phase: StreamPhase) -> torch.Tensor:
        start = phase.video_latent_start * self.frame_rows
        stop = phase.video_latent_stop * self.frame_rows
        return self.video_rows[start:stop].clone()

    def phase_audio_rows(self, phase: StreamPhase, rows: torch.Tensor | None = None) -> torch.Tensor:
        source = self.audio_rows if rows is None else rows
        total = self.plan.audio_latent_count
        return (
            source.view(2, total, _AUDIO_ROW_WIDTH)[:, phase.audio_latent_start : phase.audio_latent_stop]
            .reshape(-1, _AUDIO_ROW_WIDTH)
            .clone()
        )


@dataclass
class _PhaseState:
    phase: StreamPhase
    branch: MiniMaxH3DenoiseBranch
    condition_rows: torch.Tensor
    media_rows: torch.Tensor
    token_tags: torch.Tensor
    commit_mask: torch.Tensor
    seq_len: int
    started_at: float = field(default_factory=time.perf_counter)
    timings: dict[str, float] = field(default_factory=dict)


class _Session:
    """Model-owned state of one streaming session (one WebSocket request)."""

    def __init__(
        self,
        *,
        session_id: str,
        canvas: CanvasGeometry,
        seed: int,
        contract: KVContract,
        video_decoder: StreamingVideoDecoder,
        audio_decoder: StreamingAudioDecoder,
        audio_kv_reset_requests: int,
        pad_text_tokens: int = 0,
    ) -> None:
        self.session_id = session_id
        self.canvas = canvas
        self.pad_text_tokens = int(pad_text_tokens)
        self.seed = int(seed)
        self.cache = CleanAVKVCache(contract)
        self.video_decoder = video_decoder
        self.audio_decoder = audio_decoder
        self.audio_kv_reset_requests = int(audio_kv_reset_requests)
        self.media_time_origin: int | None = None
        self.request_index = 0
        self.video_latent_offset = 0
        self.audio_latent_offset = 0
        self.frames_published = 0
        self.renorm_anchor: tuple[torch.Tensor, torch.Tensor] | None = None
        self.teacher_previous_clean: torch.Tensor | None = None
        self.teacher_previous_count: int | None = None
        self.request: _RequestState | None = None
        self.phase: _PhaseState | None = None
        self.sigmas_video, self.sigmas_audio = student_sigmas()
        self.stats: dict[str, float] = {"teacher_seconds": 0.0, "student_forwards": 0, "clean_forwards": 0}
        # Timing bookkeeping (taomate_h3_log_timings): the last phase
        # preparation and the wall-clock end of the last logged phase.
        self.prepare_seconds = 0.0
        self.last_phase_end: float | None = None
        # Teacher graphs of this session's prompt length captured (first step).
        self.teacher_shapes_warm = False

    # -- request lifecycle -------------------------------------------------

    def begin_request(
        self,
        *,
        text_embeddings: torch.Tensor,
        text_tags: torch.Tensor,
        device: torch.device,
    ) -> _RequestState:
        index = self.request_index
        plan = request_plan(index)
        transport_video = REQUEST_VIDEO_LATENTS - plan.video_latent_count
        transport_audio = REQUEST_AUDIO_LATENTS - plan.audio_latent_count
        audio_seed = self.seed + index
        video_seed = (self.seed + index * _VIDEO_NOISE_REQUEST_STRIDE) % (2**63)
        _, official_audio = official_request_noise(seed=audio_seed, canvas=self.canvas)
        audio_rows = (
            official_audio.view(2, REQUEST_AUDIO_LATENTS, _AUDIO_ROW_WIDTH)[:, transport_audio:]
            .contiguous()
            .view(2 * plan.audio_latent_count, _AUDIO_ROW_WIDTH)
        )
        video_noise, _ = official_request_noise(seed=video_seed, canvas=self.canvas)
        frame_rows = self.canvas.frame_rows
        video_rows = minimax_h3_patchify_video_latent(video_noise, patch_size=(1, 2, 2))[transport_video * frame_rows :]
        text_len = int(text_embeddings.shape[0])
        if self.media_time_origin is None:
            self.media_time_origin = text_len
        if index > 0 and self.audio_kv_reset_requests > 0 and index % self.audio_kv_reset_requests == 0:
            dropped = self.cache.drop_audio_history()
            logger.info(
                "TaoMate-H3 session %s: dropped %d audio KV rows at request %d", self.session_id, dropped, index
            )
        self.request = _RequestState(
            index=index,
            plan=plan,
            text_embeddings=text_embeddings.detach(),
            text_tags=text_tags.detach(),
            video_rows=video_rows.to(device=device, dtype=torch.float32),
            audio_rows=audio_rows.to(device=device, dtype=torch.float32),
            audio_seed=audio_seed,
            video_seed=video_seed,
            frame_rows=frame_rows,
        )
        return self.request

    def finish_request(self) -> None:
        request = self.request
        assert request is not None
        self.video_latent_offset += request.plan.video_latent_count
        self.audio_latent_offset += request.plan.audio_latent_count
        self.request_index += 1
        self.request = None
        self.phase = None

    # -- pinned shapes ---------------------------------------------------------

    def pinned_phase_seq_len(self, phase: StreamPhase, text_len: int) -> int | None:
        """Fixed packed length for this phase kind, or ``None`` when unpinned."""
        if self.pad_text_tokens <= 0:
            return None
        if text_len > self.pad_text_tokens:
            logger.warning_once(
                "TaoMate-H3 prompt has %d tokens, above taomate_h3_pad_text_tokens=%d; this phase runs unpinned",
                text_len,
                self.pad_text_tokens,
            )
            return None
        audio_rows = 2 * _MAX_PHASE_AUDIO_LATENTS[phase.index]
        used = self.pad_text_tokens + audio_rows + phase.video_latent_count * self.canvas.frame_rows
        return -(-used // 64) * 64

    def pinned_teacher_seq_len(self, text_len: int, *, with_reference: bool) -> int | None:
        if self.pad_text_tokens <= 0 or text_len > self.pad_text_tokens:
            return None
        rows = 2 * (REQUEST_AUDIO_LATENTS + (ROLLOVER_LATENTS_PER_CHANNEL if with_reference else 0))
        return -(-(self.pad_text_tokens + rows) // 64) * 64

    # -- phases ------------------------------------------------------------

    def begin_phase(self, phase_index: int, *, transformer: TaoMateH3DiTModel, device: torch.device) -> _PhaseState:
        request = self.request
        assert request is not None and self.media_time_origin is not None
        phase = request.plan.phases[phase_index]
        packed = taomate_phase_packed_layout(
            text_len=request.text_len,
            phase=phase,
            latent_h=self.canvas.latent_h,
            latent_w=self.canvas.latent_w,
            media_time_origin=self.media_time_origin,
            video_latent_offset=self.video_latent_offset,
            audio_latent_offset=self.audio_latent_offset,
            seq_len=self.pinned_phase_seq_len(phase, request.text_len),
        )
        tags = packed["token_tags"].clone()
        tags[packed["text_pos"].view(-1)] = request.text_tags.detach().to("cpu", torch.long)
        branch = MiniMaxH3DenoiseBranch(
            packed=packed,
            text_embeddings=request.text_embeddings,
            token_tags=tags,
            device=device,
        )
        # The rank-local RoPE table is built lazily inside the first forward:
        # the sequence-parallel span is only known under the runner's forward
        # context, and ``prepare_next_chunk`` runs outside it.
        seq_len = int(packed["seq_len"])
        condition_rows = packed["text_pos"].view(-1).to(device=device, dtype=torch.long)
        media_rows = torch.cat((packed["audio_pos"].view(-1), packed["img_pos"].view(-1))).sort().values
        media_rows = media_rows.to(device=device, dtype=torch.long)
        commit_mask = torch.zeros(seq_len, dtype=torch.bool)
        commit_mask[media_rows.cpu()] = True
        self.phase = _PhaseState(
            phase=phase,
            branch=branch,
            condition_rows=condition_rows,
            media_rows=media_rows,
            token_tags=tags.to(device=device, dtype=torch.long),
            commit_mask=commit_mask.to(device=device),
            seq_len=seq_len,
        )
        return self.phase

    def stream_context(self, mode: StreamMode) -> StreamContext:
        phase = self.phase
        assert phase is not None
        return StreamContext(
            cache=self.cache,
            mode=mode,
            condition_rows=phase.condition_rows,
            media_rows=phase.media_rows,
            token_tags=phase.token_tags,
            commit_mask=phase.commit_mask,
            seq_len=phase.seq_len,
        )

    def renorm_clean_video_rows(self, rows: torch.Tensor) -> torch.Tensor:
        """Match generated phases to the first phase's per-feature statistics."""
        current = rows.detach().float()
        mean = current.mean(dim=0, keepdim=True)
        std = current.std(dim=0, keepdim=True, unbiased=False).clamp_min(1e-6)
        if self.renorm_anchor is None:
            self.renorm_anchor = (mean, std)
            return rows
        anchor_mean, anchor_std = self.renorm_anchor
        return (current - mean).div(std).mul(anchor_std).add(anchor_mean).to(dtype=rows.dtype)

    def close(self) -> None:
        self.cache.clear()
        self.video_decoder.reset()
        self.audio_decoder.reset()
        self.request = None
        self.phase = None
        self.renorm_anchor = None
        self.teacher_previous_clean = None
        self.teacher_previous_count = None


def parse_text_length_range(value: Any, name: str = "taomate_h3_teacher_graph_text_lengths") -> range | None:
    """Parse ``"lo-hi"`` (or ``[lo, hi]``) into an inclusive range of prompt token counts, or ``None``."""
    if value is None or value == "" or value is False:
        return None
    if isinstance(value, str):
        parts = value.replace(":", "-").split("-")
        if len(parts) != 2:
            raise ValueError(f"{name} must look like 'lo-hi', got {value!r}")
        lo, hi = (int(part.strip()) for part in parts)
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        lo, hi = int(value[0]), int(value[1])
    elif isinstance(value, int) and not isinstance(value, bool):
        lo = hi = int(value)
    else:
        raise ValueError(f"{name} must be 'lo-hi', [lo, hi] or a single token count, got {value!r}")
    if lo < 1 or hi < lo:
        raise ValueError(f"{name} needs 1 <= lo <= hi, got {lo}-{hi}")
    return range(lo, hi + 1)


def validate_vae_tile_value(value: Any, name: str, *, minimum: int) -> int | None:
    """A video VAE tile size or overlap: ``None`` or a multiple of 16 pixels >= ``minimum``."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer number of pixels")
    if value < minimum or value % 16:
        raise ValueError(f"{name} must be a multiple of 16 and at least {minimum}, got {value}")
    return int(value)


class TaoMateH3Pipeline(MiniMaxH3Pipeline, SupportsStepExecution, InteractionMixin):
    """Streaming TaoMate-H3 on the AR-Diffusion runtime."""

    supports_step_execution: ClassVar[bool] = True
    # The three student steps of a phase run back to back; the scheduler regains
    # control at the phase boundary, where prompt interactions are applied.
    supports_chunk_step_grouping: ClassVar[bool] = True
    # Generic warmup cannot synthesize a session; the AR runner's rollout
    # warmup (one throwaway request) replaces it, in eager mode too: a cold
    # server otherwise spends 17-20 s on its first chunk, 3 s when warm.
    dummy_run_num_frames: ClassVar[int] = 0
    ar_diffusion_warmup_eager: ClassVar[bool] = True
    _transformer_cls: ClassVar[type] = TaoMateH3DiTModel

    def __init__(self, *, od_config: OmniDiffusionConfig, prefix: str = "") -> None:
        _validate_parallel_config(od_config)
        if bool(getattr(od_config, "step_execution", False)) is False:
            logger.warning(
                "TaoMate-H3 is a streaming model; serve it with step_execution=true and streaming_output=true "
                "on the AR-Diffusion engine (see vllm_omni/deploy/taomate_h3_usp4_realtime.yaml)."
            )
        super().__init__(od_config=od_config, prefix=prefix)
        model_config = dict(getattr(od_config, "model_config", None) or {})
        self._tm_default_height = int(model_config.get("taomate_h3_height", DEFAULT_HEIGHT))
        self._tm_default_width = int(model_config.get("taomate_h3_width", DEFAULT_WIDTH))
        self._tm_default_canvas = CanvasGeometry(height=self._tm_default_height, width=self._tm_default_width)
        self._tm_default_seed = int(model_config.get("taomate_h3_seed", DEFAULT_SEED))
        self._tm_audio_kv_reset_requests = int(
            model_config.get("taomate_h3_audio_kv_reset_requests", DEFAULT_AUDIO_KV_RESET_REQUESTS)
        )
        self._tm_allow_no_lora = bool(model_config.get("taomate_h3_allow_no_lora", False))
        # Optional fixed packed lengths: with a prompt budget every phase kind
        # and the teacher documents keep one shape across prompts, which is
        # what compiled blocks and CUDA graphs need to stay warm.
        pad_text = model_config.get("taomate_h3_pad_text_tokens")
        self._tm_pad_text_tokens = int(pad_text) if pad_text else 0
        # Per-phase stage timings in the log (adds device synchronizations).
        self._tm_log_timings = bool(model_config.get("taomate_h3_log_timings", False))
        # Opt-in CUDA-graph replay of the audio teacher's nine launch-bound
        # forwards (one graph per document shape; see cuda_graph.py).
        self._tm_teacher_cuda_graph = bool(model_config.get("taomate_h3_teacher_cuda_graph", False))
        self._tm_cuda_graph_max_entries = int(model_config.get("taomate_h3_cuda_graph_max_entries", 16))
        if self._tm_cuda_graph_max_entries < 1:
            raise ValueError("taomate_h3_cuda_graph_max_entries must be at least 1")
        # Requests of the load-time warmup session. Later requests cycle
        # through three audio latent counts (198, 198, 199 per channel), so
        # four requests visit every teacher document shape once: the graphs
        # are captured and the allocator has seen every phase size before the
        # first client connects.
        self._tm_warmup_requests = int(model_config.get("taomate_h3_warmup_requests", 4))
        if self._tm_warmup_requests < 1:
            raise ValueError("taomate_h3_warmup_requests must be at least 1")
        # Prompt token counts whose teacher graphs are captured during the
        # load-time warmup (three document shapes per count). A teacher graph
        # is keyed by the prompt's token count, so without this every new
        # prompt length costs one capture per shape inside the live stream.
        self._tm_teacher_graph_text_lengths = parse_text_length_range(
            model_config.get("taomate_h3_teacher_graph_text_lengths")
        )
        if self._tm_teacher_graph_text_lengths is not None:
            needed = 3 * len(self._tm_teacher_graph_text_lengths)
            if self._tm_pad_text_tokens <= 0:
                raise ValueError("taomate_h3_teacher_graph_text_lengths needs taomate_h3_pad_text_tokens")
            if self._tm_teacher_graph_text_lengths[-1] > self._tm_pad_text_tokens:
                raise ValueError("taomate_h3_teacher_graph_text_lengths must stay within taomate_h3_pad_text_tokens")
            if needed > self._tm_cuda_graph_max_entries:
                raise ValueError(
                    f"taomate_h3_teacher_graph_text_lengths needs {needed} resident graphs; raise "
                    f"taomate_h3_cuda_graph_max_entries (now {self._tm_cuda_graph_max_entries})"
                )
        # Opt-in just-in-time prompt lock for clients that choose each request's
        # prompt at the last moment: request k >= 1 starts only after a prompt
        # update was applied since request k-1 started. Until then the session
        # idles at the request boundary (one short no-op step per poll), so the
        # stream cannot run ahead of the client and start a request on a stale
        # prompt. Off by default: the free-running stream keeps the last prompt.
        self._tm_hold_for_prompt = bool(model_config.get("taomate_h3_hold_for_prompt", False))
        self._tm_hold_poll_seconds = float(model_config.get("taomate_h3_hold_poll_seconds", 0.02))
        # Optional decoder tile size of the video VAE. The checkpoint tiles the
        # decode in 256 px tiles with at least 64 px overlap: at 480x864 that is
        # a 3x5 grid whose tiles cover 2.4x the canvas. A tile of 480 px gives
        # one 480x480 tile per column pair (2 tiles, 1.1x the canvas), which is
        # one tile per rank at USP2.
        self._tm_vae_decoder_tile_size = validate_vae_tile_value(
            model_config.get("taomate_h3_vae_decoder_tile_size"), "taomate_h3_vae_decoder_tile_size", minimum=16
        )
        self._tm_vae_decoder_tile_overlap_min = validate_vae_tile_value(
            model_config.get("taomate_h3_vae_decoder_tile_overlap_min"),
            "taomate_h3_vae_decoder_tile_overlap_min",
            minimum=0,
        )
        # The executor returns the output of DiT rank 0; the other ranks take
        # part in the collectives but do not convert or decode media.
        self._tm_output_rank = int(self._dit_rank) == 0
        self.taomate_lora: TaoMateLoRAAdapter | None = None
        self._tm_teacher: TaoMateAudioTeacher | None = None
        self._tm_teacher_graph: GraphedForward | None = None
        self._tm_sessions: dict[str, _Session] = {}
        self._tm_warmup_session_ids: set[str] = set()
        self._ar_diffusion_kv_state: ARDiffusionKVState | None = None
        if getattr(self, "transformers_ref", None) is not None:
            raise ValueError("TaoMate-H3 serves the FL2VA partition only; do not load the Ref2VA DiT")
        if not self.load_text_encoder:
            raise ValueError("TaoMate-H3 encodes each request prompt locally; keep text_encoder loaded")
        self._apply_vae_decoder_tiling()

    def _apply_vae_decoder_tiling(self) -> None:
        vae = getattr(self, "video_vae", None)
        model = getattr(vae, "model", None)
        if model is None:
            return
        if self._tm_vae_decoder_tile_size is not None:
            model.decoder_tile_size = self._tm_vae_decoder_tile_size
        if self._tm_vae_decoder_tile_overlap_min is not None:
            model.decoder_tile_overlap_min = self._tm_vae_decoder_tile_overlap_min
        count = getattr(vae, "_decoder_tile_count", None)
        if not callable(count):
            return
        canvas = self._tm_default_canvas
        try:
            tiles = int(count(torch.zeros(1, 1, 1, canvas.latent_h, canvas.latent_w)))
        except Exception as exc:  # noqa: BLE001 - diagnostics only
            logger.warning("TaoMate-H3: could not resolve the video VAE decoder tile grid: %s", exc)
            return
        parallel = int(getattr(vae, "parallel_size", 1))
        logger.info(
            "TaoMate-H3 video VAE decoder: tile %s px, overlap >= %s px, %d tile(s) at %dx%d, %d tile rank(s)",
            getattr(model, "decoder_tile_size", "?"),
            getattr(model, "decoder_tile_overlap_min", "?"),
            tiles,
            canvas.height,
            canvas.width,
            parallel,
        )
        if parallel > 1 and tiles < parallel:
            logger.warning(
                "TaoMate-H3: %d decoder tile(s) for %d tile-parallel ranks; the VAE falls back to its slower "
                "single-group decode. Lower taomate_h3_vae_decoder_tile_size.",
                tiles,
                parallel,
            )

    # -- weights ----------------------------------------------------------

    def load_weights(self, weights):  # type: ignore[override]
        loaded = super().load_weights(weights)
        lora_path = getattr(self.od_config, "lora_path", None)
        if isinstance(lora_path, (list, tuple)):
            lora_path = lora_path[0] if len(lora_path) == 1 else None
        if lora_path and is_taomate_lora_dir(lora_path):
            self.taomate_lora = TaoMateLoRAAdapter.load(
                lora_path,
                transformer=self.transformer,
                device=self.device,
                dtype=torch.bfloat16,
            )
        elif lora_path:
            raise ValueError(
                f"--lora-path {lora_path!r} is not a TaoMate-H3 native adapter directory "
                "(expected adapter_model.safetensors with <target>.lora_a/lora_b keys and config.json)"
            )
        elif not self._tm_allow_no_lora:
            raise ValueError(
                "TaoMate-H3 requires --lora-path pointing at the TaoLiveAIGC/TaoMate-H3 adapter; "
                "set model_config.taomate_h3_allow_no_lora=true to stream the base H3 without it"
            )
        graph: GraphedForward | None = None
        if self._tm_teacher_cuda_graph:
            _, _, group = _ulysses_state()
            graph = GraphedForward(
                self.transformer,
                device=self.device,
                max_entries=self._tm_cuda_graph_max_entries,
                group=group,
                name="TaoMate-H3 teacher",
            )
            if not graph.enabled:
                logger.warning("TaoMate-H3 teacher CUDA graphs requested but the device is not CUDA; running eager")
        self._tm_teacher_graph = graph
        self._tm_teacher = TaoMateAudioTeacher(
            self.transformer, lora=self.taomate_lora, device=self.device, graph=graph
        )
        return loaded

    @property
    def lora_is_fused(self) -> bool:
        # The adapter is applied by this pipeline; keep the dynamic LoRA manager away.
        return True

    # -- prompts ----------------------------------------------------------

    def _prepared_text_inputs(self, prompt: str, *, canvas: CanvasGeometry) -> PreparedEncoderInputs:
        if not isinstance(prompt, str) or not prompt.strip():
            raise OmniClientError("TaoMate-H3 requires a non-empty text prompt")
        media = MiniMaxH3EncoderMediaInput(
            task="t2va",
            height=canvas.height,
            width=canvas.width,
            num_frames=int(REQUEST_VIDEO_LATENTS),
            latent_t=REQUEST_VIDEO_LATENTS,
            audio_t=REQUEST_AUDIO_LATENTS,
        )
        return PreparedEncoderInputs(
            prompt=prompt,
            media=media,
            images=[],
            qwen_videos=[],
            video_timestamps=[],
            condition_labels=[],
        )

    def encode_prompt(  # type: ignore[override]
        self,
        prepared: PreparedEncoderInputs | None = None,
        *,
        prompt: str | None = None,
        **kwargs: Any,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode one prompt to ``(hidden [L, 5120] bf16, tags [L])`` on every DiT rank.

        Also the entry point of the streaming prompt interaction handler, which
        calls it with ``prompt=`` and the generic keyword arguments.
        """
        del kwargs
        if prepared is None:
            if prompt is None:
                raise ValueError("encode_prompt needs prepared inputs or a prompt string")
            prepared = self._prepared_text_inputs(prompt, canvas=self._tm_default_canvas)
        if not self._tm_log_timings:
            return super().encode_prompt(prepared)
        started = time.perf_counter()
        hidden, tags = super().encode_prompt(prepared)
        if hidden.is_cuda:
            torch.accelerator.synchronize()
        logger.info("TaoMate-H3 prompt encode: %.3f s, %d tokens", time.perf_counter() - started, hidden.shape[0])
        return hidden, tags

    # -- AR-Diffusion capability --------------------------------------------

    def _kv_contract(self) -> KVContract:
        return KVContract(
            num_layers=int(self.transformer.arch.num_layers),
            local_heads=int(self.transformer.streaming_local_heads),
            head_dim=int(self.transformer.arch.attention_head_dim),
            dtype=torch.bfloat16,
        )

    def _dense_kv_rows_bound(self, canvas: CanvasGeometry) -> int:
        # Sink (12 video latents) + two recent AV chunks (10 latents each) +
        # one staged chunk (12 latents) plus their audio rows.
        video_latents = 12 + 10 + 10 + 12
        audio_rows = 2 * (60 + 56 + 56 + 60)
        return video_latents * canvas.frame_rows + audio_rows

    def ar_diffusion_kv_cache_spec(self) -> ARDiffusionKVCacheSpec:
        """Declare the (tiny) paged geometry and the model-owned dense state."""
        canvas = self._tm_default_canvas
        contract = self._kv_contract()
        # The dense history is rebuilt by concatenation at commit time, so two
        # copies of one layer coexist transiently; budget the whole cache twice.
        dense_bytes = 2 * contract.bytes_for_rows(self._dense_kv_rows_bound(canvas))
        latent_bytes = 24 * REQUEST_VIDEO_LATENTS * canvas.latent_h * canvas.latent_w * 4 * 2
        audio_bytes = 2 * _AUDIO_ROW_WIDTH * 4 * REQUEST_AUDIO_LATENTS * 8
        decoder_bytes = (
            24 * 20 * canvas.latent_h * canvas.latent_w * 4 + 3 * 5 * canvas.height * canvas.width * 4 + 64 * 1024**2
        )
        return ARDiffusionKVCacheSpec(
            num_layers=contract.num_layers,
            num_kv_heads=contract.local_heads,
            head_size=contract.head_dim,
            tokens_per_frame=canvas.frame_rows,
            frames_per_block=1,
            window_frames=1,
            sink_frames=0,
            kv_branches=(ARDiffusionKVBranchSpec(_AR_BRANCH, 0),),
            session_capacity=1,
            model_owned_state_bytes_per_session=dense_bytes + latent_bytes + audio_bytes + decoder_bytes,
        )

    @contextmanager
    def bind_ar_diffusion_state(self, session_id: str, state: ARDiffusionKVState) -> Iterator[None]:
        if self._ar_diffusion_kv_state is not None:
            raise RuntimeError("TaoMate-H3 AR-Diffusion state is already bound")
        if state.session_id != session_id:
            raise ValueError(f"TaoMate-H3 bound session mismatch: {state.session_id!r} != {session_id!r}")
        self._ar_diffusion_kv_state = state
        try:
            yield
        finally:
            self._ar_diffusion_kv_state = None

    def reset_ar_diffusion_session(self, session_id: str) -> None:
        self._release_session(session_id)

    def close_ar_diffusion_session(self, session_id: str) -> None:
        self._release_session(session_id)

    def _release_session(self, session_id: str) -> None:
        session = self._tm_sessions.pop(session_id, None)
        if session is not None:
            # The caching allocator keeps the freed blocks: the next session
            # reuses them instead of paying cudaMalloc again for every new
            # history size in its first request.
            session.close()

    def _require_bound_ar_state(self) -> None:
        if self._ar_diffusion_kv_state is None:
            raise RuntimeError(
                "TaoMate-H3 step execution requires the AR-Diffusion engine "
                "(engine_backend: vllm_omni.experimental.ar_diffusion.engine.ARDiffusionEngine)"
            )

    def _bound_session_id(self, state: StepRequestState) -> str:
        bound = self._ar_diffusion_kv_state
        return bound.session_id if bound is not None else state.request_id

    def _session(self, state: StepRequestState) -> _Session:
        key = state.extra.get("taomate_session_id") or self._bound_session_id(state)
        session = self._tm_sessions.get(key)
        if session is None:
            raise RuntimeError(f"TaoMate-H3 has no session {key!r} for request {state.request_id!r}")
        return session

    # -- request mode: a whole session in one call (offline use and the AR warmup) --

    def forward(self, request: DiffusionRequestBatch) -> DiffusionOutput:  # type: ignore[override]
        """Generate every phase of the requested frame budget and return the joined media.

        Request mode under the AR-Diffusion runner (the session KV must be
        bound by the runner, so this is not a standalone offline path): it
        drives the same step contract to completion in one runner invocation
        and serves the runner's load-time warmup. Streaming clients use the
        WebSocket realtime endpoint.
        """
        if request.num_reqs != 1:
            raise OmniClientError("TaoMate-H3 request mode serves one request at a time")
        req = request.requests[0]
        state = StepRequestState(request_id=req.request_id, sampling=req.sampling_params, prompt=req.prompt)
        self.prepare_encode(state)
        state.extra["taomate_no_hold"] = True  # one call, no client to wait for
        self.prepare_next_chunk(state)
        frames: list[np.ndarray] = []
        audio: list[np.ndarray] = []
        chunk_metadata: list[dict[str, Any]] = []
        last: DiffusionOutput | None = None
        while not state.request_denoise_completed:
            for _ in range(STUDENT_STEPS):
                velocity = self.denoise_step(cast(InputBatch, None), states=[state])
                assert velocity is not None
                self.step_scheduler(state, velocity)
            last = self.post_decode(state)
            envelope = cast(dict[str, Any], last.output)
            frames.append(envelope["payload"]["video"])
            audio.append(envelope["payload"]["audio"])
            chunk_metadata.append(envelope["metadata"]["taomate_h3"])
            if not state.request_denoise_completed:
                self.prepare_next_chunk(state)
        assert last is not None
        session_id = self._bound_session_id(state)
        video = np.concatenate([item for item in frames if item.shape[0]], axis=0) if frames else np.zeros((0, 1, 1, 3))
        waveform = np.concatenate(audio, axis=0) if audio else np.zeros((0, 2), np.float32)
        return DiffusionOutput(
            output={
                "payload": {"video": video, "audio": waveform},
                "metadata": {
                    "video": {"fps": float(VIDEO_FPS)},
                    "audio": {"sample_rate": AUDIO_SAMPLE_RATE},
                    "ar_diffusion": ARDiffusionChunkMetadata(
                        session_id=session_id,
                        request_id=req.request_id,
                        chunk_index=state.chunk_index - 1,
                        applied_event_ids=(),
                    ).to_dict(),
                    "taomate_h3": {"chunks": chunk_metadata},
                },
            },
            chunk_index=state.chunk_index - 1,
            total_chunks=state.total_chunks,
            finished=True,
        )

    def ar_diffusion_warmup_requests(self, session_id: str) -> Iterator[OmniDiffusionRequest]:
        """One session of ``taomate_h3_warmup_requests`` requests: every phase and teacher shape, the decoders."""
        num_frames = REQUEST_NATIVE_FRAMES + (self._tm_warmup_requests - 1) * STEADY_NATIVE_FRAMES
        self._tm_warmup_session_ids.add(session_id)
        yield OmniDiffusionRequest(
            prompt="A presenter smiles at the camera and greets the audience warmly.",
            sampling_params=OmniDiffusionSamplingParams(
                num_frames=num_frames,
                height=self._tm_default_height,
                width=self._tm_default_width,
                seed=self._tm_default_seed,
                extra_args={"session_id": session_id, "reset": True},
            ),
            request_id=f"taomate-h3-warmup-{session_id}",
        )

    # -- step execution ------------------------------------------------------

    def prepare_encode(self, state: StepRequestState, **kwargs: Any) -> StepRequestState:
        del kwargs
        self._require_bound_ar_state()
        if self._tm_teacher is None:
            raise RuntimeError("TaoMate-H3 weights are not loaded")
        sampling = state.sampling
        if int(getattr(sampling, "num_outputs_per_prompt", 1) or 1) != 1:
            raise OmniClientError("TaoMate-H3 produces one stream per session; num_outputs_per_prompt must be 1")
        prompt_text, _ = self._extract_prompt(state.prompt)
        height = int(getattr(sampling, "height", None) or self._tm_default_height)
        width = int(getattr(sampling, "width", None) or self._tm_default_width)
        try:
            canvas = CanvasGeometry(height=height, width=width)
        except ValueError as exc:
            raise OmniClientError(str(exc)) from exc
        if canvas != self._tm_default_canvas:
            raise OmniClientError(
                f"TaoMate-H3 was deployed for {self._tm_default_width}x{self._tm_default_height}; "
                f"request asked for {width}x{height}. Set model_config.taomate_h3_width/height."
            )
        seed = getattr(sampling, "seed", None)
        seed = self._tm_default_seed if seed is None else int(seed)
        num_frames = int(getattr(sampling, "num_frames", None) or 0) or DEFAULT_SESSION_FRAMES
        total_chunks = phases_for_frames(num_frames)
        hidden, tags = self.encode_prompt(prompt=prompt_text)
        state.prompt_embeds = hidden
        session_id = self._bound_session_id(state)
        previous = self._tm_sessions.pop(session_id, None)
        if previous is not None:
            previous.close()
        session = _Session(
            session_id=session_id,
            canvas=canvas,
            seed=seed,
            contract=self._kv_contract(),
            video_decoder=StreamingVideoDecoder(
                self.video_vae,
                device=self.device,
                height=canvas.height,
                width=canvas.width,
                emit_frames=self._tm_output_rank,
            ),
            audio_decoder=StreamingAudioDecoder(self.audio_vae, device=self.device),
            audio_kv_reset_requests=self._tm_audio_kv_reset_requests,
            pad_text_tokens=self._tm_pad_text_tokens,
        )
        self._tm_sessions[session_id] = session
        state.chunk_num_steps = STUDENT_STEPS
        state.total_chunks = total_chunks
        state.chunk_index = 0
        state.step_index = 0
        state.step_in_chunk = 0
        state.do_true_cfg = False
        state.timesteps = torch.tensor(
            [1.0 - sigma for sigma in session.sigmas_video[:-1]], dtype=torch.float32, device=self.device
        )
        state.extra = {"text_tags": tags, "audio_rows": None, "taomate_session_id": session_id}
        logger.info(
            "TaoMate-H3 session %s: %dx%d, seed=%d, %d chunk(s) (%d request(s)), prompt=%.40r",
            session_id,
            canvas.width,
            canvas.height,
            seed,
            total_chunks,
            total_chunks // NUM_PHASES,
            prompt_text,
        )
        return state

    def prepare_next_chunk(self, state: StepRequestState) -> None:
        """Start the next phase (and the next request at every fourth chunk)."""
        if state.request_denoise_completed:
            return
        session = self._session(state)
        prepare_started = time.perf_counter()
        try:
            self._prepare_next_chunk(state, session)
        finally:
            session.prepare_seconds = time.perf_counter() - prepare_started

    def _prepare_next_chunk(self, state: StepRequestState, session: _Session) -> None:
        phase_index = state.chunk_index % NUM_PHASES
        if phase_index == 0:
            version = _prompt_version(state)
            if (
                self._tm_hold_for_prompt
                and state.chunk_index >= NUM_PHASES
                and not state.extra.get("taomate_no_hold")
                and version <= int(state.extra.get("taomate_prompt_version", 0))
            ):
                # Hold at the request boundary until the client locks this
                # request's prompt; denoise_step polls (see _tm_hold_for_prompt).
                state.extra["taomate_held"] = True
                # the runner batches every scheduled state: keep a valid current timestep
                # and never re-decode the finished phase while idling
                state.step_in_chunk = 0
                state.step_index = 0
                # Idle steps emit nothing: stop the AR runner from grouping them as
                # one chunk's denoise steps, so every idle step returns to the
                # scheduler (where the client's prompt update arrives).
                self.supports_chunk_step_grouping = False
                return
            self.__dict__.pop("supports_chunk_step_grouping", None)  # back to the class policy
            state.extra["taomate_held"] = False
            state.extra["taomate_prompt_version"] = version
            if state.prompt_embeds is None:
                raise RuntimeError("TaoMate-H3 request needs prompt embeddings")
            text_embeddings = state.prompt_embeds
            # The step runner batches prompt embeddings as [1, L, D]; TaoMate
            # packs plain text rows.
            if text_embeddings.ndim == 3 and text_embeddings.shape[0] == 1:
                text_embeddings = text_embeddings[0]
            if text_embeddings.ndim != 2:
                raise RuntimeError(
                    f"TaoMate-H3 prompt embeddings must be [L, 5120], got {tuple(text_embeddings.shape)}"
                )
            tags = state.extra.get("text_tags")
            if tags is None or int(tags.shape[0]) != int(text_embeddings.shape[0]):
                # A prompt interaction replaced the embeddings; TaoMate prompts are plain text rows.
                tags = torch.ones(int(text_embeddings.shape[0]), dtype=torch.long, device=text_embeddings.device)
                state.extra["text_tags"] = tags
            session.begin_request(text_embeddings=text_embeddings, text_tags=tags, device=self.device)
        request = session.request
        assert request is not None
        phase_state = session.begin_phase(phase_index, transformer=self.transformer, device=self.device)
        state.latents = request.phase_video_rows(phase_state.phase)
        state.extra["audio_rows"] = request.phase_audio_rows(phase_state.phase)
        state.timesteps = torch.tensor(
            [1.0 - sigma for sigma in session.sigmas_video[:-1]], dtype=torch.float32, device=self.device
        )
        state.step_index = 0
        state.step_in_chunk = 0

    def _warm_teacher_shapes(self, session: _Session, request: _RequestState) -> None:
        graph = self._tm_teacher_graph
        if graph is None or not graph.enabled or self._tm_teacher is None:
            return
        lengths = self._tm_teacher_graph_text_lengths
        if lengths is not None and self._is_warmup_session(session):
            self._precapture_teacher_graphs(session, request, lengths)
        started = time.perf_counter()
        text_len = request.text_len
        captured = self._tm_teacher.warm_shapes(
            text_embeddings=request.text_embeddings,
            text_tags=request.text_tags,
            canvas=session.canvas,
            seq_len_for=lambda with_reference: session.pinned_teacher_seq_len(text_len, with_reference=with_reference),
        )
        if captured:
            logger.info(
                "TaoMate-H3 session %s: captured %d teacher graph(s) for %d text rows in %.2f s",
                session.session_id,
                captured,
                text_len,
                time.perf_counter() - started,
            )

    def _is_warmup_session(self, session: _Session) -> bool:
        return session.session_id in self._tm_warmup_session_ids

    def _precapture_teacher_graphs(self, session: _Session, request: _RequestState, lengths: range) -> None:
        """Capture the teacher graphs of every configured prompt length (load-time warmup only)."""
        teacher = self._tm_teacher
        graph = self._tm_teacher_graph
        assert teacher is not None and graph is not None
        started = time.perf_counter()
        width = int(request.text_embeddings.shape[1])
        captured = 0
        for text_len in lengths:
            if not graph.enabled:
                break
            captured += teacher.warm_shapes(
                text_embeddings=torch.zeros((text_len, width), dtype=request.text_embeddings.dtype, device=self.device),
                text_tags=torch.ones(text_len, dtype=torch.long),
                canvas=session.canvas,
                seq_len_for=lambda with_reference, n=text_len: session.pinned_teacher_seq_len(
                    n, with_reference=with_reference
                ),
            )
        logger.info(
            "TaoMate-H3 warmup: captured %d teacher graph(s) for prompts of %d-%d tokens in %.1f s (%d resident)",
            captured,
            lengths[0],
            lengths[-1],
            time.perf_counter() - started,
            graph.num_graphs,
        )

    def _run_teacher(self, session: _Session) -> None:
        request = session.request
        assert request is not None and self._tm_teacher is not None
        started = time.perf_counter()
        result = self._tm_teacher.run_request(
            text_embeddings=request.text_embeddings,
            text_tags=request.text_tags,
            canvas=session.canvas,
            plan=request.plan,
            audio_seed=request.audio_seed,
            previous_clean=session.teacher_previous_clean,
            previous_audio_latent_count=session.teacher_previous_count,
            seq_len=session.pinned_teacher_seq_len(
                request.text_len, with_reference=session.teacher_previous_clean is not None
            ),
        )
        request.teacher = result
        request.teacher_seconds = time.perf_counter() - started
        session.stats["teacher_seconds"] += request.teacher_seconds
        session.teacher_previous_clean = result.clean
        session.teacher_previous_count = result.audio_latent_count
        # The request's clean audio is final now; make it available to the
        # sliding-window audio decoder ahead of the phases that publish it.
        session.audio_decoder.append(
            minimax_h3_unpack_audio_tokens(result.clean, audio_t=2 * result.audio_latent_count, audio_channel=2)
        )

    def denoise_step(
        self,
        input_batch: InputBatch,
        *,
        states: Sequence[StepRequestState] | None = None,
        **kwargs: Any,
    ) -> torch.Tensor | None:
        del input_batch, kwargs
        if states is None or len(states) != 1:
            raise ValueError("TaoMate-H3 step execution serves one session per forward")
        self._require_bound_ar_state()
        state = states[0]
        if state.extra.get("taomate_held"):
            # Still at a held request boundary: apply any prompt the client sent
            # since the last step (the same interaction sequence reaches every
            # rank, so all ranks decide alike), then start the request or idle.
            self.apply_interaction_at_chunk_boundary(state)
            self.prepare_next_chunk(state)
            if state.extra.get("taomate_held"):
                time.sleep(self._tm_hold_poll_seconds)
                return None
        session = self._session(state)
        request = session.request
        phase_state = session.phase
        if request is None or phase_state is None or state.latents is None:
            raise RuntimeError("TaoMate-H3 denoise_step called before prepare_next_chunk")
        if request.teacher is None:
            if not session.teacher_shapes_warm:
                # First step of the session, inside the runner's forward
                # context (the sequence-parallel span is resolved from it):
                # capture the teacher graphs of this prompt length now rather
                # than inside the first requests of the stream.
                session.teacher_shapes_warm = True
                self._warm_teacher_shapes(session, request)
            self._run_teacher(session)
        step = state.step_in_chunk
        if step >= STUDENT_STEPS:
            raise RuntimeError(f"TaoMate-H3 phase has only {STUDENT_STEPS} denoise steps, got step {step}")
        t_video = 1.0 - session.sigmas_video[step]
        t_audio = 1.0 - session.sigmas_audio[step]
        if "rope_table" not in phase_state.branch.static_kwargs:
            phase_state.branch.prepare_rope_table(self.transformer)
        forward_kwargs = phase_state.branch.forward_kwargs(
            video_rows=state.latents,
            audio_rows=state.extra["audio_rows"],
            t_video=t_video,
            t_audio=t_audio,
            imgvid_cond_timestep=t_video,
            audio_ref_cond_timestep=1.0,
        )
        started = time.perf_counter()
        with stream_context(session.stream_context(StreamMode.NOISY)), torch.inference_mode():
            velocity_video, _ = self.transformer(**forward_kwargs)
        if self._tm_log_timings:
            if velocity_video.is_cuda:
                torch.accelerator.synchronize()
        phase_state.timings["denoise"] = phase_state.timings.get("denoise", 0.0) + (time.perf_counter() - started)
        session.stats["student_forwards"] += 1
        return velocity_video.float()

    def step_scheduler(self, state: StepRequestState, noise_pred: torch.Tensor | None, **kwargs: Any) -> None:
        del kwargs
        if noise_pred is None and state.extra.get("taomate_held"):
            return  # idle step at a held request boundary: nothing advances
        session = self._session(state)
        request = session.request
        phase_state = session.phase
        if request is None or phase_state is None or state.latents is None or request.teacher is None:
            raise RuntimeError("TaoMate-H3 step_scheduler called out of order")
        step = state.step_in_chunk
        video_rows = state.latents.clone()
        euler_eta0_update_(
            video_rows,
            noise_pred.float(),
            sigma_curr=session.sigmas_video[step],
            sigma_next=session.sigmas_video[step + 1],
        )
        state.latents = video_rows
        # The student's audio velocity is discarded: audio comes from the base
        # teacher's milestone for this step (states 3, 6, 9).
        state.extra["audio_rows"] = request.phase_audio_rows(phase_state.phase, request.teacher.milestones[step])
        state.step_in_chunk += 1
        state.step_index += 1

    def post_decode(self, state: StepRequestState, **kwargs: Any) -> DiffusionOutput:
        del kwargs
        self._require_bound_ar_state()
        session = self._session(state)
        request = session.request
        phase_state = session.phase
        if request is None or phase_state is None or state.latents is None or request.teacher is None:
            raise RuntimeError("TaoMate-H3 post_decode called out of order")
        phase = phase_state.phase
        audio_rows = state.extra["audio_rows"]
        clean_video = session.renorm_clean_video_rows(state.latents)
        # Sigma-zero forward: recompute this chunk's K/V from its clean latents
        # and append them to the persistent history.
        cache = session.cache
        commit_started = time.perf_counter()
        cache.begin_clean_commit(cache.committed_blocks)
        try:
            forward_kwargs = phase_state.branch.forward_kwargs(
                video_rows=clean_video,
                audio_rows=audio_rows,
                t_video=1.0,
                t_audio=1.0,
                imgvid_cond_timestep=1.0,
                audio_ref_cond_timestep=1.0,
            )
            with stream_context(session.stream_context(StreamMode.CLEAN_COMMIT)), torch.inference_mode():
                self.transformer(**forward_kwargs)
            cache.commit()
        except BaseException:
            cache.rollback()
            raise
        cache.retain_sink_and_recent_commits()
        session.stats["clean_forwards"] += 1
        if self._tm_log_timings and torch.cuda.is_available():
            torch.accelerator.synchronize()
        phase_state.timings["commit"] = time.perf_counter() - commit_started

        # Publish this phase: incremental video decode plus the aligned audio.
        decode_started = time.perf_counter()
        latent = minimax_h3_unpatchify_video_tokens(
            clean_video,
            latent_shape=(phase.video_latent_count, session.canvas.latent_h // 2, session.canvas.latent_w // 2, 24),
            patch_size=(1, 2, 2),
        )
        frame_start, frames = session.video_decoder.push(latent)
        phase_state.timings["video_decode"] = time.perf_counter() - decode_started
        completed_chunk_index = state.chunk_index
        state.chunk_index += 1
        last_phase = (completed_chunk_index % NUM_PHASES) == NUM_PHASES - 1
        session_done = state.request_denoise_completed
        if session_done:
            flush_start, flushed = session.video_decoder.flush()
            if flushed is not None:
                frames = flushed if frames is None else np.concatenate((frames, flushed), axis=0)
                if frames is flushed:
                    frame_start = flush_start
        num_frames = 0 if frames is None else int(frames.shape[0])
        audio_started = time.perf_counter()
        if self._tm_output_rank:
            audio = session.audio_decoder.decode_range(
                samples_at_frame(frame_start), samples_at_frame(frame_start + num_frames)
            )
        else:
            # The executor returns rank 0's output; peers keep the decoder
            # timeline but skip the waveform decode.
            session.audio_decoder.skip_range(samples_at_frame(frame_start + num_frames))
            audio = np.zeros((0, 2), dtype=np.float32)
        phase_state.timings["audio_decode"] = time.perf_counter() - audio_started
        session.frames_published = frame_start + num_frames
        phase_end = time.perf_counter()
        phase_seconds = phase_end - phase_state.started_at
        if self._tm_log_timings:
            graph = self._tm_teacher_graph
            # ``period`` is the wall time between the ends of consecutive
            # phases: the phase itself plus everything the runner does around
            # it (phase preparation, output handling, interaction apply).
            period = 0.0 if session.last_phase_end is None else phase_end - session.last_phase_end
            logger.info(
                "TaoMate-H3 %s request %d phase %d: %.3f s total (teacher %.3f, denoise x3 %.3f, commit %.3f, "
                "video decode %.3f, audio decode %.3f, prepare %.3f), period %.3f s, %d frames, history %d rows%s",
                session.session_id,
                request.index,
                phase.index,
                phase_seconds,
                request.teacher_seconds if phase.index == 0 else 0.0,
                phase_state.timings.get("denoise", 0.0),
                phase_state.timings.get("commit", 0.0),
                phase_state.timings.get("video_decode", 0.0),
                phase_state.timings.get("audio_decode", 0.0),
                session.prepare_seconds,
                period,
                num_frames,
                cache.history_tokens,
                "" if graph is None else f", teacher graphs {graph.stats()}",
            )
        session.last_phase_end = phase_end
        payload: dict[str, Any] = {
            "video": frames
            if frames is not None
            else np.zeros((0, session.canvas.height, session.canvas.width, 3), np.uint8),
            "audio": audio,
        }
        metadata: dict[str, Any] = {
            "video": {"fps": float(VIDEO_FPS)},
            "audio": {"sample_rate": AUDIO_SAMPLE_RATE},
            "ar_diffusion": ARDiffusionChunkMetadata(
                session_id=session.session_id,
                request_id=state.request_id,
                chunk_index=completed_chunk_index,
                applied_event_ids=(),
            ).to_dict(),
            "taomate_h3": {
                "request_index": request.index,
                "phase_index": phase.index,
                "frame_start": frame_start,
                "num_frames": num_frames,
                "audio_samples": int(audio.shape[0]),
                "history_tokens": cache.history_tokens,
                "teacher_seconds": round(request.teacher_seconds, 4),
                "phase_seconds": round(phase_seconds, 4),
                **{f"{name}_seconds": round(value, 4) for name, value in phase_state.timings.items()},
            },
        }
        if last_phase:
            session.finish_request()
        return DiffusionOutput(
            output={"payload": payload, "metadata": metadata},
            chunk_index=completed_chunk_index,
            total_chunks=state.total_chunks,
            finished=session_done,
        )

    # -- interaction hooks ----------------------------------------------------

    def peek_chunk_media(self, state: StepRequestState) -> ChunkMediaSpec:
        """Frames of the next phase (approximate: the decoder holds a five-frame overlap)."""
        chunk = state.chunk_index
        plan = request_plan(chunk // NUM_PHASES)
        phase = plan.phases[chunk % NUM_PHASES]
        fps = getattr(state.sampling, "fps", None) or float(VIDEO_FPS)
        return ChunkMediaSpec(
            num_media_frames=phase.frame_count,
            fps=float(fps),
            num_latent_frames=phase.video_latent_count,
        )


def get_taomate_h3_post_process_func(od_config: OmniDiffusionConfig):
    """Pass the payload/metadata envelope through untouched."""
    del od_config

    def post_process_func(output: Any, output_type: str = "np", sampling_params: Any | None = None) -> Any:
        del output_type, sampling_params
        if isinstance(output, dict) and isinstance(output.get("payload"), dict):
            return output
        return {"payload": {"video": output}, "metadata": {}}

    return post_process_func


__all__ = ["TaoMateH3Pipeline", "get_taomate_h3_post_process_func"]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/interaction/modality_handlers/prompt.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""Prompt-track interaction handler (midway prompt updates)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import torch
from typing_extensions import override

from vllm_omni.diffusion.interaction.modality_handlers.base import InteractionHandler
from vllm_omni.diffusion.interaction.types import (
    InteractionChunkMetadata,
    InteractionEvent,
    InteractionMode,
    InteractionPayload,
    InteractionSession,
)
from vllm_omni.diffusion.worker.utils import StepRequestState

DEFAULT_TRANSITION_CHUNKS = 3

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class QueuedPromptEvent(InteractionEvent):
    """Last-write-wins prompt update waiting for / active at a chunk boundary.

    ``source_prompt_embeds`` is the lerp start endpoint, staged when this event
    is activated (not at enqueue). Live blended embeds live on
    ``StepRequestState.prompt_embeds``.
    """

    mode: InteractionMode = "target"
    prompt: str
    target_prompt_embeds: torch.Tensor
    source_prompt_embeds: torch.Tensor | None = None

    def blended_prompt_embeds(self) -> torch.Tensor:
        assert self.source_prompt_embeds is not None
        alpha = self._current_alpha()
        if alpha >= 1.0:
            return self.target_prompt_embeds
        return (1.0 - alpha) * self.source_prompt_embeds + alpha * self.target_prompt_embeds

    def advance_transition(self) -> None:
        assert self.source_prompt_embeds is not None
        if self.transition_chunks <= 0:
            self.source_prompt_embeds = self.target_prompt_embeds
            return
        self.elapsed_transition_chunks += 1
        if self.elapsed_transition_chunks >= self.transition_chunks:
            self.source_prompt_embeds = self.target_prompt_embeds
            self.elapsed_transition_chunks = float(self.transition_chunks)

    def _current_alpha(self) -> float:
        if self.transition_chunks <= 0:
            return 1.0
        return min(1.0, self.elapsed_transition_chunks / self.transition_chunks)


@dataclass
class PromptSession(InteractionSession):
    """Request-local prompt-update session under ``state.interaction_sessions['prompt']``."""

    pending_event: QueuedPromptEvent | None = None
    active_event: QueuedPromptEvent | None = None
    version: int = 0


def prompt_update_versions(states: Sequence[StepRequestState]) -> tuple[int, ...]:
    """Return per-request prompt-update versions for batch cache comparison."""
    versions: list[int] = []
    for state in states:
        session = state.interaction_sessions.get("prompt")
        versions.append(session.version if isinstance(session, PromptSession) else 0)
    return tuple(versions)


class PromptInteractionHandler(InteractionHandler):
    """Encode-and-queue prompt updates; lerp embeds at chunk boundaries.

    Mirrors the former ``PromptUpdateMixin`` behavior. Encoding happens at
    enqueue time via an injected ``encode_prompt`` callable.
    """

    modality: ClassVar[str] = "prompt"
    lazy_initialize_session: ClassVar[bool] = True

    def __init__(
        self,
        *,
        encode_prompt: Callable[..., tuple[torch.Tensor, ...]],
        device: torch.device | str,
        dtype: torch.dtype,
    ) -> None:
        self._encode_prompt = encode_prompt
        self._device = device
        self._dtype = dtype

    @classmethod
    @override
    def from_pipeline(cls, pipeline: Any) -> PromptInteractionHandler:
        """Build a handler from a diffusion pipeline that exposes ``encode_prompt``."""
        return cls(
            encode_prompt=pipeline.encode_prompt,
            device=pipeline.device,
            dtype=pipeline.transformer.dtype,
        )

    @override
    def validate_payload(
        self,
        state: StepRequestState,
        *,
        event_id: str,
        payload: InteractionPayload,
        transition_chunks: int | None,
    ) -> None:
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt must be non-empty")
        if not event_id:
            raise ValueError("event_id must be non-empty")
        if state.prompt_embeds is None:
            raise ValueError(
                f"prompt_update is not allowed before initial generation has started (request_id={state.request_id!r})"
            )
        duration = DEFAULT_TRANSITION_CHUNKS if transition_chunks is None else transition_chunks
        if duration < 0:
            raise ValueError("transition_chunks must be >= 0")

    @override
    def enqueue(
        self,
        state: StepRequestState,
        *,
        event_id: str,
        received_at: float,
        payload: InteractionPayload,
        transition_chunks: int | None,
    ) -> None:
        """Prompt updates are last-write-win and unbuffered at chunk boundary."""
        self.validate_payload(
            state,
            event_id=event_id,
            payload=payload,
            transition_chunks=transition_chunks,
        )
        prompt = payload.get("prompt")
        assert isinstance(prompt, str)
        duration = DEFAULT_TRANSITION_CHUNKS if transition_chunks is None else transition_chunks

        target_prompt_embeds, _ = self._encode_prompt(
            prompt=prompt,
            negative_prompt=None,
            do_classifier_free_guidance=False,
            num_videos_per_prompt=state.sampling.num_outputs_per_prompt,
            max_sequence_length=state.sampling.max_sequence_length,
            device=self._device,
            dtype=self._dtype,
        )
        session = state.interaction_sessions.setdefault("prompt", PromptSession())
        assert isinstance(session, PromptSession)
        with session.lock:
            # Chunk-level LWW: replace any prior pending event.
            session.pending_event = QueuedPromptEvent(
                event_id=event_id,
                received_at=received_at,
                transition_chunks=duration,
                prompt=prompt,
                target_prompt_embeds=target_prompt_embeds,
            )

    @override
    def apply_at_chunk_boundary(
        self,
        state: StepRequestState,
        *,
        boundary_at: float,
        chunk_index: int | None = None,
        num_media_frames: int | None = None,
        fps: float | None = None,
        num_latent_frames: int | None = None,
    ) -> InteractionChunkMetadata | None:
        """Advance or start prompt interpolation before the next chunk."""
        # Prompt lerp is chunk-LWW; media timeline and caller chunk_index unused.
        del chunk_index, num_media_frames, fps, num_latent_frames
        session = state.interaction_sessions.get("prompt")
        assert isinstance(session, PromptSession)

        embeds_changed = False
        next_chunk_index = state.chunk_index
        started_event_ids: list[str] = []
        active_event_ids: list[str] = []
        completed_event_ids: list[str] = []

        with session.lock:
            # Prompt ignores frame scheduling but still records the boundary clock.
            session.last_boundary_at = boundary_at
            pending_event = session.pending_event
            session.pending_event = None
            active_event = session.active_event

            # If current transition is not complete, advance it.
            # After completion, leave active_event in place (so a later pending
            # update can abort/overwrite), but do not keep bumping the version.
            if active_event is not None:
                in_transition = (
                    active_event.transition_chunks > 0
                    and active_event.elapsed_transition_chunks < active_event.transition_chunks
                )
                if in_transition:
                    active_event.advance_transition()
                    state.prompt_embeds = active_event.blended_prompt_embeds()
                    embeds_changed = True
                    active_event_ids.append(active_event.event_id)
                    if active_event.elapsed_transition_chunks >= active_event.transition_chunks:
                        state.prompt_embeds = active_event.target_prompt_embeds
                        active_event.source_prompt_embeds = active_event.target_prompt_embeds
                        completed_event_ids.append(active_event.event_id)
                        logger.debug(
                            "prompt_update transition complete request_id=%s next_chunk_index=%d prompt=%.20s...",
                            state.request_id,
                            next_chunk_index,
                            active_event.prompt,
                        )

            # If a new prompt update is pending, start a new transition.
            if pending_event is not None:
                if state.prompt_embeds is None:
                    raise RuntimeError(
                        "internal error: trying to apply a pending prompt update but "
                        f"current prompt_embeds is None (request_id={state.request_id!r})"
                    )
                # Stage lerp-start embeds at activation (after any same-boundary advance).
                pending_event.source_prompt_embeds = state.prompt_embeds.detach().clone()
                pending_event.elapsed_transition_chunks = 0.0
                session.active_event = pending_event
                active_event = pending_event
                event_id = pending_event.event_id
                duration = pending_event.transition_chunks
                prompt = pending_event.prompt
                target = pending_event.target_prompt_embeds
                started_event_ids.append(event_id)
                active_event_ids.append(event_id)
                if duration <= 0:
                    # A hard/immediate transition
                    state.prompt_embeds = target
                    pending_event.source_prompt_embeds = target
                    completed_event_ids.append(event_id)
                    logger.debug(
                        "prompt_update sharp transition request_id=%s next_chunk_index=%d prompt=%.20s...",
                        state.request_id,
                        next_chunk_index,
                        prompt,
                    )
                else:
                    # A transition that really takes some time
                    active_event.advance_transition()
                    state.prompt_embeds = active_event.blended_prompt_embeds()
                    if active_event.elapsed_transition_chunks >= active_event.transition_chunks:
                        state.prompt_embeds = active_event.target_prompt_embeds
                        active_event.source_prompt_embeds = active_event.target_prompt_embeds
                        completed_event_ids.append(event_id)
                    logger.debug(
                        "prompt_update transition start request_id=%s next_chunk_index=%d prompt=%.20s...",
                        state.request_id,
                        next_chunk_index,
                        prompt,
                    )
                embeds_changed = True

            # Indicate that prompt embeddings have changed---clear input batch cache.
            if embeds_changed:
                session.version += 1

        return InteractionChunkMetadata(
            started_event_ids=started_event_ids,
            active_event_ids=active_event_ids,
            completed_event_ids=completed_event_ids,
        )

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/worker/input_batch.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""Diffusion input-batch structures following the MRV2-style vLLM layout.

Request states remain the only persistent source of truth. Static tensors are
normalized/padded onto the request state once, while :class:`InputBatch`
assembles an ephemeral step-local view. Dynamic tensors are re-gathered every
step, and step outputs are scattered back into request states by
``scatter_latents()`` using ``idx_mapping``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import torch

from vllm_omni.diffusion.interaction.modality_handlers.prompt import prompt_update_versions
from vllm_omni.diffusion.worker.utils import StepRequestState


def _normalize_prompt_embeds(x: torch.Tensor) -> torch.Tensor:
    if x.ndim == 2:
        return x.unsqueeze(0)
    if x.ndim == 3:
        return x
    raise ValueError(f"prompt_embeds must be 2D or 3D, got shape={tuple(x.shape)}")


def _normalize_mask(x: torch.Tensor) -> torch.Tensor:
    if x.ndim == 1:
        x = x.unsqueeze(0)
    elif x.ndim != 2:
        raise ValueError(f"prompt mask must be 1D or 2D, got shape={tuple(x.shape)}")
    if x.dtype != torch.bool:
        x = x != 0
    return x


def _pad_prompt_embeds(x: torch.Tensor, target_seq_len: int) -> torch.Tensor:
    x = _normalize_prompt_embeds(x)
    bsz, seq_len, hidden = x.shape
    if seq_len == target_seq_len:
        return x
    out = x.new_zeros((bsz, target_seq_len, hidden))
    out[:, :seq_len] = x
    return out


def _pad_mask(x: torch.Tensor, target_seq_len: int) -> torch.Tensor:
    x = _normalize_mask(x)
    bsz, seq_len = x.shape
    if seq_len == target_seq_len:
        return x
    out = torch.zeros((bsz, target_seq_len), dtype=torch.bool, device=x.device)
    out[:, :seq_len] = x
    return out


def _select_states(
    states: Sequence[StepRequestState],
    idx_mapping: torch.Tensor | None,
) -> tuple[list[StepRequestState], torch.Tensor, np.ndarray]:
    if not states:
        raise ValueError("Cannot build InputBatch from empty states.")

    if idx_mapping is None:
        # The identity mapping is known on the host; build the device copy as
        # a launch and the host copy from NumPy rather than reading the device
        # tensor back. This runs on every step of every stepwise request, and
        # a device-to-host read here would stall the host until the queued
        # denoise work drained, so it must not be a synchronising operation.
        device = states[0].latents.device if states[0].latents is not None else None
        idx_mapping = torch.arange(len(states), dtype=torch.int32, device=device)
        idx_mapping_np = np.arange(len(states), dtype=np.int32)
    else:
        if idx_mapping.ndim != 1:
            raise ValueError("idx_mapping must be a 1D tensor.")
        idx_mapping = idx_mapping.to(dtype=torch.int32)
        idx_mapping_np = idx_mapping.detach().cpu().numpy()

    selected_states: list[StepRequestState] = []
    for batch_idx, state_idx in enumerate(idx_mapping_np.tolist()):
        if state_idx < 0 or state_idx >= len(states):
            raise ValueError(f"idx_mapping[{batch_idx}]={state_idx} is out of range for states.")
        selected_states.append(states[state_idx])
    return selected_states, idx_mapping, idx_mapping_np


def _prepare_request_ids(states: Sequence[StepRequestState]) -> list[str]:
    return [state.request_id for state in states]


def _prepare_prompt_field_on_state(
    state: StepRequestState,
    *,
    embeds_attr: str,
    mask_attr: str,
) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    embeds = getattr(state, embeds_attr)
    if embeds is None:
        return None, None

    normalized_embeds = _normalize_prompt_embeds(embeds)
    if normalized_embeds is not embeds:
        setattr(state, embeds_attr, normalized_embeds)
    embeds = normalized_embeds

    mask = getattr(state, mask_attr)
    if mask is None:
        return embeds, None

    normalized_mask = _normalize_mask(mask)
    if normalized_mask is not mask:
        setattr(state, mask_attr, normalized_mask)
    return embeds, normalized_mask


def _prepare_reused_buffer(
    current: torch.Tensor | None,
    *,
    shape: tuple[int, ...],
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    if current is not None and tuple(current.shape) == shape and current.dtype == dtype and current.device == device:
        return current
    return torch.empty(shape, dtype=dtype, device=device)


def _validate_gather_tensors(
    values: Sequence[torch.Tensor],
    *,
    field_name: str,
) -> tuple[torch.dtype, torch.device, tuple[int, ...], int]:
    if not values:
        raise ValueError(f"Cannot gather empty tensor list for {field_name}.")

    first = values[0]
    dtype = first.dtype
    device = first.device
    suffix_shape = tuple(first.shape[1:])
    total_rows = 0

    for value in values:
        if value.dtype != dtype:
            raise ValueError(f"Mixed dtypes in {field_name} batch.")
        if value.device != device:
            raise ValueError(f"Mixed devices in {field_name} batch.")
        if tuple(value.shape[1:]) != suffix_shape:
            raise ValueError(
                f"Mixed trailing shapes in {field_name} batch: expected {suffix_shape}, got {tuple(value.shape[1:])}."
            )
        total_rows += int(value.shape[0])

    return dtype, device, suffix_shape, total_rows


def _gather_tensor_rows(
    values: Sequence[torch.Tensor],
    *,
    field_name: str,
    out: torch.Tensor | None = None,
) -> torch.Tensor:
    dtype, device, suffix_shape, total_rows = _validate_gather_tensors(
        values,
        field_name=field_name,
    )
    gathered = _prepare_reused_buffer(
        out,
        shape=(total_rows, *suffix_shape),
        dtype=dtype,
        device=device,
    )

    row_offset = 0
    for value in values:
        next_row_offset = row_offset + int(value.shape[0])
        gathered[row_offset:next_row_offset].copy_(value)
        row_offset = next_row_offset
    return gathered


def _get_seq_lens_from_mask(mask: torch.Tensor) -> list[int]:
    return mask.sum(dim=1, dtype=torch.int32).tolist()


def _get_request_prompt_seq_lens(
    state: StepRequestState,
    *,
    embeds_attr: str,
    mask_attr: str,
    seq_lens_attr: str,
) -> list[int]:
    embeds, mask = _prepare_prompt_field_on_state(
        state,
        embeds_attr=embeds_attr,
        mask_attr=mask_attr,
    )
    if embeds is None:
        raise ValueError(f"{embeds_attr} is not initialized on request {state.request_id}.")

    if mask is not None:
        if mask.shape[0] != embeds.shape[0]:
            raise ValueError(
                f"{mask_attr} batch dimension does not match {embeds_attr} for request {state.request_id}."
            )
        return _get_seq_lens_from_mask(mask)

    seq_lens = getattr(state, seq_lens_attr)
    if seq_lens is not None:
        return [int(value) for value in seq_lens]

    return [int(embeds.shape[1])] * int(embeds.shape[0])


def _prepare_request_prompt_field(
    state: StepRequestState,
    *,
    embeds_attr: str,
    mask_attr: str,
    seq_lens_attr: str,
    target_seq_len: int,
) -> tuple[torch.Tensor, torch.Tensor | None]:
    embeds, mask = _prepare_prompt_field_on_state(
        state,
        embeds_attr=embeds_attr,
        mask_attr=mask_attr,
    )
    if embeds is None:
        raise ValueError(f"{embeds_attr} is not initialized on request {state.request_id}.")

    actual_seq_lens = _get_request_prompt_seq_lens(
        state,
        embeds_attr=embeds_attr,
        mask_attr=mask_attr,
        seq_lens_attr=seq_lens_attr,
    )
    max_actual_seq_len = max(actual_seq_lens) if actual_seq_lens else 0

    if mask is None and max_actual_seq_len != target_seq_len:
        raise ValueError(
            f"Variable-length {embeds_attr} in batch but {mask_attr} is None. "
            f"Provide masks or ensure {embeds_attr} have the same seq_len."
        )

    current_seq_len = int(embeds.shape[1])
    if current_seq_len < target_seq_len:
        embeds = _pad_prompt_embeds(embeds, target_seq_len)
        setattr(state, embeds_attr, embeds)
        if mask is not None:
            mask = _pad_mask(mask, target_seq_len)
            setattr(state, mask_attr, mask)
        current_seq_len = target_seq_len

    if current_seq_len > target_seq_len:
        if max_actual_seq_len > target_seq_len:
            raise ValueError(
                f"{embeds_attr} for request {state.request_id} requires seq_len "
                f"{max_actual_seq_len}, got target {target_seq_len}."
            )
        embeds = embeds[:, :target_seq_len]
        mask = None if mask is None else mask[:, :target_seq_len]
        setattr(state, embeds_attr, embeds)
        if mask is not None:
            setattr(state, mask_attr, mask)
        setattr(state, seq_lens_attr, [int(embeds.shape[1])] * int(embeds.shape[0]))
        return embeds, mask

    setattr(state, seq_lens_attr, [int(embeds.shape[1])] * int(embeds.shape[0]))
    return embeds, mask


def _prepare_padded_prompt_fields(
    states: Sequence[StepRequestState],
    *,
    embeds_attr: str,
    mask_attr: str,
    seq_lens_attr: str,
    embeds_out: torch.Tensor | None = None,
    mask_out: torch.Tensor | None = None,
) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    prepared_fields = [
        _prepare_prompt_field_on_state(
            state,
            embeds_attr=embeds_attr,
            mask_attr=mask_attr,
        )
        for state in states
    ]
    embeds_values = [embeds for embeds, _ in prepared_fields]
    if not any(embeds is not None for embeds in embeds_values):
        return None, None
    if not all(embeds is not None for embeds in embeds_values):
        raise ValueError(f"Mixed {embeds_attr} in batch.")

    mask_values = [mask for _, mask in prepared_fields]
    if any(mask is None for mask in mask_values):
        if any(mask is not None for mask in mask_values):
            raise ValueError(f"Mixed {mask_attr} in batch.")

    target_seq_len = max(
        max(
            _get_request_prompt_seq_lens(
                state,
                embeds_attr=embeds_attr,
                mask_attr=mask_attr,
                seq_lens_attr=seq_lens_attr,
            )
        )
        for state in states
    )

    request_embeds: list[torch.Tensor] = []
    request_masks: list[torch.Tensor] = []
    for state in states:
        prepared_embeds, prepared_mask = _prepare_request_prompt_field(
            state,
            embeds_attr=embeds_attr,
            mask_attr=mask_attr,
            seq_lens_attr=seq_lens_attr,
            target_seq_len=target_seq_len,
        )
        request_embeds.append(prepared_embeds)
        if prepared_mask is not None:
            request_masks.append(prepared_mask)

    gathered_embeds = _gather_tensor_rows(
        request_embeds,
        field_name=embeds_attr,
        out=embeds_out,
    )

    if not request_masks:
        return gathered_embeds, None

    gathered_masks = _gather_tensor_rows(
        request_masks,
        field_name=mask_attr,
        out=mask_out,
    )
    return gathered_embeds, gathered_masks


def _prepare_latents(
    states: Sequence[StepRequestState],
    *,
    out: torch.Tensor | None = None,
) -> torch.Tensor:
    latents_values = [state.latents for state in states]
    if any(latents is None for latents in latents_values):
        raise ValueError("All requests must have `latents` initialized.")
    return _gather_tensor_rows(
        [latents for latents in latents_values if latents is not None],
        field_name="latents",
        out=out,
    )


def _require_state_latents(
    state: StepRequestState,
    *,
    for_field: str,
) -> torch.Tensor:
    latents = state.latents
    if latents is None:
        raise ValueError(f"Request {state.request_id} has no latents while preparing {for_field}.")
    return latents


def _expand_scalar_or_vector(
    value: torch.Tensor,
    *,
    num_rows: int,
    field_name: str,
) -> torch.Tensor:
    if value.ndim == 0:
        return value.reshape(1).expand(num_rows)
    if value.ndim != 1:
        raise ValueError(f"{field_name} must be scalar or 1D, got ndim={value.ndim}.")
    if value.shape[0] == num_rows:
        return value
    if value.shape[0] == 1:
        return value.expand(num_rows)
    raise ValueError(
        f"Per-request {field_name} must have either 1 element or {num_rows} elements; got {value.shape[0]}."
    )


def _prepare_timesteps(
    states: Sequence[StepRequestState],
    *,
    out: torch.Tensor | None = None,
) -> torch.Tensor:
    timestep_values: list[torch.Tensor] = []
    for state in states:
        timestep = state.current_timestep
        if timestep is None:
            raise ValueError("All requests must have a current timestep initialized.")
        if not torch.is_tensor(timestep):
            raise ValueError("InputBatch expects tensor timesteps; normalize them before batching.")
        latents = _require_state_latents(state, for_field="timesteps")
        timestep_values.append(
            _expand_scalar_or_vector(
                timestep,
                num_rows=int(latents.shape[0]),
                field_name="timestep tensor",
            )
        )

    return _gather_tensor_rows(
        timestep_values,
        field_name="timesteps",
        out=out,
    )


def _prepare_cfg_scalars(
    states: Sequence[StepRequestState],
) -> tuple[bool, float, bool]:
    def _cfg_scalars(state: StepRequestState) -> tuple[bool, float, bool]:
        true_cfg_scale = getattr(state.sampling, "true_cfg_scale", None) or 4.0
        cfg_normalize = bool(getattr(state.sampling, "cfg_normalize", False))
        return state.do_true_cfg, true_cfg_scale, cfg_normalize

    scalars = _cfg_scalars(states[0])
    for state in states[1:]:
        if _cfg_scalars(state) != scalars:
            raise ValueError("Mixed CFG settings in one diffusion batch are not supported.")
    return scalars


def _prepare_guidance(
    states: Sequence[StepRequestState],
    *,
    out: torch.Tensor | None = None,
) -> torch.Tensor | None:
    guidance_values = [state.guidance for state in states]
    if all(guidance is None for guidance in guidance_values):
        return None
    if any(guidance is None for guidance in guidance_values):
        raise ValueError("Mixed guidance in one diffusion batch are not supported.")

    gathered_guidance: list[torch.Tensor] = []
    for state in states:
        latents = _require_state_latents(state, for_field="guidance")
        guidance = state.guidance
        assert guidance is not None
        guidance_tensor = torch.as_tensor(
            guidance,
            device=latents.device,
            dtype=latents.dtype,
        )
        gathered_guidance.append(
            _expand_scalar_or_vector(
                guidance_tensor,
                num_rows=int(latents.shape[0]),
                field_name="guidance tensor",
            )
        )

    return _gather_tensor_rows(
        gathered_guidance,
        field_name="guidance",
        out=out,
    )


def _prepare_image_latents(
    states: Sequence[StepRequestState],
    *,
    out: torch.Tensor | None = None,
) -> torch.Tensor | None:
    image_latents = [getattr(state.sampling, "image_latent", None) for state in states]
    if all(image_latent is None for image_latent in image_latents):
        return None
    if any(image_latent is None for image_latent in image_latents):
        raise ValueError("Mixed image_latent presence in one diffusion batch is not supported.")
    return _gather_tensor_rows(
        [image_latent for image_latent in image_latents if image_latent is not None],
        field_name="image_latents",
        out=out,
    )


def _prepare_seq_lens(
    states: Sequence[StepRequestState],
    attr_name: str,
) -> list[int] | None:
    values = [getattr(state, attr_name) for state in states]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError(f"Mixed {attr_name} in batch.")
    return [int(value[0]) for value in values if value is not None]


def _prepare_img_shapes(states: Sequence[StepRequestState]) -> list | None:
    values = [state.img_shapes for state in states]
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError("Mixed img_shapes in batch.")
    return [value[0] if value else [] for value in values if value is not None]


def _prepare_prompt_embeds(
    states: Sequence[StepRequestState],
    *,
    embeds_out: torch.Tensor | None = None,
    mask_out: torch.Tensor | None = None,
) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    prompt_embeds, prompt_embeds_mask = _prepare_padded_prompt_fields(
        states,
        embeds_attr="prompt_embeds",
        mask_attr="prompt_embeds_mask",
        seq_lens_attr="txt_seq_lens",
        embeds_out=embeds_out,
        mask_out=mask_out,
    )
    return prompt_embeds, prompt_embeds_mask


def _prepare_negative_prompt_embeds(
    states: Sequence[StepRequestState],
    *,
    embeds_out: torch.Tensor | None = None,
    mask_out: torch.Tensor | None = None,
) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    return _prepare_padded_prompt_fields(
        states,
        embeds_attr="negative_prompt_embeds",
        mask_attr="negative_prompt_embeds_mask",
        seq_lens_attr="negative_txt_seq_lens",
        embeds_out=embeds_out,
        mask_out=mask_out,
    )


def _same_composition(
    cached_batch: InputBatch | None,
    request_ids: list[str],
    idx_mapping_np: np.ndarray,
    states: Sequence[StepRequestState],
) -> bool:
    if cached_batch is None:
        return False
    if cached_batch.request_ids != request_ids:
        return False
    if not np.array_equal(cached_batch.idx_mapping_np, idx_mapping_np):
        return False
    # Midway prompt updates (typically for video generation) can change prompt_embeds without changing ids/mapping.
    # In this case, each request state manages the embedding's "version". Use it to determine if cache is still valid.
    return cached_batch._prompt_update_versions == prompt_update_versions(states)


def _scatter_batch_tensor_by_mapping(
    states: Sequence[StepRequestState],
    idx_mapping_np: np.ndarray,
    *,
    attr_name: str,
    value: torch.Tensor,
) -> None:
    row_offset = 0
    for batch_idx, state_idx in enumerate(idx_mapping_np.tolist()):
        if state_idx < 0 or state_idx >= len(states):
            raise ValueError(f"idx_mapping[{batch_idx}]={state_idx} is out of range for states.")
        state = states[state_idx]
        state_value = getattr(state, attr_name)
        num_rows = 1 if state_value is None else int(state_value.shape[0])
        next_row_offset = row_offset + num_rows
        value_slice = value[row_offset:next_row_offset]
        if state_value is None:
            setattr(state, attr_name, value_slice.clone())
        elif (
            tuple(state_value.shape) != tuple(value_slice.shape)
            or state_value.dtype != value_slice.dtype
            or state_value.device != value_slice.device
        ):
            setattr(state, attr_name, value_slice.clone())
        else:
            state_value.copy_(value_slice)
        row_offset = next_row_offset

    if row_offset != int(value.shape[0]):
        raise ValueError(
            f"Scatter for {attr_name} consumed {row_offset} rows, but batch has {int(value.shape[0])} rows."
        )


@dataclass
class InputBatch:
    """Ephemeral step-level batch view.

    Static request-local tensors are normalized and padded onto
    ``StepRequestState`` itself, making the request state the persistent
    source of truth. ``InputBatch`` only assembles a contiguous view for the
    current step and refreshes dynamic fields in-place when composition is
    unchanged.

    ``states`` is a narrow escape hatch for Hunyuan-style state-driven
    pipelines that need request-private KV/cache metadata during denoise.
    Other pipelines should continue to use the standard batch fields.
    """

    request_ids: list[str]
    num_reqs: int
    num_reqs_after_padding: int
    idx_mapping: torch.Tensor
    idx_mapping_np: np.ndarray

    latents: torch.Tensor
    timesteps: torch.Tensor
    prompt_embeds: torch.Tensor | None
    prompt_embeds_mask: torch.Tensor | None
    negative_prompt_embeds: torch.Tensor | None
    negative_prompt_embeds_mask: torch.Tensor | None
    guidance: torch.Tensor | None = None
    do_true_cfg: bool = False
    true_cfg_scale: float = 4.0
    cfg_normalize: bool = False
    image_latents: torch.Tensor | None = None

    img_shapes: list | None = None
    txt_seq_lens: list[int] | None = None
    negative_txt_seq_lens: list[int] | None = None
    states: Sequence[StepRequestState] = field(default_factory=tuple)

    # For midway prompt updates (typically for video generation) that changes embeddings without changing ids,
    # Keep a snapshot of the current per-request versions of prompt embeddings for later runtime comparison
    _prompt_update_versions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if len(self.request_ids) != int(self.idx_mapping.numel()):
            raise ValueError("`request_ids` and `idx_mapping` must have the same length.")
        if self.num_reqs != len(self.request_ids):
            raise ValueError("`num_reqs` must match the number of request ids.")
        if self.num_reqs_after_padding < self.num_reqs:
            raise ValueError("`num_reqs_after_padding` must be >= `num_reqs`.")

    def _refresh_dynamic_fields(
        self,
        selected_states: Sequence[StepRequestState],
    ) -> None:
        self.latents = _prepare_latents(selected_states, out=self.latents)
        self.timesteps = _prepare_timesteps(selected_states, out=self.timesteps)

    def _refresh_static_fields(
        self,
        states: Sequence[StepRequestState],
    ) -> None:
        self.do_true_cfg, self.true_cfg_scale, self.cfg_normalize = _prepare_cfg_scalars(states)
        self.guidance = _prepare_guidance(states, out=self.guidance)
        self.image_latents = _prepare_image_latents(states, out=self.image_latents)
        self.prompt_embeds, self.prompt_embeds_mask = _prepare_prompt_embeds(
            states,
            embeds_out=self.prompt_embeds,
            mask_out=self.prompt_embeds_mask,
        )
        (
            self.negative_prompt_embeds,
            self.negative_prompt_embeds_mask,
        ) = _prepare_negative_prompt_embeds(
            states,
            embeds_out=self.negative_prompt_embeds,
            mask_out=self.negative_prompt_embeds_mask,
        )
        self.img_shapes = _prepare_img_shapes(states)
        self.txt_seq_lens = _prepare_seq_lens(states, "txt_seq_lens")
        self.negative_txt_seq_lens = _prepare_seq_lens(states, "negative_txt_seq_lens")
        self._prompt_update_versions = prompt_update_versions(states)

    def _repack_dynamic_fields(
        self,
        selected_states: Sequence[StepRequestState],
    ) -> None:
        # Same-composition cache hits reuse static prompt fields; request ids
        # must keep the same encoded prompt metadata for the batch lifetime.
        self.states = tuple(selected_states)
        self._refresh_dynamic_fields(selected_states)

    def _rebuild(
        self,
        selected_states: Sequence[StepRequestState],
        idx_mapping: torch.Tensor,
        idx_mapping_np: np.ndarray,
        request_ids: list[str],
    ) -> InputBatch:
        self.request_ids = request_ids
        self.num_reqs = len(request_ids)
        self.num_reqs_after_padding = len(request_ids)
        self.idx_mapping = idx_mapping
        self.idx_mapping_np = idx_mapping_np
        self.states = tuple(selected_states)
        self.latents = _prepare_latents(selected_states, out=self.latents)
        self.timesteps = _prepare_timesteps(selected_states, out=self.timesteps)
        self._refresh_static_fields(selected_states)
        self.__post_init__()
        return self

    @classmethod
    def make_batch(
        cls,
        states: Sequence[StepRequestState],
        idx_mapping: torch.Tensor | None = None,
        cached_batch: InputBatch | None = None,
    ) -> InputBatch:
        """Build a temporary step-local batch view from request states."""
        selected_states, idx_mapping, idx_mapping_np = _select_states(states, idx_mapping)
        request_ids = _prepare_request_ids(selected_states)

        if _same_composition(cached_batch, request_ids, idx_mapping_np, selected_states):
            assert cached_batch is not None
            cached_batch._repack_dynamic_fields(selected_states)
            return cached_batch

        if cached_batch is not None:
            return cached_batch._rebuild(
                selected_states,
                idx_mapping,
                idx_mapping_np,
                request_ids,
            )

        prompt_embeds, prompt_embeds_mask = _prepare_prompt_embeds(selected_states)
        negative_prompt_embeds, negative_prompt_embeds_mask = _prepare_negative_prompt_embeds(selected_states)
        do_true_cfg, true_cfg_scale, cfg_normalize = _prepare_cfg_scalars(selected_states)
        return cls(
            request_ids=request_ids,
            num_reqs=len(selected_states),
            num_reqs_after_padding=len(selected_states),
            idx_mapping=idx_mapping,
            idx_mapping_np=idx_mapping_np,
            latents=_prepare_latents(selected_states),
            timesteps=_prepare_timesteps(selected_states),
            guidance=_prepare_guidance(selected_states),
            do_true_cfg=do_true_cfg,
            true_cfg_scale=true_cfg_scale,
            cfg_normalize=cfg_normalize,
            image_latents=_prepare_image_latents(selected_states),
            prompt_embeds=prompt_embeds,
            prompt_embeds_mask=prompt_embeds_mask,
            negative_prompt_embeds=negative_prompt_embeds,
            negative_prompt_embeds_mask=negative_prompt_embeds_mask,
            img_shapes=_prepare_img_shapes(selected_states),
            txt_seq_lens=_prepare_seq_lens(selected_states, "txt_seq_lens"),
            negative_txt_seq_lens=_prepare_seq_lens(
                selected_states,
                "negative_txt_seq_lens",
            ),
            states=tuple(selected_states),
            _prompt_update_versions=prompt_update_versions(selected_states),
        )


def scatter_latents(
    states: Sequence[StepRequestState],
    input_batch: InputBatch,
) -> None:
    """Scatter the step-updated latents back into persistent request states.

    This is the CPU fallback of the vLLM-style post-update path. The mapping is
    driven entirely by ``input_batch.idx_mapping_np`` so the runner remains free
    to keep request states in its own persistent storage layout.
    """
    _scatter_batch_tensor_by_mapping(
        states,
        input_batch.idx_mapping_np,
        attr_name="latents",
        value=input_batch.latents,
    )


# Alias: InputBatch is the step/tensor-level batch.
# DiffusionRequestBatch (in request_batch.py) is the request-level batch.
StepInputBatch = InputBatch
DiffusionInputBatch = StepInputBatch

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/tests/diffusion/models/taomate_h3/test_taomate_h3_cuda_graph.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""CPU tests of the TaoMate-H3 CUDA-graph helpers (no device needed)."""

from __future__ import annotations

import pytest
import torch
import torch.nn as nn

from vllm_omni.diffusion.models.minimax_h3.denoise_loop import MiniMaxH3DenoiseBranch
from vllm_omni.diffusion.models.taomate_h3.audio_teacher import (
    TEACHER_SLOT_REFERENCE,
    TEACHER_SLOT_TARGET,
    TEACHER_SLOT_TEXT,
    attach_teacher_timestep_slots,
    teacher_forward_kwargs,
)
from vllm_omni.diffusion.models.taomate_h3.cuda_graph import (
    GraphedForward,
    clone_static,
    copy_into,
    kwargs_signature,
)
from vllm_omni.diffusion.models.taomate_h3.packed import (
    taomate_audio_only_frozen_prefix_packed_layout,
    taomate_audio_only_packed_layout,
)
from vllm_omni.diffusion.models.taomate_h3.transformer import LocalEmbedPlan, local_embed_plan


def test_signature_counts_tensors_by_shape_and_values_by_value() -> None:
    a = {"x": torch.zeros(3, 4), "meta": {"n": 1, "flag": True}, "seq": (1, 2)}
    b = {"x": torch.ones(3, 4), "meta": {"n": 1, "flag": True}, "seq": (1, 2)}
    c = {"x": torch.zeros(3, 5), "meta": {"n": 1, "flag": True}, "seq": (1, 2)}
    d = {"x": torch.zeros(3, 4), "meta": {"n": 2, "flag": True}, "seq": (1, 2)}
    assert kwargs_signature(a) == kwargs_signature(b)
    assert kwargs_signature(a) != kwargs_signature(c)
    assert kwargs_signature(a) != kwargs_signature(d)
    assert kwargs_signature(torch.zeros(2, dtype=torch.float32)) != kwargs_signature(
        torch.zeros(2, dtype=torch.bfloat16)
    )
    hash(kwargs_signature(a))


def test_clone_static_and_copy_into_follow_the_tree() -> None:
    live = {"x": torch.arange(6.0).view(2, 3), "inner": {"pos": torch.tensor([1, 2])}, "n": 4, "t": (torch.ones(2),)}
    static = clone_static(live)
    assert static["x"].data_ptr() != live["x"].data_ptr()
    assert torch.equal(static["x"], live["x"]) and static["n"] == 4
    live["x"].fill_(7.0)
    live["inner"]["pos"].fill_(9)
    assert copy_into(static, live) == 3
    assert torch.equal(static["x"], torch.full((2, 3), 7.0))
    assert torch.equal(static["inner"]["pos"], torch.tensor([9, 9]))
    with pytest.raises(ValueError):
        copy_into(static, {**live, "x": torch.zeros(3, 2)})
    with pytest.raises(ValueError):
        copy_into(static, {**live, "extra": 1})


class _Doubler(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def forward(self, *, x: torch.Tensor, scale: float) -> tuple[torch.Tensor, torch.Tensor]:
        self.calls += 1
        return x * scale, x + scale


def test_graphed_forward_runs_eagerly_without_cuda() -> None:
    module = _Doubler()
    graphed = GraphedForward(module, device=torch.device("cpu"), name="test")
    assert not graphed.enabled
    out, other = graphed(variant="v", x=torch.ones(2), scale=3.0)
    assert torch.equal(out, torch.full((2,), 3.0)) and torch.equal(other, torch.full((2,), 4.0))
    assert module.calls == 1 and graphed.stats()["eager_calls"] == 1 and graphed.num_graphs == 0
    with pytest.raises(ValueError):
        GraphedForward(module, device=torch.device("cpu"), max_entries=0)


def _upstream_local_selection(img, audio, text, local_start, local_len):
    local_end = local_start + local_len
    img_mask = (img >= local_start) & (img < local_end)
    audio_mask = (audio >= local_start) & (audio < local_end)
    text_mask = (text >= local_start) & (text < local_end)
    return (
        img[img_mask],
        audio[audio_mask],
        img[img_mask] - local_start,
        audio[audio_mask] - local_start,
        text[text_mask] - local_start,
        torch.nonzero(text_mask, as_tuple=False).view(-1),
    )


def test_local_embed_plan_matches_the_upstream_mask_logic() -> None:
    text = torch.arange(0, 9)
    audio = torch.arange(9, 9 + 80)
    img = torch.arange(89, 89 + 30)
    seq_len = 128
    for local_start, local_len in ((0, 64), (64, 64), (32, 32)):
        plan = LocalEmbedPlan.build(
            img_pos=img,
            audio_pos=audio,
            text_pos=text,
            seq_len=seq_len,
            local_span=(local_start, local_len),
            device=torch.device("cpu"),
        )
        expected = _upstream_local_selection(img, audio, text, local_start, local_len)
        assert torch.equal(plan.img_global_pos, expected[0])
        assert torch.equal(plan.audio_global_pos, expected[1])
        assert torch.equal(plan.img_local_pos, expected[2])
        assert torch.equal(plan.audio_local_pos, expected[3])
        assert torch.equal(plan.text_local_pos, expected[4])
        assert plan.text_local_indices is not None and torch.equal(plan.text_local_indices, expected[5])
        assert plan.fingerprint == (seq_len, local_start, local_len, 30, 80, 9)
    full = LocalEmbedPlan.build(
        img_pos=img,
        audio_pos=audio,
        text_pos=text,
        seq_len=seq_len,
        local_span=(0, seq_len),
        device=torch.device("cpu"),
    )
    assert full.text_local_indices is None and torch.equal(full.img_local_pos, img)
    with local_embed_plan(full):
        from vllm_omni.diffusion.models.taomate_h3.transformer import _LOCAL_EMBED_PLAN

        assert _LOCAL_EMBED_PLAN.get() is full
    assert _LOCAL_EMBED_PLAN.get() is None


def _teacher_branch(*, with_reference: bool, seq_len: int | None = None) -> MiniMaxH3DenoiseBranch:
    text_len = 9
    if with_reference:
        packed = taomate_audio_only_frozen_prefix_packed_layout(
            text_len=text_len,
            ref_audio_t=40,
            audio_t=198,
            latent_h=54,
            latent_w=30,
            reference_time_start=text_len + 207 - 40,
            target_time_start=text_len + 207,
            seq_len=seq_len,
        )
    else:
        packed = taomate_audio_only_packed_layout(
            text_len=text_len, audio_t=207, latent_h=54, latent_w=30, seq_len=seq_len
        )
    tags = packed["token_tags"].clone()
    return MiniMaxH3DenoiseBranch(
        packed=packed,
        text_embeddings=torch.zeros(text_len, 5120),
        token_tags=tags,
        device=torch.device("cpu"),
    )


@pytest.mark.parametrize("with_reference", [False, True])
@pytest.mark.parametrize("pinned", [False, True])
def test_teacher_fixed_slot_timesteps_match_the_branch_fill(with_reference: bool, pinned: bool) -> None:
    branch = _teacher_branch(with_reference=with_reference, seq_len=640 if pinned else None)
    inverse = attach_teacher_timestep_slots(branch)
    assert inverse.shape == (branch.seq_len,)
    audio_rows = torch.randn(int(branch.audio_pos.numel()), 32)
    video_rows = torch.empty(0, 96)
    for t_video, t_audio in ((0.0, 0.0), (0.2, 0.5), (1.0, 1.0)):
        kwargs = teacher_forward_kwargs(
            branch, video_rows=video_rows, audio_rows=audio_rows, t_video=t_video, t_audio=t_audio
        )
        assert kwargs["unique_timesteps"].shape == (3,)
        per_row = kwargs["unique_timesteps"][kwargs["inverse_indices"]]
        expected = torch.empty(branch.seq_len)
        branch.fill_timesteps(
            expected, t_video=t_video, t_audio=t_audio, imgvid_cond_timestep=t_video, audio_ref_cond_timestep=1.0
        )
        assert torch.equal(per_row, expected)
        reference = branch.forward_kwargs(
            video_rows=video_rows,
            audio_rows=audio_rows,
            t_video=t_video,
            t_audio=t_audio,
            imgvid_cond_timestep=t_video,
            audio_ref_cond_timestep=1.0,
        )
        assert torch.equal(kwargs["audio_x"], reference["audio_x"]) and torch.equal(kwargs["x"], reference["x"])
        assert torch.equal(reference["unique_timesteps"][reference["inverse_indices"]], per_row)
    slots = set(inverse.tolist())
    assert TEACHER_SLOT_TEXT in slots and TEACHER_SLOT_TARGET in slots
    assert (TEACHER_SLOT_REFERENCE in slots) == with_reference
    # Graph identity: the same document shape gives the same signature whatever the values.
    first = teacher_forward_kwargs(branch, video_rows=video_rows, audio_rows=audio_rows, t_video=0.1, t_audio=0.2)
    second = teacher_forward_kwargs(branch, video_rows=video_rows, audio_rows=audio_rows * 2, t_video=0.7, t_audio=0.9)
    assert kwargs_signature(first) == kwargs_signature(second)


def test_vae_tile_values_are_multiples_of_16() -> None:
    from vllm_omni.diffusion.models.taomate_h3.pipeline import validate_vae_tile_value

    assert validate_vae_tile_value(None, "x", minimum=16) is None
    assert validate_vae_tile_value(480, "x", minimum=16) == 480
    assert validate_vae_tile_value(0, "x", minimum=0) == 0
    for bad in (True, 15, 100, -16, 8.0):
        with pytest.raises(ValueError):
            validate_vae_tile_value(bad, "x", minimum=16)


def test_graphed_forward_keeps_keep_alive_objects_on_cpu_passthrough() -> None:
    module = _Doubler()
    graphed = GraphedForward(module, device=torch.device("cpu"))
    plan = object()
    graphed(variant="v", keep_alive=(plan,), x=torch.ones(1), scale=1.0)
    assert graphed.num_graphs == 0  # eager on CPU; the argument is accepted

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/deploy/taomate_h3_usp2_realtime.yaml =====
# TaoMate-H3 streaming on two GPUs: pure Ulysses sequence parallel (USP2),
# tensor parallel 1, AR-Diffusion stepwise engine, streaming output, FP8
# online linears and CUDA-graph replay of the audio teacher.
#
# Serve (under a GPU reservation on the shared machine):
#
#   gpu run --gpus 2 --timeout 4h --note "taomate-h3 usp2" -- \
#     vllm serve /path/to/MiniMax-H3/FL2VA --omni --trust-remote-code \
#       --deploy-config vllm_omni/deploy/taomate_h3_usp2_realtime.yaml \
#       --lora-path /path/to/TaoMate-H3 --port 8000
#
# Status (see recipes/TaoLiveAIGC/TaoMate-H3.md, "Two GPUs"): eager BF16 at
# USP2 measures 6.3 s of wall time per 4.958 s request at 480x864 on two
# H200-class GPUs (real-time factor 1.27), i.e. not real time. This config
# turns on the two levers that do not change the generated content, FP8
# linears and teacher CUDA graphs; their combined effect on two GPUs is not
# measured yet (the four-GPU recipe stays the real-time deployment).

pipeline: taomate_h3
async_chunk: false
distributed_executor_backend: mp
dtype: bfloat16

stages:
  - stage_id: 0
    devices: "0,1"
    max_num_seqs: 1
    enforce_eager: true
    # Online FP8 weights and activations for the DiT linears (the LoRA hooks
    # add their BF16 delta on top; the teacher shares the same weights).
    quantization: fp8
    model_class_name: TaoMateH3Pipeline
    engine_backend: vllm_omni.experimental.ar_diffusion.engine.ARDiffusionEngine
    step_execution: true
    streaming_output: true
    parallel_config:
      tensor_parallel_size: 1
      sequence_parallel_size: 2
      ulysses_degree: 2
      ring_degree: 1
      text_encoder_tp_size: 2
      vae_patch_parallel_size: 2
      vae_parallel_mode: tile
    default_sampling_params:
      num_inference_steps: 3
      output_type: np
      fps: 24
    model_config:
      taomate_h3_width: 480
      taomate_h3_height: 864
      taomate_h3_seed: 8301
      taomate_h3_audio_kv_reset_requests: 12
      # One packed length per document kind (prompts up to 256 tokens), so
      # the teacher's graphs are keyed by prompt length only.
      taomate_h3_pad_text_tokens: 256
      # Replay the audio teacher's nine forwards from CUDA graphs (one graph
      # per document shape, LRU of taomate_h3_cuda_graph_max_entries).
      taomate_h3_teacher_cuda_graph: true
      # Capture the teacher graphs of prompts with 8-96 tokens during the
      # load-time warmup (3 shapes per token count, about 0.5 s each), so a
      # prompt update never captures inside the stream. Other lengths are
      # captured lazily at the request that first needs them.
      taomate_h3_teacher_graph_text_lengths: "8-96"
      taomate_h3_cuda_graph_max_entries: 320
      # One 480x480 decoder tile per column pair (2 tiles = the 2 tile ranks) instead
      # of the checkpoint's 3x5 grid of 256 px tiles that covers 2.4x the canvas.
      taomate_h3_vae_decoder_tile_size: 480
      ar_diffusion_kv_config:
        gpu_memory_fraction: 0.02
        warmup_cudagraph: true

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/recipes/TaoLiveAIGC/TaoMate-H3.md =====
# TaoMate-H3: realtime streaming MiniMax-H3 with the TaoMate LoRA

TaoMate-H3 ([TaoLiveAIGC/TaoMate-H3](https://huggingface.co/TaoLiveAIGC/TaoMate-H3)) is a
rank-128 LoRA over [MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) that turns the
bidirectional five-second text-to-video-and-audio model into a causal live streamer: a
presenter that keeps talking and acting while the prompt of each next five-second request
is chosen just in time. vLLM-Omni hosts it on the AR-Diffusion realtime runtime with pure
Ulysses sequence parallelism.

## How it works

Each five-second request (124 native frames for the first request, 119 afterwards, at
24 fps with 32 kHz stereo audio) is generated as four causal phases of 34/34/34/17 frames:

| Step | What runs | Where |
| --- | --- | --- |
| Prompt | Qwen3-VL text encoder (tensor parallel across the Ulysses ranks) | at session start and whenever the client updates the prompt |
| Audio teacher | base MiniMax-H3 (LoRA disabled), nine audio-only forwards over `[text \| 1 s clean reference tail \| new audio]` | once per request, before its first phase |
| Phase denoise | three LoRA forwards of the phase document `[text \| audio \| video]`, attending to text, the persistent clean audio/video KV of earlier phases and the current chunk | per phase |
| Clean commit | one sigma-zero forward that recomputes the phase's K/V from its clean latents and appends them to the KV history (first-phase video sink + two most recent phases; audio history dropped every twelve requests) | per phase |
| Decode | tile-parallel temporal-window video VAE decode plus sliding-window audio VAE decode | per phase, streamed as one fragmented-MP4 chunk with an AAC track |

The LoRA is never merged: the same resident BF16 weights serve the LoRA student and the
LoRA-free audio teacher, so one 62 GB DiT copy per rank is enough. TP is fixed at 1; the
attention heads are split across the Ulysses ranks and each rank keeps the clean KV
history of its own head shard.

## Requirements

- 4 GPUs with at least 96 GB each (measured 85 GB per rank at 480x864 after load: DiT
  62 GB, text encoder TP4 16 GB, VAEs, LoRA 1.2 GB, model-owned session state 12.6 GB).
- Hopper or newer (`fa3_fwd_interface` / FlashAttention-3 dense kernels; FA4 on Blackwell).
- The MiniMax-H3 snapshot (`FL2VA/` partition) and the TaoMate-H3 adapter directory
  (`adapter_model.safetensors` + `config.json`).

## Serve

```bash
vllm serve /path/to/MiniMax-H3/FL2VA --omni --trust-remote-code \
  --deploy-config vllm_omni/deploy/taomate_h3_usp4_realtime.yaml \
  --lora-path /path/to/TaoMate-H3 --port 8000
```

`--model` must point at the `FL2VA/` partition directory (the snapshot root carries the
Diffusers modular index and is resolved as the FastH3 modular checkpoint). The deploy
config pins `tensor_parallel_size: 1`, `ulysses_degree: 4`, `text_encoder_tp_size: 4`,
`vae_patch_parallel_size: 4`, the AR-Diffusion engine, step execution and streaming output.
Per-deployment knobs live under `model_config`:

| Key | Default | Meaning |
| --- | --- | --- |
| `taomate_h3_width` / `taomate_h3_height` | 480 / 864 | The fixed session canvas (32-aligned, short edge 480, 768 or 1088) |
| `taomate_h3_seed` | 8301 | Default seed; request `k` draws audio noise from `seed + k` and video noise from `seed + k * 1000003` |
| `taomate_h3_audio_kv_reset_requests` | 12 | Drop the audio KV history every N requests (video sink and recents are kept) |
| `taomate_h3_allow_no_lora` | false | Stream the base H3 without the adapter (debugging only) |
| `taomate_h3_pad_text_tokens` | unset | Prompt token budget that pins every phase and teacher document to one packed length per kind (for compiled or CUDA-graph runs) |
| `taomate_h3_log_timings` | false | Log per-phase stage timings (adds device synchronizations) |
| `taomate_h3_hold_for_prompt` | false | Just-in-time lock: request `k >= 1` starts only after a `session.interaction` prompt update arrived since request `k-1` started; until then the stream idles at the request boundary (send `session.ping` to keep the stall timer fresh). For clients that choose every request's prompt at the last moment |
| `taomate_h3_hold_poll_seconds` | 0.02 | Idle-step period while a request boundary is held |
| `taomate_h3_teacher_cuda_graph` | false | Replay the audio teacher's nine forwards from CUDA graphs, one graph per document shape (prompt length, first or later request, reference tail or not). The first capture is checked with `torch.cuda.set_sync_debug_mode("error")`; any capture failure falls back to eager for the rest of the process, agreed across the Ulysses group |
| `taomate_h3_cuda_graph_max_entries` | 16 | Resident teacher graphs (least recently used shape evicted); they share one memory pool |
| `taomate_h3_warmup_requests` | 4 | Requests of the load-time warmup session. Later requests cycle through three audio latent counts (198, 198, 199 per channel), so four requests visit every teacher document shape: the graphs are captured and every phase size has been allocated before the first client connects |
| `taomate_h3_teacher_graph_text_lengths` | unset | Prompt token counts (`"lo-hi"`) whose teacher graphs are captured during the load-time warmup, three document shapes per count (about 0.5 s and 5 MB each). A teacher graph is keyed by the prompt's token count, so without this each new prompt length captures inside the stream (about 0.7 s per shape). Needs `taomate_h3_pad_text_tokens` and enough `taomate_h3_cuda_graph_max_entries` |
| `taomate_h3_vae_decoder_tile_size` | unset (checkpoint: 256) | Decoder tile edge of the video VAE in pixels (multiple of 16). At 480x864 the checkpoint's 256 px tiles form a 3x5 grid covering 2.4x the canvas; 480 gives two 480x480 tiles (1.1x the canvas), one per tile rank at USP2. Fewer tiles than `vae_patch_parallel_size` falls back to the slower whole-frame decode (a warning is logged) |
| `taomate_h3_vae_decoder_tile_overlap_min` | unset (checkpoint: 64) | Minimum overlap between decoder tiles in pixels (multiple of 16) |

The deploy config keeps `ar_diffusion_kv_config.warmup_cudagraph: true`: the AR runner runs
one throwaway five-second request at load time (the pipeline opts into this warmup in eager
mode as well), so the first chunk of a session arrives in about 3 s instead of 17-20 s on
a cold server.

## Stream

Open `WS /v1/realtime/video`, send `session.start` with the prompt, `width`, `height`,
`fps: 24`, `seed` and `num_frames` (the frame budget decides how many five-second
requests the session runs; `124 + 119 * (n - 1)` frames is `n` requests), and receive one
binary fragmented-MP4 chunk per phase. The bundled client works unchanged:

```bash
python examples/online_serving/streaming_video_generation/streaming_video_client.py \
  --port 8000 --model /path/to/MiniMax-H3/FL2VA --size 480x864 --fps 24 --num-frames 362 \
  --seed 8301 --no-helios-distilled-preset --prompt "..." \
  --prompt-updates '[{"at": 6.0, "prompt": "..."}]'
```

A `session.interaction` prompt update is applied at the next chunk boundary and takes
effect for the *next five-second request* (the audio teacher and all four phases of a
request share one prompt), which is TaoMate's just-in-time prompt lock. Every chunk's
`video.chunk_metadata` carries `num_frames`, `num_audio_samples` and `audio_sample_rate`;
the stream has an H.264 video track and an AAC audio track. Chunk 1 of a session is
39 frames of latents but 34 frames of pixels: the decoder holds the last five frames of
each temporal window until the next phase, and flushes them with the final chunk.

## Measured (4x H200-class 141 GB, eager BF16, 480x864)

Steady-state chunk period after the cold start, one session, measured locally:

| Chunk | Frames | Period |
| --- | --- | --- |
| phase 0 of a request (includes the teacher's nine forwards and, after a prompt update, the text encode) | 34 | 1.7-2.3 s |
| phases 1-2 | 34 | 0.85-0.95 s |
| phase 3 | 17 | 0.7-0.85 s |

A 13-request session (1552 frames, 64.6 s of video and audio) took 3.9-4.1 s of wall time
per 4.958 s request in steady state (real-time factor 0.78-0.82); the first chunk arrived
after 2.3-2.9 s with the load-time warmup. Stage timings per 34-frame phase
(`model_config.taomate_h3_log_timings: true`): teacher 0.7-0.8 s per request, three student
forwards 0.42 s, clean commit 0.15 s, video decode 0.2 s, audio decode 0.03 s. Regional
`torch.compile` (`enforce_eager: false`, `VLLM_OMNI_TORCH_DYNAMO_RECOMPILE_LIMIT=64`) and
FP8 online linears (`quantization: fp8`) gave no steady-state gain over eager here (4.3 s per
request); the launch-bound teacher forwards and the per-phase VAE decode are the next targets.

## Two GPUs (USP2): `vllm_omni/deploy/taomate_h3_usp2_realtime.yaml`

The two-GPU config keeps TP=1 and splits the heads across two Ulysses ranks
(`sequence_parallel_size: 2`, `text_encoder_tp_size: 2`, `vae_patch_parallel_size: 2`).
Memory per rank in eager BF16 is 100.7 GB after load (measured locally). Eager BF16 is
**not** real time on two H200-class GPUs at 480x864 (measured locally, 2026-09-28, five
requests, constant prompt, `taomate_h3_log_timings: true`, rank 0):

| Stage | 34-frame phase | 17-frame phase |
| --- | --- | --- |
| audio teacher (once per request, 9 forwards) | 0.78-0.84 s | - |
| 3 student forwards | 0.77-0.81 s | 0.43 s |
| clean-commit forward + cache append | 0.29-0.32 s | 0.16 s |
| tile-parallel video VAE decode | 0.35-0.37 s | 0.18 s |
| audio VAE decode | 0.03 s | 0.03 s |

Per request: 2.29 + 1.55 + 1.59 + 0.86 = 6.3 s of wall time for 4.958 s of content
(real-time factor 1.27; the client saw 6.4 s between request starts). Against the USP4
breakdown the DiT forwards take 1.9x longer per rank (2200 instead of 1100 rows through the
linears, twice the heads in attention), the VAE decode 1.8x, and the launch-bound teacher
is unchanged.

The two-GPU deploy config therefore enables the levers that leave the generated content
unchanged, plus a decoder tiling that only changes how the VAE is split across the ranks:

- `quantization: fp8` for the DiT linears (the GEMMs are about 60% of a student forward at
  USP2, estimate from parameter and row counts);
- `taomate_h3_teacher_cuda_graph` (the teacher's forwards run a few hundred rows and are
  launch-bound at about 85-90 ms each; a replay takes 38 ms);
- `taomate_h3_vae_decoder_tile_size: 480` (two 480x480 tiles, one per rank, instead of the
  checkpoint's 3x5 grid of 256 px tiles that decodes 2.4x the canvas);
- `taomate_h3_pad_text_tokens: 256` so every document kind has one packed length, and
  `taomate_h3_teacher_graph_text_lengths: "8-96"` so the graphs of every plausible prompt
  length exist before the first client connects.

Measured locally (2026-09-28, 480x864, two H200-class GPUs, five requests, constant prompt
of 32 tokens, `taomate_h3_log_timings: true`, rank 0; the warmup already holds the graphs):

| Stage | 34-frame phase | 17-frame phase |
| --- | --- | --- |
| audio teacher (once per request, 9 graph replays) | 0.35 s | - |
| 3 student forwards (FP8) | 0.67-0.70 s | 0.42-0.45 s |
| clean-commit forward + cache append | 0.24-0.26 s | 0.15-0.17 s |
| tile-parallel video VAE decode (2 x 480 px tiles) | 0.21-0.22 s | 0.10 s |
| audio VAE decode | 0.03 s | 0.03 s |
| phase preparation (packing, RoPE table) | 0.01-0.03 s | 0.00 s |

Per request the phases take 1.51 + 1.19 + 1.24 + 0.76 = 4.70 s of GPU time, and the wall
time between the ends of consecutive requests (phases plus the runner's output handling) is
4.91-4.97 s for 4.958 s of content: real-time factor 0.99-1.00, against 1.27 for eager BF16.
The client saw 4.92-4.95 s between the first chunks of consecutive requests. This is real
time with no headroom: a playback buffer of about one second is needed, and the two events
below each stall the stream once.

- **A prompt length without a resident graph** captures the teacher graphs of that length
  inside the stream: about 0.7 s per shape (three shapes for a session's first prompt, two
  per later prompt update), plus one or two slow commits (0.5-0.9 s) right after a capture
  while the allocator regrows. Measured without the length range: a session start cost
  2.1 s before the first chunk, and each prompt update with a new token count stretched
  the next request by 2-3 s. With `taomate_h3_teacher_graph_text_lengths` covering the
  prompt's token count nothing is captured live.
- **A prompt update** re-encodes the text on the workers (Qwen3-VL at TP2): 0.13-0.20 s
  for 21-32 tokens, inside the phase in which the update arrives (measured locally).

Teacher graphs are keyed by the prompt's token count because the H3 attention treats the
document's valid rows as a prefix whose length is a Python int of the forward (a fixed
text length would need extra rows inside that prefix, which changes the attention), so
the graphs of a length range are captured up front instead. Reusing the last denoise
step's K/V instead of the clean-commit forward (the LingBot-World `reuse_last_step_kv`
pattern) is not offered: TaoMate's last student forward runs at sigma 0.853 of the shift-12
schedule (the ladder is 1.0, 0.961, 0.853, 0), far from the clean K/V the model was trained
to attend to.

## Limits

- One session per server (`max_num_seqs: 1`, `session_capacity: 1`).
- The canvas is fixed per deployment; a request with another size is rejected.
- Only text prompts (T2VA); the TaoMate release has no image or audio conditioning.
- Video is not bit-reproducible run to run (the release runtime has the same property).
