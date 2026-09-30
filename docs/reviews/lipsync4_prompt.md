# Codex review round 4: lip sync (fixes for round lipsync3)

Your round-3 findings and what was done:
1. (major) end evidence stale after a backward move: taken as your second option -- the first chunk_end is a snapshot;
   paints after it (the slider taking the picture back into an ended chunk) are not reported, so `painted` stays
   conservative and the server's E is a lower bound in that case. Commented at the chunk_end send; recorded in the
   decision. (Re-sending evidence would change the server's ack protocol for a slider-drag corner case.)
2. (major) fallback could wait forever while renderFrame throws: the fallback now looks at `lastGoodRender` (set only
   after renderFrame returns without an error), not `lastRaf`.
3. (minor) the check did not force re-entry into an ended chunk or check the board: the page itself waits (rAF) for a
   boundary between requests, switches the offset right after it, and the check asserts the first paint after a
   backward switch is the chunk that just ended with its chunk_end already sent, and that every paint shows its own
   chunk's caption and board (trace records `board`, `shown`). Live result during a lesson: backward switches crossed
   request boundaries where both the line and the board differ; re-entered the ended chunk; caption/board correct on
   every paint; longest pause 17.9-21.3 ms.

Inlined: the page diff against HEAD, scripts/lipsync_page_check.py, the live results. Confirm the fixes, say which
earlier findings are still open (absolute zero stays open as reported), and find anything new, most severe first.
Skip style.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/reviews/lipsync4_page.patch =====
diff --git a/live_agent/server/static/index.html b/live_agent/server/static/index.html
index 3f86aa3..4ccc2af 100644
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
 
@@ -521,7 +539,9 @@ function fitBoard() {  // shrink the text until every shown point fits: the poin
 addEventListener("resize", layoutStage);
 addEventListener("load", layoutStage);
 
+let shownBoard = null;  // the board view on display (the chunk on screen switches it only when it differs)
 function showBoard(b) {
+  shownBoard = b;
   const el = $("board");
   if (!el.classList.contains("on")) { el.classList.add("on"); layoutStage(); }
   if (el.dataset.key !== b.key) {
@@ -586,11 +606,22 @@ function schedule(c) {
   const dur = m.duration || m.n_frames / m.fps;
   const src = audioCtx.createBufferSource(); src.buffer = buf; src.connect(outGain()); src.start(start);
   playhead = start + dur;
-  const q = {...c, start, end: start + dur, src, startedSent: false, endedSent: false};
+  if (c.meta.board) lastBoard = c.meta.board;  // chunk 0 of a request carries its board; later chunks show the same
+  const q = {...c, start, end: start + dur, src, startedSent: false, endedSent: false, board: lastBoard};
   // Playback acks also come from the audio clock: in a background tab requestAnimationFrame stops (no frames are
   // painted, so render() sends nothing) while the audio plays on, and the server would stop locking new clips.
+  // In a visible tab the picture can still be on this chunk when its audio ends (output delay, "画面延后"), and
+  // render() sends chunk_end with the complete list of painted frames when the picture ends; this is the fallback.
   const ep = epoch;
-  src.onended = () => { if (ep === epoch) ackChunk(q); };
+  src.onended = () => {
+    const check = () => {
+      if (ep !== epoch || q.endedSent) return;
+      // no frame rendered (without an error) for 0.5 s: the render loop is stalled or failing, ack from the audio clock
+      if (document.hidden || performance.now() - lastGoodRender > 500) ackChunk(q);
+      else setTimeout(check, 250);  // render() sends chunk_end itself when the picture reaches the end
+    };
+    check();
+  };
   queue.push(q);
 }
 
@@ -607,6 +638,7 @@ function ackChunk(q) {  // start/end acks with their scheduled times; painted fr
 }
 
 function stopAll() {
+  if (window.__avTrace) window.__avTrace.push({stop: true, p: performance.now()});  // test hook
   epoch += 1; pending = null; decoding = [];
   $("caption").textContent = "";  // the scripted caption must not outlive a barge-in or erasure
   for (const q of queue) { try { q.src.stop(); } catch (e) {} }
@@ -625,34 +657,116 @@ function ctxToPerf(t) {
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
+// chunks stay drawable this long after their end: the slider can move the picture back by its whole range (-300 -> +300)
+const AV_KEY = "liveagent.avOffsetMs", AV_MAX_S = 0.3, RETAIN_S = 2 * AV_MAX_S + 0.05;
+let avOffsetMs = 0, refreshS = 1 / 60, lastRaf = 0, rendering = false, calib = null, onScreen = null, lastBoard = null;
+let lastGoodRender = 0;  // performance time of the last frame rendered without an error
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
+  try { renderFrame(ts); lastGoodRender = performance.now(); }
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
         send({type: "chunk_start", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.start)});
+      }
+      if (t >= q.start && t < q.end && onScreen !== q) {  // caption and board of the chunk on screen, in either
+        onScreen = q;                                      // direction (the slider can move the picture back)
         if (q.meta.transcript) $("caption").innerHTML = `<small>台词</small>${esc(q.meta.transcript)}`;
-        if (q.meta.board) showBoard(q.meta.board);  // the board point being spoken, as this chunk starts
+        if (q.board && q.board !== shownBoard) showBoard(q.board);  // the board point being spoken
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
+                                                     key: `${q.meta.request}/${q.meta.chunk}`, line: q.meta.transcript || "",
+                                                     cap: $("caption").textContent, ended: q.endedSent,
+                                                     board: q.board ? q.board.key : null,
+                                                     shown: shownBoard ? shownBoard.key : null});
       }
-      if (!q.endedSent && t >= q.end) {
-        q.endedSent = true;
+      if (!q.endedSent && t >= q.end) {  // a snapshot: if the slider later takes the picture back into this chunk,
+        q.endedSent = true;              // those paints are not reported (painted stays conservative, E a lower bound)
         send({type: "chunk_end", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.end),
               painted: Array.from(q.painted || []), tp_last_paint: q.lastPaint});
       }
     }
-    queue = queue.filter(q => !q.endedSent);
+    // a chunk leaves only when its picture is done plus the slider's whole range: moving the slider can take the
+    // picture back into a chunk that ended, and its frames must still be there
+    queue = queue.filter(q => !(q.endedSent && t >= q.end + RETAIN_S));
   }
