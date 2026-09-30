# Codex review: lip sync on the demo page and its measurement (uncommitted change on top of 1da3243)

Context: a real-time digital-teacher demo. A video model (TaoMate-H3 on vLLM-Omni) streams 5 s requests as chunks of
34/34/34/17 frames at 24 fps with 32 kHz audio; the server decodes them and sends each chunk to the browser as one
H.264 segment + PCM. The page (inlined diff of `live_agent/server/static/index.html`) schedules each chunk's PCM on an
AudioContext (`start = max(currentTime + 0.05, playhead)`, `end = start + n_frames / fps`) and draws frames on a canvas
from requestAnimationFrame, choosing frame `floor((t - start) / (end - start) * n)`. The owner asked that "the
teacher's mouth should be aligned with the audio"; an earlier change (D-037) switched `t` from `currentTime` to the
heard time (`getOutputTimestamp`). This change:
1. Page: `t = heardTime() + refreshS - avOffsetMs / 1000` (one display refresh because a canvas drawn now appears at
   the next vsync; a per-viewer offset "画面延后", -300..+300 ms in localStorage, for devices that report too little
   output delay, e.g. Bluetooth); a calibration test (six 1 kHz beeps on the audio clock, a white flash drawn on the
   media clock); a chunk leaves the draw queue only when `t >= end` even if its audio ended (onended ack) first;
   test hooks `window.__avTrace` / `window.__avFlashLog`; the render loop is started once (`startRender`).
2. `tools/av_sync.py`: measures lip sync of a recording from MediaPipe jawOpen vs the audio level (voiced runs,
   high-passed, cross-correlation +-8 frames, parabolic peak, bootstrap CI over runs for the main lobe).
3. `scripts/lipsync_page_check.py`: headless checks of the page clock; `tests/test_av_alignment.py`: flash/click
   alignment through the session recorder and the page wire format.
Measurements are in `docs/reviews/lipsync1_results.md`. Conclusion drawn: the model's lips lead the voice by ~45 ms
(CI about -65..-30 ms), inside perceptual tolerance, so no server-side shift; the page compensates output and display
delay and offers the manual offset for devices that misreport.

Please find correctness bugs and weak conclusions, most severe first. Focus on:
- the clock math: getOutputTimestamp semantics (contextTime/performanceTime), the sign and size of the refresh
  compensation, the offset sign ("画面延后" positive must delay the picture), interaction with `start`/`end`, the
  chunk_start / chunk_end acks and the `painted` QC evidence sent to the server, background tabs (rAF stops), stop /
  barge-in (`stopAll`), reconnects, the calibration beeps vs a live stream (same output gain, push-to-talk ducking);
- whether the queue-filter change can leak chunks or draw a stale chunk over a newer one;
- the measurement method: is jawOpen vs level correlation a valid lip-sync estimate, is the sign convention right,
  is the main-lobe bootstrap CI honest, are the self-checks sufficient, and is "no server-side shift" justified;
