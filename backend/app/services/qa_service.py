import datetime
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from collections.abc import Sequence
from time import perf_counter
from typing import Any

import cohere
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.conversation import Message
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus
from backend.app.repositories import knowledge_repository, qa_repository
from backend.app.services.embedding_service import generate_embeddings

logger = logging.getLogger(__name__)


def truncate_title(text: str, max_len: int = 20) -> str:
    """智能截断标题，在词边界截断并添加省略号。"""
    if not text:
        return ""

    if len(text) <= max_len:
        return text

    # 尝试在空格处截断（针对英文等有空格的语言）
    words = text.split()
    title = ""
    for word in words:
        new_len = len(title) + len(word) + (1 if title else 0)
        if new_len > max_len:
            break
        if title:
            title += " "
        title += word

    # 如果没有找到合适的词边界（如中文），则直接截断
    if not title or len(title) < max_len * 0.5:
        # 预留空间给省略号
        available = max_len - 3
        title = text[:available]

    # 添加省略号
    if len(title) < max_len and len(title) < len(text):
        title += "..."

    return title[:max_len]

RERANK_TOP_N = 5
MAX_SNIPPET_LEN = 200
SUMMARY_TRIGGER = 20
KEEP_RECENT = 4
DEBUG_PREVIEW_LIMIT = 5


class CitationValidationError(ValueError):
    """Raised when a generated answer cannot be traced to retrieved chunks."""


