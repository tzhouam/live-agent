"""Validate curriculum knowledge-base files (configs/curriculum/*.json) and report coverage.

    python3 tools/check_curriculum.py [dir]

Checks: required fields, every "source" reference points to a listed source with a URL, grade ranges are within
1-12, per-grade topics cover the subject's grade span; reports how many topics rest on a textbook, the standard,
or an estimate. Exit code 1 on a structural error (missing fields, dangling source ids, bad grades).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def check_subject(d: dict, name: str) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for key in ("subject", "grades", "sources", "stages", "grade_topics"):
        if key not in d:
            errors.append(f"{name}: missing '{key}'")
    ids = {s.get("id") for s in d.get("sources") or []}
    for s in d.get("sources") or []:
        if not str(s.get("url") or "").startswith("http"):
            errors.append(f"{name}: source {s.get('id')} has no URL")
    lo, hi = (d.get("grades") or [1, 12])[:2]
    if not (1 <= lo <= hi <= 12):
        errors.append(f"{name}: grades {d.get('grades')} out of 1-12")
    for st in d.get("stages") or []:
        gs = st.get("grades") or []
        if not gs or any(not isinstance(g, int) or not 1 <= g <= 12 for g in gs):
            errors.append(f"{name}: stage {st.get('name')} has grades {gs}")
        for dom in st.get("domains") or []:
            if dom.get("requirements") and not dom.get("source"):
                errors.append(f"{name}: stage {st.get('name')} / {dom.get('name')} has requirements but no source")
            if dom.get("source") and any(x.strip() not in ids for x in str(dom["source"]).split(",")):
                errors.append(f"{name}: stage {st.get('name')} / {dom.get('name')} cites unknown source {dom['source']}")
    gt = d.get("grade_topics") or {}
    # a grade inside the subject's range without topics is an error unless the file documents it as a gap
    # ("gaps": {"9": "why"}), e.g. 地理 and 信息科技 end in grade 8 in the 2022 compulsory standards
    documented = {str(k) for k in (d.get("gaps") or {})}
    missing = [g for g in range(lo, hi + 1) if str(g) not in gt and str(g) not in documented]
    if missing:
        errors.append(f"{name}: no topics for grades {missing} (add them or document the gap in 'gaps')")
    for g, e in gt.items():
        if not str(g).isdigit() or not 1 <= int(g) <= 12:
            errors.append(f"{name}: grade_topics key {g!r}")
        if (e or {}).get("source") and any(x.strip() not in ids for x in str(e["source"]).split(",")):
            errors.append(f"{name}: grade {g} cites unknown source {e['source']}")
        if (e or {}).get("basis") not in ("textbook", "standard", "estimate"):
            errors.append(f"{name}: grade {g} basis {(e or {}).get('basis')!r} (textbook / standard / estimate)")
        if not (e or {}).get("source"):
            errors.append(f"{name}: grade {g} has no source")
        if not (e or {}).get("topics"):
            warnings.append(f"{name}: grade {g} has no topics")
    return errors, warnings


def check_craft(d: dict) -> tuple[list[str], list[str]]:
    """teaching_craft.json: sources with URLs; every citation resolves; bands cover grades 1-12 without overlap;
    moves name known stages; masters and moves have grades within 1-12 and at least one source."""
    errors, warnings = [], []
    ids = {s.get("id") for s in d.get("sources") or []}
    for s in d.get("sources") or []:
        if not str(s.get("url") or "").startswith("http"):
            errors.append(f"teaching_craft: source {s.get('id')} has no URL")
        if not s.get("accessed"):
            warnings.append(f"teaching_craft: source {s.get('id')} has no access date")

    def cites(item: dict, what: str, required: bool = True) -> None:
        srcs = item.get("sources") or []
        if required and not srcs:
            errors.append(f"teaching_craft: {what} has no sources")
        for x in srcs:
            if x not in ids:
                errors.append(f"teaching_craft: {what} cites unknown source {x}")

    def grades_ok(item: dict, what: str) -> None:
        gs = item.get("grades")
        if gs is not None and (len(gs) != 2 or not all(isinstance(g, int) and 1 <= g <= 12 for g in gs) or gs[0] > gs[1]):
            errors.append(f"teaching_craft: {what} has grades {gs}")

    stages = [st.get("id") for st in (d.get("lesson_model") or {}).get("stages") or []]
    if not stages:
        errors.append("teaching_craft: lesson_model has no stages")
    for st in (d.get("lesson_model") or {}).get("stages") or []:
        if not st.get("rules"):
            errors.append(f"teaching_craft: stage {st.get('id')} has no rules")
        cites(st, f"stage {st.get('id')}")
    covered = Counter()
    for b in d.get("bands") or []:
        grades_ok(b, f"band {b.get('id')}")
        cites(b, f"band {b.get('id')}")
        lo, hi = (b.get("grades") or [0, -1])[:2]
        for g in range(lo, hi + 1) if isinstance(lo, int) and isinstance(hi, int) else []:
            covered[g] += 1
        for sid in (b.get("stage_notes") or {}):
            if sid not in stages:
                errors.append(f"teaching_craft: band {b.get('id')} notes unknown stage {sid}")
    for g in range(1, 13):
        if covered[g] != 1:
            errors.append(f"teaching_craft: grade {g} is in {covered[g]} bands (must be exactly one)")
    for m in d.get("moves") or []:
        for sid in m.get("stages") or []:
            if sid not in stages:
                errors.append(f"teaching_craft: move {m.get('id')} names unknown stage {sid}")
        if not m.get("stages"):
            errors.append(f"teaching_craft: move {m.get('id')} has no stages")
        if not m.get("what"):
            errors.append(f"teaching_craft: move {m.get('id')} has no 'what'")
        grades_ok(m, f"move {m.get('id')}")
        cites(m, f"move {m.get('id')}")
    for m in d.get("masters") or []:
        for key in ("name", "subjects", "method", "moves"):
            if not m.get(key):
                errors.append(f"teaching_craft: master {m.get('id')} has no '{key}'")
        grades_ok(m, f"master {m.get('id')}")
        cites(m, f"master {m.get('id')}")
        if not m.get("honours"):
            warnings.append(f"teaching_craft: master {m.get('id')} lists no honours (why outstanding?)")
    cites(d.get("board") or {}, "board", required=bool((d.get("board") or {}).get("rules")))
    for c in d.get("checklist") or []:
        if not c.get("item"):
            errors.append(f"teaching_craft: checklist entry {c.get('id')} has no item")
        if c.get("scope") not in (None, "section", "feedback"):
            errors.append(f"teaching_craft: checklist entry {c.get('id')} has scope {c.get('scope')!r}")
        grades_ok(c, f"checklist {c.get('id')}")
        cites(c, f"checklist {c.get('id')}")
    return errors, warnings


def main(directory: str = "configs/curriculum") -> int:
    d = Path(directory)
    errors, warnings = [], []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            errors.append(f"{f.name}: invalid JSON ({e})")
            continue
        if f.stem == "teaching_craft":
            e, w = check_craft(data)
            errors += e
            warnings += w
            print(f"teaching_craft: stages {len((data.get('lesson_model') or {}).get('stages') or [])}, "
                  f"moves {len(data.get('moves') or [])}, masters {len(data.get('masters') or [])}, "
                  f"bands {len(data.get('bands') or [])}, board rules {len((data.get('board') or {}).get('rules') or [])}, "
                  f"checklist {len(data.get('checklist') or [])}, sources {len(data.get('sources') or [])}")
            continue
        if f.stem == "pedagogy":
            ids = {s.get("id") for s in data.get("sources") or []}
            grades = data.get("grades") or {}
            miss = [g for g in range(1, 13) if str(g) not in grades]
            if miss:
                warnings.append(f"pedagogy: no profile for grades {miss}")
            for g, p in grades.items():
                for key in ("methods", "tone", "content"):
                    if not p.get(key):
                        warnings.append(f"pedagogy: grade {g} has no '{key}'")
                for s in p.get("sources") or []:
                    if s not in ids:
                        errors.append(f"pedagogy: grade {g} cites unknown source {s}")
            print(f"pedagogy: grades {sorted(int(g) for g in grades if str(g).isdigit())}, sources {len(ids)}")
            continue
        e, w = check_subject(data, f.name)
        errors += e
        warnings += w
        basis = Counter((v or {}).get("basis", "?") for v in (data.get("grade_topics") or {}).values())
        n_topics = sum(len((v or {}).get("topics") or []) for v in (data.get("grade_topics") or {}).values())
        print(f"{f.name}: {data.get('subject')} grades {data.get('grades')}, stages {len(data.get('stages') or [])}, "
              f"topics {n_topics}, grade basis {dict(basis)}, sources {len(data.get('sources') or [])}")
    for w in warnings:
        print("WARN", w)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
