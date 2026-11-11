#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出待复核清单：python tools/review_kp.py [--all]
默认只导出这 5 套卷里需要人看的题（含未打标、双标、可疑单标）。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN_DIR = ROOT / "data" / "generated"
OUT = GEN_DIR / "_kp_review.txt"

qs = json.load(open(GEN_DIR / "question_bank.json", encoding="utf-8"))
only_all = "--all" in sys.argv

lines = []
for q in qs:
    codes = [k["code"] for k in q["knowledge"]]
    tag = "|".join(codes) if codes else "----"
    opts = " ".join(f"{k}.{v}" for k, v in sorted(q["options"].items()))[:70]
    stem = q["stem"][:110].replace("\n", " ")
    kind = "选" if q["qtype"] == 1 else "答"
    lines.append(f'{q["year"]}-{q["no"]:02d} {kind} [{tag}] {stem}')
    if opts:
        lines.append(f'          opt: {opts}')

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"写出 {OUT}，{len(qs)} 道题，{len(lines)} 行")
