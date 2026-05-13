import asyncio
import json
import logging

import redis as sync_redis
from firecrawl import V1FirecrawlApp
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBaseStatus
from backend.app.repositories import knowledge_repository
from backend.app.services.chunking_service import split_markdown
from backend.app.services.embedding_service import generate_embeddings
from backend.app.services.summary_service import generate_knowledge_base_summary
from backend.app.services.title_generation_service import generate_knowledge_base_title
from backend.app.tasks import celery_app

logger = logging.getLogger(__name__)


def _get_sync_redis() -> sync_redis.Redis:
    """返回 Celery worker 侧使用的同步 Redis 客户端。

    这里只需要简单读写任务状态，不引入异步 Redis 依赖。
    优先使用 CELERY_BROKER_URL 以确保跨容器部署时能连接到正确的 Redis 实例。
    """

    return sync_redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )


def _set_task_status(r: sync_redis.Redis, task_id: str, status: KnowledgeBaseStatus, user_id: int, extra_data: dict | None = None) -> None:
    """将任务状态写入 Redis，并发布到用户专属频道供 SSE 实时通知。"""

    data = {
        "task_id": task_id,
        "status": status.value
    }
    if extra_data:
        data.update(extra_data)

    status_data = {
        "type": "knowledge_status",
        "data": data
    }
    # 1. 写入缓存供轮询/兜底
    r.set(f"task:{task_id}:status", status.value, ex=3600)
    # 2. 发布到频道供 SSE 实时推送
    r.publish(f"user:{user_id}:events", json.dumps(status_data, ensure_ascii=False))


async def _run_ingestion(kb_id: int, task_id: str, source_url: str, user_id: int) -> None:
    """包装完整入库流程并统一处理失败状态回写。"""

    r = _get_sync_redis()
    # 每次任务创建独立 engine，避免与 FastAPI 进程 of event loop 冲突。
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with session_factory() as db:
        try:
            await _process(db, kb_id, task_id, source_url, r, user_id)
        except Exception as exc:
            error_msg = str(exc)[:500]
            _set_task_status(r, task_id, KnowledgeBaseStatus.FAILED, user_id, extra_data={"knowledge_base_id": kb_id, "error_message": error_msg})
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
    user_id: int,
) -> None:
    """执行 来源 -> Markdown -> chunks -> embeddings -> pgvector 的主链路。"""

    _set_task_status(r, task_id, KnowledgeBaseStatus.PROCESSING, user_id, extra_data={"knowledge_base_id": kb_id})
    await knowledge_repository.update_knowledge_base_status(db, kb_id, KnowledgeBaseStatus.PROCESSING)

    # 获取知识库详情以判断类型
    kb = await knowledge_repository.get_knowledge_base_by_id(db, kb_id)
    if not kb:
        raise ValueError("Knowledge base not found")

    markdown = ""
    if kb.source_type == "url":
        # 网页爬取逻辑
        firecrawl = V1FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
        result = firecrawl.scrape_url(source_url, formats=["markdown"])
        markdown = result.markdown
    else:
        # 文件下载逻辑 (针对 .txt, .md 等)
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(source_url)
            resp.raise_for_status()
            markdown = resp.text

    if not markdown:
        raise ValueError("Content is empty")

    # 标题生成只影响展示，不应阻断主入库链路；失败时继续保留创建阶段的默认名称。
    try:
        generated_title = await generate_knowledge_base_title(markdown)
        if generated_title:
            await knowledge_repository.update_knowledge_base_name(db, kb_id, generated_title)
    except Exception:
        pass

    # 生成全局摘要并存储
    summary = None
    try:
        summary = await generate_knowledge_base_summary(markdown)
        if summary:
            await knowledge_repository.update_knowledge_base_summary(db, kb_id, summary)
    except Exception:
        logger.exception("Failed to generate/save summary for KB %s", kb_id)

    chunks = split_markdown(markdown, source_url)
    if not chunks:
        raise ValueError("No valid chunks after splitting")

    # 上下文感知嵌入：在生成向量前拼接标题路径
    texts_for_embedding = [
        f"章节路径: {c.heading_path}\n内容: {c.content}"
        for c in chunks
    ]
    embeddings = await generate_embeddings(texts_for_embedding)

    # repository 层只负责落库，因此这里先把切分结果和 embedding 组装成 ORM 对象。
    # 注意：content 字段依然存原始文本，只有算向量时用了拼接版。
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

    _set_task_status(r, task_id, KnowledgeBaseStatus.DONE, user_id, extra_data={"knowledge_base_id": kb_id, "summary": summary})
    await knowledge_repository.update_knowledge_base_status(db, kb_id, KnowledgeBaseStatus.DONE)


@celery_app.task(name="knowledge.ingest", bind=True, max_retries=0)
def ingest_knowledge(self, kb_id: int, task_id: str, source_url: str, user_id: int) -> None:
    """Celery 同步任务入口，桥接到内部异步实现。"""

    asyncio.run(_run_ingestion(kb_id, task_id, source_url, user_id))
