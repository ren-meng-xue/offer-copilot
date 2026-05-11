import asyncio

import redis as sync_redis
from firecrawl import V1FirecrawlApp
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBaseStatus
from backend.app.repositories import knowledge_repository
from backend.app.services.chunking_service import split_markdown
from backend.app.services.embedding_service import generate_embeddings
from backend.app.services.title_generation_service import generate_knowledge_base_title
from backend.app.tasks import celery_app


def _get_sync_redis() -> sync_redis.Redis:
    """返回 Celery worker 侧使用的同步 Redis 客户端。

    这里只需要简单读写任务状态，不引入异步 Redis 依赖。
    优先使用 CELERY_BROKER_URL 以确保跨容器部署时能连接到正确的 Redis 实例。
    """

    return sync_redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )


def _set_task_status(r: sync_redis.Redis, task_id: str, status: KnowledgeBaseStatus) -> None:
    """将任务状态写入 Redis，供前端轮询展示进度。"""

    r.set(f"task:{task_id}:status", status.value)


async def _run_ingestion(kb_id: int, task_id: str, source_url: str) -> None:
    """包装完整入库流程并统一处理失败状态回写。"""

    r = _get_sync_redis()
    # 每次任务创建独立 engine，避免与 FastAPI 进程的 event loop 冲突。
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with session_factory() as db:
        try:
            await _process(db, kb_id, task_id, source_url, r)
        except Exception as exc:
            error_msg = str(exc)[:500]
            _set_task_status(r, task_id, KnowledgeBaseStatus.FAILED)
            await knowledge_repository.update_knowledge_base_status(
                db, kb_id, KnowledgeBaseStatus.FAILED, error_message=error_msg
            )
            raise
        finally:
            await engine.dispose()


async def _process(
    db: AsyncSession,
    kb_id: int,
    task_id: str,
    source_url: str,
    r: sync_redis.Redis,
) -> None:
    """执行 URL -> Markdown -> chunks -> embeddings -> pgvector 的主链路。"""

    _set_task_status(r, task_id, KnowledgeBaseStatus.PROCESSING)
    await knowledge_repository.update_knowledge_base_status(db, kb_id, KnowledgeBaseStatus.PROCESSING)

    firecrawl = V1FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
    result = firecrawl.scrape_url(source_url, formats=["markdown"])

    markdown = result.markdown
    if not markdown:
        raise ValueError("Firecrawl returned empty content")

    # 标题生成只影响展示，不应阻断主入库链路；失败时继续保留创建阶段的默认名称。
    try:
        generated_title = await generate_knowledge_base_title(markdown)
        if generated_title:
            await knowledge_repository.update_knowledge_base_name(db, kb_id, generated_title)
    except Exception:
        pass

    chunks = split_markdown(markdown, source_url)
    if not chunks:
        raise ValueError("No valid chunks after splitting")

    embeddings = await generate_embeddings([c.content for c in chunks])

    # repository 层只负责落库，因此这里先把切分结果和 embedding 组装成 ORM 对象。
    db_chunks = [
        DocumentChunk(
            knowledge_base_id=kb_id,
            content=chunk.content,
            embedding=embedding,
            source_url=source_url,
            heading_path=chunk.heading_path,
            chunk_index=chunk.chunk_index,
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    await knowledge_repository.bulk_create_chunks(db, db_chunks)

    _set_task_status(r, task_id, KnowledgeBaseStatus.DONE)
    await knowledge_repository.update_knowledge_base_status(db, kb_id, KnowledgeBaseStatus.DONE)


@celery_app.task(name="knowledge.ingest", bind=True, max_retries=0)
def ingest_knowledge(self, kb_id: int, task_id: str, source_url: str) -> None:
    """Celery 同步任务入口，桥接到内部异步实现。"""

    asyncio.run(_run_ingestion(kb_id, task_id, source_url))
