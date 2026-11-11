# flink-jobs — 流处理作业

Flink 1.20 LTS / Java 11 / Maven。承担系统全部实时计算：清洗、判分、聚合、统计、异常检测。

> **当前状态：待实现（M4）**。此目录先约定作业划分与工程约定。

## 作业划分

单个 Job 内用侧输出流（Side Output）分叉，不拆成多个 Job——避免多次读取 Kafka 与状态重复维护。

| 算子 | 输入 | 输出 | 职责 |
|---|---|---|---|
| 清洗 | `exam.answer` | 清洗后事件流 | 去重、字段校验、乱序容错；脏数据走侧输出到死信 topic |
| 客观题判分 | 清洗后事件流 | 单题判分结果 | 与标准答案维表比对，产出对错与得分 |
| 累积型聚合 | 判分结果 | 成绩宽表 | 总分、均分、排名。**upsert 覆盖当前值** |
| 速率型聚合 | 清洗后事件流 | 窗口指标 | 在线人数、交卷速率、单位时间答题量；滑动窗口 |
| 知识点正确率 | 判分结果 + 知识点标签 | 知识点统计 | 按 `knowledgePointId` 聚合正确率，主/次考点按权重计入 |
| 异常检测 | 清洗后事件流 | 告警流 | `ProcessFunction + ValueState` 规则引擎 |

## 工程约定

**幂等（最重要）**

结果写入一律按主键 upsert 覆盖当前值，**禁止 `score += x` 这类增量累加**。checkpoint 恢复或作业重启会重放数据，增量写法会让总分翻倍。论文中表述为"至少一次语义 + 幂等写 = 效果上精确一次"。

**维表**

标准答案放 Redis，在 `RichFlatMapFunction.open()` 中全量加载进 Map + 定时刷新。一场考试几十到几百条，不需要 Flink CDC 维表 join。数据流向单向：MySQL → 预热 → Redis → Flink。

**异常检测**

用 `ValueState` 记录切屏次数、上次答题时间、连续快答次数即可，**不引入 CEP**——API 难调试，且规则用 YAML 配置更易扩展。

**时间语义**

先用 ProcessingTime 跑通链路，论文中讨论 EventTime + Watermark 作为改进方向。全量上 EventTime 会多耗约一周。

## 计划包结构

```
flink-jobs/
├── pom.xml
└── src/main/
    ├── java/.../
    │   ├── job/          # 作业入口与拓扑拼装
    │   ├── operator/     # 判分、聚合、异常检测算子
    │   ├── model/        # 事件与结果 POJO
    │   ├── sink/         # 幂等 upsert sink、Kafka 结果回推
    │   └── util/         # 维表加载、配置解析
    └── resources/
        ├── application.yml   # Kafka / MySQL / Redis 连接
        └── rules/            # 异常检测规则（YAML 可配置）
```

## 本地调试

在 IDEA 中以 MiniCluster 运行 `job/` 下的入口类，无需部署集群。答辩演示前单独启动一次 `deploy/` 中的 Flink 容器提交作业，用于证明分布式部署能力。
