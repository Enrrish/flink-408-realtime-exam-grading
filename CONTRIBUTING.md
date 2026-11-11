# 贡献指南

本仓库为本科毕业设计工程实现，以单人开发为主。此文档用于统一自己的提交习惯，同时便于评阅时理解工程规范。

---

## 分支策略

| 分支 | 用途 |
|---|---|
| `main` | 可运行、可演示的稳定版本，每次提交都应能编译通过 |
| `feat/<scope>` | 新功能，如 `feat/flink-grading` |
| `fix/<scope>` | 缺陷修复，如 `fix/websocket-reconnect` |
| `docs/<scope>` | 纯文档或数据处理脚本变更 |

合入 `main` 前先在本地跑通校验（见下节）。

---

## 提交规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)，首行格式：

```
<type>(<scope>): <subject>
```

**type** 取值：

| type | 含义 |
|---|---|
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档 |
| `data` | 数据处理脚本、题库、种子数据 |
| `refactor` | 重构（不改变行为） |
| `perf` | 性能优化 |
| `test` | 测试 |
| `build` | 构建脚本、依赖 |
| `ci` | CI 配置 |
| `chore` | 杂项 |

**scope** 取值：`flink`、`server`、`web`、`sql`、`data`、`deploy`、`docs`。

示例：

```
feat(flink): 客观题判分算子接入标准答案维表
fix(data): 修正 2022 年答案表按列排布的错位问题
docs(architecture): 补充结果回推链路的时序说明
```

---

## 本地校验

提交前至少完成与改动相关的检查。

### 数据与脚本（`tools/`）

```bash
pip install -r tools/requirements.txt

python tools/fetch_answers.py       # 答案生成与交叉校验（需要 data/raw 原始 PDF）
python tools/parse_408.py --report  # 解析质量报告：题数、选项完整性、总分
```

质量报告应满足：5 套卷各 47 题、选项 200/200 完整、每套总分 150。任一项不符说明解析回归了。

### SQL

```bash
mysql -u root -p < sql/01_question_bank.sql
mysql -u root -p < sql/02_question_seed.sql
```

建表脚本须可重复执行且不动已有数据；种子脚本是"清空重建"语义，执行后题目数为 235、知识点关联 287 条、小问 104 条。改动 `tools/parse_408.py` 后必须重跑这两个脚本确认可执行。

### 服务端（`exam-server/`）

```bash
cd exam-server && mvn -q verify
```

### 前端（`exam-web/`）

```bash
cd exam-web && npm ci && npm run lint && npm run build
```

---

## 代码约定

**通用**

- 源码文件 UTF-8、LF 换行（见 `.editorconfig`），提交前确保文件末尾有换行。
- 不在仓库中提交密钥、口令、个人路径；本地配置放 `.env`（已在 `.gitignore`）。

**Python（`tools/`）**

- 仅依赖 `pypdf`，不引入重型 OCR/PDF 库，保证他人可一键复现。
- 解析脚本必须输出可核对的质量指标（题数、完整性、总分），不能静默产出脏数据。
- 路径一律基于 `Path(__file__).resolve().parent.parent` 推导，禁止硬编码绝对路径。

**SQL（`sql/`）**

- 建表脚本幂等（`CREATE TABLE IF NOT EXISTS`），种子脚本可重复执行。
- 表名小写下划线，主键统一 `id`，时间字段统一 `created_at` / `updated_at`。
- 聚合结果表必须定义唯一键，供 Flink 侧 upsert。

**Flink（`flink-jobs/`）**

- 结果写入一律幂等：按主键 upsert 覆盖当前值，禁止 `score += x` 这类增量累加。
- 维表加载放 `RichFlatMapFunction.open()`，带定时刷新，不引入 Flink CDC 维表 join。
- 异常检测用 `ProcessFunction + ValueState`，不引入 CEP。

**前端（`exam-web/`）**

- 大屏刷新必须做 200ms 合并节流，避免交卷洪峰压垮渲染。
- 角色由后端返回，前端不做角色自选。

---

## 数据变更

修改 `data/seed/` 下的种子数据时，请在提交信息中说明依据：

```
data(seed): 补录 2026 年第 12 题答案，来源答案 PDF 第 1 页
```

若变更影响题库统计口径（题数、知识点分布），需同步更新 [数据源说明](docs/data/data-source.md) 中的指标表。
