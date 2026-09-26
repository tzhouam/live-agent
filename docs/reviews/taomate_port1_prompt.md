You are GPT-6 Sol, the INDEPENDENT REVIEWER for the "live-agent" project (AGENTS.md rules: read-only; numbered findings tagged blocking/major/minor, each with evidence or the check that would settle it). Review round "taomate_port1": a port of the TaoMate-H3 streaming runtime into vLLM-Omni.

Context. TaoMate-H3 is a rank-128 LoRA over MiniMax-H3 that streams five-second T2VA requests as four causal phases (34/34/34/17 frames; 12/10/10/5 video latents for the first request, 10/10/10/5 afterwards), three denoise steps per phase at sigma indices (0,16,33,49) of the 50-step shifted schedule, conditioned on the clean (sigma=0) K/V of earlier phases (first-phase video sink + two most recent AV phases; audio dropped every 12 requests). Audio comes from the base model without the LoRA ("teacher": nine audio-only forwards per request with a 40-latent clean reference tail from the previous request); the student's audio rows are overwritten with the teacher's states 3/6/9 after each step. The reference implementation (the `taomate_h3/*` files below) runs TP2 x Ulysses2 with a separate teacher process. The port (the `vllm_omni/diffusion/models/taomate_h3/*` files below) runs pure Ulysses (TP=1) on vLLM-Omni's AR-Diffusion step-execution runtime: one phase = one streamed chunk; the LoRA is applied through switchable forward hooks so the same BF16 weights serve student and teacher; the persistent K/V is a dense model-owned cache read by a custom attention after the Ulysses all-to-all; the audio/video are decoded incrementally and streamed as fragmented MP4.

Measured locally on 4 GPUs at 480x864 (eager BF16): a 13-request session streamed 1552 frames with audio; steady state about 4.1 s of wall time per 4.958 s request. Video is not bit-reproducible in the reference runtime either, so no bitwise parity is claimed.

