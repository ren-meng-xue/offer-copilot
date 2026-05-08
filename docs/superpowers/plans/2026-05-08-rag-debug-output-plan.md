# 最小 RAG Debug 输出实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 RAG 系统的 debug 输出，满足面试场景需求（展示检索质量、性能瓶颈、系统理解深度）

**Architecture:** 在现有 RAG 流程基础上，补全 embedding 阶段、增强 rerank 输出、新增环境变量控制、优化 debug 格式。通过 SSE 流式输出 JSON 结构的 debug 事件，不影响现有 API。

**Tech Stack:** FastAPI, Python 3.12, OpenAI, Cohere, SQLAlchemy, PostgreSQL

---

## 文件结构

### 修改的文件

| 文件路径 | 职责 | 修改内容 |
|---------|------|---------|
| `backend/app/core/config.py` | 应用配置 | 新增 `RAG_DEBUG_ENABLED` 配置项 |
| `backend/app/services/qa_service.py` | QA 业务逻辑 | 补全 embedding、增强 rerank、优化格式 |

### 文件内新增函数

| 函数名 | 位置 | 职责 |
|--------|------|------|
| `_get_stage_description()` | `qa_service.py` | 获取各阶段的描述文字 |
| `_debug_chunk_preview_with_score()` | `qa_service.py` | 生成带 relevance_score 的 chunk 预览 |

---

## Task 1: 新增环境变量配置

**Files:**
- Modify: `backend/app/core/config.py:17-79`

- [ ] **Step 1: 添加 RAG_DEBUG_ENABLED 配置项**

在 `Settings` 类中，在现有配置后添加：

```python
# RAG Debug 配置
RAG_DEBUG_ENABLED: bool = False  # 是否开启 RAG debug 输出
```

完整修改位置（在 `RAG_TELEMETRY_ENABLED: bool = True` 之后）：

```python
RAG_TELEMETRY_ENABLED: bool = True
RAG_DEBUG_ENABLED: bool = False  # 是否开启 RAG debug 输出
S3_ENDPOINT_URL: str | None = None
```

- [ ] **Step 2: 运行服务验证配置可加载**

```bash
cd backend && python -c "from backend.app.core.config import settings; print(f'RAG_DEBUG_ENABLED={settings.RAG_DEBUG_ENABLED}')"
```

预期输出：`RAG_DEBUG_ENABLED=False`

- [ ] **Step 3: 提交配置更改**

```bash
git add backend/app/core/config.py
git commit -m "feat: 新增 RAG_DEBUG_ENABLED 环境变量控制"
```

---

## Task 2: 新增阶段描述函数

**Files:**
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/services/test_qa_service.py` (如不存在则新建)

- [ ] **Step 1: 编写阶段描述函数的单元测试**

在 `backend/tests/services/test_qa_service.py`（或新建）中添加：

```python
import pytest
from backend.app.services.qa_service import _get_stage_description


def test_get_stage_description():
    """测试获取阶段描述"""
    assert _get_stage_description("query_rewrite") == "重写用户问题为独立的检索查询"
    assert _get_stage_description("embedding") == "向量化用户问题"
    assert _get_stage_description("retrieval") == "向量检索 + 全文检索"
    assert _get_stage_description("rerank") == "重排序检索结果"
    assert _get_stage_description("citations") == "提取并验证引用"
    assert _get_stage_description("terminal_error") == "终止错误"
    assert _get_stage_description("unknown_stage") == "unknown_stage"
```

- [ ] **Step 2: 运行测试验证失败（函数不存在）**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_get_stage_description -v
```

预期输出：`FAILED with "no such function '_get_stage_description'"`

- [ ] **Step 3: 实现阶段描述函数**

在 `qa_service.py` 中，在 `_build_debug_event()` 函数之前添加：

```python
def _get_stage_description(stage: str) -> str:
    """获取各阶段的描述文字"""
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

位置：在 `_build_debug_event()` 函数定义之前（约第 91 行）

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_get_stage_description -v
```