class ConversationCreationError(ValueError):
    """Raised when a conversation cannot be bound to the requested knowledge base."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def _duration_ms(start: float, end: float) -> int:
    return int((end - start) * 1000)


def _debug_chunk_preview(chunks: Sequence[DocumentChunk], limit: int = DEBUG_PREVIEW_LIMIT) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": str(chunk.id),
            "source_url": chunk.source_url,
            "heading_path": chunk.heading_path or "",
            "chunk_index": chunk.chunk_index,
        }
        for chunk in chunks[:limit]
    ]


def _debug_chunk_preview_with_score(
    chunks: Sequence[DocumentChunk],
    scores: Sequence[float] | None = None,
    limit: int = DEBUG_PREVIEW_LIMIT,
) -> list[dict[str, Any]]:
    """生成带 relevance_score 的 chunk 预览。

    Args:
        chunks: chunk 列表
        scores: relevance_score 列表（长度应与 chunks 相同）
        limit: 返回的最大数量

    Returns:
        chunk 预览列表，每个包含 chunk_id、source_url、heading_path、chunk_index、relevance_score
    """
    result = []
    for i, chunk in enumerate(chunks[:limit]):
        item = {
            "chunk_id": str(chunk.id),
            "source_url": chunk.source_url,
            "heading_path": chunk.heading_path or "",
            "chunk_index": chunk.chunk_index,
        }
        if scores and i < len(scores):
            item["relevance_score"] = scores[i]
        result.append(item)
    return result


def _get_stage_description(stage: str) -> str:
    """获取各阶段的描述文字"""
    descriptions = {
        "query_rewrite": "重写用户问题为独立的检索查询",
        "embedding": "向量化用户问题",
        "retrieval": "向量检索 + 全文检索",
        "rerank": "重排序检索结果",
        "citations": "提取并验证引用",
        "terminal_error": "终止错误",
    }
    return descriptions.get(stage, stage)


def _build_debug_event(
    stage: str,
    data: dict[str, Any],
    conv_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """构建 debug 事件。

    Args:
        stage: 阶段名称
        data: 阶段数据
        conv_id: 会话 ID，用于生成 trace_id

    Returns:
        如果 RAG_DEBUG_ENABLED=True，返回完整 debug 事件；否则返回空字典
    """
    if not settings.RAG_DEBUG_ENABLED:
        return {}

    trace_id = ""
    if conv_id:
        trace_id = f"conv-{conv_id}-{uuid.uuid4().hex[:8]}"

    return {
        "type": "debug",
        "stage": stage,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trace_id": trace_id,
        "data": {
            "description": _get_stage_description(stage),
            **data,
        },
    }


def _build_debug_error_data(
    *,
    code: str,
    message: str,
    retrieval_query: str,
    vector_candidates_count: int,
    fts_candidates_count: int,
    merged_candidates_count: int,
    rerank_candidates_count: int,
    citations_count: int,
    rewrite_duration_ms: int,
    vector_duration_ms: int,
    fts_duration_ms: int,
    rerank_duration_ms: int,
    generation_duration_ms: int,
) -> dict[str, Any]:
    return {
        "error_code": code,
        "message": message,
        "retrieval_query": retrieval_query,
        "vector_candidates_count": vector_candidates_count,
        "fts_candidates_count": fts_candidates_count,
        "merged_candidates_count": merged_candidates_count,
        "rerank_candidates_count": rerank_candidates_count,
        "citations_count": citations_count,
        "rewrite_duration_ms": rewrite_duration_ms,
        "vector_duration_ms": vector_duration_ms,
        "fts_duration_ms": fts_duration_ms,
        "rerank_duration_ms": rerank_duration_ms,
        "generation_duration_ms": generation_duration_ms,
    }


def _build_rag_telemetry_payload(
    *,
    conversation_id: uuid.UUID,
    knowledge_base_id: int | None,
    question: str,
    retrieval_query: str,
    vector_candidates_count: int,
    fts_candidates_count: int,
    merged_candidates_count: int,
    rerank_candidates_count: int,
    citations_count: int,
    rewrite_duration_ms: int,
    vector_duration_ms: int,
    fts_duration_ms: int,
    rerank_duration_ms: int,
    generation_duration_ms: int,
    total_duration_ms: int,
    outcome: str,
    error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "event": "rag_telemetry",
        "conversation_id": str(conversation_id),
        "knowledge_base_id": knowledge_base_id,
        "question_length": len(question),
        "retrieval_query_length": len(retrieval_query),
        "retrieval_query_rewritten": retrieval_query != question,
        "vector_candidates_count": vector_candidates_count,
        "fts_candidates_count": fts_candidates_count,
        "merged_candidates_count": merged_candidates_count,
        "rerank_candidates_count": rerank_candidates_count,
        "citations_count": citations_count,
        "rewrite_duration_ms": rewrite_duration_ms,
        "vector_duration_ms": vector_duration_ms,
        "fts_duration_ms": fts_duration_ms,
        "rerank_duration_ms": rerank_duration_ms,
        "generation_duration_ms": generation_duration_ms,
        "total_duration_ms": total_duration_ms,
        "outcome": outcome,
        "error_code": error_code,
    }


def _emit_rag_telemetry(payload: dict[str, Any]) -> None:
    if not settings.RAG_TELEMETRY_ENABLED:
        return
    try:
        logger.info("rag_telemetry %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))
    except Exception:
        return


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _cohere_client() -> cohere.AsyncClientV2:
    return cohere.AsyncClientV2(api_key=settings.COHERE_API_KEY)


async def create_conversation(db: AsyncSession, user_id: int, knowledge_base_id: int):
    kb = await knowledge_repository.get_knowledge_base_by_id(db, knowledge_base_id)
    if kb is None or kb.user_id != user_id:
        raise ConversationCreationError("知识库不存在", "knowledge_base_not_found")
    if kb.status != KnowledgeBaseStatus.DONE:
        raise ConversationCreationError("知识库尚未完成索引", "knowledge_base_not_ready")
    return await qa_repository.create_conversation_with_knowledge_base(db, user_id, knowledge_base_id)


async def _vector_search(
    db: AsyncSession,
    user_id: int,
    knowledge_base_id: int,
    query_vec: list[float],
) -> list[DocumentChunk]:
    stmt = (
        select(DocumentChunk)
        .join(KnowledgeBase, DocumentChunk.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.user_id == user_id)
        .where(KnowledgeBase.id == knowledge_base_id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vec))
        .limit(settings.RAG_VECTOR_TOP_K)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _fts_search(db: AsyncSession, user_id: int, knowledge_base_id: int, query: str) -> list[DocumentChunk]:
    search_vector = func.to_tsvector("simple", func.coalesce(DocumentChunk.content, ""))
    search_query = func.websearch_to_tsquery("simple", query)
    rank = func.ts_rank_cd(search_vector, search_query)
    stmt = (
        select(DocumentChunk)
        .join(KnowledgeBase, DocumentChunk.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.user_id == user_id)
        .where(KnowledgeBase.id == knowledge_base_id)
        .where(search_vector.op("@@")(search_query))
        .order_by(rank.desc(), DocumentChunk.id.asc())
        .limit(settings.RAG_FTS_TOP_K)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _merge_chunks_by_id(*chunk_lists: Sequence[DocumentChunk]) -> list[DocumentChunk]:
    merged: list[DocumentChunk] = []
    seen_ids: set[int] = set()
    for chunk_list in chunk_lists:
        for chunk in chunk_list:
            if chunk.id in seen_ids:
                continue
            merged.append(chunk)
            seen_ids.add(chunk.id)
    return merged


async def _rerank(
    query: str,
    chunks: list[DocumentChunk],
) -> tuple[list[DocumentChunk], list[float]]:
    """重排序 chunks。

    Args:
        query: 查询文本
        chunks: 待重排序的 chunks

    Returns:
        (重排序后的 chunks, relevance_score 列表)
    """
    if not chunks:
        return chunks, []

    try:
        client = _cohere_client()
        resp = await client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=[c.content for c in chunks],
            top_n=RERANK_TOP_N,
        )

        # 提取分数并排序
        scores = [result.relevance_score for result in resp.results]
        ranked_chunks = _filter_rerank_results(chunks, resp.results, settings.RAG_MIN_RERANK_SCORE)

        return ranked_chunks, scores[:len(ranked_chunks)]
    except Exception as e:
        logger.warning("Rerank failed, using original order: %s", e, exc_info=True)
        return chunks[:RERANK_TOP_N], []


def _filter_rerank_results(
    chunks: list[DocumentChunk],
    rerank_results: Sequence[Any],
    min_score: float,
) -> list[DocumentChunk]:
    ranked_chunks: list[DocumentChunk] = []
    for result in rerank_results:
        idx = result.index
        score = result.relevance_score
        if 0 <= idx < len(chunks) and score >= min_score:
            ranked_chunks.append(chunks[idx])
    return ranked_chunks


def _build_query_rewrite_messages(
    question: str,
    recent_messages: Sequence[Message],
    summary: str | None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "你负责把用户问题改写成适合技术文档检索的独立查询。"
                "补全上下文指代，保留关键术语、API 名称、错误码、配置项。"
                "只输出一行查询，不要解释，不要加引号。"
            ),
        }
    ]
    if summary:
        messages.append({"role": "system", "content": f"历史摘要：{summary}"})
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


async def _rewrite_query(
    question: str,
    recent_messages: Sequence[Message],
    summary: str | None,
) -> str:
    if not settings.RAG_QUERY_REWRITE_ENABLED:
        return question
    try:
        client = _openai_client()
        resp = await client.chat.completions.create(
            model=settings.RAG_QUERY_REWRITE_MODEL,
            messages=_build_query_rewrite_messages(question, recent_messages, summary),  # type: ignore[arg-type]
        )
        content = resp.choices[0].message.content or ""
        rewritten = next((line.strip() for line in content.splitlines() if line.strip()), "")
        return rewritten or question
    except Exception as e:
        logger.warning("Query rewrite failed, using original question: %s", e, exc_info=False)
        return question


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
        "如果问题是学习路线、概念解释、总结或建议类问题，只要上下文包含相关概念，"
        "就必须基于相关上下文综合回答并引用来源。"
        "只有当上下文与问题完全无关时，才回答'根据已有文档，无法回答该问题'。"
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
    # 匹配多种引用格式：[1], (1), 【1】, <1>
    # 优先提取明确的数字索引，避免误匹配
    pattern = r"[\[\(【<](\d+)[\]\)】>]"
    indices = sorted({int(m) - 1 for m in re.findall(pattern, answer)})

    citations = []
    for idx in indices:
        if 0 <= idx < len(chunks):
            c = chunks[idx]
            citations.append({
                "index": idx + 1,
                "chunk_id": str(c.id),
                "source_url": c.source_url,
                "heading_path": c.heading_path or "",
                "snippet": c.content[:MAX_SNIPPET_LEN],
            })
    return citations


def _require_citations(answer: str, chunks: list[DocumentChunk]) -> list[dict[str, Any]]:
    citations = _extract_citations(answer, chunks)
    if not citations:
        raise CitationValidationError("Generated answer has no valid citations")
    return citations


async def stream_answer(
    db: AsyncSession,
    conv_id: uuid.UUID,
    user_id: int,
    question: str,
    *,
    debug: bool = False,
) -> AsyncGenerator[dict[str, Any], None]:
    debug = debug and settings.DEBUG
    total_start = perf_counter()
    rewrite_duration_ms = 0
    vector_duration_ms = 0
    fts_duration_ms = 0
    rerank_duration_ms = 0
    generation_duration_ms = 0
    vector_candidates_count = 0
    fts_candidates_count = 0
    merged_candidates_count = 0
    rerank_candidates_count = 0
    citations_count = 0
    retrieval_query = question

    conv = await qa_repository.get_conversation_by_id(db, conv_id)
    if conv is None or conv.user_id != user_id:
        if debug:
            yield _build_debug_event(
                "terminal_error",
                _build_debug_error_data(
                    code="conversation_not_found",
                    message="对话不存在或无权访问",
                    retrieval_query=retrieval_query,
                    vector_candidates_count=vector_candidates_count,
                    fts_candidates_count=fts_candidates_count,
                    merged_candidates_count=merged_candidates_count,
                    rerank_candidates_count=rerank_candidates_count,
                    citations_count=citations_count,
                    rewrite_duration_ms=rewrite_duration_ms,
                    vector_duration_ms=vector_duration_ms,
                    fts_duration_ms=fts_duration_ms,
                    rerank_duration_ms=rerank_duration_ms,
                    generation_duration_ms=generation_duration_ms,
                ),
                conv_id=conv_id,
            )
        yield {"type": "error", "message": "对话不存在或无权访问"}
        return
    if conv.knowledge_base_id is None:
        if debug:
            yield _build_debug_event(
                "terminal_error",
                _build_debug_error_data(
                    code="conversation_scope_missing",
                    message="当前会话未绑定知识库，请新建会话",
                    retrieval_query=retrieval_query,
                    vector_candidates_count=vector_candidates_count,
                    fts_candidates_count=fts_candidates_count,
                    merged_candidates_count=merged_candidates_count,
                    rerank_candidates_count=rerank_candidates_count,
                    citations_count=citations_count,
                    rewrite_duration_ms=rewrite_duration_ms,
                    vector_duration_ms=vector_duration_ms,
                    fts_duration_ms=fts_duration_ms,
                    rerank_duration_ms=rerank_duration_ms,
                    generation_duration_ms=generation_duration_ms,
                ),
                conv_id=conv_id,
            )
        yield {
            "type": "error",
            "code": "conversation_scope_missing",
            "message": "当前会话未绑定知识库，请新建会话",
        }
        return

    recent = await qa_repository.get_recent_messages(db, conv_id, limit=KEEP_RECENT)
    rewrite_start = perf_counter()
    retrieval_query = await _rewrite_query(question, recent, conv.summary)
    rewrite_duration_ms = _duration_ms(rewrite_start, perf_counter())
    if debug:
        yield _build_debug_event(
            "query_rewrite",
            {
                "question": question,
                "retrieval_query": retrieval_query,
                "rewritten": retrieval_query != question,
                "rewrite_duration_ms": rewrite_duration_ms,
                "unit": {
                    "rewrite_duration_ms": "毫秒",
                },
            },
            conv_id=conv_id,
        )

    # 向量化问题
    embedding_start = perf_counter()
    [query_vec] = await generate_embeddings([retrieval_query])
    embedding_duration_ms = _duration_ms(embedding_start, perf_counter())

    if debug:
        yield _build_debug_event(
            "embedding",
            {
                "model": "text-embedding-3-small",
                "dimension": len(query_vec[0]) if query_vec else 0,
                "query_length": len(retrieval_query),
                "duration_ms": embedding_duration_ms,
                "unit": {
                    "duration_ms": "毫秒",
                    "dimension": "向量维度",
                    "query_length": "字符数",
                },
            },
            conv_id=conv_id,
        )

    # 向量检索
    vector_start = perf_counter()
    vector_candidates = await _vector_search(db, user_id, conv.knowledge_base_id, query_vec)
    vector_duration_ms = _duration_ms(vector_start, perf_counter())
    vector_candidates_count = len(vector_candidates)
    try:
        fts_start = perf_counter()
        fts_candidates = await _fts_search(db, user_id, conv.knowledge_base_id, retrieval_query)
        fts_duration_ms = _duration_ms(fts_start, perf_counter())
    except Exception as e:
        logger.warning("FTS search failed: %s", e, exc_info=True)
        fts_candidates = []
        fts_duration_ms = 0
    fts_candidates_count = len(fts_candidates)
    candidates = _merge_chunks_by_id(vector_candidates, fts_candidates)
    merged_candidates_count = len(candidates)
    if debug:
        yield _build_debug_event(
            "retrieval",
            {
                "vector_candidates_count": vector_candidates_count,
                "fts_candidates_count": fts_candidates_count,
                "merged_candidates_count": merged_candidates_count,
                "vector_duration_ms": vector_duration_ms,
                "fts_duration_ms": fts_duration_ms,
                "unit": {
                    "vector_candidates_count": "候选数",
                    "fts_candidates_count": "候选数",
                    "merged_candidates_count": "候选数",
                    "vector_duration_ms": "毫秒",
                    "fts_duration_ms": "毫秒",
                },
            },
            conv_id=conv_id,
        )
    if not candidates:
        _emit_rag_telemetry(
            _build_rag_telemetry_payload(
                conversation_id=conv_id,
                knowledge_base_id=conv.knowledge_base_id,
                question=question,
                retrieval_query=retrieval_query,
                vector_candidates_count=vector_candidates_count,
                fts_candidates_count=fts_candidates_count,
                merged_candidates_count=merged_candidates_count,
                rerank_candidates_count=0,
                citations_count=0,
                rewrite_duration_ms=rewrite_duration_ms,
                vector_duration_ms=vector_duration_ms,
                fts_duration_ms=fts_duration_ms,
                rerank_duration_ms=0,
                generation_duration_ms=0,
                total_duration_ms=_duration_ms(total_start, perf_counter()),
                outcome="error",
                error_code="no_knowledge_base",
            )
        )
        if debug:
            yield _build_debug_event(
                "terminal_error",
                _build_debug_error_data(
                    code="no_knowledge_base",
                    message="请先导入知识库",
                    retrieval_query=retrieval_query,
                    vector_candidates_count=vector_candidates_count,
                    fts_candidates_count=fts_candidates_count,
                    merged_candidates_count=merged_candidates_count,
                    rerank_candidates_count=0,
                    citations_count=0,
                    rewrite_duration_ms=rewrite_duration_ms,
                    vector_duration_ms=vector_duration_ms,
                    fts_duration_ms=fts_duration_ms,
                    rerank_duration_ms=0,
                    generation_duration_ms=0,
                ),
            )
        yield {"type": "error", "message": "请先导入知识库"}
        return

    # Rerank
    rerank_start = perf_counter()
    top_chunks, rerank_scores = await _rerank(retrieval_query, candidates)
    rerank_duration_ms = _duration_ms(rerank_start, perf_counter())
    rerank_candidates_count = len(top_chunks)
    if debug:
        yield _build_debug_event(
            "rerank",
            {
                "rerank_candidates_count": rerank_candidates_count,
                "top_chunks": _debug_chunk_preview_with_score(top_chunks, rerank_scores),
                "unit": {
                    "relevance_score": "相关性分数 (0-1)",
                    "rerank_candidates_count": "候选数",
                },
            },
            conv_id=conv_id,
        )
    if not top_chunks:
        _emit_rag_telemetry(
            _build_rag_telemetry_payload(
                conversation_id=conv_id,
                knowledge_base_id=conv.knowledge_base_id,
                question=question,
                retrieval_query=retrieval_query,
                vector_candidates_count=vector_candidates_count,
                fts_candidates_count=fts_candidates_count,
                merged_candidates_count=merged_candidates_count,
                rerank_candidates_count=rerank_candidates_count,
                citations_count=0,
                rewrite_duration_ms=rewrite_duration_ms,
                vector_duration_ms=vector_duration_ms,
                fts_duration_ms=fts_duration_ms,
                rerank_duration_ms=rerank_duration_ms,
                generation_duration_ms=0,
                total_duration_ms=_duration_ms(total_start, perf_counter()),
                outcome="error",
                error_code="no_relevant_context",
            )
        )
        if debug:
            yield _build_debug_event(
                "terminal_error",
                _build_debug_error_data(
                    code="no_relevant_context",
                    message="根据已有文档，无法回答该问题",
                    retrieval_query=retrieval_query,
                    vector_candidates_count=vector_candidates_count,
                    fts_candidates_count=fts_candidates_count,
                    merged_candidates_count=merged_candidates_count,
                    rerank_candidates_count=rerank_candidates_count,
                    citations_count=0,
                    rewrite_duration_ms=rewrite_duration_ms,
                    vector_duration_ms=vector_duration_ms,
                    fts_duration_ms=fts_duration_ms,
                    rerank_duration_ms=rerank_duration_ms,
                    generation_duration_ms=0,
                ),
            )
        yield {"type": "error", "message": "根据已有文档，无法回答该问题"}
        return

    # 构建 prompt
    messages = _build_prompt(question, top_chunks, recent, conv.summary)
    is_first_message = (conv.message_count or 0) == 0

    # 写入用户消息
    await qa_repository.create_message(db, conv_id, "user", question)

    # 更新对话标题（第一条消息）
    if is_first_message:
        await qa_repository.update_conversation_title(db, conv_id, truncate_title(question))

    # gpt-4o streaming
    client = _openai_client()
    full_answer = ""
    generation_start = perf_counter()
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
    except Exception:
        generation_duration_ms = _duration_ms(generation_start, perf_counter())
        _emit_rag_telemetry(
            _build_rag_telemetry_payload(
                conversation_id=conv_id,
                knowledge_base_id=conv.knowledge_base_id,
                question=question,
                retrieval_query=retrieval_query,
                vector_candidates_count=vector_candidates_count,
                fts_candidates_count=fts_candidates_count,
                merged_candidates_count=merged_candidates_count,
                rerank_candidates_count=rerank_candidates_count,
                citations_count=0,
                rewrite_duration_ms=rewrite_duration_ms,
                vector_duration_ms=vector_duration_ms,
                fts_duration_ms=fts_duration_ms,
                rerank_duration_ms=rerank_duration_ms,
                generation_duration_ms=generation_duration_ms,
                total_duration_ms=_duration_ms(total_start, perf_counter()),
                outcome="error",
                error_code="generation_failed",
            )
        )
        if debug:
            yield _build_debug_event(
                "terminal_error",
                _build_debug_error_data(
                    code="generation_failed",
                    message="生成失败，请重试",
                    retrieval_query=retrieval_query,
                    vector_candidates_count=vector_candidates_count,
                    fts_candidates_count=fts_candidates_count,
                    merged_candidates_count=merged_candidates_count,
                    rerank_candidates_count=rerank_candidates_count,
                    citations_count=0,
                    rewrite_duration_ms=rewrite_duration_ms,
                    vector_duration_ms=vector_duration_ms,
                    fts_duration_ms=fts_duration_ms,
                    rerank_duration_ms=rerank_duration_ms,
                    generation_duration_ms=generation_duration_ms,
                ),
            )
        yield {"type": "error", "message": "生成失败，请重试"}
        return
    generation_duration_ms = _duration_ms(generation_start, perf_counter())

    # 提取并校验 citations；无有效引用的答案不能作为可信回答入库。
    try:
        citations = _require_citations(full_answer, top_chunks)
    except CitationValidationError:
        _emit_rag_telemetry(
            _build_rag_telemetry_payload(
                conversation_id=conv_id,
                knowledge_base_id=conv.knowledge_base_id,
                question=question,
                retrieval_query=retrieval_query,
                vector_candidates_count=vector_candidates_count,
                fts_candidates_count=fts_candidates_count,
                merged_candidates_count=merged_candidates_count,
                rerank_candidates_count=rerank_candidates_count,
                citations_count=0,
                rewrite_duration_ms=rewrite_duration_ms,
                vector_duration_ms=vector_duration_ms,
                fts_duration_ms=fts_duration_ms,
                rerank_duration_ms=rerank_duration_ms,
                generation_duration_ms=generation_duration_ms,
                total_duration_ms=_duration_ms(total_start, perf_counter()),
                outcome="error",
                error_code="missing_citations",
            )
        )
        if debug:
            yield _build_debug_event(
                "terminal_error",
                _build_debug_error_data(
                    code="missing_citations",
                    message="生成结果缺少有效引用，请重试",
                    retrieval_query=retrieval_query,
                    vector_candidates_count=vector_candidates_count,
                    fts_candidates_count=fts_candidates_count,
                    merged_candidates_count=merged_candidates_count,
                    rerank_candidates_count=rerank_candidates_count,
                    citations_count=0,
                    rewrite_duration_ms=rewrite_duration_ms,
                    vector_duration_ms=vector_duration_ms,
                    fts_duration_ms=fts_duration_ms,
                    rerank_duration_ms=rerank_duration_ms,
                    generation_duration_ms=generation_duration_ms,
                ),
            )
        yield {"type": "error", "message": "生成结果缺少有效引用，请重试"}
        return
    citations_count = len(citations)

    if debug:
        yield _build_debug_event(
            "citations",
            {
                "citations_count": citations_count,
                "citation_indices": [citation["index"] for citation in citations],
                "unit": {
                    "citations_count": "引用数",
                },
            },
            conv_id=conv_id,
        )
    yield {"type": "citations", "data": citations}

    # 写入 assistant 消息
    msg = await qa_repository.create_message(db, conv_id, "assistant", full_answer, citations or None)

    # 检查是否需要摘要压缩
    updated_conv = await qa_repository.get_conversation_by_id(db, conv_id)
    if updated_conv and (updated_conv.message_count or 0) > SUMMARY_TRIGGER:
        try:
            from backend.app.tasks.qa_tasks import summarize_conversation

            summarize_conversation.apply_async(args=(str(conv_id),))
            logger.info("Enqueued summarization task for conversation %s", conv_id)
        except ImportError as e:
            logger.warning("Failed to import Celery, skipping summarization: %s", e)
        except Exception as e:
            logger.error("Failed to enqueue summarization task: %s", e, exc_info=True)

    _emit_rag_telemetry(
        _build_rag_telemetry_payload(
            conversation_id=conv_id,
            knowledge_base_id=conv.knowledge_base_id,
            question=question,
            retrieval_query=retrieval_query,
            vector_candidates_count=vector_candidates_count,
            fts_candidates_count=fts_candidates_count,
            merged_candidates_count=merged_candidates_count,
            rerank_candidates_count=rerank_candidates_count,
            citations_count=citations_count,
            rewrite_duration_ms=rewrite_duration_ms,
            vector_duration_ms=vector_duration_ms,
            fts_duration_ms=fts_duration_ms,
            rerank_duration_ms=rerank_duration_ms,
            generation_duration_ms=generation_duration_ms,
            total_duration_ms=_duration_ms(total_start, perf_counter()),
            outcome="success",
            error_code=None,
        )
    )
    yield {"type": "done"}
