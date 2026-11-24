"""Live hosted-teaching check against an isolated puppet server and verification profile.

Runs real provider calls and grades a synthetic answer. Use an isolated backend with
--student verification and separate memory, profiles and recordings. No API key is
read here: the backend owns provider credentials. Screenshots/reports are local.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
import re
from pathlib import Path
import time

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


async def check(args):
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    events, statuses, chunks, browser_errors = [], [], [], []
    report = {"label": "measured locally", "base_url": args.base_url, "checks": {}}

    def receive(raw):
        if not isinstance(raw, str):
            return
        try:
            packet = json.loads(raw)
        except ValueError:
            return
        kind = packet.get("type")
        if kind == "event":
            events.append(packet)
        elif kind == "status":
            statuses.append(packet)
        elif kind == "chunk":
            chunks.append(packet)
        elif kind in ("error", "input_error", "transcript"):
            events.append(packet)

    async def wait_event(predicate, start=0, timeout=70):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for packet in events[start:]:
                if predicate(packet):
                    return packet
            failures = [p for p in events[start:] if p.get("type") in ("error", "input_error")]
            if failures:
                raise AssertionError(f"Input/session failed: {failures[-1]}")
            await asyncio.sleep(.25)
        raise AssertionError(f"Timed out waiting for event; recent events: {events[-4:]}")

    def decision(packet, kind):
        return packet.get("event") == "utterance_end" and packet.get("data", {}).get("applied") is True \
            and (packet.get("data", {}).get("decision") or {}).get("kind") == kind

    def lesson(packet, stage):
        return packet.get("event") == "lesson" and packet.get("data", {}).get("stage") == stage

    async with async_playwright() as pw:
        options = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
        if args.microphone:
            options.append("--use-file-for-fake-audio-capture=" + str(Path(args.microphone).resolve()))
        browser = await pw.chromium.launch(headless=True, args=options)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 1100}, permissions=["microphone"])
        page = await ctx.new_page()
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        page.on("websocket", lambda socket: socket.on("framereceived", receive))
        base = args.base_url.rstrip("/")
        try:
            # The named test profile is mandatory, so no real learner is modified.
            response = await ctx.request.get(base + "/api/students/verification")
            assert response.ok, "Backend must allow an isolated verification profile"
            before = await response.json()
            if not before.get("grade"):
                response = await ctx.request.put(base + "/api/students/verification", data={
                    "version": before["version"], "name": "功能验证", "grade": "小学五年级"})
                assert response.ok
                before = await response.json()
            await page.goto(base + "/?edition=secondary&student=verification", wait_until="networkidle")
            await page.wait_for_function('!document.querySelector("#connect").disabled')
            await page.locator("#connect").click()
            await page.wait_for_function('sessionState === "ready"', timeout=30000)
            status = statuses[-1]
            assert status["generator"] == "puppet" and status["responder"] != "rules"
            assert status["asr"] and status["board"] and status["judge"] == "vlm"
            assert await page.locator("#runtimeNotice").is_hidden()
            assert await page.locator("#talk").is_enabled()
            report["checks"]["real_session"] = {k: status[k] for k in ("generator", "responder", "asr", "board", "judge")}
            session = status["session"]

            start = len(events)
            await page.locator("#text").fill("同分母分数相加，为什么分母不变？请举一个例子。")
            await page.locator("#text").press("Enter")
            answer = await wait_event(lambda p: decision(p, "content"), start)
            await wait_event(lambda p: p.get("event") == "speech_onset" and p.get("data", {}).get("audibility") == "heard", start)
            await page.wait_for_function('document.querySelector("#boardTitle").textContent !== "学习黑板"', timeout=20000)
            await page.locator("#classroom").screenshot(path=str(out / "answer.png"))
            report["checks"]["question"] = answer["data"]["decision"]

            if args.microphone:
                start = len(events)
                await page.locator("#talk").focus()
                await page.keyboard.down("Space")
                await page.wait_for_function('document.querySelector("#talk").classList.contains("recording")')
                await page.wait_for_timeout(4500)
                await page.keyboard.up("Space")
                transcript = await wait_event(lambda p: p.get("type") == "transcript" and "分数" in p.get("text", ""), start, timeout=45)
                await wait_event(lambda p: decision(p, "content"), start, timeout=45)
                report["checks"]["microphone"] = {"transcript": transcript["text"], "recording": "Chromium fake microphone with real MediaRecorder and hosted ASR"}

            start = len(events)
            await page.locator("#lessonTopic").fill("同分母分数相加")
            await page.locator("#startLesson").click()
            outline = await wait_event(lambda p: lesson(p, "outline"), start)
            section = await wait_event(lambda p: lesson(p, "section"), start)
            await page.wait_for_timeout(1500)
            await page.locator("#classroom").screenshot(path=str(out / "lesson.png"))
            report["checks"]["lesson"] = {"outline": outline["data"], "section": section["data"]}

            start = len(events)
            await page.locator("#text").fill("先不上课了，请停止课程。")
            await page.locator("#text").press("Enter")
            await wait_event(lambda p: decision(p, "lesson_stop"), start)
            report["checks"]["interrupt"] = True
            await page.locator("#lessonTopic").fill(
                "整数加法。只出一道简答计算题，题干必须是两个正整数相加的算式 a + b = ?；"
                "不要应用题、小数、分数和单位。")
            start = len(events)
            await page.wait_for_function('!document.querySelector("#practice").disabled', timeout=10000)
            await page.locator("#practice").click()
            exercise = await wait_event(lambda p: lesson(p, "exercise_open"), start)
            assert await page.locator("#exerciseCard").is_visible()
            await page.locator("#classroom").screenshot(path=str(out / "exercise.png"))
            question = exercise["data"]["question"]
            expression = re.search(r"\d+\s*(?:[+＋]\s*\d+\s*)+", question)
            operands = re.findall(r"\d+", expression.group()) if expression else []
            assert operands and not re.search(r"\d+\.\d+", question) \
                and operands == re.findall(r"\d+", question), \
                f"Expected a simple addition question, received: {question}"
            expected_answer = str(sum(map(int, operands)))
            start = len(events)
            await page.locator("#text").fill(expected_answer)
            await page.locator("#text").press("Enter")
            graded = await wait_event(lambda p: lesson(p, "exercise_graded"), start)
            assert graded["data"].get("correct") is True, graded
            await page.wait_for_timeout(1000)
            await page.locator("#exerciseCard").screenshot(path=str(out / "graded.png"))
            response = await ctx.request.get(base + "/api/students/verification")
            after = await response.json()
            assert after["version"] > before["version"]
            # API history is newest first; on-disk profile history is newest last.
            assert after.get("history") and after["history"][0]["correct"] is True
            assert after["history"][0]["answer"] == expected_answer
            report["checks"]["exercise"] = {"question": exercise["data"], "independently_computed_answer": expected_answer, "grading": graded["data"]}
            report["checks"]["profile"] = {"version_before": before["version"], "version_after": after["version"], "history_count": len(after["history"])}

            await page.locator("#disconnect").click()
            await page.wait_for_function('sessionState === "disconnected"')
            # A new session must load the saved profile; do not rely on page memory.
            await page.locator("#connect").click()
            await page.wait_for_function('sessionState === "ready"', timeout=30000)
            assert statuses[-1]["student"]["version"] == after["version"]
            report["checks"]["reconnect"] = True
            await page.wait_for_timeout(2000)
            await page.locator("#disconnect").click()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                response = await ctx.request.get(base + "/api/traces?student=verification")
                traces = await response.json()
                trace = next((t for t in traces.get("sessions", []) if t["id"] == session), None)
                videos = [v for v in (trace or {}).get("videos", []) if v["label"].startswith("presented")]
                if videos:
                    break
                await asyncio.sleep(.5)
            assert videos, "No presented recording finalized"
            media = await ctx.request.get(base + videos[0]["url"], headers={"Range": "bytes=0-4095"})
            assert media.status in (200, 206)
            body = await media.body()
            assert b"ftyp" in body[:64], "Presented recording is not MP4"
            response = await ctx.request.get(base + trace["transcript_url"])
            assert response.ok
            transcript = await response.json()
            assert transcript.get("entries"), transcript
            report["checks"]["recording"] = {"session": session, "video": videos[0], "transcript_entries": len(transcript["entries"])}
            assert not browser_errors, browser_errors
            fatal = [p for p in events if p.get("type") in ("error", "input_error")]
            assert not fatal, fatal
            report["video_chunks"] = len(chunks)
            report["browser_errors"] = browser_errors
            report["server_diagnostics"] = [p for p in events if p.get("event") == "error"]
            report["stages"] = dict(Counter(p.get("data", {}).get("stage") for p in events if p.get("event") == "lesson"))
            report["ok"] = True
        except Exception as error:
            report["ok"] = False
            report["failure"] = str(error)
            report["recent_events"] = events[-8:]
            await page.screenshot(path=str(out / "failure.png"), full_page=True)
            raise
        finally:
            (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            await browser.close()
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8230")
    parser.add_argument("--output", default=str(ROOT / ".cache/full-puppet/browser"))
    parser.add_argument("--microphone", help="WAV file for Chromium fake microphone (real ASR still runs)")
    asyncio.run(check(parser.parse_args()))


if __name__ == "__main__":
    main()
