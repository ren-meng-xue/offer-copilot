from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus
from backend.app.repositories import knowledge_repository
from backend.app.schemas.knowledge import (
    CreateKnowledgeResponse,
    KnowledgeBaseListItem,
    KnowledgeStatusResponse,
)


def _default_name(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    return path.split("/")[-1] or parsed.netloc or source_url


# 创建知识库，写入数据库并返回知识库 ID；异步任务由路由层触发。
async def create_knowledge_base(
    db: AsyncSession,
    source_url: str,
    name: str | None,
    user_id: int,
    task_id: str,
    source_type: str = "url",
) -> CreateKnowledgeResponse:
    kb = KnowledgeBase(
        user_id=user_id,
        name=name or _default_name(source_url),
        source_url=source_url,
        source_type=source_type,
        status=KnowledgeBaseStatus.PENDING,
    )
    kb = await knowledge_repository.create_knowledge_base(db, kb)

    return CreateKnowledgeResponse(
        knowledge_base_id=kb.id,
        task_id=task_id,
        status=KnowledgeBaseStatus.PENDING,
    )


# 查询知识库状态，返回当前进度和错误信息。
async def get_knowledge_status(
    db: AsyncSession, kb_id: int, user_id: int
) -> KnowledgeStatusResponse | None:
    kb = await knowledge_repository.get_knowledge_base_by_id(db, kb_id)
    if kb is None or kb.user_id != user_id:
        return None
    return KnowledgeStatusResponse(
        knowledge_base_id=kb.id,
        status=kb.status,
        error_message=kb.error_message,
    )


async def list_knowledge_bases(
    db: AsyncSession, user_id: int
) -> list[KnowledgeBaseListItem]:
    """返回当前用户创建的知识库列表，供前端知识库页面展示。"""

    knowledge_bases = await knowledge_repository.list_knowledge_bases_by_user(
        db, user_id
    )
    return [
        KnowledgeBaseListItem(
            knowledge_base_id=kb.id,
            name=kb.name,
            source_url=kb.source_url,
            status=kb.status,
            error_message=kb.error_message,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )
        for kb in knowledge_bases
    ]


async def delete_knowledge_base(db: AsyncSession, kb_id: int, user_id: int) -> None:
    kb = await knowledge_repository.get_knowledge_base_by_id(db, kb_id)
    if kb is None or kb.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )
    if kb.status in {KnowledgeBaseStatus.PENDING, KnowledgeBaseStatus.PROCESSING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Knowledge base is still processing",
        )
    await knowledge_repository.delete_knowledge_base(db, kb)


async def update_knowledge_status(
    db: AsyncSession,
    kb_id: int,
    status: KnowledgeBaseStatus,
    error_message: str | None = None,
) -> None:
    """更新知识库状态，供同步接口处理任务入队失败等边界情况。"""

    await knowledge_repository.update_knowledge_base_status(
        db, kb_id, status, error_message
    )
