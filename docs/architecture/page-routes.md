# 页面结构与路由规划

> 基于 Flink 的 408 在线模考实时阅卷数据流处理与大屏监控
> 版本：v1（2026-11-11）　对应系统数据流程：答题端 → Spring Boot → Kafka → Flink → MySQL/Redis → exam.result → WebSocket → 大屏

---

## 一、总体原则

1. **角色决定入口，不由用户选择**：`role` 来自账号表，登录后后端返回，前端据此重定向，路由守卫二次校验。
2. **教师端一切以"考试"为上下文**：所有业务页 URL 内含 `:examId`，避免"当前在看哪场考试"的隐式状态。
3. **三套布局，路由 meta 控制**：`AuthLayout` / `ExamLayout`（全屏、无导航、拦截后退）/ `AdminLayout`（侧边栏）。
4. **大屏与工作台分离**：大屏是投放物（只读、无导航），工作台是操作界面（可写、有导航）。

---

## 二、路由表

### 学生端（role = student）

| 路由 | 页面 | 布局 | 优先级 | 说明 |
|---|---|---|---|---|
| `/login` | 登录 | Auth | P0 | 账号密码登录，后端返回 role 与 token，前端按角色重定向；不做角色自选 |
| `/exam/list` | 考试列表 | Admin | P0 | 待考 / 进行中 / 已结束三态；进行中支持"继续考试" |
| `/exam/:examId/intro` | 考前须知 | Exam | P1 | 考试时长、题量、交卷规则；"开始考试"按钮启动计时器；进行中重入走续考逻辑 |
| `/exam/:examId/answer` | 答题页 | Exam | P0 | 核心页面。答题卡锚点跳转、倒计时、自动暂存（localStorage + 定时上报）、交卷二次确认、切屏计数上报 |
| `/exam/:examId/result` | 交卷结果 | Admin | P0 | 客观题得分、总分明细、**知识点薄弱项 Top3**（消费 Flink 聚合结果）、主观题待复核提示 |

### 教师端（role = teacher）

| 路由 | 页面 | 布局 | 优先级 | 说明 |
|---|---|---|---|---|
| `/teacher/exams` | 考试管理 | Admin | P1 | 考试列表、从题库随机组卷、发布、绑定标准答案（写入 Redis 维表） |
| `/teacher/exams/:examId/monitor` | 实时监控工作台 | Admin | P0 | 卡片式：在线人数、交卷进度、均分、知识点正确率、告警摘要；每张卡片可点进明细 |
| `/teacher/exams/:examId/review` | 人工复核队列 | Admin | P0 | **按题分组**（同一道题的所有答卷一起看），支持筛选低置信度、批量给分 |
| `/teacher/exams/:examId/review?reviewId=` | 复核详情 | 弹窗 | P0 | 不单独开页，用 query 存状态，支持刷新保持与深链接 |
| `/teacher/exams/:examId/alerts` | 异常告警 | Admin | P1 | 规则命中列表：考生、规则名、证据（切屏次数 / 答题间隔）、处置动作（标记 / 警告 / 忽略） |
| `/teacher/exams/:examId/analysis` | 考后分析 | Admin | P2 | 分数分布、知识点正确率排名、题目难度系数；支持导出 |
| `/teacher/questions` | 题库 | Admin | P2 | 只读浏览，按知识点 / 题型筛选 |
| `/screen/:examId` | 监控大屏 | Screen | P0 | 1920×1080、auto scale、无导航、只读、WebSocket 增量刷新 |

### 公共

| 路由 | 说明 |
|---|---|
| `/` | 按 role 重定向到 `/exam/list` 或 `/teacher/exams` |
| `/404` `/403` | 兜底页 |
| `*` | 重定向 `/404` |

---

## 三、关键跳转链路

必须打通的两条，否则系统观感会停留在"几张独立报表"：

1. **告警闭环链**
   `/screen/:examId` 或 `/alerts` 中的某条记录 → 点击 → 学生答卷详情（抽屉）→ 该生主观题 → `/review?reviewId=xxx`
2. **复核回流链**
   `/review` 复核完成 → 更新成绩 → 通过 WebSocket 或手动刷新，`/monitor` 上的均分与复核进度同步变化

---

## 四、布局与交互约定

### ExamLayout（答题页）
- 全屏铺满，隐藏所有导航
- 拦截 `beforeunload` 与浏览器后退，二次确认
- 倒计时以服务端时间为准（前端时间可被修改），定时校时
- 断线重连：WebSocket / 轮询恢复后从草稿继续

### AdminLayout（后台）
- 左侧导航：考试管理、题库
- 顶部：当前考试选择器（进入 `:examId` 上下文后固定显示考试名与状态）
- 面包屑：`考试管理 / 2026 秋季模考一 / 人工复核`

### ScreenLayout（大屏）
- `transform: scale()` 按 1920×1080 等比缩放，禁止滚动
- 三区布局：顶部标题与全局指标、中部左（交卷进度 / 分数分布）中（知识点热力）右（异常告警滚动）、底部状态栏
- 数据刷新：WebSocket 增量 + 前端 200ms 合并节流，避免交卷洪峰把渲染打爆

---

## 五、前端状态与接口约定

| 数据 | 来源 | 刷新方式 |
|---|---|---|
| 考生作答草稿 | localStorage + POST 定时上报 | 每 10s 或每题变更 |
| 实时监控指标 | `/api/monitor/{examId}` 首屏快照 | WebSocket `exam.result` 推送增量 |
| 复核队列 | `/api/review/list?examId=&questionId=` | 分页拉取 |
| 告警列表 | `/api/alerts?examId=` | WebSocket 推送新告警 + 手动刷新 |
| 知识点分析 | `/api/analysis/knowledge?examId=&studentId=` | 页面加载 |

WebSocket 消息体建议统一信封，前端按 `type` 分发：

```json
{ "type": "score_update | alert | progress | review_done", "examId": 1, "payload": {} }
```

---

## 六、与原规划的差异汇总

| 原规划 | 调整 | 原因 |
|---|---|---|
| `/login` 角色选择 | 角色由账号决定 | 前端选角色等于把权限交给浏览器 |
| `/teacher/dashboard` | 拆为 `/teacher/exams/:examId/monitor` + `/screen/:examId` | 工作台与大屏是两种信息密度，混用会互相拖累 |
| `/teacher/review/:id` 路径 | 改 `?reviewId=` | 弹窗状态存 URL，刷新不丢、可深链 |
| 无 | 新增 `/exam/:examId/intro` | 缺考试须知、开考确认、续考入口 |
| 无 | 新增 `/teacher/exams` 考试管理 | 标准答案维表的数据来源缺失，演示链路断在第一环 |
| 无 | 新增 `/teacher/exams/:examId/alerts` | 异常检测无处置出口，功能不闭环 |
| `result` 仅总分 | 增加知识点薄弱项 | Flink 算出的知识点正确率需要被学生消费 |
