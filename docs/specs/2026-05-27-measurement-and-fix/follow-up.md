# Follow-up：B 堆背景修复（不进本次 spec）

本文档列出 review 中识别出、但**不进入** `2026-05-27-measurement-and-fix` spec 故事线的 5 项问题。spec ship 后单独开 PR 处理。

| ID | 来源 | 定位 | 问题摘要 | 严重度 | 处理建议 |
|---|---|---|---|---|---|
| **B1** | Claude review | `backend/app/services/qa_service.py:~2072, ~2090` | `_build_debug_event` 返回 None 时被 yield 到 SSE 流（缺 `if event:` 检查） | P1 | 直接修，~5 行改动；可顺手做一遍同模式审计 |
| **B2** | Claude review | `backend/app/core/config.py:72` | `REFRESH_TOKEN_COOKIE_PATH` 从 `/api/v1/auth/` 改为 `/`，refresh token 现在随所有请求发送 | INFO（安全） | 评估是否真的需要全局携带；若否改回 `/api/v1/auth/` |
| **B3** | Claude review | `backend/app/core/config.py:94` | `RAG_DEBUG_ENABLED: bool = True` 默认打开，生产环境会全量写入 trace + 用户提问 | INFO | 默认值改回 `False`，生产环境显式配置打开 |
| **B4** | Codex review | `frontend/src/features/chat/components/chat-page.tsx:132` | 本地 traceEvents 合并按 `msg.id` 查缓存，乐观助手消息 id 是 `${clientId}-assistant`，与后端落库 id 不匹配；导航或刷新后 Debug trace 丢失 | P2 | 按 assistant 消息顺序/clientId 映射，或在后端返回可关联的 client id |
| **B5** | Codex review | `frontend/src/features/chat/components/chat-page.tsx:273` | `askConversation` 新增 `location`、`debug` 参数，相关测试断言仍是旧签名，前端测试套件失败 | P2 | 同步更新测试断言，覆盖普通模式和 `?debug=1` 模式下的参数传递 |

---

## 处理建议

- **批量处理**：B1+B2+B3 可合一个后端 PR（都是配置/小逻辑收敛）
- **独立处理**：B4+B5 可合一个前端 PR（都是 chat-page 相关）
- **预计工时**：合计 ~0.5 天

## 关联

- 主 spec：[`spec.md`](./spec.md)
- 流程图：[`flow.html`](./flow.html)
