# 最小 RAG Debug 输出设计文档

> 日期：2026-05-08
> 目标：补全最小 RAG debug 输出，满足面试场景需求

---

## 1. 需求背景

### 1.1 当前问题

RAG 系统已实现基本的问答功能，但 debug 输出不完整，存在以下问题：

- **缺失阶段**：embedding、prompt 构建等关键阶段无 debug 输出
- **细节不足**：rerank score、chunk 完整内容等缺失
- **无控制开关**：无法通过环境变量控制 debug 输出
- **格式不统一**：缺少描述说明、单位标注等

### 1.2 面试场景需求

从面试官角度分析，以下 debug 输出是刚需：

1. **检索质量评估**：需要看到 rerank score 证明检索质量
2. **性能瓶颈定位**：需要看到 embedding、检索、生成各阶段耗时
3. **系统理解深度**：需要展示对每个环节的深入理解
4. **工程化思维**：需要展示可观测性设计和生产环境考虑

---

## 2. 设计目标

### 2.1 核心目标

补全最小 RAG debug 输出，满足以下需求：

- ✅ 补全 embedding 阶段输出
- ✅ 添加 rerank relevance_score
- ✅ 新增环境变量控制开关
- ✅ 优化 debug 输出格式（description、unit、timestamp）

### 2.2 约束

- 最小改动原则：只修改必要文件，不重构架构
- 向后兼容：不影响现有 API 和功能
- 性能影响最小：debug 输出开销控制在 5ms 内
- 面试导向：重点展示检索质量和系统理解

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                  QA Service (qa_service.py)              │
├─────────────────────────────────────────────────────────┤
│  stream_answer()                                      │
│    ├── 检查会话和权限                                   │
│    ├── query_rewrite + debug                           │
│    ├── embedding + debug (NEW)                         │
│    ├── vector_search                                   │
│    ├── fts_search                                      │
│    ├── merge_chunks                                    │
│    ├── retrieval + debug                               │
│    ├── rerank + debug (ENHANCED)                       │
│    ├── build_prompt                                   │
│    ├── gpt-4o streaming                               │
│    ├── extract_citations + debug                       │
│    └── telemetry + done                               │
└─────────────────────────────────────────────────────────┘

配置层 (config.py)
├── RAG_DEBUG_ENABLED: bool (NEW)
└── RAG_DEBUG_MODE: str (OPTIONAL)
```

### 3.2 Debug 事件流

每个 RAG 流程阶段生成一个 debug 事件：

```json
{
  "type": "debug",
  "stage": "stage_name",
  "timestamp": "ISO-8601",
  "trace_id": "conv-{conv_id}-{random}",
  "data": {
    "description": "阶段说明",
    "...": "具体数据",
    "unit": {
      "field_name": "单位说明"
    }
  }
}
```

---

## 4. 详细设计

### 4.1 环境变量控制

#### 配置项

在 `backend/app/core/config.py` 新增：

```python
# RAG Debug 配置
RAG_DEBUG_ENABLED: bool = False  # 是否开启 debug 输出
```

#### 调用逻辑

```python
def _build_debug_event(stage: str, data: dict[str, Any]) -> dict[str, Any]:
    if not settings.RAG_DEBUG_ENABLED:
        return {}

    return {
        "type": "debug",
        "stage": stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": f"conv-{conv_id}-{uuid.uuid4().hex[:8]}",
        "data": {
            "description": _get_stage_description(stage),
            **data,
        },
    }
```

---

### 4.2 Embedding 阶段

#### 输出时机

在 `stream_answer()` 函数中，调用 `generate_embeddings()` 之后：

```python
embedding_start = perf_counter()
[query_vec] = await generate_embeddings([retrieval_query])
embedding_duration_ms = _duration_ms(embedding_start, perf_counter())

if debug:
    yield _build_debug_event(
        "embedding",
        {
            "model": "text-embedding-3-small",
            "dimension": len(query_vec),
            "query_length": len(retrieval_query),
            "duration_ms": embedding_duration_ms,
            "unit": {
                "duration_ms": "毫秒",
                "dimension": "向量维度",
                "query_length": "字符数",
            },
        },
    )
