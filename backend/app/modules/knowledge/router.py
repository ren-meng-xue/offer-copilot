import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.response import Response
from backend.app.core.security import get_current_user
from backend.app.db import get_db
from backend.app.schemas.knowledge import CreateKnowledgeRequest, CreateKnowledgeResponse, KnowledgeStatusResponse
from backend.app.services import knowledge_service
from backend.app.tasks.knowledge_tasks import ingest_knowledge

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.post("", response_model=Response[CreateKnowledgeResponse], status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    body: CreateKnowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[CreateKnowledgeResponse]:
    result = await knowledge_service.create_knowledge_base(
        db=db,
        source_url=str(body.source_url),
        name=body.name,
        user_id=int(current_user_id),
    )
    task_id = str(uuid.uuid4())
    ingest_knowledge.delay(result.knowledge_base_id, task_id, str(body.source_url))
    return Response.success(data=result)


@router.get("/{kb_id}/status", response_model=Response[KnowledgeStatusResponse])
async def get_knowledge_status(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response[KnowledgeStatusResponse]:
    result = await knowledge_service.get_knowledge_status(db, kb_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return Response.success(data=result)
