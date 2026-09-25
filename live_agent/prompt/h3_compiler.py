"""Compile a BlockScript into the one-string-per-request prompt TaoMate-H3 accepts.

Format follows the official examples (external/TaoMate-H3/examples/prompts_60s.json):

    integrated_multimodal_description: [Shot 1] <style>, one uninterrupted five-second shot.
    The same <subject> ... <scene> remain unchanged. <camera> remain constant. <voice>.
    <action>, then says once: <d>[Chinese] <line></d> Her lips close. <negative>

    overall_soundscape: <soundscape>

    non_diegetic_music: N/A

The canon fields are copied verbatim (never paraphrased) so that every request restates
the persona identically -- this is the state-ledger convention of proposal §9.
"""

from __future__ import annotations

import re

from live_agent.types import BlockScript

STYLE = "Live-action portrait livestream"

# Characters that would break the <d>...</d> dialogue tag or the section headers.
_FORBIDDEN = re.compile(r"</?d>|integrated_multimodal_description:|overall_soundscape:|non_diegetic_music:", re.I)


class PromptError(ValueError):
    pass


def _clean(text: str, *, field: str, max_len: int = 400) -> str:
    text = " ".join(text.split())
    if _FORBIDDEN.search(text):
        raise PromptError(f"{field} contains a reserved prompt token")
    if len(text) > max_len:
        raise PromptError(f"{field} too long ({len(text)} > {max_len})")
    return text


def _sentence(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?。！？":
        text += "."
    return text


def compile_prompt(script: BlockScript, *, first_request: bool = False) -> str:
    """Return the TaoMate-H3 prompt string for one 5-second request."""
    c = script.canon
    subject = _clean(c.subject, field="subject")
    scene = _clean(c.scene, field="scene")
    camera = _clean(c.camera, field="camera")
    voice = _clean(c.voice, field="voice")
    action = _clean(script.action, field="action", max_len=300) if script.action else ""
    line = _clean(script.transcript, field="transcript", max_len=120) if script.transcript else ""

    same = "" if first_request else "The same "
    parts: list[str] = [f"[Shot 1] {STYLE}, one uninterrupted five-second shot."]
    if first_request:
        parts.append(_sentence(f"{subject[0].upper()}{subject[1:]} is in {scene}"))
    else:
        parts.append(_sentence(f"{same}{subject} stays in the same setting; {scene} remain unchanged"))
    parts.append(_sentence(f"{camera}, all remaining constant"))
    parts.append(_sentence(voice))
    for fix in script.corrections:
        parts.append(_sentence(_clean(fix, field="correction", max_len=200)))

    if action and line:
        parts.append(f"{_sentence(action)[:-1]}, then says once: <d>[{c.language}] {line}</d> Her lips close.")
    elif line:
        parts.append(f"S1 looks into the lens and says once: <d>[{c.language}] {line}</d> Her lips close.")
    elif action:
        parts.append(_sentence(action) + " She does not speak.")
    else:
        parts.append("S1 continues quietly with small natural movements and does not speak.")
    parts.append(_sentence(c.negative))

    description = " ".join(parts)
    soundscape = _sentence(_clean(script.soundscape, field="soundscape", max_len=200))
    if line:
        soundscape = f"Clear dry {c.speech_language} speech, {soundscape[0].lower()}{soundscape[1:]}"
    return (
        f"integrated_multimodal_description: {description}\n\n"
        f"overall_soundscape: {soundscape}\n\n"
        f"non_diegetic_music: N/A"
    )


def extract_dialogue(prompt: str) -> str:
    """Return the spoken line inside <d>[...] ...</d> (for ASR fidelity checks)."""
    m = re.search(r"<d>\[[^\]]*\]\s*(.*?)</d>", prompt, re.S)
    return m.group(1).strip() if m else ""
