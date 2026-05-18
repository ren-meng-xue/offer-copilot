import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.conversation import (
    Conversation,
    ConversationKnowledgeScopeItem,
    Message,
)
from backend.app.models.knowledge_base import KnowledgeBase


async def create_conversation(db: AsyncSession, user_id: int) -> Conversation:
    conv = Conversation(user_id=user_id, title="新会话")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def create_conversation_with_knowledge_base(
    db: AsyncSession,
    user_id: int,
    knowledge_base_id: int,
) -> Conversation:
    conv = Conversation(
        user_id=user_id, knowledge_base_id=knowledge_base_id, title="新会话"
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def create_conversation_with_scope(
    db: AsyncSession,
    user_id: int,
    scope_items: list[dict],
) -> Conversation:
    """创建会话并写入问题路由得到的知识范围成员。"""

    first_kb_id = scope_items[0]["knowledge_base_id"] if scope_items else None
    conv = Conversation(user_id=user_id, knowledge_base_id=first_kb_id, title="新会话")
    db.add(conv)
    await db.flush()

    await add_scope_items_to_conversation(db, conv.id, scope_items)

    await db.commit()
    await db.refresh(conv)
    return conv


async def add_scope_items_to_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    scope_items: list[dict],
) -> None:
    """为现有会话追加知识范围成员。"""

    for position, item in enumerate(scope_items):
        db.add(
            ConversationKnowledgeScopeItem(
                conversation_id=conversation_id,
                knowledge_base_id=item["knowledge_base_id"],
                knowledge_base_name_snapshot=item["knowledge_base_name_snapshot"],
                source_url_snapshot=item["source_url_snapshot"],
                position=position,
                route_score=item.get("route_score"),
                route_reason=item.get("route_reason"),
            )
        )
    # 如果会话原本没有绑定知识库，则同步更新第一个作为默认
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalars().one_or_none()
    if conv and conv.knowledge_base_id is None and scope_items:
        conv.knowledge_base_id = scope_items[0]["knowledge_base_id"]

    await db.flush()


async def get_conversation_by_id(
    db: AsyncSession, conv_id: uuid.UUID
) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.id == conv_id)
    result = await db.execute(stmt)
    return result.scalars().one_or_none()


async def list_conversations(db: AsyncSession, user_id: int) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_scope_items_by_conversation_id(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> list[ConversationKnowledgeScopeItem]:
    """查询单个会话锁定的知识范围。"""

    stmt = (
        select(ConversationKnowledgeScopeItem)
        .where(ConversationKnowledgeScopeItem.conversation_id == conversation_id)
        .order_by(ConversationKnowledgeScopeItem.position.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_scope_items_by_conversation_ids(
    db: AsyncSession,
    conversation_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[ConversationKnowledgeScopeItem]]:
    """批量查询会话知识范围，避免列表接口逐条查询。"""

    if not conversation_ids:
        return {}

    stmt = (
        select(ConversationKnowledgeScopeItem)
        .where(ConversationKnowledgeScopeItem.conversation_id.in_(conversation_ids))
        .order_by(
            ConversationKnowledgeScopeItem.conversation_id.asc(),
            ConversationKnowledgeScopeItem.position.asc(),
        )
    )
    result = await db.execute(stmt)
    grouped: dict[uuid.UUID, list[ConversationKnowledgeScopeItem]] = {
        conversation_id: [] for conversation_id in conversation_ids
    }
    for item in result.scalars().all():
        grouped.setdefault(item.conversation_id, []).append(item)
    return grouped


async def build_legacy_scope_item(
    db: AsyncSession,
    conversation: Conversation,
) -> ConversationKnowledgeScopeItem | None:
    """为旧单知识库会话构造只读 scope item。"""

    if conversation.knowledge_base_id is None:
        return None

    stmt = select(KnowledgeBase).where(
        KnowledgeBase.id == conversation.knowledge_base_id
    )
    result = await db.execute(stmt)
    kb = result.scalars().one_or_none()
    if kb is None:
        return None

    return ConversationKnowledgeScopeItem(
        conversation_id=conversation.id,
        knowledge_base_id=kb.id,
        knowledge_base_name_snapshot=kb.name,
        source_url_snapshot=kb.source_url,
        position=0,
        route_score=None,
        route_reason="历史单知识库会话兼容",
    )


async def update_conversation_title(
    db: AsyncSession, conv_id: uuid.UUID, title: str
) -> None:
    conv = await get_conversation_by_id(db, conv_id)
    if conv is None:
        return
    conv.title = title
    await db.commit()


async def update_conversation_summary(
    db: AsyncSession, conv_id: uuid.UUID, summary: str
) -> None:
    conv = await get_conversation_by_id(db, conv_id)
    if conv is None:
        return
    conv.summary = summary
    await db.commit()


async def create_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    citations: list | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations=citations,
    )
    db.add(msg)
    # 同步递增 message_count
    conv = await get_conversation_by_id(db, conversation_id)
    if conv is not None:
        conv.message_count = (conv.message_count or 0) + 1
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(db: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_conversation(db: AsyncSession, conv_id: uuid.UUID) -> bool:
    conv = await get_conversation_by_id(db, conv_id)
    if conv is None:
        return False
    await db.delete(conv)
    await db.commit()
    return True


async def get_recent_messages(
    db: AsyncSession, conversation_id: uuid.UUID, limit: int = 4
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(reversed(result.scalars().all()))


async def get_old_messages_for_summary(
    db: AsyncSession, conversation_id: uuid.UUID, keep_recent: int = 4
) -> list[Message]:
    """返回除最近 keep_recent 条外的所有消息，用于摘要压缩。"""
    total_stmt = select(func.count()).where(Message.conversation_id == conversation_id)
    total = (await db.execute(total_stmt)).scalar_one()
    to_summarize = total - keep_recent
    if to_summarize <= 0:
        return []
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .limit(to_summarize)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
