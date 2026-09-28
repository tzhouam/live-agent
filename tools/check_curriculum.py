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
            warnings.append(f"{name}: source {s.get('id')} has no URL")
    lo, hi = (d.get("grades") or [1, 12])[:2]
    if not (1 <= lo <= hi <= 12):
        errors.append(f"{name}: grades {d.get('grades')} out of 1-12")
    for st in d.get("stages") or []:
        gs = st.get("grades") or []
        if not gs or any(not isinstance(g, int) or not 1 <= g <= 12 for g in gs):
            errors.append(f"{name}: stage {st.get('name')} has grades {gs}")
        for dom in st.get("domains") or []:
            if dom.get("source") and any(x.strip() not in ids for x in str(dom["source"]).split(",")):
                errors.append(f"{name}: stage {st.get('name')} / {dom.get('name')} cites unknown source {dom['source']}")
    gt = d.get("grade_topics") or {}
    missing = [g for g in range(lo, hi + 1) if str(g) not in gt]
    if missing:
        warnings.append(f"{name}: no topics for grades {missing}")
    for g, e in gt.items():
        if not str(g).isdigit() or not 1 <= int(g) <= 12:
            errors.append(f"{name}: grade_topics key {g!r}")
        if (e or {}).get("source") and any(x.strip() not in ids for x in str(e["source"]).split(",")):
            errors.append(f"{name}: grade {g} cites unknown source {e['source']}")
        if not (e or {}).get("topics"):
            warnings.append(f"{name}: grade {g} has no topics")
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
