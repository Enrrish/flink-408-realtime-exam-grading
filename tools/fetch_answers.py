#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
answers.csv 生成与校验
用法：python tools/fetch_answers.py

两条来源通道：
  1) text  ：答案 PDF 带文本层，逐题解析 "NN. X" 或 "NN.【参考答案】X" 抽取，可复现
  2) visual：答案 PDF 是纯图片，人工/视觉读图录入，此处以字面量固化并注明页码

答案来源可信度必须可追溯，故 csv 保留 source 列；parse_408.py 只读 answer 列。
"""
import re
import csv
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "408-exam-paper"
ANS_DIR = RAW_DIR / "answers"
OUT = ROOT / "data" / "seed" / "answers.csv"

SCOPE = [2022, 2023, 2024, 2025, 2026]

# 逐题解析文本可用的年份，直接抽取
TEXT_YEARS = [2022, 2023]

# 纯图片年份：读图录入（1-40 顺序）。2024/2025 来自答案 PDF 第 1 页内嵌图，
# 2024 的 36-40 在第 2 张图顶部；2026 来自第 1 页内嵌图，1-40 完整一页。
VISUAL = {
    # 每行 8 题，共 5 行
    2024: "DAABDADA" "BCDBBCDD" "CBCBACAA" "DAABACCC" "BCDBDDCD",
    2025: "BDDBDCCC" "ADADDDCB" "CBAABADC" "CBDCCACB" "BCCCBABA",
    2026: "ADCBDDBD" "BAACABAD" "ACAADCCD" "DACCDBDD" "BDBBBACD",
}


def read_text(year: int) -> str:
    r = PdfReader(str(ANS_DIR / f"{year}-answer.pdf"))
    if r.is_encrypted:
        r.decrypt("")
    return "\n".join((p.extract_text() or "") for p in r.pages)


def from_text(year: int) -> dict:
    """优先用逐题解析（每题的解析句首自带答案），再用首页答案表交叉校验。"""
    t = read_text(year)
    per = {}
    for m in re.finditer(
        r"(?m)^\s*0?(\d{1,2})\s*[.．]\s*(?:【参考答案】)?\s*([A-D])\s*(?=[。．]|$)", t
    ):
        n = int(m.group(1))
        if 1 <= n <= 40 and n not in per:
            per[n] = m.group(2)

    table = from_table(year)
    diff = [n for n in range(1, 41) if n in per and n in table and per[n] != table[n]]
    if diff:
        raise SystemExit(f"{year} 逐题解析与答案表冲突：{diff}")
    merged = {**table, **per}
    missing = [n for n in range(1, 41) if n not in merged]
    if missing:
        raise SystemExit(f"{year} 缺答案：{missing}")
    return merged


def read_layout(year: int) -> str:
    r = PdfReader(str(ANS_DIR / f"{year}-answer.pdf"))
    if r.is_encrypted:
        r.decrypt("")
    return r.pages[0].extract_text(extraction_mode="layout") or ""


def from_table(year: int) -> dict:
    """首页答案表：字母按列排布，第 c 列依次对应 c+1, c+9, c+17, c+25, c+33。

    2022 的表格是 8 列 × 5 行，普通抽取会打乱列序，必须用 layout 模式还原。
    """
    try:
        layout = read_layout(year)
    except Exception:
        return {}
    m = re.search(r"单项选择题\s*((?:[A-D]{5}\s*){8})", layout)
    if not m:
        return {}
    groups = re.findall(r"[A-D]{5}", m.group(1))
    out = {}
    for c, g in enumerate(groups):
        for j, ch in enumerate(g):
            out[c + 1 + 8 * j] = ch
    return out


def main():
    rows = []
    for y in SCOPE:
        if y in VISUAL:
            s = re.sub(r"\s", "", VISUAL[y])
            if len(s) != 40:
                raise SystemExit(f"{y} 视觉转录长度 {len(s)}，应为 40")
            ans, src = {i + 1: ch for i, ch in enumerate(s)}, "visual"
        else:
            ans, src = from_text(y), "text"
        bad = {ch: sum(1 for v in ans.values() if v == ch) for ch in "ABCD"}
        if max(bad.values()) > 20:
            raise SystemExit(f"{y} 答案分布异常：{bad}")
        rows += [(y, n, ans[n], src) for n in range(1, 41)]
        print(f"{y}  {''.join(ans[n] for n in range(1, 41))}  ({src})  分布 {bad}")

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "qno", "answer", "source"])
        w.writerows(rows)
    print(f"\n写出 {OUT.relative_to(ROOT)}，共 {len(rows)} 条")


if __name__ == "__main__":
    main()
