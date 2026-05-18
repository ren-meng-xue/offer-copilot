from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from backend.app.models.knowledge_base import KnowledgeBaseStatus
from backend.app.services import knowledge_service


@pytest.mark.asyncio
async def test_delete_knowledge_base_succeeds_for_done_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    kb = SimpleNamespace(id=1, user_id=7, status=KnowledgeBaseStatus.DONE)
    delete_mock = AsyncMock()

    monkeypatch.setattr(
        knowledge_service.knowledge_repository,
        "get_knowledge_base_by_id",
        AsyncMock(return_value=kb),
    )
    monkeypatch.setattr(
        knowledge_service.knowledge_repository, "delete_knowledge_base", delete_mock
    )

    await knowledge_service.delete_knowledge_base(db, 1, 7)

    delete_mock.assert_awaited_once_with(db, kb)


@pytest.mark.asyncio
async def test_delete_knowledge_base_rejects_processing_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    kb = SimpleNamespace(id=1, user_id=7, status=KnowledgeBaseStatus.PROCESSING)

    monkeypatch.setattr(
        knowledge_service.knowledge_repository,
        "get_knowledge_base_by_id",
        AsyncMock(return_value=kb),
    )

    with pytest.raises(HTTPException) as exc_info:
        await knowledge_service.delete_knowledge_base(db, 1, 7)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_delete_knowledge_base_hides_other_users_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    kb = SimpleNamespace(id=1, user_id=8, status=KnowledgeBaseStatus.DONE)

    monkeypatch.setattr(
        knowledge_service.knowledge_repository,
        "get_knowledge_base_by_id",
        AsyncMock(return_value=kb),
    )

    with pytest.raises(HTTPException) as exc_info:
        await knowledge_service.delete_knowledge_base(db, 1, 7)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
