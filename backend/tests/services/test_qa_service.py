import uuid
from types import SimpleNamespace

import pytest

from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBaseStatus
from backend.app.services.qa_service import (
    CitationValidationError,
    ConversationCreationError,
    _build_debug_event,
    _build_rag_telemetry_payload,
    _build_query_rewrite_messages,
    _debug_chunk_preview,
    _debug_chunk_preview_with_score,
    _emit_rag_telemetry,
    _extract_citations,
    _filter_rerank_results,
    _get_stage_description,
    _merge_chunks_by_id,
    _rewrite_query,
    _require_citations,
    create_conversation,
    stream_answer,
)


def _chunk(chunk_id: int, content: str = "LangChain docs") -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        knowledge_base_id=1,
        content=content,
        embedding=[0.0] * 1536,
        source_url="https://docs.example.com/langchain",
        heading_path="Overview",
        chunk_index=chunk_id - 1,
    )


def test_extract_citations_serializes_frontend_contract() -> None:
    chunk = _chunk(
        123, "LangChain is a framework for building applications with language models."
    )
    chunk.heading_path = None

    citations = _extract_citations("LangChain 用于构建语言模型应用。[1]", [chunk])

    assert citations == [
        {
            "index": 1,
            "chunk_id": "123",
            "source_url": "https://docs.example.com/langchain",
            "heading_path": "",
            "snippet": "LangChain is a framework for building applications with language models.",
        }
    ]


def test_require_citations_rejects_answer_without_reference() -> None:
    chunk = _chunk(
        123, "LangChain is a framework for building applications with language models."
    )

    try:
        _require_citations("LangChain 用于构建语言模型应用。", [chunk])
    except CitationValidationError:
        return

    raise AssertionError("Expected CitationValidationError")


def test_require_citations_rejects_out_of_range_reference() -> None:
    chunk = _chunk(
        123, "LangChain is a framework for building applications with language models."
    )

    try:
        _require_citations("LangChain 用于构建语言模型应用。[99]", [chunk])
    except CitationValidationError:
        return

    raise AssertionError("Expected CitationValidationError")


def test_extract_citations_supports_parentheses_format() -> None:
    chunk = _chunk(
        123, "LangChain is a framework for building applications with language models."
    )

    citations = _extract_citations("LangChain 用于构建语言模型应用。(1)", [chunk])

    assert citations == [
        {
            "index": 1,
            "chunk_id": "123",
            "source_url": "https://docs.example.com/langchain",
            "heading_path": "Overview",
            "snippet": "LangChain is a framework for building applications with language models.",
        }
    ]


def test_extract_citations_supports_full_width_brackets() -> None:
    chunk = _chunk(
        123, "LangChain is a framework for building applications with language models."
    )

    citations = _extract_citations("LangChain 用于构建语言模型应用。【1】", [chunk])

    assert citations == [
        {
            "index": 1,
            "chunk_id": "123",
            "source_url": "https://docs.example.com/langchain",
            "heading_path": "Overview",
            "snippet": "LangChain is a framework for building applications with language models.",
        }
    ]


def test_extract_citations_supports_angle_brackets() -> None:
    chunk = _chunk(
        123, "LangChain is a framework for building applications with language models."
    )

    citations = _extract_citations("LangChain 用于构建语言模型应用。<1>", [chunk])

    assert citations == [
        {
            "index": 1,
            "chunk_id": "123",
            "source_url": "https://docs.example.com/langchain",
            "heading_path": "Overview",
            "snippet": "LangChain is a framework for building applications with language models.",
        }
    ]


def test_extract_citations_handles_mixed_formats() -> None:
    chunk1 = _chunk(1, "First chunk content")
    chunk2 = _chunk(2, "Second chunk content")

    citations = _extract_citations(
        "根据 [1] 和(2)，以及【3】和<4>的内容", [chunk1, chunk2]
    )

    # 只提取有效的索引（1 和 2）
    assert len(citations) == 2
    assert citations[0]["index"] == 1
    assert citations[1]["index"] == 2