```

#### 输出示例

```json
{
  "type": "debug",
  "stage": "embedding",
  "timestamp": "2026-05-08T10:30:45.123Z",
  "trace_id": "conv-12345-abcde",
  "data": {
    "description": "向量化用户问题",
    "model": "text-embedding-3-small",
    "dimension": 1536,
    "query_length": 24,
    "duration_ms": 125,
    "unit": {
      "duration_ms": "毫秒",
      "dimension": "向量维度",
      "query_length": "字符数"
    }
  }
}
```

---

### 4.3 Rerank 增强

#### 修改内容

在 `_debug_chunk_preview()` 函数中增加 relevance_score：

```python
def _debug_chunk_preview_with_score(
    chunks: Sequence[DocumentChunk],
    scores: Sequence[float] | None = None,
    limit: int = DEBUG_PREVIEW_LIMIT,
) -> list[dict[str, Any]]:
    result = []
    for i, chunk in enumerate(chunks[:limit]):
        item = {
            "chunk_id": str(chunk.id),
            "source_url": chunk.source_url,
            "heading_path": chunk.heading_path or "",
            "chunk_index": chunk.chunk_index,
        }
        if scores and i < len(scores):
            item["relevance_score"] = scores[i]
        result.append(item)
    return result
```

#### 输出示例

```json
{
  "type": "debug",
  "stage": "rerank",
  "timestamp": "2026-05-08T10:30:45.345Z",
  "trace_id": "conv-12345-abcde",
  "data": {
    "description": "重排序检索结果",
    "rerank_candidates_count": 5,
    "top_chunks": [
      {
        "chunk_id": "uuid",
        "source_url": "https://docs.example.com/install",
        "heading_path": "Installation > Redis",
        "chunk_index": 12,
        "relevance_score": 0.92
      },
      {
        "chunk_id": "uuid",
        "source_url": "https://docs.example.com/install",
        "heading_path": "Installation > PostgreSQL",
        "chunk_index": 15,
        "relevance_score": 0.85
      }
    ],
    "unit": {
      "relevance_score": "相关性分数 (0-1)",
      "rerank_candidates_count": "候选数"
    }
  }
}
```

---

### 4.4 格式优化

#### 4.4.1 Description 映射

为每个 stage 定义描述：

```python
def _get_stage_description(stage: str) -> str:
    descriptions = {
        "query_rewrite": "重写用户问题为独立的检索查询",
        "embedding": "向量化用户问题",
        "retrieval": "向量检索 + 全文检索",
        "rerank": "重排序检索结果",
        "citations": "提取并验证引用",
        "terminal_error": "终止错误",
    }
    return descriptions.get(stage, stage)
