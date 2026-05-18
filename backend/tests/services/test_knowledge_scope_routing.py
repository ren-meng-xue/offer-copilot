import uuid
from unittest.mock import AsyncMock

import pytest
from types import SimpleNamespace
from backend.app.models.knowledge_base import KnowledgeBaseStatus
from backend.app.services.qa_service import (
    create_conversation,
    route_knowledge_scope,
    stream_answer,
    ScopeRouteCandidate,
)


@pytest.mark.anyio
async def test_route_knowledge_scope_limits_to_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 准备 4 个已完成的知识库
    kbs = [
        SimpleNamespace(
            id=i,
            name=f"KB {i}",
            summary=f"Summary {i}",
            source_url=f"http://kb{i}.com",
            updated_at=i,
            status=KnowledgeBaseStatus.DONE,
            user_id=1,
        )
        for i in range(1, 5)
    ]

    async def fake_list_done_knowledge_bases_by_user(db: object, user_id: int):
        return kbs

    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.list_done_knowledge_bases_by_user",
        fake_list_done_knowledge_bases_by_user,
    )

    # 模拟评分逻辑，让每个库都命中
    def fake_score(question, kb):
        return ScopeRouteCandidate(kb, 1.0, "Matched")

    monkeypatch.setattr(
        "backend.app.services.qa_service._score_knowledge_base_for_question",
        fake_score,
    )

    selected = await route_knowledge_scope(AsyncMock(), user_id=1, question="test")

    assert len(selected) == 3
    assert [c.knowledge_base.id for c in selected] == [4, 3, 2]  # 按 updated_at 倒序


@pytest.mark.anyio
async def test_create_conversation_binds_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    kb = SimpleNamespace(
        id=1,
        name="Test KB",
        source_url="http://test.com",
        status=KnowledgeBaseStatus.DONE,
        user_id=1,
    )

    async def fake_route_knowledge_scope(db, user_id, question):
        return [ScopeRouteCandidate(kb, 1.0, "Matched")]

    async def fake_create_conversation_with_scope(db, user_id, scope_items):
        return SimpleNamespace(id=uuid.uuid4(), user_id=user_id)

    monkeypatch.setattr(
        "backend.app.services.qa_service.route_knowledge_scope",
        fake_route_knowledge_scope,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_conversation_with_scope",
        fake_create_conversation_with_scope,
    )

    conv = await create_conversation(AsyncMock(), user_id=1, question="what is this?")
    assert conv is not None


@pytest.mark.anyio
async def test_stream_answer_prevents_re_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    # 模拟一个已经有 Scope 的会话
    conv = SimpleNamespace(
        id=conv_id, user_id=1, knowledge_base_id=None, summary=None, message_count=1
    )

    scope_item = SimpleNamespace(
        knowledge_base_id=1,
        knowledge_base_name_snapshot="KB 1",
        source_url_snapshot="http://kb1.com",
        route_score=1.0,
        route_reason="Matched",
    )

    async def fake_get_conversation_by_id(db, requested_conv_id):
        return conv

    async def fake_list_scope_items_by_conversation_id(db, cid):
        return [scope_item]

    async def fake_get_knowledge_bases_by_ids(db, ids):
        return [
            SimpleNamespace(
                id=1, user_id=1, status=KnowledgeBaseStatus.DONE, summary="KB Summary"
            )
        ]

    # Mock 其他必要的 RAG 环节
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        fake_get_conversation_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.list_scope_items_by_conversation_id",
        fake_list_scope_items_by_conversation_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_bases_by_ids",
        fake_get_knowledge_bases_by_ids,
    )

    # 核心：确保 route_knowledge_scope 没被调用
    route_mock = AsyncMock()
    monkeypatch.setattr(
        "backend.app.services.qa_service.route_knowledge_scope", route_mock
    )

    # Mock 意图识别和检索，让它快点跑完
    monkeypatch.setattr(
        "backend.app.services.qa_service._is_kb_listing", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._classify_retrieval_intent",
        AsyncMock(return_value="MICRO_RETRIEVAL"),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._rewrite_query",
        AsyncMock(return_value="query"),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.generate_embeddings",
        AsyncMock(return_value=[[0.1] * 1536]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._vector_search_scope",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=1,
                    content="...",
                    source_url="...",
                    heading_path="...",
                    knowledge_base_id=1,
                )
            ]
        ),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._rerank",
        AsyncMock(
            return_value=(
                [
                    SimpleNamespace(
                        id=1,
                        content="...",
                        source_url="...",
                        heading_path="...",
                        knowledge_base_id=1,
                    )
                ],
                [1.0],
            )
        ),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_message", AsyncMock()
    )

    # Mock OpenAI
    class FakeStream:
        async def __aiter__(self):
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="Answer[1]"))]
            )

        async def __anext__(self):
            raise StopAsyncIteration

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create.return_value = FakeStream()
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: mock_openai
    )

    async for _ in stream_answer(AsyncMock(), conv_id, user_id=1, question="next?"):
        pass

    # 验证没有调用路由算法
    route_mock.assert_not_called()


