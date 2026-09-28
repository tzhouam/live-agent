"""Student attention from the page's camera (opt-in): is the student following the lesson right now?

The page sends a downscaled camera frame every few seconds only while the student has switched the camera on.
A VLM classifies it (focused / distracted / absent); frames are analysed in memory and never stored, logged or
recorded; the log keeps the state, a confidence and a one-line reason that must not describe the person.
The state is smoothed over the last few frames (one odd frame is not a change of state).
"""

from __future__ import annotations

import asyncio
import base64
from collections import deque
from typing import Any

from live_agent.llm import ChatLLM, parse_json

STATES = ("focused", "distracted", "absent")
ATTENTION_PROMPT = """这是在线课堂上学生摄像头的一帧画面。判断学生此刻是否在专注听课：
focused：看着屏幕，或低头记笔记、看课本；
distracted：明显看向别处、玩手机、和别人说话、趴着或闭眼；
absent：画面里没有人。
只根据画面判断，只输出 JSON：{"state": "focused" 或 "distracted" 或 "absent", "confidence": 0 到 1 的小数, "reason": 一句话说明依据（只说动作和视线，不描述长相、衣着和环境）}"""

NUDGES = {
    "distracted": ["同学，看这里，这一步很关键。", "我们一起看黑板上的这一条。", "注意听哦，马上就要用到。"],
    "absent": ["同学还在吗？我们先继续。"],
}


class AttentionMonitor:
    def __init__(self, vlm: ChatLLM, window: int = 3, min_confidence: float = 0.5):
        self.vlm = vlm
        self.min_confidence = min_confidence
        self.recent: deque[str] = deque(maxlen=window)
        self.busy = False  # one frame at a time: frames arriving meanwhile are dropped
        self.stable: str | None = None
        self.run = 0  # consecutive checks with the same stable state

    async def classify(self, jpeg: bytes) -> dict[str, Any]:
        url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        raw = await self.vlm.chat([{"role": "user", "content": [
            {"type": "text", "text": ATTENTION_PROMPT}, {"type": "image_url", "image_url": {"url": url}}]}],
            max_tokens=120, temperature=0.0, json_mode=True)
        d = parse_json(raw)
        state = str(d.get("state", "")).lower()
        return {"state": state if state in STATES else "unknown",
                "confidence": float(d.get("confidence") or 0.0), "reason": str(d.get("reason") or "")[:60]}

    def update(self, result: dict[str, Any]) -> str | None:
        """Add one classification; the stable state is the majority of the recent confident ones."""
        if result.get("state") in STATES and result.get("confidence", 0.0) >= self.min_confidence:
            self.recent.append(result["state"])
        if not self.recent:
            return self.stable
        top = max(STATES, key=lambda s: list(self.recent).count(s))
        if list(self.recent).count(top) * 2 > len(self.recent):
            self.run = self.run + 1 if top == self.stable else 1
            self.stable = top
        return self.stable

    def reset(self) -> None:
        self.recent.clear()
        self.stable, self.run = None, 0


async def check_frame(monitor: AttentionMonitor, jpeg: bytes, timeout_s: float = 8.0) -> dict[str, Any] | None:
    """Classify one frame unless one is already being classified (then drop it)."""
    if monitor.busy:
        return None
    monitor.busy = True
    try:
        result = await asyncio.wait_for(monitor.classify(jpeg), timeout=timeout_s)
    finally:
        monitor.busy = False
    result["stable"] = monitor.update(result)
    result["run"] = monitor.run
    return result


__all__ = ["ATTENTION_PROMPT", "AttentionMonitor", "NUDGES", "check_frame"]