```

#### 4.4.2 Unit 字段

为数值字段添加单位说明：

```python
{
  "rewrite_duration_ms": 45,
  "vector_duration_ms": 123,
  "fts_duration_ms": 67,
  "rerank_duration_ms": 89,
  "generation_duration_ms": 1234,
  "unit": {
    "rewrite_duration_ms": "毫秒",
    "vector_duration_ms": "毫秒",
    "fts_duration_ms": "毫秒",
    "rerank_duration_ms": "毫秒",
    "generation_duration_ms": "毫秒"
  }
}
```

#### 4.4.3 元信息

添加 timestamp 和 trace_id：

```python
{
  "type": "debug",
  "stage": "retrieval",
  "timestamp": "2026-05-08T10:30:45.234Z",
  "trace_id": "conv-12345-abcde",
  "data": { ... }
}
```

---

## 5. 修改文件清单

### 5.1 修改文件

| 文件 | 修改内容 |
|------|---------|
| `backend/app/core/config.py` | 新增 `RAG_DEBUG_ENABLED` 配置项 |
| `backend/app/services/qa_service.py` | 补全 embedding、增强 rerank、优化格式 |

### 5.2 新增函数

| 函数名 | 位置 | 说明 |
|--------|------|------|
| `_get_stage_description()` | qa_service.py | 获取阶段描述 |
| `_debug_chunk_preview_with_score()` | qa_service.py | 带分数的 chunk 预览 |

### 5.3 修改函数

| 函数名 | 修改内容 |
|--------|---------|
| `stream_answer()` | 补全 embedding debug、优化 debug 事件构建 |
| `_build_debug_event()` | 添加 description、timestamp、trace_id |
| `_rerank()` | 返回分数用于 debug 输出 |

---

## 6. 实现计划

### Phase 1: 环境变量配置（15分钟）

1. 在 `config.py` 新增 `RAG_DEBUG_ENABLED`
2. 修改 `stream_answer()` 中的 debug 控制逻辑
3. 测试：环境变量关闭时不输出 debug

### Phase 2: Embedding 阶段（20分钟）

1. 在 `stream_answer()` 补全 embedding debug 输出
2. 获取 embedding 模型名称和维度
3. 测试：输出正确的 embedding 信息

### Phase 3: Rerank 增强（25分钟）

1. 修改 `_rerank()` 返回分数列表
2. 新增 `_debug_chunk_preview_with_score()` 函数
3. 在 rerank debug 输出中添加 relevance_score
4. 测试：输出正确的分数

### Phase 4: 格式优化（20分钟）

1. 新增 `_get_stage_description()` 函数
2. 修改 `_build_debug_event()` 添加 description
3. 为各阶段添加 unit 字段
4. 添加 timestamp 和 trace_id
5. 测试：所有 debug 事件格式统一

### Phase 5: 集成测试（20分钟）

1. 端到 debug 输出的完整链路
2. 验证环境变量开关
3. 验证所有阶段都有 debug 输出
4. 记录性能影响（应 < 5ms）

---

## 7. 测试验证

### 7.1 单元测试

```python
async def test_embedding_debug_event():
    """测试 embedding 阶段 debug 输出"""
    ...

async def test_rerank_with_score():
    """测试 rerank 输出包含分数"""
    ...

async def test_debug_format_unified():
    """测试 debug 格式统一（description、unit、timestamp）"""
    ...
```

### 7.2 集成测试

```python
async def test_rag_debug_complete_flow():
    """测试完整 RAG 流程的 debug 输出"""
    # 启用 debug
    # 发起问题
    # 验证所有阶段都有 debug 输出
    # 验证格式正确
```

### 7.3 手动测试

1. 启动后端服务（`RAG_DEBUG_ENABLED=True`）
2. 创建知识库并导入文档
3. 创建对话并提问
4. 观察 SSE 流输出的 debug 事件
5. 验证每个阶段的输出内容

---

## 8. 验收标准

### 8.1 功能验收

- [ ] 环境变量 `RAG_DEBUG_ENABLED=True` 时，所有 debug 事件正常输出
- [ ] 环境变量 `RAG_DEBUG_ENABLED=False` 时，不输出任何 debug 事件
- [ ] embedding 阶段输出模型名称、维度、耗时
- [ ] rerank 阶段输出每个 chunk 的 relevance_score
- [ ] 所有 debug 事件都有 description 字段
- [ ] 数值类型字段有 unit 说明
- [ ] 所有 debug 事件有 timestamp 和 trace_id

### 8.2 质量验收

- [ ] debug 输出格式统一（结构、命名、类型）
- [ ] description 描述清晰易懂
- [ ] unit 单位说明准确
- [ ] 性能影响 < 5ms（对比无 debug 输出）

### 8.3 面试场景验收

- [ ] 能通过 debug 输出展示检索质量（rerank score）
- [ ] 能通过 debug 输出展示性能瓶颈（各阶段耗时）
- [ ] 能通过 debug 输出展示对系统的深入理解
- [ ] 能回答"生产环境怎么办"（环境变量控制）

---

## 9. 风险和缓解

### 9.1 风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| debug 输出性能影响大 | 高 | 低 | 只在 debug 模式下输出，控制输出量 |
| 格式不一致导致解析困难 | 中 | 中 | 定义严格的 schema，写测试验证 |
| 环境变量配置错误 | 低 | 低 | 默认关闭，有明确文档说明 |

### 9.2 缓解措施

1. **性能控制**：只输出必要信息，避免大文本（如完整 chunk）
2. **格式验证**：写单元测试验证所有 debug 事件的格式
3. **文档说明**：在 README 中说明环境变量的使用

---

## 10. 附录

### 10.1 完整 Debug 输出示例

```json
data: {"type": "debug", "stage": "query_rewrite", "timestamp": "2026-05-08T10:30:45.000Z", "trace_id": "conv-12345-abcde", "data": {"description": "重写用户问题为独立的检索查询", "question": "如何安装 Redis?", "retrieval_query": "Redis 安装步骤", "rewritten": true, "rewrite_duration_ms": 45, "unit": {"rewrite_duration_ms": "毫秒"}}}

