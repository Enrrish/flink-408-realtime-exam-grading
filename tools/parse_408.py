#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
408 真题 PDF → 结构化题库

用法：
    python tools/parse_408.py                      # 解析全部年份
    python tools/parse_408.py --years 2023 2024    # 只解析指定年份
    python tools/parse_408.py --report             # 只输出解析质量报告

输入：
    data/raw/408-exam-paper/papers-rebuild/{year}.pdf   试卷（有文本层）
    data/seed/answers.csv                               答案（人工补录 + 校验）
    data/seed/kp_override.csv                           知识点人工复核结果

输出：
    data/generated/question_bank.json   结构化题库
    sql/02_question_seed.sql            可直接执行的 INSERT 脚本

说明：
    1. 题干与选项可全自动解析；答案不在试卷 PDF 里，需从答案 PDF 补录
    2. 知识点标签为关键词规则预标注（mark=auto），必须人工复核后再用于统计
    3. 题干中的插图未提取，仅标记 has_figure，原图见 PDF
"""
import os
import re
import json
import csv
import sys
import argparse
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "408-exam-paper"
PAPER_DIR = RAW_DIR / "papers-rebuild"
ANSWER_CSV = ROOT / "data" / "seed" / "answers.csv"
KP_OVERRIDE = ROOT / "data" / "seed" / "kp_override.csv"
OUT_DIR = ROOT / "data" / "generated"
OUT_JSON = OUT_DIR / "question_bank.json"
OUT_SQL = ROOT / "sql" / "02_question_seed.sql"

# 项目口径：只收最近 5 套（2022-2026）。
# 理由：一场模考用 1 套 150 分整卷即可，压测用同一套卷 × N 个虚拟考生，
# 无需更多题；而答案补录与标签复核的成本随套数线性增长。
SCOPE_YEARS = [2022, 2023, 2024, 2025, 2026]

# ---------------------------------------------------------------- 科目划分
# 408 试卷结构（2009 年起稳定）：单选 40 题，数据结构 1-11、组成原理 12-22、
# 操作系统 23-32、计算机网络 33-40；综合应用题 7 题，41-42 数据结构、
# 43-44 组成原理、45-46 操作系统、47 计算机网络。
# 注：已用 2009-2026 全部 18 套卷逐年核对，Q11 均为数据结构内容、Q12 均为组成原理。
SUBJECT_OF = {}
for n in range(1, 12):
    SUBJECT_OF[n] = 1
for n in range(12, 23):
    SUBJECT_OF[n] = 2
for n in range(23, 33):
    SUBJECT_OF[n] = 3
for n in range(33, 41):
    SUBJECT_OF[n] = 4
for n in (41, 42):
    SUBJECT_OF[n] = 1
for n in (43, 44):
    SUBJECT_OF[n] = 2
for n in (45, 46):
    SUBJECT_OF[n] = 3
SUBJECT_OF[47] = 4

SUBJECT_NAME = {1: "数据结构", 2: "计算机组成原理", 3: "操作系统", 4: "计算机网络"}
# 大题分值不固定（2024 年为 13+10、2023 年为 13+10、2022 年为 14+9），
# 一律从题干中的“（X 分）”解析，解析失败才回落到这里的缺省值
BIG_SCORE_DEFAULT = {41: 13, 42: 10, 43: 13, 44: 10, 45: 7, 46: 8, 47: 9}

# ---------------------------------------------------------------- 知识点规则
# 顺序敏感：具体规则在前，宽泛规则在后；首个命中即采用。
# code 对应 sql/01_question_bank.sql 里 knowledge_point.code
KP_RULES = {
    1: [
        (r"哈夫曼|Huffman", "DS.TREE.HUFF"),
        # B 树、散列等属于“查找”，必须排在“树”之前，否则会被 DS.TREE 抢走
        (r"B 树|B\+树|散列|哈希|Hash|折半|二分查找|ASL|装填因子|红黑树|平衡二叉|二叉搜索树|查找", "DS.SEARCH"),
        (r"二叉树|遍历|中序|前序|后序|线索|完全二叉|满二叉|AVL", "DS.TREE.BT"),
        (r"树|森林|孩子兄弟|并查集|三叉树", "DS.TREE"),
        (r"有向图|无向图|邻接|顶点|拓扑|连通|生成树|最短路径|关键路径|AOE|AOV|DAG", "DS.GRAPH"),
        # 排序排在数组/栈之前，避免“对数组排序”被归到 DS.STACK
        (r"排序|归并|快排|堆排序|基数|希尔|冒泡|直接插入|败者树", "DS.SORT"),
        (r"栈|队列|后缀|前缀|表达式|稀疏矩阵|三元组|循环队列|出入栈", "DS.STACK"),
        (r"链表|线性表|顺序表|单链|双链|指针", "DS.LIST"),
        (r"时间复杂度|空间复杂度", "DS"),
    ],
    2: [
        (r"Cache|cache|缓存|命中率|主存|虚拟存储|TLB|存储器|替换算法|写策略|局部性|页表|页框", "CO.MEMORY.CACHE"),
        (r"浮点|补码|原码|反码|IEEE|定点|溢出|移码|ALU|阶码|尾数", "CO.DATA"),
        (r"流水线|数据通路|控制器|微程序|微指令|冒险|多核|SMP", "CO.CPU"),
        # 性能指标排在指令之前，避免“执行 10000 条指令 + CPI”被归到指令系统
        (r"CPI|MIPS|主频|性能|吞吐|响应时间|基准程序", "CO.OVERVIEW"),
        (r"指令|寻址|汇编|RISC|CISC|操作码|机器级|链接|编译|寄存器", "CO.ISA"),
        (r"总线|DMA|I/O|磁盘|SSD|接口|程序查询|RAID", "CO.IO"),
        (r"异常|中断", "CO.CPU"),
    ],
    3: [
        (r"页面置换|LRU|FIFO|OPT|CLOCK|缺页|页框|请求分页|工作集|抖动|Belady", "OS.MEMORY.PR"),
        # 磁盘调度必须先于“进程/调度”规则，否则会被误判为进程调度
        (r"磁盘调度|SPOOLing|缓冲区|设备|DMA|中断|I/O|固态|SSD|扇区", "OS.IO"),
        (r"分页|分段|段页|虚拟内存|逻辑地址|物理地址|页表|内存分配|地址转换|快表", "OS.MEMORY"),
        (r"进程|线程|调度|同步|互斥|信号量|PV 操作|死锁|临界区|管程|银行家|就绪|阻塞|原语", "OS.PROCESS"),
        (r"文件|目录|索引结点|inode|文件系统|空闲空间|FAT|位示图|超级块", "OS.FILE"),
        (r"内核|用户态|系统调用|微内核|虚拟机|引导|特权", "OS.OVERVIEW"),
    ],
    4: [
        (r"香农|奈奎斯特|编码|调制|波特|码元|信道|双绞线|光纤|信噪比|曼彻斯特", "NET.PHY.SHANNON"),
        (r"以太网|CSMA|VLAN|交换机|帧|PPP|GBN|选择重传|停止等待|滑动窗口|CRC|海明|网桥|冲突域", "NET.LINK"),
        (r"IP 分组|IPv4|IPv6|子网|CIDR|ARP|DHCP|ICMP|路由|RIP|OSPF|BGP|NAT|组播|自治系统|TTL|前缀", "NET.IP"),
        (r"TCP|UDP|拥塞|三次握手|四次挥手|确认号|序号|慢开始|重传|套接字|端口", "NET.TCP"),
        (r"DNS|HTTP|FTP|SMTP|POP3|P2P|应用层|URL|万维网", "NET.APP"),
        (r"OSI|TCP/IP 模型|体系结构|分层|协议|服务|接口", "NET.ARCH"),
    ],
}

# 知识点 code → 数据库 id（与 sql/01_question_bank.sql 一致）
KP_ID = {    "DS": 1, "DS.LIST": 2, "DS.STACK": 3, "DS.TREE": 4, "DS.GRAPH": 5,
    "DS.SEARCH": 6, "DS.SORT": 7, "DS.TREE.BT": 8, "DS.TREE.HUFF": 9,
    "CO": 10, "CO.OVERVIEW": 11, "CO.DATA": 12, "CO.MEMORY": 13,
    "CO.ISA": 14, "CO.CPU": 15, "CO.IO": 16, "CO.MEMORY.CACHE": 17,
    "OS": 18, "OS.OVERVIEW": 19, "OS.PROCESS": 20, "OS.MEMORY": 21,
    "OS.FILE": 22, "OS.IO": 23, "OS.MEMORY.PR": 24,
    "NET": 25, "NET.ARCH": 26, "NET.PHY": 27, "NET.LINK": 28,
    "NET.IP": 29, "NET.TCP": 30, "NET.APP": 31, "NET.PHY.SHANNON": 32,
}

# 知识点父子关系（用于过滤“父节点”式冗余标签）与根节点集合
KP_PARENT = {
    2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 4, 9: 4,
    11: 10, 12: 10, 13: 10, 14: 10, 15: 10, 16: 10, 17: 13,
    19: 18, 20: 18, 21: 18, 22: 18, 23: 18, 24: 21,
    26: 25, 27: 25, 28: 25, 29: 25, 30: 25, 31: 25, 32: 27,
}
KP_ROOT = {1, 10, 18, 25}


def is_ancestor(a: int, b: int) -> bool:
    """a 是否为 b 的祖先"""
    cur = KP_PARENT.get(b)
    while cur:
        if cur == a:
            return True
        cur = KP_PARENT.get(cur)
    return False


# ---------------------------------------------------------------- 文本清洗
RE_PAGE_HEAD = re.compile(r"第\s*\d+\s*页\s*[（(]\s*共\s*\d+\s*页\s*[)）]")
RE_Q_START = re.compile(r"^(\d{1,2})\s*[.．、]\s*")
RE_OPT_SPLIT = re.compile(r"(?:^|\s)([A-D])\s*[.．、]\s*")
RE_FIG = re.compile(r"题\s*(\d{1,2})\s*图")
RE_SUBQ = re.compile(r"[（(]\s*(\d)\s*[)）]")
RE_SCORE = re.compile(r"^[（(]\s*(\d{1,2})\s*分\s*[)）]\s*")
TITLE_NOISE = re.compile(r"全国硕士研究生入学统一考试|计算机学科专业基础综合试题|^一、单项选择题|^二、综合应用题|^[一二三四五六七八九十]、")


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    parts = []
    for page in reader.pages:
        t = page.extract_text() or ""
        parts.append(t)
    return "\n".join(parts)


def clean_lines(raw: str):
    lines = []
    for line in raw.split("\n"):
        line = line.replace("\u3000", " ").strip()
        if not line:
            continue
        if RE_PAGE_HEAD.search(line):
            continue
        if TITLE_NOISE.search(line) and len(line) < 60 and not RE_Q_START.match(line):
            continue
        lines.append(line)
    return lines


def split_options(block_lines):
    """从题目行块中剥离选项，返回 (题干行列表, {A:..,B:..,C:..,D:..})"""
    first_opt = None
    for i, line in enumerate(block_lines):
        if re.match(r"^[A-D]\s*[.．、]", line):
            first_opt = i
            break
    if first_opt is None:
        return block_lines, {}

    stem_lines = block_lines[:first_opt]
    opt_text = " ".join(block_lines[first_opt:])
    # 按 " A. / B. / C. / D." 切分，注意首项前面没有空格
    padded = " " + opt_text
    marks = list(RE_OPT_SPLIT.finditer(padded))
    options = {}
    for idx, m in enumerate(marks):
        key = m.group(1)
        start = m.end()
        end = marks[idx + 1].start() if idx + 1 < len(marks) else len(padded)
        val = padded[start:end].strip(" 　,，;；")
        if key not in options and val:
            options[key] = val
    return stem_lines, options


def parse_paper(year: int):
    pdf = PAPER_DIR / f"{year}.pdf"
    if not pdf.exists():
        return [], f"{year}: 文件不存在"

    raw = extract_text(pdf)
    lines = clean_lines(raw)

    # 切分题块：以行首数字编号为界
    blocks = []
    cur_no, cur_lines = None, []
    for line in lines:
        m = RE_Q_START.match(line)
        if m:
            no = int(m.group(1))
            if 1 <= no <= 47:
                if cur_no is not None:
                    blocks.append((cur_no, cur_lines))
                cur_no = no
                cur_lines = [line[m.end():].strip()]
                continue
        if cur_no is not None:
            cur_lines.append(line)
    if cur_no is not None:
        blocks.append((cur_no, cur_lines))

    questions = []
    seen = set()
    for no, blines in blocks:
        if no in seen:
            # 题干内部出现“1.”“2.”这类编号会被误判为新题号。
            # 误切块的归属是“当前正在解析的那道题”，而不是历史上同号的题，
            # 否则第 47 题里的编号会被拼进第 1 题（2022 年曾出现）。
            if questions:
                questions[-1]["stem"] += " " + " ".join(blines)
            continue
        seen.add(no)

        stem_lines, options = split_options(blines)
        stem = " ".join(stem_lines).strip()
        stem = re.sub(r"\s{2,}", " ", stem)

        has_fig = bool(RE_FIG.search(" ".join(blines)))

        if no <= 40:
            q = {
                "no": no,
                "qtype": 1,
                "subject": SUBJECT_OF[no],
                "stem": stem,
                "options": options,
                "score": 2.0,
                "has_figure": has_fig,
                # 少数题目四个选项本身就是图片，解析不到文字选项
                "options_image": len(options) == 0,
            }
        else:
            subs = []
            sub_text = " ".join(stem_lines)
            marks = list(RE_SUBQ.finditer(sub_text))
            if marks:
                head = sub_text[: marks[0].start()].strip()
                for i, m in enumerate(marks):
                    s = m.end()
                    e = marks[i + 1].start() if i + 1 < len(marks) else len(sub_text)
                    subs.append({"seq": int(m.group(1)), "stem": sub_text[s:e].strip()})
            else:
                head = sub_text
            # 分数字段写在题干开头：“（13 分）2023 年 10 月……”
            score = float(BIG_SCORE_DEFAULT.get(no, 0))
            m = RE_SCORE.match(head)
            if m:
                score = float(m.group(1))
                head = head[m.end():].strip()
            q = {
                "no": no,
                "qtype": 2,
                "subject": SUBJECT_OF[no],
                "stem": head,
                "options": {},
                "subs": subs,
                "score": score,
                "has_figure": has_fig,
                "options_image": False,
            }
        questions.append(q)

    # 补齐缺失题号
    got = {q["no"] for q in questions}
    missing = [n for n in range(1, 48) if n not in got]
    for q in questions:
        q["year"] = year
        q["id"] = year * 1000 + q["no"]

    note = f"{year}: 解析 {len(questions)}/47"
    if missing:
        note += f"，缺 {missing}"
    return questions, note


def tag_knowledge(q):
    """关键词规则预标注，返回 [{"kp_id","code","weight","mark"}]

    匹配顺序：题干 → 小问 → 选项。选项只在题干毫无命中时才参与，
    因为选项里常出现“数组”“结点”“指针”这类通用词，会污染主要考点。
    结果标记 auto，必须人工复核后才能用于学情统计。
    """
    rules = KP_RULES.get(q["subject"], [])

    def hits(text, limit):
        out = []
        for pattern, code in rules:
            if code in [c for c, _ in out]:
                continue
            if re.search(pattern, text):
                out.append((code, 1.00 if not out else 0.50))
            if len(out) >= limit:
                break
        return out

    stem_text = q["stem"]
    if q.get("subs"):
        stem_text += " " + " ".join(s["stem"] for s in q["subs"])
    found = hits(stem_text, 2)

    if not found and q.get("options"):
        found = hits(" ".join(q["options"].values()), 1)

    out = []
    for code, w in found:
        kp = KP_ID.get(code)
        if not kp:
            continue
        if out:
            primary = out[0]["kp_id"]
            # 父节点/根节点式标签会重复计分，直接丢弃
            if kp == primary or kp in KP_ROOT or is_ancestor(kp, primary):
                continue
        out.append({"kp_id": kp, "code": code, "weight": w, "mark": "auto"})
    return out


def load_overrides():
    """人工复核结果，{(year, qno): [code, ...]}

    首个 code 为主要考点（权重 1.0），其余为次要考点（0.5）。
    CSV 列：year,qno,codes,note；codes 用 | 或 , 分隔。
    """
    out = {}
    if not KP_OVERRIDE.exists():
        return out
    with open(KP_OVERRIDE, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                y, n = int(row["year"]), int(row["qno"])
            except (KeyError, ValueError, TypeError):
                continue
            raw = (row.get("codes") or "").replace("|", ",")
            codes = [c.strip() for c in raw.split(",") if c.strip()]
            codes = [c for c in codes if c in KP_ID]
            if codes:
                out[(y, n)] = codes
    return out


# ---------------------------------------------------------------- 输出
def load_answers():
    """读取 data/answers.csv，返回 {(year, qno): 'A'}"""
    ans = {}
    if not ANSWER_CSV.exists():
        return ans
    with open(ANSWER_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                y, n = int(row["year"]), int(row["qno"])
                a = (row.get("answer") or "").strip().upper()
                if a in ("A", "B", "C", "D"):
                    ans[(y, n)] = a
            except (KeyError, ValueError, TypeError):
                continue
    return ans


def sql_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def write_sql(questions):
    lines = [
        "-- 由 tools/parse_408.py 自动生成，请勿手工修改",
        "SET NAMES utf8mb4;",
        "",
        "DELETE FROM question_knowledge;",
        "DELETE FROM question_sub;",
        "DELETE FROM question;",
        "",
    ]
    for q in questions:
        opts = json.dumps(
            [{"key": k, "content": v} for k, v in sorted(q["options"].items())],
            ensure_ascii=False,
        )
        answer = q.get("answer") or None
        vals = [
            str(q["id"]),
            str(q["subject"]),
            str(q["qtype"]),
            f"'{sql_escape(q['stem'])}'",
            f"'{sql_escape(opts)}'" if opts != "[]" else "NULL",
            f"'{answer}'" if answer else "NULL",
            f"{q['score']}",
            f"'{q['year']}-408-{q['no']}'",
        ]
        lines.append(
            "INSERT INTO question (id, subject, qtype, stem, options, answer, score, source) "
            "VALUES (" + ", ".join(vals) + ");"
        )
    lines.append("")

    for q in questions:
        for kp in q["knowledge"]:
            lines.append(
                "INSERT INTO question_knowledge (question_id, knowledge_point_id, weight) "
                f"VALUES ({q['id']}, {kp['kp_id']}, {kp['weight']:.2f});"
            )
    lines.append("")

    for q in questions:
        for sub in q.get("subs", []):
            lines.append(
                "INSERT INTO question_sub (question_id, seq, stem, score) VALUES "
                f"({q['id']}, {sub['seq']}, '{sql_escape(sub['stem'])}', 0.0);"
            )

    OUT_SQL.parent.mkdir(parents=True, exist_ok=True)
    OUT_SQL.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    years = args.years or [y for y in SCOPE_YEARS if (PAPER_DIR / f"{y}.pdf").exists()]
    if not years:
        print("未找到 PDF，请先确认 data/408-exam-paper/papers-rebuild/")
        sys.exit(1)

    answers = load_answers()
    overrides = load_overrides()
    reviewed = 0
    all_q, notes = [], []
    for y in years:
        qs, note = parse_paper(y)
        notes.append(note)
        for q in qs:
            q["answer"] = answers.get((y, q["no"]))
            ov = overrides.get((y, q["no"]))
            if ov:
                reviewed += 1
                q["knowledge"] = [
                    {
                        "kp_id": KP_ID[c],
                        "code": c,
                        "weight": 1.0 if i == 0 else 0.5,
                        "mark": "review",
                    }
                    for i, c in enumerate(ov)
                ]
            else:
                q["knowledge"] = tag_knowledge(q)
        all_q.extend(qs)

    print("=" * 62)
    print("解析结果")
    print("=" * 62)
    for n in notes:
        print(" ", n)

    sel = [q for q in all_q if q["qtype"] == 1]
    big = [q for q in all_q if q["qtype"] == 2]
    with_ans = [q for q in all_q if q.get("answer")]
    tagged = [q for q in all_q if q["knowledge"]]

    print(f"\n  单选 {len(sel)} 道，综合应用题 {len(big)} 道，合计 {len(all_q)}")
    print(f"  已有答案：{len(with_ans)} 道（{len(with_ans) / max(len(sel), 1) * 100:.0f}% 的选择题）")
    print(f"  已打知识点标签：{len(tagged)} 道（{len(tagged) / max(len(all_q), 1) * 100:.0f}%）")
    print(f"    其中人工复核：{reviewed} 道，规则预标注：{len(tagged) - reviewed} 道")
    opt_ok = [q for q in sel if len(q["options"]) == 4]
    print(f"  四个选项完整：{len(opt_ok)}/{len(sel)}")

    if args.report:
        print("\n各年质量校验：")
        print("  年份   选项完整   答案   总分   备注")
        for y in years:
            ys = [q for q in sel if q["year"] == y]
            ok = [q for q in ys if len(q["options"]) == 4]
            ans = [q for q in ys if q.get("answer")]
            total = sum(q["score"] for q in all_q if q["year"] == y)
            note = "" if total == 150 else "总分异常，需对照原卷核实分值"
            print(f"  {y}   {len(ok)}/{len(ys)}     {len(ans)}/40   {total:.0f}   {note}")
        return

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(all_q, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    write_sql(all_q)
    print(f"\n  已写出 {OUT_JSON.relative_to(ROOT)}")
    print(f"  已写出 {OUT_SQL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