@pytest.mark.anyio
async def test_stream_answer_triggers_delayed_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    # 模拟一个没有 Scope 的会话（比如第一问是你好）
    conv = SimpleNamespace(
        id=conv_id, user_id=1, knowledge_base_id=None, summary=None, message_count=1
    )

    async def fake_get_conversation_by_id(db, requested_conv_id):
        return conv

    async def fake_list_scope_items_by_conversation_id(db, cid):
        # 第一次调用返回空，第二次（路由后）返回匹配项
        if not hasattr(fake_list_scope_items_by_conversation_id, "called"):
            fake_list_scope_items_by_conversation_id.called = True
            return []
        return [
            SimpleNamespace(
                knowledge_base_id=1,
                knowledge_base_name_snapshot="KB 1",
                source_url_snapshot="http://kb1.com",
                route_score=1.0,
                route_reason="Matched",
            )
        ]

    async def fake_get_knowledge_bases_by_ids(db, ids):
        return [
            SimpleNamespace(
                id=1, user_id=1, status=KnowledgeBaseStatus.DONE, summary="KB Summary"
            )
        ]

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        fake_get_conversation_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.list_scope_items_by_conversation_id",
        fake_list_scope_items_by_conversation_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_bases_by_ids",
        fake_get_knowledge_bases_by_ids,
    )

    # 模拟路由成功
    kb = SimpleNamespace(
        id=1,
        name="KB 1",
        source_url="http://kb1.com",
        updated_at=1,
        status=KnowledgeBaseStatus.DONE,
        user_id=1,
        summary="KB Summary",
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.route_knowledge_scope",
        AsyncMock(return_value=[ScopeRouteCandidate(kb, 1.0, "Matched")]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.add_scope_items_to_conversation",
        AsyncMock(),
    )

    # Mock 意图识别和检索，让它快点跑完
    monkeypatch.setattr(
        "backend.app.services.qa_service._is_kb_listing", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._classify_retrieval_intent",
        AsyncMock(return_value="MICRO_RETRIEVAL"),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._rewrite_query",
        AsyncMock(return_value="query"),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.generate_embeddings",
        AsyncMock(return_value=[[0.1] * 1536]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._vector_search_scope",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=1,
                    content="...",
                    source_url="...",
                    heading_path="...",
                    knowledge_base_id=1,
                )
            ]
        ),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._rerank",
        AsyncMock(
            return_value=(
                [
                    SimpleNamespace(
                        id=1,
                        content="...",
                        source_url="...",
                        heading_path="...",
                        knowledge_base_id=1,
                    )
                ],
                [1.0],
            )
        ),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_message", AsyncMock()
    )

    # Mock OpenAI
    class FakeStream:
        async def __aiter__(self):
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="Answer[1]"))]
            )

        async def __anext__(self):
            raise StopAsyncIteration

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create.return_value = FakeStream()
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: mock_openai
    )

    async for _ in stream_answer(
        AsyncMock(), conv_id, user_id=1, question="test delayed routing"
    ):
        pass

    # 验证触发了路由
    from backend.app.services.qa_service import route_knowledge_scope

    assert route_knowledge_scope.called


