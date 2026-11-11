# exam-web — Vue 3 前端

Vue 3 + Vite + Pinia + Element Plus + `@kjgl77/datav-vue3`。含三端：学生答题端、教师工作台、监控大屏。

> **当前状态：待实现（M5）**。此目录先约定布局与路由，完整路由表见 [页面结构与路由规划](../docs/architecture/page-routes.md)。

## 四套布局

| 布局 | 适用 | 特征 |
|---|---|---|
| `AuthLayout` | `/login` | 居中卡片，无导航 |
| `ExamLayout` | `/exam/*` | 全屏、无导航、**拦截后退与刷新**、倒计时以服务端时间为准 |
| `AdminLayout` | `/teacher/*`、`/exam/list` | 侧边栏 + 顶栏，可操作 |
| `ScreenLayout` | `/screen/:examId` | 1920×1080 等比缩放（`transform: scale`）、无导航、只读 |

用路由 `meta.layout` 控制，不做条件渲染——避免答题页误触返回导致丢卷。

## 计划目录

```
exam-web/
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── layouts/      # Auth / Exam / Admin / Screen
    ├── views/
    │   ├── auth/     # 登录
    │   ├── student/  # 考试列表、须知、答题、结果
    │   ├── teacher/  # 考试管理、监控、复核、告警、分析、题库
    │   └── screen/   # 监控大屏
    ├── components/   # 答题卡、倒计时、图表卡片、告警列表
    ├── composables/  # useWebSocket、useCountdown、useThrottle
    ├── stores/       # Pinia：auth、exam、realtime
    ├── api/          # 按模块拆分的请求封装
    └── router/       # 路由表 + 守卫
```

## 必须遵守的三条

1. **DataV 用社区 Vue3 版**：`npm i @kjgl77/datav-vue3`，官方包只支持 Vue 2。不要用 patch-package 打补丁，没有时间维护。
2. **大屏刷新做 200ms 合并节流**：交卷洪峰时 WebSocket 消息密集，不节流会把渲染压垮。在 `composables/useThrottle` 统一处理。
3. **角色由后端返回**：登录后按 `role` 重定向，路由守卫二次校验。前端不做角色自选，否则等于把权限判断交给浏览器。

## 关键交互

- **答题页**：答题卡锚点跳转、倒计时、自动暂存（localStorage + 定时上报）、交卷二次确认、切屏计数上报。
- **结果页**：客观题得分 + 总分明细 + **知识点薄弱项 Top3**（消费 Flink 的知识点聚合结果，这是学情反馈的落点）。
- **复核页**：按题分组（同一道题的所有答卷一起看），支持筛选低置信度、批量给分。详情用 `?reviewId=` query 参数，支持刷新保持与深链接。
- **大屏**：从异常告警可下钻到学生答卷详情，再进入人工复核——这条链路是系统"可用"与"几张独立报表"的分界。

## 开发

```bash
npm install
npm run dev      # 默认 5173，代理 /api 与 /ws 到 exam-server
npm run build
```
