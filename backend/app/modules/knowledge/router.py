import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
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
from backend.app.services.storage_service import storage_service
from backend.app.tasks.knowledge_tasks import ingest_knowledge

logger = logging.getLogger(__name__)

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
        source_type="url",
    )
    try:
        ingest_knowledge.delay(result.knowledge_base_id, task_id, str(body.source_url), int(current_user_id))
    except Exception as exc:
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


@router.post("/upload", response_model=Response[CreateKnowledgeResponse], status_code=status.HTTP_201_CREATED)
async def upload_knowledge(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[CreateKnowledgeResponse]:
    # 1. 上传文件到云存储
    try:
        # 保持原始文件名，但在前面加一个 uuid 防止冲突
        file_key = f"kb/{uuid.uuid4()}_{file.filename}"
        file_url = await storage_service.upload_file(file.file, file_key)
    except Exception as e:
        logger.exception(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # 2. 创建知识库记录
    task_id = str(uuid.uuid4())
    result = await knowledge_service.create_knowledge_base(
        db=db,
        source_url=file_url,
        name=name or file.filename,
        user_id=int(current_user_id),
        task_id=task_id,
        source_type="file",
    )

    # 3. 触发异步解析任务
    try:
        ingest_knowledge.delay(result.knowledge_base_id, task_id, file_url, int(current_user_id))
    except Exception as exc:
        logger.exception("Celery task enqueue failed: %s", exc)
        raise HTTPException(status_code=503, detail="Task queue failed")

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


@router.get("/{kb_id}/raw", response_model=Response[None])
async def delete_knowledge(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[None]:
    await knowledge_service.delete_knowledge_base(db, kb_id, int(current_user_id))
    return Response.success(msg="删除成功")
