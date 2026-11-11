# exam-server — Spring Boot 服务端

Spring Boot 2.7 / JDK 11 / Maven。承担接入层与推送层，**不做业务计算**（计算全部在 Flink）。

> **当前状态：待实现（M3）**。此目录先约定模块划分与接口。

## 职责边界

| 做 | 不做 |
|---|---|
| REST 接入、参数校验、身份认证 | 判分、聚合、统计（交给 Flink） |
| 把作答事件生产到 Kafka | 直接写聚合结果表 |
| 消费 `exam.result` 并广播 WebSocket | 轮询数据库推大屏 |
| 题库与考试的 CRUD、组卷 | 维护标准答案副本（写入 Redis 供 Flink 读） |

## 模块划分

```
exam-server/
├── pom.xml
└── src/main/
    ├── java/.../
    │   ├── controller/   # REST 接口，按角色分组
    │   ├── service/      # 业务逻辑
    │   ├── producer/     # Kafka 生产者（作答、交卷事件）
    │   ├── consumer/     # exam.result 消费者
    │   ├── websocket/    # STOMP / 原生 WS 广播
    │   ├── repository/   # MyBatis-Plus
    │   ├── model/        # 实体与 DTO
    │   └── config/       # Kafka、Redis、WS、安全
    └── resources/
        ├── application.yml
        └── mapper/
```

## 接口约定（与前端路由一一对应）

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/auth/login` | 登录，返回 `role` 与 token，**角色由账号决定** |
| `GET` | `/api/student/exams` | 待考 / 进行中 / 已结束 |
| `GET` | `/api/student/exams/{id}/paper` | 拉取试卷（不含答案） |
| `POST` | `/api/student/exams/{id}/answer` | 上报单题作答事件 → Kafka |
| `POST` | `/api/student/exams/{id}/submit` | 交卷 |
| `GET` | `/api/student/exams/{id}/result` | 成绩 + 知识点薄弱项 |
| `GET` | `/api/teacher/exams` | 考试列表 |
| `POST` | `/api/teacher/exams` | 创建考试（从题库随机组卷） |
| `POST` | `/api/teacher/exams/{id}/publish` | 发布，标准答案写入 Redis 维表 |
| `GET` | `/api/teacher/exams/{id}/monitor` | 工作台聚合卡片数据 |
| `GET` | `/api/teacher/exams/{id}/review` | 复核队列（按题分组） |
| `POST` | `/api/teacher/review/{id}/score` | 提交人工评分 |
| `GET` | `/api/teacher/exams/{id}/alerts` | 异常告警列表 |
| `POST` | `/api/teacher/alerts/{id}/handle` | 处置（标记 / 警告 / 忽略） |
| `GET` | `/api/teacher/exams/{id}/analysis` | 考后分析 |

## WebSocket

- 端点 `/ws/exam/{examId}`，按考试分房间。
- 服务端消费 `exam.result` 后**立即广播**，不做定时轮询。
- 消息信封统一含 `type`（如 `SCORE_UPDATE` / `ALERT` / `ONLINE_COUNT`）、`examId`、`payload`、`timestamp`。
- 断线重连后由前端重拉一次快照接口补齐状态，不依赖消息重放。

## 关键实现点

- **Kafka 分区键用 `examId`**：保证同一场考试的作答事件落到同一分区、场内有序。
- **交卷洪峰**：`POST /answer` 接口只做校验与投递，不做同步落库，避免打满数据库连接池。
- **大屏数据来源分离**：实时增量走 WebSocket，首屏快照走 REST。
