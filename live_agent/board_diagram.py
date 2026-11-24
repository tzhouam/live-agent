"""CPU educational diagrams from bounded data: labels, shapes and directed relations.

The teacher model plans the relationships; Pillow draws their labels exactly. This
does not synthesize photographs or infer accurate geometry from prose. Functions
and geometry continue to use ``board_plot`` and its numerical specifications.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DIAGRAM_PROMPT = """把这段教学配图要求编成清晰、正确的教学关系示意图。只输出 JSON 数据，不输出代码或 HTML。
要求：{prompt}
只画要求已经给出的概念、物体、步骤及其关系，不补充不确定的科学结论。
用文字标注的矩形或椭圆代表概念/物体，用箭头表示方向；这是一张关系示意图，不是照片。
保留要求中「」内的标注，文字用简体中文。不要把整段要求画成文字。
几何长度和函数图像由另一个精确作图器负责；此处只表达概念关系，不能伪造曲线或空间尺寸。
最多 8 个节点、10 条箭头；每个节点占据三行三列网格中独立的一格，避免交叉，左右上下顺序应有意义。
节点 text 最多 24 字，箭头 label 最多 10 字；节点 id 用简短字母数字。
格式：{{"title":"图标题", "nodes":[{{"id":"a","text":"概念","column":0,"row":1,"shape":"box"}}],
"arrows":[{{"from":"a","to":"b","label":"关系"}}]}}
column 与 row 是 0、1 或 2，shape 为 box 或 ellipse。箭头只能连接已存在节点。
同一条箭头的 from 与 to 必须不同，禁止自环；循环流程应经过不同节点再回到起点。
"""


def _text(value, limit: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"invalid diagram {field}")
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"control character in diagram {field}")
    return value.strip()


def compile_diagram(data: dict) -> dict:
    """Validate model data before drawing; accepts no expressions, HTML or executable instructions."""
    if not isinstance(data, dict):
        raise ValueError("diagram must be an object")
    title = _text(data.get("title"), 40, "title")
    nodes, arrows = data.get("nodes"), data.get("arrows", [])
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 8:
        raise ValueError("diagram needs 1 to 8 nodes")
    if not isinstance(arrows, list) or len(arrows) > 10:
        raise ValueError("diagram has too many arrows")
    out, ids, cells = [], set(), set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("invalid diagram node")
        ident = node.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", ident) or ident in ids:
            raise ValueError("invalid or duplicate diagram node id")
        column, row = node.get("column"), node.get("row")
        if any(type(v) is not int or v not in range(3) for v in (column, row)):
            raise ValueError("diagram node outside the grid")
        if (column, row) in cells:
            raise ValueError("diagram nodes overlap")
        shape = node.get("shape", "box")
        if shape not in ("box", "ellipse"):
            raise ValueError("invalid diagram shape")
        out.append({"id": ident, "text": _text(node.get("text"), 24, "node text"),
                    "column": column, "row": row, "shape": shape})
        ids.add(ident)
        cells.add((column, row))
    edges = []
    for arrow in arrows:
        if (not isinstance(arrow, dict) or not isinstance(arrow.get("from"), str)
                or not isinstance(arrow.get("to"), str) or arrow["from"] not in ids or arrow["to"] not in ids):
            raise ValueError("diagram arrow needs existing nodes")
        if arrow["from"] == arrow["to"]:
            raise ValueError("diagram self arrow")
        label = arrow.get("label", "")
        if label:
            label = _text(label, 10, "arrow label")
        elif not isinstance(label, str):
            raise ValueError("invalid diagram arrow label")
        edges.append({"from": arrow["from"], "to": arrow["to"], "label": label})
    return {"title": title, "nodes": out, "arrows": edges}


def diagram_name(spec: dict) -> str:
    return "d" + hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:15] + ".png"


def render_diagram(spec: dict, out_dir: str | Path, *, name: str | None = None) -> str:
    """Draw validated relationships into a legible 1024×768 PNG; return its basename."""
    spec = compile_diagram(spec)
    name = name or diagram_name(spec)
    if not re.fullmatch(r"d[0-9a-f]{15}\.png", name):
        raise ValueError("invalid diagram filename")
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1024, 768), "white")
    draw = ImageDraw.Draw(image)
    fonts = {}

    def font(char, size):
        cjk = "\u2e80" <= char <= "\uffef"
        path = ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf" if cjk
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        if (path, size) not in fonts:
            fonts[path, size] = ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default(size=size)
        return fonts[path, size]

    def width(text, size):
        return sum(draw.textlength(c, font=font(c, size)) for c in text)

    def lines(text, size, max_width):
        total = width(text, size)
        if total > max_width:
            count = math.ceil(total / max_width)
            max_width = min(max_width, math.ceil(len(text) / count) * total / len(text) + .1)
        result, line = [], ""
        for c in text:
            if line and width(line + c, size) > max_width:
                result.append(line)
                line = ""
            line += c
        return result + ([line] if line else [])

    def text_at(text, center, size, max_width, color="#29473c", max_height=None):
        rows = lines(text, size, max_width)
        while max_height is not None and len(rows) * (size + 7) > max_height and size > 18:
            size -= 1
            rows = lines(text, size, max_width)
        y = center[1] - len(rows) * (size + 7) / 2
        for row in rows:
            x = center[0] - width(row, size) / 2
            for c in row:
                f = font(c, size)
                draw.text((x, y), c, font=f, fill=color, anchor="lt")
                x += draw.textlength(c, font=f)
            y += size + 7

    text_at(spec["title"], (512, 49), 36, 920)
    centers = {n["id"]: (172 + n["column"] * 340, 234 + n["row"] * 207) for n in spec["nodes"]}

    def boundary(node, toward):
        x, y = centers[node["id"]]
        dx, dy = toward[0] - x, toward[1] - y
        if node["shape"] == "ellipse":
            factor = 1 / math.sqrt((dx / 126) ** 2 + (dy / 63) ** 2)
        else:
            factor = min(126 / abs(dx) if dx else math.inf, 63 / abs(dy) if dy else math.inf)
        return x + dx * factor, y + dy * factor

    lookup = {n["id"]: n for n in spec["nodes"]}
    labels = []
    occupied = [(x - 136, y - 73, x + 136, y + 73) for x, y in centers.values()]
    occupied += [(0, 0, 1024, 105), (0, 727, 1024, 768)]

    def intersects(a, b):
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    for arrow in spec["arrows"]:
        a, b = centers[arrow["from"]], centers[arrow["to"]]
        start, end = boundary(lookup[arrow["from"]], b), boundary(lookup[arrow["to"]], a)
        draw.line((start, end), fill="#467b70", width=5)
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        draw.polygon([end, (end[0] - 17 * math.cos(angle - .45), end[1] - 17 * math.sin(angle - .45)),
                      (end[0] - 17 * math.cos(angle + .45), end[1] - 17 * math.sin(angle + .45))], fill="#467b70")
        if arrow["label"]:
            mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
            rows = lines(arrow["label"], 24, 180)
            half_width = max(width(row, 24) for row in rows) / 2 + 8
            half_height = (len(rows) * 31 + 8) / 2
            nx, ny = -math.sin(angle), math.cos(angle)
            placed = None
            for distance in (28, -28, 48, -48, 72, -72, 104, -104, 140, -140):
                for along in (0, -36, 36, -72, 72):
                    x, y = mx + nx * distance + math.cos(angle) * along, my + ny * distance + math.sin(angle) * along
                    box = (x - half_width, y - half_height, x + half_width, y + half_height)
                    if (box[0] >= 20 and box[2] <= 1004 and box[1] >= 110 and box[3] <= 722
                            and not any(intersects(box, other) for other in occupied)):
                        placed = (x, y, box)
                        break
                if placed:
                    break
            if not placed:
                raise ValueError("diagram arrow labels do not fit; use a simpler layout")
            occupied.append(placed[2])
            labels.append((arrow["label"], placed))
    for node in spec["nodes"]:
        x, y = centers[node["id"]]
        box = (x - 126, y - 63, x + 126, y + 63)
        if node["shape"] == "ellipse":
            draw.ellipse(box, fill="#e9f1e7", outline="#467b70", width=3)
        else:
            draw.rounded_rectangle(box, radius=18, fill="#e9f1e7", outline="#467b70", width=3)
        text_at(node["text"], (x, y), 30, 180 if node["shape"] == "ellipse" else 216,
                max_height=98 if node["shape"] == "ellipse" else 110)
    for label, (x, y, box) in labels:
        draw.rounded_rectangle(box, radius=6, fill="white")
        text_at(label, (x, y), 24, 180)
    draw.text((38, 733), "SCHEMATIC", font=font("S", 17), fill="#71847a")
    with tempfile.NamedTemporaryFile(dir=directory, suffix=".png", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        image.save(temp_path, format="PNG")
        temp_path.replace(directory / name)
    finally:
        temp_path.unlink(missing_ok=True)
    return name
