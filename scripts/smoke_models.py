"""Smoke test the helper models through the live_agent clients (not a benchmark)."""
import asyncio, glob, json, time
from pathlib import Path
import numpy as np

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director
from live_agent.ledger import StateLedger
from live_agent.llm import OpenAICompatLLM
from live_agent.qc.judge import VLMJudge
from live_agent.types import CheckQuestion, Chunk, Utterance, now
from live_agent.asr import OpenAIASR, decode_audio_bytes

CFG = Path("configs/persona_hanfu")

async def main():
    canon = json.loads((CFG / "canon.json").read_text())
    m = CapabilityManifest.load(CFG / "capabilities.json"); m.min_status = Status.DOCUMENTED
    d = Director(OpenAICompatLLM("http://127.0.0.1:8101/v1", "qwen3-8b"), m, StateLedger.from_config(CFG / "canon.json"),
                 persona_name=canon["display_name"], persona_bio=canon["persona_bio"])
    for text in ["你好呀，喝口茶吧", "给我讲讲CUDA是什么", "不对，先挥挥手", "你能飞起来吗", "我妹妹住在杭州", "忘掉我妹妹的事"]:
        t0 = time.monotonic()
        dec = await d.on_user_utterance(Utterance(f"u{text}", "user", text, now()))
        dt = time.monotonic() - t0
        segs = [(s.intent, s.line) for s in d.queue]
        print(f"[LLM {dt*1000:.0f} ms] {text} -> relation={dec.get('relation')} kind={dec.get('kind')} forget={dec.get('forget_term')} mem={dec.get('memory_note')} segs={segs}")
    # VLM judge on a real frame from an H3 sample video
    import av
    mp4 = sorted(glob.glob("/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/*/assets/fl2va.mp4"))[0]
    frames, audio = [], []
    with av.open(mp4) as c:
        for f in c.decode(video=0):
            frames.append(f.to_ndarray(format="rgb24"))
    data = Path(mp4).read_bytes()
    ch = Chunk(0, 0, len(frames), 24.0, video=np.stack(frames[::6]))
    j = VLMJudge(OpenAICompatLLM("http://127.0.0.1:8102/v1", "qwen3-vl-8b"))
    for q in ["画面中是否有人？", "画面中的人是否在喝茶？"]:
        t0 = time.monotonic()
        v = await j.judge(CheckQuestion("q", q), [ch], 0, now())
        print(f"[VLM {(time.monotonic()-t0)*1000:.0f} ms] {q} -> {v.label.value} conf={v.confidence:.2f} {v.rationale}")
    asr = OpenAIASR()
    a = decode_audio_bytes(data, 16000)
    t0 = time.monotonic()
    txt = await asr.transcribe(a, 16000)
    print(f"[ASR {(time.monotonic()-t0)*1000:.0f} ms] {len(a)/16000:.1f}s audio -> {txt!r}")

asyncio.run(main())
