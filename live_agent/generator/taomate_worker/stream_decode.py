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
