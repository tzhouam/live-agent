"""Online QC (proposal §8.2 layer 5): deadline-bounded checks on *presented* content.

- ``VLMJudge``: asks a VLM a yes/no question about K frames sampled from the presented
  chunks of a request; may abstain (UNKNOWN).
- ``SpeechCheck``: ASR of the generated audio vs the scripted line (character error rate).
- ``ForwardCorrector``: VQQA-style "semantic gradient": turns failed Q/A into a correction
  sentence for the earliest correctable request (never regenerates presented content).
- ``MockJudge``: for tests/simulation; decides compliance from the prompt with a
  per-capability success probability.
"""

from __future__ import annotations

import asyncio

import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from live_agent.llm import ChatLLM, frame_to_data_url, parse_json
from live_agent.types import CheckQuestion, Chunk, Verdict, VerdictLabel, now

JUDGE_PROMPT = """你是严格的视频质检员。下面是直播画面中按时间顺序抽取的 {k} 帧。
问题：{question}
只根据画面回答，只输出 JSON：{{"answer": "yes" | "no" | "unsure", "confidence": 0到1之间的小数, "reason": "一句话"}}"""

# Contrast mode (after E1 pilot): a state question ("is she seated?") is satisfied without any
# action, and 4 sparse frames miss late or brief actions. The judge sees the clip's first frame as
# the "before" state plus dense frames through the last one, and must decide whether the action
# *happened in this clip*.
JUDGE_PROMPT_CONTRAST = """你是严格的视频质检员。下面是一段约 5 秒直播视频中按时间顺序抽取的 {k} 帧：第 1 帧是这段开始时的画面，最后一帧是结尾。
要检查的动作：{question}
判断标准：只有当这个动作**在这段视频里实际发生了**（能看到动作过程或前后状态的变化）才回答 yes。
如果人物从头到尾只是保持原来的状态（例如一直坐着、一直在看书），即使最终状态符合描述，也回答 no。动作只要在任何一帧出现就算发生，哪怕在最后一帧。
只输出 JSON：{{"answer": "yes" | "no" | "unsure", "confidence": 0到1之间的小数, "reason": "一句话"}}"""


def sample_frames(chunks: Sequence[Chunk], k: int = 4) -> list[np.ndarray]:
    frames = [f for c in chunks if c.video is not None for f in c.video]
    if not frames:
        return []
    idx = np.linspace(0, len(frames) - 1, num=min(k, len(frames))).round().astype(int)
    return [frames[i] for i in idx]


@dataclass
class VLMJudge:
    vlm: ChatLLM
    k: int = 4
    min_confidence: float = 0.6
    contrast: bool = False  # True: dense frames incl. start/end + "did it happen in this clip" prompt

    async def judge(self, q: CheckQuestion, chunks: Sequence[Chunk], request_index: int,
                    t_evidence: float) -> Verdict:
        frames = sample_frames(chunks, self.k)
        if not frames:
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, "no frames", t_evidence, now())
        prompt = JUDGE_PROMPT_CONTRAST if self.contrast else JUDGE_PROMPT
        content = [{"type": "text", "text": prompt.format(k=len(frames), question=q.text)}]
        urls = await asyncio.to_thread(lambda: [frame_to_data_url(f) for f in frames])  # JPEG+base64 off the loop
        content += [{"type": "image_url", "image_url": {"url": u}} for u in urls]
        try:
            d = parse_json(await self.vlm.chat([{"role": "user", "content": content}], max_tokens=128,
                                               temperature=0.0, json_mode=True))
            ans, conf = str(d.get("answer", "unsure")).lower(), float(d.get("confidence", 0.0))
            reason = str(d.get("reason", ""))
        except Exception as e:  # abstain on any judge failure
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, f"judge error: {e}", t_evidence, now())
        if conf < self.min_confidence or ans not in ("yes", "no"):
            label = VerdictLabel.UNKNOWN
        else:
            label = VerdictLabel.COMPLIED if ans == "yes" else VerdictLabel.NOT_COMPLIED
        return Verdict(q.qid, request_index, label, conf, reason, t_evidence, now())


def char_error_rate(ref: str, hyp: str) -> float:
    """Levenshtein distance / len(ref) on characters, ignoring punctuation and spaces."""
    norm = lambda s: re.sub(r"[\s\W_]+", "", s.lower())  # noqa: E731
    r, h = norm(ref), norm(hyp)
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hc in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return prev[-1] / len(r)


