# Spec 文档约定

本目录用于存放按 feature 拆分的需求文档。

## 目录结构

- `frontend/*.md`：前端主 spec
- `backend/*.md`：后端主 spec
- `backend/addenda/*.md`：后端增量 / 归档 spec
- `devops/*.md`：部署运维 spec（预留）
- `assets/*.png`：兼容性更好的位图预览

示例：

- `backend/knowledge-ingestion.md`
- `frontend/frontend-workspace.md`
- `assets/knowledge-ingestion-flow.png`

## 维护规则

1. spec 正文中直接引用 PNG 流程图，保证在 Markdown 中可直接预览。
2. 流程图图片统一放在 `spec/assets/` 下。
3. 每次修改 spec 的主流程、异常分支或状态流转时，spec 中的图片也必须同步更新。

## 命名规则

- spec 文件：`{feature}.md`
- PNG 文件：`assets/{feature}-flow.png`

## 当前约定

- PNG：作为 spec 内直接展示的默认流程图格式。

## 当前主 spec（已整合）

- `backend/knowledge-ingestion.md`：知识库导入链路
- `backend/qa.md`：问答后端主链路
- `backend/README.md`：后端主 spec 与增量 spec 索引
- `frontend/frontend-workspace.md`：前端工作台总览（按当前实现对齐）
- `frontend/chat-streaming-interaction.md`：聊天流式交互状态机（按当前实现对齐）
- `frontend/chat-ui-polish.md`：聊天 UI/UX（按当前实现对齐）
- `frontend/chat-knowledge-scope.md`：Chat 问题驱动知识库路由（Draft）
- `backend/addenda/conversation-knowledge-scope.md`：问题驱动会话级知识库 scope（Draft）

## 分层归类（前端 / 后端 / 部署运维）

| 分类 | 文件 |
| --- | --- |
| 前端（Frontend） | `frontend/frontend-workspace.md`, `frontend/chat-streaming-interaction.md`, `frontend/chat-ui-polish.md`, `frontend/chat-knowledge-scope.md` |
| 后端（Backend） | `backend/knowledge-ingestion.md`, `backend/qa.md`, `backend/addenda/*.md`, `backend/addenda/conversation-knowledge-scope.md` |
| 部署运维（DevOps） | `devops/*.md`（预留） |
