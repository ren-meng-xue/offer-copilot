from __future__ import annotations

import datetime
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from collections.abc import Sequence
from dataclasses import dataclass
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
from backend.app.services.title_generation_service import generate_conversation_title
from backend.app.services import weather_service
from backend.app.schemas.qa import LocationInput
from backend.app.services.weather_service import WeatherData

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
KEEP_RECENT = 10
DEBUG_PREVIEW_LIMIT = 5


class CitationValidationError(ValueError):
    """Raised when a generated answer cannot be traced to retrieved chunks."""


class ConversationCreationError(ValueError):
    """Raised when a conversation cannot be bound to the requested knowledge base."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class KnowledgeScopeEntry:
    """会话知识范围中的单个知识库成员。"""

    knowledge_base_id: int | None
    name: str
    source_url: str
    route_score: float | None = None
    route_reason: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class ScopeRouteCandidate:
    """首问路由阶段的候选知识库与分数。"""

    knowledge_base: KnowledgeBase
    score: float
    reason: str


def _duration_ms(start: float, end: float) -> int:
    return int((end - start) * 1000)


def _debug_chunk_preview(
    chunks: Sequence[DocumentChunk], limit: int = DEBUG_PREVIEW_LIMIT
) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": str(chunk.id),
            "source_url": chunk.source_url,
            "heading_path": chunk.heading_path or "",
            "chunk_index": chunk.chunk_index,
        }
        for chunk in chunks[:limit]
    ]


def _scope_debug_payload(
    scope_entries: Sequence[KnowledgeScopeEntry],
) -> list[dict[str, Any]]:
    """构造不含正文的 scope debug 信息。"""

    return [
        {
            "knowledge_base_id": entry.knowledge_base_id,
            "name": entry.name,
            "route_score": entry.route_score,
            "route_reason": entry.route_reason,
        }
        for entry in scope_entries
    ]


def _scope_entries_to_response_items(
    scope_entries: Sequence[KnowledgeScopeEntry],
) -> list[dict[str, Any]]:
    """把服务层 scope entry 转成 API 响应可序列化结构。"""

    return [
        {
            "knowledge_base_id": entry.knowledge_base_id,
            "name": entry.name,
            "source_url": entry.source_url,
            "route_score": entry.route_score,
            "route_reason": entry.route_reason,
            "deleted": entry.knowledge_base_id is None,
        }
        for entry in scope_entries
    ]


def _knowledge_base_ids_from_scope(
    scope_entries: Sequence[KnowledgeScopeEntry],
) -> list[int]:
    """提取 scope 中仍然可用的知识库 ID。"""

    return [
        entry.knowledge_base_id
        for entry in scope_entries
        if entry.knowledge_base_id is not None
    ]


def _knowledge_base_names_by_id(
    scope_entries: Sequence[KnowledgeScopeEntry],
) -> dict[int, str]:
    """构造知识库 ID 到名称快照的映射。"""

    return {
        entry.knowledge_base_id: entry.name
        for entry in scope_entries
        if entry.knowledge_base_id is not None
    }


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
    knowledge_base_ids: list[int] | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    resolved_knowledge_base_ids = knowledge_base_ids or (
        [knowledge_base_id] if knowledge_base_id else []
    )
    return {
        "event": "rag_telemetry",
        "conversation_id": str(conversation_id),
        "knowledge_base_id": knowledge_base_id,
        "knowledge_base_ids": resolved_knowledge_base_ids,
        "scope_size": len(resolved_knowledge_base_ids),
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
        # 加上醒目的星号分隔符，防止 JSON 被淹没
        msg = f"\n{'*' * 20} RAG TELEMETRY {'*' * 20}\nrag_telemetry {json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n{'*' * 45}\n"
        logger.info(msg)
        # 强制同步输出
        print(msg, flush=True)
    except Exception:
        return


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )


def _cohere_client() -> cohere.AsyncClientV2:
    return cohere.AsyncClientV2(
        api_key=settings.COHERE_API_KEY,
        base_url=settings.COHERE_BASE_URL,
    )


def _route_tokens(text: str) -> set[str]:
    """提取用于知识库路由的中英文轻量词项。"""

    normalized = text.lower()
    latin_tokens = {
        token
        for token in re.findall(r"[a-z0-9_\-./]{2,}", normalized)
        if len(token.strip("-_./")) >= 2
    }
    chinese_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", normalized))
    # 中文连续句子可能很长，额外取 2-4 字滑窗，增强短问题与摘要的匹配。
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    windows: set[str] = set()
    for size in (2, 3, 4):
        for index in range(max(len(chinese_chars) - size + 1, 0)):
            windows.add("".join(chinese_chars[index : index + size]))
    return latin_tokens | chinese_tokens | windows


def _score_knowledge_base_for_question(
    question: str, kb: KnowledgeBase
) -> ScopeRouteCandidate:
    """基于问题与知识库元数据的重叠程度计算路由分数。"""

    question_tokens = _route_tokens(question)
    metadata_text = " ".join(
        part for part in [kb.name, kb.summary or "", kb.source_url] if part
    )
    metadata_tokens = _route_tokens(metadata_text)
    overlap = question_tokens & metadata_tokens

    if not question_tokens:
        return ScopeRouteCandidate(kb, 0, "问题缺少可用于路由的关键词")

    score = len(overlap) / max(len(question_tokens), 1)
    if kb.name and kb.name.lower() in question.lower():
        score += 0.4
    score = min(score, 1.0)

    if overlap:
        reason = f"问题关键词匹配：{', '.join(sorted(overlap)[:5])}"
    else:
        reason = "未命中知识库名称、摘要或来源 URL"
    return ScopeRouteCandidate(kb, score, reason)


async def route_knowledge_scope(
    db: AsyncSession,
    user_id: int,
    question: str,
) -> list[ScopeRouteCandidate]:
    """根据首问自动选择最多 3 个可用知识库。"""

    knowledge_bases = await knowledge_repository.list_done_knowledge_bases_by_user(
        db, user_id
    )
    if not knowledge_bases:
        # 不再报错，允许创建空范围会话（用于闲聊或后续手动关联）
        return []

    if len(knowledge_bases) == 1:
        kb = knowledge_bases[0]
        return [
            ScopeRouteCandidate(kb, 1.0, "当前只有一个可用知识库，自动作为本次范围")
        ]

    candidates = [
        _score_knowledge_base_for_question(question, kb) for kb in knowledge_bases
    ]
    candidates.sort(
        key=lambda item: (item.score, item.knowledge_base.updated_at), reverse=True
    )
    selected = [
        item for item in candidates if item.score >= settings.RAG_SCOPE_ROUTE_MIN_SCORE
    ][: settings.RAG_SCOPE_MAX_KNOWLEDGE_BASES]

    # 不再报错，允许创建空范围会话
    return selected


def _scope_items_from_candidates(
    candidates: Sequence[ScopeRouteCandidate],
) -> list[dict[str, Any]]:
    """把 route candidates 转成 repository 可写入结构。"""

    return [
        {
            "knowledge_base_id": candidate.knowledge_base.id,
            "knowledge_base_name_snapshot": candidate.knowledge_base.name,
            "source_url_snapshot": candidate.knowledge_base.source_url,
            "route_score": candidate.score,
            "route_reason": candidate.reason,
        }
        for candidate in candidates
    ]


async def create_conversation(
    db: AsyncSession,
    user_id: int,
    knowledge_base_id: int | None = None,
    question: str | None = None,
):
    """创建会话；新路径基于首问自动路由知识范围，旧路径兼容单知识库。"""

    if question:
        candidates = await route_knowledge_scope(db, user_id, question)
        return await qa_repository.create_conversation_with_scope(
            db,
            user_id,
            _scope_items_from_candidates(candidates),
        )

    if knowledge_base_id is None:
        raise ConversationCreationError(
            "缺少问题或知识库", "conversation_scope_missing"
        )

    kb = await knowledge_repository.get_knowledge_base_by_id(db, knowledge_base_id)
    if kb is None or kb.user_id != user_id:
        raise ConversationCreationError("知识库不存在", "knowledge_base_not_found")
    if kb.status != KnowledgeBaseStatus.DONE:
        raise ConversationCreationError(
            "知识库尚未完成索引", "knowledge_base_not_ready"
        )
    return await qa_repository.create_conversation_with_scope(
        db,
        user_id,
        [
            {
                "knowledge_base_id": kb.id,
                "knowledge_base_name_snapshot": kb.name,
                "source_url_snapshot": kb.source_url,
                "route_score": None,
                "route_reason": "旧单知识库创建路径兼容",
            }
        ],
    )


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
        .limit(settings.RAG_VECTOR_TOP_K_PER_KB)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _fts_search(
    db: AsyncSession, user_id: int, knowledge_base_id: int, query: str
) -> list[DocumentChunk]:
    # 使用 pg_trgm word_similarity，支持中英文关键词匹配
    similarity = func.word_similarity(query, DocumentChunk.content)
    stmt = (
        select(DocumentChunk)
        .join(KnowledgeBase, DocumentChunk.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.user_id == user_id)
        .where(KnowledgeBase.id == knowledge_base_id)
        .where(similarity > 0.15)
        .order_by(similarity.desc())
        .limit(settings.RAG_FTS_TOP_K_PER_KB)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _resolve_conversation_scope(
    db: AsyncSession,
    conv: Any,
    user_id: int,
) -> list[KnowledgeScopeEntry]:
    """解析会话锁定的知识范围，兼容旧单知识库会话。"""

    try:
        scope_items = await qa_repository.list_scope_items_by_conversation_id(
            db, conv.id
        )
    except Exception as exc:
        logger.debug(
            "Load conversation scope failed, fallback to legacy scope: %s", exc
        )
        scope_items = []

    if scope_items:
        entries = [
            KnowledgeScopeEntry(
                knowledge_base_id=item.knowledge_base_id,
                name=item.knowledge_base_name_snapshot,
                source_url=item.source_url_snapshot,
                route_score=item.route_score,
                route_reason=item.route_reason,
            )
            for item in scope_items
        ]
    elif getattr(conv, "knowledge_base_id", None) is not None:
        try:
            kb = await knowledge_repository.get_knowledge_base_by_id(
                db, conv.knowledge_base_id
            )
        except Exception as exc:
            logger.debug(
                "Load legacy knowledge base failed, using id-only scope: %s", exc
            )
            kb = None
        if kb is None:
            entries = [
                KnowledgeScopeEntry(
                    knowledge_base_id=conv.knowledge_base_id,
                    name=f"Knowledge Base {conv.knowledge_base_id}",
                    source_url="",
                    route_reason="历史单知识库会话兼容",
                )
            ]
        else:
            entries = [
                KnowledgeScopeEntry(
                    knowledge_base_id=kb.id,
                    name=kb.name,
                    source_url=kb.source_url,
                    route_reason="历史单知识库会话兼容",
                    summary=kb.summary,
                )
            ]
    else:
        return []

    available_ids = _knowledge_base_ids_from_scope(entries)
    if not available_ids:
        raise ConversationCreationError(
            "当前会话范围中的知识库已不可用", "conversation_scope_unavailable"
        )

    try:
        knowledge_bases = await knowledge_repository.get_knowledge_bases_by_ids(
            db, available_ids
        )
    except Exception as exc:
        logger.debug(
            "Validate conversation scope failed, using current scope only: %s", exc
        )
        return entries
    by_id = {kb.id: kb for kb in knowledge_bases}
    for entry in entries:
        if entry.knowledge_base_id is None:
            raise ConversationCreationError(
                "当前会话范围中的知识库已不可用", "conversation_scope_unavailable"
            )
        kb = by_id.get(entry.knowledge_base_id)
        if kb is None or kb.user_id != user_id or kb.status != KnowledgeBaseStatus.DONE:
            raise ConversationCreationError(
                "当前会话范围中的知识库已不可用", "conversation_scope_unavailable"
            )

    return [
        KnowledgeScopeEntry(
            knowledge_base_id=entry.knowledge_base_id,
            name=entry.name,
            source_url=entry.source_url,
            route_score=entry.route_score,
            route_reason=entry.route_reason,
            summary=by_id[entry.knowledge_base_id].summary
            if entry.knowledge_base_id in by_id
            else None,
        )
        for entry in entries
    ]


async def _vector_search_scope(
    db: AsyncSession,
    user_id: int,
    scope_entries: Sequence[KnowledgeScopeEntry],
    query_vec: list[float],
) -> list[DocumentChunk]:
    """对 scope 内每个知识库分别执行向量召回。"""

    chunks: list[DocumentChunk] = []
    for knowledge_base_id in _knowledge_base_ids_from_scope(scope_entries):
        chunks.extend(await _vector_search(db, user_id, knowledge_base_id, query_vec))
    return chunks


async def _fts_search_scope(
    db: AsyncSession,
    user_id: int,
    scope_entries: Sequence[KnowledgeScopeEntry],
    query: str,
) -> list[DocumentChunk]:
    """对 scope 内每个知识库分别执行全文召回。"""

    chunks: list[DocumentChunk] = []
    for knowledge_base_id in _knowledge_base_ids_from_scope(scope_entries):
        chunks.extend(await _fts_search(db, user_id, knowledge_base_id, query))
    return chunks


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
        ranked_chunks = _filter_rerank_results(
            chunks, resp.results, settings.RAG_MIN_RERANK_SCORE
        )

        return ranked_chunks, scores[: len(ranked_chunks)]
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
        rewritten = next(
            (line.strip() for line in content.splitlines() if line.strip()), ""
        )
        return rewritten or question
    except Exception as e:
        logger.warning(
            "Query rewrite failed, using original question: %s", e, exc_info=False
        )
        return question


_GREETING_RE = re.compile(
    r"^(你好|您好|hi|hello|嗨|谢谢|感谢|再见|拜拜|bye|早上好|下午好|晚上好|哈喽)[\s，。！!？?]*$",
    re.IGNORECASE,
)


def _is_greeting(question: str) -> bool:
    return bool(_GREETING_RE.match(question.strip()))


_IDENTITY_RE = re.compile(
    r"^(你是谁|您是谁|你叫什么|你叫什么名字|你是什么|你是什么助手|介绍.{0,4}自己|你能做什么|你有什么功能|你能帮.*什么)[\s，。！!？?]*$",
    re.IGNORECASE,
)


def _is_identity_question(question: str) -> bool:
    return bool(_IDENTITY_RE.match(question.strip()))


async def _is_kb_listing(
    question: str, recent_messages: list[Message] | None = None
) -> bool:
    """判断用户是否在询问"有哪些知识库/文档"，返回 True/False。失败时返回 False 以保证进入检索流程。"""
    try:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是一个意图分类助手。请判断用户是否在询问当前有哪些知识库或已导入的文档。\n"
                    "如果是，回答 YES；否则回答 NO。\n"
                    "只输出 YES 或 NO，不要输出其他内容。"
                ),
            }
        ]
        if recent_messages:
            for msg in recent_messages:
                messages.append({"role": msg.role, "content": msg.content[:200]})
        messages.append({"role": "user", "content": question})
        client = _openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            max_tokens=5,
        )
        return (resp.choices[0].message.content or "NO").strip().upper() == "YES"
    except Exception as e:
        logger.warning("KB listing check failed: %s", e)
        return False


async def _is_weather_query(
    question: str, recent_messages: list[Message] | None = None
) -> bool:
    """判断用户是否在询问天气（当天或预报），含追问城市名的场景。失败时返回 False。"""
    try:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是一个意图分类助手。请判断用户是否在询问天气信息（当天天气、明天天气、未来几天预报等），"
                    "或者是在回答上一轮助手关于城市的追问（如助手问「您想查询哪里的天气」，用户回复「北京」）。\n"
                    "如果是，回答 YES；否则回答 NO。\n"
                    "只输出 YES 或 NO，不要输出其他内容。"
                ),
            }
        ]
        if recent_messages:
            for msg in recent_messages:
                messages.append({"role": msg.role, "content": msg.content[:200]})
        messages.append({"role": "user", "content": question})
        client = _openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            max_tokens=5,
        )
        return (resp.choices[0].message.content or "NO").strip().upper() == "YES"
    except Exception as e:
        logger.warning("Weather query check failed: %s", e)
        return False


async def _extract_city_from_question(question: str) -> str | None:
    """从问题文本中提取城市名，提取不到返回 None。"""
    try:
        client = _openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "从用户的问题中提取城市名。如果有城市名，只输出城市名（如「北京」「上海」「成都市」），"
                        "不要输出任何其他内容。如果没有城市名，输出 NONE。"
                    ),
                },
                {"role": "user", "content": question},
            ],  # type: ignore[arg-type]
            temperature=0,
            max_tokens=20,
        )
        result = (resp.choices[0].message.content or "NONE").strip()
        return None if result.upper() == "NONE" else result
    except Exception as e:
        logger.warning("City extraction failed: %s", e)
        return None


async def _resolve_city_adcode(
    question: str,
    location: "LocationInput | None",  # noqa: F821
    recent_messages: list[Message],
) -> str | None:
    """按优先级解析城市 adcode：坐标逆解 → 问题文本提取 → 对话历史城市名。"""
    # 1. 坐标逆解
    if location is not None:
        adcode = await weather_service.reverse_geocode(location.lat, location.lng)
        if adcode:
            return adcode

    # 2. 从问题文本提取城市名
    city = await _extract_city_from_question(question)
    if city:
        adcode = await weather_service.geocode_city(city)
        if adcode:
            return adcode

    # 3. 从对话历史提取（用户回答了追问）
    for msg in reversed(recent_messages):
        if msg.role == "user" and len(msg.content.strip()) <= 20:
            adcode = await weather_service.geocode_city(msg.content.strip())
            if adcode:
                return adcode

    return None


def _build_weather_prompt(
    question: str,
    weather: WeatherData,
    recent_messages: list[Message],
) -> list[dict[str, str]]:
    """把天气数据拼入 system prompt，让 LLM 用自然语言回答。"""
    live = weather.live
    live_text = (
        f"{weather.city}当前天气：{live.weather}，气温 {live.temperature}°C，"
        f"{live.wind_direction}风 {live.wind_power} 级，湿度 {live.humidity}%。"
    )
    forecast_lines = []
    for day in weather.forecast:
        forecast_lines.append(
            f"{day.date}：白天 {day.day_weather} {day.day_temp}°C / "
            f"夜间 {day.night_weather} {day.night_temp}°C，{day.day_wind}风 {day.day_power} 级"
        )
    forecast_text = "\n".join(forecast_lines)

    system = (
        "我是你的个人助手。请根据以下天气数据，用自然、简洁的中文回答用户的天气问题。\n\n"
        f"【实况】{live_text}\n"
        f"【预报】\n{forecast_text}"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


async def _classify_retrieval_intent(
    question: str, recent_messages: list[Message] | None = None
) -> str:
    """判断检索意图：MACRO_RETRIEVAL（宏观总结）或 MICRO_RETRIEVAL（具体内容）。"""
    try:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是一个意图分类助手。请判断用户输入属于哪种检索类别：\n"
                    "1. MACRO_RETRIEVAL: 涉及全局总结、主要模块介绍、项目背景、文档大纲，"
                    "或询问这份文档/知识库整体讲了什么。\n"
                    "2. MICRO_RETRIEVAL: 涉及具体细节、配置项、步骤、代码、个人信息、"
                    "或任何需要从文档中查找具体内容的问题。\n"
                    "只输出类别名称（MACRO_RETRIEVAL 或 MICRO_RETRIEVAL），不要输出其他任何内容。"
                ),
            }
        ]
        if recent_messages:
            for msg in recent_messages:
                messages.append({"role": msg.role, "content": msg.content[:200]})
        messages.append({"role": "user", "content": question})
        client = _openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            max_tokens=20,
        )
        content = (resp.choices[0].message.content or "MICRO_RETRIEVAL").strip().upper()
        if content in ["MACRO_RETRIEVAL", "MICRO_RETRIEVAL"]:
            return content
        return "MICRO_RETRIEVAL"
    except Exception as e:
        logger.warning("Retrieval intent classification failed: %s", e)
        return "MICRO_RETRIEVAL"


async def _send_general_response(
    db: AsyncSession,
    conv_id: uuid.UUID,
    question: str,
    messages: list[dict[str, str]],
    conv_message_count: int,
    label: str = "general",
) -> AsyncGenerator[dict[str, Any], None]:
    """流式发送非检索回复（招呼/通用/无知识库兜底），写入消息记录后返回事件流。"""
    client = _openai_client()
    full_answer = ""
    try:
        is_first_message = (conv_message_count or 0) == 0
        await qa_repository.create_message(db, conv_id, "user", question)
        if is_first_message:
            await qa_repository.update_conversation_title(
                db, conv_id, truncate_title(question)
            )
            smart_title = await generate_conversation_title(question)
            if smart_title:
                await qa_repository.update_conversation_title(db, conv_id, smart_title)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,  # type: ignore[arg-type]
            stream=True,
        )
        async for chunk in resp:
            token = chunk.choices[0].delta.content or ""
            if token:
                full_answer += token
                yield {"type": "token", "content": token}
        await qa_repository.create_message(db, conv_id, "assistant", full_answer, None)
        yield {"type": "no_citations_required"}
        yield {"type": "done"}
    except Exception as e:
        logger.error("%s response failed: %s", label, e)
        yield {"type": "error", "message": "生成回答失败，请稍后重试"}


def _build_kb_listing_prompt(
    question: str,
    knowledge_bases: list[KnowledgeBase],
    recent_messages: list[Message],
) -> list[dict[str, str]]:
    """为知识库列表查询构建 Prompt。"""
    kb_list_str = "\n".join(
        f"- {kb.name}: {kb.summary or '暂无摘要'}" for kb in knowledge_bases
    )
    if not kb_list_str:
        kb_list_str = "当前没有任何已完成的知识库。"

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "我是你的个人助手。用户正在询问当前有哪些知识库或文档。\n"
                "请根据以下提供的知识库列表回答用户。如果列表为空，请告知用户当前没有文档，可以先导入文档。\n\n"
                f"当前可用的知识库列表：\n{kb_list_str}\n\n"
                "请礼貌且清晰地列出这些知识库，并鼓励用户针对这些内容进行提问。"
            ),
        }
    ]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


def _build_weather_ask_city_prompt(
    question: str,
    recent_messages: list[Message],
) -> list[dict[str, str]]:
    """当无法确定城市时，引导用户提供城市名称。"""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "你是一个友好的个人助手。用户询问了天气，但未提供城市信息。"
                "请简短、自然地询问用户想查询哪个城市的天气，不要超过两句话。"
            ),
        }
    ]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


def _build_weather_fetch_error_prompt(
    question: str,
    recent_messages: list[Message],
) -> list[dict[str, str]]:
    """当天气 API 获取失败时，告知用户稍后重试。"""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "你是一个友好的个人助手。用户询问了天气，但天气数据暂时无法获取。"
                "请简短、友好地告知用户天气信息暂时获取失败，建议稍后重试，不要超过两句话。"
            ),
        }
    ]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


def _build_identity_prompt(
    question: str,
    recent_messages: list[Message],
) -> list[dict[str, str]]:
    """为用户询问助手身份构建 Prompt。"""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "你是用户的个人助手。当用户询问你是谁时，请简短地介绍自己是用户的个人助手，"
                "并告知可以帮助用户基于文档进行知识问答，以及回答天气等日常问题。"
            ),
        }
    ]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


def _build_general_prompt(
    question: str,
    recent_messages: list[Message],
    summary: str | None = None,
) -> list[dict[str, str]]:
    """为通用闲聊构建 Prompt。"""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": "你是一个友好的个人助手。对于用户的招呼或闲聊，请礼貌且简洁地回复，并告知用户你可以基于文档提供专业的技术问答支持。",
        }
    ]
    if summary:
        messages.append({"role": "system", "content": f"历史摘要：{summary}"})

    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


def _build_prompt(
    question: str,
    chunks: list[DocumentChunk],
    recent_messages: list[Message],
    summary: str | None,
    kb_summary: str | None = None,
    knowledge_base_names_by_id: dict[int, str] | None = None,
) -> list[dict[str, str]]:
    knowledge_base_names_by_id = knowledge_base_names_by_id or {}
    context_parts = []
    for i, chunk in enumerate(chunks):
        kb_name = knowledge_base_names_by_id.get(chunk.knowledge_base_id)
        source_prefix = f"知识库：{kb_name}\n" if kb_name else ""
        context_parts.append(
            f"[{i + 1}] {source_prefix}章节：{chunk.heading_path or ''}\n{chunk.content}"
        )
    context_str = "\n\n".join(context_parts)

    system = (
        "你是一个友好的个人助手。只基于提供的上下文回答问题。"
        "回答中必须用 [1]、[2] 等编号引用对应的微观上下文来源。"
        "如果回答是基于知识库的全局摘要（摘要内容见下文），请在回答中明确提到知识库的名称（例如：根据《XXX知识库》的摘要...）。"
        "如果问题是学习路线、概念解释、总结或建议类问题，只要上下文或摘要包含相关概念，"
        "就必须基于相关内容综合回答。"
        "只有当上下文和摘要与问题完全无关时，才回答'根据已有文档，无法回答该问题'。"
    )

    if kb_summary:
        system += f"\n\n知识库全局摘要（用于回答宏观问题）:\n{kb_summary}"

    if context_str:
        system += f"\n\n具体相关上下文片段:\n{context_str}"

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    if summary:
        messages.append({"role": "system", "content": f"历史摘要：{summary}"})

    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": question})
    return messages


def _extract_citations(
    answer: str,
    chunks: list[DocumentChunk],
    knowledge_base_names_by_id: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    # 匹配多种引用格式：[1], (1), 【1】, <1>
    pattern = r"[\[\(【<](\d+)[\]\)】>]"
    indices = sorted({int(m) - 1 for m in re.findall(pattern, answer)})

    citations = []

    # 如果有具体的 chunks，按原始逻辑提取
    if chunks:
        for idx in indices:
            if 0 <= idx < len(chunks):
                c = chunks[idx]
                citation = {
                    "index": idx + 1,
                    "chunk_id": str(c.id),
                    "source_url": c.source_url,
                    "heading_path": c.heading_path or "",
                    "snippet": c.content[:MAX_SNIPPET_LEN],
                }
                if knowledge_base_names_by_id is not None:
                    citation["knowledge_base_id"] = c.knowledge_base_id
                    citation["knowledge_base_name"] = knowledge_base_names_by_id.get(
                        c.knowledge_base_id
                    )
                citations.append(citation)

    # 兜底逻辑：如果没有匹配到 chunk 引用，或者 chunks 为空（宏观问答场景）
    # 检查是否提到了知识库名称
    if not citations and knowledge_base_names_by_id:
        for kb_id, kb_name in knowledge_base_names_by_id.items():
            if kb_name in answer:
                citations.append(
                    {
                        "index": len(citations) + 1,
                        "chunk_id": "",  # 宏观引用无具体 chunk
                        "knowledge_base_id": kb_id,
                        "knowledge_base_name": kb_name,
                        "source_url": "",  # 可以在这里补充 repository 里的主 URL，暂设为空
                        "heading_path": "全局摘要",
                        "snippet": f"该回答基于知识库《{kb_name}》的整体摘要生成。",
                    }
                )

    return citations


def _require_citations(
    answer: str,
    chunks: list[DocumentChunk],
    knowledge_base_names_by_id: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    citations = _extract_citations(answer, chunks, knowledge_base_names_by_id)
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
    location: LocationInput | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    yield {"type": "ping"}
    debug = debug and settings.DEBUG and settings.RAG_DEBUG_ENABLED
    total_start = perf_counter()
    try:
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
        scope_entries: list[KnowledgeScopeEntry] = []
        knowledge_base_ids: list[int] = []
        knowledge_base_names_by_id: dict[int, str] = {}

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
        try:
            scope_entries = await _resolve_conversation_scope(db, conv, user_id)
        except ConversationCreationError as exc:
            if debug:
                yield _build_debug_event(
                    "terminal_error",
                    _build_debug_error_data(
                        code=exc.code,
                        message=str(exc),
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
                "code": exc.code,
                "message": str(exc),
            }
            return
        knowledge_base_ids = _knowledge_base_ids_from_scope(scope_entries)
        knowledge_base_names_by_id = _knowledge_base_names_by_id(scope_entries)

        # 预先获取历史消息，用于意图识别和后续 Prompt 构建
        recent = await qa_repository.get_recent_messages(db, conv_id, limit=KEEP_RECENT)

        # 1. 快速通道：打招呼（正则）→ 通用回复；知识库列表（LLM 二分类）→ 列出知识库
        #    其余全部进入检索流程（检索优先）
        if _is_greeting(question):
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_general_prompt(question, recent, conv.summary),
                conv.message_count or 0,
                "greeting",
            ):
                yield event
            return

        if _is_identity_question(question):
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_identity_prompt(question, recent),
                conv.message_count or 0,
                "identity",
            ):
                yield event
            return

        if await _is_kb_listing(question, recent):
            knowledge_bases = (
                await knowledge_repository.list_done_knowledge_bases_by_user(
                    db, user_id
                )
            )
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_kb_listing_prompt(question, knowledge_bases, recent),
                conv.message_count or 0,
                "kb_listing",
            ):
                yield event
            return

        if await _is_weather_query(question, recent):
            adcode = await _resolve_city_adcode(question, location, recent)
            if adcode is None:
                async for event in _send_general_response(
                    db,
                    conv_id,
                    question,
                    _build_weather_ask_city_prompt(question, recent),
                    conv.message_count or 0,
                    "weather_ask_city",
                ):
                    yield event
                return
            weather_data = await weather_service.fetch_weather(adcode)
            if weather_data is None:
                async for event in _send_general_response(
                    db,
                    conv_id,
                    question,
                    _build_weather_fetch_error_prompt(question, recent),
                    conv.message_count or 0,
                    "weather_fetch_error",
                ):
                    yield event
                return
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_weather_prompt(question, weather_data, recent),
                conv.message_count or 0,
                "weather",
            ):
                yield event
            return

        # 2. 检索意图处理 (MACRO 或 MICRO)
        intent = await _classify_retrieval_intent(question, recent)
        # 如果当前 Scope 为空，则触发"延迟路由"
        if not scope_entries:
            logger.info(
                "Current scope is empty, triggering delayed routing for question: %s",
                question,
            )
            candidates = await route_knowledge_scope(db, user_id, question)
            if candidates:
                await qa_repository.add_scope_items_to_conversation(
                    db, conv_id, _scope_items_from_candidates(candidates)
                )
                # 重新解析 Scope
                scope_entries = await _resolve_conversation_scope(db, conv, user_id)
                knowledge_base_ids = _knowledge_base_ids_from_scope(scope_entries)
                knowledge_base_names_by_id = _knowledge_base_names_by_id(scope_entries)

        if not scope_entries:
            # 路由未找到匹配知识库，降级为通用回复（不报错）
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_general_prompt(question, recent, conv.summary),
                conv.message_count or 0,
                "no_scope_fallback",
            ):
                yield event
            return

        # 获取知识库摘要以增强全局理解
        kb_summary = (
            "\n\n".join(
                f"{entry.name}: {entry.summary}"
                for entry in scope_entries
                if entry.summary
            )
            or None
        )

        top_chunks = []
        rerank_scores = []

        # 如果是 MICRO_RETRIEVAL，执行完整检索
        if intent == "MICRO_RETRIEVAL":
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
                    },
                    conv_id=conv_id,
                )

            # 向量检索
            embedding_start = perf_counter()
            [query_vec] = await generate_embeddings([retrieval_query])
            embedding_duration_ms = _duration_ms(embedding_start, perf_counter())
            if debug:
                yield _build_debug_event(
                    "embedding",
                    {"embedding_duration_ms": embedding_duration_ms},
                    conv_id=conv_id,
                )

            vector_start = perf_counter()
            vector_candidates = await _vector_search_scope(
                db, user_id, scope_entries, query_vec
            )
            vector_duration_ms = _duration_ms(vector_start, perf_counter())
            vector_candidates_count = len(vector_candidates)

            # 全文检索
            try:
                fts_start = perf_counter()
                fts_candidates = await _fts_search_scope(
                    db, user_id, scope_entries, retrieval_query
                )
                fts_duration_ms = _duration_ms(fts_start, perf_counter())
            except Exception as e:
                logger.warning("FTS search failed: %s", e)
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
                    },
                    conv_id=conv_id,
                )

            # Rerank
            if candidates:
                rerank_start = perf_counter()
                top_chunks, rerank_scores = await _rerank(retrieval_query, candidates)
                rerank_duration_ms = _duration_ms(rerank_start, perf_counter())
                rerank_candidates_count = len(top_chunks)
                if debug:
                    yield _build_debug_event(
                        "rerank",
                        {
                            "rerank_candidates_count": rerank_candidates_count,
                            "top_chunks_preview": _debug_chunk_preview_with_score(
                                top_chunks, rerank_scores
                            ),
                        },
                        conv_id=conv_id,
                    )

        # 兜底判断：如果既没有微观切片（或 MACRO 意图跳过了微观检索），也没有全局摘要，则报错
        if not top_chunks and not kb_summary:
            if debug:
                yield _build_debug_event(
                    "terminal_error",
                    {"error_code": "no_relevant_context"},
                    conv_id=conv_id,
                )
            _emit_rag_telemetry(
                _build_rag_telemetry_payload(
                    conversation_id=conv_id,
                    knowledge_base_id=knowledge_base_ids[0]
                    if knowledge_base_ids
                    else None,
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
                    knowledge_base_ids=knowledge_base_ids,
                    error_code="no_relevant_context",
                )
            )
            yield {"type": "error", "message": "根据已有文档，无法回答该问题"}
            return

        # 构建提示词并进入生成阶段
        messages = _build_prompt(
            question,
            top_chunks,
            recent,
            conv.summary,
            kb_summary,
            knowledge_base_names_by_id,
        )
        is_first_message = (conv.message_count or 0) == 0

        # 写入用户消息
        await qa_repository.create_message(db, conv_id, "user", question)

        # 更新对话标题（第一条消息）
        if is_first_message:
            await qa_repository.update_conversation_title(
                db, conv_id, truncate_title(question)
            )
            # 异步获取智能标题（仅基于问题）
            smart_title = await generate_conversation_title(question)
            if smart_title:
                await qa_repository.update_conversation_title(db, conv_id, smart_title)

    except Exception as e:
        logger.error("Error in stream_answer preamble: %s", e, exc_info=True)
        yield {"type": "error", "message": f"检索初始化失败: {str(e)}"}
        return

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
                knowledge_base_id=knowledge_base_ids[0] if knowledge_base_ids else None,
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
                knowledge_base_ids=knowledge_base_ids,
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
    # 优化：如果是基于全局摘要回答且没有切片，则放宽校验。
    try:
        citations = _require_citations(
            full_answer, top_chunks, knowledge_base_names_by_id
        )
    except CitationValidationError:
        _emit_rag_telemetry(
            _build_rag_telemetry_payload(
                conversation_id=conv_id,
                knowledge_base_id=knowledge_base_ids[0] if knowledge_base_ids else None,
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
                knowledge_base_ids=knowledge_base_ids,
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
    await qa_repository.create_message(
        db, conv_id, "assistant", full_answer, citations or None
    )

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
            knowledge_base_id=knowledge_base_ids[0] if knowledge_base_ids else None,
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
            knowledge_base_ids=knowledge_base_ids,
            error_code=None,
        )
    )
    yield {"type": "done"}