-  requestAnimationFrame(render);
 }
 
 // ---------------------------------------------------------------- camera focus check (opt-in)

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
  5. moving the offset mid-playback (0 -> +300, -300 -> +300, +300 -> -300 ms) must not stall the picture (a chunk it
     goes back into is kept), and the caption must be the line of the chunk on screen;
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


def offset_change(page, before: int = 0, after: int = 300) -> dict:
    """An offset change mid-playback moves the picture by (before - after) ms. For a move back, the page switches right
    after a chunk boundary, so the picture must re-enter the chunk that just ended (its chunk_end already sent): its
    frames, caption and board must come back. Either way: no stall, right frames, caption and board of the chunk on
    screen."""
    page.evaluate(f"setAvOffset({before}); window.__avTrace = [];")
    time.sleep(2)
    sw = page.evaluate("""async (after) => {
      const key = () => onScreen ? `${onScreen.meta.request}/${onScreen.meta.chunk}` : null;
      const next = (cond) => new Promise(r => { const f = () => cond() ? r(key()) : requestAnimationFrame(f); f(); });
      // prefer a boundary between requests (new line and, for the teacher, a new board); fall back after 12 s
      const req = (k) => k.split("/")[0], t0 = performance.now();
      let k0 = await next(() => key()), k1;
      for (;;) {
        k1 = await next(() => key() !== k0);  // a boundary just passed: k0 has ended
        if (req(k1) !== req(k0) || performance.now() - t0 > 12000) break;
        k0 = k1;
      }
      const prev = queue.find(q => `${q.meta.request}/${q.meta.chunk}` === k0);
      window.__avSwitch = performance.now(); setAvOffset(after);
      return {k0, k1, request_boundary: req(k1) !== req(k0), prev_ended: !!(prev && prev.endedSent), prev_kept: !!prev,
              lines_differ: !!(prev && onScreen && prev.meta.transcript !== onScreen.meta.transcript),
              boards_differ: !!(prev && onScreen && prev.board !== onScreen.board)};
    }""", after)
    time.sleep(2.5)
    tr = paints(page.evaluate("window.__avTrace.splice(0)"))
    sw_t = page.evaluate("window.__avSwitch")
    ps = [x["p"] for x in tr]
    around = [b - a for a, b in zip(ps, ps[1:]) if a <= sw_t + 500 and b >= sw_t - 500]
    wrong = sum(1 for x in tr if x["idx"] != min(x["n"] - 1, int((x["t"] - x["start"]) / (x["end"] - x["start"]) * x["n"])))
    # caption and board are set before the frame is drawn, so every paint shows its chunk's line and board
    caption_wrong = sum(1 for x in tr if x["line"] and x["line"] not in x["cap"])
    board_wrong = sum(1 for x in tr if x["board"] and x["board"] != x["shown"])
    first_after = next((x for x in tr if x["p"] > sw_t), None)
    back = after > before
    reentered = (first_after is not None and first_after["key"] == sw["k0"] and first_after["ended"]) if back else None
    return {"paints": len(tr), "switch": sw, "first_paint_after": first_after and first_after["key"],
            "reentered_ended_chunk": reentered, "max_gap_near_switch_ms": round(max(around), 1) if around else None,
            "wrong_index": wrong, "caption_not_on_screen_chunk": caption_wrong, "board_not_on_screen_chunk": board_wrong,
            "ok": bool(around) and max(around) < 60 and wrong == 0 and caption_wrong == 0 and board_wrong == 0
                  and (reentered is not False)}


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
        check("offset change 0 -> +300 ms", offset_change, page, 0, 300)
        check("offset change -300 -> +300 ms", offset_change, page, -300, 300)
        check("offset change +300 -> -300 ms", offset_change, page, 300, -300)
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

