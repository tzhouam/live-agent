"""Student attention from the page's camera (opt-in): is the student following the lesson right now?

The page sends a downscaled camera frame every few seconds only while the student has switched the camera on.
A VLM classifies it (focused / distracted / absent); frames are analysed in memory and never stored, logged or
recorded; the log keeps the state, a confidence and a one-line reason that must not describe the person.
The state is smoothed over the last few frames (one odd frame is not a change of state).
"""

from __future__ import annotations

import asyncio
import base64
import math
from collections import deque
from typing import Any

from live_agent.llm import ChatLLM, parse_json

STATES = ("focused", "distracted", "absent")
ATTENTION_PROMPT = """这是在线课堂上学生摄像头的一帧画面。判断此刻可见的课堂参与行为，不要猜测心理状态：
focused：面向屏幕或正在看课本、书写学习笔记；
distracted：有明确证据在使用无关物品、头部明显转向屏幕以外、与旁人互动，或明显趴睡；
absent：画面清楚且没有学生，不把局部脸部遮挡当作离开；
unknown：画面模糊、昏暗、遮挡，或分不清是在做笔记还是处理无关事情。
认真检查视线方向、头部朝向、手部和物品：出现明确走神证据时不要默认 focused。
一帧不能判断持续时长；正常眨眼、短暂低头、手托下巴或仅仅戴眼镜不构成走神证据。
只根据画面判断，只输出 JSON：{"state": "focused" 或 "distracted" 或 "absent" 或 "unknown", "confidence": 0 到 1 的小数, "reason": 简短依据（只说动作和视线，不描述长相、衣着和环境）}"""

NUDGES = {
    "distracted": ["同学，看这里，这一步很关键。", "我们一起看黑板上的这一条。", "注意听哦，马上就要用到。"],
    "absent": ["同学还在吗？我们先继续。"],
}


class AttentionMonitor:
    def __init__(self, vlm: ChatLLM, window: int = 2, min_confidence: float = 0.5):
        if type(window) is not int or window < 2:
            raise ValueError("attention window must contain at least two observations")
        if not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1:
            raise ValueError("attention confidence must be between zero and one")
        self.vlm = vlm
        self.min_confidence = min_confidence
        self.recent: deque[str] = deque(maxlen=window)
        self.busy = False  # one frame at a time: frames arriving meanwhile are dropped
        self.stable: str | None = None
        self.run = 0  # consecutive checks with the same stable state
        self._observed: str | None = None
        self._observed_run = 0
        self.epoch = 0  # resets invalidate in-flight classifications

    async def classify(self, jpeg: bytes) -> dict[str, Any]:
        url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        raw = await self.vlm.chat([{"role": "user", "content": [
            {"type": "text", "text": ATTENTION_PROMPT}, {"type": "image_url", "image_url": {"url": url}}]}],
            max_tokens=120, temperature=0.0, json_mode=True)
        d = parse_json(raw)
        state = str(d.get("state", "")).lower()
        try:
            confidence = float(d.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            confidence = 0.0
        return {"state": state if state in STATES else "unknown",
                "confidence": confidence, "reason": str(d.get("reason") or "")[:60]}

    def update(self, result: dict[str, Any]) -> str | None:
        """Confirm changes promptly; uncertainty never reinforces an old verdict."""
        state = result.get("state")
        confidence = result.get("confidence", 0.0)
        if state not in STATES or type(confidence) not in (int, float) \
                or not math.isfinite(confidence) or confidence < self.min_confidence or confidence > 1:
            self.recent.clear()
            self.stable, self.run, self._observed, self._observed_run = None, 0, None, 0
            return None
        self._observed_run = self._observed_run + 1 if state == self._observed else 1
        self._observed = state
        self.recent.append(state)
        top = max(STATES, key=lambda s: list(self.recent).count(s))
        # A first focused frame is usable; distraction/absence and later changes
        # require repeated evidence, so one blink or glance cannot trigger a reminder.
        if list(self.recent).count(top) * 2 > len(self.recent) \
                and (top == "focused" and self.stable is None or list(self.recent).count(top) >= 2):
            self.stable = top
        self.run = self._observed_run if state == self.stable else 0
        return self.stable

    def reset(self) -> None:
        self.epoch += 1
        self.recent.clear()
        self.stable, self.run, self._observed, self._observed_run = None, 0, None, 0


async def check_frame(monitor: AttentionMonitor, jpeg: bytes, timeout_s: float = 8.0) -> dict[str, Any] | None:
    """Classify one frame unless one is already being classified (then drop it)."""
    if monitor.busy:
        return None
    monitor.busy = True
    epoch = monitor.epoch
    try:
        result = await asyncio.wait_for(monitor.classify(jpeg), timeout=timeout_s)
    finally:
        monitor.busy = False
    if epoch != monitor.epoch:
        return None
    result["stable"] = monitor.update(result)
    result["run"] = monitor.run
    return result


__all__ = ["ATTENTION_PROMPT", "AttentionMonitor", "NUDGES", "check_frame"]
