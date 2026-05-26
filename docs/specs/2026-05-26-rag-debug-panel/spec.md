# Spec: RAG Debug 面板

**日期：** 2026-05-26
**状态：** Draft
**关联流程图：** `flow.html`

---

## 目标

在聊天界面每条 AI 回复下方，展示该次问答的完整 RAG 执行 Trace，帮助开发者快速定位检索失败或性能瓶颈，无需翻后端日志。

---

## 核心流程

1. URL 带 `?debug=1` 或 localStorage 设置 `rag_debug=true` 时进入开发者模式
2. 前端发起问答请求时，在请求体加 `debug: true`
3. 后端逐步 `yield` debug 事件（`query_rewrite` → `embedding` → `retrieval` → `rerank` → `citations` / `terminal_error`）
4. 前端实时收到每个 debug 事件，追加到该条消息的 trace 列表
5. 消息气泡下方渲染折叠面板，默认展开，每行对应一个阶段

---

## 技术方案

- **采用方案：** 方案 A — 仅开发者模式展示
- **关键决策理由：** 零额外生产开销；普通用户界面不受影响；URL 开关方便面试演示
- **依赖的现有模块：**
  - `frontend/src/lib/stream.ts` — 扩展 `SseEvent` 类型，新增 `debug` 事件
  - `frontend/src/services/qa.ts` — `askConversation` 加 `debug?: boolean` 参数
  - `frontend/src/features/chat/components/chat-page.tsx` — 传递 debug 标志、处理 debug 事件
  - `backend/app/services/qa_service.py` — 已完成，无需修改

---

## API 变更

后端接口已支持 `debug` 参数，无新增接口。

请求体新增字段：
```json
{
  "question": "xxx",
  "debug": true
}
```

后端 debug 事件格式（现有）：
```json
{ "type": "debug", "stage": "query_rewrite", "data": { "retrieval_query": "...", "rewrite_duration_ms": 85, "rewritten": true } }
{ "type": "debug", "stage": "retrieval",     "data": { "vector_candidates_count": 10, "fts_candidates_count": 0, "merged_candidates_count": 10 } }
{ "type": "debug", "stage": "rerank",        "data": { "rerank_candidates_count": 3 } }
{ "type": "debug", "stage": "citations",     "data": { "citations_count": 2 } }
{ "type": "debug", "stage": "terminal_error","data": { "error_code": "missing_citations" } }
```

---

## 数据模型

无数据库变更。

Debug trace 仅存在前端内存（React state），不持久化。

---

## 前端改动清单

### 1. `stream.ts` — 扩展事件类型

```typescript
| { type: "debug"; stage: string; data: Record<string, unknown> }
```

`parseEvent` 里增加 `debug` 分支，不再抛 `StreamFormatError`。

### 2. `services/qa.ts` — 请求加 debug 参数

`askConversation` 增加 `debug?: boolean`，透传到请求体。

### 3. `chat-page.tsx` — 开关检测 + 事件处理

- 读取 `?debug=1` 或 `localStorage.getItem("rag_debug")`
- 收到 `debug` 事件时追加到对应消息的 `traceEvents` 列表

### 4. 新组件 `rag-trace-panel.tsx`

```
RagTracePanel
├── 折叠/展开按钮（默认展开）
└── 每行：StageRow
    ├── 状态图标（✅ 成功 / ❌ 失败 / ⏳ 进行中）
    ├── 阶段名称（中文）
    ├── 耗时 badge（ms）
    └── 关键数据（候选数、改写前后对比等）
```

### 5. `message-bubble.tsx` — 挂载面板

在 assistant 消息气泡下方，debug 模式下渲染 `<RagTracePanel events={traceEvents} />`。

---

## 阶段展示规则

| stage | 中文名 | 展示的关键字段 |
|---|---|---|
| `query_rewrite` | Query 改写 | 改写前 / 改写后 / 耗时 |
| `embedding` | 向量化 | 耗时 |
| `retrieval` | 检索 | 向量召回 / FTS 召回 / 合并 |
| `rerank` | 重排序 | 保留候选数 / 耗时 |
| `citations` | 引用提取 | 引用数 |
| `terminal_error` | 终止（错误） | error_code（红色高亮） |

---

## 边界 & 不做的事

- ✅ 做：URL `?debug=1` 开启；折叠面板实时更新；终止阶段红色高亮
- ✅ 做：debug 模式下 `askConversation` 才传 `debug: true`，生产默认不传
- ❌ 不做：持久化 trace 到数据库
- ❌ 不做：普通用户可见的入口
- ❌ 不做：后端修改（已完备）

---

## TODO 清单

- [ ] `stream.ts` 扩展 `SseEvent` 新增 `debug` 类型
- [ ] `qa.ts` `askConversation` 加 `debug` 参数
- [ ] `chat-page.tsx` 读取 debug 开关，处理 debug 事件追加到消息 state
- [ ] 新建 `rag-trace-panel.tsx` 组件
- [ ] `message-bubble.tsx` 挂载面板
- [ ] 本地开启 `?debug=1` 手动验证各阶段是否正确展示
- [ ] 验证非 debug 模式下面板不出现、不影响正常问答

---

## 测试计划

- **正常路径：** `?debug=1` 下发起成功问答，面板显示全部阶段均为 ✅，最后一行引用数正确
- **错误路径：** rerank 后无候选，面板显示到 `terminal_error` 行，红色高亮 `missing_citations`
- **非 debug 模式：** 正常 URL 下面板不渲染，`debug` 字段不出现在请求体
- **流式实时性：** 面板各行随 SSE 事件逐步出现，不是等全部完成后一次性渲染
