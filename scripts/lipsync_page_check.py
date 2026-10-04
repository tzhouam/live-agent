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
  7. after a reconnect the render loop runs once per display refresh (not twice);
  8. while every frame's rendering throws, chunk_end still comes from the audio clock, and drawing resumes after.

It cannot see the screen or hear the speaker: the physical display and output delay are what the offset setting and
its beep-and-flash test are for.

Usage: python scripts/lipsync_page_check.py http://127.0.0.1:8200 [--prompt TEXT] [--seconds 9] [--shots out]
Run it against the frontend of a CPU mock stack (``scripts/run_live.sh demo``) or a live stack
(one live session at a time). For isolated checks, start ``live_agent.backend.app`` with scratch
``--student-store`` / ``--log-dir`` paths, and point the frontend's ``BACKEND_URL`` at that backend.
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


def offset_change(page, before: int = 0, after: int = 300, expect_boards: bool = False) -> dict:
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
                  and sw["request_boundary"] and sw["prev_kept"] and sw["prev_ended"]
                  and (reentered is not False)
                  and (not expect_boards or (sw["lines_differ"] and sw["boards_differ"]))}


def render_error_fallback(page) -> dict:
    """If every frame's rendering throws, the audio clock must still send chunk_end (else the server stops locking new
    requests); the loop must draw again once rendering works."""
    page.evaluate("""() => {
      window.__sent = []; window.__origSend = send; window.__origRF = renderFrame;
      window.send = (m) => { window.__sent.push(m.type); window.__origSend(m); };
      window.renderFrame = () => { throw new Error("forced by lipsync_page_check"); };
    }""")
    time.sleep(4)
    sent = page.evaluate("window.__sent.splice(0)")
    page.evaluate("() => { window.renderFrame = window.__origRF; window.send = window.__origSend; window.__avTrace = []; }")
    time.sleep(1.5)
    resumed = len(paints(page.evaluate("window.__avTrace.splice(0)")))
    ends = sent.count("chunk_end")
    return {"chunk_end_while_failing": ends, "paints_after_restore": resumed, "ok": ends >= 1 and resumed > 0}


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
    ap.add_argument("--expect-boards", action="store_true",
                    help="a lesson is playing: the offset checks must cross a boundary where the line and board change")
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
        check("offset change 0 -> +300 ms", offset_change, page, 0, 300, a.expect_boards)
        check("offset change -300 -> +300 ms", offset_change, page, -300, 300, a.expect_boards)
        check("offset change +300 -> -300 ms", offset_change, page, 300, -300, a.expect_boards)
        check("render errors: audio-clock chunk_end", render_error_fallback, page)
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