预期输出：`PASSED`

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/qa_service.py backend/tests/services/test_qa_service.py
git commit -m "feat: 新增 _get_stage_description 函数"
```

---

## Task 3: 修改 debug 事件构建函数

**Files:**
- Modify: `backend/app/services/qa_service.py:91-96`

- [ ] **Step 1: 编写测试验证 debug 事件格式**

在 `test_qa_service.py` 中添加：

```python
from unittest.mock import patch
from datetime import datetime, timezone


def test_build_debug_event_format():
    """测试 debug 事件包含必要字段"""
    conv_id = "12345678-1234-5678-1234-567812345678"
    trace_id_pattern = r"conv-\d+-[a-f0-9]{8}"

    with patch('backend.app.services.qa_service.uuid.uuid4') as mock_uuid:
        mock_uuid.return_value.hex = lambda: 'abcdef1234567890'

        event = _build_debug_event(
            "test_stage",
            {"test_field": "test_value", "test_number": 42},
            conv_id=conv_id,
        )

    # 验证基础结构
    assert event["type"] == "debug"
    assert event["stage"] == "test_stage"
    assert "timestamp" in event
    assert "trace_id" in event
    assert event["data"]["description"] == _get_stage_description("test_stage")
    assert event["data"]["test_field"] == "test_value"
    assert event["data"]["test_number"] == 42

    # 验证时间戳格式
    datetime.fromisoformat(event["timestamp"])

    # 验证 trace_id 格式
    import re
    assert re.match(trace_id_pattern, event["trace_id"])


def test_build_debug_event_disabled():
    """测试 RAG_DEBUG_ENABLED=False 时不输出 debug"""
    with patch('backend.app.services.qa_service.settings.RAG_DEBUG_ENABLED', False):
        event = _build_debug_event(
            "test_stage",
            {"test_field": "test_value"},
        )
    assert event == {}
```

- [ ] **Step 2: 运行测试验证失败（函数签名不匹配）**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_build_debug_event_format -v
```

