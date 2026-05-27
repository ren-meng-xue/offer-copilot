"""F2 反向断言测试：删除 kb_id=5 不应误删 kb_id=15/50/125。"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.app.models import SemanticCache
from backend.app.repositories.qa_repository import evict_caches_by_kb_id
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_evict_by_kb_id_does_not_affect_neighbors():
    """反向断言：删除 kb_id=5 不应误删 kb_id=15/50。"""
    engine = create_async_engine(settings.DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as db:
        rows = [
            SemanticCache(
                question="q1",
                query_vector=[0.0] * 1536,
                response_events=[],
                knowledge_base_ids=[5],
            ),
            SemanticCache(
                question="q2",
                query_vector=[0.0] * 1536,
                response_events=[],
                knowledge_base_ids=[15],
            ),
            SemanticCache(
                question="q3",
                query_vector=[0.0] * 1536,
                response_events=[],
                knowledge_base_ids=[50],
            ),
        ]
        for r in rows:
            db.add(r)
        await db.commit()

        await evict_caches_by_kb_id(db, kb_id=5)

        result = await db.execute(select(SemanticCache))
        remaining = result.scalars().all()
        remaining_ids = {tuple(r.knowledge_base_ids or []) for r in remaining}

        assert (5,) not in remaining_ids, "kb_id=5 应被删除"
        assert (15,) in remaining_ids, "kb_id=15 不应被误删（LIKE %5% bug）"
        assert (50,) in remaining_ids, "kb_id=50 不应被误删"

        for r in remaining:
            await db.delete(r)
        await db.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_evict_by_kb_id_with_multi_kb_entry():
    """如果 cache entry 涉及多个 KB（如 [5,15]），删 5 应该把这条删掉。"""
    engine = create_async_engine(settings.DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as db:
        db.add(
            SemanticCache(
                question="q-multi",
                query_vector=[0.0] * 1536,
                response_events=[],
                knowledge_base_ids=[5, 15],
            )
        )
        await db.commit()

        await evict_caches_by_kb_id(db, kb_id=5)

        result = await db.execute(select(SemanticCache))
        remaining = result.scalars().all()
        assert len(remaining) == 0

        for r in remaining:
            await db.delete(r)
        await db.commit()

    await engine.dispose()