def test_extract_citations_filters_out_of_range_reference() -> None:
    chunk = _chunk(
        123, "LangChain is a framework for building applications with language models."
    )

    citations = _require_citations("LangChain 用于构建语言模型应用。[1][99]", [chunk])

    assert citations == [
        {
            "index": 1,
            "chunk_id": "123",
            "source_url": "https://docs.example.com/langchain",
            "heading_path": "Overview",
            "snippet": "LangChain is a framework for building applications with language models.",
        }
    ]


def test_filter_rerank_results_keeps_results_at_or_above_threshold() -> None:
    chunks = [_chunk(1), _chunk(2)]
    results = [
        SimpleNamespace(index=0, relevance_score=0.15),
        SimpleNamespace(index=1, relevance_score=0.7),
    ]

    filtered = _filter_rerank_results(chunks, results, min_score=0.15)

    assert filtered == chunks


def test_filter_rerank_results_removes_low_score_results() -> None:
    chunks = [_chunk(1), _chunk(2)]
    results = [
        SimpleNamespace(index=0, relevance_score=0.14),
        SimpleNamespace(index=1, relevance_score=0.7),
    ]

    filtered = _filter_rerank_results(chunks, results, min_score=0.15)

    assert filtered == [chunks[1]]


def test_filter_rerank_results_returns_empty_when_all_results_are_low_score() -> None:
    chunks = [_chunk(1), _chunk(2)]
    results = [
        SimpleNamespace(index=0, relevance_score=0.01),
        SimpleNamespace(index=1, relevance_score=0.02),
    ]

    filtered = _filter_rerank_results(chunks, results, min_score=0.15)

    assert filtered == []


def test_filter_rerank_results_can_be_disabled_with_zero_threshold() -> None:
    chunks = [_chunk(1), _chunk(2)]
    results = [
        SimpleNamespace(index=0, relevance_score=0.0),
        SimpleNamespace(index=1, relevance_score=0.02),
    ]

    filtered = _filter_rerank_results(chunks, results, min_score=0)

    assert filtered == chunks


def test_merge_chunks_by_id_deduplicates_same_chunk_from_multiple_retrievers() -> None:
    chunk1 = _chunk(1, "LANGCHAIN_API_KEY")
    chunk2 = _chunk(2, "OPENAI_API_KEY")

    merged = _merge_chunks_by_id([chunk1, chunk2], [chunk2, chunk1])

    assert merged == [chunk1, chunk2]


def test_merge_chunks_by_id_preserves_first_seen_order() -> None:
    chunk1 = _chunk(1, "vector hit")
    chunk2 = _chunk(2, "fts hit")
    chunk3 = _chunk(3, "shared hit")

    merged = _merge_chunks_by_id([chunk1, chunk3], [chunk2, chunk3])

    assert merged == [chunk1, chunk3, chunk2]


def test_build_query_rewrite_messages_includes_summary_history_and_question() -> None:
    recent_messages = [
        SimpleNamespace(role="user", content="Redis 怎么配置？"),
        SimpleNamespace(role="assistant", content="先看安装章节。[1]"),
    ]

    messages = _build_query_rewrite_messages(
        "那生产环境怎么写？",
        recent_messages,
        "用户正在配置 Redis",
    )

    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "system", "content": "历史摘要：用户正在配置 Redis"}
    assert messages[-1] == {"role": "user", "content": "那生产环境怎么写？"}


def test_build_rag_telemetry_payload_uses_lengths_not_raw_text() -> None:
    payload = _build_rag_telemetry_payload(
        conversation_id=uuid.uuid4(),
        knowledge_base_id=11,
        question="Redis 怎么配置？",
        retrieval_query="Redis production configuration",
        vector_candidates_count=20,
        fts_candidates_count=4,
        merged_candidates_count=22,
        rerank_candidates_count=5,
        citations_count=2,
        rewrite_duration_ms=10,
        vector_duration_ms=12,
        fts_duration_ms=3,
        rerank_duration_ms=20,
        generation_duration_ms=100,
        total_duration_ms=145,
        outcome="success",
        error_code=None,
        cohere_top_score=0.85,
    )

    assert payload["question_length"] == len("Redis 怎么配置？")
    assert payload["retrieval_query_length"] == len("Redis production configuration")
    assert payload["retrieval_query_rewritten"] is True
    assert payload["cohere_top_score"] == 0.85
    assert "question" not in payload
    assert "answer" not in payload


