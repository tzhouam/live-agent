# Codex review round 2: lip sync (fixes for round lipsync1)

Same change as round lipsync1 (instructions and your findings are summarised here), revised. Your round-1 findings and
what was done:
1. chunk_end sent from audio `onended` with incomplete `painted`: onended now only covers a stalled render loop (sent
   at once in a hidden tab, else after 1 s + the offset); render sends chunk_end when the picture reaches the end.
2. high-pass edge spikes: each run's mean is removed and its ends mirrored before the 1 s moving average; remeasured.
3. CI / absolute zero: unrestricted bootstrap interval and main-lobe share are reported; long runs are split into 10 s
   pieces; five real speakers (Wikitongues, CC BY/BY-SA) measured with the same method as the reference for the
   method's zero (results file). The "no server-side shift" conclusion now rests on the model offset lying inside that
   reference spread.
4. offset change stranding a frame: chunks are kept until `t >= end + 0.35 s` (largest positive offset + margin); the
   draw test now requires `t >= start` (moving back produced a negative index, drawImage(undefined) threw and, since
   the loop re-armed rAF at its end, stopped the picture: found by the new check); render errors can no longer stop the
   loop (try/catch around the frame body).
5. one-refresh display term: labelled as an estimate (no page API gives photon time); the calibration covers the chain.
6. fallback clock: baseLatency + outputLatency.
7. self-referential page check: added injected-latency checks against AudioContext.currentTime (getOutputTimestamp
   reporting 250 ms, and the fallback), offset change 0 -> +300 mid-playback (no stall), stop on a new comment (nothing
   from before the stop drawn), reconnect (one render loop); tests use the 34/34/34/17 shape.
8. calibration: a second click cancels the first; beeps go straight to the destination (push-to-talk ducking only
   affects outGain); help text says to test when the teacher is quiet and after changing headsets; a devicechange
   notice when an offset is set.

Inlined: the page diff against HEAD (all lip-sync hunks), tools/av_sync.py, scripts/lipsync_page_check.py,
tests/test_av_alignment.py, the results file. Check that each fix is correct and complete, and find anything new, most
severe first: file:line or function, concrete failure scenario, severity, fix. Say explicitly if a round-1 finding is
still open. Skip style.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/reviews/lipsync2_page.patch =====
diff --git a/live_agent/server/static/index.html b/live_agent/server/static/index.html
index 3f86aa3..9ac28f0 100644
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
+        <div class="meta" id="avHelp">口型已按声卡报告的输出延迟自动对齐。蓝牙耳机常比报告的多慢 0.1–0.3 秒：最好在老师不说话时点「测试」，拖动滑块直到画面闪光和“嘀”声同时出现（声音晚就往右拖）。设置只保存在这个浏览器里，换了耳机或音箱请重新测试。</div>
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
 
@@ -589,8 +607,14 @@ function schedule(c) {
   const q = {...c, start, end: start + dur, src, startedSent: false, endedSent: false};
   // Playback acks also come from the audio clock: in a background tab requestAnimationFrame stops (no frames are
   // painted, so render() sends nothing) while the audio plays on, and the server would stop locking new clips.
+  // In a visible tab the picture can still be on this chunk when its audio ends (output delay, "画面延后"), and
+  // render() sends chunk_end with the complete list of painted frames when the picture ends; this is the fallback.
   const ep = epoch;
-  src.onended = () => { if (ep === epoch) ackChunk(q); };
+  src.onended = () => {
+    if (ep !== epoch) return;
+    if (document.hidden) ackChunk(q);
+    else setTimeout(() => { if (ep === epoch) ackChunk(q); }, 1000 + Math.max(0, avOffsetMs));
+  };
   queue.push(q);
 }
 
