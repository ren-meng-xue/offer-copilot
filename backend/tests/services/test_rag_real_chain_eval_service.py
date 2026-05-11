from types import SimpleNamespace

import pytest

from backend.app.services.rag_eval_service import RagEvalCase, RagEvalTurn
from backend.app.services.rag_real_chain_eval_service import (
    _history_to_messages,
    _resolve_knowledge_base_for_case,
    observe_eval_case,
)


def _case() -> RagEvalCase:
    return RagEvalCase(
        id="case_1",
        category="rewrite",
        knowledge_base_id=123,
        knowledge_base_name=None,
        knowledge_base_source_url="https://redis.io/docs/latest/operate/oss_and_stack/management/config/",
        history=[
            RagEvalTurn(role="user", content="Redis 怎么配置？"),
            RagEvalTurn(role="assistant", content="先看安装章节。[1]"),
        ],
        question="那生产环境怎么写？",
        expected_mode="answer",
        expected_retrieval_query_contains=["Redis", "production"],
        expected_answer_contains=["redis"],
        expected_citation_urls=["https://redis.io/docs"],
    )


def test_history_to_messages_preserves_turn_order() -> None:
    messages = _history_to_messages(_case())

    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "Redis 怎么配置？"


@pytest.mark.anyio
async def test_resolve_knowledge_base_prefers_source_url(monkeypatch: pytest.MonkeyPatch) -> None:
    kb = SimpleNamespace(id=88, user_id=7, status=SimpleNamespace(value="done"))

    async def fake_get_by_source_url(db: object, source_url: str):
        assert source_url == _case().knowledge_base_source_url
        return kb

    async def fail_get_by_name(db: object, name: str):
        raise AssertionError("name lookup should not run")

    async def fail_get_by_id(db: object, kb_id: int):
        raise AssertionError("id lookup should not run")

    monkeypatch.setattr(
        "backend.app.services.rag_real_chain_eval_service.knowledge_repository.get_knowledge_base_by_source_url",
        fake_get_by_source_url,
    )
    monkeypatch.setattr(
        "backend.app.services.rag_real_chain_eval_service.knowledge_repository.get_latest_knowledge_base_by_name",
        fail_get_by_name,
    )
    monkeypatch.setattr(
        "backend.app.services.rag_real_chain_eval_service.knowledge_repository.get_knowledge_base_by_id",
        fail_get_by_id,
    )

    resolved = await _resolve_knowledge_base_for_case(object(), _case())

    assert resolved is kb


@pytest.mark.anyio
async def test_observe_eval_case_returns_scope_unresolved_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_by_source_url(db: object, source_url: str):
        return None

    async def fail_get_by_id(db: object, kb_id: int):
        raise AssertionError("id lookup should not run when source_url is provided")

    monkeypatch.setattr(
        "backend.app.services.rag_real_chain_eval_service.knowledge_repository.get_knowledge_base_by_source_url",
        fake_get_by_source_url,
    )
    monkeypatch.setattr(
        "backend.app.services.rag_real_chain_eval_service.knowledge_repository.get_latest_knowledge_base_by_name",
        fake_get_by_source_url,
    )
    monkeypatch.setattr(
        "backend.app.services.rag_real_chain_eval_service.knowledge_repository.get_knowledge_base_by_id",
        fail_get_by_id,
    )

    observed = await observe_eval_case(object(), _case())

    assert observed.outcome == "error"
    assert observed.error_code == "fixture_scope_unresolved"


@pytest.mark.anyio
async def test_observe_eval_case_returns_not_ready_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_by_source_url(db: object, source_url: str):
        return SimpleNamespace(id=123, user_id=7, status=SimpleNamespace(value="processing"))

    monkeypatch.setattr(
        "backend.app.services.rag_real_chain_eval_service.knowledge_repository.get_knowledge_base_by_source_url",
        fake_get_by_source_url,
    )

    observed = await observe_eval_case(object(), _case())

    assert observed.outcome == "error"
    assert observed.error_code == "knowledge_base_not_ready"
