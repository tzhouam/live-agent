"""Headless WebSocket client that behaves like frontend/public/index.html (for backend-path checks).

Plays chunks back to back on its own clock (time.monotonic, reported in ms as ``tp`` like the
browser's performance clock), sends chunk_start / chunk_end acks, answers pongs with clock
samples, and sends scripted text turns. Prints a JSON summary (chunks, gaps, RTT, events).

    python3 scripts/ws_client_check.py --url ws://127.0.0.1:8201/ws --seconds 45 \
        --say 5:请喝口茶吧 --say 25:跟我挥挥手吧
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import websockets


async def main(args) -> None:
    turns = sorted((float(x.split(":", 1)[0]), x.split(":", 1)[1]) for x in args.say)
    summary = {"chunks": 0, "max_gap_s": 0.0, "gaps_over_50ms": 0, "rtt_ms": [], "messages": {}}
    async with websockets.connect(args.url, max_size=None) as ws:
        hello = {"type": "hello", "mode": "private", "user_id": "check"}
        if args.h264:
            hello["video_codecs"] = ["h264"]  # like a WebCodecs page: one H.264 segment per chunk
        await ws.send(json.dumps(hello))
        t0 = time.monotonic()
        playhead = None
        pending = None
        plays: asyncio.Queue = asyncio.Queue()

        async def player():
            nonlocal playhead
            while True:
                meta = await plays.get()
                dur = meta.get("duration") or meta["n_frames"] / meta["fps"]
                start = max(time.monotonic(), playhead or 0.0)
                if playhead is not None and start - playhead > 0.05:
                    summary["gaps_over_50ms"] += 1
                if playhead is not None:
                    summary["max_gap_s"] = max(summary["max_gap_s"], start - playhead)
                await asyncio.sleep(max(0.0, start - time.monotonic()))
                await ws.send(json.dumps({"type": "chunk_start", "request": meta["request"], "chunk": meta["chunk"],
                                          "tp": start * 1000}))
                await asyncio.sleep(dur)
                playhead = start + dur
                await ws.send(json.dumps({"type": "chunk_end", "request": meta["request"], "chunk": meta["chunk"],
                                          "tp": playhead * 1000, "painted": list(range(meta["n_frames"]))}))
                summary["chunks"] += 1

        async def talker():
            for at, text in turns:
                await asyncio.sleep(max(0.0, t0 + at - time.monotonic()))
                await ws.send(json.dumps({"type": "speech_start"}))
                await ws.send(json.dumps({"type": "text", "text": text, "tp": time.monotonic() * 1000}))

        async def pinger():
            while True:
                await ws.send(json.dumps({"type": "ping", "t": time.monotonic() * 1000}))
                await asyncio.sleep(2.0)

        tasks = [asyncio.create_task(player()), asyncio.create_task(talker()), asyncio.create_task(pinger())]
        try:
            while time.monotonic() - t0 < args.seconds:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed as e:
                    summary["closed_by_server"] = f"{e.rcvd.code if e.rcvd else '?'} {e.rcvd.reason if e.rcvd else ''}"
                    break
                if isinstance(msg, bytes):
                    if pending is None:
                        continue
                    pending["got"] += 1
                    video_msgs = 1 if pending.get("codec") == "h264" else pending["n_frames"]
                    if pending.get("codec") == "h264" and pending["got"] == 1:
                        summary["h264_bytes"] = summary.get("h264_bytes", 0) + len(msg)
                    if pending["got"] == video_msgs + 1:  # video (n JPEGs or one H.264 segment) + pcm
                        await ws.send(json.dumps({"type": "chunk_received", "request": pending["request"],
                                                  "chunk": pending["chunk"], "tp": time.monotonic() * 1000}))
                        plays.put_nowait(pending)
                        pending = None
                    continue
                m = json.loads(msg)
                summary["messages"][m["type"]] = summary["messages"].get(m["type"], 0) + 1
                if m["type"] == "error":
                    summary["server_error"] = m.get("error")
                if m["type"] == "chunk":
                    pending = {**m, "got": 0}
                elif m["type"] == "stop":
                    pending = None
                    while not plays.empty():
                        plays.get_nowait()
                    playhead = None
                elif m["type"] == "pong":
                    rtt = time.monotonic() * 1000 - m["t"]
                    summary["rtt_ms"].append(round(rtt, 2))
                    await ws.send(json.dumps({"type": "clock", "t_client": m["t"], "t_server": m["ts"], "rtt": rtt}))
                elif m["type"] == "status":
                    summary["session"] = m.get("session")
        finally:
            for t in tasks:
                t.cancel()
    summary["rtt_ms"] = summary["rtt_ms"][:5]
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="ws://127.0.0.1:8201/ws")
    p.add_argument("--seconds", type=float, default=45)
    p.add_argument("--say", action="append", default=[])
    p.add_argument("--h264", action="store_true", help="announce H.264 support (as a WebCodecs browser does)")
    asyncio.run(main(p.parse_args()))
