# Spec: 意图细分与延迟路由机制 (Archived)

> 分类：后端（Backend）
> 状态：Merged into `qa.md`

## 1. 目标

优化 QA 系统的检索逻辑，使知识库的范围路由（Scope Routing）更加智能。支持“延迟路由”（在第一条检索意图的问题时才触发路由，而非固定在首问），并支持基于全局摘要（Summary）回答宏观问题，避免无切片时直接报错，提升“大字典”全量体验。

---

## 2. 核心流程

1. **细分意图识别**：当用户提问时，大模型将意图分类为 `GENERAL`（闲聊）、`MACRO_RETRIEVAL`（宏观提问/全局摘要）或 `MICRO_RETRIEVAL`（微观/切片细节）。
2. **延迟锁定 Scope**：如果当前会话尚未绑定任何知识库（Scope 为空），且意图被判定为 `MACRO` 或 `MICRO` 检索时，系统自动执行范围路由并锁定 Top 3 知识库。
3. **宏观问答兜底**：如果意图为 `MACRO_RETRIEVAL`，或者虽然是 `MICRO_RETRIEVAL` 但检索结果为空：
   - 只要成功锁定了带有全局摘要的知识库，则利用大模型基于全局摘要进行回答。
   - 生成伪引用（基于知识库级别）以通过引用校验器（Citation Guard）。

---

## 3. 技术方案

- **采用方案**：扩展现有的 `qa_service.py` 和 `qa_repository.py`。
- **关键决策理由**：保持原有的大部分逻辑不动，仅增加判断分支：
  1. 修改 `_classify_intent` 的 Prompt。
  2. 新增 `add_scope_items_to_conversation` 方法，以便在提问中间追加记录。
  3. 优化 `_require_citations` 与 `_extract_citations`，增加知识库级别兜底。

---

## 4. API 设计

API 接口无需改变，原有的 `POST /api/v1/qa/conversations/{conv_id}/ask` 能够自然承载。
但在 SSE Citations 返回时，如果是基于全局摘要回答且无切片：

**响应 (Citations)：**
```json
{
  "type": "citations",
  "data": [
    {
      "index": 1,
      "chunk_id": "", 
      "knowledge_base_id": 123,
      "knowledge_base_name": "API 文档",
      "source_url": "https://...",
      "heading_path": "全局摘要",
      "snippet": "全局摘要: ..."
    }
  ]
}
```

---

## 5. 数据模型

不新增数据库表。需要复用现有的表：
- `conversation_knowledge_scope_items`
- `conversations`

---

## 6. 边界 & 不做的事

- ✅ 做：支持 `MACRO_RETRIEVAL`，并能针对无具体切片的请求返回宏观摘要回答。
- ✅ 做：支持“无痛”的延迟路由。
- ❌ 不做：暂不支持中途变更已锁定的 Scope（只能追加一次）。
