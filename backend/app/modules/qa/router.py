import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.response import Response
from backend.app.core.security import get_current_user
from backend.app.db import get_db
from backend.app.repositories import qa_repository
from backend.app.schemas.qa import (
    AskRequest,
    ConversationListItem,
    CreateConversationRequest,
    CreateConversationResponse,
    KnowledgeScope,
    KnowledgeScopeItem,
    MessageItem,
)
from backend.app.services import qa_service
from backend.app.tasks.qa_tasks import summarize_conversation

router = APIRouter(prefix="/qa", tags=["问答"])


def _scope_from_items(items: list) -> KnowledgeScope | None:
    """把 ORM scope items 转成前端展示用结构。"""

    if not items:
        return None
    return KnowledgeScope(
        type="question_routed",
        items=[
            KnowledgeScopeItem(
                knowledge_base_id=item.knowledge_base_id,
                name=item.knowledge_base_name_snapshot,
                source_url=item.source_url_snapshot,
                route_score=item.route_score,
                route_reason=item.route_reason,
                deleted=item.knowledge_base_id is None,
            )
            for item in items
        ],
    )


@router.post(
    "/conversations",
    response_model=Response[CreateConversationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    body: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[CreateConversationResponse]:
    try:
        conv = await qa_service.create_conversation(
            db,
            int(current_user_id),
            knowledge_base_id=body.knowledge_base_id,
            question=body.question,
        )
    except qa_service.ConversationCreationError as exc:
        status_code_by_error = {
            "knowledge_base_not_found": status.HTTP_404_NOT_FOUND,
            "no_knowledge_base": status.HTTP_404_NOT_FOUND,
            "knowledge_base_not_ready": status.HTTP_409_CONFLICT,
            "knowledge_scope_route_empty": status.HTTP_409_CONFLICT,
        }
        status_code = status_code_by_error.get(exc.code, status.HTTP_409_CONFLICT)
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    scope_items = await qa_repository.list_scope_items_by_conversation_id(db, conv.id)
    knowledge_base_ids = [
        item.knowledge_base_id
        for item in scope_items
        if item.knowledge_base_id is not None
    ]
    return Response.success(
        data=CreateConversationResponse(
            conv_id=conv.id,
            knowledge_base_id=knowledge_base_ids[0]
            if knowledge_base_ids
            else conv.knowledge_base_id,
            knowledge_base_ids=knowledge_base_ids,
            knowledge_scope=_scope_from_items(scope_items),
            created_at=conv.created_at,
        )
    )


@router.get("/conversations", response_model=Response[list[ConversationListItem]])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[list[ConversationListItem]]:
    convs = await qa_repository.list_conversations(db, int(current_user_id))
    scope_items_by_conv_id = await qa_repository.list_scope_items_by_conversation_ids(
        db,
        [c.id for c in convs],
    )
    data: list[ConversationListItem] = []
    for conv in convs:
        scope_items = scope_items_by_conv_id.get(conv.id, [])
        if not scope_items and conv.knowledge_base_id is not None:
            legacy_item = await qa_repository.build_legacy_scope_item(db, conv)
            scope_items = [legacy_item] if legacy_item else []
        knowledge_base_ids = [
            item.knowledge_base_id
            for item in scope_items
            if item.knowledge_base_id is not None
        ]
        data.append(
            ConversationListItem(
                conv_id=conv.id,
                knowledge_base_id=conv.knowledge_base_id,
                knowledge_base_ids=knowledge_base_ids,
                knowledge_scope=_scope_from_items(scope_items),
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
    return Response.success(data=[*data])


@router.post("/conversations/{conv_id}/ask")
async def ask(
    conv_id: uuid.UUID,
    body: AskRequest,
    debug: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    user_id = int(current_user_id)
    debug_enabled = debug and settings.DEBUG

    async def event_stream():
        async for event in qa_service.stream_answer(
            db, conv_id, user_id, body.question, debug=debug_enabled
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event["type"] in ("done", "error"):
                # 触发摘要压缩检查
                if event["type"] == "done":
                    conv = await qa_repository.get_conversation_by_id(db, conv_id)
                    if conv and (conv.message_count or 0) > qa_service.SUMMARY_TRIGGER:
                        summarize_conversation.delay(str(conv_id))
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get(
    "/conversations/{conv_id}/messages", response_model=Response[list[MessageItem]]
)
async def get_messages(
    conv_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
) -> Response[list[MessageItem]]:
    conv = await qa_repository.get_conversation_by_id(db, conv_id)
    if conv is None or conv.user_id != int(current_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    msgs = await qa_repository.list_messages(db, conv_id)
    return Response.success(
        data=[
            MessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=m.citations,
                created_at=m.created_at,
            )
            for m in msgs
        ]
    )


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
