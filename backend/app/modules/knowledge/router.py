import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.response import Response
from backend.app.core.security import get_current_user
from backend.app.db import get_db
from backend.app.models.knowledge_base import KnowledgeBaseStatus
from backend.app.schemas.knowledge import (
    CreateKnowledgeRequest,
    CreateKnowledgeResponse,
    KnowledgeBaseListItem,
    KnowledgeStatusResponse,
)
from backend.app.services import knowledge_service
from backend.app.tasks.knowledge_tasks import ingest_knowledge

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.post("", response_model=Response[CreateKnowledgeResponse], status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    body: CreateKnowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[CreateKnowledgeResponse]:
    task_id = str(uuid.uuid4())
    result = await knowledge_service.create_knowledge_base(
        db=db,
        source_url=str(body.source_url),
        name=body.name,
        user_id=int(current_user_id),
        task_id=task_id,
    )
    try:
        ingest_knowledge.delay(result.knowledge_base_id, task_id, str(body.source_url))
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Celery task enqueue failed: %s", exc)
        await knowledge_service.update_knowledge_status(
            db,
            result.knowledge_base_id,
            KnowledgeBaseStatus.FAILED,
            "任务入队失败，请稍后重试",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge ingestion task enqueue failed",
        ) from exc
    return Response.success(data=result)


@router.get("", response_model=Response[list[KnowledgeBaseListItem]])
async def list_knowledge(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[list[KnowledgeBaseListItem]]:
    result = await knowledge_service.list_knowledge_bases(db, int(current_user_id))
    return Response.success(data=result)


@router.get("/{kb_id}/status", response_model=Response[KnowledgeStatusResponse])
async def get_knowledge_status(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[KnowledgeStatusResponse]:
    result = await knowledge_service.get_knowledge_status(db, kb_id, int(current_user_id))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return Response.success(data=result)


@router.delete("/{kb_id}", response_model=Response[None])
async def delete_knowledge(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[None]:
    await knowledge_service.delete_knowledge_base(db, kb_id, int(current_user_id))
    return Response.success(msg="删除成功")