def test_debug_chunk_preview_exposes_only_lightweight_metadata() -> None:
    chunk = _chunk(123, "full content should stay out of debug preview")

    preview = _debug_chunk_preview([chunk])

    assert preview == [
        {
            "chunk_id": "123",
            "source_url": "https://docs.example.com/langchain",
            "heading_path": "Overview",
            "chunk_index": 122,
        }
    ]


def test_get_stage_description() -> None:
    """测试获取阶段描述"""
    assert _get_stage_description("query_rewrite") == "重写用户问题为独立的检索查询"
    assert _get_stage_description("embedding") == "向量化用户问题"
    assert _get_stage_description("retrieval") == "向量检索 + 全文检索"
    assert _get_stage_description("rerank") == "重排序检索结果"
    assert _get_stage_description("citations") == "提取并验证引用"
    assert _get_stage_description("terminal_error") == "终止错误"
    assert _get_stage_description("unknown_stage") == "unknown_stage"


def test_build_debug_event_wraps_stage_and_payload() -> None:
    from unittest.mock import patch

    with patch("backend.app.services.qa_service.settings.RAG_DEBUG_ENABLED", True):
        event = _build_debug_event("retrieval", {"merged_candidates_count": 2})

    assert event["type"] == "debug"
    assert event["stage"] == "retrieval"
    assert event["data"]["merged_candidates_count"] == 2


def test_build_debug_event_format():
    """测试 debug 事件包含必要字段"""
    from unittest.mock import patch, MagicMock
    from datetime import datetime

    conv_id = "12345678-1234-5678-1234-567812345678"
    trace_id_pattern = r"conv-[0-9a-f-]+-[a-f0-9]{8}"

    with (
        patch("backend.app.services.qa_service.uuid.uuid4") as mock_uuid,
        patch("backend.app.services.qa_service.settings.RAG_DEBUG_ENABLED", True),
    ):
        mock_uuid_obj = MagicMock()
        mock_uuid_obj.hex = "abcdef1234567890"
        mock_uuid.return_value = mock_uuid_obj

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
    from unittest.mock import patch

    with patch("backend.app.services.qa_service.settings.RAG_DEBUG_ENABLED", False):
        event = _build_debug_event(
            "test_stage",
            {"test_field": "test_value"},
        )
    assert event == {}


def test_emit_rag_telemetry_logs_single_structured_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeLogger:
        def info(self, message: str, body: str | None = None) -> None:
            if body is not None:
                events.append(f"{message} {body}")
            else:
                events.append(message)

    monkeypatch.setattr("backend.app.services.qa_service.logger", FakeLogger())
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_TELEMETRY_ENABLED", True
    )

    _emit_rag_telemetry({"event": "rag_telemetry", "outcome": "success"})

    assert len(events) == 1
    assert "rag_telemetry " in events[0]


@pytest.mark.anyio
async def test_rewrite_query_returns_rewritten_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: object) -> SimpleNamespace:
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(
                                    content="Redis production configuration settings\nextra line"
                                )
                            )
                        ]
                    )

    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_QUERY_REWRITE_ENABLED", True
    )

    rewritten = await _rewrite_query("那生产环境怎么写？", [], None)

    assert rewritten == "Redis production configuration settings"


@pytest.mark.anyio
async def test_rewrite_query_falls_back_to_original_on_empty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: object) -> SimpleNamespace:
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(message=SimpleNamespace(content="  \n  "))
                        ]
                    )

    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_QUERY_REWRITE_ENABLED", True
    )

    rewritten = await _rewrite_query("那生产环境怎么写？", [], None)

    assert rewritten == "那生产环境怎么写？"


@pytest.mark.anyio
async def test_rewrite_query_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_QUERY_REWRITE_ENABLED", False
    )

    rewritten = await _rewrite_query("那生产环境怎么写？", [], None)

    assert rewritten == "那生产环境怎么写？"


