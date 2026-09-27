"""Exact board graphs: function plots and labelled points drawn with matplotlib from a small spec.

An image model draws illustrations well but not mathematics (a parabola asked to open upward came out opening
downward, with garbled x₁/x₂ labels [measured locally]), so graphs the lesson needs to be *right* are rendered from
data. Expressions are parsed with an allow-list (numbers, x, + - * / **, a few functions); nothing is executed.

Spec: {"functions": ["x**2-2*x-3"], "x": [-3, 5], "y": [-5, 6] (optional), "points": [{"x": -1, "y": 0, "label": "x₁"}]}
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np

FUNCS = {"sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "sqrt": np.sqrt, "abs": np.abs}
CONSTS = {"pi": np.pi, "e": np.e}
CJK_FONT = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)


def parse_function(expr: str):
    """'x^2-2x-3' style text -> vectorised callable f(x); raises ValueError on anything outside the allow-list."""
    src = str(expr).replace("^", "**").replace("×", "*").replace("−", "-").strip()
    if src.lower().startswith("y="):
        src = src[2:]
    tree = ast.parse(src, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Load)) or isinstance(node, _OPS):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            continue
        if isinstance(node, ast.Name) and (node.id == "x" or node.id in FUNCS or node.id in CONSTS):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
            continue
        raise ValueError(f"not allowed in a plotted function: {ast.dump(node)[:60]}")
    code = compile(tree, "<function>", "eval")
    return lambda x: np.asarray(eval(code, {"__builtins__": {}}, {"x": x, **FUNCS, **CONSTS}), dtype=float)  # noqa: S307


def plot_name(spec: dict) -> str:
    return "p" + hashlib.sha1(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:15] + ".png"


def render_plot(spec: dict, out_dir: str | Path) -> str:
    """Draw the spec into ``out_dir`` (1024x768, the board's 4:3); returns the file name. Raises on a bad spec."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    if Path(CJK_FONT).exists():  # Latin from DejaVu, Chinese from the fallback (it has no Latin glyphs)
        font_manager.fontManager.addfont(CJK_FONT)
        plt.rcParams["font.family"] = ["DejaVu Sans", font_manager.FontProperties(fname=CJK_FONT).get_name()]

    name = plot_name(spec)
    path = Path(out_dir) / name
    if path.exists():
        return name
    funcs = [(str(f), parse_function(f)) for f in (spec.get("functions") or [])][:4]
    points = [p for p in (spec.get("points") or []) if isinstance(p, dict)][:8]
    if not funcs and not points:
        raise ValueError("empty plot")
    x0, x1 = (spec.get("x") or [-5, 5])[:2]
    xs = np.linspace(float(x0), float(x1), 600)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=128)
    colors = ["#1f5fa8", "#c0392b", "#2e8b57", "#8e44ad"]
    ys_all = []
    for (label, f), c in zip(funcs, colors):
        with np.errstate(all="ignore"):
            ys = f(xs) * np.ones_like(xs)
        ys[~np.isfinite(ys)] = np.nan
        ys_all.append(ys)
        tex = label.replace("**", "^").replace("*", "")
        ax.plot(xs, ys, color=c, lw=2.5, label=f"$y = {tex}$")
    for p in points:
        ax.plot(float(p["x"]), float(p["y"]), "o", color="#222", ms=7)
        if p.get("label"):
            ax.annotate(str(p["label"]), (float(p["x"]), float(p["y"])), textcoords="offset points",
                        xytext=(8, 8), fontsize=18)
    if spec.get("y"):
        ax.set_ylim(*[float(v) for v in spec["y"][:2]])
    elif ys_all:
        finite = np.concatenate([y[np.isfinite(y)] for y in ys_all] + [np.array([float(p["y"]) for p in points])])
        lo, hi = np.percentile(finite, [2, 98]) if finite.size else (-5, 5)
        pad = max(1.0, 0.1 * (hi - lo))
        ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(float(x0), float(x1))
    for side in ("left", "bottom"):
        ax.spines[side].set_position("zero")  # axes through the origin, as on a school board
    for side in ("right", "top"):
        ax.spines[side].set_visible(False)
    ax.grid(alpha=0.25)
    if funcs:
        ax.legend(loc="upper left", fontsize=16)
    if spec.get("title"):
        ax.set_title(str(spec["title"])[:30], fontsize=20)
    fig.tight_layout()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.png")
    fig.savefig(tmp, facecolor="white")
    plt.close(fig)
    tmp.replace(path)
    return name


__all__ = ["parse_function", "plot_name", "render_plot"]
