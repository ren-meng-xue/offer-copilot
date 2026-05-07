import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.response import Response
from backend.app.core.security import get_current_user
from backend.app.db import get_db
from backend.app.repositories import qa_repository
from backend.app.schemas.qa import AskRequest, ConversationListItem, CreateConversationResponse, MessageItem
from backend.app.services import qa_service
from backend.app.tasks.qa_tasks import summarize_conversation

router = APIRouter(prefix="/qa", tags=["问答"])


@router.post("/conversations", response_model=Response[CreateConversationResponse], status_code=status.HTTP_201_CREATED)
async def create_conversation(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[CreateConversationResponse]:
    conv = await qa_repository.create_conversation(db, int(current_user_id))
    return Response.success(data=CreateConversationResponse(conv_id=conv.id, created_at=conv.created_at))


@router.get("/conversations", response_model=Response[list[ConversationListItem]])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[list[ConversationListItem]]:
    convs = await qa_repository.list_conversations(db, int(current_user_id))
    return Response.success(data=[
        ConversationListItem(conv_id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at)
        for c in convs
    ])


@router.post("/conversations/{conv_id}/ask")
async def ask(
    conv_id: uuid.UUID,
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    user_id = int(current_user_id)

    async def event_stream():
        async for event in qa_service.stream_answer(db, conv_id, user_id, body.question):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event["type"] in ("done", "error"):
                # 触发摘要压缩检查
                if event["type"] == "done":
                    conv = await qa_repository.get_conversation_by_id(db, conv_id)
                    if conv and (conv.message_count or 0) > qa_service.SUMMARY_TRIGGER:
                        summarize_conversation.delay(str(conv_id))
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations/{conv_id}/messages", response_model=Response[list[MessageItem]])
async def get_messages(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[list[MessageItem]]:
    conv = await qa_repository.get_conversation_by_id(db, conv_id)
    if conv is None or conv.user_id != int(current_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    msgs = await qa_repository.list_messages(db, conv_id)
    return Response.success(data=[
        MessageItem(id=m.id, role=m.role, content=m.content, citations=m.citations, created_at=m.created_at)
        for m in msgs
    ])


@router.delete("/conversations/{conv_id}", response_model=Response[None])
async def delete_conversation(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[None]:
    conv = await qa_repository.get_conversation_by_id(db, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if conv.user_id != int(current_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    await qa_repository.delete_conversation(db, conv_id)
    return Response.success(msg="删除成功")