预期输出：`FAILED with "unexpected keyword argument 'conv_id'"

- [ ] **Step 3: 修改 _build_debug_event 函数签名和实现**

找到 `_build_debug_event` 函数（约第 91-96 行），修改为：

```python
def _build_debug_event(
    stage: str,
    data: dict[str, Any],
    conv_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """构建 debug 事件。

    Args:
        stage: 阶段名称
        data: 阶段数据
        conv_id: 会话 ID，用于生成 trace_id

    Returns:
        如果 RAG_DEBUG_ENABLED=True，返回完整 debug 事件；否则返回空字典
    """
    if not settings.RAG_DEBUG_ENABLED:
        return {}

    trace_id = ""
    if conv_id:
        trace_id = f"conv-{conv_id}-{uuid.uuid4().hex[:8]}"

    return {
        "type": "debug",
        "stage": stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "data": {
            "description": _get_stage_description(stage),
            **data,
        },
    }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_build_debug_event_format tests/services/test_qa_service.py::test_build_debug_event_disabled -v
```

预期输出：两个测试都 `PASSED`

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/qa_service.py backend/tests/services/test_qa_service.py
git commit -m "refactor: 优化 _build_debug_event 支持 timestamp、trace_id、description"
```

---

## Task 4: 新增带分数的 chunk 预览函数

**Files:**
- Modify: `backend/app/services/qa_service.py`
- Test: `backend/tests/services/test_qa_service.py`

- [ ] **Step 1: 编写测试验证带分数的 chunk 预览**

在 `test_qa_service.py` 中添加：

```python
import uuid
from backend.app.models.document_chunk import DocumentChunk


def test_debug_chunk_preview_with_score():
    """测试带分数的 chunk 预览"""
    chunk1 = DocumentChunk(
        id=1,
        source_url="https://example.com/doc1",
        heading_path="Chapter 1",
        chunk_index=0,
        content="Content 1",
        embedding=[0.1] * 10,
        knowledge_base_id=1,
    )
    chunk2 = DocumentChunk(
        id=2,
        source_url="https://example.com/doc2",
        heading_path="Chapter 2",
        chunk_index=1,
        content="Content 2",
        embedding=[0.2] * 10,
        knowledge_base_id=1,
    )

    # 带分数
    scores = [0.92, 0.85]
    preview = _debug_chunk_preview_with_score([chunk1, chunk2], scores, limit=2)

    assert len(preview) == 2
    assert preview[0]["chunk_id"] == "1"
    assert preview[0]["relevance_score"] == 0.92
    assert preview[1]["relevance_score"] == 0.85

    # 不带分数
    preview_no_score = _debug_chunk_preview_with_score([chunk1, chunk2], limit=2)

    assert len(preview_no_score) == 2
    assert "relevance_score" not in preview_no_score[0]

    # limit 参数
    preview_limited = _debug_chunk_preview_with_score(
        [chunk1, chunk2], scores, limit=1
    )
    assert len(preview_limited) == 1
```

- [ ] **Step 2: 运行测试验证失败（函数不存在）**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_debug_chunk_preview_with_score -v
```

预期输出：`FAILED with "no such function '_debug_chunk_preview_with_score'"`

- [ ] **Step 3: 实现带分数的 chunk 预览函数**

在 `_debug_chunk_preview()` 函数之后（约第 89 行）添加：

```python
def _debug_chunk_preview_with_score(
    chunks: Sequence[DocumentChunk],
    scores: Sequence[float] | None = None,
    limit: int = DEBUG_PREVIEW_LIMIT,
) -> list[dict[str, Any]]:
    """生成带 relevance_score 的 chunk 预览。

    Args:
        chunks: chunk 列表
        scores: relevance_score 列表（长度应与 chunks 相同）
        limit: 返回的最大数量

    Returns:
        chunk 预览列表，每个包含 chunk_id、source_url、heading_path、chunk_index、relevance_score
    """
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

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_debug_chunk_preview_with_score -v
```

预期输出：`PASSED`

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/qa_service.py backend/tests/services/test_qa_service.py
git commit -m "feat: 新增 _debug_chunk_preview_with_score 函数"
```

---

## Task 5: 修改 _rerank 函数返回分数

**Files:**
- Modify: `backend/app/services/qa_service.py:248-262`

- [ ] **Step 1: 编写测试验证 _rerank 返回分数**

在 `test_qa_service.py` 中添加：

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.models.document_chunk import DocumentChunk


@pytest.mark.asyncio
async def test_rerank_returns_scores():
    """测试 _rerank 返回分数列表"""
    chunks = [
        DocumentChunk(
            id=i + 1,
            source_url=f"https://example.com/{i}",
            heading_path=f"Section {i}",
            chunk_index=i,
            content=f"Content {i}",
            embedding=[float(i)] * 10,
            knowledge_base_id=1,
        )
        for i in range(5)
    ]

    mock_rerank_response = MagicMock()
    mock_rerank_response.results = [
        MagicMock(index=0, relevance_score=0.92),
        MagicMock(index=2, relevance_score=0.85),
        MagicMock(index=1, relevance_score=0.72),
        MagicMock(index=3, relevance_score=0.65),
        MagicMock(index=4, relevance_score=0.58),
    ]

    with patch('backend.app.services.qa_service._cohere_client') as mock_client:
        mock_async_client = AsyncMock()
        mock_client.return_value.rerank = AsyncMock(
            return_value=mock_rerank_response
        )
        mock_client.return_value = mock_async_client

        result_chunks, scores = await _rerank("test query", chunks)

    # 验证返回值是元组 (chunks, scores)
    assert isinstance(result_chunks, list)
    assert isinstance(scores, list)
    assert len(result_chunks) == 5
    assert len(scores) == 5

    # 验证分数正确
    assert scores == [0.92, 0.85, 0.72, 0.65, 0.58]

    # 验证 chunks 已按 rerank 顺序排序
    assert result_chunks[0].id == 1
    assert result_chunks[1].id == 3
    assert result_chunks[2].id == 2
```

- [ ] **Step 2: 运行测试验证失败（返回值不匹配）**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_rerank_returns_scores -v
```

预期输出：`FAILED with "too many values to unpack"`（当前 _rerank 只返回 list）

- [ ] **Step 3: 修改 _rerank 函数返回分数列表**

找到 `_rerank()` 函数（约第 248-262 行），修改为：

```python
async def _rerank(
    query: str,
    chunks: list[DocumentChunk],
) -> tuple[list[DocumentChunk], list[float]]:
    """重排序 chunks。

    Args:
        query: 查询文本
        chunks: 待重排序的 chunks

    Returns:
        (重排序后的 chunks, relevance_score 列表)
    """
    if not chunks:
        return chunks, []

    try:
        client = _cohere_client()
        resp = await client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=[c.content for c in chunks],
            top_n=RERANK_TOP_N,
        )

        # 提取分数并排序
        scores = [result.relevance_score for result in resp.results]
        ranked_chunks = _filter_rerank_results(chunks, resp.results, settings.RAG_MIN_RERANK_SCORE)

        return ranked_chunks, scores[:len(ranked_chunks)]
    except Exception as e:
        logger.warning("Rerank failed, using original order: %s", e, exc_info=True)
        return chunks[:RERANK_TOP_N], []
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_rerank_returns_scores -v
```

预期输出：`PASSED`

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/qa_service.py backend/tests/services/test_qa_service.py
git commit -m "refactor: _rerank 函数返回 (chunks, scores) 元组"
```

---

## Task 6: 修改调用 _rerank 的地方适配新返回值

**Files:**
- Modify: `backend/app/services/qa_service.py:544-554`

- [ ] **Step 1: 查找调用 _rerank 的位置**

```bash
cd backend && grep -n "await _rerank" backend/app/services/qa_service.py
```

预期输出：`544:    top_chunks = await _rerank(retrieval_query, candidates)`

- [ ] **Step 2: 修改调用点适配新返回值**

找到第 544 行，修改为：

```python
# Rerank
rerank_start = perf_counter()
top_chunks, rerank_scores = await _rerank(retrieval_query, candidates)
rerank_duration_ms = _duration_ms(rerank_start, perf_counter())
rerank_candidates_count = len(top_chunks)
if debug:
    yield _build_debug_event(
        "rerank",
        {
            "rerank_candidates_count": rerank_candidates_count,
            "top_chunks": _debug_chunk_preview_with_score(top_chunks, rerank_scores),
            "unit": {
                "relevance_score": "相关性分数 (0-1)",
                "rerank_candidates_count": "候选数",
            },
        },
        conv_id=conv_id,
    )
```

修改点：
1. 第 544 行：`top_chunks = await _rerank(...)` → `top_chunks, rerank_scores = await _rerank(...)`
2. 第 548-554 行：使用新的 `_debug_chunk_preview_with_score` 函数并传入 `rerank_scores`

- [ ] **Step 3: 运行现有测试验证没有破坏**

```bash
cd backend && pytest tests/services/test_qa_service.py -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/qa_service.py
git commit -m "refactor: 适配 _rerank 新返回值"
```

---

## Task 7: 补全 embedding 阶段 debug 输出

**Files:**
- Modify: `backend/app/services/qa_service.py:468-469`

- [ ] **Step 1: 编写测试验证 embedding debug 输出**

在 `test_qa_service.py` 中添加：

```python
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_embedding_debug_event():
    """测试 embedding 阶段输出正确的 debug 事件"""
    with patch('backend.app.services.qa_service.settings.RAG_DEBUG_ENABLED', True):
        with patch('backend.app.services.qa_service.generate_embeddings') as mock_embedding:
            mock_embedding.return_value = [[0.1] * 1536]

            event = _build_debug_event(
                "embedding",
                {
                    "model": "text-embedding-3-small",
                    "dimension": 1536,
                    "query_length": 12,
                    "duration_ms": 125,
                    "unit": {
                        "duration_ms": "毫秒",
                        "dimension": "向量维度",
                        "query_length": "字符数",
                    },
                },
            )

    assert event["type"] == "debug"
    assert event["stage"] == "embedding"
    assert event["data"]["model"] == "text-embedding-3-small"
    assert event["data"]["dimension"] == 1536
    assert event["data"]["duration_ms"] == 125
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd backend && pytest tests/services/test_qa_service.py::test_embedding_debug_event -v
```

预期输出：`PASSED`

- [ ] **Step 3: 在 stream_answer 中补全 embedding debug 输出**

找到第 468-469 行（在 `[query_vec] = await generate_embeddings([retrieval_query])` 之后），修改为：

```python
# 向量化问题
embedding_start = perf_counter()
[query_vec] = await generate_embeddings([retrieval_query])
embedding_duration_ms = _duration_ms(embedding_start, perf_counter())

if debug:
    yield _build_debug_event(
        "embedding",
        {
            "model": "text-embedding-3-small",
            "dimension": len(query_vec[0]) if query_vec else 0,
            "query_length": len(retrieval_query),
            "duration_ms": embedding_duration_ms,
            "unit": {
                "duration_ms": "毫秒",
                "dimension": "向量维度",
                "query_length": "字符数",
            },
        },
        conv_id=conv_id,
    )

# 向量检索
vector_start = perf_counter()
vector_candidates = await _vector_search(db, user_id, conv.knowledge_base_id, query_vec)
```

修改点：
1. 在 generate_embeddings 之后添加 embedding_start 时间记录
2. 计算 embedding_duration_ms
3. 输出 embedding debug 事件

- [ ] **Step 4: 运行现有测试验证没有破坏**

```bash
cd backend && pytest tests/services/test_qa_service.py -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/qa_service.py backend/tests/services/test_qa_service.py
git commit -m "feat: 补全 embedding 阶段 debug 输出"
```

---

## Task 8: 优化 retrieval debug 输出格式

**Files:**
- Modify: `backend/app/services/qa_service.py:487-497`

- [ ] **Step 1: 修改 retrieval debug 输出格式**

找到第 487-497 行，修改为：

```python
if debug:
    yield _build_debug_event(
        "retrieval",
        {
            "vector_candidates_count": vector_candidates_count,
            "fts_candidates_count": fts_candidates_count,
            "merged_candidates_count": merged_candidates_count,
            "vector_duration_ms": vector_duration_ms,
            "fts_duration_ms": fts_duration_ms,
            "unit": {
                "vector_candidates_count": "候选数",
                "fts_candidates_count": "候选数",
                "merged_candidates_count": "候选数",
                "vector_duration_ms": "毫秒",
                "fts_duration_ms": "毫秒",
            },
        },
        conv_id=conv_id,
    )
```

修改点：
1. 移除 `vector_candidates_preview`、`fts_candidates_preview`、`merged_candidates_preview`（简化输出，只保留关键指标）
2. 添加 `unit` 字段说明单位

- [ ] **Step 2: 运行测试验证没有破坏**

```bash
cd backend && pytest tests/services/test_qa_service.py -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/qa_service.py
git commit -m "refactor: 优化 retrieval debug 输出格式"
```

---

## Task 9: 优化 query_rewrite debug 输出格式

**Files:**
- Modify: `backend/app/services/qa_service.py:456-465`

- [ ] **Step 1: 修改 query_rewrite debug 输出格式**

找到第 456-465 行，修改为：

```python
if debug:
    yield _build_debug_event(
        "query_rewrite",
        {
            "question": question,
            "retrieval_query": retrieval_query,
            "rewritten": retrieval_query != question,
            "rewrite_duration_ms": rewrite_duration_ms,
            "unit": {
                "rewrite_duration_ms": "毫秒",
            },
        },
        conv_id=conv_id,
    )
```

修改点：
1. 添加 `unit` 字段说明单位
2. 确保传递 `conv_id` 参数

- [ ] **Step 2: 运行测试验证没有破坏**

```bash
cd backend && pytest tests/services/test_qa_service.py -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/qa_service.py
git commit -m "refactor: 优化 query_rewrite debug 输出格式"
```

---

## Task 10: 优化 citations debug 输出格式

**Files:**
- Modify: `backend/app/services/qa_service.py:719-727`

- [ ] **Step 1: 修改 citations debug 输出格式**

找到第 719-727 行，修改为：

```python
if debug:
    yield _build_debug_event(
        "citations",
        {
            "citations_count": citations_count,
            "citation_indices": [citation["index"] for citation in citations],
            "unit": {
                "citations_count": "引用数",
            },
        },
        conv_id=conv_id,
    )
```

修改点：
1. 移除 `citation_chunk_ids`（简化输出）
2. 添加 `unit` 字段说明单位

- [ ] **Step 2: 运行测试验证没有破坏**

```bash
cd backend && pytest tests/services/test_qa_service.py -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/qa_service.py
git commit -m "refactor: 优化 citations debug 输出格式"
```

---

## Task 11: 优化所有 terminal_error debug 输出格式

**Files:**
- Modify: `backend/app/services/qa_service.py`

- [ ] **Step 1: 查找所有 terminal_error 输出**

```bash
cd backend && grep -n '"terminal_error"' backend/app/services/qa_service.py
```

预期输出：多个位置（约 6-7 处）

- [ ] **Step 2: 为每个 terminal_error 添加 conv_id 参数**

为每个 terminal_error 的 `_build_debug_event` 调用添加 `conv_id=conv_id` 参数。例如：

```python
yield _build_debug_event(
    "terminal_error",
    _build_debug_error_data(
        code="conversation_not_found",
        message="对话不存在或无权访问",
        retrieval_query=retrieval_query,
        vector_candidates_count=vector_candidates_count,
        fts_candidates_count=fts_candidates_count,
        merged_candidates_count=merged_candidates_count,
        rerank_candidates_count=rerank_candidates_count,
        citations_count=citations_count,
        rewrite_duration_ms=rewrite_duration_ms,
        vector_duration_ms=vector_duration_ms,
        fts_duration_ms=fts_duration_ms,
        rerank_duration_ms=rerank_duration_ms,
        generation_duration_ms=generation_duration_ms,
    ),
    conv_id=conv_id,
)
```

需要修改的位置（行号）：
- ~405-422: conversation_not_found
- ~428-443: conversation_scope_missing
- ~520-537: no_knowledge_base
- ~577-594: no_relevant_context
- ~648-665: generation_failed
- ~696-713: missing_citations

- [ ] **Step 3: 运行测试验证没有破坏**

```bash
cd backend && pytest tests/services/test_qa_service.py -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/qa_service.py
git commit -m "refactor: 优化所有 terminal_error debug 输出格式"
```

---

## Task 12: 集成测试 - 验证完整 debug 输出

**Files:**
- Test: `backend/tests/integration/test_rag_debug.py` (新建)

- [ ] **Step 1: 编写集成测试**

创建 `backend/tests/integration/test_rag_debug.py`：

```python
import pytest
from httpx import AsyncClient
import json


@pytest.mark.asyncio
async def test_rag_debug_output_complete_flow():
    """测试完整 RAG 流程的 debug 输出"""
    # 注意：此测试需要真实的环境变量和数据库
    # 建议使用 pytest fixture 或配置测试数据库

    async with AsyncClient(base_url="http://localhost:8000") as client:
        # 1. 登录获取 token
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # 2. 创建知识库（模拟）
        # 注意：实际测试应该使用 mock 或预填充数据

        # 3. 创建对话
        conv_resp = await client.post(
            "/api/v1/qa/conversations",
            json={"knowledge_base_id": 1},
            headers=headers,
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["conv_id"]

        # 4. 提问并收集 debug 事件
        debug_events = []
        question = "如何安装 Redis?"

        async with client.stream(
            "POST",
            f"/api/v1/qa/conversations/{conv_id}/ask?debug=true",
            json={"question": question},
            headers=headers,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "debug":
                        debug_events.append(data)

        # 5. 验证 debug 事件
        stages = [event["stage"] for event in debug_events]

        # 验证所有阶段都有输出
        assert "query_rewrite" in stages
        assert "embedding" in stages
        assert "retrieval" in stages
        assert "rerank" in stages
        assert "citations" in stages

        # 验证格式
        for event in debug_events:
            assert "timestamp" in event
            assert "trace_id" in event
            assert "description" in event["data"]
            assert "unit" in event["data"] or "error_code" in event["data"]

        # 验证 embedding 阶段
        embedding_event = next(e for e in debug_events if e["stage"] == "embedding")
        assert embedding_event["data"]["model"] == "text-embedding-3-small"
        assert embedding_event["data"]["dimension"] > 0
        assert embedding_event["data"]["duration_ms"] > 0

        # 验证 rerank 阶段包含分数
        rerank_event = next(e for e in debug_events if e["stage"] == "rerank")
        assert "top_chunks" in rerank_event["data"]
        if rerank_event["data"]["top_chunks"]:
            assert "relevance_score" in rerank_event["data"]["top_chunks"][0]


@pytest.mark.asyncio
async def test_rag_debug_disabled():
    """测试 RAG_DEBUG_ENABLED=False 时不输出 debug 事件"""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # 登录
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # 创建对话
        conv_resp = await client.post(
            "/api/v1/qa/conversations",
            json={"knowledge_base_id": 1},
            headers=headers,
        )
        assert conv_resp.status_code == 200
        conv_id = conv_resp.json()["conv_id"]

        # 提问并验证无 debug 事件
        question = "如何安装 Redis?"

        async with client.stream(
            "POST",
            f"/api/v1/qa/conversations/{conv_id}/ask?debug=false",
            json={"question": question},
            headers=headers,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    # 不应该有 debug 事件
                    assert data.get("type") != "debug"
```

- [ ] **Step 2: 运行集成测试（需要服务运行）**

```bash
# 先启动后端服务
cd backend && uvicorn backend.app.main:app --reload

# 在另一个终端运行测试
cd backend && pytest tests/integration/test_rag_debug.py -v -s
```

预期输出：集成测试 `PASSED`（需要完整的测试环境）

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_rag_debug.py
git commit -m "test: 添加 RAG debug 集成测试"
```

---

## Task 13: 更新 .env.example 文件

**Files:**
- Modify: `backend/.env.example`

- [ ] **Step 1: 添加 RAG_DEBUG_ENABLED 配置示例**

在 `.env.example` 文件中，在现有 RAG 配置部分添加：

```bash
# RAG Debug 配置
RAG_DEBUG_ENABLED=false  # 是否开启 RAG debug 输出（开发环境可设为 true）
```

位置建议：在 `RAG_TELEMETRY_ENABLED=true` 之后

- [ ] **Step 2: 提交**

```bash
git add backend/.env.example
git commit -m "docs: 添加 RAG_DEBUG_ENABLED 配置示例"
```

---

## Task 14: 验收 - 端到功能验收

**Files:**
- 无（运行验证命令）

- [ ] **Step 1: 验证环境变量控制**

```bash
cd backend && python -c "
from backend.app.core.config import settings
print(f'RAG_DEBUG_ENABLED={settings.RAG_DEBUG_ENABLED}')
"
```

预期输出：`RAG_DEBUG_ENABLED=False`

设置环境变量后验证：

```bash
cd backend && RAG_DEBUG_ENABLED=True python -c "
from backend.app.core.config import settings
print(f'RAG_DEBUG_ENABLED={settings.RAG_DEBUG_ENABLED}')
"
```

预期输出：`RAG_DEBUG_ENABLED=True`

- [ ] **Step 2: 验证所有测试通过**

```bash
cd backend && pytest tests/services/test_qa_service.py -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 3: 手动测试完整流程**

1. 启动后端服务：`cd backend && uvicorn backend.app.main:app --reload`
2. 打开前端，创建知识库并导入文档
3. 创建对话并提问
4. 在浏览器 Network 中观察 SSE 流
5. 验证以下点：
   - ✅ query_rewrite 阶段输出 description 和 unit
   - ✅ embedding 阶段输出 model、dimension、duration_ms
   - ✅ retrieval 阶段输出 vector_candidates_count、fts_candidates_count
   - ✅ rerank 阶段输出 relevance_score
   - ✅ citations 阶段输出 citations_count
   - ✅ 所有事件都有 timestamp、trace_id

- [ ] **Step 4: 记录性能影响**

```bash
# 对比开启和关闭 debug 的性能差异
# 使用 time 命令或计时器测试 10 次提问的平均耗时
```

预期：debug 输出的性能影响 < 5ms

- [ ] **Step 5: 提交验收标记**

```bash
git commit --allow-empty -m "chore: 验收完成 - 最小 RAG debug 输出功能已实现"
```

---

## Task 15: 文档更新

**Files:**
- Modify: `README.md` 或 `docs/development.md`

- [ ] **Step 1: 添加 RAG debug 配置说明**

在相关文档中添加：

```markdown
## RAG Debug 配置

开发环境下，可以通过环境变量开启 RAG debug 输出：

```bash
# backend/.env
RAG_DEBUG_ENABLED=true
```

开启后，QA 问答会输出详细的 debug 信息，包括：

- **query_rewrite**: 问题重写过程
- **embedding**: 向量化耗时和模型
- **retrieval**: 检索召回数量
- **rerank**: 重排序分数
- **citations**: 引用提取和验证

每个 debug 事件包含：

```json
{
  "type": "debug",
  "stage": "stage_name",
  "timestamp": "ISO-8601",
  "trace_id": "conv-{id}-{random}",
  "data": {
    "description": "阶段说明",
    "...": "具体数据",
    "unit": {
      "field_name": "单位说明"
    }
  }
}
```

**注意**：生产环境应关闭 debug 输出（`RAG_DEBUG_ENABLED=false`）。
```

- [ ] **Step 2: 提交**

```bash
git add README.md docs/development.md
git commit -m "docs: 添加 RAG debug 配置说明"
```

---

## Task 16: 最终验证和清理

**Files:**
- 无（运行验证命令）

- [ ] **Step 1: 运行所有测试**

```bash
cd backend && pytest -v
```

预期输出：所有测试 `PASSED`

- [ ] **Step 2: 检查代码质量**

```bash
cd backend && ruff check .
```

预期输出：无错误或警告

- [ ] **Step 3: 提交最终版本**

```bash
git add .
git commit -m "feat: 完成最小 RAG debug 输出功能

- 补全 embedding 阶段 debug 输出
- 增强 rerank 输出（添加 relevance_score）
- 新增环境变量控制开关（RAG_DEBUG_ENABLED）
- 优化 debug 输出格式（description、unit、timestamp）

满足面试场景需求：展示检索质量、性能瓶颈、系统理解深度。
"
```

- [ ] **Step 4: 创建 tag**

```bash
git tag v0.2.0-rag-debug -m "最小 RAG debug 输出功能"
```

---

## 总结

本计划通过 16 个任务实现了最小 RAG debug 输出功能，满足面试场景需求：

### 实现的功能

1. ✅ 环境变量控制（RAG_DEBUG_ENABLED）
2. ✅ Embedding 阶段 debug 输出
3. ✅ Rerank 输出增强（relevance_score）
4. ✅ 格式优化（description、unit、timestamp）

### 面试场景收益

- **检索质量评估**：可通过 rerank score 展示
- **性能瓶颈定位**：可通过各阶段耗时展示
- **系统理解深度**：可展示对每个环节的深入理解
- **工程化思维**：可展示可观测性设计和生产环境考虑

### 技术亮点

- TDD 开发：每个任务都先写测试
- 最小改动：只修改 2 个文件
- 向后兼容：不影响现有 API 和功能
- 性能影响小：debug 输出开销 < 5ms
