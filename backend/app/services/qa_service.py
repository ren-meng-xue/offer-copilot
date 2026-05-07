import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import cohere
from openai import AsyncOpenAI
from pgvector.sqlalchemy import Vector
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.conversation import Conversation, Message
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.repositories import qa_repository
from backend.app.services.embedding_service import generate_embeddings

VECTOR_TOP_K = 20
RERANK_TOP_N = 5
MAX_SNIPPET_LEN = 200
SUMMARY_TRIGGER = 20
KEEP_RECENT = 4


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _cohere_client() -> cohere.AsyncClientV2:
    return cohere.AsyncClientV2(api_key=settings.COHERE_API_KEY)


async def _vector_search(db: AsyncSession, user_id: int, query_vec: list[float]) -> list[DocumentChunk]:
    stmt = (
        select(DocumentChunk)
        .join(KnowledgeBase, DocumentChunk.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vec))
        .limit(VECTOR_TOP_K)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _rerank(query: str, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    if not chunks:
        return chunks
    try:
        client = _cohere_client()
        resp = await client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=[c.content for c in chunks],
            top_n=RERANK_TOP_N,
        )
        return [chunks[r.index] for r in resp.results]
    except Exception:
        return chunks[:RERANK_TOP_N]


def _build_prompt(
    question: str,
    chunks: list[DocumentChunk],
    recent_messages: list[Message],
    summary: str | None,
) -> list[dict[str, str]]:
    context_parts = [f"[{i+1}] {c.heading_path or ''}\n{c.content}" for i, c in enumerate(chunks)]
    context_str = "\n\n".join(context_parts)

    system = (
        "你是技术文档助手。只基于提供的上下文回答问题。"
        "回答中必须用 [1]、[2] 等编号引用对应的上下文来源。"
        "如果上下文中没有相关信息，回答'根据已有文档，无法回答该问题'。"
        f"\n\ncontext:\n{context_str}"
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    if summary:
        messages.append({"role": "system", "content": f"历史摘要：{summary}"})

    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": question})
    return messages


def _extract_citations(answer: str, chunks: list[DocumentChunk]) -> list[dict[str, Any]]:
    indices = sorted({int(m) - 1 for m in re.findall(r"\[(\d+)\]", answer)})
    citations = []
    for idx in indices:
        if 0 <= idx < len(chunks):
            c = chunks[idx]
            citations.append({
                "index": idx + 1,
                "chunk_id": c.id,
                "source_url": c.source_url,
                "heading_path": c.heading_path,
                "snippet": c.content[:MAX_SNIPPET_LEN],
            })
    return citations


async def stream_answer(
    db: AsyncSession,
    conv_id: uuid.UUID,
    user_id: int,
    question: str,
) -> AsyncGenerator[dict[str, Any], None]:
    conv = await qa_repository.get_conversation_by_id(db, conv_id)
    if conv is None or conv.user_id != user_id:
        yield {"type": "error", "message": "对话不存在或无权访问"}
        return

    # 向量化问题
    [query_vec] = await generate_embeddings([question])

    # 向量检索
    candidates = await _vector_search(db, user_id, query_vec)
    if not candidates:
        yield {"type": "error", "message": "请先导入知识库"}
        return

    # Rerank
    top_chunks = await _rerank(question, candidates)

    # 构建 prompt
    recent = await qa_repository.get_recent_messages(db, conv_id, limit=KEEP_RECENT)
    messages = _build_prompt(question, top_chunks, recent, conv.summary)

    # 写入用户消息
    await qa_repository.create_message(db, conv_id, "user", question)

    # 更新对话标题（第一条消息）
    if conv.message_count == 0:
        await qa_repository.update_conversation_title(db, conv_id, question[:20])

    # gpt-4o streaming
    client = _openai_client()
    full_answer = ""
    try:
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,  # type: ignore[arg-type]
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_answer += delta
                yield {"type": "token", "content": delta}
    except Exception as e:
        yield {"type": "error", "message": f"生成失败，请重试"}
        return

    # 提取 citations
    citations = _extract_citations(full_answer, top_chunks)
    yield {"type": "citations", "data": citations}
    yield {"type": "done"}

    # 写入 assistant 消息
    await qa_repository.create_message(db, conv_id, "assistant", full_answer, citations or None)
