from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.app.modules.knowledge import router as knowledge_router


@pytest.mark.asyncio
async def test_delete_knowledge_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    delete_mock = AsyncMock()
    monkeypatch.setattr(knowledge_router.knowledge_service, "delete_knowledge_base", delete_mock)

    response = await knowledge_router.delete_knowledge(5, db=SimpleNamespace(), current_user_id="7")

    delete_mock.assert_awaited_once()
    assert response.msg == "删除成功"


@pytest.mark.asyncio
async def test_delete_knowledge_propagates_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    delete_mock = AsyncMock(side_effect=HTTPException(status_code=409, detail="Knowledge base is still processing"))
    monkeypatch.setattr(knowledge_router.knowledge_service, "delete_knowledge_base", delete_mock)

    with pytest.raises(HTTPException) as exc_info:
        await knowledge_router.delete_knowledge(5, db=SimpleNamespace(), current_user_id="7")

    assert exc_info.value.status_code == 409