@@ -607,6 +631,7 @@ function ackChunk(q) {  // start/end acks with their scheduled times; painted fr
 }
 
 function stopAll() {
+  if (window.__avTrace) window.__avTrace.push({stop: true, p: performance.now()});  // test hook
   epoch += 1; pending = null; decoding = [];
   $("caption").textContent = "";  // the scripted caption must not outlive a barge-in or erasure
   for (const q of queue) { try { q.src.stop(); } catch (e) {} }
@@ -625,12 +650,82 @@ function ctxToPerf(t) {
 function heardTime() {
   const o = audioCtx.getOutputTimestamp ? audioCtx.getOutputTimestamp() : null;
   if (o && o.performanceTime > 0 && o.contextTime > 0) return o.contextTime + (performance.now() - o.performanceTime) / 1000;
-  return audioCtx.currentTime - (audioCtx.outputLatency || audioCtx.baseLatency || 0);
+  return audioCtx.currentTime - ((audioCtx.baseLatency || 0) + (audioCtx.outputLatency || 0));  // both stages
 }
 
-function render() {
+// ---------------------------------------------------------------- lip sync
+// A frame is drawn for the sound the listener hears when that frame reaches the screen: the heard time (above), plus
+// one display refresh (a canvas drawn now appears at the next vsync at the earliest; the real display delay is not
+// observable from a page, so this is an estimate), minus the viewer's own offset ("画面延后": Bluetooth headsets often
+// add more delay than the device reports; the beep-and-flash test measures the whole chain by eye and ear).
+// Caption and board switch on the same clock.
+const AV_KEY = "liveagent.avOffsetMs", AV_MAX_S = 0.3, RETAIN_S = AV_MAX_S + 0.05;
+let avOffsetMs = 0, refreshS = 1 / 60, lastRaf = 0, rendering = false, calib = null;
+try { avOffsetMs = Math.max(-300, Math.min(300, Number(localStorage.getItem(AV_KEY)) || 0)); } catch (e) {}
+function mediaTime() { return heardTime() + refreshS - avOffsetMs / 1000; }
+function startRender() { if (!rendering) { rendering = true; requestAnimationFrame(render); } }
+function setAvOffset(ms) {
+  avOffsetMs = Math.max(-AV_MAX_S * 1000, Math.min(AV_MAX_S * 1000, Math.round(ms / 10) * 10));
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
+  if (calib) calib.oscs.forEach(o => { try { o.stop(); } catch (e) {} });  // a second click restarts the test
+  const t0 = audioCtx.currentTime + 0.3, times = [], oscs = [];
+  for (let i = 0; i < 6; i++) {
+    const t = t0 + i * 0.8, osc = audioCtx.createOscillator(), env = audioCtx.createGain();
+    osc.frequency.value = 1000; env.gain.setValueAtTime(0, t);
+    env.gain.linearRampToValueAtTime(0.5, t + 0.005); env.gain.setValueAtTime(0.5, t + 0.07);
+    env.gain.linearRampToValueAtTime(0, t + 0.08);
+    osc.connect(env).connect(audioCtx.destination);  // not through outGain: push-to-talk ducking must not mute it
+    osc.start(t); osc.stop(t + 0.09);
+    times.push(t); oscs.push(osc);
+  }
+  calib = {times, oscs, until: t0 + 6 * 0.8};
+  startRender(); setTimeout(avInfo, 500);
+};
+setAvOffset(avOffsetMs);
+if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {  // a new headset has its own delay
+  navigator.mediaDevices.addEventListener("devicechange", () => {
+    if (avOffsetMs) chat("sys", "音频设备有变化：如果口型和声音又对不上，打开「音画同步」重新测试。");
+  });
+}
+
+function render(ts) {
+  try { renderFrame(ts); }
+  catch (e) { console.error("render", e); }  // one bad frame must not stop the picture for the rest of the session
+  if (rendering) requestAnimationFrame(render);
+}
+
+function renderFrame(ts) {
+  if (window.__avTrace) window.__avRenders = (window.__avRenders || 0) + 1;  // test hook: one loop, not two
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
@@ -638,11 +733,14 @@ function render() {
         if (q.meta.transcript) $("caption").innerHTML = `<small>台词</small>${esc(q.meta.transcript)}`;
         if (q.meta.board) showBoard(q.meta.board);  // the board point being spoken, as this chunk starts
       }
-      if (q.startedSent && t < q.end && q.frames.length) {
-        const idx = Math.min(q.frames.length - 1, Math.floor((t - q.start) / (q.end - q.start) * q.frames.length));
+      if (q.startedSent && t >= q.start && t < q.end && q.frames.length) {  // t can move back (offset change)
+        const idx = Math.max(0, Math.min(q.frames.length - 1, Math.floor((t - q.start) / (q.end - q.start) * q.frames.length)));
         g.drawImage(q.frames[idx], 0, 0, canvas.width, canvas.height);
         (q.painted = q.painted || new Set()).add(idx);  // frames actually shown (QC evidence)
         q.lastPaint = performance.now();
+        if (window.__avTrace) window.__avTrace.push({t, heard: heardTime(), ctx: audioCtx.currentTime, p: performance.now(),
+                                                     start: q.start, end: q.end, idx, n: q.frames.length,
+                                                     key: `${q.meta.request}/${q.meta.chunk}`});
       }
       if (!q.endedSent && t >= q.end) {
         q.endedSent = true;
@@ -650,9 +748,10 @@ function render() {
               painted: Array.from(q.painted || []), tp_last_paint: q.lastPaint});
       }
     }
-    queue = queue.filter(q => !q.endedSent);
+    // a chunk leaves only when its picture is done, plus the largest "画面延后": moving the slider can take the
+    // picture back into a chunk that just ended, and its frames must still be there
+    queue = queue.filter(q => !(q.endedSent && t >= q.end + RETAIN_S));
   }
-  requestAnimationFrame(render);
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
Checks that do not rely on the page's own heard-time value:
  4. an injected output delay (getOutputTimestamp reporting 250 ms, then the fallback with baseLatency +
     outputLatency) must move the picture by exactly that much against AudioContext.currentTime;
  5. moving the offset from 0 to +300 ms mid-playback must not stall the picture (the chunk it goes back into is kept);
  6. after a stop (a new comment makes the server switch to the reply), nothing from before the stop is drawn;
  7. after a reconnect the render loop runs once per display refresh (not twice).

It cannot see the screen or hear the speaker: the physical display and output delay are what the offset setting and
its beep-and-flash test are for.

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


def paints(tr: list[dict]) -> list[dict]:
    return [x for x in tr if "idx" in x]


def playback(page, offset_ms: int, seconds: float) -> dict:
    page.evaluate(f"setAvOffset({offset_ms}); window.__avTrace = [];")
    time.sleep(seconds)
    tr = paints(page.evaluate("window.__avTrace.splice(0)"))
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


def injected_latency(page, seconds: float) -> dict:
    """The picture must follow a reported output delay, measured against AudioContext.currentTime."""
    out = {}
    page.evaluate("setAvOffset(0)")
    for name, patch, delay_js in (
            ("getOutputTimestamp 250 ms", "audioCtx.getOutputTimestamp = () => ({contextTime: audioCtx.currentTime - 0.25,"
                                          " performanceTime: performance.now()});", "0.25"),
            ("fallback base+output latency", "audioCtx.getOutputTimestamp = undefined;",
             "(audioCtx.baseLatency || 0) + (audioCtx.outputLatency || 0)")):
        page.evaluate(patch + " window.__avTrace = [];")
        time.sleep(seconds)
        tr = paints(page.evaluate("window.__avTrace.splice(0)"))
        delay = page.evaluate(delay_js) * 1000
        refresh = page.evaluate("refreshS") * 1000
        d = [(x["t"] - x["ctx"]) * 1000 for x in tr]
        med = st.median(d) if d else None
        exp = -delay + refresh
        out[name] = {"paints": len(tr), "media_minus_context_ms": round(med, 1) if d else None,
                     "expected_ms": round(exp, 1), "ok": bool(tr) and abs(med - exp) < 5}
    page.evaluate("delete audioCtx.getOutputTimestamp; 0")  # the instance override goes, the prototype method is back
    return out


def offset_change(page) -> dict:
    """0 -> +300 ms mid-playback: the picture goes back 300 ms and must keep drawing (no stall, right frames)."""
    page.evaluate("setAvOffset(0); window.__avTrace = [];")
    time.sleep(3)
    page.evaluate("window.__avSwitch = performance.now(); setAvOffset(300);")
    time.sleep(3)
    tr = paints(page.evaluate("window.__avTrace.splice(0)"))
    sw = page.evaluate("window.__avSwitch")
    ps = [x["p"] for x in tr]
    around = [b - a for a, b in zip(ps, ps[1:]) if a <= sw + 500 and b >= sw - 500]
    wrong = sum(1 for x in tr if x["idx"] != min(x["n"] - 1, int((x["t"] - x["start"]) / (x["end"] - x["start"]) * x["n"])))
    return {"paints": len(tr), "max_gap_near_switch_ms": round(max(around), 1) if around else None,
            "wrong_index": wrong, "ok": bool(around) and max(around) < 60 and wrong == 0}


def stop_switch(page, prompt: str) -> dict:
    """A new comment: the server switches to the reply and tells the page to stop; old chunks must not be drawn."""
    page.evaluate("setAvOffset(0); window.__avTrace = [];")
    time.sleep(1)
    page.fill("#text", prompt)
    page.press("#text", "Enter")
    time.sleep(12)
    tr = page.evaluate("window.__avTrace.splice(0)")
    stops = [i for i, x in enumerate(tr) if x.get("stop")]
    if not stops:
        return {"stops": 0, "ok": None, "note": "the server did not switch (nothing was playing ahead)"}
    i = stops[-1]
    before = {int(x["key"].split("/")[0]) for x in paints(tr[:i])}
    after = [x for x in paints(tr[i + 1:])]
    stale = [x["key"] for x in after if before and int(x["key"].split("/")[0]) <= max(before)]
    return {"stops": len(stops), "paints_after": len(after), "stale_after_stop": len(stale), "ok": not stale}


def reconnect(page) -> dict:
    """A live server holds one session at a time and releases it a few seconds after a disconnect ("busy" until
    then), so reconnecting retries."""
    page.click("#disconnect")
    deadline = time.time() + 60
    while True:
        time.sleep(2)
        page.click("#connect")
        try:
            page.wait_for_selector("#text:not([disabled])", timeout=8000)
            time.sleep(1)
            if page.evaluate("ws && ws.readyState === 1"):
                break
        except Exception:  # noqa: BLE001 - refused while the old session is being released
            pass
        if time.time() > deadline:
            return {"ok": False, "note": "could not reconnect within 60 s"}
        page.wait_for_selector("#connect:not([disabled])", timeout=10000)
    page.evaluate("window.__avTrace = []; window.__avRenders = 0;")
    t0 = time.time()
    time.sleep(2)
    n = page.evaluate("window.__avRenders")
    rate = n / (time.time() - t0)
    per_refresh = rate * page.evaluate("refreshS")
    return {"renders_per_refresh": round(per_refresh, 2), "ok": 0.8 < per_refresh < 1.2}


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
    ap.add_argument("--second-prompt", default="换个话题，说说你的爱好", help="a comment mid-playback (stop check)")
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
        def check(name, fn, *args):
            try:
                r = fn(*args)
            except Exception as e:  # noqa: BLE001 - report it and go on with the other checks
                r = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
            res.update(r if name is None else {name: r})

        for off in (0, 200, -100):
            check(f"playback offset {off:+d} ms", playback, page, off, a.seconds)
        check(None, lambda: {f"injected: {k}": v for k, v in injected_latency(page, min(a.seconds, 5)).items()})
        check("offset change 0 -> +300 ms", offset_change, page)
        check("stop on a new comment", stop_switch, page, a.second_prompt)
        check("reconnect", reconnect, page)
        if page.evaluate("!!ws && ws.readyState === 1"):
            page.click("#disconnect")
        check("calibration offset +120 ms", calibration, page, 120)
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

FPS, SR = 24.0, 32000
SHAPE = [34, 34, 34, 17]  # one TaoMate-H3 request: four phases of frames at 24 fps, 32 kHz stereo audio
# (chunk, frame within the chunk). Not the final frame: the recorder's final mux (-shortest) may trim the last
# tens of ms of audio at the very end of a recording, which is a session-end effect, not a sync one.
FLASHES = [(0, 10), (1, 5), (2, 30), (3, 12)]


def _chunks():
    """Audio lengths as the stream decoder releases them: samples_at(end) - samples_at(start) on one timeline."""
    out, start = [], 0
    for k, n in enumerate(SHAPE):
        video = np.full((n, 64, 64, 3), 30, np.uint8)
        audio = np.zeros((int(start + n) * SR // int(FPS) - start * SR // int(FPS), 2), np.float32)
        for c, f in FLASHES:
            if c == k:
                video[f] = 250
                s = (start + f) * SR // int(FPS) - start * SR // int(FPS)
                audio[s:s + 64] = 0.9  # a 2 ms click at the flash frame's start
        out.append(Chunk(request_index=0, chunk_index=k, n_frames=n, fps=FPS, video=video, audio=audio, sample_rate=SR))
        start += n
    return out


def _expected_times():
    return [(sum(SHAPE[:c]) + f) / FPS for c, f in FLASHES]


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
    """Each chunk's PCM covers its frames to within one sample (the page schedules chunk k at the previous start plus
    n_frames / fps and maps frame i to start + i / fps, so a click stays with its flash)."""
    from live_agent.server.app import to_pcm16

    start = 0
    for ch in _chunks():
        pcm = np.frombuffer(to_pcm16(ch.audio, int(ch.duration_s * SR)), np.int16)
        assert abs(len(pcm) - ch.n_frames / FPS * SR) < 1  # no padding or trimming that would shift the clock
        for c, f in FLASHES:
            if c == ch.chunk_index:
                click = np.flatnonzero(np.abs(pcm) > 20000)[0] / SR
                assert abs(click - f / FPS) < 1 / SR + 1e-9  # where the page will show the flash frame
        start += ch.n_frames

===== FILE: docs/reviews/lipsync2_results.md =====
# Lip-sync measurements (evidence for review lipsync2), all measured locally 2026-09-30 / 10-01

## Method zero on real, presumably synchronous speech (Wikimedia Commons, Wikitongues; 480p transcodes, first 300 s)
| clip | licence | offset (ms) | 95% CI main lobe | runs | speech (s) | peak corr |
|---|---|---|---|---|---|---|
| Jesse speaking English (Wikitongues and AfroCrowd) | CC BY-SA 4.0 | 79.0 | [71.1, 85.6] | 40 | 256.4 | 0.164 |
| Leena speaking English (Wikitongues and AfroCrowd) | CC BY-SA 4.0 | -52.1 | [-63.0, -41.4] | 38 | 225.5 | 0.214 |
| WIKITONGUES- Chengxi speaking Hanghzounese | CC BY-SA 4.0 | -166.6 | [-183.8, -148.0] | 18 | 107.4 | 0.264 |
| WIKITONGUES- Orsolya speaking Hungarian | CC BY 3.0 | -78.7 | [-97.3, -56.2] | 9 | 89.5 | 0.232 |
| WIKITONGUES- Tao speaking Yunnan Mandarin with Thai and Taiwanese accent | CC BY-SA 4.0 | -104.1 | [-113.7, -95.1] | 12 | 117.0 | 0.273 |

Median -78.7 ms, range -166.6..+79.0 ms: by this method real speech shows the jaw opening ahead of the level peaks by
about 50-100 ms, with a per-recording spread of about +-90 ms (each source's own capture offset and speaking style;
the sources' sync is not independently known).

## Model output (TaoMate-H3, two GPUs, merge off), after the edge fix and 10 s run pieces
| recording | speech (s) | runs | offset (ms) | 95% CI main lobe | 95% CI unrestricted | main-lobe share | peak corr |
|---|---|---|---|---|---|---|---|
| sess-aea89030eebf (330 s lesson, 2026-09-30) | 84.9 | 31 | -44.8 | [-64.9, -30.1] | [-69.4, 333.3] | 0.923 | 0.161 |
| sess-1ff5d1bb12c0 (2026-09-29) | 38.4 | 15 | -37.9 | [-69.8, -14.5] | [-333.3, 203.7] | 0.712 | 0.123 |

Self-checks (audio delayed by N frames): aea N=+2 -127.7 ms (delta -82.9), N=-2 +37.0 (delta +81.8); 1ff5 N=+2 -120.0, N=-2 +47.5.
Conclusion used: the model's offset lies inside the spread of real speech measured the same way, so there is no basis for a
server-side shift; the method cannot certify absolute sync better than that spread.

## Server media paths: tests/test_av_alignment.py (recording and wire format, 34/34/34/17 shape) and tests/test_fmp4.py

## Page clock: scripts/lipsync_page_check.py on the live stack (8200 demo, real H.264), 2026-10-01
- playback offset +0 ms: {"paints": 603, "chunks": 9, "media_minus_heard_ms": 16.7, "expected_ms": 16.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset +200 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": -183.3, "expected_ms": -183.3, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset -100 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": 116.7, "expected_ms": 116.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- injected: getOutputTimestamp 250 ms: {"paints": 301, "media_minus_context_ms": -233.3, "expected_ms": -233.3, "ok": true}
- injected: fallback base+output latency: {"paints": 300, "media_minus_context_ms": -25.3, "expected_ms": -25.3, "ok": true}
- offset change 0 -> +300 ms: {"paints": 361, "max_gap_near_switch_ms": 22.7, "wrong_index": 0, "ok": true}
- stop on a new comment: {"stops": 1, "paints_after": 200, "stale_after_stop": 0, "ok": true}
- reconnect: {"renders_per_refresh": 1.0, "ok": true}
- calibration offset +120 ms: {"beeps": 6, "flashes": 6, "flash_minus_beep_ms": [114.4, 114.1, 114.1, 114.0, 113.9, 114.0], "expected_ms": 103.3, "ok": true}
- phone_no_horizontal_scroll: true
- page_errors: []

Same checks pass on the CPU mock server (calibration 113.6-113.8 ms; offset change max gap 17.2 ms).