@pytest.mark.anyio
async def test_create_conversation_rejects_missing_knowledge_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_knowledge_base_by_id(db: object, kb_id: int):
        return None

    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_base_by_id",
        fake_get_knowledge_base_by_id,
    )

    with pytest.raises(ConversationCreationError) as exc_info:
        await create_conversation(object(), user_id=7, knowledge_base_id=11)

    assert exc_info.value.code == "knowledge_base_not_found"


@pytest.mark.anyio
async def test_create_conversation_rejects_not_ready_knowledge_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_knowledge_base_by_id(db: object, kb_id: int):
        return SimpleNamespace(
            id=kb_id, user_id=7, status=KnowledgeBaseStatus.PROCESSING
        )

    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_base_by_id",
        fake_get_knowledge_base_by_id,
    )

    with pytest.raises(ConversationCreationError) as exc_info:
        await create_conversation(object(), user_id=7, knowledge_base_id=11)

    assert exc_info.value.code == "knowledge_base_not_ready"


@pytest.mark.anyio
async def test_create_conversation_binds_knowledge_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_knowledge_base_by_id(db: object, kb_id: int):
        return SimpleNamespace(
            id=kb_id,
            user_id=7,
            status=KnowledgeBaseStatus.DONE,
            name="Test KB",
            source_url="http://example.com",
        )

    async def fake_create_conversation_with_scope(
        db: object,
        user_id: int,
        scope_items: list[dict],
    ):
        return SimpleNamespace(
            id="conv_1",
            user_id=user_id,
            knowledge_base_id=scope_items[0]["knowledge_base_id"],
        )

    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_base_by_id",
        fake_get_knowledge_base_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_conversation_with_scope",
        fake_create_conversation_with_scope,
    )

    conv = await create_conversation(object(), user_id=7, knowledge_base_id=11)

    assert conv.knowledge_base_id == 11


@pytest.mark.anyio
async def test_stream_answer_suppresses_debug_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    chunk = _chunk(1, "Redis production configuration")
    events = []

    async def fake_get_conversation_by_id(db: object, requested_conv_id: uuid.UUID):
        return SimpleNamespace(
            id=conv_id, user_id=7, knowledge_base_id=11, summary=None, message_count=0
        )

    async def fake_get_recent_messages(
        db: object, requested_conv_id: uuid.UUID, limit: int
    ):
        return []

    async def fake_generate_embeddings(texts: list[str]):
        return [[0.1] * 1536]

    async def fake_vector_search(
        db: object, user_id: int, knowledge_base_id: int, query_vec: list[float]
    ):
        return [chunk]

    async def fake_fts_search(
        db: object, user_id: int, knowledge_base_id: int, query: str
    ):
        return []

    async def fake_rerank(query: str, chunks: list[DocumentChunk]):
        return chunks, [0.9] * len(chunks), 0.9

    async def fake_create_message(*args: object, **kwargs: object):
        return SimpleNamespace(id="msg_1")

    async def fake_update_conversation_title(*args: object, **kwargs: object):
        return None

    class FakeStream:
        def __aiter__(self):
            self._chunks = [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="答案[1]"))]
                )
            ]
            return self

        async def __anext__(self):
            if not self._chunks:
                raise StopAsyncIteration
            return self._chunks.pop(0)

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: object):
                    if kwargs.get("stream"):
                        return FakeStream()
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content="MICRO_RETRIEVAL")
                            )
                        ]
                    )

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        fake_get_conversation_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        fake_get_recent_messages,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.generate_embeddings", fake_generate_embeddings
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._vector_search", fake_vector_search
    )
    monkeypatch.setattr("backend.app.services.qa_service._fts_search", fake_fts_search)
    monkeypatch.setattr("backend.app.services.qa_service._rerank", fake_rerank)
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_message",
        fake_create_message,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.update_conversation_title",
        fake_update_conversation_title,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_QUERY_REWRITE_ENABLED", False
    )
    monkeypatch.setattr("backend.app.services.qa_service.settings.DEBUG", True)

    async for event in stream_answer(
        object(), conv_id, 7, "Redis 生产环境怎么配？", debug=False
    ):
        events.append(event)

    assert [event["type"] for event in events] == ["ping", "token", "citations", "done"]


