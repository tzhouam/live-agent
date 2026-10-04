"""Font loading and mixed Latin/CJK text drawing for PIL-rendered generator frames.

No installed font covers both scripts on this host, so runs are split by script and drawn
with the first font that loads. Shared by the mock placeholder frames and the puppet rig.
"""

from __future__ import annotations

import re

_CJK_FONTS = ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
_LATIN_FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",)
_font_cache: dict[tuple[str, int], object] = {}


def font(kind: str, size: int):
    key = (kind, size)
    if key not in _font_cache:
        from PIL import ImageFont

        f = None
        for path in (_CJK_FONTS if kind == "cjk" else _LATIN_FONTS):
            try:
                f = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        _font_cache[key] = f or ImageFont.load_default()
    return _font_cache[key]


def runs(text: str):
    """Split into (is_ascii, run) pieces: no installed font covers both Latin and CJK here."""
    out: list[tuple[bool, str]] = []
    for ch in text:
        a = ord(ch) < 0x2E80  # Latin, punctuation, symbols -> DejaVu; CJK blocks start at U+2E80
        if out and out[-1][0] == a:
            out[-1] = (a, out[-1][1] + ch)
        else:
            out.append((a, ch))
    return out


def width(text: str, size: int) -> float:
    return sum(font("latin" if a else "cjk", size).getlength(r) for a, r in runs(text))


def draw(d, x: float, y: float, text: str, size: int, fill) -> None:
    for a, r in runs(text):
        f = font("latin" if a else "cjk", size)
        d.text((x, y), r, fill=fill, font=f)
        x += f.getlength(r)


def wrap(text: str, size: int, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in re.split(r"(\s+)", text):
        pieces = [word] if all(ord(c) < 0x2E80 for c in word) else list(word)  # CJK wraps per character
        for piece in pieces:
            if cur and width(cur + piece, size) > max_w:
                lines.append(cur.rstrip())
                cur = piece.lstrip()
            else:
                cur += piece
    return lines + ([cur] if cur.strip() else [])