@pytest.mark.anyio
async def test_stream_answer_supports_macro_summary_answering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    conv = SimpleNamespace(
        id=conv_id, user_id=1, knowledge_base_id=None, summary=None, message_count=1
    )

    scope_item = SimpleNamespace(
        knowledge_base_id=1,
        knowledge_base_name_snapshot="KB 1",
        source_url_snapshot="http://kb1.com",
        route_score=1.0,
        route_reason="Matched",
    )

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        AsyncMock(return_value=conv),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.list_scope_items_by_conversation_id",
        AsyncMock(return_value=[scope_item]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_bases_by_ids",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=1,
                    user_id=1,
                    status=KnowledgeBaseStatus.DONE,
                    summary="KB Summary",
                )
            ]
        ),
    )

    # 模拟 MACRO 意图
    monkeypatch.setattr(
        "backend.app.services.qa_service._is_kb_listing", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._classify_retrieval_intent",
        AsyncMock(return_value="MACRO_RETRIEVAL"),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_message", AsyncMock()
    )

    # Mock OpenAI - 返回包含知识库名称的回答
    class FakeStream:
        async def __aiter__(self):
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="根据《KB 1》的摘要...")
                    )
                ]
            )

        async def __anext__(self):
            raise StopAsyncIteration

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create.return_value = FakeStream()
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: mock_openai
    )

    events = []
    async for event in stream_answer(
        AsyncMock(), conv_id, user_id=1, question="summary?"
    ):
        events.append(event)

    # 验证生成了引用（即使没有 chunks）
    assert any(e.get("type") == "citations" for e in events)
    citations = next(e["data"] for e in events if e.get("type") == "citations")
    assert citations[0]["knowledge_base_name"] == "KB 1"
    assert citations[0]["heading_path"] == "全局摘要"


@pytest.mark.anyio
async def test_resolve_conversation_scope_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services.qa_service import _resolve_conversation_scope

    conv_id = uuid.uuid4()
    # 模拟旧会话，没有 scope items 但有 knowledge_base_id
    conv = SimpleNamespace(id=conv_id, user_id=1, knowledge_base_id=101)

    async def fake_list_scope_items_by_conversation_id(db, cid):
        return []  # 没有新 Scope Items

    async def fake_get_knowledge_base_by_id(db, kb_id):
        return SimpleNamespace(
            id=kb_id,
            user_id=1,
            name="Legacy KB",
            source_url="http://legacy.com",
            status=KnowledgeBaseStatus.DONE,
            summary="Legacy Summary",
        )

    async def fake_get_knowledge_bases_by_ids(db, ids):
        return [
            SimpleNamespace(
                id=101,
                user_id=1,
                status=KnowledgeBaseStatus.DONE,
                summary="Legacy Summary",
            )
        ]

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.list_scope_items_by_conversation_id",
        fake_list_scope_items_by_conversation_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_base_by_id",
        fake_get_knowledge_base_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.get_knowledge_bases_by_ids",
        fake_get_knowledge_bases_by_ids,
    )

    scope = await _resolve_conversation_scope(AsyncMock(), conv, user_id=1)

    assert len(scope) == 1
    assert scope[0].knowledge_base_id == 101
    assert scope[0].name == "Legacy KB"


@pytest.mark.anyio
async def test_stream_answer_handles_empty_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv_id = uuid.uuid4()
    conv = SimpleNamespace(
        id=conv_id, user_id=1, knowledge_base_id=None, summary=None, message_count=1
    )

    async def fake_get_conversation_by_id(db, requested_conv_id):
        return conv

    async def fake_list_scope_items_by_conversation_id(db, cid):
        return []  # 空 Scope

    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_conversation_by_id",
        fake_get_conversation_by_id,
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.list_scope_items_by_conversation_id",
        fake_list_scope_items_by_conversation_id,
    )

    # Mock 路由相关调用，使其返回空（模拟匹配失败）
    monkeypatch.setattr(
        "backend.app.services.qa_service.knowledge_repository.list_done_knowledge_bases_by_user",
        AsyncMock(return_value=[]),
    )

    # mock get_recent_messages 和意图识别
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.get_recent_messages",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._is_kb_listing", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service._classify_retrieval_intent",
        AsyncMock(return_value="MICRO_RETRIEVAL"),
    )
    monkeypatch.setattr(
        "backend.app.services.qa_service.qa_repository.create_message", AsyncMock()
    )

    class FakeStream:
        async def __aiter__(self):
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="通用回复"))]
            )

        async def __anext__(self):
            raise StopAsyncIteration

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create.return_value = FakeStream()
    monkeypatch.setattr(
        "backend.app.services.qa_service._openai_client", lambda: mock_openai
    )

    events = []
    async for event in stream_answer(
        AsyncMock(), conv_id, user_id=1, question="empty?"
    ):
        events.append(event)

    # 空路由时降级为通用回复，应有 no_citations_required + done，不应有错误
    assert any(e.get("type") == "no_citations_required" for e in events)
    assert any(e.get("type") == "done" for e in events)
    assert not any(e.get("type") == "error" for e in events)
