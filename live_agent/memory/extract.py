"""Pluggable fact extraction, claim-type classification and viewer-chat sanitisation.

The write policy (proposal §5.6) first decides *what kind of sentence* an utterance is
(own assertion, quote of the persona, question, hypothetical/joke) and only then extracts
facts. Only ``own_assertion`` candidates may become user facts; the classification of
everything else is still recorded on the episode for audit.

:class:`RuleExtractor` is a small deterministic default for tests and offline use
(simple Chinese/English patterns). An LLM extractor can implement :class:`Extractor`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .schema import ClaimType


@dataclass
class CandidateFact:
    text: str  # the sentence the fact came from
    claim_type: ClaimType
    subject: str | None = None  # relative: "user" or "user/sister"; the store makes it absolute
    predicate: str | None = None
    value: str | None = None
    confidence: float = 0.8
    correction: bool = False  # explicit correction cue ("actually", "不对", "moved to" ...)


@runtime_checkable
class Extractor(Protocol):
    version: str

    def classify(self, text: str) -> ClaimType:
        """Utterance-level claim type (used to tag the episode)."""
        ...

    def extract(self, text: str) -> list[CandidateFact]:
        """Candidate facts, each tagged with the claim type of its sentence."""
        ...


# --------------------------------------------------------------------------- rules

_SENT = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]*")

_QUOTE = re.compile(
    r"(你(刚才|之前|上次|以前)?(说过|说|讲过|告诉过?我|提到过?)|听你说|you (told|said|mentioned)|"
    r"you'?ve (told|said)|as you said|according to you)",
    re.IGNORECASE,
)
_HYPO = re.compile(
    r"(如果|假如|假设|要是|万一|开玩笑|逗你|\bif\b|\bsuppose\b|\bimagine\b|\bpretend\b|"
    r"\bjust kidding\b|\bjk\b|\bwhat if\b|\bhypothetically\b)",
    re.IGNORECASE,
)
_QMARK = re.compile(r"[?？]\s*$|[吗嘛呢]\s*[。.]?\s*$")
_QWORD_EN = re.compile(
    r"^\s*(do|does|did|is|are|was|were|can|could|will|would|should|have|has|what|where|who|when|why|how)\b",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"(不对|其实|更正|纠正|说错了|搬到|搬去|现在|改成|\bactually\b|\bno longer\b|\banymore\b|"
    r"\bmoved to\b|\bcorrection\b|\bnot anymore\b|\bi meant\b|\bnow\b)",
    re.IGNORECASE,
)

_REL_ZH = {
    "妹妹": "sister", "姐姐": "sister", "哥哥": "brother", "弟弟": "brother",
    "妈妈": "mother", "母亲": "mother", "爸爸": "father", "父亲": "father",
    "老婆": "wife", "妻子": "wife", "老公": "husband", "丈夫": "husband",
    "儿子": "son", "女儿": "daughter", "男朋友": "boyfriend", "女朋友": "girlfriend", "朋友": "friend",
}
_REL_EN = {
    "sister": "sister", "brother": "brother", "mother": "mother", "mom": "mother", "mum": "mother",
    "father": "father", "dad": "father", "wife": "wife", "husband": "husband", "son": "son",
    "daughter": "daughter", "friend": "friend", "boyfriend": "boyfriend", "girlfriend": "girlfriend",
}
_OBJ_ZH = {"喝": "drink", "吃": "food", "看": "watch", "听": "music", "玩": "game"}

_ZH_REL = "|".join(sorted(_REL_ZH, key=len, reverse=True))
_EN_REL = "|".join(sorted(_REL_EN, key=len, reverse=True))
_ZV = r"(?P<val>[^，。！？；,.!?;\s的]{1,20})"
_EV = r"(?P<val>[^,.!?;]{1,40}?)(?=\s+(?:and|but|now|too|already)\b|[,.!?;]|$)"

# (pattern, predicate or None if derived from groups)
_ZH_RULES: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(rf"我(?:的)?(?P<rel>{_ZH_REL})?(?:现在|目前|其实|也|已经)?(?:住在|搬到了?|搬去了?)" + _ZV), "lives_in"),
    (re.compile(r"(?:我的名字是|我叫)" + _ZV), "name"),
    (re.compile(r"我最(?:喜欢|爱)(?P<obj>喝|吃|看|听|玩)?" + _ZV), "favorite"),
    (re.compile(r"我(?:不喜欢|讨厌|不爱)(?P<obj>喝|吃|看|听|玩)?" + _ZV), "dislikes"),
    (re.compile(r"我(?:很|也|非常|特别)?(?:喜欢|爱)(?P<obj>喝|吃|看|听|玩)?" + _ZV), "likes"),
    (re.compile(r"我在(?P<val>[^，。！？；,.!?;\s]{1,20}?)(?:工作|上班)"), "works_at"),
]
_EN_RULES: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(rf"\bmy (?P<rel>{_EN_REL}) (?:now |still |actually |also )?(?:lives|is living|has moved|moved) (?:in|to) " + _EV, re.IGNORECASE), "lives_in"),
    (re.compile(r"\bI (?:now |still |actually |also )?(?:live|am living|have moved|'ve moved|moved) (?:in|to) " + _EV, re.IGNORECASE), "lives_in"),
    (re.compile(r"\b(?:my name is|call me) " + _EV, re.IGNORECASE), "name"),
    (re.compile(r"\bmy favou?rite (?P<obj>\w+) is " + _EV, re.IGNORECASE), "favorite"),
    (re.compile(r"\bI (?:don't|do not|really don't) (?:like|love) " + _EV + r"|\bI hate " + _EV.replace("val", "val2"), re.IGNORECASE), "dislikes"),
    (re.compile(r"\bI (?:really |also )?(?:like|love|enjoy) " + _EV, re.IGNORECASE), "likes"),
    (re.compile(r"\bI work (?:at|for) " + _EV, re.IGNORECASE), "works_at"),
]
_TRAIL_ZH = re.compile(r"[了呢啊呀吧哦嘛吗]+$")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.findall(text) if s.strip()]


class RuleExtractor:
    """Deterministic pattern extractor (Chinese + English). Version is stored in provenance."""

    version = "rule-v1"

    def classify(self, text: str) -> ClaimType:
        # An utterance counts as an assertion if any sentence is one; otherwise it takes the
        # type of its first sentence. Facts are still classified per sentence in extract().
        types = [self._classify_sentence(s) for s in split_sentences(text)] or [ClaimType.OWN_ASSERTION]
        return ClaimType.OWN_ASSERTION if ClaimType.OWN_ASSERTION in types else types[0]

    def _classify_sentence(self, s: str) -> ClaimType:
        if _QUOTE.search(s):
            return ClaimType.QUESTION if _QMARK.search(s) else ClaimType.QUOTE_OF_PERSONA
        if _QMARK.search(s) or _QWORD_EN.search(s):
            return ClaimType.QUESTION
        if _HYPO.search(s):
            return ClaimType.HYPOTHETICAL
        return ClaimType.OWN_ASSERTION

    def extract(self, text: str) -> list[CandidateFact]:
        out: list[CandidateFact] = []
        for sent in split_sentences(text):
            ct = self._classify_sentence(sent)
            corr = bool(_CORRECTION.search(sent))
            taken: list[tuple[int, int]] = []
            for pat, pred in _ZH_RULES + _EN_RULES:
                for m in pat.finditer(sent):
                    if any(a < m.end() and m.start() < b for a, b in taken):
                        continue  # a more specific rule already consumed this span
                    fact = self._build(m, pred or "", sent, ct, corr)
                    if fact is not None:
                        taken.append((m.start(), m.end()))
                        out.append(fact)
        return out

    @staticmethod
    def _build(m: re.Match[str], pred: str, sent: str, ct: ClaimType, corr: bool) -> CandidateFact | None:
        gd = m.groupdict()
        val = (gd.get("val") or gd.get("val2") or "").strip()
        val = _TRAIL_ZH.sub("", val).strip(" '\"“”")
        if not val:
            return None
        rel = gd.get("rel")
        subject = "user"
        if rel:
            subject = "user/" + (_REL_ZH.get(rel) or _REL_EN.get(rel.lower(), rel.lower()))
        obj = gd.get("obj")
        if pred == "favorite":
            if obj:
                pred = "favorite_" + (_OBJ_ZH.get(obj) or obj.lower())
        return CandidateFact(
            text=sent, claim_type=ct, subject=subject, predicate=pred, value=val,
            confidence=0.8, correction=corr,
        )


# --------------------------------------------------------------------------- sanitising

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
        r"disregard (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
        r"forget (all |your )?(previous |prior )?(instructions|rules)",
        r"you are now\b",
        r"\bsystem prompt\b",
        r"\bnew instructions?:",
        r"\b(remember|memori[sz]e) (that|this)\b",
        r"<\|[^|>]*\|>",
        r"\[/?(INST|SYS)\]",
        r"^\s*#{2,}",
        r"(?:^|\s)(system|assistant)\s*:",
        r"忽略(之前|以上|前面|上面|先前)?的?(所有)?(指令|指示|提示|规则|设定)",
        r"无视(之前|以上|前面)?的?(所有)?(指令|指示|提示|规则)",
        r"(系统提示|系统指令|你现在是|请记住|记住[:：])",
    )
]


@dataclass
class SanitizedText:
    text: str
    injection: bool
    truncated: bool


def sanitize(text: str, max_len: int = 200) -> SanitizedText:
    """Strip control/format characters, drop prompt-injection markers, cap length."""
    cleaned = "".join(
        " " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in text
    )
    injection = False
    for pat in INJECTION_PATTERNS:
        cleaned, n = pat.subn(" ", cleaned)
        injection = injection or n > 0
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    truncated = len(cleaned) > max_len
    return SanitizedText(cleaned[:max_len], injection, truncated)
