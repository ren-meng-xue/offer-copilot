import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.conversation import Conversation, Message


async def create_conversation(db: AsyncSession, user_id: int) -> Conversation:
    conv = Conversation(user_id=user_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def create_conversation_with_knowledge_base(
    db: AsyncSession,
    user_id: int,
    knowledge_base_id: int,
) -> Conversation:
    conv = Conversation(user_id=user_id, knowledge_base_id=knowledge_base_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation_by_id(db: AsyncSession, conv_id: uuid.UUID) -> Conversation | None:
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


async def update_conversation_title(db: AsyncSession, conv_id: uuid.UUID, title: str) -> None:
    conv = await get_conversation_by_id(db, conv_id)
    if conv is None:
        return
    conv.title = title
    await db.commit()


async def update_conversation_summary(db: AsyncSession, conv_id: uuid.UUID, summary: str) -> None:
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
        .order_by(Message.created_at.asc())
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


async def get_recent_messages(db: AsyncSession, conversation_id: uuid.UUID, limit: int = 4) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
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
        .order_by(Message.created_at.asc())
        .limit(to_summarize)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