@pytest.mark.anyio
async def test_stream_answer_emits_debug_events_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    vector_chunk = _chunk(1, "Redis production configuration")
    fts_chunk = _chunk(2, "Redis persistence settings")
    events = []

    async def fake_get_conversation_by_id(db: object, requested_conv_id: uuid.UUID):
        return SimpleNamespace(
            id=conv_id, user_id=7, knowledge_base_id=11, summary=None, message_count=0
        )

    async def fake_get_recent_messages(
        db: object, requested_conv_id: uuid.UUID, limit: int
    ):
        return []

    async def fake_rewrite_query(
        question: str, recent: list[object], summary: str | None
    ):
        return "Redis production configuration settings"

    async def fake_generate_embeddings(texts: list[str]):
        return [[0.1] * 1536]

    async def fake_vector_search(
        db: object, user_id: int, knowledge_base_id: int, query_vec: list[float]
    ):
        return [vector_chunk]

    async def fake_fts_search(
        db: object, user_id: int, knowledge_base_id: int, query: str
    ):
        return [fts_chunk]

    async def fake_rerank(query: str, chunks: list[DocumentChunk]):
        reordered = [chunks[1], chunks[0]]
        return reordered, [0.9, 0.8], 0.9

    async def fake_create_message(*args: object, **kwargs: object):
        return SimpleNamespace(id="msg_1")

    async def fake_update_conversation_title(*args: object, **kwargs: object):
        return None

    class FakeStream:
        def __aiter__(self):
            self._chunks = [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="答案[1][2]"))
                    ]
                )
            ]
            return self

        async def __anext__(self):
            if not self._chunks:
                raise StopAsyncIteration
            return self._chunks.pop(0)

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: object):
                    if kwargs.get("stream"):
                        return FakeStream()
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content="MICRO_RETRIEVAL")
                            )
                        ]
                    )

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        fake_get_conversation_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        fake_get_recent_messages,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._rewrite_query", fake_rewrite_query
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.generate_embeddings", fake_generate_embeddings
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._vector_search", fake_vector_search
    )
    monkeypatch.setattr("backend.app.services.qa_service._fts_search", fake_fts_search)
    monkeypatch.setattr("backend.app.services.qa_service._rerank", fake_rerank)
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_message",
        fake_create_message,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.update_conversation_title",
        fake_update_conversation_title,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: FakeClient()
    )
    monkeypatch.setattr("backend.app.services.qa_service.settings.DEBUG", True)
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_DEBUG_ENABLED", True
    )

    async for event in stream_answer(
        object(), conv_id, 7, "Redis 生产环境怎么配？", debug=True
    ):
        events.append(event)

    assert [event["type"] for event in events] == [
        "ping",
        "debug",
        "debug",
        "debug",
        "debug",
        "token",
        "debug",
        "citations",
        "done",
    ]
    assert [event["stage"] for event in events if event["type"] == "debug"] == [
        "query_rewrite",
        "embedding",
        "retrieval",
        "rerank",
        "citations",
    ]
    retrieval_event = next(
        event for event in events if event.get("stage") == "retrieval"
    )
    assert retrieval_event["data"]["vector_candidates_count"] == 1
    assert retrieval_event["data"]["fts_candidates_count"] == 1
    assert retrieval_event["data"]["merged_candidates_count"] == 2
    rerank_event = next(event for event in events if event.get("stage") == "rerank")
    assert rerank_event["data"]["rerank_candidates_count"] == 2
    assert rerank_event["data"]["top_chunks_preview"][0]["chunk_id"] == "2"


