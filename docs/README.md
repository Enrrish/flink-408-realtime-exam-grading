# docs — 设计文档

按"架构设计"与"数据"两类组织。文件名用英文以保证在 GitHub 上路径可读，内容为中文。

## 索引

| 文档 | 说明 | 适用章节 |
|---|---|---|
| [architecture/data-flow.html](architecture/data-flow.html) | 系统总体数据流程图，含双通道聚合与结果回推链路。A4 横向，浏览器打开后可直接打印或导出 PDF | 论文"系统设计"、答辩投屏 |
| [architecture/page-routes.md](architecture/page-routes.md) | 13 条路由的完整表格、四套布局策略、前后端接口与 WebSocket 消息信封约定 | 论文"系统设计"、前端开发 |
| [data/data-source.md](data/data-source.md) | 题库来源、解析与补录流程、答案双通道校验、知识点复核方法、遗留问题 | 论文"数据准备"、实验设置 |

## 约定

- 新增设计文档放在 `architecture/`，数据相关放 `data/`，图片资源放 `assets/`。
- 文档内引用仓库路径一律使用**仓库根目录为基准的相对路径**（如 `tools/parse_408.py`），便于在 GitHub 与本地编辑器中同时正确跳转。
- 文档头部注明版本与最后更新日期。
