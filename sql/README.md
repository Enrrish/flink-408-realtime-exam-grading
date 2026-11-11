# sql — 建表与种子数据

MySQL 8.0 脚本，按编号顺序执行。

| 文件 | 内容 | 是否入库 |
|---|---|---|
| `01_question_bank.sql` | 建库建表：知识点树、题目、题目-知识点关联、小问、试卷、组卷；32 个考纲知识点；5 道样例题 | 手工维护 |
| `02_question_seed.sql` | 5 套真题的种子数据（235 题 + 287 条知识点关联 + 104 个小问），由 `tools/parse_408.py` 生成 | 生成物，已提交以便他人免解析直接导入 |

## 执行

```bash
mysql -u root -p < 01_question_bank.sql
mysql -u root -p < 02_question_seed.sql
```

**执行语义不同，务必区分**：

| 脚本 | 语义 | 可否重复执行 |
|---|---|---|
| `01_question_bank.sql` | 建库建表，`CREATE TABLE IF NOT EXISTS` | 可重复，不改动已有数据 |
| `02_question_seed.sql` | **先 `DELETE` 三张表再全量 `INSERT`** | 可重复，但每次都会清空题目数据 |

`02` 是"题库重建"脚本，仅用于初始化或重新解析题库后刷新。**已发布考试期间不要执行**：`exam_question` 按题目 id 引用题目，重建后旧 id 可能指向不同题目。

日常新增题目应另写增量脚本，不要改这个生成物。

> 表之间未建立数据库外键约束。作答与聚合表属高频写入场景，外键检查会拖慢写入，引用完整性由应用层与 Flink 侧保证。

## 表关系

```
knowledge_point (三级树，自引用 parent_id)
      ▲
      │ question_knowledge (weight 区分主/次考点)
      │
   question ──1:N──> question_sub   (综合应用题的小问，独立给分)
      ▲
      │ exam_question (score 存快照，题库改分不影响已发布试卷)
      │
    exam
```

## 设计要点

- **知识点用关联表而非逗号分隔字符串**：Flink 侧要 `keyBy(knowledgePointId)` 聚合，逗号串既不能 JOIN 也不能建索引。`weight` 让一道题可横跨两个知识点（主考点 1.0、次考点 0.5），比"一刀切算两次"更准。
- **选项存 JSON 字段**：选择题固定 4 项，建 `question_option` 表会让组卷查询变成 4~5 表 JOIN。
- **`exam_question.score` 存快照**：题库调整分值不能影响已发布的试卷。
- **`question_sub.rubric` 存 JSON 采分点**：这是"规则辅助打分"的输入，按采分点匹配关键词给建议分，低于阈值转人工。**当前 104 个小问的 rubric 为空，待补。**

## 后续

M2 阶段将新增 `03_answer_flow.sql`：作答事件表、成绩聚合表、知识点统计表、异常记录表——即 Flink Sink 的落地目标。聚合表必须带唯一键以支持幂等 upsert。
