# Plan: RAG Debug 面板

**日期：** 2026-05-26
**关联 Spec：** `docs/specs/2026-05-26-rag-debug-panel/spec.md`
**状态：** Ready to implement

---

## 执行顺序

```
步骤1: stream.ts        ← 无依赖，必须首先改（防止 debug 事件崩溃 SSE 流）
步骤2: qa.ts            ← 无依赖，可与步骤1并行
步骤3: types.ts         ← 依赖步骤1（需要 RagTraceEvent 类型）
步骤4: rag-trace-panel  ← 新建组件，依赖步骤3
步骤5: chat-page.tsx    ← 依赖步骤1/2/3
步骤6: message-bubble   ← 依赖步骤4
```

---

## 步骤详情

### 步骤1：`frontend/src/lib/stream.ts`

**目标**：让 SSE 解析层识别 `debug` 事件，不再抛 StreamFormatError。

改动：
- `SseEvent` union type 新增：
  ```typescript
  | { type: "debug"; stage: string; data: Record<string, unknown> }
  ```
- 新增导出类型：
  ```typescript
  export type RagTraceEvent = { stage: string; data: Record<string, unknown> };
  ```
- `parseEvent`（第154行）在 `throw StreamFormatError` 之前插入 `debug` 分支：
  ```typescript
  if (
    payload.type === "debug" &&
    typeof payload.stage === "string" &&
    isRecord(payload.data)
  ) {
    return { type: "debug", stage: payload.stage, data: payload.data };
  }
  ```

---

### 步骤2：`frontend/src/services/qa.ts`

**目标**：支持透传 `debug: boolean` 到请求体。

改动：
- `askConversation` 两处签名（第62、68行）加 `debug?: boolean` 参数（位于 `signal` 之后）
- `fetchAskConversation` 参数对象加 `debug?: boolean`
- 请求体按条件拼入：
  ```typescript
  body: JSON.stringify({
    question,
    location: location ?? null,
    ...(debug ? { debug: true } : {}),
  }),
  ```

---

### 步骤3：`frontend/src/features/chat/types.ts`

**目标**：`LocalChatMessage` 携带 trace 事件列表。

改动：
- 顶部新增 import：
  ```typescript
  import type { RagTraceEvent } from "@/lib/stream";
  ```
- `LocalChatMessage` 加字段：
  ```typescript
  traceEvents?: RagTraceEvent[];
  ```

---

### 步骤4：新建 `frontend/src/features/chat/components/rag-trace-panel.tsx`

**目标**：折叠/展开的 RAG Trace 展示组件。

关键设计：
- Props：`{ events: RagTraceEvent[] }`
- 默认展开，点击头部折叠
- stage 中文映射表：
  ```typescript
  const STAGE_LABELS: Record<string, string> = {
    query_rewrite:  "Query 改写",
    embedding:      "向量化",
    retrieval:      "检索",
    rerank:         "重排序",
    citations:      "引用提取",
    terminal_error: "终止",
  };
  ```
- 耗时提取：找 `data` 中以 `_duration_ms` 结尾的键
- 视觉规则：
  - 正常行：`text-emerald-500`
  - `terminal_error`：整行红色高亮（`bg-rose-50 dark:bg-rose-900/20`）
  - `rerank_candidates_count === 0`：警告色 `text-amber-500`，显示"⚠ 无候选"

---

### 步骤5：`frontend/src/features/chat/components/chat-page.tsx`

**目标**：读取 debug 开关，透传参数，处理 debug 事件。

改动：
- 组件顶部加 `isDebug` state（用懒初始化防止 SSR Hydration mismatch）：
  ```typescript
  const [isDebug] = useState(() =>
    typeof window !== "undefined" &&
    (new URLSearchParams(window.location.search).get("debug") === "1" ||
      localStorage.getItem("rag_debug") === "true"),
  );
  ```
- `askConversation` 调用（第260行）加 `isDebug` 参数
- SSE 处理加 `debug` 分支（在 `error` 分支之后）：
  ```typescript
  if (event.type === "debug") {
    setMessages((current) =>
      current.map((msg) =>
        msg.clientId === clientId && msg.role === "assistant"
          ? { ...msg, traceEvents: [...(msg.traceEvents ?? []), { stage: event.stage, data: event.data }] }
          : msg,
      ),
    );
    // 注意：此处故意不调用 writeMessageCache，traceEvents 不持久化
  }
  ```
- `writeMessageCache` 调用处，序列化前剔除 `traceEvents`：
  ```typescript
  const sanitized = messages.map(({ traceEvents: _, ...rest }) => rest);
  ```

---

### 步骤6：`frontend/src/features/chat/components/message-bubble.tsx`

**目标**：在 CitationList 下方条件渲染 RagTracePanel。

改动：
- 新增 import：
  ```typescript
  import { RagTracePanel } from "./rag-trace-panel";
  ```
- `<CitationList />` 后插入：
  ```tsx
  {message.traceEvents && message.traceEvents.length > 0 && (
    <RagTracePanel events={message.traceEvents} />
  )}
  ```

---

## 风险点

| 风险 | 位置 | 严重度 | 缓解措施 |
|---|---|---|---|
| `traceEvents` 被序列化进 sessionStorage | `writeMessageCache` | 高 | 存储前 spread omit `traceEvents` |
| SSR Hydration mismatch | `chat-page.tsx` | 中 | `useState` 懒初始化读 `window.location` |
| `payload.data` 为空时 parseEvent 崩溃 | `stream.ts` | 中 | `isRecord(payload.data)` 校验，不满足则 fallthrough |
| `chat-state.ts` 展开操作丢失 traceEvents | `chat-state.ts` | 低 | 已确认所有函数用 `{...msg, field}` 形式，不覆写 traceEvents |

---

## 验收标准

- [ ] `?debug=1` 下发起成功问答，面板显示全部阶段 ✅
- [ ] rerank 无候选时，面板显示 `terminal_error` 红色高亮
- [ ] 普通 URL 下面板不渲染，请求体无 `debug` 字段
- [ ] 面板各行随 SSE 事件逐步出现（流式），不是一次性渲染
- [ ] 刷新页面后 traceEvents 不保留（不持久化）