@pytest.mark.anyio
async def test_stream_answer_emits_terminal_error_debug_before_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    chunk = _chunk(1, "Redis production configuration")
    events = []

    async def fake_get_conversation_by_id(db: object, requested_conv_id: uuid.UUID):
        return SimpleNamespace(
            id=conv_id, user_id=7, knowledge_base_id=11, summary=None, message_count=0
        )

    async def fake_get_recent_messages(
        db: object, requested_conv_id: uuid.UUID, limit: int
    ):
        return []

    async def fake_generate_embeddings(texts: list[str]):
        return [[0.1] * 1536]

    async def fake_vector_search(
        db: object, user_id: int, knowledge_base_id: int, query_vec: list[float]
    ):
        return [chunk]

    async def fake_fts_search(
        db: object, user_id: int, knowledge_base_id: int, query: str
    ):
        return []

    async def fake_rerank(query: str, chunks: list[DocumentChunk]):
        return [], [], None

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: object):
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content="MICRO_RETRIEVAL")
                            )
                        ]
                    )

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        fake_get_conversation_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        fake_get_recent_messages,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.generate_embeddings", fake_generate_embeddings
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._vector_search", fake_vector_search
    )
    monkeypatch.setattr("backend.app.services.qa_service._fts_search", fake_fts_search)
    monkeypatch.setattr("backend.app.services.qa_service._rerank", fake_rerank)
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_QUERY_REWRITE_ENABLED", False
    )
    monkeypatch.setattr("backend.app.services.qa_service.settings.DEBUG", True)
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_DEBUG_ENABLED", True
    )

    async for event in stream_answer(
        object(), conv_id, 7, "Redis 生产环境怎么配？", debug=True
    ):
        events.append(event)

    assert events[0]["type"] == "ping"
    assert events[-1]["type"] == "error"
    assert all(event["type"] == "debug" for event in events[1:-1])
    assert events[-2]["stage"] == "terminal_error"
    assert events[-2]["data"]["error_code"] == "no_relevant_context"
    assert events[-1]["message"] == "根据已有文档，无法回答该问题"


@pytest.mark.anyio
async def test_stream_answer_blocks_debug_events_when_app_debug_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    chunk = _chunk(1, "Redis production configuration")
    events = []

    async def fake_get_conversation_by_id(db: object, requested_conv_id: uuid.UUID):
        return SimpleNamespace(
            id=conv_id, user_id=7, knowledge_base_id=11, summary=None, message_count=0
        )

    async def fake_get_recent_messages(
        db: object, requested_conv_id: uuid.UUID, limit: int
    ):
        return []

    async def fake_generate_embeddings(texts: list[str]):
        return [[0.1] * 1536]

    async def fake_vector_search(
        db: object, user_id: int, knowledge_base_id: int, query_vec: list[float]
    ):
        return [chunk]

    async def fake_fts_search(
        db: object, user_id: int, knowledge_base_id: int, query: str
    ):
        return []

    async def fake_rerank(query: str, chunks: list[DocumentChunk]):
        return chunks, [0.9] * len(chunks), 0.9

    async def fake_create_message(*args: object, **kwargs: object):
        return SimpleNamespace(id="msg_1")

    async def fake_update_conversation_title(*args: object, **kwargs: object):
        return None

    class FakeStream:
        def __aiter__(self):
            self._chunks = [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="答案[1]"))]
                )
            ]
            return self

        async def __anext__(self):
            if not self._chunks:
                raise StopAsyncIteration
            return self._chunks.pop(0)

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs: object):
                    if kwargs.get("stream"):
                        return FakeStream()
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content="MICRO_RETRIEVAL")
                            )
                        ]
                    )

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        fake_get_conversation_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        fake_get_recent_messages,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.generate_embeddings", fake_generate_embeddings
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._vector_search", fake_vector_search
    )
    monkeypatch.setattr("backend.app.services.qa_service._fts_search", fake_fts_search)
    monkeypatch.setattr("backend.app.services.qa_service._rerank", fake_rerank)
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_message",
        fake_create_message,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.update_conversation_title",
        fake_update_conversation_title,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: FakeClient()
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.settings.RAG_QUERY_REWRITE_ENABLED", False
    )
    monkeypatch.setattr("backend.app.services.qa_service.settings.DEBUG", False)

    async for event in stream_answer(
        object(), conv_id, 7, "Redis 生产环境怎么配？", debug=False
    ):
        events.append(event)

    assert [event["type"] for event in events] == ["ping", "token", "citations", "done"]


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
    preview_limited = _debug_chunk_preview_with_score([chunk1, chunk2], scores, limit=1)
    assert len(preview_limited) == 1