===== FILE: docs/reviews/lipsync4_results.md =====
# Page check during a live lesson (8200 demo, real H.264, teacher persona with boards), 2026-10-01 00:55
- playback offset +0 ms: {"paints": 604, "chunks": 9, "media_minus_heard_ms": 16.7, "expected_ms": 16.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset +200 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": -183.3, "expected_ms": -183.3, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset -100 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": 116.7, "expected_ms": 116.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- injected: getOutputTimestamp 250 ms: {"paints": 300, "media_minus_context_ms": -233.3, "expected_ms": -233.3, "ok": true}
- injected: fallback base+output latency: {"paints": 300, "media_minus_context_ms": -25.3, "expected_ms": -25.3, "ok": true}
- offset change 0 -> +300 ms: {"paints": 515, "switch": {"k0": "16/3", "k1": "17/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "16/3", "reentered_ended_chunk": true, "max_gap_near_switch_ms": 17.9, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- offset change -300 -> +300 ms: {"paints": 276, "switch": {"k0": "17/3", "k1": "18/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "17/3", "reentered_ended_chunk": true, "max_gap_near_switch_ms": 19.2, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- offset change +300 -> -300 ms: {"paints": 331, "switch": {"k0": "18/3", "k1": "19/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "19/0", "reentered_ended_chunk": null, "max_gap_near_switch_ms": 21.3, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- stop on a new comment: {"stops": 1, "paints_after": 97, "stale_after_stop": 0, "ok": true}
- reconnect: {"renders_per_refresh": 1.0, "ok": true}
- calibration offset +120 ms: {"beeps": 6, "flashes": 6, "flash_minus_beep_ms": [112.9, 113.0, 113.0, 112.9, 112.8, 112.9], "expected_ms": 103.3, "ok": true}
- phone_no_horizontal_scroll: true
- page_errors: []
