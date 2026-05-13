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


async def get_knowledge_base_by_source_url(db: AsyncSession, source_url: str) -> KnowledgeBase | None:
    """按 source_url 查询知识库，供评测 fixture 解析稳定作用域使用。"""

    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.source_url == source_url)
        .order_by(KnowledgeBase.updated_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_latest_knowledge_base_by_name(db: AsyncSession, name: str) -> KnowledgeBase | None:
    """按名称查询最近更新的一条知识库，避免 fixture 依赖固定主键。"""

    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.name == name)
        .order_by(KnowledgeBase.updated_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def list_knowledge_bases_by_user(db: AsyncSession, user_id: int) -> list[KnowledgeBase]:
    """按用户查询知识库列表，避免跨用户展示导入记录。"""

    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


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


async def update_knowledge_base_summary(db: AsyncSession, kb_id: int, summary: str) -> None:
    """回写知识库摘要。"""

    kb = await get_knowledge_base_by_id(db, kb_id)
    if kb is None:
        return
    kb.summary = summary
    await db.commit()


async def delete_knowledge_base(db: AsyncSession, kb: KnowledgeBase) -> None:
    """删除知识库及其关联 chunks。"""

    await db.delete(kb)
    await db.commit()


async def bulk_create_chunks(db: AsyncSession, chunks: list[DocumentChunk]) -> None:
    """批量写入切分后的文档块及其 metadata / embedding 结果。"""

    db.add_all(chunks)
    await db.commit()
