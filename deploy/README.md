# deploy — 部署编排

基础设施一键启动：Kafka、MySQL、Redis、Flink，以及容器初始化 SQL 挂载。

> **当前状态：待实现（M2）**。此目录先占位并约定端口与初始化方式，避免后期各模块各写一套。

## 计划组件

| 组件 | 镜像 | 端口 | 用途 |
|---|---|---|---|
| MySQL | `mysql:8.0` | 3306 | 题库、作答明细、聚合结果 |
| Redis | `redis:7-alpine` | 6379 | 标准答案维表、热数据 |
| Kafka | `bitnami/kafka:3.x` | 9092 | `exam.answer` 作答事件、`exam.result` 结果回推 |
| Kafka UI | `provectuslabs/kafka-ui` | 8080 | 调试用，查看 topic 与消费进度 |
| Flink | `flink:1.20-scala_2.12` | 8081 | 作业提交与 Web UI（答辩演示"分布式部署"） |

## 计划目录

```
deploy/
├── docker-compose.yml
├── .env.example          # 端口、密码等变量，实际 .env 不入库
└── mysql/init/           # 容器首次启动自动执行
    ├── 01_question_bank.sql   # ← 由 sql/01_question_bank.sql 同步
    └── 02_question_seed.sql   # ← 由 sql/02_question_seed.sql 同步
```

## 约定

- **端口可覆盖**：全部走 `.env`，避免与本机已装服务冲突。
- **初始化脚本来源唯一**：`mysql/init/` 下的文件从 `sql/` 复制，不单独维护，避免两份 schema 漂移。
- **本地开发优先**：日常在 IDEA 里跑 MiniCluster 调试 Flink，`docker compose` 只用于联调与答辩演示。Windows 上不折腾 standalone 集群。
- **Topic 初始化**：`exam.answer` 按 `examId` 分区以保证同一场考试内有序；该配置由容器启动脚本创建，不依赖手工命令。
