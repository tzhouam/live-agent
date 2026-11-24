"""Board figures: optional remote images or CPU diagrams planned by the existing teacher model.

A figure is requested when a lesson section (or an answer's board) asks for one and is generated in the background.
Its ready event refreshes the matching current or queued board point; later locked requests also carry its URL.
Files live in ``out_dir`` and are served by the app under ``/board/img/<name>.png``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import time
from pathlib import Path

STYLE = ("clean educational textbook illustration for a middle-school lesson, white background, simple flat colors, "
         "clear thin outlines, large legible Simplified Chinese labels where needed, no photo realism, no watermark: ")


class ImageMaker:
    def __init__(self, url: str, out_dir: str | Path, *, model: str = "qwen-image", size: str = "1024x768",
                 steps: int = 4, timeout_s: float = 90.0):
        self.url = url.rstrip("/")
        self.out_dir = Path(out_dir)
        self.model, self.size, self.steps, self.timeout_s = model, size, steps, timeout_s
        self._lock = asyncio.Lock()  # one image at a time: the model shares its card with the judge and ASR
        self.timings: list[float] = []

    @staticmethod
    def name_for(prompt: str, seed: int = 42) -> str:
        return hashlib.sha1(f"{seed}:{prompt}".encode("utf-8")).hexdigest()[:16] + ".png"

    async def make(self, prompt: str, seed: int = 42) -> str:
        """Generate (or reuse) the figure for ``prompt``; returns its page URL. Raises on failure."""
        import httpx

        name = self.name_for(prompt, seed)
        path = self.out_dir / name
        if path.exists():
            return f"/board/img/{name}"
        async with self._lock:
            t0 = time.monotonic()
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post(self.url + "/v1/images/generations", json={
                    "model": self.model, "prompt": STYLE + prompt, "size": self.size, "n": 1,
                    "num_inference_steps": self.steps, "guidance_scale": 1.0, "seed": seed,
                    "response_format": "b64_json"})
            if r.status_code != 200:
                raise RuntimeError(f"image server {r.status_code}: {r.text[:200]}")
            data = r.json()["data"][0]["b64_json"]
            self.out_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(base64.b64decode(data))
            tmp.replace(path)
            self.timings.append(time.monotonic() - t0)
        return f"/board/img/{name}"


class LocalDiagramMaker:
    """Teacher-planned labelled schematics, drawn locally without an image server or GPU."""

    exact_labels = True  # validated source labels are painted verbatim; no image-model OCR is needed
    kind = "diagram"

    def __init__(self, llm, out_dir: str | Path, *, timeout_s: float = 30.0, max_attempts: int = 3):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise ValueError("diagram planning attempts must be between 1 and 3")
        self.llm, self.out_dir, self.timeout_s = llm, Path(out_dir), timeout_s
        self.max_attempts = max_attempts
        self._lock = asyncio.Lock()
        self.timings: list[float] = []

    @staticmethod
    def name_for(prompt: str, seed: int = 42) -> str:
        return "d" + hashlib.sha256(f"diagram-v1:{seed}:{prompt}".encode()).hexdigest()[:15] + ".png"

    async def make(self, prompt: str, seed: int = 42) -> str:
        from live_agent.board_diagram import DIAGRAM_PROMPT, compile_diagram, render_diagram
        from live_agent.llm import parse_json

        name = self.name_for(prompt, seed)
        async with self._lock:
            if (self.out_dir / name).exists():
                return f"/board/img/{name}"
            t0 = time.monotonic()
            messages = [{"role": "user", "content": DIAGRAM_PROMPT.format(prompt=prompt)}]
            # One overall budget covers planning, repair and rendering. Invalid
            # data never publishes a file; the model can correct its own spec.
            async with asyncio.timeout(self.timeout_s):
                for attempt in range(self.max_attempts):
                    raw = await self.llm.chat(messages, max_tokens=1800, temperature=0.1, json_mode=True)
                    try:
                        spec = compile_diagram(parse_json(raw))
                        labels = [spec["title"], *[n["text"] for n in spec["nodes"]], *[a["label"] for a in spec["arrows"]]]
                        # A central concept copied from the request is legitimate
                        # diagram text. Only check its explicitly requested labels.
                        missing = missing_labels(expected_labels(prompt), labels)
                        if missing:
                            raise ValueError(f"diagram did not preserve requested labels: {missing}")
                        await asyncio.to_thread(render_diagram, spec, self.out_dir, name=name)
                        break
                    except (ValueError, TypeError, KeyError) as error:
                        if attempt + 1 == self.max_attempts:
                            raise ValueError(f"diagram invalid after {self.max_attempts} planning attempts: {error}") from error
                        messages = [*messages, {"role": "assistant", "content": str(raw)[:12000]},
                                         {"role": "user", "content":
                                          f"上次的 JSON 数据不能安全绘图：{str(error)[:240]}。请修正后重新输出完整 JSON。"
                                          "节点位置不能重复，箭头不能自环且必须连接已存在节点，保留要求中的标注。"
                                          "若标注放不下，请减少节点或箭头、缩短箭头文字并重新安排位置；不要改动知识含义。"}]
            self.timings.append(time.monotonic() - t0)
        return f"/board/img/{name}"


def expected_labels(prompt: str) -> list[str]:
    """Labels a figure prompt asks for (the planner quotes them: 标注「阳光」)."""
    import re

    return [x.strip() for x in re.findall(r"[「“\"]([^」”\"]{1,12})[」”\"]", prompt) if x.strip()]


LABEL_PROMPT = """这是一张教学示意图。请逐字列出图中所有可见的文字标注（中文、字母、数字都要），不要纠正错别字，照图上写的抄。
只输出 JSON：{"labels": ["...", "..."]}"""


async def read_labels(vlm, image_path: Path) -> list[str]:
    """The labels a VLM reads in the image, verbatim (typos included)."""
    import numpy as np
    from PIL import Image

    from live_agent.llm import frame_to_data_url, parse_json

    frame = np.asarray(Image.open(image_path).convert("RGB"))
    url = await asyncio.to_thread(frame_to_data_url, frame)
    raw = await vlm.chat([{"role": "user", "content": [{"type": "text", "text": LABEL_PROMPT},
                                                        {"type": "image_url", "image_url": {"url": url}}]}],
                         max_tokens=256, temperature=0.0, json_mode=True)
    return [str(x) for x in parse_json(raw).get("labels", [])]


_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹", "01234567890123456789")


def _norm(s: str) -> str:
    return s.translate(_SUB).replace(" ", "").strip("「」“”\"'")


def missing_labels(expected: list[str], seen: list[str], prompt: str = "") -> list[str]:
    """Requested labels that are absent, plus seen labels one character off a requested one that are not
    themselves requested (a misspelt copy, e.g. 二氧化硼 next to 二氧化碳, is wrong even when the right spelling
    appears elsewhere; 细胞壁 next to 细胞膜 is fine when both were asked for)."""
    want = {_norm(x) for x in expected}
    got = {_norm(s) for s in seen}
    text = " ".join(got)
    out = [x for x in dict.fromkeys(_norm(x) for x in expected) if x not in text]
    for s in sorted(got - want):
        if any(len(s) == len(x) >= 2 and sum(a != b for a, b in zip(s, x)) == 1 for x in want):
            out.append(s)
        elif len(s) >= 4 and s in _norm(prompt):  # the prompt itself painted onto the picture
            out.append(s)
    return out


__all__ = ["ImageMaker", "LocalDiagramMaker", "STYLE", "expected_labels", "missing_labels", "read_labels"]
