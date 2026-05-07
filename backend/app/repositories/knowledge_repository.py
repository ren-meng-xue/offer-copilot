from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus


async def create_knowledge_base(db: AsyncSession, kb: KnowledgeBase) -> KnowledgeBase:
    """持久化知识库记录并刷新主键、默认状态等数据库侧字段。"""

    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def get_knowledge_base_by_id(db: AsyncSession, kb_id: int) -> KnowledgeBase | None:
    """按主键查询知识库，供创建流程和异步任务复用。"""

    stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    result = await db.execute(stmt)
    return result.scalars().one_or_none()


async def update_knowledge_base_status(
    db: AsyncSession,
    kb_id: int,
    status: KnowledgeBaseStatus,
    error_message: str | None = None,
) -> None:
    """更新异步索引流程中的知识库状态。

    这里找不到记录时直接返回，不在 repository 层抛错，调用方可按需决定
    是否将其视为任务失败。
    """

    kb = await get_knowledge_base_by_id(db, kb_id)
    if kb is None:
        return
    kb.status = status
    kb.error_message = error_message
    await db.commit()


async def update_knowledge_base_name(db: AsyncSession, kb_id: int, name: str) -> None:
    """回写知识库名称，例如在抓取正文后用 LLM 生成更准确的主题名。"""

    kb = await get_knowledge_base_by_id(db, kb_id)
    if kb is None:
        return
    kb.name = name
    await db.commit()


async def bulk_create_chunks(db: AsyncSession, chunks: list[DocumentChunk]) -> None:
    """批量写入切分后的文档块及其 metadata / embedding 结果。"""

    db.add_all(chunks)
    await db.commit()