data: {"type": "debug", "stage": "embedding", "timestamp": "2026-05-08T10:30:45.045Z", "trace_id": "conv-12345-abcde", "data": {"description": "向量化用户问题", "model": "text-embedding-3-small", "dimension": 1536, "query_length": 12, "duration_ms": 125, "unit": {"duration_ms": "毫秒", "dimension": "向量维度", "query_length": "字符数"}}}

data: {"type": "debug", "stage": "retrieval", "timestamp": "2026-05-08T10:30:45.170Z", "trace_id": "conv-12345-abcde", "data": {"description": "向量检索 + 全文检索", "vector_candidates_count": 20, "fts_candidates_count": 15, "merged_candidates_count": 25, "vector_duration_ms": 123, "fts_duration_ms": 67, "unit": {"vector_candidates_count": "候选数", "fts_candidates_count": "候选数", "merged_candidates_count": "候选数", "vector_duration_ms": "毫秒", "fts_duration_ms": "毫秒"}}}

data: {"type": "debug", "stage": "rerank", "timestamp": "2026-05-08T10:30:45.259Z", "trace_id": "conv-12345-abcde", "data": {"description": "重排序检索结果", "rerank_candidates_count": 5, "top_chunks": [{"chunk_id": "uuid", "source_url": "https://docs.example.com/install", "heading_path": "Installation > Redis", "chunk_index": 12, "relevance_score": 0.92}, {"chunk_id": "uuid", "source_url": "https://docs.example.com/install", "heading_path": "Installation > PostgreSQL", "chunk_index": 15, "relevance_score": 0.85}], "unit": {"relevance_score": "相关性分数 (0-1)", "rerank_candidates_count": "候选数"}}}

data: {"type": "debug", "stage": "citations", "timestamp": "2026-05-08T10:30:47.123Z", "trace_id": "conv-12345-abcde", "data": {"description": "提取并验证引用", "citations_count": 3, "citation_indices": [1, 2, 5], "unit": {"citations_count": "引用数"}}}
```

### 10.2 面试回答示例

**面试官：你怎么评估检索质量？**

**回答（有详细 debug 输出）**：
```
我们通过 debug 输出来评估检索质量。比如 rerank 阶段会输出每个
chunk 的相关性分数，像 [0.92, 0.85, 0.72, 0.65, 0.58]。

通过这个分数分布，我们可以：
1. 判断检索质量：分数都在 0.7 以上说明检索很准确
2. 优化阈值：如果很多 0.6 左右的分数，可能需要调低 RAG_MIN_RERANK_SCORE
3. 对比分析：看问题和高分数 chunk 的相关性是否合理

生产环境我们会关闭详细 debug 输出，通过结构化的 telemetry
日志监控关键指标。
```

**面试官：性能瓶颈怎么定位？**

**回答（有详细 debug 输出）**：
```
我们每个阶段都有耗时统计：
- embedding: ~125ms（向量化）
- vector search: ~123ms（向量检索）
- FTS: ~67ms（全文检索）
- rerank: ~89ms（重排序）
- generation: ~1234ms（答案生成）

从这个例子看，generation 占了 70% 的时间，是主要瓶颈。
我们可以：
1. 优化 prompt 长度
2. 使用更快的模型（如 gpt-4o-mini）
3. 调整 top-k 参数减少生成上下文
```

---

## 11. 总结

本设计通过最小改动补全了 RAG debug 输出，满足面试场景需求：

1. ✅ 补全 embedding 阶段：输出模型、维度、耗时
2. ✅ 增强 rerank 输出：输出 relevance_score
3. ✅ 环境变量控制：生产环境可关闭
4. ✅ 格式优化：description、unit、timestamp

改动小、风险低、价值高，预期 2 小时内完成实现和测试。