@dataclass
class SpeechCheck:
    """Compare ASR of generated speech with the scripted line (used within sigma before playback)."""

    asr: Callable[[np.ndarray, int], str]  # (audio [S,C] float32, sample_rate) -> text
    max_cer: float = 0.10

    def check(self, q: CheckQuestion, script_line: str, chunks: Sequence[Chunk], request_index: int,
              t_evidence: float) -> Verdict:
        audio = [c.audio for c in chunks if c.audio is not None and len(c.audio)]
        if not audio:
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, "no audio", t_evidence, now())
        sr = chunks[0].sample_rate
        try:
            text = self.asr(np.concatenate(audio, axis=0), sr)
        except Exception as e:  # abstain: a failed check is not evidence either way
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, f"asr error: {e}", t_evidence, now())
        cer = char_error_rate(script_line, text)
        label = VerdictLabel.COMPLIED if cer <= self.max_cer else VerdictLabel.NOT_COMPLIED
        return Verdict(q.qid, request_index, label, 1.0 - min(cer, 1.0), f"asr={text!r} cer={cer:.2f}",
                       t_evidence, now())


CORRECTION_PROMPT = """视频生成模型没有执行下面的动作。请把动作描述改写成更明确、更容易被画出来的英文短句（一句，不超过 30 个词），
只描述人物 S1 的可见动作，不要改变人物外貌、场景或镜头。
原动作：{action}
失败的检查问答：{qa}
只输出 JSON：{{"correction": "..."}}"""


@dataclass
class ForwardCorrector:
    llm: ChatLLM | None = None

    async def correction(self, action_phrase: str, failed: Sequence[Verdict], questions: dict[str, str]) -> str:
        qa = "; ".join(f"Q: {questions.get(v.qid, v.qid)} A: {v.label.value} ({v.rationale})" for v in failed)
        if self.llm is not None:
            try:
                d = parse_json(await self.llm.chat(
                    [{"role": "user", "content": CORRECTION_PROMPT.format(action=action_phrase, qa=qa)}],
                    max_tokens=96, temperature=0.2, json_mode=True))
                text = str(d.get("correction", "")).strip()
                if text and _valid_correction(text, action_phrase):
                    return fit_correction(text)
            except Exception:
                pass
        # Template fallback: emphasise visibility and timing (fits the compiler's 200-char correction limit).
        return fit_correction(f"This time S1 clearly and visibly does it: {action_phrase}, facing the lens, "
                              f"within the first two seconds")


# A correction may only restate the permitted action more visibly. It must not touch the
# immutable canon (appearance, wardrobe, scene, camera, light) or introduce a new action.
_CANON_WORDS = re.compile(r"\b(hair|hairstyle|face|skin|eyes|dress|robe colou?r|hanfu|outfit|clothes|wardrobe|background|"
                          r"room|scene|window view|camera|lens angle|zoom|lighting|light|shot)\b", re.I)


CORRECTION_MAX = 200  # = h3_compiler's correction limit


def fit_correction(text: str, limit: int = CORRECTION_MAX) -> str:
    """Trim a correction at a word boundary so it always compiles (a longer one crashed the repair)."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;: ")
    return cut + "."


def _valid_correction(text: str, action_phrase: str) -> bool:
    if len(text) > 240 or _CANON_WORDS.search(text):
        return False
    # it must share content words with the permitted action (no substitute action)
    words = {w for w in re.findall(r"[a-z]{4,}", action_phrase.lower())}
    return not words or bool(words & set(re.findall(r"[a-z]{4,}", text.lower())))


class MockJudge:
    """Simulated judge: an action 'renders' with probability p (per phrase), boosted by corrections."""

    def __init__(self, p_default: float = 0.7, p_by_phrase: dict[str, float] | None = None,
                 correction_boost: float = 0.2, seed: int = 0):
        self.p_default = p_default
        self.p_by_phrase = p_by_phrase or {}
        self.boost = correction_boost
        self._rng = random.Random(seed)

    async def judge(self, q: CheckQuestion, chunks: Sequence[Chunk], request_index: int,
                    t_evidence: float) -> Verdict:
        prompt = chunks[0].meta.get("prompt", "") if chunks else ""
        p = self.p_default
        for phrase, pp in self.p_by_phrase.items():
            if phrase in prompt:
                p = pp
        if "clearly and visibly" in prompt:
            p = min(1.0, p + self.boost)
        ok = self._rng.random() < p
        return Verdict(q.qid, request_index, VerdictLabel.COMPLIED if ok else VerdictLabel.NOT_COMPLIED,
                       0.9, "mock", t_evidence, now())
