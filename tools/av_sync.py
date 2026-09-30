"""Lip sync of a talking-persona recording: how far the teacher's mouth is ahead of or behind the voice.

Method (mouth opening against the speech envelope, the usual landmark-based lip-sync measure):
1. MediaPipe Face Landmarker on every frame: mouth opening = inner-lip gap (landmarks 13-14) divided by the outer
   eye-corner distance (33-263), so head size and distance do not matter. Frames without a face are masked.
2. Audio: RMS envelope at each frame's time (40 ms Hann window centred on the frame), in dB.
3. Both signals high-passed over one second (syllable rhythm, not loudness drift), then the normalised
   cross-correlation over +-8 frames; the offset is the lag of its peak, refined by a parabola through the peak.
4. Only continuous speech counts: runs of at least 2 s within 30 dB of loud speech (the page mutes requests without a
   line, and the model still moves the mouth then, often humming). The runs' curves are averaged weighted by length,
   and a bootstrap over runs gives 95% intervals: for the main peak (+-3 frames around the estimate; speech repeats
   every ~8 frames, so the curve has side lobes) and unrestricted, with the share of bootstrap samples whose global
   peak stays in the main lobe (``main_lobe_share``; near 1 means the estimate is not a side lobe).

Sign: offset_ms > 0 means the picture is late (the voice leads the lips); < 0 means the lips lead the voice.
Perceptual reference [cited, ITU-R BT.1359-1]: detectable at about +45 ms (voice first) / -125 ms (picture first),
acceptable up to about +90 / -185 ms. The method's own zero is not the physical
zero: jaw opening and sound level have a natural phase in real speech. Measure known-synchronous recordings of real
speakers the same way and compare against those, not against 0.

Needs mediapipe (not a project dependency: ``python3.12 -m venv --system-site-packages .cache/venv-avsync &&
.cache/venv-avsync/bin/pip install mediapipe``) and the Face Landmarker model file
(https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task,
saved as .cache/models/face_landmarker.task).

Usage: .cache/venv-avsync/bin/python tools/av_sync.py <recording.mp4> [--start S] [--dur D] [--shift-frames N]
       [--signal jaw|lips] [--plot out.png] [--cache mouth.npz]
``--shift-frames N`` delays the audio by N frames before measuring: a self-check, the offset must drop by N frames.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

MAX_LAG = 8  # frames either way (+-333 ms at 24 fps)
MODEL = Path(__file__).resolve().parent.parent / ".cache" / "models" / "face_landmarker.task"
UPPER_LIP, LOWER_LIP, EYE_L, EYE_R = 13, 14, 33, 263


def _frames(container, stream):
    """Decoded frames of one stream, ending quietly at a damaged or truncated packet (partial downloads)."""
    import av

    it = container.decode(stream)
    while True:
        try:
            yield next(it)
        except StopIteration:
            return
        except (av.error.InvalidDataError, av.error.EOFError, ValueError):
            return


def mouth_opening(path: str, start: float = 0.0, dur: float | None = None, model: Path = MODEL):
    """Per-frame mouth opening and jawOpen blendshape score (NaN where no face was found), the frame times (s,
    absolute) and the fps."""
    import av
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model)),
                                        running_mode=vision.RunningMode.VIDEO, num_faces=1,
                                        output_face_blendshapes=True)
    lm = vision.FaceLandmarker.create_from_options(opts)
    out, jaw, times = [], [], []
    try:
        with av.open(path) as c:
            vs = c.streams.video[0]
            fps = float(vs.average_rate)
            if start > 0:
                c.seek(int(max(0.0, start - 2) / vs.time_base), stream=vs)
            for f in _frames(c, vs):
                t = float(f.pts * vs.time_base)
                if t < start - 1e-6:
                    continue
                if dur is not None and t >= start + dur - 1e-6:
                    break
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(f.to_ndarray(format="rgb24")))
                r = lm.detect_for_video(img, int(round(t * 1000)))
                if r.face_landmarks:
                    p = r.face_landmarks[0]
                    eye = np.hypot(p[EYE_L].x - p[EYE_R].x, p[EYE_L].y - p[EYE_R].y)
                    gap = np.hypot(p[UPPER_LIP].x - p[LOWER_LIP].x, p[UPPER_LIP].y - p[LOWER_LIP].y)
                    out.append(gap / eye if eye > 0 else np.nan)
                    bs = {b.category_name: b.score for b in r.face_blendshapes[0]} if r.face_blendshapes else {}
                    jaw.append(bs.get("jawOpen", np.nan))
                else:
                    out.append(np.nan)
                    jaw.append(np.nan)
                times.append(t)
    finally:
        lm.close()
    return np.array(out), np.array(jaw), np.array(times), fps


def audio_envelope(path: str, times: np.ndarray, half: float = 0.02) -> np.ndarray:
    """RMS level (dB) of the audio in a Hann window of +-``half`` s around each time, placed by audio timestamps."""
    import av

    t0, t1 = float(times[0]) - 1.0, float(times[-1]) + 1.0
    with av.open(path) as c:
        a = c.streams.audio[0]
        sr = a.rate
        buf = np.zeros(int((t1 - t0) * sr) + 1, np.float32)
        if t0 > 0:
            c.seek(int(max(0.0, t0 - 1) / a.time_base), stream=a)
        for f in _frames(c, a):
            if f.pts is None:
                continue
            s0 = int(round((float(f.pts * a.time_base) - t0) * sr))
            if s0 > len(buf):
                break
            x = f.to_ndarray()
            x = x.mean(axis=0) if x.ndim == 2 else x.reshape(-1)
            lo, hi = max(0, s0), min(len(buf), s0 + len(x))
            if hi > lo:
                buf[lo:hi] = x[lo - s0:hi - s0]
    n = int(round(half * sr))
    w = np.hanning(2 * n + 1)
    env = []
    for t in times:
        c0 = int(round((t - t0) * sr))
        seg = buf[max(0, c0 - n):c0 + n + 1]
        ww = w[:len(seg)]
        env.append(10 * np.log10(np.sum(ww * seg.astype(np.float64) ** 2) / np.sum(ww) + 1e-9))
    return np.array(env)


def _highpass(x: np.ndarray, k: int) -> np.ndarray:
    """x minus its centred k-point moving average; the run's mean is removed and its ends are mirrored first, so a
    steady level does not turn into spikes at the edges of the run (zero padding would)."""
    x = x - x.mean()
    h = k // 2
    if len(x) <= h:
        return x
    xp = np.pad(x, (h, k - 1 - h), mode="reflect")
    return x - np.convolve(xp, np.ones(k) / k, mode="valid")


def _fill(x: np.ndarray) -> np.ndarray:
    ok = np.isfinite(x)
    if ok.all() or not ok.any():
        return np.nan_to_num(x)
    idx = np.arange(len(x))
    return np.interp(idx, idx[ok], x[ok])


def xcorr(v: np.ndarray, a: np.ndarray, max_lag: int = MAX_LAG) -> np.ndarray:
    """Normalised correlation of v[t] with a[t - lag] for lag in [-max_lag, max_lag] (lag > 0: picture late)."""
    out = []
    for lag in range(-max_lag, max_lag + 1):
        x, y = (v[lag:], a[:len(a) - lag]) if lag >= 0 else (v[:lag], a[-lag:])
        x, y = x - x.mean(), y - y.mean()
        out.append(float((x * y).sum() / (np.sqrt((x ** 2).sum() * (y ** 2).sum()) + 1e-12)))
    return np.array(out)


def peak(curve: np.ndarray, max_lag: int = MAX_LAG, near: tuple[int, int] | None = None) -> tuple[float, float]:
    """Sub-frame lag of the maximum (parabola through the peak and its neighbours) and the peak value; ``near``
    limits the search to lags [lo, hi] (the main lobe)."""
    if near is None:
        i = int(np.argmax(curve))
    else:
        lo, hi = max(near[0], -max_lag) + max_lag, min(near[1], max_lag) + max_lag
        i = lo + int(np.argmax(curve[lo:hi + 1]))
    off = 0.0
    if 0 < i < len(curve) - 1:
        y0, y1, y2 = curve[i - 1], curve[i], curve[i + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den < 0 else 0.0
    return i - max_lag + off, float(curve[i])


def voiced_runs(env: np.ndarray, fps: float, min_len: float = 2.0, gap: float = 0.3) -> list[tuple[int, int]]:
    """[start, end) frame ranges of continuous speech: within 30 dB of loud speech, short pauses (< ``gap`` s)
    bridged, at least ``min_len`` s long, split into pieces of at most 10 s. Muted requests (digital silence) and
    long pauses split runs."""
    voiced_env = env[np.isfinite(env) & (env > -80)]
    if not len(voiced_env):
        return []
    on = env > np.percentile(voiced_env, 95) - 30
    g = int(round(gap * fps))
    runs, i, n = [], 0, len(on)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j < n and (on[j] or (j + g < n and on[j:j + g + 1].any())):
            j += 1
        if j - i >= min_len * fps:
            step = int(round(10 * fps))  # long runs in 10 s pieces: the bootstrap needs several units
            for a in range(i, j, step):
                b = min(j, a + step)
                if b - a >= min_len * fps:
                    runs.append((a, b))
        i = j + 1
    return runs


def measure(opening: np.ndarray, env: np.ndarray, fps: float, min_face: float = 0.9, seed: int = 0) -> dict:
    """Correlation curves over the voiced runs (weighted by length); 95% bootstrap interval over runs."""
    k = int(round(fps))
    loud = np.percentile(env[env > -80], 95) if (env > -80).any() else 0.0
    env_f = np.maximum(env, loud - 35)  # pauses count as quiet, not as -90 dB
    curves, weights, skipped = [], [], 0
    for i, j in voiced_runs(env, fps):
        o = opening[i:j]
        if np.mean(np.isfinite(o)) < min_face:
            skipped += 1
            continue
        curves.append(xcorr(_highpass(_fill(o), k), _highpass(env_f[i:j], k)))
        weights.append(j - i)
    if not curves:
        return {"runs": 0, "skipped": skipped}
    c, w = np.stack(curves), np.array(weights, float)
    lag, value = peak((c * w[:, None]).sum(axis=0) / w.sum())
    # speech repeats every ~8 frames (syllables), so the curve has side lobes; the interval is for the main lobe
    # (+-3 frames around the peak), the point estimate above is the global maximum
    lobe = (int(round(lag)) - 3, int(round(lag)) + 3)
    rng = np.random.default_rng(seed)
    boot, free = [], []
    for _ in range(1000):
        s_ = rng.integers(0, len(c), len(c))
        cur = (c[s_] * w[s_, None]).sum(axis=0) / w[s_].sum()
        boot.append(peak(cur, near=lobe)[0])
        free.append(peak(cur)[0])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    flo, fhi = np.percentile(free, [2.5, 97.5])
    share = float(np.mean([lobe[0] <= x <= lobe[1] for x in free]))
    return {"offset_frames": round(lag, 2), "offset_ms": round(lag / fps * 1000, 1),
            "ci95_ms": [round(lo / fps * 1000, 1), round(hi / fps * 1000, 1)],
            "ci95_unrestricted_ms": [round(flo / fps * 1000, 1), round(fhi / fps * 1000, 1)],
            "main_lobe_share": round(share, 3), "peak_corr": round(value, 3),
            "curve": [round(float(x), 3) for x in (c * w[:, None]).sum(axis=0) / w.sum()],
            "runs": len(c), "speech_s": round(float(w.sum()) / fps, 1), "skipped": skipped,
            "face_found": round(float(np.mean(np.isfinite(opening))), 3)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=None)
    ap.add_argument("--shift-frames", type=int, default=0, help="delay the audio by N frames first (self-check)")
    ap.add_argument("--plot", default="", help="save the two signals and the correlation curve as a PNG")
    ap.add_argument("--cache", default="", help="reuse / save the per-frame mouth opening (.npz)")
    ap.add_argument("--signal", choices=("lips", "jaw"), default="jaw",
                    help="lips: inner-lip gap / eye distance; jaw: the jawOpen blendshape (default)")
    a = ap.parse_args(argv)
    if a.cache and Path(a.cache).exists():
        z = np.load(a.cache)
        lips, jaw, times, fps = z["lips"], z["jaw"], z["times"], float(z["fps"])
    else:
        lips, jaw, times, fps = mouth_opening(a.path, a.start, a.dur)
        if a.cache:
            np.savez(a.cache, lips=lips, jaw=jaw, times=times, fps=fps)
    opening = jaw if a.signal == "jaw" else lips
    env = audio_envelope(a.path, times - a.shift_frames / fps)  # audio delayed by N frames
    res = measure(opening, env, fps)
    if a.plot and res.get("runs"):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
        n = min(len(times), int(12 * fps))
        loud = np.nanpercentile(env, 95)
        voiced = np.convolve((env > loud - 30).astype(float), np.ones(n), mode="valid")
        i0 = int(np.argmax(voiced))  # the 12 s with the most speech
        sl = slice(i0, i0 + n)
        z = lambda x: (x - np.nanmean(x)) / (np.nanstd(x) + 1e-9)  # noqa: E731
        ax1.plot(times[sl], z(opening[sl]), label="mouth opening (lip gap / eye distance)")
        ax1.plot(times[sl], z(env[sl]), label="audio level (dB)", alpha=0.7)
        ax1.set_xlabel("s"), ax1.legend(loc="upper right")
        lags = np.arange(-MAX_LAG, MAX_LAG + 1) / fps * 1000
        ax2.plot(lags, res["curve"], "o-")
        ax2.axvline(0, color="grey", lw=0.8)
        ax2.axvline(res["offset_ms"], color="red", lw=0.8)
        ax2.set_xlabel("lag (ms, > 0: picture late)"), ax2.set_ylabel("correlation")
        fig.tight_layout()
        fig.savefig(a.plot, dpi=90)
    json.dump(res, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