Please challenge specifically, quoting file:line of the inlined code:
1. Semantic parity of the streaming attention (`attention.py`) with the reference hook (`attention_hook.py`): which rows attend to what, what is staged into the cache, RoPE applied before the all-to-all and before staging, padding rows, softmax scale, the Ulysses head/sequence exchange (does each rank's cache really hold full-sequence rows of its own head shard, and are the same heads used for the history and the current chunk?).
2. Parity of the phase documents (`packed.py` vs `runtime.py` `build_streaming_phase_packed_layout`): prompt right-alignment, video/audio absolute times, the media time origin fixed at the first request's text length, request/phase offsets after the first request, token tags and the commit mask.
3. The denoise loop and the audio teacher (`pipeline.py` `denoise_step`/`step_scheduler`/`post_decode`, `audio_teacher.py` vs `runtime.py`, `denoise.py`, `teacher.py`, `base10_teacher.py`): sigma ladders, the Euler update op order, timestep assignment for text/pad/audio/reference rows, noise draw order and seeds (audio seed = seed + k; video seed = seed + k*1000003), the transport prefix handling (continuation requests drop 2 video latents and 8-9 audio latents), milestone capture (states 3/6/9), the tail-40 rollover and its RoPE times, the clean-commit forward at t=1 with renormalized video rows, cache retention after each commit, audio drop every 12 requests.
4. The LoRA (`lora.py` vs `lora_checkpoint.py`): fused-QKV row order (the port now applies lora_b unpermuted, matching the reference loader that reorders only the base weight), fc1 gate/up order, scale alpha/rank, hook placement on vLLM linears that return (out, bias), and whether disabling the adapter for the teacher forwards is complete (token refiner included).
5. Runtime integration hazards: the step runner batches `state.prompt_embeds` as [1, L, D] (squeezed at request start); the RoPE table must be built inside the forward context; sessions keyed by the runner's AR session id; the prompt interaction takes effect at the next request; `post_decode` runs the commit forward then the VAE; error handling (rollback) and session release; anything that could desynchronize ranks (rank-local exceptions, collectives inside try/except).
6. Streaming decode (`stream_decode.py`): window/overlap arithmetic versus the checkpoint's `tokens_chunk_size=5, token_overlap=2, frame_pre_padding=3, frame_overlap=5`; audio sample alignment (800 samples/latent, 1333.33 samples/frame); the end-of-session flush and tail padding.
7. Anything in the port that is not real time by construction (per-phase work, teacher placement) and the most promising optimizations given the measured 4.1 s per request.
Be concrete and concise; list checks I can run locally to settle each open question.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/attention.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""Streaming attention for TaoMate-H3.

Outside a streaming context the layer is the upstream ``MiniMaxH3Attention``
(packed varlen attention through the shared ``Attention`` layer, including its
Ulysses strategy); that path serves the audio teacher and the token refiner.

Inside a streaming context (installed by the pipeline around every student
forward) the layer implements TaoMate's causal conditioning for the live
document of the current chunk:

* condition (text) rows attend to the text rows only;
* media (audio + video) rows attend to ``[text K/V | persistent clean AV K/V | current chunk K/V]``;
* alignment-padding rows produce zeros;
* in clean-commit mode the layer additionally stages its post-all-to-all
  K/V rows of the current chunk into the session's ``CleanAVKVCache``.

Sequence parallelism is pure Ulysses: the layer performs the sequence-to-head
all-to-all itself (as LingBot-World does) so that the persistent cache holds
full-sequence rows for this rank's head shard, and gathers back before the
output projection. Attention runs as dense FlashAttention-3 (``fa3_fwd_interface``
or ``flash_attn_interface``), the same kernel family as the release; SDPA is the
CPU / no-FA fallback.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

import torch

from vllm_omni.diffusion.attention.backends.abstract import VideoTokenLayout
from vllm_omni.diffusion.distributed.comm import SeqAllToAll4D, all_to_all_5D
from vllm_omni.diffusion.layers.fused_qk_norm_rope import fused_qk_norm_rope
from vllm_omni.diffusion.models.minimax_h3.minimax_h3_transformer import MiniMaxH3Attention

from .kv_cache import CleanAVKVCache


class StreamMode(str, Enum):
    NOISY = "noisy"
    CLEAN_COMMIT = "clean_commit"


@dataclass
class StreamContext:
    """Full-sequence metadata of the live chunk document, shared by all layers."""

    cache: CleanAVKVCache
    mode: StreamMode
    # Global (full packed sequence) row indices, on the compute device.
    condition_rows: torch.Tensor
    media_rows: torch.Tensor
    token_tags: torch.Tensor
    commit_mask: torch.Tensor
    seq_len: int
    kernel_calls: int = 0


_STREAM_CONTEXT: ContextVar[StreamContext | None] = ContextVar("taomate_h3_stream_context", default=None)


def current_stream_context() -> StreamContext | None:
    return _STREAM_CONTEXT.get()


@contextmanager
def stream_context(context: StreamContext) -> Iterator[StreamContext]:
    if _STREAM_CONTEXT.get() is not None:
        raise RuntimeError("TaoMate-H3 streaming attention context is nested")
    token = _STREAM_CONTEXT.set(context)
    try:
        yield context
    finally:
        _STREAM_CONTEXT.reset(token)


def _ulysses_state() -> tuple[int, int, torch.distributed.ProcessGroup | None]:
    try:
        from vllm_omni.diffusion.distributed.parallel_state import get_sp_group

        coordinator = get_sp_group()
    except (AssertionError, ImportError, RuntimeError):
        return 1, 0, None
    return int(coordinator.ulysses_world_size), int(coordinator.ulysses_rank), coordinator.ulysses_group


def _resolve_flash_attention():
    try:
        from vllm_omni.diffusion.attention.backends.utils.fa import flash_attn_func

        return flash_attn_func
    except Exception:  # noqa: BLE001 - fall back to SDPA below
        return None


def _dense_attention(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    *,
    scale: float,
    flash_attn_func,
) -> torch.Tensor:
    """Non-causal dense attention over ``[rows, heads, head_dim]`` tensors."""
    if flash_attn_func is not None and query.is_cuda and query.dtype in (torch.bfloat16, torch.float16):
        output = flash_attn_func(
            query.unsqueeze(0),
            key.unsqueeze(0),
            value.unsqueeze(0),
            softmax_scale=scale,
            causal=False,
        )
        if isinstance(output, tuple):
            output = output[0]
        return output.squeeze(0)
    out = torch.nn.functional.scaled_dot_product_attention(
        query.transpose(0, 1).unsqueeze(0),
        key.transpose(0, 1).unsqueeze(0),
        value.transpose(0, 1).unsqueeze(0),
        scale=scale,
    )
    return out.squeeze(0).transpose(0, 1).contiguous()


class TaoMateH3StreamingAttention(MiniMaxH3Attention):
    """``MiniMaxH3Attention`` with TaoMate's persistent-KV streaming path."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Assigned by the DiT model; ``None`` keeps the layer on the base path
        # (token refiner blocks are never streamed).
        self.layer_name: str | None = None
        self.ulysses_world_size, self.ulysses_rank, self.ulysses_group = _ulysses_state()
        if self.num_heads % self.ulysses_world_size:
            raise ValueError(
                "TaoMate-H3 local attention heads must be divisible by the Ulysses degree: "
                f"heads={self.num_heads}, ulysses={self.ulysses_world_size}"
            )
        self.num_sp_heads = self.num_heads // self.ulysses_world_size
        self._flash_attn_func = _resolve_flash_attention()

    def forward(
        self,
        x: torch.Tensor,
        *,
        rope_table: torch.Tensor | None,
        cu_seqlens: torch.Tensor,
        max_seqlen: int,
        packed_total: int | None = None,
        num_requests: int = 1,
        sp_seq_lens: list[int] | None = None,
        video_layout: VideoTokenLayout | None = None,
        vsa_prefix_segments: tuple[int, ...] = (),
    ) -> torch.Tensor:
        context = _STREAM_CONTEXT.get()
        if context is None or self.layer_name is None:
            return super().forward(
                x,
                rope_table=rope_table,
                cu_seqlens=cu_seqlens,
                max_seqlen=max_seqlen,
                packed_total=packed_total,
                num_requests=num_requests,
                sp_seq_lens=sp_seq_lens,
                video_layout=video_layout,
                vsa_prefix_segments=vsa_prefix_segments,
            )
        if num_requests != 1:
            raise ValueError("TaoMate-H3 streaming attention serves one live document per forward")
        if rope_table is None:
            raise ValueError("TaoMate-H3 streaming attention requires the phase RoPE table")
        total = x.shape[0]
        qkv, _ = self.qkv_proj(x)
        q_size = self.num_heads * self.head_dim
        kv_size = self.num_kv_heads * self.head_dim
        q, k, v = qkv.split([q_size, kv_size, kv_size], dim=-1)
        q = q.view(total, self.num_heads, self.head_dim)
        k = k.view(total, self.num_kv_heads, self.head_dim)
        v = v.view(total, self.num_kv_heads, self.head_dim)
        q, k = fused_qk_norm_rope(
            q,
            k,
            self.q_norm.weight,
            self.k_norm.weight,
            rope_table,
            self.q_norm.variance_epsilon,
        )
        if self.ulysses_world_size > 1:
            # One fused sequence->head all-to-all for q/k/v:
            # (1, S/N, 3, H, D) -> (1, S, 3, H/N, D).
            stacked = all_to_all_5D(
                torch.stack((q, k, v), dim=1).unsqueeze(0),
                scatter_idx=3,
                gather_idx=1,
                group=self.ulysses_group,
            )
            q, k, v = stacked[0].unbind(1)
        out = self._streaming_attention(q, k, v, context)
        if self.ulysses_world_size > 1:
            out = SeqAllToAll4D.apply(self.ulysses_group, out.unsqueeze(0), 1, 2, False)[0]
        out = out.reshape(total, self.num_heads * self.head_dim)
        out, _ = self.out_proj(out)
        return out

    @torch.compiler.disable
    def _streaming_attention(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        v: torch.Tensor,
        context: StreamContext,
    ) -> torch.Tensor:
        """Attention of the full live document with this rank's head shard."""
        seq_len = int(q.shape[0])
        if seq_len != context.seq_len:
            raise RuntimeError(
                f"{self.layer_name}: streaming attention saw {seq_len} rows, the phase document has {context.seq_len}"
            )
        scale = float(self.softmax_scale)
        condition_rows = context.condition_rows
        media_rows = context.media_rows
        k_condition = k.index_select(0, condition_rows)
        v_condition = v.index_select(0, condition_rows)
        condition_out = _dense_attention(
            q.index_select(0, condition_rows),
            k_condition,
            v_condition,
            scale=scale,
            flash_attn_func=self._flash_attn_func,
        )
        history = context.cache.history(self.layer_name)
        k_media = k.index_select(0, media_rows)
        v_media = v.index_select(0, media_rows)
        if history is None:
            keys = torch.cat((k_condition, k_media), dim=0)
            values = torch.cat((v_condition, v_media), dim=0)
        else:
            keys = torch.cat((k_condition, history.key, k_media), dim=0)
            values = torch.cat((v_condition, history.value, v_media), dim=0)
        media_out = _dense_attention(
            q.index_select(0, media_rows),
            keys,
            values,
            scale=scale,
            flash_attn_func=self._flash_attn_func,
        )
        context.kernel_calls += 2
        out = torch.zeros_like(q)
        out.index_copy_(0, condition_rows, condition_out)
        out.index_copy_(0, media_rows, media_out)
        if context.mode is StreamMode.CLEAN_COMMIT:
            context.cache.stage(self.layer_name, k, v, context.token_tags, context.commit_mask)
        return out


__all__ = [
    "StreamContext",
    "StreamMode",
    "TaoMateH3StreamingAttention",
    "current_stream_context",
    "stream_context",
]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/kv_cache.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""Persistent clean audio/video KV cache for TaoMate-H3 streaming.

TaoMate-H3 conditions every new chunk on the *clean* (sigma = 0) keys and
values of earlier chunks. After the three noisy denoise forwards of a chunk, a
fourth forward at sigma = 0 recomputes the chunk's K/V from its clean latents
and appends them to this cache. Retention keeps the first chunk's video rows
as a permanent sink plus the two most recent complete audio/video chunks; the
audio history is dropped every twelve requests.

The cache is model-owned and dense: it stores, per transformer layer, the K
and V rows *after* the Ulysses all-to-all, so each sequence-parallel rank keeps
the full row history for its own head shard (56 / ulysses_degree heads).
Chunk sizes are irregular (12/10/10/5 video latents plus a variable number of
audio latents) and the sink is video-only, which is why this does not use the
runner's paged block pool.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

VIDEO_TOKEN_TAG = 0
TEXT_TOKEN_TAG = 1
AUDIO_TOKEN_TAG = 2


@dataclass(frozen=True)
class KVContract:
    """Shape contract for the rank-local attention shard."""

    num_layers: int
    local_heads: int
    head_dim: int
    dtype: torch.dtype = torch.bfloat16

    @property
    def layer_names(self) -> tuple[str, ...]:
        return tuple(f"blocks.{index}.attn" for index in range(self.num_layers))

    def bytes_for_rows(self, rows: int) -> int:
        """Bytes of K plus V for ``rows`` rows across all layers."""
        element = torch.empty((), dtype=self.dtype).element_size()
        return 2 * self.num_layers * rows * self.local_heads * self.head_dim * element


@dataclass(frozen=True)
class AVKV:
    """Dense clean audio/video keys and values for one attention layer."""

    key: torch.Tensor
    value: torch.Tensor


def _validate_av_pair(pair: AVKV, contract: KVContract, *, layer_name: str) -> None:
    expected_tail = (contract.local_heads, contract.head_dim)
    if pair.key.ndim != 3 or tuple(pair.key.shape[1:]) != expected_tail:
        raise RuntimeError(
            f"{layer_name}: expected key shape [tokens, {expected_tail[0]}, {expected_tail[1]}], "
            f"got {tuple(pair.key.shape)}"
        )
    if pair.value.shape != pair.key.shape:
        raise RuntimeError(f"{layer_name}: key/value shape mismatch")
    if pair.key.dtype != contract.dtype or pair.value.dtype != contract.dtype:
        raise RuntimeError(f"{layer_name}: persistent KV must be {contract.dtype}")


class CleanAVKVCache:
    """Transactional persistent cache holding clean media KV only.

    A clean commit stages one chunk layer by layer (``begin_clean_commit`` ->
    ``stage`` x layers -> ``commit``); ``rollback`` discards a partial stage.
    ``retain_sink_and_recent_commits`` applies TaoMate's retention policy after
    each commit and ``drop_audio_history`` implements the periodic audio reset.
    """

    def __init__(self, contract: KVContract) -> None:
        self.contract = contract
        self._layer_names = set(contract.layer_names)
        self._history: dict[str, AVKV] = {}
        self._staged: dict[str, AVKV] = {}
        self._staged_block: int | None = None
        self._staged_tags: tuple[int, ...] | None = None
        self._staged_indices: torch.Tensor | None = None
        self._block_index = 0
        self._commit_token_counts: list[int] = []
        self._commit_token_tags: list[tuple[int, ...]] = []

    @property
    def committed_blocks(self) -> int:
        return self._block_index

    @property
    def history_tokens(self) -> int:
        if not self._history:
            return 0
        return int(next(iter(self._history.values())).key.shape[0])

    @property
    def history_audio_tokens(self) -> int:
        return sum(tag == AUDIO_TOKEN_TAG for tags in self._commit_token_tags for tag in tags)

    @property
    def history_video_tokens(self) -> int:
        return sum(tag == VIDEO_TOKEN_TAG for tags in self._commit_token_tags for tag in tags)

    @property
    def clean_commit_active(self) -> bool:
        return self._staged_block is not None

    def history(self, layer_name: str) -> AVKV | None:
        self._validate_layer_name(layer_name)
        return self._history.get(layer_name)

    def begin_clean_commit(self, block_index: int) -> None:
        if self.clean_commit_active:
            raise RuntimeError("a clean KV commit is already active")
        if block_index != self._block_index:
            raise RuntimeError(f"expected clean chunk {self._block_index}, got {block_index}")
        self._staged_block = block_index
        self._staged.clear()
        self._staged_tags = None
        self._staged_indices = None

    def stage(
        self,
        layer_name: str,
        key: torch.Tensor,
        value: torch.Tensor,
        token_tags: torch.Tensor,
        commit_mask: torch.Tensor,
    ) -> None:
        """Stage the clean audio/video rows produced by one transformer layer.

        ``key``/``value`` are the full post-all-to-all rows of the current
        chunk sequence ``[seq_len, local_heads, head_dim]``; ``token_tags`` and
        ``commit_mask`` are the full-sequence modality tags and the mask of
        rows that enter the persistent history (audio and video targets).
        """
        if not self.clean_commit_active:
            raise RuntimeError("begin_clean_commit() must be called before stage()")
        self._validate_layer_name(layer_name)
        if layer_name in self._staged:
            raise RuntimeError(f"{layer_name}: KV was staged more than once")
        if key.shape != value.shape or key.ndim != 3:
            raise RuntimeError(f"{layer_name}: key/value must have matching rank-3 shapes")
        if token_tags.ndim != 1 or commit_mask.ndim != 1:
            raise RuntimeError("token_tags and commit_mask must be rank-1")
        if token_tags.shape[0] != key.shape[0] or commit_mask.shape[0] != key.shape[0]:
            raise RuntimeError(f"{layer_name}: packed metadata length does not match KV rows")
        if self._staged_indices is None:
            indices = torch.nonzero(commit_mask.to(torch.bool), as_tuple=False).flatten()
            if indices.numel() == 0:
                raise RuntimeError("clean commit did not contain audio/video rows")
            selected_tags = token_tags.index_select(0, indices)
            tags = tuple(int(tag) for tag in selected_tags.detach().cpu().tolist())
            if frozenset(tags) != frozenset((VIDEO_TOKEN_TAG, AUDIO_TOKEN_TAG)):
                raise RuntimeError("each clean chunk must contain both video and audio KV")
            self._staged_indices = indices
            self._staged_tags = tags
        indices = self._staged_indices
        assert indices is not None
        pair = AVKV(
            key=key.index_select(0, indices).detach().to(self.contract.dtype),
            value=value.index_select(0, indices).detach().to(self.contract.dtype),
        )
        _validate_av_pair(pair, self.contract, layer_name=layer_name)
        self._staged[layer_name] = pair

    def commit(self) -> None:
        """Atomically append all staged layers to the persistent history."""
        if not self.clean_commit_active:
            raise RuntimeError("no clean KV commit is active")
        missing = [name for name in self.contract.layer_names if name not in self._staged]
        if missing:
            raise RuntimeError(f"clean KV commit is missing {len(missing)} transformer layers")
        assert self._staged_tags is not None
        token_count = len(self._staged_tags)
        # One layer at a time, so old and new histories are never both resident
        # for every layer at the steady-state memory peak.
        for layer_name in self.contract.layer_names:
            current = self._staged.pop(layer_name)
            previous = self._history.pop(layer_name, None)
            if previous is None:
                combined = current
            else:
                combined = AVKV(
                    key=torch.cat((previous.key, current.key), dim=0),
                    value=torch.cat((previous.value, current.value), dim=0),
                )
            self._history[layer_name] = combined
        self._commit_token_counts.append(token_count)
        self._commit_token_tags.append(self._staged_tags)
        self._block_index += 1
        self._clear_staging()

    def retain_sink_and_recent_commits(self) -> None:
        """Keep the first chunk's video sink and the two most recent clean chunks."""
        if self.clean_commit_active:
            raise RuntimeError("cannot trim persistent KV during an active clean commit")
        block_count = len(self._commit_token_counts)
        # As soon as three clean chunks exist, age chunk zero to a video-only
        # sink and keep the two most recent chunks as complete AV recents.
        if block_count <= 2:
            return
        recent_start = max(1, block_count - 2)
        selection = [(0, True)] + [(index, False) for index in range(recent_start, block_count)]
        self._retain_commit_rows(selection)

    def drop_audio_history(self) -> int:
        """Remove audio rows while preserving every retained video row."""
        if self.clean_commit_active:
            raise RuntimeError("cannot drop audio history during an active clean commit")
        removed = self.history_audio_tokens
        if not self._commit_token_counts:
            return 0
        self._retain_commit_rows([(index, True) for index in range(len(self._commit_token_counts))])
        return removed

    def rollback(self) -> None:
        self._clear_staging()

    def clear(self) -> None:
        self._history.clear()
        self._commit_token_counts.clear()
        self._commit_token_tags.clear()
        self._block_index = 0
        self._clear_staging()

    def _retain_commit_rows(self, selection: list[tuple[int, bool]]) -> None:
        offsets = [0]
        for count in self._commit_token_counts:
            offsets.append(offsets[-1] + count)
        selected_rows: list[int] = []
        selected_counts: list[int] = []
        selected_tags: list[tuple[int, ...]] = []
        for block_index, video_only in selection:
            tags = self._commit_token_tags[block_index]
            start = offsets[block_index]
            local_rows = [i for i, tag in enumerate(tags) if not video_only or tag == VIDEO_TOKEN_TAG]
            if not local_rows:
                continue
            selected_rows.extend(start + row for row in local_rows)
            kept_tags = tuple(tags[row] for row in local_rows)
            selected_counts.append(len(kept_tags))
            selected_tags.append(kept_tags)
        if not selected_rows:
            self._history.clear()
            self._commit_token_counts.clear()
            self._commit_token_tags.clear()
            return
        next_history: dict[str, AVKV] = {}
        indices: torch.Tensor | None = None
        for layer_name, pair in self._history.items():
            if indices is None or indices.device != pair.key.device:
                indices = torch.tensor(selected_rows, dtype=torch.long, device=pair.key.device)
            next_history[layer_name] = AVKV(
                key=pair.key.index_select(0, indices),
                value=pair.value.index_select(0, indices),
            )
        self._history = next_history
        self._commit_token_counts = selected_counts
        self._commit_token_tags = selected_tags

    def _clear_staging(self) -> None:
        self._staged.clear()
        self._staged_block = None
        self._staged_tags = None
        self._staged_indices = None

    def _validate_layer_name(self, layer_name: str) -> None:
        if layer_name not in self._layer_names:
            raise KeyError(f"unexpected transformer layer: {layer_name}")


__all__ = ["AUDIO_TOKEN_TAG", "AVKV", "CleanAVKVCache", "KVContract", "TEXT_TOKEN_TAG", "VIDEO_TOKEN_TAG"]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/packed.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""Packed-sequence layouts for TaoMate-H3 streaming phases and the audio teacher.

A streaming phase is one future-free T2VA document ``[text | audio | video | pad]``
built with the shared MiniMax-H3 builder and then re-timed onto the session's
global RoPE timeline:

* the current prompt is right-aligned to the request's media time origin;
* video latents sit at their absolute positions (the release's 5/3-scaled
  (1, 4, 4, 4, 4) spacing continued across requests);
* audio latents sit at their absolute 40 Hz index.

The audio teacher runs audio-only documents ``[text | (reference audio) | audio | pad]``
whose builders are ported here because the shared builder always packs a video
target. Both return the layout dictionary that ``MiniMaxH3DenoiseBranch``
consumes, so the upstream DiT forward path is reused unchanged.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from vllm_omni.diffusion.models.minimax_h3.packed_sequence import (
    MINIMAX_H3_SEQ_ALIGN,
    _axis_from_sqrt_area,
    minimax_h3_packed_sequence,
)

from .geometry import StreamPhase, video_temporal_position, video_temporal_positions

_PATCH_H = 2
_PATCH_W = 2


def _pad_len(used: int, seq_len: int | None) -> int:
    if seq_len is None:
        return ((used + MINIMAX_H3_SEQ_ALIGN - 1) // MINIMAX_H3_SEQ_ALIGN) * MINIMAX_H3_SEQ_ALIGN
    if seq_len < used or seq_len % MINIMAX_H3_SEQ_ALIGN:
        raise ValueError(f"seq_len {seq_len} must cover {used} used rows and be a multiple of {MINIMAX_H3_SEQ_ALIGN}")
    return seq_len


def prompt_rope_start(*, text_len: int, media_time_origin: int, video_latent_offset: int) -> float:
    """Right-align the current prompt to the request's global media origin."""
    return float(media_time_origin + video_temporal_position(video_latent_offset) - text_len)


def taomate_phase_packed_layout(
    *,
    text_len: int,
    phase: StreamPhase,
    latent_h: int,
    latent_w: int,
    media_time_origin: int,
    video_latent_offset: int,
    audio_latent_offset: int,
    seq_len: int | None = None,
) -> dict[str, Any]:
    """One streaming phase document on the global timeline.

    ``video_latent_offset`` / ``audio_latent_offset`` are the session-global
    latent indices at which the current *request* starts; ``phase`` carries the
    request-local offsets of this chunk.
    """
    packed = minimax_h3_packed_sequence(
        text_len=text_len,
        latent_t=phase.video_latent_count,
        latent_h=latent_h,
        latent_w=latent_w,
        audio_t=phase.audio_latent_count,
        audio_channel=2,
        include_keyframe_cond=False,
        seq_len=seq_len,
    )
    grid: torch.Tensor = packed["img_position_ids"]
    text_pos: torch.Tensor = packed["text_pos"].view(-1)
    img_pos: torch.Tensor = packed["img_pos"].view(-1)
    audio_pos: torch.Tensor = packed["audio_pos"].view(-1)
    frame_rows = (latent_h // _PATCH_H) * (latent_w // _PATCH_W)
    if int(img_pos.numel()) != phase.video_latent_count * frame_rows:
        raise RuntimeError("chunk video rows do not match the latent geometry")

    start = prompt_rope_start(
        text_len=text_len,
        media_time_origin=media_time_origin,
        video_latent_offset=video_latent_offset,
    )
    grid[text_pos, 0] = start + torch.arange(text_len, dtype=grid.dtype)
    positions = video_temporal_positions(video_latent_offset + phase.video_latent_start, phase.video_latent_count)
    video_times = torch.tensor([float(media_time_origin + position) for position in positions], dtype=grid.dtype)
    grid[img_pos, 0] = video_times.repeat_interleave(frame_rows)
    audio_by_channel = audio_pos.view(2, phase.audio_latent_count)
    audio_times = media_time_origin + torch.arange(
        audio_latent_offset + phase.audio_latent_start,
        audio_latent_offset + phase.audio_latent_stop,
        dtype=grid.dtype,
    )
    grid[audio_by_channel[0], 0] = audio_times
    grid[audio_by_channel[1], 0] = audio_times
    packed["taomate_times"] = {
        "text_time_start": start,
        "phase_video_time_start": float(video_times[0]),
        "phase_audio_time_start": float(audio_times[0]),
    }
    return packed


def _audio_only_common(
    *,
    text_len: int,
    latent_h: int,
    latent_w: int,
    ref_audio_t: int,
    audio_t: int,
    reference_time_start: float,
    target_time_start: float,
    audio_channel: int,
    seq_len: int | None,
) -> dict[str, Any]:
    if min(text_len, audio_t, latent_h, latent_w, audio_channel) <= 0 or ref_audio_t < 0:
        raise ValueError("audio-only layout dimensions must be positive")
    if latent_h % _PATCH_H or latent_w % _PATCH_W:
        raise ValueError("latent_h and latent_w must be divisible by the 2x2 patch")
    ref_rows = ref_audio_t * audio_channel
    target_rows = audio_t * audio_channel
    used = text_len + ref_rows + target_rows
    seq_len = _pad_len(used, seq_len)
    text_sl = slice(0, text_len)
    ref_sl = slice(text_len, text_len + ref_rows)
    target_sl = slice(ref_sl.stop, ref_sl.stop + target_rows)

    grid = torch.zeros(seq_len, 3, dtype=torch.float64)
    grid[text_sl, 0] = torch.arange(text_len, dtype=torch.float64)
    if ref_audio_t:
        grid[ref_sl, 0] = (float(reference_time_start) + torch.arange(ref_audio_t, dtype=torch.float64)).repeat(
            audio_channel
        )
    grid[target_sl, 0] = (float(target_time_start) + torch.arange(audio_t, dtype=torch.float64)).repeat(audio_channel)
    sqrt_area = np.sqrt(latent_h * latent_w)
    w_grid = _axis_from_sqrt_area(latent_w, _PATCH_W, sqrt_area)
    for audio_sl, temporal_rows in ((ref_sl, ref_audio_t), (target_sl, audio_t)):
        if temporal_rows:
            grid[audio_sl.start : audio_sl.start + temporal_rows, 2] = float(w_grid[0])
            grid[audio_sl.start + temporal_rows : audio_sl.stop, 2] = float(w_grid[-1])

    audio_pos = torch.arange(ref_sl.start, target_sl.stop)
    audio_update_mask = torch.zeros(ref_rows + target_rows, dtype=torch.bool)
    audio_update_mask[ref_rows:] = True
    token_tags = torch.full((seq_len,), -1, dtype=torch.long)
    token_tags[text_sl] = 1
    token_tags[audio_pos] = 2
    ph, pw = latent_h // _PATCH_H, latent_w // _PATCH_W
    return {
        "seq_len": torch.tensor(seq_len),
        "img_pos": torch.empty(0, dtype=torch.long),
        "audio_pos": audio_pos,
        "audio_update_mask": audio_update_mask,
        "text_pos": torch.arange(text_len),
        "update_mask": torch.zeros(0, dtype=torch.bool),
        "img_position_ids": grid,
        "token_tags": token_tags,
        "cu_seqlens": torch.tensor([0, used, seq_len], dtype=torch.int32),
        # No video rows: the layout metadata is informational only.
        "latent_grid": torch.tensor([0, ph, pw], dtype=torch.int64),
        "video_row_start": torch.tensor(target_sl.stop, dtype=torch.int64),
    }


def taomate_audio_only_packed_layout(
    *,
    text_len: int,
    audio_t: int,
    latent_h: int,
    latent_w: int,
    audio_channel: int = 2,
    seq_len: int | None = None,
) -> dict[str, Any]:
    """The teacher's first-request text/audio document without video tokens."""
    return _audio_only_common(
        text_len=text_len,
        latent_h=latent_h,
        latent_w=latent_w,
        ref_audio_t=0,
        audio_t=audio_t,
        reference_time_start=float(text_len),
        target_time_start=float(text_len),
        audio_channel=audio_channel,
        seq_len=seq_len,
    )


def taomate_audio_only_frozen_prefix_packed_layout(
    *,
    text_len: int,
    ref_audio_t: int,
    audio_t: int,
    latent_h: int,
    latent_w: int,
    reference_time_start: int,
    target_time_start: int,
    audio_channel: int = 2,
    seq_len: int | None = None,
) -> dict[str, Any]:
    """The teacher's continuation document with a clean, read-only reference tail."""
    if ref_audio_t <= 0:
        raise ValueError("frozen-prefix layout requires ref_audio_t > 0")
    return _audio_only_common(
        text_len=text_len,
        latent_h=latent_h,
        latent_w=latent_w,
        ref_audio_t=ref_audio_t,
        audio_t=audio_t,
        reference_time_start=float(reference_time_start),
        target_time_start=float(target_time_start),
        audio_channel=audio_channel,
        seq_len=seq_len,
    )


__all__ = [
    "prompt_rope_start",
    "taomate_audio_only_frozen_prefix_packed_layout",
    "taomate_audio_only_packed_layout",
    "taomate_phase_packed_layout",
]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/geometry.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""TaoMate-H3 streaming geometry.

TaoMate-H3 generates one five-second MiniMax-H3 T2VA request at a time and
splits it into four causal phases of (2, 2, 2, 1) native 17-frame groups. The
first request additionally owns the five-frame / two-latent affine prefix of a
standalone H3 request; later requests ("canonical continuations") generate only
the steady 119 frames and inherit the previous request's tail as a transport
prefix. Audio latents run at 40 Hz and their phase boundaries are rounded on
the global frame timeline, so a continuation request has 198 or 199 audio
latents per channel rather than a request-local 207.

Everything in this module is host-side integer bookkeeping shared by the
denoise loop, the audio teacher and the streaming decoder. It mirrors the
validated TaoMate-H3 direct-streaming contract and must not drift from it: the
LoRA was distilled for exactly this phase geometry and RoPE timeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

VIDEO_FPS = 24
AUDIO_LATENT_RATE = 40
AUDIO_SAMPLE_RATE = 32000
AUDIO_SAMPLES_PER_LATENT = AUDIO_SAMPLE_RATE // AUDIO_LATENT_RATE  # 800
VIDEO_PREFIX_FRAMES = 5
VIDEO_PREFIX_LATENTS = 2
VIDEO_GROUP_FRAMES = 17
VIDEO_GROUP_LATENTS = 5
REQUEST_SECONDS = 5
PHASE_GROUP_COUNTS = (2, 2, 2, 1)
# Official standalone request geometry (37 video latents, 207 audio latents).
REQUEST_VIDEO_LATENTS = 37
REQUEST_AUDIO_LATENTS = 207
REQUEST_NATIVE_FRAMES = 124
STEADY_NATIVE_FRAMES = REQUEST_NATIVE_FRAMES - VIDEO_PREFIX_FRAMES  # 119
SUPPORTED_SHORT_EDGES = (480, 768, 1088)
CANVAS_MULTIPLE = 32
# RoPE temporal spacing of H3 video latents: the first latent of every group of
# five spans one native frame, the other four span four frames each, all
# rescaled by 5/3 so that one 40 Hz audio latent is one RoPE unit.
_TEMPORAL_WEIGHTS = (1, 4, 4, 4, 4)
_FRAME_RESCALE = Fraction(5, 3)


def _round_half_even(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    doubled = remainder * 2
    if doubled < value.denominator:
        return quotient
    if doubled > value.denominator:
        return quotient + 1
    return quotient + (quotient & 1)


def audio_latent_boundary(frame: int) -> int:
    """40 Hz audio latent index at a 24 fps frame boundary (round half even)."""
    return _round_half_even(Fraction(frame * AUDIO_LATENT_RATE, VIDEO_FPS))


def video_temporal_position(latent_index: int) -> Fraction:
    """Absolute H3 RoPE time coordinate of a video latent before the text origin offset."""
    if isinstance(latent_index, bool) or not isinstance(latent_index, int):
        raise TypeError("latent_index must be an integer")
    if latent_index < 0:
        raise ValueError("latent_index must be non-negative")
    return sum(
        (_FRAME_RESCALE * _TEMPORAL_WEIGHTS[index % len(_TEMPORAL_WEIGHTS)] for index in range(latent_index)),
        start=Fraction(0),
    )


def video_temporal_positions(start: int, count: int) -> tuple[Fraction, ...]:
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("count must be a positive integer")
    return tuple(video_temporal_position(index) for index in range(start, start + count))


@dataclass(frozen=True)
class StreamPhase:
    """One causal chunk of a request: a contiguous frame / latent span."""

    index: int
    group_count: int
    frame_start: int
    frame_stop: int
    video_latent_start: int
    video_latent_stop: int
    audio_latent_start: int
    audio_latent_stop: int

    @property
    def frame_count(self) -> int:
        return self.frame_stop - self.frame_start

    @property
    def video_latent_count(self) -> int:
        return self.video_latent_stop - self.video_latent_start

    @property
    def audio_latent_count(self) -> int:
        return self.audio_latent_stop - self.audio_latent_start


@dataclass(frozen=True)
class StreamPlan:
    """The phases of one request, in request-local frame / latent coordinates."""

    native_frame_count: int
    phases: tuple[StreamPhase, ...]

    @property
    def video_latent_count(self) -> int:
        return self.phases[-1].video_latent_stop

    @property
    def audio_latent_count(self) -> int:
        return self.phases[-1].audio_latent_stop


def direct_5s_plan() -> StreamPlan:
    """The four-phase plan of the first (standalone) five-second request."""
    phases: list[StreamPhase] = []
    frame_stop = 0
    video_stop = 0
    for index, groups in enumerate(PHASE_GROUP_COUNTS):
        frame_start = frame_stop
        video_start = video_stop
        frame_stop += groups * VIDEO_GROUP_FRAMES
        video_stop += groups * VIDEO_GROUP_LATENTS
        if index == 0:
            frame_stop += VIDEO_PREFIX_FRAMES
            video_stop += VIDEO_PREFIX_LATENTS
        phases.append(
            StreamPhase(
                index=index,
                group_count=groups,
                frame_start=frame_start,
                frame_stop=frame_stop,
                video_latent_start=video_start,
                video_latent_stop=video_stop,
                audio_latent_start=audio_latent_boundary(frame_start),
                audio_latent_stop=audio_latent_boundary(frame_stop),
            )
        )
    plan = StreamPlan(native_frame_count=REQUEST_NATIVE_FRAMES, phases=tuple(phases))
    if plan.video_latent_count != REQUEST_VIDEO_LATENTS or plan.audio_latent_count != REQUEST_AUDIO_LATENTS:
        raise RuntimeError("TaoMate-H3 direct plan does not match the official H3 request geometry")
    return plan


def canonical_continuation_plan(base_plan: StreamPlan, *, request_index: int) -> StreamPlan:
    """The steady-state plan of request ``request_index > 0``.

    A continuation advances seven native 17-frame groups (35 video latents)
    without regenerating the affine prefix. Audio boundaries are rounded on the
    global frame timeline, so the per-request audio count is 198 or 199.
    """
    if isinstance(request_index, bool) or not isinstance(request_index, int):
        raise TypeError("request_index must be an integer")
    if request_index <= 0:
        raise ValueError("canonical continuation requires request_index > 0")
    steady_frame_count = base_plan.native_frame_count - VIDEO_PREFIX_FRAMES
    global_frame_start = base_plan.native_frame_count + (request_index - 1) * steady_frame_count
    global_audio_start = audio_latent_boundary(global_frame_start)
    phases: list[StreamPhase] = []
    frame_stop = 0
    video_stop = 0
    for index, base_phase in enumerate(base_plan.phases):
        frame_start = frame_stop
        video_start = video_stop
        frame_stop += base_phase.group_count * VIDEO_GROUP_FRAMES
        video_stop += base_phase.group_count * VIDEO_GROUP_LATENTS
        phases.append(
            StreamPhase(
                index=index,
                group_count=base_phase.group_count,
                frame_start=frame_start,
                frame_stop=frame_stop,
                video_latent_start=video_start,
                video_latent_stop=video_stop,
                audio_latent_start=audio_latent_boundary(global_frame_start + frame_start) - global_audio_start,
                audio_latent_stop=audio_latent_boundary(global_frame_start + frame_stop) - global_audio_start,
            )
        )
    return StreamPlan(native_frame_count=steady_frame_count, phases=tuple(phases))


def request_plan(request_index: int) -> StreamPlan:
    """The plan of request ``request_index`` of a session."""
    base = direct_5s_plan()
    if request_index == 0:
        return base
    return canonical_continuation_plan(base, request_index=request_index)


@dataclass(frozen=True)
class CanvasGeometry:
    """Latent canvas of one output resolution."""

    height: int
    width: int

    def __post_init__(self) -> None:
        if isinstance(self.width, bool) or isinstance(self.height, bool):
            raise ValueError("width and height must be integers")
        if self.width <= 0 or self.height <= 0 or self.width % CANVAS_MULTIPLE or self.height % CANVAS_MULTIPLE:
            raise ValueError("TaoMate-H3 width and height must be positive multiples of 32")
        if min(self.width, self.height) not in SUPPORTED_SHORT_EDGES:
            raise ValueError("TaoMate-H3 requires a 480-, 768-, or 1088-pixel short edge")

    @property
    def latent_h(self) -> int:
        return self.height // 16

    @property
    def latent_w(self) -> int:
        return self.width // 16

    @property
    def frame_rows(self) -> int:
        """Packed DiT rows per video latent frame ((H/16/2) * (W/16/2))."""
        return (self.latent_h // 2) * (self.latent_w // 2)


def phases_for_frames(num_frames: int) -> int:
    """Number of phases (chunks) needed to publish at least ``num_frames`` frames."""
    if num_frames <= 0:
        raise ValueError("num_frames must be positive")
    requests = 1
    published = REQUEST_NATIVE_FRAMES
    while published < num_frames:
        requests += 1
        published += STEADY_NATIVE_FRAMES
    return requests * len(PHASE_GROUP_COUNTS)


__all__ = [
    "AUDIO_LATENT_RATE",
    "AUDIO_SAMPLES_PER_LATENT",
    "AUDIO_SAMPLE_RATE",
    "CanvasGeometry",
    "PHASE_GROUP_COUNTS",
    "REQUEST_AUDIO_LATENTS",
    "REQUEST_NATIVE_FRAMES",
    "REQUEST_VIDEO_LATENTS",
    "STEADY_NATIVE_FRAMES",
    "StreamPhase",
    "StreamPlan",
    "VIDEO_FPS",
    "audio_latent_boundary",
    "canonical_continuation_plan",
    "direct_5s_plan",
    "phases_for_frames",
    "request_plan",
    "video_temporal_position",
    "video_temporal_positions",
]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/schedule.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""TaoMate-H3 sigma schedules and the positive-only Euler (eta = 0) update.

The student runs three denoise steps per chunk at the sigma positions
``(0, 16, 33, 49)`` of MiniMax-H3's 50-point time-shifted schedule (shift 12
for video, 3 for audio). The audio teacher runs the base model's 10-point
schedule (nine forwards). Both are the release's ``time_shift_sigmas`` with
``torch.linspace(1, 0, n)``; they are kept here verbatim so the port cannot
drift from the distilled contract through a shared helper's defaults.
"""

from __future__ import annotations

import math

import torch

DISTILLED_STATE_INDICES = (0, 16, 33, 49)
STUDENT_SCHEDULE_STEPS = 50
TEACHER_SCHEDULE_STEPS = 10
TEACHER_STATE_NUMBERS = (3, 6, 9)
VIDEO_SHIFT = 12.0
AUDIO_SHIFT = 3.0


def time_shift_sigmas(*, num_steps: int, shift_scale: float) -> list[float]:
    if num_steps <= 1 or not math.isfinite(shift_scale) or shift_scale <= 0:
        raise ValueError("sigma schedule requires num_steps > 1 and shift_scale > 0")
    base = torch.linspace(1.0, 0.0, num_steps, dtype=torch.float32, device="cpu")
    shifted = shift_scale * base / (1.0 + (shift_scale - 1.0) * base)
    shifted = torch.unique_consecutive(shifted)
    if int(shifted.numel()) != num_steps:
        raise ValueError("shifted sigma schedule changed cardinality")
    return [float(item) for item in shifted.tolist()]


def select_time_shift_sigmas(
    *,
    num_steps: int,
    shift_scale: float,
    state_indices: tuple[int, ...] | None = None,
) -> list[float]:
    schedule = time_shift_sigmas(num_steps=num_steps, shift_scale=shift_scale)
    if state_indices is None:
        return schedule
    indices = tuple(state_indices)
    if len(indices) < 2 or indices[0] != 0 or indices[-1] != num_steps - 1 or tuple(sorted(set(indices))) != indices:
        raise ValueError("retained sigma indices must be sorted, unique, and span the schedule")
    return [schedule[index] for index in indices]


def student_sigmas() -> tuple[list[float], list[float]]:
    """(video, audio) sigma ladders of the three-step distilled student."""
    return (
        select_time_shift_sigmas(
            num_steps=STUDENT_SCHEDULE_STEPS, shift_scale=VIDEO_SHIFT, state_indices=DISTILLED_STATE_INDICES
        ),
        select_time_shift_sigmas(
            num_steps=STUDENT_SCHEDULE_STEPS, shift_scale=AUDIO_SHIFT, state_indices=DISTILLED_STATE_INDICES
        ),
    )


def teacher_sigmas() -> tuple[list[float], list[float]]:
    """(video, audio) sigma ladders of the ten-state base audio teacher."""
    return (
        select_time_shift_sigmas(num_steps=TEACHER_SCHEDULE_STEPS, shift_scale=VIDEO_SHIFT),
        select_time_shift_sigmas(num_steps=TEACHER_SCHEDULE_STEPS, shift_scale=AUDIO_SHIFT),
    )


@torch.no_grad()
def euler_eta0_update_(
    state: torch.Tensor,
    velocity: torch.Tensor,
    *,
    sigma_curr: float,
    sigma_next: float,
) -> torch.Tensor:
    """In-place rectified-flow Euler step with eta = 0, in the release's op order.

    ``denoised = state + sigma * v``; ``state <- ratio * state + (1 - ratio) * denoised``
    with ``ratio = sigma_next / sigma_curr``.
    """
    denoised = torch.add(state, velocity, alpha=float(sigma_curr))
    ratio = float(sigma_next) / float(sigma_curr)
    state.mul_(ratio).add_(denoised, alpha=1.0 - ratio)
    return state


__all__ = [
    "AUDIO_SHIFT",
    "DISTILLED_STATE_INDICES",
    "TEACHER_STATE_NUMBERS",
    "VIDEO_SHIFT",
    "euler_eta0_update_",
    "select_time_shift_sigmas",
    "student_sigmas",
    "teacher_sigmas",
    "time_shift_sigmas",
]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/lora.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""TaoMate-H3 native LoRA adapter applied as switchable forward hooks.

The TaoMate-H3 release (``TaoLiveAIGC/TaoMate-H3``) is a rank-128 LoRA over
the fused MiniMax-H3 checkpoint layout: 52 blocks (2 token-refiner blocks and
50 DiT blocks) x 4 projections (``attn.qkv_proj``, ``attn.out_proj``,
``mlp.fc1``, ``mlp.fc2``), stored as ``<target>.lora_a`` [r, in] and
``<target>.lora_b`` [out, r] in ``adapter_model.safetensors`` with
``{"rank": 128, "alpha": 128.0}`` in ``config.json`` / ``adapter_config.json``.

The adapter is deliberately *not* merged into the weights: TaoMate's audio
teacher is the base H3 model without the LoRA, and it must share the resident
BF16 weights with the LoRA student (two copies of the 62 GB DiT do not fit one
device). Instead every target linear gets a forward hook that adds
``(x @ A^T) @ B^T * alpha / rank`` to its output while the adapter is enabled;
``disabled()`` switches it off for the teacher forwards.

Only ``tensor_parallel_size == 1`` is supported (the realtime topology is pure
Ulysses sequence parallelism): the adapter is then replicated on every rank
and no A/B sharding is required. The fused QKV base weight is re-ordered from
the checkpoint's per-head grouped layout to ``[Q; K; V]`` at load time, so the
QKV ``lora_b`` rows are permuted the same way.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import torch
import torch.nn as nn
from safetensors import safe_open
from vllm.logger import init_logger

from vllm_omni.diffusion.models.minimax_h3.minimax_h3_transformer import MiniMaxH3DiTModel

logger = init_logger(__name__)

TAOMATE_LORA_TARGET_SUFFIXES = ("attn.qkv_proj", "attn.out_proj", "mlp.fc1", "mlp.fc2")
TAOMATE_LORA_WEIGHTS_FILE = "adapter_model.safetensors"


def taomate_lora_targets(*, num_blocks: int = 50, num_refiner_blocks: int = 2) -> tuple[str, ...]:
    """The adapter's exact block x projection inventory, in checkpoint order."""
    blocks = [f"token_refiner.blocks.{index}" for index in range(num_refiner_blocks)]
    blocks.extend(f"blocks.{index}" for index in range(num_blocks))
    return tuple(f"{block}.{suffix}" for block in blocks for suffix in TAOMATE_LORA_TARGET_SUFFIXES)


class TaoMateLoRAError(RuntimeError):
    pass


def _read_adapter_config(adapter_dir: Path) -> tuple[int, float]:
    config_path = adapter_dir / "config.json"
    if not config_path.is_file():
        config_path = adapter_dir / "adapter_config.json"
    if not config_path.is_file():
        raise TaoMateLoRAError(f"TaoMate-H3 adapter config not found under {adapter_dir}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaoMateLoRAError(f"cannot read TaoMate-H3 adapter config: {exc}") from exc
    rank = config.get("rank", config.get("r"))
    alpha = config.get("alpha", config.get("lora_alpha"))
    if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
        raise TaoMateLoRAError("TaoMate-H3 adapter rank is invalid")
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not math.isfinite(float(alpha)) or alpha <= 0:
        raise TaoMateLoRAError("TaoMate-H3 adapter alpha is invalid")
    return int(rank), float(alpha)


def is_taomate_lora_dir(path: str | Path | None) -> bool:
    """Whether ``path`` looks like a TaoMate-H3 native adapter directory."""
    if not path:
        return False
    root = Path(path)
    if not root.is_dir() or not (root / TAOMATE_LORA_WEIGHTS_FILE).is_file():
        return False
    if not ((root / "config.json").is_file() or (root / "adapter_config.json").is_file()):
        return False
    try:
        with safe_open(str(root / TAOMATE_LORA_WEIGHTS_FILE), framework="pt", device="cpu") as handle:
            keys = list(handle.keys())
    except Exception:  # noqa: BLE001 - not ours if it does not open
        return False
    return any(key.endswith(".lora_a") for key in keys) and any(key.endswith(".lora_b") for key in keys)


class TaoMateLoRAAdapter:
    """Hook-based, switchable application of the TaoMate-H3 LoRA."""

    def __init__(
        self,
        *,
        rank: int,
        alpha: float,
        lora_a: dict[str, torch.Tensor],
        lora_b: dict[str, torch.Tensor],
        source: str,
    ) -> None:
        self.rank = rank
        self.alpha = alpha
        self.scale = alpha / rank
        self.source = source
        self._lora_a = lora_a
        self._lora_b = lora_b
        self._handles: list[torch.utils.hooks.RemovableHandle] = []
        self._bound_targets: tuple[str, ...] = ()
        self.enabled = True

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(self._lora_a)

    @property
    def bound_targets(self) -> tuple[str, ...]:
        return self._bound_targets

    @classmethod
    def load(
        cls,
        adapter_dir: str | Path,
        *,
        transformer: MiniMaxH3DiTModel,
        device: torch.device,
        dtype: torch.dtype = torch.bfloat16,
    ) -> TaoMateLoRAAdapter:
        """Read the adapter and prepare rank-local A/B buffers in the model's fused layout."""
        root = Path(adapter_dir).expanduser().resolve()
        rank, alpha = _read_adapter_config(root)
        arch = transformer.arch
        targets = taomate_lora_targets(
            num_blocks=arch.num_layers,
            num_refiner_blocks=arch.token_refiner_num_layers,
        )
        expected = {f"{target}.{leaf}" for target in targets for leaf in ("lora_a", "lora_b")}
        weights_path = root / TAOMATE_LORA_WEIGHTS_FILE
        lora_a: dict[str, torch.Tensor] = {}
        lora_b: dict[str, torch.Tensor] = {}
        modules = dict(transformer.named_modules())
        with safe_open(str(weights_path), framework="pt", device="cpu") as handle:
            present = set(handle.keys())
            if present != expected:
                raise TaoMateLoRAError(
                    "TaoMate-H3 LoRA tensor inventory differs from the 52-block x 4-projection contract: "
                    f"missing={len(expected - present)}, unexpected={len(present - expected)}"
                )
            for target in targets:
                module = modules.get(target)
                if module is None or not hasattr(module, "weight"):
                    raise TaoMateLoRAError(f"TaoMate-H3 LoRA target {target!r} has no linear module in the DiT")
                a = handle.get_tensor(f"{target}.lora_a")
                b = handle.get_tensor(f"{target}.lora_b")
                if a.ndim != 2 or b.ndim != 2 or a.shape[0] != rank or b.shape[1] != rank:
                    raise TaoMateLoRAError(f"TaoMate-H3 LoRA tensor shape differs for {target}")
                weight = module.weight
                out_features, in_features = _linear_shape(module)
                if a.shape[1] != in_features or b.shape[0] != out_features:
                    raise TaoMateLoRAError(
                        f"TaoMate-H3 LoRA {target}: A {tuple(a.shape)} / B {tuple(b.shape)} do not match the "
                        f"linear ({out_features}, {in_features}); tensor parallel is not supported by this adapter"
                    )
                # The adapter's fused-QKV ``lora_b`` is already in the merged
                # [Q; K; V] row order of the loaded base weight (the release
                # loader reorders only the grouped base checkpoint), so no
                # permutation is applied here.
                lora_a[target] = a.to(device=device, dtype=dtype).contiguous()
                lora_b[target] = b.to(device=device, dtype=dtype).contiguous()
                del weight
        adapter = cls(rank=rank, alpha=alpha, lora_a=lora_a, lora_b=lora_b, source=str(root))
        adapter.bind(transformer)
        logger.info(
            "TaoMate-H3 LoRA loaded from %s: rank=%d alpha=%g targets=%d dtype=%s",
            root,
            rank,
            alpha,
            len(targets),
            dtype,
        )
        return adapter

    def bind(self, transformer: nn.Module) -> None:
        """Install the forward hooks on every target linear."""
        self.unbind()
        modules = dict(transformer.named_modules())
        bound: list[str] = []
        for target in self.targets:
            module = modules[target]
            self._handles.append(module.register_forward_hook(self._make_hook(target)))
            bound.append(target)
        self._bound_targets = tuple(bound)

    def unbind(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        self._bound_targets = ()

    def _make_hook(self, target: str):
        lora_a = self._lora_a[target]
        lora_b = self._lora_b[target]
        scale = float(self.scale)
        adapter = self

        def hook(module: nn.Module, args: tuple, output):
            if not adapter.enabled:
                return None
            x = args[0]
            if isinstance(output, tuple):
                out = output[0]
            else:
                out = output
            flat = x.reshape(-1, x.shape[-1])
            delta = torch.matmul(torch.matmul(flat.to(lora_a.dtype), lora_a.t()), lora_b.t())
            if scale != 1.0:
                delta = delta * scale
            out.add_(delta.reshape(out.shape).to(out.dtype))
            return None

        return hook

    @contextmanager
    def disabled(self) -> Iterator[None]:
        """Run the base model without the adapter (the audio teacher path)."""
        previous = self.enabled
        self.enabled = False
        try:
            yield
        finally:
            self.enabled = previous

    def state_bytes(self) -> int:
        return sum(t.numel() * t.element_size() for t in self._lora_a.values()) + sum(
            t.numel() * t.element_size() for t in self._lora_b.values()
        )


def _linear_shape(module: nn.Module) -> tuple[int, int]:
    """(out_features, in_features) of a vLLM linear, robust to quantized layouts."""
    out_features = getattr(module, "output_size", None)
    in_features = getattr(module, "input_size", None)
    if out_features is None or in_features is None:
        weight = module.weight
        out_features, in_features = int(weight.shape[0]), int(weight.shape[1])
    return int(out_features), int(in_features)


__all__ = [
    "TAOMATE_LORA_TARGET_SUFFIXES",
    "TaoMateLoRAAdapter",
    "TaoMateLoRAError",
    "is_taomate_lora_dir",
    "taomate_lora_targets",
]

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

from dataclasses import dataclass

import torch
import torch.nn as nn

from vllm_omni.diffusion.models.minimax_h3.denoise_loop import MiniMaxH3DenoiseBranch

from .geometry import REQUEST_AUDIO_LATENTS, REQUEST_VIDEO_LATENTS, CanvasGeometry, StreamPlan
from .lora import TaoMateLoRAAdapter
from .packed import taomate_audio_only_frozen_prefix_packed_layout, taomate_audio_only_packed_layout
from .schedule import TEACHER_STATE_NUMBERS, euler_eta0_update_, teacher_sigmas

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
    audio = torch.randn(2 * REQUEST_AUDIO_LATENTS, AUDIO_ROW_WIDTH, generator=generator, dtype=torch.float32, device="cpu")
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
    ) -> None:
        self.transformer = transformer
        self.lora = lora
        self.device = device
        self.sigmas_video, self.sigmas_audio = teacher_sigmas()

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
        return branch

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
        with lora_scope:
            for step in range(steps):
                s_v, s_v_next = self.sigmas_video[step], self.sigmas_video[step + 1]
                s_a, s_a_next = self.sigmas_audio[step], self.sigmas_audio[step + 1]
                t_v, t_a = 1.0 - s_v, 1.0 - s_a
                forward_kwargs = branch.forward_kwargs(
                    video_rows=video_rows,
                    audio_rows=audio_rows,
                    t_video=t_v,
                    t_audio=t_a,
                    imgvid_cond_timestep=t_v,
                    audio_ref_cond_timestep=1.0,
                )
                _, velocity_audio = self.transformer(**forward_kwargs)
                velocity_target = velocity_audio.float()[target]
                target_rows = audio_rows[ref_rows:]
                euler_eta0_update_(target_rows, velocity_target, sigma_curr=s_a, sigma_next=s_a_next)
                state_number = step + 1
                if state_number in TEACHER_STATE_NUMBERS:
                    captured[state_number] = target_rows.detach().clone()
        milestones = [captured[number] for number in TEACHER_STATE_NUMBERS]
        return TeacherResult(milestones=milestones, audio_latent_count=active_audio_latents, forwards=steps)


class _NullScope:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


__all__ = ["ROLLOVER_LATENTS_PER_CHANNEL", "TaoMateAudioTeacher", "TeacherResult", "official_request_noise"]

===== FILE: /data/zhoutaichang/worldmodel/vllm-omni-taomate/vllm_omni/diffusion/models/taomate_h3/stream_decode.py =====
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM-Omni project
"""Incremental (per-phase) VAE decoding for TaoMate-H3 streaming.

Video
-----
The MiniMax-H3 video VAE decodes a latent timeline in temporal windows: window
``i`` reads latents ``[5i, 5i+7)``, decodes 28 frames, keeps frames ``[3, 20)``
as its 17 primary frames and frames ``[23, 28)`` as a five-frame overlap that is
linearly blended into the first five frames of window ``i+1``. TaoMate phases
add 12/10/10/5 latents (request 0) and 10/10/10/5 afterwards, so after every
phase all windows with ``5i + 7 <= latents_so_far`` decode exactly as a one-shot
decode would; each phase yields 34/34/34/17 frames and the newest window's
five-frame overlap is held until the next phase (or ``flush``). Frames are
native 24 fps, 119 per steady request.

All ranks of a tile-parallel VAE group call ``push`` collectively because the
checkpoint splits spatial tiles across the group.

Audio
-----
The audio VAE (40 latents/s, 800 samples per latent at 32 kHz) is decoded with
a sliding window of 48 latents of left context and 24 of right context, then
cropped to the samples aligned with the frames of the same phase.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from vllm_omni.diffusion.models.minimax_h3.vae import MiniMaxH3AudioVAE, MiniMaxH3VideoVAE
from vllm_omni.platforms import current_omni_platform

from .geometry import AUDIO_SAMPLE_RATE, AUDIO_SAMPLES_PER_LATENT, VIDEO_FPS

_TOKENS_PER_WINDOW = 5
_WINDOW_TOKENS = 7
_PRE_PAD = 3
_PRIMARY_FRAMES = 17
_OVERLAP_FRAMES = 5


def samples_at_frame(frame: int) -> int:
    return (frame * AUDIO_SAMPLE_RATE) // VIDEO_FPS


class StreamingVideoDecoder:
    """Stateful temporal-window decode through the pipeline's H3 video VAE."""

    def __init__(self, vae: MiniMaxH3VideoVAE, *, device: torch.device, height: int, width: int) -> None:
        self.vae = vae
        self.model = vae.model
        self.device = device
        self.height = int(height)
        self.width = int(width)
        expected = (_TOKENS_PER_WINDOW, _WINDOW_TOKENS - _TOKENS_PER_WINDOW, _PRE_PAD, _OVERLAP_FRAMES)
        actual = (
            int(self.model.tokens_chunk_size),
            int(self.model.token_overlap),
            int(self.model.frame_pre_padding),
            int(self.model.frame_overlap),
        )
        if actual != expected or self.model.isolated_first_frame or self.model.isolated_last_frame:
            raise RuntimeError(f"unexpected MiniMax-H3 video VAE temporal windowing {actual}")
        self.reset()

    def reset(self) -> None:
        self.latents: torch.Tensor | None = None  # denormalized [1, 24, T, H, W] fp32 on device
        self.base = 0  # global latent index of self.latents[:, :, 0]
        self.total = 0  # latents pushed so far
        self.next_window = 0
        self.overlap: torch.Tensor | None = None
        self.frames_emitted = 0

    def state_bytes(self, latent_h: int, latent_w: int) -> int:
        """Upper bound of resident latent and overlap buffers for one session."""
        latent_rows = 24 * (_WINDOW_TOKENS + 12) * latent_h * latent_w * 4
        overlap = 3 * _OVERLAP_FRAMES * self.height * self.width * 4
        return latent_rows + overlap

    def _to_uint8(self, frames: torch.Tensor) -> np.ndarray:
        # frames: [1, 3, T, H, W] in VAE output space -> [T, H, W, 3] uint8, cropped to the canvas
        reverted = self.vae._revert_decoded_inplace(frames.float())
        reverted = reverted[..., : self.height, : self.width]
        pixels = reverted[0].permute(1, 2, 3, 0).mul(255.0).round_().clamp_(0, 255).to(torch.uint8)
        return pixels.contiguous().cpu().numpy()

    def advance(self, latents: torch.Tensor) -> torch.Tensor | None:
        """Append ``[1, 24, n, H, W]`` normalized latents and decode every complete window."""
        visual = self.vae._denormalize_latent(latents.to(device=self.device, dtype=torch.float32))
        self.latents = visual if self.latents is None else torch.cat((self.latents, visual), dim=2)
        self.total += int(visual.shape[2])
        outputs: list[torch.Tensor] = []
        autocast = current_omni_platform.create_autocast_context(
            device_type=self.device.type,
            dtype=torch.float16,
            enabled=self.device.type == "cuda",
        )
        with torch.inference_mode(), autocast:
            while _TOKENS_PER_WINDOW * self.next_window + _WINDOW_TOKENS <= self.total:
                start = _TOKENS_PER_WINDOW * self.next_window - self.base
                clip = self.latents[:, :, start : start + _WINDOW_TOKENS]
                with self.vae._decode_tiling_context(clip):
                    decoded = self.model._adaptive_decode(clip)
                if int(decoded.shape[2]) != 4 * _WINDOW_TOKENS:
                    raise RuntimeError(f"video VAE window returned {decoded.shape[2]} frames")
                primary = decoded[:, :, _PRE_PAD : _PRE_PAD + _PRIMARY_FRAMES]
                overlap = decoded[:, :, 4 * _TOKENS_PER_WINDOW + _PRE_PAD :].contiguous()
                if self.overlap is not None:
                    primary = self.model.blend(self.overlap, primary, _OVERLAP_FRAMES, dim=-3)
                outputs.append(primary)
                self.overlap = overlap
                self.next_window += 1
                self.frames_emitted += _PRIMARY_FRAMES
            keep_from = _TOKENS_PER_WINDOW * self.next_window
            if keep_from > self.base:
                self.latents = self.latents[:, :, keep_from - self.base :].contiguous()
                self.base = keep_from
        return torch.cat(outputs, dim=2) if outputs else None

    def push(self, latents: torch.Tensor) -> tuple[int, np.ndarray | None]:
        """Collective: append latents; return ``(frame_start, uint8 [T, H, W, 3] or None)``."""
        frame_start = self.frames_emitted
        frames = self.advance(latents)
        if frames is None:
            return frame_start, None
        return frame_start, self._to_uint8(frames)

    def flush(self) -> tuple[int, np.ndarray | None]:
        """Emit the held five-frame overlap of the last window (end of a session)."""
        if self.overlap is None:
            return self.frames_emitted, None
        frame_start = self.frames_emitted
        frames = self._to_uint8(self.overlap)
        self.frames_emitted += _OVERLAP_FRAMES
        self.overlap = None
        return frame_start, frames


class StreamingAudioDecoder:
    """Sliding-window audio VAE decode aligned to emitted video frames."""

    def __init__(self, vae: MiniMaxH3AudioVAE, *, device: torch.device, left: int = 48, right: int = 24) -> None:
        self.vae = vae
        self.device = device
        self.left = int(left)
        self.right = int(right)
        if int(getattr(vae, "sample_rate", AUDIO_SAMPLE_RATE)) != AUDIO_SAMPLE_RATE:
            raise RuntimeError("MiniMax-H3 audio VAE sample rate differs from 32 kHz")
        self.reset()

    def reset(self) -> None:
        self.latents: torch.Tensor | None = None  # normalized [2, 32, L] fp32 on device
        self.base = 0
        self.total = 0

    def append(self, latents: torch.Tensor) -> None:
        """Append normalized clean audio latents ``[2, 32, L]``."""
        latents = latents.to(device=self.device, dtype=torch.float32)
        self.latents = latents if self.latents is None else torch.cat((self.latents, latents), dim=2)
        self.total += int(latents.shape[2])

    def decode_range(self, s0: int, s1: int) -> np.ndarray:
        """Return samples ``[s0, s1)`` as float32 ``[n, 2]``.

        The video timeline may outrun the generated audio by less than one
        latent at the end of a session (audio boundaries are rounded to 40 Hz
        latents); that tail is padded with silence rather than refused.
        """
        if s1 <= s0:
            return np.zeros((0, 2), dtype=np.float32)
        if self.latents is None:
            raise RuntimeError("no audio latents have been appended")
        available = self.total * AUDIO_SAMPLES_PER_LATENT
        if available < s1 - AUDIO_SAMPLES_PER_LATENT:
            raise RuntimeError("audio latents do not cover the requested samples")
        requested = s1 - s0
        s1 = min(s1, available)
        if s1 <= s0:
            return np.zeros((requested, 2), dtype=np.float32)
        l0 = max(self.base, s0 // AUDIO_SAMPLES_PER_LATENT - self.left)
        l1 = min(self.total, -(-s1 // AUDIO_SAMPLES_PER_LATENT) + self.right)
        window = self.latents[:, :, l0 - self.base : l1 - self.base]
        with torch.inference_mode():
            wave = self.vae.decode_latent(window)  # [1, 2, S]
        if wave.ndim != 3 or int(wave.shape[1]) != 2:
            raise RuntimeError(f"unexpected audio VAE output {tuple(wave.shape)}")
        if int(wave.shape[2]) != (l1 - l0) * AUDIO_SAMPLES_PER_LATENT:
            raise RuntimeError("audio VAE hop differs from 800 samples per latent")
        start = s0 - l0 * AUDIO_SAMPLES_PER_LATENT
        segment = wave[0, :, start : start + (s1 - s0)].float().transpose(0, 1).contiguous()
        keep_from = max(self.base, s1 // AUDIO_SAMPLES_PER_LATENT - self.left - 1)
        if keep_from > self.base:
            self.latents = self.latents[:, :, keep_from - self.base :].contiguous()
            self.base = keep_from
        samples = segment.cpu().numpy()
        if samples.shape[0] < requested:
            samples = np.concatenate((samples, np.zeros((requested - samples.shape[0], 2), np.float32)), axis=0)
        return samples

    def state_bytes(self) -> int:
        return 2 * 32 * (self.left + self.right + 2 * 210) * 4


def video_frames_to_payload(frames: np.ndarray | None) -> np.ndarray:
    if frames is None:
        return np.zeros((0, 1, 1, 3), dtype=np.uint8)
    return frames


__all__: list[Any] = [
    "StreamingAudioDecoder",
    "StreamingVideoDecoder",
    "samples_at_frame",
    "video_frames_to_payload",
]

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
from vllm_omni.diffusion.worker.input_batch import InputBatch
from vllm_omni.diffusion.worker.request_batch import DiffusionRequestBatch
from vllm_omni.diffusion.request import OmniDiffusionRequest
from vllm_omni.diffusion.worker.utils import StepRequestState
from vllm_omni.errors import OmniClientError
from vllm_omni.experimental.ar_diffusion.capability import ARDiffusionKVBranchSpec, ARDiffusionKVCacheSpec
from vllm_omni.experimental.ar_diffusion.kv_cache.state import ARDiffusionKVState
from vllm_omni.experimental.ar_diffusion.tick_protocol import ARDiffusionChunkMetadata
from vllm_omni.inputs.data import OmniDiffusionSamplingParams
from vllm_omni.model_executor.models.minimax_h3.conditioning import MiniMaxH3EncoderMediaInput
from vllm_omni.model_executor.models.minimax_h3.encoder_processing import PreparedEncoderInputs

from .attention import StreamContext, StreamMode, stream_context
from .audio_teacher import (
    ROLLOVER_LATENTS_PER_CHANNEL,
    TaoMateAudioTeacher,
    TeacherResult,
    official_request_noise,
)
from .geometry import (
    AUDIO_SAMPLE_RATE,
    PHASE_GROUP_COUNTS,
    REQUEST_AUDIO_LATENTS,
    REQUEST_NATIVE_FRAMES,
    REQUEST_VIDEO_LATENTS,
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
    max(request_plan(index).phases[phase].audio_latent_count for index in range(0, 8))
    for phase in range(NUM_PHASES)
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
            logger.info("TaoMate-H3 session %s: dropped %d audio KV rows at request %d", self.session_id, dropped, index)
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


class TaoMateH3Pipeline(MiniMaxH3Pipeline, SupportsStepExecution, InteractionMixin):
    """Streaming TaoMate-H3 on the AR-Diffusion runtime."""

    supports_step_execution: ClassVar[bool] = True
    # The three student steps of a phase run back to back; the scheduler regains
    # control at the phase boundary, where prompt interactions are applied.
    supports_chunk_step_grouping: ClassVar[bool] = True
    # Generic warmup cannot synthesize a session; the AR runner warms up lazily.
    dummy_run_num_frames: ClassVar[int] = 0
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
        self.taomate_lora: TaoMateLoRAAdapter | None = None
        self._tm_teacher: TaoMateAudioTeacher | None = None
        self._tm_sessions: dict[str, _Session] = {}
        self._ar_diffusion_kv_state: ARDiffusionKVState | None = None
        if getattr(self, "transformers_ref", None) is not None:
            raise ValueError("TaoMate-H3 serves the FL2VA partition only; do not load the Ref2VA DiT")
        if not self.load_text_encoder:
            raise ValueError("TaoMate-H3 encodes each request prompt locally; keep text_encoder loaded")

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
        self._tm_teacher = TaoMateAudioTeacher(self.transformer, lora=self.taomate_lora, device=self.device)
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
        return super().encode_prompt(prepared)

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
            session.close()
            torch.cuda.empty_cache() if torch.cuda.is_available() else None

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

        Streaming clients should use the WebSocket realtime endpoint; this path
        drives the same step contract to completion in one runner invocation and
        is what the AR-Diffusion runner uses for its load-time warmup.
        """
        if request.num_reqs != 1:
            raise OmniClientError("TaoMate-H3 request mode serves one request at a time")
        req = request.requests[0]
        state = StepRequestState(request_id=req.request_id, sampling=req.sampling_params, prompt=req.prompt)
        self.prepare_encode(state)
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
        """One five-second request that exercises every phase shape, the teacher and the decoders."""
        yield OmniDiffusionRequest(
            prompt="A presenter smiles at the camera and greets the audience warmly.",
            sampling_params=OmniDiffusionSamplingParams(
                num_frames=REQUEST_NATIVE_FRAMES,
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
                self.video_vae, device=self.device, height=canvas.height, width=canvas.width
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
        phase_index = state.chunk_index % NUM_PHASES
        if phase_index == 0:
            if state.prompt_embeds is None:
                raise RuntimeError("TaoMate-H3 request needs prompt embeddings")
            text_embeddings = state.prompt_embeds
            # The step runner batches prompt embeddings as [1, L, D]; TaoMate
            # packs plain text rows.
            if text_embeddings.ndim == 3 and text_embeddings.shape[0] == 1:
                text_embeddings = text_embeddings[0]
            if text_embeddings.ndim != 2:
                raise RuntimeError(f"TaoMate-H3 prompt embeddings must be [L, 5120], got {tuple(text_embeddings.shape)}")
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
        session = self._session(state)
        request = session.request
        phase_state = session.phase
        if request is None or phase_state is None or state.latents is None:
            raise RuntimeError("TaoMate-H3 denoise_step called before prepare_next_chunk")
        if request.teacher is None:
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
        with stream_context(session.stream_context(StreamMode.NOISY)), torch.inference_mode():
            velocity_video, _ = self.transformer(**forward_kwargs)
        session.stats["student_forwards"] += 1
        return velocity_video.float()

    def step_scheduler(self, state: StepRequestState, noise_pred: torch.Tensor, **kwargs: Any) -> None:
        del kwargs
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

        # Publish this phase: incremental video decode plus the aligned audio.
        latent = minimax_h3_unpatchify_video_tokens(
            clean_video,
            latent_shape=(phase.video_latent_count, session.canvas.latent_h // 2, session.canvas.latent_w // 2, 24),
            patch_size=(1, 2, 2),
        )
        frame_start, frames = session.video_decoder.push(latent)
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
        audio = session.audio_decoder.decode_range(
            samples_at_frame(frame_start), samples_at_frame(frame_start + num_frames)
        )
        session.frames_published = frame_start + num_frames
        payload: dict[str, Any] = {
            "video": frames if frames is not None else np.zeros((0, session.canvas.height, session.canvas.width, 3), np.uint8),
            "audio": audio,
        }
        metadata: dict[str, Any] = {
            "video": {"fps": float(VIDEO_FPS)},
            "audio": {"sample_rate": AUDIO_SAMPLE_RATE},
            "ar_diffusion": ARDiffusionChunkMetadata(
                session_id=state.request_id,
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
                "phase_seconds": round(time.perf_counter() - phase_state.started_at, 4),
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

===== FILE: external/TaoMate-H3/src/taomate_h3/streaming/attention_hook.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
"""Dense FlashAttention-3 hook for direct Stage3 streaming."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import torch

from .cache import AVKV, CleanAVKVCache


class HookMode(str, Enum):
    IDLE = "idle"
    NOISY = "noisy"
    CLEAN_COMMIT = "clean_commit"


@dataclass(frozen=True)
class _KVPart:
    key: torch.Tensor
    value: torch.Tensor


def _live_documents_from_mask(
    commit_mask: torch.Tensor,
    boundaries: Sequence[tuple[int, int]],
) -> tuple[int, ...]:
    live: list[int] = []
    for document_index, (start, stop) in enumerate(boundaries):
        if bool(commit_mask[start:stop].any().item()):
            live.append(document_index)
    return tuple(live)


class H3StreamingAttentionHook:
    """Condition current media on text, persistent clean AV KV, and current KV."""

    def __init__(self, cache: CleanAVKVCache, *, backend: str = "flash_attn_3") -> None:
        if backend != "flash_attn_3":
            raise ValueError("the accelerated direct runtime requires FlashAttention-3")
        try:
            from flash_attn_interface import flash_attn_func
        except ImportError as exc:
            raise RuntimeError("FlashAttention-3 kernels are required") from exc
        self.cache = cache
        self._flash_attention = flash_attn_func
        self.kernel_calls = 0
        self.query_tokens = 0
        self.key_tokens = 0
        self.mode = HookMode.IDLE
        self._live_documents: tuple[int, ...] | None = None
        self._live_document_rows: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}

    def receipt(self) -> dict[str, object]:
        return {
            "backend": "flash_attn_3_dense",
            "tensor_layout": "NHD",
            "is_causal": False,
            "kernel_calls": self.kernel_calls,
            "query_tokens": self.query_tokens,
            "key_tokens": self.key_tokens,
        }

    def _attention(
        self,
        query: torch.Tensor,
        parts: Sequence[_KVPart],
        *,
        scale: float,
    ) -> torch.Tensor:
        if not parts:
            raise RuntimeError("attention requires at least one KV part")
        key = (
            parts[0].key if len(parts) == 1 else torch.cat(tuple(part.key for part in parts), dim=0)
        )
        value = (
            parts[0].value
            if len(parts) == 1
            else torch.cat(tuple(part.value for part in parts), dim=0)
        )
        output = self._flash_attention(
            query.unsqueeze(0),
            key.unsqueeze(0),
            value.unsqueeze(0),
            softmax_scale=scale,
            causal=False,
            num_splits=1,
        )
        if isinstance(output, tuple):
            output = output[0]
        self.kernel_calls += 1
        self.query_tokens += int(query.shape[0])
        self.key_tokens += int(key.shape[0])
        return output.squeeze(0)

    @property
    def active(self) -> bool:
        return self.mode is not HookMode.IDLE

    def activate(self, mode: HookMode) -> None:
        if self.active:
            raise RuntimeError("streaming attention hook is already active")
        if mode not in (HookMode.NOISY, HookMode.CLEAN_COMMIT):
            raise ValueError(f"unsupported streaming hook mode: {mode}")
        self.mode = mode
        self._live_documents = None
        self._live_document_rows.clear()

    def deactivate(self) -> None:
        self.mode = HookMode.IDLE
        self._live_documents = None
        self._live_document_rows.clear()

    def __call__(
        self,
        *,
        attention: object,
        layer_name: str,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        token_tags: torch.Tensor,
        commit_mask: torch.Tensor,
        cu_seqlens_host: Sequence[int],
    ) -> torch.Tensor:
        if not self.active:
            raise RuntimeError("streaming attention hook was called while inactive")
        self._validate_qkv(layer_name, query, key, value)
        if commit_mask.ndim != 1 or commit_mask.shape[0] != query.shape[0]:
            raise RuntimeError(f"{layer_name}: commit_mask does not match packed QKV rows")
        if token_tags.ndim != 1 or token_tags.shape[0] != query.shape[0]:
            raise RuntimeError(f"{layer_name}: token_tags does not match packed QKV rows")

        points = tuple(int(point) for point in cu_seqlens_host)
        if (
            len(points) < 2
            or points[0] != 0
            or points[-1] != query.shape[0]
            or any(left > right for left, right in zip(points, points[1:]))
        ):
            raise RuntimeError(f"{layer_name}: invalid packed sequence boundaries")
        boundaries = tuple(zip(points[:-1], points[1:]))

        if self._live_documents is None:
            self._live_documents = _live_documents_from_mask(
                commit_mask,
                boundaries,
            )
            if len(self._live_documents) != 1:
                raise RuntimeError(
                    "direct streaming expects exactly one live document, got "
                    f"{self._live_documents}"
                )
        live_document = self._live_documents[0]
        scale = float(getattr(attention, "softmax_scale"))
        persistent: AVKV | None = self.cache.history(layer_name)
        outputs: list[torch.Tensor] = []

        for document_index, (start, stop) in enumerate(boundaries):
            if start == stop:
                continue
            q_document = query[start:stop]
            k_document = key[start:stop]
            v_document = value[start:stop]
            if document_index != live_document:
                outputs.append(
                    self._attention(
                        q_document,
                        (_KVPart(k_document, v_document),),
                        scale=scale,
                    )
                )
                continue

            rows = self._live_document_rows.get(document_index)
            if rows is None:
                media_mask = commit_mask[start:stop].to(torch.bool)
                condition_indices = torch.nonzero(~media_mask, as_tuple=False).flatten()
                media_indices = torch.nonzero(media_mask, as_tuple=False).flatten()
                rows = (condition_indices, media_indices)
                self._live_document_rows[document_index] = rows
            condition_indices, media_indices = rows
            if condition_indices.numel() == 0 or media_indices.numel() == 0:
                raise RuntimeError("live streaming document must contain condition and media rows")

            condition_key = k_document.index_select(0, condition_indices)
            condition_value = v_document.index_select(0, condition_indices)
            condition_output = self._attention(
                q_document.index_select(0, condition_indices),
                (_KVPart(condition_key, condition_value),),
                scale=scale,
            )

            media_parts = [_KVPart(condition_key, condition_value)]
            if persistent is not None:
                media_parts.append(_KVPart(persistent.key, persistent.value))
            media_parts.append(
                _KVPart(
                    k_document.index_select(0, media_indices),
                    v_document.index_select(0, media_indices),
                )
            )
            media_output = self._attention(
                q_document.index_select(0, media_indices),
                media_parts,
                scale=scale,
            )

            document_output = torch.zeros_like(q_document)
            document_output.index_copy_(0, condition_indices, condition_output)
            document_output.index_copy_(0, media_indices, media_output)
            outputs.append(document_output)

        output = torch.cat(outputs, dim=0)
        if self.mode is HookMode.CLEAN_COMMIT:
            self.cache.stage(layer_name, key, value, token_tags, commit_mask)
        return output

    def _validate_qkv(
        self,
        layer_name: str,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
    ) -> None:
        contract = self.cache.contract
        expected_tail = (contract.local_heads, contract.head_dim)
        if query.shape != key.shape or value.shape != key.shape or key.ndim != 3:
            raise RuntimeError(f"{layer_name}: query/key/value must have matching rank-3 shapes")
        if tuple(key.shape[1:]) != expected_tail:
            raise RuntimeError(
                f"{layer_name}: expected local attention tail {expected_tail}, "
                f"got {tuple(key.shape[1:])}"
            )
        if (
            query.dtype != contract.dtype
            or key.dtype != contract.dtype
            or value.dtype != contract.dtype
        ):
            raise RuntimeError(f"{layer_name}: streaming attention requires {contract.dtype} QKV")
        if (
            query.device.type != contract.device_type
            or key.device.type != contract.device_type
            or value.device.type != contract.device_type
        ):
            raise RuntimeError(
                f"{layer_name}: streaming attention requires {contract.device_type} QKV"
            )

===== FILE: external/TaoMate-H3/src/taomate_h3/streaming/cache.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
"""Persistent clean audio/video KV cache for direct Stage3 streaming."""

from __future__ import annotations

from dataclasses import dataclass

import torch

MAIN_LAYER_NAMES = tuple(f"blocks.{index}.attn" for index in range(50))
VIDEO_TOKEN_TAG = 0
AUDIO_TOKEN_TAG = 2


@dataclass(frozen=True)
class KVContract:
    """Shape contract for the local attention shard."""

    local_heads: int = 14
    head_dim: int = 128
    dtype: torch.dtype = torch.bfloat16
    device_type: str = "cuda"


def kv_contract_from_model(model: object) -> KVContract:
    """Build the KV shape contract from an installed MiniMax-H3 model."""

    blocks = getattr(model, "blocks", None)
    if blocks is None:
        raise RuntimeError("model does not expose transformer blocks")
    layers = len(blocks)
    if layers != len(MAIN_LAYER_NAMES):
        raise RuntimeError(f"expected {len(MAIN_LAYER_NAMES)} transformer layers, got {layers}")

    architecture = getattr(model, "arch", None)
    context = getattr(model, "parallel_context", None)
    total_heads = int(getattr(architecture, "num_attention_heads", 0))
    head_dim = int(getattr(architecture, "attention_head_dim", 0))
    tp_size = int(getattr(context, "tp_world_size", 0))
    ulysses_size = int(getattr(context, "ulysses_world_size", 0))
    parallel_size = tp_size * ulysses_size
    if total_heads <= 0 or head_dim <= 0 or parallel_size <= 0 or total_heads % parallel_size:
        raise RuntimeError("model topology cannot resolve post-Ulysses local KV heads")
    return KVContract(
        local_heads=total_heads // parallel_size,
        head_dim=head_dim,
    )


@dataclass(frozen=True)
class AVKV:
    """Dense BF16 clean audio/video keys and values for one attention layer."""

    key: torch.Tensor
    value: torch.Tensor


def _validate_av_pair(pair: AVKV, contract: KVContract, *, layer_name: str) -> None:
    expected_tail = (contract.local_heads, contract.head_dim)
    if pair.key.ndim != 3 or tuple(pair.key.shape[1:]) != expected_tail:
        raise RuntimeError(
            f"{layer_name}: expected key shape [tokens, {expected_tail[0]}, {expected_tail[1]}], "
            f"got {tuple(pair.key.shape)}"
        )
    if pair.value.shape != pair.key.shape:
        raise RuntimeError(f"{layer_name}: key/value shape mismatch")
    if pair.key.dtype != contract.dtype or pair.value.dtype != contract.dtype:
        raise RuntimeError(f"{layer_name}: persistent KV must be {contract.dtype}")
    if (
        pair.key.device.type != contract.device_type
        or pair.value.device.type != contract.device_type
    ):
        raise RuntimeError(f"{layer_name}: persistent KV must reside on {contract.device_type}")


class CleanAVKVCache:
    """Transactional persistent cache containing clean media KV only.

    Clean commits append one small streaming chunk. Retention preserves the first
    video's rows as a long-term sink and the two most recent clean chunks.
    """

    def __init__(self, contract: KVContract) -> None:
        self.contract = contract
        self._history: dict[str, AVKV] = {}
        self._staged: dict[str, AVKV] = {}
        self._staged_block: int | None = None
        self._staged_tags: tuple[int, ...] | None = None
        self._staged_indices: torch.Tensor | None = None
        self._block_index = 0
        self._commit_token_counts: list[int] = []
        self._commit_token_tags: list[tuple[int, ...]] = []

    @property
    def committed_blocks(self) -> int:
        """Logical number of clean chunks committed since the last clear."""

        return self._block_index

    @property
    def history_tokens(self) -> int:
        if not self._history:
            return 0
        return int(next(iter(self._history.values())).key.shape[0])

    @property
    def history_audio_tokens(self) -> int:
        return sum(tag == AUDIO_TOKEN_TAG for tags in self._commit_token_tags for tag in tags)

    @property
    def history_video_tokens(self) -> int:
        return sum(tag == VIDEO_TOKEN_TAG for tags in self._commit_token_tags for tag in tags)

    @property
    def clean_commit_active(self) -> bool:
        return self._staged_block is not None

    def history(self, layer_name: str) -> AVKV | None:
        self._validate_layer_name(layer_name)
        return self._history.get(layer_name)

    def begin_clean_commit(self, block_index: int) -> None:
        if self.clean_commit_active:
            raise RuntimeError("a clean KV commit is already active")
        if block_index != self._block_index:
            raise RuntimeError(f"expected clean chunk {self._block_index}, got {block_index}")
        self._staged_block = block_index
        self._staged.clear()
        self._staged_tags = None
        self._staged_indices = None

    def stage(
        self,
        layer_name: str,
        key: torch.Tensor,
        value: torch.Tensor,
        token_tags: torch.Tensor,
        commit_mask: torch.Tensor,
    ) -> None:
        """Stage clean audio/video rows produced by one transformer layer."""

        if not self.clean_commit_active:
            raise RuntimeError("begin_clean_commit() must be called before stage()")
        self._validate_layer_name(layer_name)
        if layer_name in self._staged:
            raise RuntimeError(f"{layer_name}: KV was staged more than once")
        if key.shape != value.shape or key.ndim != 3:
            raise RuntimeError(f"{layer_name}: key/value must have matching rank-3 shapes")
        if token_tags.ndim != 1 or commit_mask.ndim != 1:
            raise RuntimeError("token_tags and commit_mask must be rank-1")
        if token_tags.shape[0] != key.shape[0] or commit_mask.shape[0] != key.shape[0]:
            raise RuntimeError(f"{layer_name}: packed metadata length does not match KV rows")

        if self._staged_indices is None:
            indices = torch.nonzero(commit_mask.to(torch.bool), as_tuple=False).flatten()
            if indices.numel() == 0:
                raise RuntimeError("clean commit did not contain audio/video rows")
            selected_tags = token_tags.index_select(0, indices)
            tags = tuple(int(tag) for tag in selected_tags.detach().cpu().tolist())
            if frozenset(tags) != frozenset((VIDEO_TOKEN_TAG, AUDIO_TOKEN_TAG)):
                raise RuntimeError("each clean chunk must contain both video and audio KV")
            self._staged_indices = indices
            self._staged_tags = tags

        indices = self._staged_indices
        assert indices is not None
        pair = AVKV(
            key=key.index_select(0, indices).detach(),
            value=value.index_select(0, indices).detach(),
        )
        _validate_av_pair(pair, self.contract, layer_name=layer_name)
        self._staged[layer_name] = pair

    def commit(self) -> None:
        """Atomically append all staged layers to persistent history."""

        if not self.clean_commit_active:
            raise RuntimeError("no clean KV commit is active")
        missing = [name for name in MAIN_LAYER_NAMES if name not in self._staged]
        if missing:
            raise RuntimeError(f"clean KV commit is missing {len(missing)} transformer layers")
        assert self._staged_tags is not None
        token_count = len(self._staged_tags)

        # Update one layer at a time so old and new 50-layer caches are never
        # resident together at the direct-inference steady-state memory peak.
        for layer_name in MAIN_LAYER_NAMES:
            current = self._staged.pop(layer_name)
            previous = self._history.pop(layer_name, None)
            if previous is None:
                combined = current
            else:
                combined = AVKV(
                    key=torch.cat((previous.key, current.key), dim=0),
                    value=torch.cat((previous.value, current.value), dim=0),
                )
            _validate_av_pair(combined, self.contract, layer_name=layer_name)
            self._history[layer_name] = combined

        self._commit_token_counts.append(token_count)
        self._commit_token_tags.append(self._staged_tags)
        self._block_index += 1
        self._clear_staging()

    def retain_sink_and_recent_commits(self) -> None:
        """Keep the first chunk's video sink and the most recent clean chunks."""

        if self.clean_commit_active:
            raise RuntimeError("cannot trim persistent KV during an active clean commit")
        block_count = len(self._commit_token_counts)
        # As soon as three clean chunks exist, age chunk zero to a video-only
        # sink and keep chunks one and two as the two complete AV recents.
        if block_count <= 2:
            return

        recent_start = max(1, block_count - 2)
        selection = [(0, True)] + [(index, False) for index in range(recent_start, block_count)]
        self._retain_commit_rows(selection)

    def drop_audio_history(self) -> int:
        """Remove audio rows while preserving every retained video row."""

        if self.clean_commit_active:
            raise RuntimeError("cannot drop audio history during an active clean commit")
        removed_tokens = self.history_audio_tokens
        if not self._commit_token_counts:
            return 0
        self._retain_commit_rows([(index, True) for index in range(len(self._commit_token_counts))])
        return removed_tokens

    def rollback(self) -> None:
        """Discard the currently staged clean chunk."""

        self._clear_staging()

    def clear(self) -> None:
        """Clear persistent and staged KV and reset the logical chunk count."""

        self._history.clear()
        self._commit_token_counts.clear()
        self._commit_token_tags.clear()
        self._block_index = 0
        self._clear_staging()

    def _retain_commit_rows(self, selection: list[tuple[int, bool]]) -> None:
        offsets = [0]
        for count in self._commit_token_counts:
            offsets.append(offsets[-1] + count)

        selected_rows: list[int] = []
        selected_counts: list[int] = []
        selected_tags: list[tuple[int, ...]] = []
        for block_index, video_only in selection:
            tags = self._commit_token_tags[block_index]
            start = offsets[block_index]
            local_rows = [
                i for i, tag in enumerate(tags) if not video_only or tag == VIDEO_TOKEN_TAG
            ]
            if not local_rows:
                continue
            selected_rows.extend(start + row for row in local_rows)
            kept_tags = tuple(tags[row] for row in local_rows)
            selected_counts.append(len(kept_tags))
            selected_tags.append(kept_tags)

        if not selected_rows:
            self._history.clear()
            self._commit_token_counts.clear()
            self._commit_token_tags.clear()
            return

        next_history: dict[str, AVKV] = {}
        for layer_name, pair in self._history.items():
            indices = torch.tensor(selected_rows, dtype=torch.long, device=pair.key.device)
            retained = AVKV(
                key=pair.key.index_select(0, indices),
                value=pair.value.index_select(0, indices),
            )
            _validate_av_pair(retained, self.contract, layer_name=layer_name)
            next_history[layer_name] = retained
        self._history = next_history
        self._commit_token_counts = selected_counts
        self._commit_token_tags = selected_tags

    def _clear_staging(self) -> None:
        self._staged.clear()
        self._staged_block = None
        self._staged_tags = None
        self._staged_indices = None

    def _validate_layer_name(self, layer_name: str) -> None:
        if layer_name not in MAIN_LAYER_NAMES:
            raise KeyError(f"unexpected transformer layer: {layer_name}")

===== FILE: external/TaoMate-H3/src/taomate_h3/streaming/runtime.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterator

from ..config import DIRECT_POLICY
from ..inference import ExternalBase10TeacherArtifact
from .cache import CleanAVKVCache, kv_contract_from_model
from .geometry import (
    StreamPhase,
    canonical_continuation_plan,
    direct_5s_plan,
    video_temporal_position,
    video_temporal_positions,
)
from .session import H3StreamingSession


@dataclass(frozen=True)
class StreamingPhaseExecution:
    phase_index: int
    frame_start: int
    frame_stop: int
    video_latent_start: int
    video_latent_stop: int
    audio_latent_start: int
    audio_latent_stop: int
    denoise_forwards: int
    clean_forwards: int
    committed_history_tokens: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StreamingExecution:
    phase_executions: tuple[StreamingPhaseExecution, ...]
    video_latent_offset: int = 0
    audio_latent_offset: int = 0
    starting_history_tokens: int = 0
    retained_history_tokens: int = 0
    cross_request_kv_reused: bool = False
    request_index: int = 0
    audio_kv_reset_applied: bool = False
    audio_kv_reset_tokens: int = 0
    starting_history_audio_tokens: int = 0
    starting_history_video_tokens: int = 0
    retained_history_audio_tokens: int = 0
    retained_history_video_tokens: int = 0
    native_frame_offset: int = 0
    published_native_frames: int = 0
    video_transport_prefix_latents: int = 0
    audio_transport_prefix_latents_per_channel: int = 0
    published_video_latents: int = 0
    published_audio_latents_per_channel: int = 0
    current_text_token_count: int = 0
    text_time_start: float = 0.0
    fixed_media_time_origin: int = 0
    position_capture: dict[str, object] | None = None
    audio_teacher: dict[str, object] | None = None
    attention_backend: dict[str, object] | None = None

    @property
    def phase_count(self) -> int:
        return len(self.phase_executions)

    @property
    def denoise_forwards(self) -> int:
        return sum(item.denoise_forwards for item in self.phase_executions)

    @property
    def clean_forwards(self) -> int:
        return sum(item.clean_forwards for item in self.phase_executions)

    def to_dict(self) -> dict[str, object]:
        return {
            "phase_count": self.phase_count,
            "denoise_forwards": self.denoise_forwards,
            "clean_forwards": self.clean_forwards,
            "video_latent_offset": self.video_latent_offset,
            "audio_latent_offset": self.audio_latent_offset,
            "starting_history_tokens": self.starting_history_tokens,
            "retained_history_tokens": self.retained_history_tokens,
            "cross_request_kv_reused": self.cross_request_kv_reused,
            "request_index": self.request_index,
            "audio_kv_reset_applied": self.audio_kv_reset_applied,
            "audio_kv_reset_tokens": self.audio_kv_reset_tokens,
            "starting_history_audio_tokens": self.starting_history_audio_tokens,
            "starting_history_video_tokens": self.starting_history_video_tokens,
            "retained_history_audio_tokens": self.retained_history_audio_tokens,
            "retained_history_video_tokens": self.retained_history_video_tokens,
            "native_frame_offset": self.native_frame_offset,
            "published_native_frames": self.published_native_frames,
            "video_transport_prefix_latents": (self.video_transport_prefix_latents),
            "audio_transport_prefix_latents_per_channel": (
                self.audio_transport_prefix_latents_per_channel
            ),
            "published_video_latents": self.published_video_latents,
            "published_audio_latents_per_channel": (self.published_audio_latents_per_channel),
            "current_text_token_count": self.current_text_token_count,
            "text_time_start": self.text_time_start,
            "fixed_media_time_origin": self.fixed_media_time_origin,
            "position_capture": self.position_capture,
            "audio_teacher": self.audio_teacher,
            "attention_backend": self.attention_backend,
            "phases": [item.to_dict() for item in self.phase_executions],
        }


def _required_tensor(value: Any, name: str) -> Any:
    import torch

    if not torch.is_tensor(value):
        raise TypeError(f"{name} must be a torch.Tensor")
    return value


def _resolve_spatial_latent_shape(
    positive: Any,
    *,
    frame_rows: int,
) -> tuple[int, int]:
    """Recover the exact target latent canvas from official absolute positions."""

    import torch

    position_ids = _required_tensor(
        positive.img_position_ids,
        "positive.img_position_ids",
    )
    target_info = positive.static_kwargs.get("img_pos_for_infer_output_info")
    if not isinstance(target_info, dict):
        raise TypeError("img_pos_for_infer_output_info must be a mapping")
    target_ids = _required_tensor(
        target_info.get("position_ids"),
        "img_pos_for_infer_output_info.position_ids",
    ).view(-1)
    if position_ids.ndim != 3 or int(position_ids.shape[0]) != 1:
        raise ValueError("official H3 img_position_ids must be [1, sequence, 3]")
    with torch.no_grad():
        target_grid = position_ids[0].index_select(
            0, target_ids.to(device=position_ids.device, dtype=torch.long)
        )
        latent_h = int(torch.unique(target_grid[:, 1]).numel()) * 2
        latent_w = int(torch.unique(target_grid[:, 2]).numel()) * 2
    if (latent_h // 2) * (latent_w // 2) != frame_rows:
        raise RuntimeError("official H3 spatial RoPE grid and target packed-row count disagree")
    return latent_h, latent_w


def _current_prompt_rope_start(
    *,
    text_len: int,
    media_time_origin: int,
    video_latent_offset: int,
) -> float:
    """Right-align the current prompt to the global request media origin."""

    return float(media_time_origin + video_temporal_position(video_latent_offset) - text_len)


def build_streaming_phase_packed_layout(
    *,
    positive: Any,
    phase: StreamPhase,
    latent_h: int,
    latent_w: int,
    text_token_tags: Any,
    media_time_origin: int,
    video_latent_offset: int,
    audio_latent_offset: int,
) -> dict[str, Any]:
    """Build one future-free T2VA chunk on the global canonical timeline."""

    import torch

    from taomate_h3.model.packed_sequence import minimax_h3_packed_sequence

    prompt_embeds = _required_tensor(
        positive.static_kwargs.get("prompt_embeds"),
        "positive.static_kwargs['prompt_embeds']",
    )
    text_len = int(prompt_embeds.shape[0])
    packed = minimax_h3_packed_sequence(
        text_len=text_len,
        latent_t=phase.video_latent_count,
        latent_h=latent_h,
        latent_w=latent_w,
        audio_t=phase.audio_latent_count,
        audio_channel=2,
    )
    text_pos = _required_tensor(packed.get("text_pos"), "text_pos").view(-1)
    tags = _required_tensor(packed.get("token_tags"), "token_tags")
    if list(text_token_tags.shape) != [text_len]:
        raise ValueError("text token tags do not match prompt embeddings")
    tags[text_pos] = text_token_tags.to(device=tags.device, dtype=tags.dtype)

    grid = _required_tensor(packed.get("img_position_ids"), "img_position_ids")
    img_pos = _required_tensor(packed.get("img_pos"), "img_pos").view(-1)
    target_pos = img_pos
    frame_rows = (latent_h // 2) * (latent_w // 2)
    if int(target_pos.numel()) != phase.video_latent_count * frame_rows:
        raise RuntimeError("chunk video rows do not match its latent geometry")

    prompt_start = _current_prompt_rope_start(
        text_len=text_len,
        media_time_origin=media_time_origin,
        video_latent_offset=video_latent_offset,
    )
    grid[text_pos, 0] = prompt_start + torch.arange(text_len, dtype=grid.dtype, device=grid.device)
    video_positions = video_temporal_positions(
        video_latent_offset + phase.video_latent_start,
        phase.video_latent_count,
    )
    video_times = torch.tensor(
        [float(media_time_origin + position) for position in video_positions],
        dtype=grid.dtype,
    )
    grid[target_pos, 0] = video_times.repeat_interleave(frame_rows)

    audio_pos = _required_tensor(packed.get("audio_pos"), "audio_pos").view(
        2, phase.audio_latent_count
    )
    audio_times = media_time_origin + torch.arange(
        audio_latent_offset + phase.audio_latent_start,
        audio_latent_offset + phase.audio_latent_stop,
        dtype=grid.dtype,
    )
    grid[audio_pos[0], 0] = audio_times
    grid[audio_pos[1], 0] = audio_times
    packed["_taomate_h3_position_capture"] = {
        "text_count": text_len,
        "text_time_start": prompt_start,
        "text_time_stop": prompt_start + text_len,
        "request_media_time_start": float(
            media_time_origin + video_temporal_position(video_latent_offset)
        ),
        "phase_video_time_start": float(video_times[0]),
        "phase_audio_time_start": float(audio_times[0]),
    }
    return packed


def _build_phase_branch(
    *,
    positive: Any,
    phase: StreamPhase,
    latent_h: int,
    latent_w: int,
    model: Any,
    device: Any,
    text_token_tags: Any,
    media_time_origin: int,
    video_latent_offset: int,
    audio_latent_offset: int,
) -> Any:
    import torch

    packed = build_streaming_phase_packed_layout(
        positive=positive,
        phase=phase,
        latent_h=latent_h,
        latent_w=latent_w,
        text_token_tags=text_token_tags,
        media_time_origin=media_time_origin,
        video_latent_offset=video_latent_offset,
        audio_latent_offset=audio_latent_offset,
    )
    position_capture = packed.pop("_taomate_h3_position_capture")
    prompt_embeds = _required_tensor(
        positive.static_kwargs.get("prompt_embeds"),
        "positive.static_kwargs['prompt_embeds']",
    )
    branch = type(positive)(
        packed=packed,
        text_embeddings=prompt_embeds,
        token_tags=packed["token_tags"],
        device=device,
        parallel_context=model.parallel_context,
    )
    with torch.no_grad():
        branch.static_kwargs["rope_cache"] = model.build_rope_cache(
            branch.img_position_ids, device=device
        )
    branch._taomate_h3_position_capture = position_capture
    return branch


def _resolve_global_text_token_tags(positive: Any) -> Any:
    """Recover official text/vision AdaLN tags before rebuilding phase layouts."""

    import torch

    prompt_embeds = _required_tensor(
        positive.static_kwargs.get("prompt_embeds"),
        "positive.static_kwargs['prompt_embeds']",
    )
    text_len = int(prompt_embeds.shape[0])
    local_tags = _required_tensor(
        positive.static_kwargs.get("block_token_tags"),
        "positive.static_kwargs['block_token_tags']",
    ).view(-1)
    seq_len = int(getattr(positive, "seq_len", 0))
    if seq_len <= 0:
        raise ValueError("official H3 branch sequence length is invalid")
    if int(local_tags.numel()) == seq_len:
        global_tags = local_tags
    else:
        from taomate_h3.distributed import ulysses_all_gather_rows

        global_tags = ulysses_all_gather_rows(
            local_tags.view(-1, 1), context=positive.parallel_context
        ).view(-1)
    if int(global_tags.numel()) != seq_len or text_len > seq_len:
        raise RuntimeError("official H3 global token-tag reconstruction differs")
    tags = global_tags[:text_len].detach().to(device="cpu", dtype=torch.long)
    if bool(((tags != 0) & (tags != 1)).any().item()):
        raise ValueError("H3 prompt rows contain unsupported streaming token tags")
    return tags


def _teacher_phase_audio_rows(
    rows: Any,
    *,
    phase: StreamPhase,
    total_audio_latents: int,
) -> Any:
    return (
        rows.view(2, total_audio_latents, -1)[:, phase.audio_latent_start : phase.audio_latent_stop]
        .contiguous()
        .view(-1, int(rows.shape[-1]))
    )


def _base_audio_teacher_step_callback(
    teacher: dict[str, Any],
    *,
    phase: StreamPhase,
    total_audio_latents: int,
) -> Callable[[int, Any, Any], None]:
    """Inject the request-wide Base10 milestone used by one Stage3 loop."""

    milestones = teacher["milestones"]

    def on_step(step_index: int, video_rows: Any, audio_rows: Any) -> None:
        milestone = milestones.get(step_index)
        if milestone is not None:
            teacher_rows = _teacher_phase_audio_rows(
                milestone,
                phase=phase,
                total_audio_latents=total_audio_latents,
            )
            audio_rows.copy_(teacher_rows)

    return on_step


@contextmanager
def _native_attention_metadata(
    branch: Any,
) -> Iterator[None]:
    """Bind full-sequence modality tags and target-media commit rows."""

    import torch

    from taomate_h3.distributed import ulysses_all_gather_rows
    from taomate_h3.model.layers import native_stream_attention_metadata

    tags = _required_tensor(branch.static_kwargs.get("block_token_tags"), "block_token_tags").view(
        -1
    )
    if int(tags.numel()) != int(branch.seq_len):
        tags = ulysses_all_gather_rows(tags.view(-1, 1), context=branch.parallel_context).view(-1)
    if int(tags.numel()) != int(branch.seq_len):
        raise RuntimeError("native H3 streaming token tags do not cover the sequence")
    mask = torch.zeros(int(branch.seq_len), dtype=torch.bool, device=tags.device)
    mask.index_fill_(0, branch.img_target_seq_idx.to(tags.device), True)
    mask.index_fill_(0, branch.audio_target_seq_idx.to(tags.device), True)
    with native_stream_attention_metadata(tags, mask):
        yield


def _phase_initial_rows(
    *,
    initial_video_rows: Any,
    initial_audio_rows: Any,
    phase: StreamPhase,
    frame_rows: int,
    total_audio_latents: int,
) -> tuple[Any, Any]:
    video = initial_video_rows[
        phase.video_latent_start * frame_rows : phase.video_latent_stop * frame_rows
    ].contiguous()
    audio = initial_audio_rows.view(2, total_audio_latents, -1)[
        :, phase.audio_latent_start : phase.audio_latent_stop
    ].contiguous()
    return video, audio.view(-1, int(audio.shape[-1]))


def _join_phase_audio(rows: list[Any], phases: tuple[StreamPhase, ...]) -> Any:
    import torch

    by_channel: list[list[Any]] = [[], []]
    for value, phase in zip(rows, phases):
        current = value.view(2, phase.audio_latent_count, -1)
        by_channel[0].append(current[0])
        by_channel[1].append(current[1])
    return torch.cat(
        (torch.cat(by_channel[0], dim=0), torch.cat(by_channel[1], dim=0)),
        dim=0,
    )


class H3StreamingRuntime:
    """Split each T2VA request into small phases with persistent clean AV-KV."""

    def __init__(self, *, base10_teacher: ExternalBase10TeacherArtifact) -> None:
        self.plan = direct_5s_plan()
        self.executions: list[StreamingExecution] = []
        self._running = False
        self._cache: CleanAVKVCache | None = None
        self._media_time_origin: int | None = None
        self._request_index = 0
        self._native_frame_offset = 0
        self._video_latent_offset = 0
        self._audio_latent_offset = 0
        self._canonical_transport_video_rows: Any | None = None
        self._canonical_transport_audio_rows: Any | None = None
        self._prefix_renorm_video_anchor: tuple[Any, Any] | None = None
        self._base10_teacher = base10_teacher
        self._dit_cuda_events: list[tuple[Any, Any]] = []
        self._dit_noisy_calls = 0
        self._dit_clean_calls = 0

    def release_retained_state(self) -> None:
        """Release cross-request CUDA state after the final generated chunk."""

        if self._running:
            raise RuntimeError("cannot release streaming state during generation")
        if self._cache is not None:
            self._cache.clear()
            self._cache = None
        self._canonical_transport_video_rows = None
        self._canonical_transport_audio_rows = None
        self._prefix_renorm_video_anchor = None

    def _renorm_clean_video_rows(self, rows: Any) -> Any:
        """Match generated blocks to persistent block-zero statistics."""

        current = rows.detach().float()
        mean = current.mean(dim=0, keepdim=True)
        std = current.std(dim=0, keepdim=True, unbiased=False).clamp_min(1e-6)
        if self._prefix_renorm_video_anchor is None:
            self._prefix_renorm_video_anchor = (mean, std)
            return rows
        anchor_mean, anchor_std = self._prefix_renorm_video_anchor
        normalized = (current - mean).div(std).mul(anchor_std).add(anchor_mean)
        return normalized.to(dtype=rows.dtype)

    def dit_timing_receipt(self) -> dict[str, float | int]:
        """Return synchronized Transformer-only CUDA time across all ranks."""

        import torch

        torch.cuda.synchronize()
        local_seconds = sum(
            float(start.elapsed_time(stop)) for start, stop in self._dit_cuda_events
        ) / 1000.0
        maximum = torch.tensor(local_seconds, dtype=torch.float64, device="cuda")
        torch.distributed.all_reduce(maximum, op=torch.distributed.ReduceOp.MAX)
        return {
            "noisy_calls": self._dit_noisy_calls,
            "clean_kv_calls": self._dit_clean_calls,
            "total_calls": self._dit_noisy_calls + self._dit_clean_calls,
            "cuda_seconds": float(maximum.item()),
        }

    def run(self, **kwargs: Any) -> Any:
        import torch

        from taomate_h3.model.denoise import minimax_h3_denoise_loop

        if self._running:
            raise RuntimeError("one H3 streaming runtime cannot run concurrent requests")
        self._running = True
        try:
            model = kwargs["model"]
            positive = kwargs["positive"]
            initial_video = _required_tensor(kwargs["initial_video_rows"], "initial_video_rows")
            initial_audio = _required_tensor(kwargs["initial_audio_rows"], "initial_audio_rows")
            request_index = self._request_index
            canonical_continuation = request_index > 0
            active_plan = (
                canonical_continuation_plan(
                    self.plan,
                    request_index=request_index,
                )
                if canonical_continuation
                else self.plan
            )
            official_video_latents = self.plan.phases[-1].video_latent_stop
            official_audio_latents = self.plan.phases[-1].audio_latent_stop
            total_video_latents = active_plan.phases[-1].video_latent_stop
            total_audio_latents = active_plan.phases[-1].audio_latent_stop
            video_transport_prefix_latents = official_video_latents - total_video_latents
            audio_transport_prefix_latents = official_audio_latents - total_audio_latents
            target_video_rows = int(initial_video.shape[0])
            if target_video_rows <= 0 or target_video_rows % official_video_latents:
                raise ValueError("request target video rows do not match the stream plan")
            frame_rows = target_video_rows // official_video_latents
            if list(initial_audio.shape) != [2 * official_audio_latents, 32]:
                raise ValueError(
                    "request audio rows do not match cumulative 40 Hz phase boundaries"
                )
            latent_h, latent_w = _resolve_spatial_latent_shape(
                positive,
                frame_rows=frame_rows,
            )
            if list(initial_video.shape) != [official_video_latents * frame_rows, 96]:
                raise ValueError("direct streaming accepts T2VA target rows only")
            request_video_rows = initial_video
            transport_video_rows = None
            transport_audio_rows = None
            if canonical_continuation:
                transport_video_rows = self._canonical_transport_video_rows
                transport_audio_rows = self._canonical_transport_audio_rows
                if transport_video_rows is None or list(transport_video_rows.shape) != [
                    video_transport_prefix_latents * frame_rows,
                    96,
                ]:
                    raise RuntimeError(
                        "canonical continuation has no exact prior video transport prefix"
                    )
                if transport_audio_rows is None:
                    raise RuntimeError("canonical continuation has no prior audio transport prefix")
                previous_audio_t = int(transport_audio_rows.shape[0]) // 2
                if list(transport_audio_rows.shape) != [2 * previous_audio_t, 32] or (
                    previous_audio_t < audio_transport_prefix_latents
                ):
                    raise RuntimeError(
                        "canonical continuation has no exact prior audio transport prefix"
                    )
                request_video_rows = request_video_rows[
                    video_transport_prefix_latents * frame_rows :
                ].contiguous()
                initial_audio_by_channel = initial_audio.view(2, official_audio_latents, -1)
                initial_audio = (
                    initial_audio_by_channel[:, audio_transport_prefix_latents:]
                    .contiguous()
                    .view(-1, int(initial_audio.shape[-1]))
                )
            text_token_tags = _resolve_global_text_token_tags(positive)
            text_len = int(
                _required_tensor(
                    positive.static_kwargs.get("prompt_embeds"),
                    "positive.static_kwargs['prompt_embeds']",
                ).shape[0]
            )
            media_time_origin = (
                text_len if self._media_time_origin is None else self._media_time_origin
            )
            device = initial_video.device
            if device.type != "cpu":
                raise ValueError("official H3 initial noise must enter denoise from CPU")
            cuda_device = torch.device("cuda")

            sigmas_video = list(kwargs["sigmas_video"])
            sigmas_audio = list(kwargs["sigmas_audio"])
            if len(sigmas_video) != len(sigmas_audio) or len(sigmas_video) < 2:
                raise ValueError("H3 video/audio sigma schedules must match")
            phase_video_outputs: list[Any] = []
            phase_audio_outputs: list[Any] = []
            phase_records: list[StreamingPhaseExecution] = []
            position_capture: dict[str, object] = {"phases": []}
            phases = active_plan.phases
            cache = self._cache
            if cache is None:
                cache = CleanAVKVCache(kv_contract_from_model(model))
                self._cache = cache
            audio_kv_reset_applied = (
                request_index > 0
                and request_index % DIRECT_POLICY.audio_kv_reset_window_requests == 0
            )
            audio_kv_reset_tokens = cache.drop_audio_history() if audio_kv_reset_applied else 0
            starting_history_tokens = cache.history_tokens
            starting_history_audio_tokens = cache.history_audio_tokens
            starting_history_video_tokens = cache.history_video_tokens
            reused_kv = starting_history_tokens > 0
            current_prompt_rope_start = _current_prompt_rope_start(
                text_len=text_len,
                media_time_origin=media_time_origin,
                video_latent_offset=self._video_latent_offset,
            )
            audio_teacher = self._base10_teacher.load_request(
                torch,
                request_index=request_index,
                audio_latent_count=total_audio_latents,
                device=cuda_device,
            )

            with H3StreamingSession(
                active_plan,
                cache=cache,
            ) as session:
                for phase in phases:
                    branch = _build_phase_branch(
                        positive=positive,
                        phase=phase,
                        latent_h=latent_h,
                        latent_w=latent_w,
                        model=model,
                        device=cuda_device,
                        text_token_tags=text_token_tags,
                        media_time_origin=media_time_origin,
                        video_latent_offset=self._video_latent_offset,
                        audio_latent_offset=self._audio_latent_offset,
                    )
                    position_capture["phases"].append(
                        {
                            "phase_index": phase.index,
                            **dict(branch._taomate_h3_position_capture),
                        }
                    )
                    phase_video, phase_audio = _phase_initial_rows(
                        initial_video_rows=request_video_rows,
                        initial_audio_rows=initial_audio,
                        phase=phase,
                        frame_rows=frame_rows,
                        total_audio_latents=total_audio_latents,
                    )

                    def noisy_forward(
                        active_model: Any,
                        call_kwargs: dict[str, Any],
                        step_index: int,
                        active_phase_index: int = phase.index,
                        active_branch: Any = branch,
                    ) -> tuple[Any, Any]:
                        del step_index
                        cuda_start = torch.cuda.Event(enable_timing=True)
                        cuda_stop = torch.cuda.Event(enable_timing=True)
                        with (
                            session.noisy_step(active_phase_index),
                            _native_attention_metadata(active_branch),
                        ):
                            cuda_start.record()
                            result = active_model(**call_kwargs)
                            cuda_stop.record()
                        self._dit_cuda_events.append((cuda_start, cuda_stop))
                        self._dit_noisy_calls += 1
                        return result

                    phase_on_step = _base_audio_teacher_step_callback(
                        audio_teacher,
                        phase=phase,
                        total_audio_latents=total_audio_latents,
                    )

                    generated_video, generated_audio = minimax_h3_denoise_loop(
                        model=model,
                        model_forward=noisy_forward,
                        positive=branch,
                        initial_video_rows=phase_video,
                        initial_audio_rows=phase_audio,
                        sigmas_video=sigmas_video,
                        sigmas_audio=sigmas_audio,
                        device=cuda_device,
                        on_step=phase_on_step,
                    )

                    clean_phase_video = self._renorm_clean_video_rows(
                        generated_video,
                    )
                    generated_video.copy_(clean_phase_video)
                    history_before_commit = session.cache.history_tokens

                    clean_timestep = branch.prepare_timestep_plan(
                        video_timesteps=[1.0],
                        audio_timesteps=[1.0],
                    )[0]
                    clean_kwargs = branch.forward_kwargs(
                        video_rows=generated_video,
                        audio_rows=generated_audio,
                        step_timesteps=clean_timestep,
                    )
                    with (
                        session.clean_commit(phase.index),
                        _native_attention_metadata(branch),
                        torch.no_grad(),
                    ):
                        clean_kwargs["streaming_cache_only"] = True
                        cuda_start = torch.cuda.Event(enable_timing=True)
                        cuda_stop = torch.cuda.Event(enable_timing=True)
                        cuda_start.record()
                        model(**clean_kwargs)
                        cuda_stop.record()
                        self._dit_cuda_events.append((cuda_start, cuda_stop))
                        self._dit_clean_calls += 1

                    expected_history_tokens = history_before_commit + (
                        phase.video_latent_count * frame_rows + 2 * phase.audio_latent_count
                    )
                    if session.cache.history_tokens != expected_history_tokens:
                        raise RuntimeError(
                            "clean H3 KV history does not match the committed "
                            f"AV phase boundary: {session.cache.history_tokens} != "
                            f"{expected_history_tokens}"
                        )

                    session.cache.retain_sink_and_recent_commits()
                    phase_video_outputs.append(clean_phase_video)
                    phase_audio_outputs.append(generated_audio)
                    phase_records.append(
                        StreamingPhaseExecution(
                            phase_index=phase.index,
                            frame_start=phase.frame_start,
                            frame_stop=phase.frame_stop,
                            video_latent_start=phase.video_latent_start,
                            video_latent_stop=phase.video_latent_stop,
                            audio_latent_start=phase.audio_latent_start,
                            audio_latent_stop=phase.audio_latent_stop,
                            denoise_forwards=len(sigmas_video) - 1,
                            clean_forwards=1,
                            committed_history_tokens=session.cache.history_tokens,
                        )
                    )

            attention_receipt = session.hook.receipt()
            joined_video = torch.cat(phase_video_outputs, dim=0)
            joined_audio = _join_phase_audio(phase_audio_outputs, phases)
            if joined_video.shape != request_video_rows.shape:
                raise RuntimeError("reassembled streaming video rows changed request shape")
            if joined_audio.shape != initial_audio.shape:
                raise RuntimeError("reassembled streaming audio rows changed request shape")
            final_teacher = audio_teacher["milestones"][2]
            if not torch.equal(joined_audio, final_teacher):
                raise RuntimeError(
                    "published streaming audio differs from Base teacher clean latent"
                )
            audio_teacher_receipt = dict(audio_teacher["receipt"])
            audio_teacher_receipt["published_clean_audio_exact_match"] = True
            returned_video = joined_video
            returned_audio = joined_audio
            if canonical_continuation:
                returned_video = torch.cat(
                    (
                        transport_video_rows.to(
                            device=joined_video.device,
                            dtype=joined_video.dtype,
                        ),
                        joined_video,
                    ),
                    dim=0,
                )
                previous_audio = transport_audio_rows.view(2, -1, int(joined_audio.shape[-1]))[
                    :, -audio_transport_prefix_latents:
                ]
                returned_audio = (
                    torch.cat(
                        (
                            previous_audio.to(
                                device=joined_audio.device,
                                dtype=joined_audio.dtype,
                            ),
                            joined_audio.view(2, total_audio_latents, int(joined_audio.shape[-1])),
                        ),
                        dim=1,
                    )
                    .contiguous()
                    .view(-1, int(joined_audio.shape[-1]))
                )
            self._canonical_transport_video_rows = (
                joined_video[-2 * frame_rows :]
                .detach()
                .to(device="cpu", dtype=torch.float32)
                .contiguous()
            )
            audio_by_channel = joined_audio.view(
                2, total_audio_latents, int(joined_audio.shape[-1])
            )
            self._canonical_transport_audio_rows = (
                audio_by_channel[:, -min(9, total_audio_latents) :]
                .detach()
                .to(device="cpu", dtype=torch.float32)
                .contiguous()
                .view(-1, int(joined_audio.shape[-1]))
            )
            retained_history_tokens = cache.history_tokens
            retained_history_audio_tokens = cache.history_audio_tokens
            retained_history_video_tokens = cache.history_video_tokens
            self._media_time_origin = media_time_origin
            execution = StreamingExecution(
                phase_executions=tuple(phase_records),
                video_latent_offset=self._video_latent_offset,
                audio_latent_offset=self._audio_latent_offset,
                starting_history_tokens=starting_history_tokens,
                retained_history_tokens=retained_history_tokens,
                cross_request_kv_reused=reused_kv,
                request_index=request_index,
                audio_kv_reset_applied=audio_kv_reset_applied,
                audio_kv_reset_tokens=audio_kv_reset_tokens,
                starting_history_audio_tokens=starting_history_audio_tokens,
                starting_history_video_tokens=starting_history_video_tokens,
                retained_history_audio_tokens=retained_history_audio_tokens,
                retained_history_video_tokens=retained_history_video_tokens,
                native_frame_offset=self._native_frame_offset,
                published_native_frames=active_plan.native_frame_count,
                video_transport_prefix_latents=(video_transport_prefix_latents),
                audio_transport_prefix_latents_per_channel=(audio_transport_prefix_latents),
                published_video_latents=total_video_latents,
                published_audio_latents_per_channel=total_audio_latents,
                current_text_token_count=text_len,
                text_time_start=current_prompt_rope_start,
                fixed_media_time_origin=media_time_origin,
                position_capture=position_capture,
                audio_teacher=audio_teacher_receipt,
                attention_backend=attention_receipt,
            )
            self.executions.append(execution)
            self._video_latent_offset += total_video_latents
            self._audio_latent_offset += total_audio_latents
            self._native_frame_offset += active_plan.native_frame_count
            self._request_index += 1
            if returned_video.shape != initial_video.shape:
                raise RuntimeError("streaming output no longer matches official request rows")
            if list(returned_audio.shape) != [2 * official_audio_latents, 32]:
                raise RuntimeError("streaming audio output no longer matches official request rows")
            return returned_video, returned_audio
        finally:
            self._running = False


__all__ = [
    "H3StreamingRuntime",
]

===== FILE: external/TaoMate-H3/src/taomate_h3/streaming/geometry.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction

VIDEO_FPS = 24
AUDIO_LATENT_RATE = 40
VIDEO_PREFIX_FRAMES = 5
VIDEO_PREFIX_LATENTS = 2
VIDEO_GROUP_FRAMES = 17
VIDEO_GROUP_LATENTS = 5


def _round_half_even(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    doubled = remainder * 2
    if doubled < value.denominator:
        return quotient
    if doubled > value.denominator:
        return quotient + 1
    return quotient + (quotient & 1)


def _audio_latent_boundary(frame: int) -> int:
    return _round_half_even(Fraction(frame * AUDIO_LATENT_RATE, VIDEO_FPS))


def canonical_continuation_plan(
    base_plan: StreamPlan,
    *,
    request_index: int,
) -> StreamPlan:
    """Build the true steady-state target geometry after request zero.

    The standalone H3 request owns a five-frame/two-latent affine prefix.  A
    continuation does not generate that prefix again: it advances seven native
    17-frame groups (35 video latents), while audio boundaries are rounded on
    the global frame timeline.  Consequently the per-request audio target is
    198 or 199 latents rather than a repeated request-local 207.
    """

    if not isinstance(base_plan, StreamPlan):
        raise TypeError("base_plan must be a StreamPlan")
    if isinstance(request_index, bool) or not isinstance(request_index, int):
        raise TypeError("request_index must be an integer")
    if request_index <= 0:
        raise ValueError("canonical continuation requires request_index > 0")
    if base_plan.native_frame_count <= VIDEO_PREFIX_FRAMES:
        raise ValueError("base stream has no steady continuation geometry")

    steady_frame_count = base_plan.native_frame_count - VIDEO_PREFIX_FRAMES
    global_frame_start = base_plan.native_frame_count + (request_index - 1) * steady_frame_count
    global_audio_start = _audio_latent_boundary(global_frame_start)

    phases: list[StreamPhase] = []
    frame_stop = 0
    video_stop = 0
    for index, base_phase in enumerate(base_plan.phases):
        frame_start = frame_stop
        video_start = video_stop
        frame_stop += base_phase.group_count * VIDEO_GROUP_FRAMES
        video_stop += base_phase.group_count * VIDEO_GROUP_LATENTS
        phases.append(
            StreamPhase(
                index=index,
                group_count=base_phase.group_count,
                frame_start=frame_start,
                frame_stop=frame_stop,
                video_latent_start=video_start,
                video_latent_stop=video_stop,
                audio_latent_start=(
                    _audio_latent_boundary(global_frame_start + frame_start) - global_audio_start
                ),
                audio_latent_stop=(
                    _audio_latent_boundary(global_frame_start + frame_stop) - global_audio_start
                ),
            )
        )
    return StreamPlan(
        native_frame_count=steady_frame_count,
        phases=tuple(phases),
    )


def video_temporal_position(latent_index: int) -> Fraction:
    """Absolute H3 RoPE time coordinate before the request text-origin offset."""

    if isinstance(latent_index, bool) or not isinstance(latent_index, int):
        raise TypeError("latent_index must be an integer")
    if latent_index < 0:
        raise ValueError("latent_index must be non-negative")
    weights = (1, 4, 4, 4, 4)
    return sum(
        (Fraction(5, 3) * weights[index % len(weights)] for index in range(latent_index)),
        start=Fraction(0),
    )


def video_temporal_positions(start: int, count: int) -> tuple[Fraction, ...]:
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("count must be a positive integer")
    return tuple(video_temporal_position(index) for index in range(start, start + count))


@dataclass(frozen=True)
class StreamPhase:
    index: int
    group_count: int
    frame_start: int
    frame_stop: int
    video_latent_start: int
    video_latent_stop: int
    audio_latent_start: int
    audio_latent_stop: int

    @property
    def frame_count(self) -> int:
        return self.frame_stop - self.frame_start

    @property
    def duration(self) -> Fraction:
        return Fraction(self.frame_count, VIDEO_FPS)

    @property
    def video_latent_count(self) -> int:
        return self.video_latent_stop - self.video_latent_start

    @property
    def audio_latent_count(self) -> int:
        return self.audio_latent_stop - self.audio_latent_start

    @property
    def video_rope_start(self) -> Fraction:
        return video_temporal_position(self.video_latent_start)

    @property
    def audio_rope_start(self) -> int:
        return self.audio_latent_start

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value.update(
            duration_numerator=self.duration.numerator,
            duration_denominator=self.duration.denominator,
            duration_seconds=float(self.duration),
            video_rope_start_numerator=self.video_rope_start.numerator,
            video_rope_start_denominator=self.video_rope_start.denominator,
            audio_rope_start=self.audio_rope_start,
        )
        return value


@dataclass(frozen=True)
class StreamPlan:
    native_frame_count: int
    phases: tuple[StreamPhase, ...]

    @property
    def duration(self) -> Fraction:
        return Fraction(self.native_frame_count, VIDEO_FPS)

    def to_dict(self) -> dict[str, object]:
        return {
            "native_frame_count": self.native_frame_count,
            "duration_seconds": float(self.duration),
            "phase_count": len(self.phases),
            "phases": [phase.to_dict() for phase in self.phases],
        }


def direct_5s_plan() -> StreamPlan:
    """Return the validated four-chunk plan for one five-second request."""

    native_frame_count = 124
    phases: list[StreamPhase] = []
    frame_stop = 0
    video_stop = 0
    for index, groups in enumerate((2, 2, 2, 1)):
        frame_start = frame_stop
        video_start = video_stop
        frame_stop += groups * VIDEO_GROUP_FRAMES
        video_stop += groups * VIDEO_GROUP_LATENTS
        if index == 0:
            frame_stop += VIDEO_PREFIX_FRAMES
            video_stop += VIDEO_PREFIX_LATENTS
        phases.append(
            StreamPhase(
                index=index,
                group_count=groups,
                frame_start=frame_start,
                frame_stop=frame_stop,
                video_latent_start=video_start,
                video_latent_stop=video_stop,
                audio_latent_start=_audio_latent_boundary(frame_start),
                audio_latent_stop=_audio_latent_boundary(frame_stop),
            )
        )
    return StreamPlan(native_frame_count=native_frame_count, phases=tuple(phases))


__all__ = [
    "StreamPhase",
    "StreamPlan",
    "canonical_continuation_plan",
    "direct_5s_plan",
    "video_temporal_position",
    "video_temporal_positions",
]

===== FILE: external/TaoMate-H3/src/taomate_h3/model/denoise.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
"""Native MiniMax H3 cfg-distilled audio-video denoise loop.

The released algorithm is implemented directly around TaoMate-H3's explicit
local ``ParallelContext``.
"""

from __future__ import annotations

from typing import Any, Callable

import torch

from taomate_h3.distributed import ParallelContext

from .architecture import MINIMAX_H3_ADALN_MODALITY_NUM

_VIDEO_ROW_WIDTH = 96
_AUDIO_ROW_WIDTH = 32


@torch.no_grad()
def _minimax_h3_update_target_rows_(
    state: torch.Tensor,
    velocity: torch.Tensor,
    *,
    sigma_t: torch.Tensor,
    sigma_ratio: torch.Tensor,
    one_minus_sigma_ratio: torch.Tensor,
    denoised_scratch: torch.Tensor,
) -> None:
    torch.mul(sigma_t, velocity, out=denoised_scratch)
    torch.add(state, denoised_scratch, out=denoised_scratch)
    torch.mul(one_minus_sigma_ratio, denoised_scratch, out=velocity)
    torch.mul(sigma_ratio, state, out=state)
    torch.add(state, velocity, out=state)


def _build_local_embedding_layout(
    *,
    seq_len: int,
    text_pos: torch.Tensor,
    img_pos: torch.Tensor,
    audio_pos: torch.Tensor,
    world_size: int,
    rank: int,
    device: torch.device,
) -> dict[str, torch.Tensor | int]:
    if seq_len % world_size:
        raise ValueError(
            f"packed seq_len {seq_len} not divisible by Ulysses world size {world_size}"
        )
    local_seq_len = seq_len // world_size
    row_start = rank * local_seq_len
    row_stop = row_start + local_seq_len

    def local_ids(pos: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        source_ids = torch.nonzero(
            (pos >= row_start) & (pos < row_stop),
            as_tuple=False,
        ).view(-1)
        return source_ids.to(device), pos.index_select(0, source_ids).to(device)

    text_source_start = min(row_start, int(text_pos.shape[0]))
    text_source_stop = min(row_stop, int(text_pos.shape[0]))
    _, img_global_ids = local_ids(img_pos)
    _, audio_global_ids = local_ids(audio_pos)
    return {
        "text_source_start": text_source_start,
        "text_source_stop": text_source_stop,
        "img_global_ids": img_global_ids,
        "img_row_ids": img_global_ids - row_start,
        "audio_global_ids": audio_global_ids,
        "audio_row_ids": audio_global_ids - row_start,
    }


class MiniMaxH3DenoiseBranch:
    """Static positive-branch packed state and step-local forward inputs."""

    def __init__(
        self,
        *,
        packed: dict[str, Any],
        text_embeddings: torch.Tensor,
        token_tags: torch.Tensor,
        device: torch.device,
        parallel_context: ParallelContext,
    ) -> None:
        seq_len = int(packed["seq_len"])
        self.seq_len = seq_len
        self.img_pos = packed["img_pos"].view(-1).to(torch.long)
        self.audio_pos = packed["audio_pos"].view(-1).to(torch.long)
        self.audio_update_mask = packed.get(
            "audio_update_mask",
            torch.ones(self.audio_pos.shape[0], dtype=torch.bool),
        ).view(-1).to(torch.bool)
        if self.audio_update_mask.shape[0] != self.audio_pos.shape[0]:
            raise ValueError("audio update mask differs from packed audio rows")
        self.audio_target_start = int((~self.audio_update_mask).sum())
        if not torch.all(self.audio_update_mask[self.audio_target_start :]):
            raise ValueError("audio reference rows must form one frozen prefix")
        self.audio_target_slice = slice(self.audio_target_start, None)

        text_pos = packed["text_pos"].view(-1).to(torch.long)
        text_len = int(text_pos.shape[0])
        if int(text_embeddings.shape[0]) != text_len:
            raise ValueError(
                f"text_embeddings rows {list(text_embeddings.shape)} != packed text_len {text_len}"
            )
        if int(token_tags.view(-1).shape[0]) != seq_len:
            raise ValueError(
                f"token_tags length {int(token_tags.view(-1).shape[0])} != seq_len {seq_len}"
            )
        cu = packed["cu_seqlens"].to(torch.int32)
        self.img_pos_dev = self.img_pos.to(device)
        self.audio_pos_dev = self.audio_pos.to(device)
        self.audio_update_mask_dev = self.audio_update_mask.to(device)
        self.img_target_seq_idx = self.img_pos_dev
        self.audio_target_seq_idx = self.audio_pos_dev[self.audio_update_mask_dev]
        self.audio_ref_seq_idx = self.audio_pos_dev[~self.audio_update_mask_dev]
        self.x_buffer = torch.zeros(
            1,
            seq_len,
            _VIDEO_ROW_WIDTH,
            dtype=torch.float32,
            device=device,
        )
        self.audio_x_buffer = torch.zeros(
            1,
            seq_len,
            _AUDIO_ROW_WIDTH,
            dtype=torch.float32,
            device=device,
        )
        self.parallel_context = parallel_context
        ulysses_world_size = parallel_context.ulysses_world_size
        ulysses_rank = parallel_context.ulysses_rank
        if seq_len % ulysses_world_size:
            raise ValueError(
                f"packed seq_len {seq_len} not divisible by Ulysses world size {ulysses_world_size}"
            )
        token_tags_host = token_tags.view(-1).to(dtype=torch.long)
        # Native streaming attention needs the complete tag vector before the
        # Ulysses-local slice is moved to the device.
        local_seq_len = seq_len // ulysses_world_size
        local_row_start = ulysses_rank * local_seq_len
        local_row_stop = local_row_start + local_seq_len
        self.local_row_slice = slice(local_row_start, local_row_stop)
        self.block_token_tags = (
            token_tags_host[local_row_start:local_row_stop].clamp(min=0).to(device)
        )
        self.img_position_ids = packed["img_position_ids"][None].to(
            device=device,
            dtype=torch.float32,
        )
        self.static_kwargs: dict[str, Any] = {
            "block_token_tags": self.block_token_tags,
            "prompt_embeds": text_embeddings.to(device),
            "img_pos_info": {"position_ids": self.img_pos_dev},
            "audio_pos_info": {"position_ids": self.audio_pos_dev},
            "img_pos_for_infer_output_info": {"position_ids": self.img_target_seq_idx},
            "local_embedding_layout": _build_local_embedding_layout(
                seq_len=seq_len,
                text_pos=text_pos,
                img_pos=self.img_pos,
                audio_pos=self.audio_pos,
                world_size=ulysses_world_size,
                rank=ulysses_rank,
                device=device,
            ),
            "packed_seq_params": {
                "cu_seqlens_q_host": tuple(int(value) for value in cu.tolist()),
                "max_seqlen_q": int(cu[1]),
            },
        }
        self.refiner_cu_seqlens = torch.tensor(
            [0, text_len, text_len], dtype=torch.int32, device=device
        )

    def forward_kwargs(
        self,
        *,
        video_rows: torch.Tensor,
        audio_rows: torch.Tensor,
        step_timesteps: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    ) -> dict[str, Any]:
        x = self.x_buffer
        audio_x = self.audio_x_buffer
        x[0].index_copy_(0, self.img_pos_dev, video_rows)
        audio_x[0].index_copy_(0, self.audio_pos_dev, audio_rows)
        unique_timesteps, inverse_indices, block_combined_indices = step_timesteps
        return {
            **self.static_kwargs,
            "x": x,
            "audio_x": audio_x,
            "unique_timesteps": unique_timesteps,
            "inverse_indices": inverse_indices,
            "block_combined_indices": block_combined_indices,
        }

    def _expand_step_timesteps(
        self,
        *,
        t_video: float,
        t_audio: float,
        inverse_indices_by_pattern: dict[tuple[int, ...], torch.Tensor],
        block_combined_by_pattern: dict[tuple[int, ...], torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # Text, padding and video rows use the video clock; all audio rows use
        # the audio clock.  Keeping torch.unique here preserves the reference
        # float32 ordering and inverse-index construction exactly.
        candidates = [float(t_video), float(t_audio)]
        audio_ref_slot: int | None = None
        if self.audio_ref_seq_idx.numel() > 0:
            audio_ref_slot = len(candidates)
            candidates.append(1.0)
        unique_cpu, slot_to_unique = torch.unique(
            torch.tensor(candidates, dtype=torch.float32),
            sorted=True,
            return_inverse=True,
        )
        device = self.img_pos_dev.device
        base_index = int(slot_to_unique[0])
        pattern = tuple(slot_to_unique.tolist())
        inverse_indices = inverse_indices_by_pattern.get(pattern)
        if inverse_indices is None:
            inverse_indices = torch.full(
                (self.seq_len,), base_index, dtype=torch.long, device=device
            )
            inverse_indices.index_fill_(0, self.audio_target_seq_idx, int(slot_to_unique[1]))
            if audio_ref_slot is not None:
                inverse_indices.index_fill_(
                    0,
                    self.audio_ref_seq_idx,
                    int(slot_to_unique[audio_ref_slot]),
                )
            inverse_indices_by_pattern[pattern] = inverse_indices
        block_combined = block_combined_by_pattern.get(pattern)
        if block_combined is None:
            block_combined = torch.add(
                self.block_token_tags,
                inverse_indices[self.local_row_slice],
                alpha=MINIMAX_H3_ADALN_MODALITY_NUM,
            )
            block_combined_by_pattern[pattern] = block_combined
        return unique_cpu.to(device), inverse_indices, block_combined

    def prepare_timestep_plan(
        self,
        *,
        video_timesteps: list[float],
        audio_timesteps: list[float],
    ) -> list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
        if len(video_timesteps) != len(audio_timesteps):
            raise ValueError("video/audio timestep plans must have equal length")
        inverse_indices_by_pattern: dict[tuple[int, ...], torch.Tensor] = {}
        block_combined_by_pattern: dict[tuple[int, ...], torch.Tensor] = {}
        return [
            self._expand_step_timesteps(
                t_video=t_video,
                t_audio=t_audio,
                inverse_indices_by_pattern=inverse_indices_by_pattern,
                block_combined_by_pattern=block_combined_by_pattern,
            )
            for t_video, t_audio in zip(video_timesteps, audio_timesteps)
        ]


def minimax_h3_denoise_loop(
    *,
    model: Any,
    positive: MiniMaxH3DenoiseBranch,
    initial_video_rows: torch.Tensor,
    initial_audio_rows: torch.Tensor,
    sigmas_video: list[float],
    sigmas_audio: list[float],
    device: torch.device,
    model_forward: (
        Callable[[Any, dict[str, Any], int], tuple[torch.Tensor, torch.Tensor]] | None
    ) = None,
    on_step: Callable[[int, torch.Tensor, torch.Tensor], None] | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Run positive-only MiniMax H3 Euler-eta0 denoising for video and audio."""

    if len(sigmas_video) != len(sigmas_audio):
        raise ValueError("video/audio sigma schedules must have equal length")
    if len(sigmas_video) < 2:
        raise ValueError("sigma schedules need at least 2 entries")
    video_rows = initial_video_rows.to(device=device, dtype=torch.float32, copy=True)
    audio_rows = initial_audio_rows.to(device=device, dtype=torch.float32, copy=True)
    if int(video_rows.shape[0]) != int(positive.img_pos.shape[0]):
        raise ValueError(
            f"initial video rows {int(video_rows.shape[0])} != positive layout "
            f"rows {int(positive.img_pos.shape[0])}"
        )
    if int(audio_rows.shape[0]) != int(positive.audio_pos.shape[0]):
        raise ValueError(
            f"initial audio rows {int(audio_rows.shape[0])} != positive layout "
            f"rows {int(positive.audio_pos.shape[0])}"
        )
    video_timesteps = [1.0 - sigma for sigma in sigmas_video[:-1]]
    audio_timesteps = [1.0 - sigma for sigma in sigmas_audio[:-1]]
    video_step_t = torch.tensor(video_timesteps, dtype=torch.float32, device=device)
    audio_step_t = torch.tensor(audio_timesteps, dtype=torch.float32, device=device)
    timestep_plan = positive.prepare_timestep_plan(
        video_timesteps=video_timesteps,
        audio_timesteps=audio_timesteps,
    )
    video_sigmas = torch.tensor(sigmas_video, dtype=torch.float32, device=device)
    audio_sigmas = torch.tensor(sigmas_audio, dtype=torch.float32, device=device)
    video_sigma_ratios = video_sigmas[1:] / video_sigmas[:-1]
    audio_sigma_ratios = audio_sigmas[1:] / audio_sigmas[:-1]
    video_sigma_t = 1.0 - video_step_t
    audio_sigma_t = 1.0 - audio_step_t
    video_one_minus_sigma_ratios = 1.0 - video_sigma_ratios
    audio_one_minus_sigma_ratios = 1.0 - audio_sigma_ratios
    video_denoised_scratch = torch.empty_like(video_rows)
    audio_target_slice = positive.audio_target_slice
    audio_denoised_scratch = torch.empty_like(audio_rows[audio_target_slice])
    for step in range(len(sigmas_video) - 1):
        forward_kwargs = positive.forward_kwargs(
            video_rows=video_rows,
            audio_rows=audio_rows,
            step_timesteps=timestep_plan[step],
        )
        if model_forward is None:
            velocity_video, velocity_audio = model(**forward_kwargs)
        else:
            velocity_video, velocity_audio = model_forward(model, forward_kwargs, step)
        velocity_video = velocity_video.float()
        velocity_audio = velocity_audio[audio_target_slice].float()
        _minimax_h3_update_target_rows_(
            video_rows,
            velocity_video,
            sigma_t=video_sigma_t[step],
            sigma_ratio=video_sigma_ratios[step],
            one_minus_sigma_ratio=video_one_minus_sigma_ratios[step],
            denoised_scratch=video_denoised_scratch,
        )
        _minimax_h3_update_target_rows_(
            audio_rows[audio_target_slice],
            velocity_audio,
            sigma_t=audio_sigma_t[step],
            sigma_ratio=audio_sigma_ratios[step],
            one_minus_sigma_ratio=audio_one_minus_sigma_ratios[step],
            denoised_scratch=audio_denoised_scratch,
        )
        if on_step is not None:
            on_step(step, video_rows, audio_rows)
    return video_rows, audio_rows


__all__ = [
    "MiniMaxH3DenoiseBranch",
    "minimax_h3_denoise_loop",
]

===== FILE: external/TaoMate-H3/src/taomate_h3/teacher.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
"""Generate internal audio guidance for streaming inference."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Sequence

from .config import DirectRunConfig, parse_devices, parse_resolution, resolve_prompts
from .inference.base10_teacher import (
    BASE10_TEACHER_STATE_NUMBERS as _TEACHER_STATE_NUMBERS,
)
from .inference.base10_teacher import (
    STAGE3_TARGET_STATE_INDICES as _STAGE3_TARGET_STATE_INDICES,
)

_TP_SIZE = 2
_ROLLOVER_LATENTS_PER_CHANNEL = 40


@dataclass(frozen=True)
class TeacherConfig:
    model_root: Path
    output_dir: Path
    prompts: tuple[str, ...]
    request_seeds: tuple[int, ...]
    duration_seconds: int
    width: int
    height: int
    resolution: str
    devices: tuple[str, ...]
    audio_seed_base: int
    gpu_count: int
    ulysses_degree: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m taomate_h3.teacher",
        description="Generate internal audio guidance for TaoMate-H3 inference.",
    )
    prompts = parser.add_mutually_exclusive_group(required=True)
    prompts.add_argument("--prompt", help="one prompt; reused for every five-second request")
    prompts.add_argument(
        "--prompt-json",
        type=Path,
        help="JSON containing prompts and optional per-request seeds",
    )
    parser.add_argument(
        "--duration",
        type=int,
        help="total seconds; must be a positive multiple of five",
    )
    parser.add_argument(
        "--resolution",
        default="768x1376",
        help="480p, 768p, or aligned 1080p consumer canvas WIDTHxHEIGHT (default: 768x1376)",
    )
    parser.add_argument(
        "--gpus",
        type=int,
        choices=(4, 8),
        default=8,
        help="local GPU count: 4 or 8 (default: 8)",
    )
    parser.add_argument(
        "--devices",
        help="comma-separated CUDA devices; defaults to 0..gpus-1",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        required=True,
        help="local MiniMax-H3 root containing FL2VA/",
    )
    parser.add_argument("--seed", type=int, default=8301)
    parser.add_argument(
        "--audio-seed-base",
        type=int,
        default=8301,
        help="first audio-noise seed; request index is added",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new or empty audio-guidance directory",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _config_from_args(args: argparse.Namespace) -> TeacherConfig:
    prompts, duration_seconds, prompt_seeds = resolve_prompts(
        prompt=args.prompt,
        prompt_json=args.prompt_json,
        duration_seconds=args.duration,
    )
    if type(args.seed) is not int or args.seed < 0:
        raise ValueError("--seed must be a non-negative integer")
    if type(args.audio_seed_base) is not int or args.audio_seed_base < 0:
        raise ValueError("--audio-seed-base must be a non-negative integer")
    width, height, resolution = parse_resolution(args.resolution)
    model_root = args.model_root.expanduser().resolve()
    if not (model_root / "FL2VA").is_dir():
        raise ValueError("--model-root must contain the official FL2VA directory")
    return TeacherConfig(
        model_root=model_root,
        output_dir=args.output.expanduser().resolve(),
        prompts=prompts,
        request_seeds=(prompt_seeds if prompt_seeds is not None else (args.seed,) * len(prompts)),
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        resolution=resolution,
        devices=parse_devices(args.devices, gpu_count=args.gpus),
        audio_seed_base=args.audio_seed_base,
        gpu_count=args.gpus,
        ulysses_degree={4: 2, 8: 4}[args.gpus],
    )


def _prepare_output(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError("--output must be a new or empty directory")
    else:
        path.mkdir(parents=True)


def _worker_arguments(config: TeacherConfig, *, prompt_path: Path) -> list[str]:
    args = [
        "--worker",
        "--model-root",
        str(config.model_root),
        "--duration",
        str(config.duration_seconds),
        "--resolution",
        config.resolution,
        "--audio-seed-base",
        str(config.audio_seed_base),
        "--devices",
        ",".join(config.devices),
        "--gpus",
        str(config.gpu_count),
        "--output",
        str(config.output_dir),
    ]
    prompt_path.write_text(
        json.dumps(
            {"prompts": list(config.prompts), "seeds": list(config.request_seeds)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    args.extend(("--prompt-json", str(prompt_path)))
    return args


def _launch(config: TeacherConfig) -> None:
    with tempfile.TemporaryDirectory(prefix="taomate-h3-teacher-") as temporary:
        prompt_path = Path(temporary) / "prompts.json"
        command = [
            sys.executable,
            "-m",
            "torch.distributed.run",
            "--standalone",
            f"--nproc-per-node={config.gpu_count}",
            "--module",
            "taomate_h3.teacher",
            *_worker_arguments(config, prompt_path=prompt_path),
        ]
        environment = os.environ.copy()
        environment["CUDA_VISIBLE_DEVICES"] = ",".join(config.devices)
        environment.setdefault("OMP_NUM_THREADS", "1")
        subprocess.run(command, check=True, env=environment)


def _parallel_context(torch: Any, rank: int, *, ulysses_degree: int) -> Any:
    from .distributed import ParallelContext

    tp_groups = [
        torch.distributed.new_group(
            ranks=[ulysses_rank * _TP_SIZE + tp_rank for tp_rank in range(_TP_SIZE)],
            backend="nccl",
        )
        for ulysses_rank in range(ulysses_degree)
    ]
    ulysses_groups = [
        torch.distributed.new_group(
            ranks=[ulysses_rank * _TP_SIZE + tp_rank for ulysses_rank in range(ulysses_degree)],
            backend="nccl",
        )
        for tp_rank in range(_TP_SIZE)
    ]
    return ParallelContext(
        tp_world_size=_TP_SIZE,
        tp_rank=rank % _TP_SIZE,
        ulysses_world_size=ulysses_degree,
        ulysses_rank=rank // _TP_SIZE,
        tp_group=tp_groups[rank // _TP_SIZE],
        ulysses_group=ulysses_groups[rank % _TP_SIZE],
    )


def _official_audio_noise(torch: Any, *, geometry: Any, seed: int) -> Any:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    # H3 draws full-AV video noise before audio. The teacher discards these
    # values, but advancing this exact CPU generator is part of audio identity.
    torch.randn(
        1,
        24,
        geometry.video_latent_t,
        geometry.video_latent_h,
        geometry.video_latent_w,
        generator=generator,
        dtype=torch.float32,
        device="cpu",
    )
    return torch.randn(
        2 * geometry.audio_latent_t,
        32,
        generator=generator,
        dtype=torch.float32,
        device="cpu",
    )


def _audio_branch(
    torch: Any,
    *,
    pipeline: Any,
    geometry: Any,
    text_features: tuple[Any, Any],
    audio_latent_count: int,
    previous_audio_latent_count: int | None,
) -> Any:
    from .model.denoise import MiniMaxH3DenoiseBranch
    from .model.packed_sequence import (
        minimax_h3_audio_only_frozen_prefix_packed_sequence,
        minimax_h3_audio_only_packed_sequence,
    )

    text_embeddings, text_tags = text_features
    text_len = int(text_embeddings.shape[0])
    if previous_audio_latent_count is None:
        packed = minimax_h3_audio_only_packed_sequence(
            text_len=text_len,
            audio_t=audio_latent_count,
            latent_h=geometry.video_latent_h,
            latent_w=geometry.video_latent_w,
        )
    else:
        packed = minimax_h3_audio_only_frozen_prefix_packed_sequence(
            text_len=text_len,
            ref_audio_t=_ROLLOVER_LATENTS_PER_CHANNEL,
            audio_t=audio_latent_count,
            latent_h=geometry.video_latent_h,
            latent_w=geometry.video_latent_w,
            reference_time_start=(
                text_len + previous_audio_latent_count - _ROLLOVER_LATENTS_PER_CHANNEL
            ),
            target_time_start=text_len + previous_audio_latent_count,
        )
    packed["token_tags"][packed["text_pos"].view(-1)] = text_tags.view(-1)
    branch = MiniMaxH3DenoiseBranch(
        packed=packed,
        text_embeddings=text_embeddings,
        token_tags=packed["token_tags"],
        device=pipeline.device,
        parallel_context=pipeline.parallel_context,
    )
    refined = pipeline.transformer.refine_prompt_embeds(
        branch.static_kwargs["prompt_embeds"],
        branch.refiner_cu_seqlens,
        device=pipeline.device,
    )
    branch.static_kwargs["prompt_embeds"] = refined
    branch.static_kwargs["rope_cache"] = pipeline.transformer.build_rope_cache(
        branch.img_position_ids,
        device=pipeline.device,
    )
    return branch


def _previous_clean_tail(clean: Any, *, audio_latent_count: int) -> Any:
    return (
        clean.view(2, audio_latent_count, 32)[:, -_ROLLOVER_LATENTS_PER_CHANNEL:]
        .contiguous()
        .view(2 * _ROLLOVER_LATENTS_PER_CHANNEL, 32)
    )


def _generate_request(
    torch: Any,
    *,
    pipeline: Any,
    geometry: Any,
    text_features: tuple[Any, Any],
    audio_seed: int,
    request_index: int,
    previous_clean: Any | None,
    previous_audio_latent_count: int | None,
) -> tuple[list[Any], Any, int, dict[str, Any]]:
    from .denoise_schedule import select_time_shift_sigmas
    from .model.denoise import minimax_h3_denoise_loop
    from .streaming.geometry import canonical_continuation_plan, direct_5s_plan

    official_plan = direct_5s_plan()
    active_plan = (
        official_plan
        if request_index == 0
        else canonical_continuation_plan(official_plan, request_index=request_index)
    )
    official_audio_latents = geometry.audio_latent_t
    active_audio_latents = active_plan.phases[-1].audio_latent_stop
    transport_prefix = official_audio_latents - active_audio_latents
    official_audio = _official_audio_noise(torch, geometry=geometry, seed=audio_seed)
    target_noise = (
        official_audio.view(2, official_audio_latents, 32)[:, transport_prefix:]
        .contiguous()
        .view(2 * active_audio_latents, 32)
    )
    previous_tail = (
        None
        if previous_clean is None
        else _previous_clean_tail(
            previous_clean,
            audio_latent_count=int(previous_audio_latent_count),
        )
    )
    initial_audio = (
        target_noise if previous_tail is None else torch.cat((previous_tail, target_noise), dim=0)
    )
    branch = _audio_branch(
        torch,
        pipeline=pipeline,
        geometry=geometry,
        text_features=text_features,
        audio_latent_count=active_audio_latents,
        previous_audio_latent_count=previous_audio_latent_count,
    )
    video_sigmas = select_time_shift_sigmas(num_steps=10, shift_scale=12.0)
    audio_sigmas = select_time_shift_sigmas(num_steps=10, shift_scale=3.0)
    captured: dict[int, Any] = {}

    def capture(step: int, _video: Any, audio: Any) -> None:
        state_number = step + 1
        if state_number in _TEACHER_STATE_NUMBERS:
            captured[state_number] = (
                audio[branch.audio_target_slice]
                .detach()
                .to(device="cpu", dtype=torch.float32)
                .contiguous()
            )

    empty_video = torch.empty(
        (0, int(pipeline.transformer.arch.video_row_width)),
        dtype=torch.float32,
        device="cpu",
    )
    with torch.no_grad():
        minimax_h3_denoise_loop(
            model=pipeline.transformer,
            positive=branch,
            initial_video_rows=empty_video,
            initial_audio_rows=initial_audio,
            sigmas_video=video_sigmas,
            sigmas_audio=audio_sigmas,
            device=pipeline.device,
            on_step=capture,
        )
    milestones = [captured[state_number] for state_number in _TEACHER_STATE_NUMBERS]
    target_clean = milestones[-1]
    return (
        milestones,
        target_clean,
        active_audio_latents,
        {
            "transport_prefix_audio_latents_per_channel": transport_prefix,
            "packed_text_rows": int(text_features[0].shape[0]),
            "packed_audio_rows": int(branch.audio_pos.shape[0]),
            "reference_latents_per_channel": (
                0 if previous_tail is None else _ROLLOVER_LATENTS_PER_CHANNEL
            ),
            "reference_duration_seconds": 0.0 if previous_tail is None else 1.0,
            "audio_noise_seed": audio_seed,
        },
    )


def _run_worker(config: TeacherConfig) -> None:
    import torch

    from .model.geometry import direct_5s_geometry
    from .model.pipeline import MiniMaxH3NativePipeline

    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", str(rank)))
    if world_size != config.gpu_count:
        raise ValueError(
            f"audio-guidance torchrun world size must be {config.gpu_count}, got {world_size}"
        )
    torch.cuda.set_device(local_rank)
    device = torch.device("cuda", local_rank)
    torch.distributed.init_process_group(
        backend="nccl", init_method="env://", timeout=timedelta(hours=3)
    )
    context = _parallel_context(torch, rank, ulysses_degree=config.ulysses_degree)
    pipeline = MiniMaxH3NativePipeline(
        model_root=config.model_root,
        device=device,
        parallel_context=context,
        rank=rank,
        world_size=world_size,
        transformer_load_w8a8_policy=None,
    )
    geometry = direct_5s_geometry(width=config.width, height=config.height)
    text_features = tuple(
        (
            hidden.detach().to(device="cpu").contiguous(),
            tags.detach().to(device="cpu").contiguous(),
        )
        for hidden, tags in (pipeline._encode_text(prompt=prompt) for prompt in config.prompts)
    )
    pipeline._offload_text()

    active_counts: list[int] = []
    request_receipts: list[dict[str, Any]] = []
    audio_seed_sequence = [config.audio_seed_base + index for index in range(len(config.prompts))]
    previous_clean = None
    previous_audio_latent_count: int | None = None
    for request_index, features in enumerate(text_features):
        milestones, current_clean, active_audio_latents, request_receipt = _generate_request(
            torch,
            pipeline=pipeline,
            geometry=geometry,
            text_features=features,
            audio_seed=audio_seed_sequence[request_index],
            request_index=request_index,
            previous_clean=previous_clean,
            previous_audio_latent_count=previous_audio_latent_count,
        )
        active_counts.append(active_audio_latents)
        request_receipt["prefix_source_request"] = (
            None if request_index == 0 else request_index - 1
        )
        request_receipts.append(request_receipt)
        previous_clean = current_clean
        previous_audio_latent_count = active_audio_latents
        if rank == 0:
            torch.save(
                {
                    "prompt": config.prompts[request_index],
                    "seed": config.request_seeds[request_index],
                    "audio_latent_count": active_audio_latents,
                    "teacher_state_numbers": _TEACHER_STATE_NUMBERS,
                    "stage3_target_state_indices": _STAGE3_TARGET_STATE_INDICES,
                    "milestones": milestones,
                },
                config.output_dir / f"request_{request_index:02d}.pt",
            )
        torch.distributed.barrier()

    if rank == 0:
        completion = {
            "mode": "base10_milestones",
            "strategy": "previous_clean_audio_tail_reference_then_new_noise",
            "partition": "fl2va",
            "base_precision": "bf16",
            "parallelism": {
                "tensor_parallel_size": _TP_SIZE,
                "ulysses_degree": config.ulysses_degree,
            },
            "request_count": len(config.prompts),
            "request_seconds": 5,
            "request_seeds": list(config.request_seeds),
            "audio_noise_seed_sequence": audio_seed_sequence,
            "producer_geometry": {
                "width": config.width,
                "height": config.height,
                "video_latent_h": geometry.video_latent_h,
                "video_latent_w": geometry.video_latent_w,
            },
            "official_audio_latents_per_channel": geometry.audio_latent_t,
            "active_audio_latents_per_channel": active_counts,
            "request_receipts": request_receipts,
            "full_state_count": 10,
            "executed_forwards_per_request": 9,
            "teacher_state_numbers": list(_TEACHER_STATE_NUMBERS),
            "stage3_target_state_indices": list(_STAGE3_TARGET_STATE_INDICES),
            "artifact_storage_dtype": "float32",
            "video_rows": 0,
            "noise_order": "draw_and_discard_full_video_then_draw_audio",
            "reference_latents_per_channel": _ROLLOVER_LATENTS_PER_CHANNEL,
            "reference_duration_seconds": 1.0,
            "persistent_kv": False,
            "waveform_crossfade": False,
            "audio_vae_decode_count": 0,
            "adapter_loaded": False,
        }
        (config.output_dir / "complete.json").write_text(
            json.dumps(completion, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    torch.distributed.barrier()


def launch_audio_guidance(
    run_config: DirectRunConfig,
    *,
    output_dir: Path,
) -> None:
    """Generate the audio guidance consumed by one inference run."""

    config = TeacherConfig(
        model_root=run_config.model_root,
        output_dir=output_dir,
        prompts=run_config.prompts,
        request_seeds=run_config.request_seeds,
        duration_seconds=run_config.duration_seconds,
        width=run_config.width,
        height=run_config.height,
        resolution=run_config.resolution,
        devices=run_config.devices,
        audio_seed_base=run_config.seed,
        gpu_count=run_config.gpu_count,
        ulysses_degree=run_config.ulysses_degree,
    )
    _prepare_output(config.output_dir)
    _launch(config)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _config_from_args(args)
        if args.worker:
            _run_worker(config)
        else:
            _prepare_output(config.output_dir)
            _launch(config)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["TeacherConfig", "build_parser", "launch_audio_guidance", "main"]

===== FILE: external/TaoMate-H3/src/taomate_h3/inference/lora_checkpoint.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
from __future__ import annotations

import importlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_H3_LORA_TARGET_SUFFIXES = (
    "attn.qkv_proj",
    "attn.out_proj",
    "mlp.fc1",
    "mlp.fc2",
)


def canonical_h3_lora_targets() -> tuple[str, ...]:
    """Return the adapter's exact 52-block x 4-projection inventory."""

    blocks = [f"token_refiner.blocks.{index}" for index in range(2)]
    blocks.extend(f"blocks.{index}" for index in range(50))
    return tuple(f"{block}.{suffix}" for block in blocks for suffix in _H3_LORA_TARGET_SUFFIXES)


class H3LoRACheckpointError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedH3LoRA:
    rank: int
    alpha: float
    state: Mapping[str, Any]
    loaded_tensor_count: int

    @property
    def scale(self) -> float:
        return self.alpha / self.rank


def _read_adapter_config(adapter_dir: Path) -> tuple[Path, Mapping[str, Any]]:
    root = adapter_dir.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise H3LoRACheckpointError("H3 LoRA adapter root is not a directory")
    config_path = root / "config.json"
    if not config_path.is_file():
        config_path = root / "adapter_config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise H3LoRACheckpointError(f"cannot read H3 LoRA adapter config: {exc}") from exc
    if not isinstance(config, Mapping):
        raise H3LoRACheckpointError("H3 LoRA adapter config must be an object")
    return root, config


def load_h3_lora_checkpoint(
    adapter_dir: str | Path,
) -> LoadedH3LoRA:
    """Load an inference-only LoRA adapter from safetensors."""

    torch = importlib.import_module("torch")
    root, config = _read_adapter_config(Path(adapter_dir))
    rank = config.get("rank")
    alpha = config.get("alpha")
    if (
        isinstance(rank, bool)
        or not isinstance(rank, int)
        or rank <= 0
        or isinstance(alpha, bool)
        or not isinstance(alpha, (int, float))
        or not math.isfinite(float(alpha))
        or float(alpha) <= 0
    ):
        raise H3LoRACheckpointError("H3 LoRA rank/alpha is invalid")
    targets = canonical_h3_lora_targets()
    leaves = ("lora_a", "lora_b")
    expected = {f"{target}.{leaf}" for target in targets for leaf in leaves}
    weights_path = root / "adapter_model.safetensors"
    safe_open = importlib.import_module("safetensors").safe_open
    selected: dict[str, Any] = {}
    with safe_open(str(weights_path), framework="pt", device="cpu") as handle:
        present = set(handle.keys())
        if present != expected:
            raise H3LoRACheckpointError(
                "H3 LoRA tensor inventory differs: "
                f"missing={len(expected - present)}, unexpected={len(present - expected)}"
            )
        for target in targets:
            for leaf in leaves:
                name = f"{target}.{leaf}"
                tensor = handle.get_tensor(name)
                if (
                    tensor.ndim != 2
                    or tensor.dtype != torch.float32
                    or (leaf == "lora_a" and int(tensor.shape[0]) != rank)
                    or (leaf == "lora_b" and int(tensor.shape[1]) != rank)
                ):
                    raise H3LoRACheckpointError(f"H3 LoRA tensor shape/dtype differs: {name}")
                selected[name] = tensor.contiguous()
    if os.environ.get("LOCAL_RANK", "0") == "0":
        print(
            f"[adapter-load] H3 LoRA tensors loaded={len(selected)}",
            flush=True,
        )
    return LoadedH3LoRA(
        rank=rank,
        alpha=float(alpha),
        state=selected,
        loaded_tensor_count=len(selected),
    )


def _tensor_parallel_coordinates(module: Any) -> tuple[int, int]:
    tp_size = int(module.tp_size)
    tp_rank = int(module.tp_rank)
    if tp_size <= 0 or tp_rank < 0 or tp_rank >= tp_size:
        raise H3LoRACheckpointError("H3 inference LoRA TP coordinates are invalid")
    return tp_size, tp_rank


def _column_local_b(full_b: Any, module: Any) -> Any:
    torch = importlib.import_module("torch")
    tp_size, tp_rank = _tensor_parallel_coordinates(module)
    output_sizes = module.output_sizes
    pieces: list[Any] = []
    offset = 0
    for raw_size in output_sizes:
        size = int(raw_size)
        if size % tp_size:
            raise H3LoRACheckpointError("H3 merged-column LoRA output is not TP-divisible")
        shard = size // tp_size
        pieces.append(full_b.narrow(0, offset + tp_rank * shard, shard))
        offset += size
    if offset != int(full_b.shape[0]):
        raise H3LoRACheckpointError("H3 merged-column LoRA output inventory differs")
    return torch.cat(pieces, dim=0).contiguous()


def _row_local_a(full_a: Any, module: Any) -> Any:
    tp_size, tp_rank = _tensor_parallel_coordinates(module)
    input_size = int(full_a.shape[1])
    if input_size % tp_size:
        raise H3LoRACheckpointError("H3 row LoRA input is not TP-divisible")
    shard = input_size // tp_size
    return full_a.narrow(1, tp_rank * shard, shard).contiguous()


def apply_h3_lora_checkpoint(
    transformer: Any,
    adapter_dir: str | Path,
) -> Mapping[str, Any]:
    """Install a TP-aware, inference-only LoRA bank on the live H3 DiT."""

    torch = importlib.import_module("torch")
    linear = importlib.import_module("taomate_h3.distributed.linear")
    collectives = importlib.import_module("taomate_h3.distributed.collectives")
    loaded = load_h3_lora_checkpoint(adapter_dir)
    adapter_rank = loaded.rank
    adapter_alpha = loaded.alpha
    adapter_scale = loaded.scale
    loaded_tensor_count = loaded.loaded_tensor_count
    targets = canonical_h3_lora_targets()
    modules = dict(transformer.named_modules())
    supported_column = (linear.MergedColumnParallelLinear,)
    supported_row = (linear.RowParallelLinear,)

    class H3InferenceParallelLinearLoRA(torch.nn.Module):
        def __init__(self, base: Any, *, kind: str, a: Any, b: Any) -> None:
            super().__init__()
            self.base = base
            self.kind = kind
            self.scale = adapter_scale
            self.fused_row_reduce_enabled = False
            self._taomate_h3_inference_lora = True
            self.register_buffer("lora_a", a, persistent=False)
            self.register_buffer("lora_b", b, persistent=False)

        def forward(self, inputs: Any) -> Any:
            if self.kind == "row" and self.fused_row_reduce_enabled and int(self.base.tp_size) > 1:
                base_partial = self.base.forward_local(inputs)
                compute_dtype = base_partial.dtype
                update_partial = torch.nn.functional.linear(
                    torch.nn.functional.linear(inputs.to(compute_dtype), self.lora_a),
                    self.lora_b,
                )
                output = self.base.reduce_local_output(base_partial + update_partial * self.scale)
                if self.base.bias is not None:
                    output = output + self.base.bias
                return output
            output = self.base(inputs)
            compute_dtype = output.dtype
            update = torch.nn.functional.linear(
                torch.nn.functional.linear(inputs.to(compute_dtype), self.lora_a),
                self.lora_b,
            )
            if self.kind == "row" and int(self.base.tp_size) > 1:
                update = collectives.tp_all_reduce(update, context=self.base.parallel_context)
            if tuple(update.shape) != tuple(output.shape):
                raise H3LoRACheckpointError("H3 inference LoRA output shape differs")
            return output + update * self.scale

    replacements: list[tuple[str, Any, Any]] = []
    local_numel = 0
    for target in targets:
        module = modules.get(target)
        if type(module) in supported_column:
            if bool(getattr(module, "gather_output", False)):
                raise H3LoRACheckpointError("gathered H3 column output is not qualified")
            kind = "column"
        elif type(module) in supported_row:
            kind = "row"
        else:
            raise H3LoRACheckpointError(f"H3 inference LoRA target type differs: {target}")

        full_a = loaded.state[f"{target}.lora_a"]
        full_b = loaded.state[f"{target}.lora_b"]
        if int(full_a.shape[1]) != int(module.input_size) or int(full_b.shape[0]) != int(
            module.output_size
        ):
            raise H3LoRACheckpointError(f"H3 inference LoRA full shape differs: {target}")
        device = module.weight.device
        if kind == "column":
            local_a = full_a.to(device=device, dtype=torch.float32)
            local_b = _column_local_b(full_b, module).to(device=device, dtype=torch.float32)
        else:
            local_a = _row_local_a(full_a, module).to(device=device, dtype=torch.float32)
            local_b = full_b.to(device=device, dtype=torch.float32)
        if int(local_a.shape[1]) != int(module.weight.shape[1]) or int(local_b.shape[0]) != int(
            module.weight.shape[0]
        ):
            raise H3LoRACheckpointError(f"H3 inference LoRA local shape differs: {target}")
        replacement = H3InferenceParallelLinearLoRA(module, kind=kind, a=local_a, b=local_b).eval()
        replacements.append((target, module, replacement))
        local_numel += int(local_a.numel() + local_b.numel())

    for target, expected, replacement in replacements:
        parent = transformer
        parts = target.split(".")
        for part in parts[:-1]:
            parent = getattr(parent, part)
        if getattr(parent, parts[-1]) is not expected:
            raise H3LoRACheckpointError(f"H3 inference LoRA target changed: {target}")
        setattr(parent, parts[-1], replacement)

    return {
        "rank": adapter_rank,
        "alpha": adapter_alpha,
        "scale": adapter_scale,
        "target_count": len(replacements),
        "loaded_tensor_count": loaded_tensor_count,
        "local_adapter_numel": local_numel,
        "tensor_parallel_size": int(replacements[0][1].tp_size),
    }


def materialize_h3_lora_bf16_buffers_(transformer: Any) -> Mapping[str, Any]:
    """Materialize the inference LoRA buffers once in their BF16 compute dtype."""

    torch = importlib.import_module("torch")
    adapters = [
        module
        for module in transformer.modules()
        if getattr(module, "_taomate_h3_inference_lora", False)
    ]
    if not adapters:
        raise H3LoRACheckpointError("BF16 LoRA buffers require a loaded adapter")
    converted_numel = 0
    for module in adapters:
        for name in ("lora_a", "lora_b"):
            value = getattr(module, name)
            if value.dtype != torch.bfloat16:
                converted_numel += int(value.numel())
                setattr(module, name, value.to(dtype=torch.bfloat16))
    return {
        "target_count": len(adapters),
        "buffer_count": 2 * len(adapters),
        "converted_numel": converted_numel,
        "dtype": "bfloat16",
    }


def enable_h3_fused_lora_row_reduce_(transformer: Any) -> Mapping[str, Any]:
    """Add each row-parallel LoRA partial before the existing TP reduction."""

    rows = [
        module
        for module in transformer.modules()
        if getattr(module, "_taomate_h3_inference_lora", False)
        and getattr(module, "kind", None) == "row"
    ]
    if not rows:
        raise H3LoRACheckpointError("fused row reduction requires a loaded adapter")
    for module in rows:
        module.fused_row_reduce_enabled = True
    return {
        "row_parallel_module_count": len(rows),
        "tp_all_reduce_calls_saved_per_forward": len(rows),
    }


__all__ = [
    "H3LoRACheckpointError",
    "apply_h3_lora_checkpoint",
    "enable_h3_fused_lora_row_reduce_",
    "materialize_h3_lora_bf16_buffers_",
]

===== FILE: external/TaoMate-H3/src/taomate_h3/model/packed_sequence.py =====
# Modified for TaoMate-H3 streaming inference, 2026.
# Licensed under the MiniMax H3 Community License Agreement; see LICENSE.
"""Native MiniMax H3 T2VA packed-sequence builders.

The row layout and fp64 position-grid math are kept byte-for-byte compatible
with the pinned MiniMax H3 reference behavior.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from .architecture import MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT

_INTERP = 32
_T_GROUP = 5
_FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
_FRAME_RESCALE = 5.0 / 3.0
_PATCH_H = 2
_PATCH_W = 2


def _axis_from_sqrt_area(dim: int, patch: int, sqrt_area: float) -> torch.Tensor:
    ratio = dim / sqrt_area
    left = (1.0 - ratio) / 2.0
    right = left + ratio
    grid = np.linspace(left, right, dim // patch, endpoint=False) * _INTERP
    return torch.from_numpy(grid).to(torch.float64)


def _video_t_grid(n: int, origin: float) -> torch.Tensor:
    spans = torch.tensor(
        [_FRAME_RESCALE * _FRAME_PER_TOKEN[k % _T_GROUP] for k in range(n)],
        dtype=torch.float64,
    )
    return origin + torch.cat([torch.zeros(1, dtype=torch.float64), spans[:-1].cumsum(0)])


def minimax_h3_packed_sequence(
    *,
    text_len: int,
    latent_t: int,
    latent_h: int,
    latent_w: int,
    audio_t: int,
    audio_channel: int = 2,
) -> dict[str, Any]:
    """Build one positive-branch T2VA layout: text/audio/video/pad."""

    if min(text_len, latent_t, latent_h, latent_w, audio_t, audio_channel) <= 0:
        raise ValueError("all MiniMax H3 packed-sequence dimensions must be positive")
    if latent_h % _PATCH_H or latent_w % _PATCH_W:
        raise ValueError("latent_h and latent_w must be divisible by the 2x2 patch")
    ph, pw = latent_h // _PATCH_H, latent_w // _PATCH_W
    frame_rows = ph * pw
    video_rows = latent_t * frame_rows
    audio_rows = audio_t * audio_channel
    used = text_len + audio_rows + video_rows
    seq_len = (
        (used + MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT - 1)
        // MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT
        * MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT
    )

    text_sl = slice(0, text_len)
    audio_sl = slice(text_len, text_len + audio_rows)
    video_sl = slice(audio_sl.stop, audio_sl.stop + video_rows)
    img_pos = torch.arange(video_sl.start, video_sl.stop)
    audio_pos = torch.arange(audio_sl.start, audio_sl.stop)
    text_pos = torch.arange(0, text_len)

    grid = torch.zeros(seq_len, 3, dtype=torch.float64)
    grid[text_sl, 0] = torch.arange(text_len, dtype=torch.float64)
    t_grid = _video_t_grid(latent_t, float(text_len))
    sqrt_area = np.sqrt(latent_h * latent_w)
    h_grid = _axis_from_sqrt_area(latent_h, _PATCH_H, sqrt_area)
    w_grid = _axis_from_sqrt_area(latent_w, _PATCH_W, sqrt_area)
    hh, ww = torch.meshgrid(h_grid, w_grid, indexing="ij")
    frame = torch.stack([hh.reshape(-1), ww.reshape(-1)], dim=-1)
    video_grid = grid[video_sl].view(latent_t, frame_rows, 3)
    video_grid[:, :, 0] = t_grid[:, None]
    video_grid[:, :, 1:] = frame[None]
    audio_t_grid = float(text_len) + torch.arange(audio_t, dtype=torch.float64)
    grid[audio_sl, 0] = audio_t_grid.repeat(audio_channel)
    grid[audio_sl.start : audio_sl.start + audio_t, 2] = float(w_grid[0])
    grid[audio_sl.start + audio_t : audio_sl.stop, 2] = float(w_grid[-1])

    token_tags = torch.full((seq_len,), -1, dtype=torch.long)
    token_tags[text_sl] = 1
    token_tags[audio_sl] = 2
    token_tags[img_pos] = 0
    cu_seqlens = torch.tensor([0, used, seq_len], dtype=torch.int32)
    return {
        "seq_len": seq_len,
        "img_pos": img_pos,
        "audio_pos": audio_pos,
        "text_pos": text_pos,
        "img_position_ids": grid,
        "token_tags": token_tags,
        "cu_seqlens": cu_seqlens,
    }


def minimax_h3_audio_only_packed_sequence(
    *,
    text_len: int,
    audio_t: int,
    latent_h: int,
    latent_w: int,
    audio_channel: int = 2,
) -> dict[str, Any]:
    """Build the Base teacher's text/audio sequence without video tokens."""

    if min(text_len, audio_t, latent_h, latent_w, audio_channel) <= 0:
        raise ValueError("all MiniMax H3 audio-only dimensions must be positive")
    if latent_h % _PATCH_H or latent_w % _PATCH_W:
        raise ValueError("latent_h and latent_w must be divisible by the 2x2 patch")

    audio_rows = audio_t * audio_channel
    used = text_len + audio_rows
    seq_len = (
        (used + MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT - 1)
        // MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT
        * MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT
    )
    text_sl = slice(0, text_len)
    audio_sl = slice(text_len, text_len + audio_rows)

    grid = torch.zeros(seq_len, 3, dtype=torch.float64)
    grid[text_sl, 0] = torch.arange(text_len, dtype=torch.float64)
    audio_t_grid = float(text_len) + torch.arange(audio_t, dtype=torch.float64)
    grid[audio_sl, 0] = audio_t_grid.repeat(audio_channel)
    sqrt_area = np.sqrt(latent_h * latent_w)
    w_grid = _axis_from_sqrt_area(latent_w, _PATCH_W, sqrt_area)
    grid[audio_sl.start : audio_sl.start + audio_t, 2] = float(w_grid[0])
    grid[audio_sl.start + audio_t : audio_sl.stop, 2] = float(w_grid[-1])

    token_tags = torch.full((seq_len,), -1, dtype=torch.long)
    token_tags[text_sl] = 1
    token_tags[audio_sl] = 2
    return {
        "seq_len": seq_len,
        "img_pos": torch.empty(0, dtype=torch.long),
        "audio_pos": torch.arange(audio_sl.start, audio_sl.stop),
        "text_pos": torch.arange(text_len),
        "img_position_ids": grid,
        "token_tags": token_tags,
        "cu_seqlens": torch.tensor([0, used, seq_len], dtype=torch.int32),
    }


def minimax_h3_audio_only_frozen_prefix_packed_sequence(
    *,
    text_len: int,
    ref_audio_t: int,
    audio_t: int,
    latent_h: int,
    latent_w: int,
    reference_time_start: int,
    target_time_start: int,
    audio_channel: int = 2,
) -> dict[str, Any]:
    """Build an audio-only request with a clean, read-only reference tail."""

    if min(text_len, ref_audio_t, audio_t, latent_h, latent_w, audio_channel) <= 0:
        raise ValueError("all MiniMax H3 audio-reference dimensions must be positive")
    if latent_h % _PATCH_H or latent_w % _PATCH_W:
        raise ValueError("latent_h and latent_w must be divisible by the 2x2 patch")

    ref_rows = ref_audio_t * audio_channel
    target_rows = audio_t * audio_channel
    used = text_len + ref_rows + target_rows
    seq_len = (
        (used + MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT - 1)
        // MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT
        * MINIMAX_H3_PACKED_SEQUENCE_ALIGNMENT
    )
    text_sl = slice(0, text_len)
    ref_sl = slice(text_sl.stop, text_sl.stop + ref_rows)
    target_sl = slice(ref_sl.stop, ref_sl.stop + target_rows)

    grid = torch.zeros(seq_len, 3, dtype=torch.float64)
    grid[text_sl, 0] = torch.arange(text_len, dtype=torch.float64)
    grid[ref_sl, 0] = (
        float(reference_time_start) + torch.arange(ref_audio_t, dtype=torch.float64)
    ).repeat(audio_channel)
    grid[target_sl, 0] = (
        float(target_time_start) + torch.arange(audio_t, dtype=torch.float64)
    ).repeat(audio_channel)

    sqrt_area = np.sqrt(latent_h * latent_w)
    w_grid = _axis_from_sqrt_area(latent_w, _PATCH_W, sqrt_area)
    for audio_sl, temporal_rows in ((ref_sl, ref_audio_t), (target_sl, audio_t)):
        grid[audio_sl.start : audio_sl.start + temporal_rows, 2] = float(w_grid[0])
        grid[audio_sl.start + temporal_rows : audio_sl.stop, 2] = float(w_grid[-1])

    audio_pos = torch.arange(ref_sl.start, target_sl.stop)
    audio_update_mask = torch.zeros(ref_rows + target_rows, dtype=torch.bool)
    audio_update_mask[ref_rows:] = True
    token_tags = torch.full((seq_len,), -1, dtype=torch.long)
    token_tags[text_sl] = 1
    token_tags[audio_pos] = 2
    return {
        "seq_len": seq_len,
        "img_pos": torch.empty(0, dtype=torch.long),
        "audio_pos": audio_pos,
        "audio_update_mask": audio_update_mask,
        "text_pos": torch.arange(text_len),
        "img_position_ids": grid,
        "token_tags": token_tags,
        "cu_seqlens": torch.tensor([0, used, seq_len], dtype=torch.int32),
    }


__all__ = [
    "minimax_h3_audio_only_frozen_prefix_packed_sequence",
    "minimax_h3_audio_only_packed_sequence",
    "minimax_h3_packed_sequence",
]

===== FILE: live_agent/generator/taomate_worker/stream_decode.py =====
"""Incremental (per-chunk) VAE decoding for the TaoMate-H3 student (T3).

Video
-----
The bundled H3 video VAE decodes the latent timeline in temporal windows
(``klvae.decode_temporal``): clip_length 17, vae_ratio_t 4, token_drop 3, hence
``tokens_chunk_size = 5``, ``token_overlap = 2``, ``frame_pre_padding = 3`` and
``frame_overlap = 5``. Window ``i`` reads latents ``[5i, 5i+7)``, decodes 28 frames, keeps
frames ``[3, 20)`` as its 17 primary frames and frames ``[23, 28)`` as a 5-frame overlap
that is linearly blended into the first 5 frames of window ``i+1``.

TaoMate-H3 chunks carry 12/10/10/5 new latents (request 0) and 10/10/10/5 afterwards, so
after every chunk all windows with ``5i+7 <= latents_so_far`` can be decoded exactly as the
one-shot decode would (same windows, same blend). Each chunk therefore yields 34/34/34/17
final frames; only the 5-frame overlap of the newest window is held back until the next
chunk (or ``flush``). Unlike the published path there is no 124+119n -> 120n time warp:
frames are native 24 fps, 119 per 5-second request.

All ranks call ``push`` collectively because the bundled VAE splits spatial tiles across
the world group (``parallel_tiling``); rank 0 receives the uint8 frames.

Audio
-----
The audio VAE (40 latents/s, 800 samples/latent at 32 kHz) is decoded on rank 0 with a
sliding window: to emit samples ``[s0, s1)`` it decodes latents
``[s0/800 - left, s1/800 + right)`` (bounded by what the teacher has produced) and crops.
Audio is emitted aligned to the video frames of the same chunk (1333.33 samples/frame).
"""

from __future__ import annotations

from typing import Any

import numpy as np

# bundled H3 video VAE temporal windowing (checked at construction)
_TOKENS_PER_WINDOW = 5
_WINDOW_TOKENS = 7
_PRE_PAD = 3
_PRIMARY_FRAMES = 17
_OVERLAP_FRAMES = 5
SAMPLES_PER_LATENT = 800
SAMPLE_RATE = 32000
FPS = 24


def samples_at_frame(frame: int) -> int:
    return (frame * SAMPLE_RATE) // FPS


class StreamingVideoDecoder:
    def __init__(self, decoder: Any, *, device: Any, rank: int, group: Any) -> None:
        import torch

        from taomate_h3.inference.video_vae_exact_fusions import (
            install_h3_video_vae_exact_fusions_,
        )
        from taomate_h3.model.components import configure_bundled_video_vae_tile_parallel

        self.torch = torch
        self.device = device
        self.rank = rank
        self.config = decoder.video_config
        vae = decoder.video_vae.to(device).eval()
        self.vae = vae
        self.model = vae.model
        self.model.stack_tiling = True  # H3LatentDecoder.enable_video_vae_batched_tiles
        install_h3_video_vae_exact_fusions_(self.model.decoder, device=device)
        world = torch.distributed.get_world_size()
        configure_bundled_video_vae_tile_parallel(vae, group=group, rank=rank, world_size=world)
        prepare = getattr(vae, "prepare_decoder_autocast_weights", None)
        if callable(prepare):
            prepare(torch.float16)
        expected = (_TOKENS_PER_WINDOW, _WINDOW_TOKENS - _TOKENS_PER_WINDOW, _PRE_PAD, _OVERLAP_FRAMES)
        actual = (
            int(self.model.tokens_chunk_size),
            int(self.model.token_overlap),
            int(self.model.frame_pre_padding),
            int(self.model.frame_overlap),
        )
        if actual != expected or self.model.isolated_first_frame or self.model.isolated_last_frame:
            raise RuntimeError(f"unexpected H3 video VAE temporal windowing {actual}")
        self.reset()

    def reset(self) -> None:
        self.latents = None  # reverse-normalized [1, 24, T, H, W] float32 on device
        self.base = 0  # global latent index of self.latents[:, :, 0]
        self.total = 0  # latents pushed so far
        self.next_window = 0
        self.overlap = None
        self.frames_emitted = 0

    def _reverse_normalize(self, latents: Any) -> Any:
        from taomate_h3.model.output import _reverse_normalize

        return _reverse_normalize(
            latents.to(device=self.device, dtype=self.torch.float32),
            mean_values=self.config["latents_mean"],
            std_values=self.config["latents_std"],
        )

    def _to_uint8(self, frames: Any) -> np.ndarray:
        # frames: [1, 3, T, H, W] in VAE output space -> [T, H, W, 3] uint8 (as save_h3_video_mp4)
        pixels = self.vae.processor.revert_tensor(frames.float())
        return (
            pixels[0].permute(1, 2, 3, 0).mul(255.0).round().clamp(0, 255)
            .to(self.torch.uint8).contiguous().cpu().numpy()
        )

    def advance(self, latents: Any) -> Any:
        """Append ``[1, 24, n, H, W]`` latents and decode every window that became complete.

        Returns the new final frames in VAE output space ``[1, 3, T, H, W]`` (or None).
        """

        torch = self.torch
        visual = self._reverse_normalize(latents)
        self.latents = visual if self.latents is None else torch.cat((self.latents, visual), dim=2)
        self.total += int(visual.shape[2])
        outputs = []
        autocast = torch.autocast("cuda", dtype=torch.float16, enabled=self.device.type == "cuda")
        with torch.inference_mode(), autocast:
            while _TOKENS_PER_WINDOW * self.next_window + _WINDOW_TOKENS <= self.total:
                start = _TOKENS_PER_WINDOW * self.next_window - self.base
                clip = self.latents[:, :, start : start + _WINDOW_TOKENS]
                decoded = self.model._adaptive_decode(clip)
                if int(decoded.shape[2]) != 4 * _WINDOW_TOKENS:
                    raise RuntimeError(f"video VAE window returned {decoded.shape[2]} frames")
                primary = decoded[:, :, _PRE_PAD : _PRE_PAD + _PRIMARY_FRAMES]
                overlap = decoded[:, :, 4 * _TOKENS_PER_WINDOW + _PRE_PAD :].contiguous()
                if self.overlap is not None:
                    primary = self.model.blend(self.overlap, primary, _OVERLAP_FRAMES, dim=-3)
                outputs.append(primary)
                self.overlap = overlap
                self.next_window += 1
                self.frames_emitted += _PRIMARY_FRAMES
            # drop latents no longer needed by any future window
            keep_from = _TOKENS_PER_WINDOW * self.next_window
            if keep_from > self.base:
                self.latents = self.latents[:, :, keep_from - self.base :].contiguous()
                self.base = keep_from
        return torch.cat(outputs, dim=2) if outputs else None

    def push(self, latents: Any) -> tuple[int, np.ndarray | None]:
        """Collective: append latents; return (frame_start, uint8 [T,H,W,3] on rank 0 or None)."""

        frame_start = self.frames_emitted
        frames = self.advance(latents)
        if frames is None or self.rank != 0:
            return frame_start, None
        return frame_start, self._to_uint8(frames)

    def flush(self) -> tuple[int, np.ndarray | None]:
        """Emit the held 5-frame overlap of the last window (end of a session)."""

        if self.overlap is None:
            return self.frames_emitted, None
        frame_start = self.frames_emitted
        frames = self._to_uint8(self.overlap) if self.rank == 0 else None
        self.frames_emitted += _OVERLAP_FRAMES
        self.overlap = None
        return frame_start, frames


class StreamingAudioDecoder:
    """Rank-0 sliding-window audio VAE decode aligned to emitted video frames."""

    def __init__(self, decoder: Any, *, device: Any, left: int = 48, right: int = 24) -> None:
        import torch

        self.torch = torch
        self.device = device
        self.config = decoder.audio_config
        self.vae = decoder.audio_vae.to(device).eval()
        self.left = int(left)
        self.right = int(right)
        self.reset()

    def reset(self) -> None:
        self.latents = None  # [2, 32, L] float32 (normalized, as produced by the teacher)
        self.base = 0
        self.total = 0

    def append(self, latents: Any) -> None:
        latents = latents.to(device=self.device, dtype=self.torch.float32)
        self.latents = latents if self.latents is None else self.torch.cat((self.latents, latents), dim=2)
        self.total += int(latents.shape[2])

    def decode_range(self, s0: int, s1: int) -> tuple[np.ndarray, dict[str, int]]:
        """Return samples [s0, s1) as float32 [n, 2] plus the context actually used."""

        from taomate_h3.model.output import _reverse_normalize

        torch = self.torch
        if s1 <= s0:
            return np.zeros((0, 2), dtype=np.float32), {"left": 0, "right": 0}
        l0 = max(self.base, s0 // SAMPLES_PER_LATENT - self.left)
        l1 = min(self.total, -(-s1 // SAMPLES_PER_LATENT) + self.right)
        if l1 * SAMPLES_PER_LATENT < s1:
            raise RuntimeError("audio latents do not cover the requested samples")
        z = self.latents[:, :, l0 - self.base : l1 - self.base]
        z = _reverse_normalize(z, mean_values=self.config["latents_mean"],
                               std_values=self.config["latents_std"])
        with torch.inference_mode():
            wave = self.vae.decode(z)  # [2, 1, S]
        if wave.ndim != 3 or int(wave.shape[1]) != 1:
            raise RuntimeError(f"unexpected audio VAE output {tuple(wave.shape)}")
        if int(wave.shape[2]) != (l1 - l0) * SAMPLES_PER_LATENT:
            raise RuntimeError("audio VAE hop differs from 800 samples/latent")
        start = s0 - l0 * SAMPLES_PER_LATENT
        segment = wave[:, 0, start : start + (s1 - s0)].float().transpose(0, 1).contiguous()
        # trim latents that no future call can need
        keep_from = max(self.base, s1 // SAMPLES_PER_LATENT - self.left - 1)
        if keep_from > self.base:
            self.latents = self.latents[:, :, keep_from - self.base :].contiguous()
            self.base = keep_from
        used = {"left": s0 // SAMPLES_PER_LATENT - l0, "right": l1 - (-(-s1 // SAMPLES_PER_LATENT))}
        return segment.cpu().numpy(), used

    def decode_full(self, latents: Any) -> np.ndarray:
        """One-shot decode of a complete latent timeline (for parity checks)."""

        from taomate_h3.model.output import _reverse_normalize

        z = _reverse_normalize(latents.to(device=self.device, dtype=self.torch.float32),
                               mean_values=self.config["latents_mean"],
                               std_values=self.config["latents_std"])
        with self.torch.inference_mode():
            wave = self.vae.decode(z)
        return wave[:, 0].float().transpose(0, 1).contiguous().cpu().numpy()


__all__ = [
    "SAMPLES_PER_LATENT",
    "StreamingAudioDecoder",
    "StreamingVideoDecoder",
    "samples_at_frame",
]