- the tests and check script: can they pass while the behaviour is wrong?
For each finding: file:line or function, a concrete failure scenario, severity (high/medium/low), and a fix. Skip style.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/reviews/lipsync1_page.patch =====
diff --git a/live_agent/server/static/index.html b/live_agent/server/static/index.html
index 3f86aa3..ce41aa4 100644
--- a/live_agent/server/static/index.html
+++ b/live_agent/server/static/index.html
@@ -70,6 +70,13 @@
   .board li.hidden { opacity:0; }
   .board li.now { color:#ffe08a; }
   .camview { width: 88px; height: 66px; border-radius: 6px; object-fit: cover; background: #000; transform: scaleX(-1); }
+  .avflash { position:absolute; inset:0; border-radius:10px; background:#fff; opacity:0; pointer-events:none; }
+  .avsync { display:flex; flex-wrap:wrap; gap:8px 12px; align-items:center; margin:0 0 8px; padding:8px 10px;
+            border:1px solid var(--line); border-radius:8px; }
+  .avsync[hidden] { display:none; }
+  .avsync input[type=range] { width:min(260px, 100%); }
+  .avsync output { font-variant-numeric:tabular-nums; min-width:5.5em; }
+  .avsync .meta { flex-basis:100%; }
   .focusline { margin-top: 8px; padding: 6px 10px; border-radius: 8px; background: var(--chip); font-size: 14px; }
   .focusline.focused { box-shadow: inset 4px 0 0 var(--ok); }
   .focusline.distracted, .focusline.absent { box-shadow: inset 4px 0 0 var(--warn); }
@@ -128,6 +135,7 @@
         <div class="screen" id="screenWrap">
           <canvas id="screen" width="480" height="864" aria-label="数字人画面"></canvas>
           <div class="overlay" id="overlay">点击「连接」开始会话</div>
+          <div class="avflash" id="avFlash" aria-hidden="true"></div>
         </div>
         <section class="board" id="board" aria-label="板书" aria-live="polite"><h3 id="boardTitle"></h3>
           <div class="body"><ol id="boardItems"></ol><figure><img id="boardImg" alt=""><figcaption id="boardCap"></figcaption></figure></div>
@@ -148,9 +156,19 @@
         <button class="talk" id="talk" disabled aria-label="按住说话">🎙 按住说话</button>
         <button id="cam" hidden title="摄像头画面只用于判断是否专注，不保存">📷 开启专注检测</button>
         <video id="camView" class="camview" muted playsinline hidden aria-label="摄像头预览"></video>
+        <button id="avBtn" aria-expanded="false" aria-controls="avPanel" title="口型和声音对不上时在这里调整">🔈 音画同步</button>
         <input type="text" id="text" placeholder="输入指令，回车发送（发送即打断当前播放）" disabled aria-label="文字输入">
         <button id="send" disabled>发送</button>
       </div>
+      <div class="avsync" id="avPanel" hidden>
+        <label for="avOffset">画面延后</label>
+        <input type="range" id="avOffset" min="-300" max="300" step="10" value="0" aria-describedby="avHelp">
+        <output id="avOffsetV" for="avOffset">0 ms</output>
+        <button id="avTest">测试：闪光 + 嘀声</button>
+        <button id="avReset">恢复 0</button>
+        <div class="meta" id="avHelp">口型已按声卡报告的输出延迟自动对齐。蓝牙耳机常比报告的多慢 0.1–0.3 秒：点「测试」，拖动滑块直到画面闪光和“嘀”声同时出现（声音晚就往右拖）。设置只保存在这个浏览器里。</div>
+        <div class="meta" id="avInfo"></div>
+      </div>
       <div class="chips" id="chips" aria-label="示例指令"></div>
     </div>
     <div class="card">
@@ -263,7 +281,7 @@ $("connect").onclick = () => {
     $("overlay").style.display = "flex"; $("overlay").textContent = "会话已结束，可重新连接";
   };
   ws.onmessage = onMessage;
-  requestAnimationFrame(render);
+  startRender();
 };
 $("disconnect").onclick = () => { if (ws) ws.close(); };
 
@@ -628,9 +646,63 @@ function heardTime() {
   return audioCtx.currentTime - (audioCtx.outputLatency || audioCtx.baseLatency || 0);
 }
 
-function render() {
+// ---------------------------------------------------------------- lip sync
+// A frame is drawn for the sound the listener hears when that frame reaches the screen: the heard time (above), plus
+// one display refresh (a canvas drawn now appears at the next vsync), minus the viewer's own offset ("画面延后":
+// Bluetooth headsets often add more delay than the device reports). Caption and board switch on the same clock.
+const AV_KEY = "liveagent.avOffsetMs";
+let avOffsetMs = 0, refreshS = 1 / 60, lastRaf = 0, rendering = false, calib = null;
+try { avOffsetMs = Math.max(-300, Math.min(300, Number(localStorage.getItem(AV_KEY)) || 0)); } catch (e) {}
+function mediaTime() { return heardTime() + refreshS - avOffsetMs / 1000; }
+function startRender() { if (!rendering) { rendering = true; requestAnimationFrame(render); } }
+function setAvOffset(ms) {
+  avOffsetMs = Math.max(-300, Math.min(300, Math.round(ms / 10) * 10));
+  $("avOffset").value = avOffsetMs; $("avOffsetV").textContent = `${avOffsetMs > 0 ? "+" : ""}${avOffsetMs} ms`;
+  try { localStorage.setItem(AV_KEY, String(avOffsetMs)); } catch (e) {}
+}
+function avInfo() {
+  if (!audioCtx) { $("avInfo").textContent = ""; return; }
+  const out = Math.max(0, audioCtx.currentTime - heardTime());
+  $("avInfo").textContent = `声卡报告的输出延迟 ≈ ${Math.round(out * 1000)} ms，屏幕刷新 ≈ ${Math.round(refreshS * 1000)} ms（均已自动补偿）`;
+}
+$("avBtn").onclick = () => {
+  const p = $("avPanel"), open = p.hidden;
+  p.hidden = !open; $("avBtn").setAttribute("aria-expanded", String(open));
+  if (open) avInfo();
+};
+$("avOffset").oninput = (e) => setAvOffset(+e.target.value);
+$("avReset").onclick = () => setAvOffset(0);
+$("avTest").onclick = () => {  // six beeps on the audio clock, each with a white flash drawn on the media clock
+  audioCtx = audioCtx || new AudioContext();
+  audioCtx.resume();
+  const t0 = audioCtx.currentTime + 0.3, times = [];
+  for (let i = 0; i < 6; i++) {
+    const t = t0 + i * 0.8, osc = audioCtx.createOscillator(), env = audioCtx.createGain();
+    osc.frequency.value = 1000; env.gain.setValueAtTime(0, t);
+    env.gain.linearRampToValueAtTime(0.5, t + 0.005); env.gain.setValueAtTime(0.5, t + 0.07);
+    env.gain.linearRampToValueAtTime(0, t + 0.08);
+    osc.connect(env).connect(outGain()); osc.start(t); osc.stop(t + 0.09);
+    times.push(t);
+  }
+  calib = {times, until: t0 + 6 * 0.8};
+  startRender(); setTimeout(avInfo, 500);
+};
+setAvOffset(avOffsetMs);
+
+function render(ts) {
+  if (lastRaf && ts > lastRaf) {  // the display's refresh interval, smoothed (60 Hz: 16.7 ms)
+    const dt = (ts - lastRaf) / 1000;
+    if (dt > 0.004 && dt < 0.05) refreshS += 0.1 * (dt - refreshS);
+  }
+  lastRaf = ts || lastRaf;
+  if (calib && audioCtx) {
+    const mt = mediaTime(), on = calib.times.some(b => mt >= b && mt < b + 0.08);
+    if (on && !calib.on && window.__avFlashLog) window.__avFlashLog.push(heardTime());  // test hook
+    calib.on = on; $("avFlash").style.opacity = on ? "0.9" : "0";
+    if (mt > calib.until) { calib = null; $("avFlash").style.opacity = "0"; }
+  }
   if (audioCtx) {
-    const t = heardTime();  // frames, caption and board follow the sound as heard (lip sync)
+    const t = mediaTime();  // frames, caption and board follow the sound as heard (lip sync)
     for (const q of queue) {
       if (!q.startedSent && t >= q.start) {
         q.startedSent = true; $("overlay").style.display = "none";
@@ -643,6 +715,8 @@ function render() {
         g.drawImage(q.frames[idx], 0, 0, canvas.width, canvas.height);
         (q.painted = q.painted || new Set()).add(idx);  // frames actually shown (QC evidence)
         q.lastPaint = performance.now();
+        if (window.__avTrace) window.__avTrace.push({t, heard: heardTime(), start: q.start, end: q.end, idx,
+                                                     n: q.frames.length, key: `${q.meta.request}/${q.meta.chunk}`});
       }
       if (!q.endedSent && t >= q.end) {
         q.endedSent = true;
@@ -650,9 +724,10 @@ function render() {
               painted: Array.from(q.painted || []), tp_last_paint: q.lastPaint});
       }
     }
-    queue = queue.filter(q => !q.endedSent);
+    // a chunk leaves only when its picture is done: with "画面延后" the audio (and its onended ack) ends first
+    queue = queue.filter(q => !(q.endedSent && t >= q.end));
   }
-  requestAnimationFrame(render);
+  if (rendering) requestAnimationFrame(render);
 }
 
 // ---------------------------------------------------------------- camera focus check (opt-in)

===== FILE: tools/av_sync.py =====
"""Lip sync of a talking-persona recording: how far the teacher's mouth is ahead of or behind the voice.

Method (mouth opening against the speech envelope, the usual landmark-based lip-sync measure):
1. MediaPipe Face Landmarker on every frame: mouth opening = inner-lip gap (landmarks 13-14) divided by the outer
   eye-corner distance (33-263), so head size and distance do not matter. Frames without a face are masked.
2. Audio: RMS envelope at each frame's time (40 ms Hann window centred on the frame), in dB.
3. Both signals high-passed over one second (syllable rhythm, not loudness drift), then the normalised
   cross-correlation over +-8 frames; the offset is the lag of its peak, refined by a parabola through the peak.
4. Only continuous speech counts: runs of at least 2 s within 30 dB of loud speech (the page mutes requests without a
   line, and the model still moves the mouth then, often humming). The runs' curves are averaged weighted by length,
   and a bootstrap over runs gives a 95% interval for the main peak (speech repeats every ~8 frames, so the curve
   has side lobes; the point estimate is the global maximum over +-8 frames).

Sign: offset_ms > 0 means the picture is late (the voice leads the lips); < 0 means the lips lead the voice.
Perceptual reference [cited, ITU-R BT.1359-1]: detectable at about +45 ms (voice first) / -125 ms (picture first),
acceptable up to about +90 / -185 ms. Natural speech itself shows the lips opening slightly before the sound
(roughly 0-1 frame at 24 fps [estimate]), so a result within about one frame of zero is "in sync".

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
            for f in c.decode(vs):
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
        for f in c.decode(a):
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
    return x - np.convolve(x, np.ones(k) / k, mode="same")


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
    bridged, at least ``min_len`` s long. Muted requests (digital silence) and long pauses split runs."""
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
            runs.append((i, j))
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
    boot = []
    for _ in range(1000):
        s_ = rng.integers(0, len(c), len(c))
        boot.append(peak((c[s_] * w[s_, None]).sum(axis=0) / w[s_].sum(), near=lobe)[0])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"offset_frames": round(lag, 2), "offset_ms": round(lag / fps * 1000, 1),
            "ci95_ms": [round(lo / fps * 1000, 1), round(hi / fps * 1000, 1)], "peak_corr": round(value, 3),
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

===== FILE: scripts/lipsync_page_check.py =====
"""Headless check of the demo page's lip-sync clock (Chromium via Playwright).

The page draws each frame for the sound the listener hears when the frame reaches the screen: heard time
(AudioContext.getOutputTimestamp) + one display refresh - the viewer's offset ("画面延后"). With a trace hook on,
it records every painted frame; this script checks, for each offset:
  1. media time - heard time = refresh - offset (median within 2 ms);
  2. every painted frame is the one for its media time;
  3. no frame is skipped inside a chunk and every full chunk reaches its last frame (a positive offset must not cut
     the end of a chunk when its audio ends first);
and the calibration test: six beeps on the audio clock, each with a flash drawn on the media clock; the flash must
come on at beep + offset - refresh on the heard clock, within one refresh.

It cannot hear the speaker: physical output delay (e.g. Bluetooth) is what the offset setting is for.

Usage: python scripts/lipsync_page_check.py http://127.0.0.1:8200 [--prompt TEXT] [--seconds 9] [--shots out]
Run it against a CPU mock server (``python -m live_agent.server.app --generator mock --llm-url scripted
--vlm-url mock --asr-url "" --port 8211 --student-store <scratch dir>``) or a live stack (one live session at a time).
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time

from playwright.sync_api import sync_playwright


def playback(page, offset_ms: int, seconds: float) -> dict:
    page.evaluate(f"setAvOffset({offset_ms}); window.__avTrace = [];")
    time.sleep(seconds)
    tr = page.evaluate("window.__avTrace.splice(0)")
    refresh = page.evaluate("refreshS")
    d = [(x["t"] - x["heard"]) * 1000 for x in tr]
    wrong = sum(1 for x in tr if x["idx"] != min(x["n"] - 1, int((x["t"] - x["start"]) / (x["end"] - x["start"]) * x["n"])))
    by: dict[str, list[int]] = {}
    for x in tr:
        by.setdefault(x["key"], []).append(x["idx"])
    skipped = sum(1 for ids in by.values() for a, c in zip(ids, ids[1:]) if c - a > 1)
    full = list(by)[1:-1]  # the first and last chunk of the trace are cut by the trace window
    n_of = {x["key"]: x["n"] for x in tr}
    ends = all(max(by[k]) == n_of[k] - 1 for k in full)
    med = st.median(d) if d else None
    exp = refresh * 1000 - offset_ms
    return {"paints": len(tr), "chunks": len(by), "media_minus_heard_ms": round(med, 1) if d else None,
            "expected_ms": round(exp, 1), "wrong_index": wrong, "skipped_frames": skipped, "chunk_ends_shown": ends,
            "ok": bool(tr) and abs(med - exp) < 2 and wrong == 0 and skipped == 0 and ends}


def calibration(page, offset_ms: int) -> dict:
    page.evaluate(f"setAvOffset({offset_ms})")
    if page.evaluate("$('avPanel').hidden"):
        page.click("#avBtn")
    page.evaluate("window.__avFlashLog = []")  # the page logs the heard time of each flash onset
    page.click("#avTest")
    beeps = page.evaluate("calib.times")
    time.sleep(6)
    fl = page.evaluate("window.__avFlashLog")
    refresh = page.evaluate("refreshS") * 1000
    lag = [(f - t) * 1000 for f, t in zip(fl, beeps)]
    exp = offset_ms - refresh
    return {"beeps": len(beeps), "flashes": len(fl), "flash_minus_beep_ms": [round(x, 1) for x in lag],
            "expected_ms": round(exp, 1),
            "ok": len(fl) == len(beeps) == 6 and all(exp - 1 <= x <= exp + refresh + 1 for x in lag)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("base")
    ap.add_argument("--prompt", default="你好，请介绍一下你自己")
    ap.add_argument("--seconds", type=float, default=9.0)
    ap.add_argument("--warmup", type=float, default=4.0, help="seconds to wait for playback before tracing")
    ap.add_argument("--shots", default="", help="save screenshots of the panel (desktop, phone) with this prefix")
    a = ap.parse_args(argv)
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = b.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(a.base + "/")
        page.click("#connect")
        page.wait_for_selector("#text:not([disabled])", timeout=60000)
        page.fill("#text", a.prompt)
        page.press("#text", "Enter")
        time.sleep(a.warmup)
        for off in (0, 200, -100):
            res[f"playback offset {off:+d} ms"] = playback(page, off, a.seconds)
        page.click("#disconnect")
        res["calibration offset +120 ms"] = calibration(page, 120)
        if a.shots:
            page.screenshot(path=a.shots + "_desktop.png")
            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("$('avPanel').scrollIntoView()")
            page.screenshot(path=a.shots + "_phone.png")
            res["phone_no_horizontal_scroll"] = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.evaluate("setAvOffset(0)")
        res["page_errors"] = errors
        b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    ok = all(v.get("ok", True) for v in res.values() if isinstance(v, dict)) and not res["page_errors"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

===== FILE: tests/test_av_alignment.py =====
"""Audio and video stay aligned through the server's own media paths: the session recording (ffmpeg, AAC) and the
chunk -> page wire format. A white flash and an audio click are placed at the same instants; each path must keep them
within a millisecond or two (lip sync is judged in tens of milliseconds)."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

from live_agent.types import Chunk

av = pytest.importorskip("av")

FPS, SR, N = 24.0, 32000, 34  # the generator's chunk shape (34 frames at 24 fps, 32 kHz stereo)
FLASHES = [(0, 10), (1, 5), (2, 30), (3, 17)]  # (chunk, frame within the chunk)


def _chunks():
    out = []
    for k in range(4):
        video = np.full((N, 64, 64, 3), 30, np.uint8)
        audio = np.zeros((int(round(N / FPS * SR)), 2), np.float32)
        for c, f in FLASHES:
            if c == k:
                video[f] = 250
                s = int(round(f / FPS * SR))
                audio[s:s + 64] = 0.9  # a 2 ms click at the flash frame's start
        out.append(Chunk(request_index=0, chunk_index=k, n_frames=N, fps=FPS, video=video, audio=audio, sample_rate=SR))
    return out


def _expected_times():
    return [(c * N + f) / FPS for c, f in FLASHES]


def _flash_and_click_times(path: Path):
    with av.open(str(path)) as cont:
        vs = cont.streams.video[0]
        flashes = [float(fr.pts * vs.time_base) for fr in cont.decode(vs) if fr.to_ndarray(format="gray").mean() > 150]
    with av.open(str(path)) as cont:
        a = cont.streams.audio[0]
        clicks, prev = [], 0.0
        for fr in cont.decode(a):
            x = np.abs(fr.to_ndarray()).max(axis=0)
            t0 = float(fr.pts * a.time_base)
            for i in np.flatnonzero(x > 0.4):
                t = t0 + i / a.rate
                if t - prev > 0.1:
                    clicks.append(t)
                prev = max(prev, t) if clicks else prev
    return flashes, clicks


@pytest.mark.skipif(not shutil.which("ffmpeg") and not Path("/usr/bin/ffmpeg").exists(), reason="needs ffmpeg")
def test_the_session_recording_keeps_flash_and_click_together(tmp_path):
    from live_agent.sim import Recorder

    rec = Recorder(tmp_path / "s.mp4", ffmpeg=shutil.which("ffmpeg") or "/usr/bin/ffmpeg")
    for ch in _chunks():
        rec._write(ch)  # synchronous path of write()
    rec.close()
    flashes, clicks = _flash_and_click_times(tmp_path / "s.mp4")
    expected = _expected_times()
    assert len(flashes) == len(expected) and len(clicks) == len(expected), (flashes, clicks)
    for e, f, c in zip(expected, flashes, clicks):
        assert abs(f - e) < 1e-3  # the flash frame is where it was put
        assert abs(c - e) < 2e-3, (e, c)  # and so is the click: the AAC encoder delay is hidden by the edit list


def test_the_page_wire_format_keeps_audio_on_the_frame_timeline():
    """Each chunk's PCM covers exactly its frames (the page maps frame i to start + i / fps of the same buffer)."""
    from live_agent.server.app import to_pcm16

    for ch in _chunks():
        pcm = np.frombuffer(to_pcm16(ch.audio, int(ch.duration_s * SR)), np.int16)
        assert len(pcm) == int(round(ch.n_frames / FPS * SR))  # no padding or trimming that would shift the clock
        for c, f in FLASHES:
            if c == ch.chunk_index:
                assert np.flatnonzero(np.abs(pcm) > 20000)[0] == int(round(f / FPS * SR))

===== FILE: docs/reviews/lipsync1_results.md =====
# Lip-sync measurements (evidence for review lipsync1), all measured locally on 2026-09-30

## Model output (TaoMate-H3, two GPUs, merge off), tools/av_sync.py --signal jaw
| recording | speech (s) | runs | offset (ms, >0 picture late) | 95% CI (main lobe) | peak corr |
|---|---|---|---|---|---|
| sess-aea89030eebf (2026-09-30, 330 s lesson on the 8200 demo) | 84.9 | 31 | -45.2 | [-65.3, -30.0] | 0.118 |
| sess-1ff5d1bb12c0 (2026-09-29 two-GPU demo) | 38.4 | 15 | -42.6 | [-72.8, -20.6] | 0.094 |

Self-checks (audio delayed by N frames before measuring; the offset must drop by N frames):
- sess-aea89030eebf: N=0 -1.08 frames, N=+2 -3.01 (delta -1.93), N=-2 +0.93 (delta +2.01)
- sess-1ff5d1bb12c0: N=0 -1.02, N=+3 -3.86 (delta -2.84), N=-3 +2.09 (delta +3.11)
The inner-lip gap signal (landmarks 13/14 over eye distance) did not track the shifts (face ~70 px wide), so jawOpen is the default.
Earlier attempts that failed and why: motion-energy cells (head motion dominates, CI +-300 ms); fixed 5-10 s windows (muted no-line requests are digital silence, the jumps dominated; negative correlation at lag 0).
The USP4 BF16 recording sess-b61bbb5ad485 has only 23 s of speech in 1447 s (idle session), not measured.

## Server media paths (tests/test_av_alignment.py)
- Session recording (ffmpeg libx264 + AAC with edit list): flash vs click within 2 ms at 4 positions.
- Page wire format: each chunk's PCM covers exactly its frames, click at the flash frame's sample.
- fMP4 decoder from the vLLM-Omni stream: sample-accurate tone phase (tests/test_fmp4.py, existing).

## Page clock (scripts/lipsync_page_check.py, headless Chromium, 60 Hz rAF)
Live stack (8200 demo, real H.264 chunks), 12 s per offset:
- playback offset +0 ms: {"paints": 722, "chunks": 11, "media_minus_heard_ms": 16.7, "expected_ms": 16.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset +200 ms: {"paints": 721, "chunks": 11, "media_minus_heard_ms": -183.3, "expected_ms": -183.3, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset -100 ms: {"paints": 720, "chunks": 11, "media_minus_heard_ms": 116.7, "expected_ms": 116.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- calibration offset +120 ms: {"beeps": 6, "flashes": 6, "flash_minus_beep_ms": [112.4, 112.3, 112.2, 112.1, 112.1, 112.2], "expected_ms": 103.3, "ok": true}
- phone_no_horizontal_scroll: true
- page_errors: []
CPU mock server: same checks pass (calibration flash onsets 110.3-110.5 ms for expected 103.3 + up to one refresh).

===== FILE: live_agent/generator/fmp4.py =====
"""Incremental decoder for the fragmented-MP4 stream of the vLLM-Omni realtime video endpoint.

The server sends one binary message per generated phase: the first carries the init segment (``ftyp`` +
``moov``), every message carries ``moof``/``mdat`` fragments of H.264 video and AAC audio. Each message is
demuxed on its own (the init segment is prepended) and its packets are decoded with persistent codec
contexts, so decoder state carries across messages. Video frames are counted in decode order (the
muxer's video pts are off by one frame after frame 0); audio pts is the absolute sample index (measured
locally on the server's own encoder, ``tests/data/vllm_omni_fmp4``: offset 0; only the first 1024 samples of
a stream are AAC priming silence).

Both encoders hold media back at a message boundary (x264 about 2 frames, AAC about 3-4 k samples,
measured locally), so a message's audio ends earlier than its video. ``take()`` releases frames only as far
as their audio has been decoded, which keeps each released chunk in A/V sync: the video is delayed by the
few held-back frames (about 0.1-0.2 s) rather than the audio lagging the lips.
"""

from __future__ import annotations

import io
from fractions import Fraction

import numpy as np


def split_init(data: bytes) -> tuple[bytes, bytes]:
    """(leading ftyp/moov boxes, rest) of an fMP4 message."""
    i = 0
    while i + 8 <= len(data):
        size = int.from_bytes(data[i:i + 4], "big")
        if data[i + 4:i + 8] not in (b"ftyp", b"moov") or size < 8:
            break
        i += size
    return data[:i], data[i:]


class FMP4StreamDecoder:
    def __init__(self, fps: float = 24.0, sample_rate: int = 32000) -> None:
        self.fps = float(fps)
        self.sample_rate = int(sample_rate)
        self._init = b""
        self._vdec = None
        self._adec = None
        self._frames: list[np.ndarray] = []  # decoded, not yet released; frame index of [0] is _vbase
        self._vbase = 0
        self._audio = np.zeros((0, 2), np.float32)  # decoded, not yet released; sample index of [0] is _abase
        self._abase = 0

    def samples_at(self, frame: int) -> int:
        return int(Fraction(frame) * self.sample_rate / Fraction(self.fps).limit_denominator(1000))

    def frame_at(self, sample: int) -> int:
        """Last frame boundary whose audio is complete at ``sample``."""
        return int(Fraction(sample) * Fraction(self.fps).limit_denominator(1000) / self.sample_rate)

    def push(self, data: bytes) -> None:
        """Decode one server message (blocking; call it off the event loop)."""
        import av

        init, _ = split_init(data)
        if init:
            self._init = init
        elif not self._init:
            raise ValueError("fMP4 stream starts without an init segment")
        blob = data if init else self._init + data
        with av.open(io.BytesIO(blob), format="mp4") as container:
            vstream = container.streams.video[0] if container.streams.video else None
            astream = container.streams.audio[0] if container.streams.audio else None
            if self._vdec is None and vstream is not None:
                self._vdec = av.CodecContext.create(vstream.codec_context.name, "r")
                self._vdec.extradata = vstream.codec_context.extradata
                self._vdec.thread_type = "NONE"  # no frame-threading delay: every packet decodes at once
            if self._adec is None and astream is not None:
                self._adec = av.CodecContext.create(astream.codec_context.name, "r")
                self._adec.extradata = astream.codec_context.extradata
                self._adec.sample_rate = astream.codec_context.sample_rate
                self._adec.layout = astream.codec_context.layout
            for packet in container.demux():
                if packet.size == 0 or packet.pts is None:
                    continue
                if packet.stream.type == "video":
                    # frames are counted, not placed by pts: the server's muxer labels frame i >= 1 with pts
                    # i + 1 (measured on the fixture); the stream has no reordering (pts == dts), so decode
                    # order is display order
                    for frame in self._vdec.decode(packet):
                        self._frames.append(frame.to_ndarray(format="rgb24"))
                elif packet.stream.type == "audio":
                    base = packet.stream.time_base
                    for frame in self._adec.decode(packet):
                        pts = packet.pts if frame.pts is None else frame.pts
                        sample_index = int(round(float(pts * base) * self.sample_rate))
                        pcm = frame.to_ndarray()  # planar float: [channels, samples]
                        if pcm.ndim == 1:
                            pcm = pcm[None, :]
                        pcm = pcm.T.astype(np.float32)
                        if pcm.shape[1] == 1:
                            pcm = np.repeat(pcm, 2, axis=1)
                        self._put_audio(sample_index, pcm[:, :2])

    def flush(self) -> None:
        """End of stream: drain the frame the video decoder still holds (it returns frames one packet late)."""
        if self._vdec is not None:
            for frame in self._vdec.decode(None):
                self._frames.append(frame.to_ndarray(format="rgb24"))

    def _put_audio(self, index: int, pcm: np.ndarray) -> None:
        end = self._abase + len(self._audio)
        if index + len(pcm) <= end:
            return
        if index < end:
            pcm = pcm[end - index:]
            index = end
        if index > end:
            pcm = np.concatenate([np.zeros((index - end, 2), np.float32), pcm])
        self._audio = np.concatenate([self._audio, pcm]) if len(self._audio) else pcm

    @property
    def decoded_frames(self) -> int:
        return self._vbase + len(self._frames)

    def take(self, final: bool = False) -> tuple[int, np.ndarray | None, np.ndarray]:
        """Release the frames whose audio is complete (all of them when ``final``).

        Returns ``(frame_start, video [T,H,W,3] uint8 or None, audio [S,2] float32)``; the audio covers exactly
        the released frames on the fps/sample-rate timeline (zero-padded only at the final flush).
        """
        v_end = self.decoded_frames
        a_end = self._abase + len(self._audio)
        edge = v_end if final else min(v_end, self.frame_at(a_end))
        start = self._vbase
        n = max(0, edge - start)
        if n == 0:
            return start, None, np.zeros((0, 2), np.float32)
        video = np.stack(self._frames[:n])
        del self._frames[:n]
        self._vbase += n
        s0, s1 = self.samples_at(start), self.samples_at(start + n)
        lo, hi = s0 - self._abase, s1 - self._abase
        audio = self._audio[max(0, lo):max(0, hi)]
        if lo < 0:  # released frames start before any decoded audio (stream start): silence
            audio = np.concatenate([np.zeros((min(-lo, s1 - s0), 2), np.float32), audio])
        if len(audio) < s1 - s0:
            audio = np.concatenate([audio, np.zeros((s1 - s0 - len(audio), 2), np.float32)])
        drop = max(0, hi)
        self._audio = self._audio[drop:]
        self._abase += drop
        return start, video, np.ascontiguousarray(audio, dtype=np.float32)


__all__ = ["FMP4StreamDecoder", "split_init"]
