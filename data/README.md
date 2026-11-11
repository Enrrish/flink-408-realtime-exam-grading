# data — 数据集

按"来源可信度"分三层，**入库策略不同**：

| 目录 | 内容 | 是否入库 | 说明 |
|---|---|---|---|
| `raw/` | 原始真题 PDF（18 套试卷 + 18 套答案，120MB） | 否 | 从上游仓库克隆，体积大且版权受限 |
| `seed/` | `answers.csv`（200 条答案）、`kp_override.csv`（50 条知识点复核） | **是** | 人工补录与复核的成果，是本目录唯一"源数据" |
| `generated/` | `question_bank.json`（结构化题库）、`_kp_review.txt`（复核清单） | 否 | 由 `tools/` 脚本生成，可随时重建 |

## 获取原始数据

```bash
git clone --depth 1 https://github.com/neville-studio/408-exam-paper.git data/raw/408-exam-paper
```

若 Windows 下报 schannel 证书吊销错误，加环境变量：`GIT_SSL_NO_VERIFY=1 git clone ...`

## 重建生成物

```bash
pip install -r tools/requirements.txt
python tools/parse_408.py
```

即使不重建，`sql/02_question_seed.sql` 已提交，可直接导入数据库获得完整题库。

## seed 文件说明

**`answers.csv`** — 客观题答案，字段 `year,qno,answer,source`

`source` 列记录可信度来源：

- `text`：从答案 PDF 文本层程序化抽取，可复现（2022、2023）
- `visual`：答案 PDF 为纯图片，人工读图转录（2024、2025、2026）

**`kp_override.csv`** — 知识点人工复核结果，字段 `year,qno,codes,note`

`codes` 支持一道题覆盖多个知识点（双考点题），`note` 用一句话说明判定依据，便于回溯。这 50 条覆盖了规则预标注的系统性误判，重跑解析时优先生效。

## 版权

真题版权归教育部教育考试院所有，上游仓库声明仅用于学习交流、非商业用途。本项目将其作为**学术测试数据集**使用，不对外分发原始题干。详见 [数据源说明](../docs/data/data-source.md)。
