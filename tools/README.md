# tools — 题库数据加工

把 408 真题 PDF 转成可入库的结构化题库。三个脚本构成一条单向管道：

```
data/raw/408-exam-paper/          (原始 PDF，不入库)
        │
        ├─ fetch_answers.py ──► data/seed/answers.csv
        │
        ├─ parse_408.py ──────► data/generated/question_bank.json
        │                       sql/02_question_seed.sql
        │      ▲
        │      └── data/seed/kp_override.csv  (人工复核结果)
        │
        └─ review_kp.py ──────► data/generated/_kp_review.txt  (复核清单)
```

## 环境

```bash
pip install -r requirements.txt
```

仅依赖 `pypdf`。刻意不引入 OCR / 重型 PDF 库，保证他人 clone 后可一键复现。

## 脚本

### `fetch_answers.py` — 生成答案

```bash
python tools/fetch_answers.py
```

两条通道，每条答案带 `source` 标记（`text` / `visual`）以便追溯：

| 年份 | 形态 | 方式 |
|---|---|---|
| 2022 | 文本层，首页 8 列 × 5 行答案表 + 逐题解析 | 逐题抽取，再用 `extraction_mode="layout"` 还原答案表**交叉校验** |
| 2023 | 文本层（AES 空口令加密） | 逐题抽取 `N.【参考答案】X` |
| 2024–2026 | 带水印截图，无文本层 | 读图转录（`VISUAL` 字面量，注明页码） |

**2022 年的坑**：答案表字母按**列**排布（第 c 列对应题号 c+1、c+9、c+17、c+25、c+33）。普通抽取得到的 `DAAAB BCDBD…` 按题号直读会 40 题全错。脚本已固化为 `from_table()`，与逐题解析逐题比对，冲突直接抛错。

### `parse_408.py` — 解析题库

```bash
python tools/parse_408.py                    # 解析 SCOPE_YEARS 内的年份
python tools/parse_408.py --years 2023 2024  # 指定年份
python tools/parse_408.py --report           # 只输出质量报告，不写文件
```

处理流程：提取文本层 → 清洗页眉页脚 → 按题号切块 → 剥离选项 → 拆小问 → 解析分值 → 知识点规则预标注。

**质量基线**（改动后必须保持）：

| 指标 | 基线值 |
|---|---|
| 每年题数 | 47 / 47 |
| 选项完整 | 200 / 200 |
| 单套总分 | 150 |
| 答案覆盖 | 200 / 200 |
| 标签覆盖 | 235 / 235 |

任一指标下降即说明解析出现回归。

### `review_kp.py` — 导出复核清单

```bash
python tools/review_kp.py         # 需人看的题（未打标、双标、可疑单标）
python tools/review_kp.py --all   # 全部题目
```

输出 `data/generated/_kp_review.txt`，每题一行标签与题干摘要。人工核对后把错判写入 `data/seed/kp_override.csv`（`year,no,code,reason`），重跑 `parse_408.py` 即生效。

## 知识点规则的四类系统性误判

规则预标注只能覆盖大概，以下问题已在代码里修正，改动规则时不要回退：

1. **单字规则**：`图` 会命中"如图 1 所示" → 限定为图论专有名词（邻接/顶点/拓扑/AOE）
2. **跨科归属**：`页表` 属操作系统，不能出现在组成原理的 Cache 规则里
3. **顺序冲突**：按"具体优先"排序——`B 树` 先于 `树`、`CPI` 先于 `指令`、`磁盘调度` 先于 `进程调度`
4. **选项污染**：题干优先，题干无命中才看选项；主标签为子节点时自动剔除父节点冗余标签

## 已知限制

- 35 道综合应用题的 104 个小问未填采分点（`rubric`），规则辅助打分暂不可用
- 24 道含插图的题未提取原图，仅标记 `has_figure`
- 源 PDF 经 OCR，存在少量形近字错误
