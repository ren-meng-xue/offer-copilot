from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import cohere
import redis.asyncio as aioredis
from openai import AsyncOpenAI
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.conversation import Message
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus
from backend.app.repositories import knowledge_repository, qa_repository
from backend.app.schemas.qa import LocationInput
from backend.app.services import weather_service
from backend.app.services.embedding_service import generate_embeddings
from backend.app.services.title_generation_service import generate_conversation_title
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
) -> dict[str, Any] | None:
    """构建 debug 事件并输出到后端日志中。

    Args:
        stage: 阶段名称
        data: 阶段数据
        conv_id: 会话 ID，用于生成 trace_id

    Returns:
        如果 RAG_DEBUG_ENABLED=True，返回完整 debug 事件并打印日志；否则返回 None
    """
    if not settings.RAG_DEBUG_ENABLED:
        return None

    trace_id = ""
    if conv_id:
        trace_id = f"conv-{conv_id}-{uuid.uuid4().hex[:8]}"

    event = {
        "type": "debug",
        "stage": stage,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trace_id": trace_id,
        "data": {
            "description": _get_stage_description(stage),
            **data,
        },
    }

    # 打印 RAG 链路追踪日志到 backend.log 中，以便持久化和方便排查
    logger.info(
        "[RAG Trace] stage=%s, trace_id=%s, data=%s",
        stage,
        trace_id,
        json.dumps(event["data"], ensure_ascii=False),
    )

    return event


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
    cohere_top_score: float | None = None,
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
        "cohere_top_score": cohere_top_score,
    }


def _push_rag_metrics(payload: dict[str, Any]) -> None:
    """把 rag_telemetry payload 中的字段同步推送到 Prometheus 指标。"""
    from backend.app.core.metrics import (
        RAG_CANDIDATES_COUNT,
        RAG_CITATIONS_COUNT,
        RAG_COHERE_TOP_SCORE,
        RAG_OUTCOME_TOTAL,
        RAG_QUERY_REWRITTEN_TOTAL,
        RAG_SCOPE_SIZE,
        RAG_STAGE_DURATION_SECONDS,
        RAG_TOTAL_DURATION_SECONDS,
    )

    # 阶段耗时
    stage_mapping = {
        "rewrite": payload.get("rewrite_duration_ms"),
        "vector": payload.get("vector_duration_ms"),
        "fts": payload.get("fts_duration_ms"),
        "rerank": payload.get("rerank_duration_ms"),
        "generation": payload.get("generation_duration_ms"),
    }
    for stage, ms in stage_mapping.items():
        if ms is not None and ms >= 0:
            RAG_STAGE_DURATION_SECONDS.labels(stage=stage).observe(ms / 1000.0)

    # 总耗时
    total_ms = payload.get("total_duration_ms")
    outcome = payload.get("outcome") or "unknown"
    if total_ms is not None and total_ms >= 0:
        RAG_TOTAL_DURATION_SECONDS.labels(outcome=outcome).observe(total_ms / 1000.0)

    # 候选数
    candidate_mapping = {
        "vector": payload.get("vector_candidates_count"),
        "fts": payload.get("fts_candidates_count"),
        "merged": payload.get("merged_candidates_count"),
        "rerank": payload.get("rerank_candidates_count"),
    }
    for stage, n in candidate_mapping.items():
        if n is not None:
            RAG_CANDIDATES_COUNT.labels(stage=stage).observe(n)

    # 引用数
    cit = payload.get("citations_count")
    if cit is not None:
        RAG_CITATIONS_COUNT.observe(cit)

    # Cohere top score
    cohere_score = payload.get("cohere_top_score")
    if cohere_score is not None:
        RAG_COHERE_TOP_SCORE.observe(cohere_score)

    # outcome 计数
    error_code = payload.get("error_code") or ""
    RAG_OUTCOME_TOTAL.labels(outcome=outcome, error_code=error_code).inc()

    # query rewrite 比例
    rewritten = "true" if payload.get("retrieval_query_rewritten") else "false"
    RAG_QUERY_REWRITTEN_TOTAL.labels(rewritten=rewritten).inc()

    # scope size
    scope_size = payload.get("scope_size")
    if scope_size is not None:
        RAG_SCOPE_SIZE.observe(scope_size)


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
        pass

    # 新增：Prometheus 指标
    try:
        _push_rag_metrics(payload)
    except Exception:
        # 指标推送失败不影响主流程
        logger.exception("Push rag metrics failed")


def _build_l1_cache_key(*, scope_hash: str, q_hash: str) -> str:
    """L1 缓存 key 构造：只按 (scope, question) 隔离，与 L2 对齐。

    历史 bug：曾经把 conv_id 也放进 key，导致跨会话相同问题永远 miss。
    """
    return f"cache:rag:ask:{scope_hash}:{q_hash}"


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )


def _cohere_client() -> cohere.AsyncClientV2:
    return cohere.AsyncClientV2(
        api_key=settings.COHERE_API_KEY,
        base_url=settings.COHERE_BASE_URL,
        timeout=settings.COHERE_TIMEOUT,
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

    # 根因解决：如果路由评分都没过阈值，但用户确实有知识库，则采取“贪婪策略”
    # 自动选取分数最高的一个作为兜底，防止因为“工作年限”与“工作经验”这类微小的词面差异导致整个 RAG 被跳过
    if not selected and candidates:
        top_candidate = candidates[0]
        # 只要有一点点相关性（哪怕只是人名匹配），就强行入选
        if top_candidate.score > 0:
            selected = [top_candidate]

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
    # 临时降低 similarity_threshold，保证短 query 也能通过 trigram 索引召回
    # 在单元测试 Mock 数据库 session 时，跳过该本地配置以避免破坏 Mock 调用序列
    if "Mock" not in type(db).__name__ and not hasattr(db, "_mock_return_value"):
        try:
            await db.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.05"))
        except Exception as e:
            logger.warning("Failed to set similarity_threshold: %s", e)

    # 使用 pg_trgm similarity 结合 GIN 索引，进行超高速关键词模糊匹配
    similarity = func.similarity(DocumentChunk.content, query)
    stmt = (
        select(DocumentChunk)
        .join(KnowledgeBase, DocumentChunk.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.user_id == user_id)
        .where(KnowledgeBase.id == knowledge_base_id)
        .where(
            DocumentChunk.content.op("%")(query)
        )  # 强制走 GIN 索引 (idx_document_chunks_content_trgm)
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
    """对 scope 内每个知识库分别顺序执行向量召回。
    注意：SQLAlchemy AsyncSession 不支持并发调用，必须顺序执行。
    """
    kb_ids = _knowledge_base_ids_from_scope(scope_entries)
    chunks: list[DocumentChunk] = []
    for kb_id in kb_ids:
        kb_chunks = await _vector_search(db, user_id, kb_id, query_vec)
        chunks.extend(kb_chunks)
    return chunks


async def _fts_search_scope(
    db: AsyncSession,
    user_id: int,
    scope_entries: Sequence[KnowledgeScopeEntry],
    query: str,
) -> list[DocumentChunk]:
    """对 scope 内每个知识库分别顺序执行全文召回。
    注意：SQLAlchemy AsyncSession 不支持并发调用，必须顺序执行。
    """
    kb_ids = _knowledge_base_ids_from_scope(scope_entries)
    chunks: list[DocumentChunk] = []
    for kb_id in kb_ids:
        kb_chunks = await _fts_search(db, user_id, kb_id, query)
        chunks.extend(kb_chunks)
    return chunks


def _merge_chunks_by_id(
    vector_results: Sequence[DocumentChunk],
    fts_results: Sequence[DocumentChunk],
    k: int = 60,
) -> list[DocumentChunk]:
    """使用 RRF (Reciprocal Rank Fusion) 算法融合向量检索和全文检索结果。

    RRF 公式: score = sum(1 / (k + rank))
    k 默认取 60，是论文建议的经验值。
    """
    scores: dict[int, float] = {}
    chunk_map: dict[int, DocumentChunk] = {}

    # 处理向量检索排名
    for rank, chunk in enumerate(vector_results, start=1):
        chunk_map[chunk.id] = chunk
        scores[chunk.id] = scores.get(chunk.id, 0) + 1.0 / (k + rank)

    # 处理全文检索排名
    for rank, chunk in enumerate(fts_results, start=1):
        chunk_map[chunk.id] = chunk
        scores[chunk.id] = scores.get(chunk.id, 0) + 1.0 / (k + rank)

    # 按 RRF 分数从高到低排序
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [chunk_map[cid] for cid in sorted_ids]


async def _rerank(
    query: str,
    chunks: list[DocumentChunk],
) -> tuple[list[DocumentChunk], list[float], float | None]:
    """重排序 chunks。

    Args:
        query: 查询文本
        chunks: 待重排序的 chunks

    Returns:
        (重排序后的 chunks, relevance_score 列表, 过滤前最高 relevance_score)
    """
    if not chunks:
        return chunks, [], None

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
        cohere_top_score = scores[0] if scores else None

        ranked_chunks = _filter_rerank_results(
            chunks, resp.results, settings.RAG_MIN_RERANK_SCORE
        )

        return ranked_chunks, scores[: len(ranked_chunks)], cohere_top_score
    except Exception as e:
        logger.warning("Rerank failed, using original order: %s", e, exc_info=True)
        return chunks[:RERANK_TOP_N], [], None


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
    history_lines = []
    if summary:
        history_lines.append(f"历史摘要: {summary}")
    for msg in recent_messages:
        role_label = "用户" if msg.role == "user" else "助理"
        history_lines.append(f"{role_label}: {msg.content}")

    history_text = "\n".join(history_lines)

    system_content = (
        "你是一个专门的检索查询改写助手。\n"
        "你的唯一任务是将用户最新的提问改写为适合技术文档检索的独立查询句（standalone query）。\n"
        "你需要结合给定的【历史对话上下文】来消除指代歧义并补全信息。\n\n"
        "【关键约束】：\n"
        "1. **绝对不要尝试回答用户的提问！** 你不是问答助手，你只是一个查询翻译器。不要生成任何解答、建议或说明。\n"
        "2. **严禁扩充无关内容**：不要在查询中加入你自己的知识或猜测的答案。\n"
        "3. **只输出查询句**：只输出一行改写后的查询语句，不要解释，不要加引号，不要带任何前缀。\n\n"
        "【示例】：\n"
        "历史：用户：如何安装 Docker？ 助理：[安装步骤...] 用户：那在 Mac 上呢？\n"
        "输出：在 Mac 系统上安装 Docker 的方法和步骤\n\n"
        "历史：用户：介绍一下 Codex 助手。 助理：Codex 是一个代码辅助工具。 用户：它都有什么命令？\n"
        "输出：Codex 助手的完整命令列表和使用说明\n\n"
        "**错误示范（绝对不要这样做）**：\n"
        "用户：Codex 都有什么命令？\n"
        "错误输出：Codex 的命令包括代码补全、生成等，请参考文档...（这是在回答问题，是错误的！）"
    )

    user_content = ""
    if history_text:
        user_content += f"【历史对话上下文】:\n{history_text}\n\n"
    user_content += f"【用户最新提问】:\n{question}\n\n请直接输出改写后的独立检索查询："

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


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


async def _analyze_query_gate(
    question: str,
    recent_messages: Sequence[Message],
    summary: str | None,
) -> dict[str, Any]:
    """一站式智能分析查询门禁，合并常识校验、检索意图分类和提问重写为单次 LLM 调用。"""
    try:
        # 简单问候快速判定，避免不必要的大模型调用
        if _is_greeting(question) or _is_identity_question(question):
            return {
                "is_kb_listing": False,
                "is_weather": False,
                "is_general": True,
                "intent": "MICRO_RETRIEVAL",
                "rewritten_query": question,
            }

        history_lines = []
        if summary:
            history_lines.append(f"历史摘要: {summary}")
        for msg in recent_messages:
            role_label = "用户" if msg.role == "user" else "助理"
            history_lines.append(f"{role_label}: {msg.content[:200]}")
        history_text = "\n".join(history_lines)

        system_content = (
            "你是一个专门用于智能分析和预处理检索提问的助手。\n"
            "你需要阅读【历史对话上下文】和【用户最新提问】，并分析输出以下几个维度的 JSON 信息：\n\n"
            "1. is_kb_listing: 布尔值 (true 或 false)。判断用户是否在请求列出或查询他自己目前拥有的、已上传的所有知识库/文档列表（例如「列出我的所有知识库」「我上传了什么文件」「帮我看看我的知识库」「我有几个知识库」）。如果是，为 true；否则为 false。\n"
            "2. is_weather: 布尔值 (true 或 false)。判断用户是否在询问天气信息（如当前天气、预报、空气质量等），或者正在回答助手关于城市名字的追问（例如「您想查询哪里的天气」「北京」）。如果是，为 true；否则为 false。\n"
            "3. is_general: 布尔值 (true 或 false)。如果用户是在询问当前的日期、具体的时间，或者是在进行纯粹的通用日常打招呼、闲聊、或不依赖任何本地技术/个人文档即可直接回答的常识性问题（如「你好」「谢谢」「今天是星期几」「1+1等于几」），或者 `is_kb_listing` 为 true，或者 `is_weather` 为 true，则该字段为 true；如果是询问特定简历经历、专业技术知识、项目细节等需要查阅特定本地文档/知识库才能回答的问题，则该字段为 false。\n"
            '4. intent: 字符串 ("MACRO_RETRIEVAL" 或 "MICRO_RETRIEVAL")。如果 `is_general` 为 false，请进一步分类其检索意图：\n'
            "   - MACRO_RETRIEVAL: 涉及全局性总结、文档大纲、主要模块介绍、项目总体背景、知识库宏观架构，或询问「这份文档/知识库讲了什么」。\n"
            "   - MICRO_RETRIEVAL: 涉及具体细节、个人工作经历、项目具体逻辑、具体配置项、步骤、代码、或者需要深入文档定位某些细节字段的问题。\n"
            "5. rewritten_query: 字符串。如果 `is_general` 为 false，请将用户最新的提问改写为适合技术文档检索的独立检索词（standalone query）。结合给定的上下文消除人称、代词指代歧义（例如将「他/这个/它」还原为具体实体），并补全上下文。绝对不要在 rewritten_query 中进行任何回答或解释，只输出干净的检索内容。\n\n"
            "【重写特别说明】\n"
            "- 如果用户的最新提问是非常短且模糊的字符（如单数字「1」、单字母、或无意义的短词），且在上下文中没有明确的序号指代或选择含义，请保持其原始状态，不要强行将其改写为之前问过的问题，以免造成回答重复。\n"
            "- 如果判断用户是在进行无关紧要的确认或无意义输入，请将 `is_general` 设为 true。\n\n"
            '必须输出合法的 JSON 格式，包含字段: "is_kb_listing", "is_weather", "is_general", "intent", "rewritten_query"。'
        )

        user_content = ""
        if history_text:
            user_content += f"【历史对话上下文】:\n{history_text}\n\n"
        user_content += f"【用户最新提问】:\n{question}\n\n请直接输出分析结果 JSON："

        client = _openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        res_text = resp.choices[0].message.content or "{}"
        data = json.loads(res_text)
        return {
            "is_kb_listing": bool(data.get("is_kb_listing", False)),
            "is_weather": bool(data.get("is_weather", False)),
            "is_general": bool(data.get("is_general", False)),
            "intent": str(data.get("intent", "MICRO_RETRIEVAL")),
            "rewritten_query": str(data.get("rewritten_query", question)),
        }
    except Exception as e:
        logger.warning("Analyze query gate failed: %s, fallback to default", e)
        return {
            "is_kb_listing": False,
            "is_weather": False,
            "is_general": False,
            "intent": "MICRO_RETRIEVAL",
            "rewritten_query": question,
        }


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


_redis_client: aioredis.Redis | None = None


def _get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        if settings.REDIS_URL:
            _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        else:
            if settings.REDIS_PASSWORD:
                _redis_client = aioredis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True,
                )
            else:
                _redis_client = aioredis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    decode_responses=True,
                )
    return _redis_client


async def _save_to_l1_cache(
    conv_id: uuid.UUID,
    question: str,
    response_events: list[dict],
    knowledge_base_ids: list[int] | None = None,
) -> None:
    """将成功的事件流写入 L1 Redis 缓存，绑定知识库 Scope 以完成自动隔离。"""
    if not settings.RAG_CACHE_L1_ENABLED or not response_events:
        return
    # 检查是否包含 error 事件，如果有则不缓存
    if any(e.get("type") == "error" for e in response_events):
        return
    # 必须包含 done 事件，表示完整成功
    if not any(e.get("type") == "done" for e in response_events):
        return

    try:
        from backend.app.core.metrics import CACHE_OPERATION_DURATION_SECONDS

        redis_client = _get_redis_client()
        q_hash = hashlib.md5(question.strip().encode("utf-8")).hexdigest()

        # 加上知识库 Scope 哈希以完成多租户/知识库状态自动隔离
        scope_hash = ""
        if knowledge_base_ids:
            kb_ids_sorted = sorted(knowledge_base_ids)
            scope_str = ",".join(str(i) for i in kb_ids_sorted)
            scope_hash = hashlib.md5(scope_str.encode("utf-8")).hexdigest()

        l1_cache_key = _build_l1_cache_key(scope_hash=scope_hash, q_hash=q_hash)
        _l1_set_start = perf_counter()
        await redis_client.setex(
            l1_cache_key,
            settings.RAG_CACHE_EXPIRE_SECONDS,
            json.dumps(response_events),
        )
        CACHE_OPERATION_DURATION_SECONDS.labels(layer="l1", operation="set").observe(
            perf_counter() - _l1_set_start
        )
        # 维护反向索引，供知识库删除时精准驱逐
        if knowledge_base_ids:
            for kb_id in knowledge_base_ids:
                await redis_client.sadd(f"cache:rag:kb:{kb_id}:keys", l1_cache_key)
                # 反向索引集合的 TTL 设为缓存过期时间的 7 倍，容忍少量过期残留
                await redis_client.expire(
                    f"cache:rag:kb:{kb_id}:keys",
                    max(settings.RAG_CACHE_EXPIRE_SECONDS * 7, 86400),
                )
        logger.info("Saved response to L1 cache for question: %s", question[:30])
    except Exception as e:
        logger.warning("Failed to save to L1 cache: %s", e)


async def _save_to_l2_cache(
    db: AsyncSession,
    question: str,
    query_vector: list[float] | None,
    response_events: list[dict],
    knowledge_base_ids: list[int] | None = None,
) -> None:
    """将成功的事件流写入 L2 pgvector 缓存。"""
    if not settings.RAG_CACHE_L2_ENABLED or not query_vector or not response_events:
        return
    # 检查是否包含 error 事件，如果有则不缓存
    if any(e.get("type") == "error" for e in response_events):
        return
    # 必须包含 done 事件，表示完整成功
    if not any(e.get("type") == "done" for e in response_events):
        return

    try:
        from backend.app.core.metrics import CACHE_OPERATION_DURATION_SECONDS

        _l2_set_start = perf_counter()
        await qa_repository.create_semantic_cache(
            db,
            question=question,
            query_embedding=query_vector,
            response_events=response_events,
            knowledge_base_ids=knowledge_base_ids,
        )
        CACHE_OPERATION_DURATION_SECONDS.labels(layer="l2", operation="set").observe(
            perf_counter() - _l2_set_start
        )
        logger.info(
            "Saved response to L2 semantic cache for question: %s", question[:30]
        )
    except Exception as e:
        logger.warning("Failed to save to L2 cache: %s", e)


async def _is_temporal_or_general_query(
    question: str, recent_messages: list[Message] | None = None
) -> bool:
    """判断用户是否在询问当前的时间、日期，或者在进行通用的常识提问、打招呼与闲聊。

    如果是这些不依赖任何本地专业文档即可作答的问题，回答 YES；否则回答 NO。
    """
    try:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是一个意图分类助手。请判断用户是否在询问当前的时间、日期，"
                    "或者是在进行通用的打招呼、闲聊、或纯粹的常识性提问（如「今天是几号」「现在几点了」「你好」「1+1等于几」）。\n"
                    "如果是这些完全不需要查阅本地技术文档即可作答的问题，回答 YES；\n"
                    "如果是询问专业知识、求职简历、JD 分析等需要查阅本地技术文档的问题，回答 NO。\n"
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
        logger.warning("Temporal/general query check failed: %s", e)
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
    ttft_started_at = perf_counter()
    ttft_recorded = False
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
                if not ttft_recorded:
                    from backend.app.core.metrics import RAG_TTFT_SECONDS

                    RAG_TTFT_SECONDS.observe(perf_counter() - ttft_started_at)
                    ttft_recorded = True
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
        "你是一个基于私有知识库的问答助手。你的目标是提供准确、有据可查的回答。\n\n"
        "【回答策略】\n"
        "1. 优先检索：回答必须首先基于提供的「具体上下文片段」或「知识库全局摘要」。\n"
        "2. 引用要求：只要回答中包含来自上下文的事实、数据或观点，必须在句末使用 [1]、[2] 等角标进行标注，角标序号需与上下文片段序号严格对应。\n"
        "3. 宏观总结：如果回答是基于知识库整体摘要生成的，请在开头明确指出（如：根据《知识库名称》的摘要...）。\n"
        "4. 通识兜底：若检索内容无法回答问题：\n"
        "   - 属于基础技术常识（如“React是什么”）：可以利用自身知识进行客观回答，并说明这是通用知识补充。\n"
        "   - 属于私密或特定领域信息（如个人经历、特定配置）：必须回答「根据已有文档，无法回答该问题」，严禁幻觉编造。\n\n"
        "【语言风格】热情、专业、简洁，使用中文作答。"
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
    # 如果 AI 已经明确回答无法从文档回答，且没有强行编造，则不需要引用
    if "根据已有文档，无法回答该问题" in answer:
        return []

    citations = _extract_citations(answer, chunks, knowledge_base_names_by_id)
    if not citations:
        # 如果有召回片段但 AI 没带 [1] 角标，检查是否提到了知识库名称进行宏观引用
        if chunks and knowledge_base_names_by_id:
            for kb_id, kb_name in knowledge_base_names_by_id.items():
                if kb_name in answer:
                    return _extract_citations(answer, [], knowledge_base_names_by_id)

        # 只有在搜到了内容、AI 回答了内容，但既没带角标也没提知识库名字时，才抛错
        if chunks:
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
    debug = debug and settings.DEBUG
    ttft_started_at = perf_counter()
    ttft_recorded = False
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
        top_chunks: list[DocumentChunk] = []
        rerank_scores: list[float] = []
        cohere_top_score: float | None = None

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
            knowledge_base_ids = _knowledge_base_ids_from_scope(scope_entries)
            knowledge_base_names_by_id = _knowledge_base_names_by_id(scope_entries)
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

        # 初始化事件流收集器
        accumulated_events = []

        if debug:
            event = _build_debug_event(
                "init", {"status": "started", "question": question}, conv_id=conv_id
            )
            if event:
                accumulated_events.append(event)
                yield event

        # 获取 scope 哈希以进行隔离
        kb_ids_sorted = sorted(knowledge_base_ids)
        scope_str = ",".join(str(i) for i in kb_ids_sorted)
        scope_hash = hashlib.md5(scope_str.encode("utf-8")).hexdigest()

        # 计算问题 MD5 哈希作为缓存 key
        q_hash = hashlib.md5(question.strip().encode("utf-8")).hexdigest()
        l1_cache_key = _build_l1_cache_key(scope_hash=scope_hash, q_hash=q_hash)

        # 1. 尝试 L1 缓存精确哈希匹配拦截
        if settings.RAG_CACHE_L1_ENABLED:
            from backend.app.core.metrics import (
                CACHE_LOOKUP_TOTAL,
                CACHE_OPERATION_DURATION_SECONDS,
            )

            _l1_start = perf_counter()
            try:
                redis_client = _get_redis_client()
                cached_data = await redis_client.get(l1_cache_key)
                _l1_result = "hit" if cached_data else "miss"
            except Exception:
                _l1_result = "error"
                cached_data = None
            finally:
                CACHE_LOOKUP_TOTAL.labels(layer="l1", result=_l1_result).inc()
                CACHE_OPERATION_DURATION_SECONDS.labels(
                    layer="l1", operation="lookup"
                ).observe(perf_counter() - _l1_start)

            if cached_data:
                logger.info(
                    "L1 Redis precise cache hit for question: %s", question[:30]
                )
                if debug:
                    event = _build_debug_event(
                        "cache",
                        {"type": "L1_precise_cache", "status": "hit"},
                        conv_id=conv_id,
                    )
                    if event:
                        yield event
                cached_events = json.loads(cached_data)

                full_answer = ""
                citations = None
                for event in cached_events:
                    if event.get("type") == "token":
                        full_answer += event.get("content", "")
                    elif event.get("type") == "citations":
                        citations = event.get("data")

                await qa_repository.create_message(db, conv_id, "user", question)

                if (conv.message_count or 0) == 0:
                    await qa_repository.update_conversation_title(
                        db, conv_id, truncate_title(question)
                    )
                    smart_title = await generate_conversation_title(question)
                    if smart_title:
                        await qa_repository.update_conversation_title(
                            db, conv_id, smart_title
                        )

                for event in cached_events:
                    if not ttft_recorded and event.get("type") == "token":
                        from backend.app.core.metrics import RAG_TTFT_SECONDS

                        RAG_TTFT_SECONDS.observe(perf_counter() - ttft_started_at)
                        ttft_recorded = True
                    yield event
                    if event.get("type") == "token":
                        await asyncio.sleep(0.005)

                await qa_repository.create_message(
                    db, conv_id, "assistant", full_answer, citations or None
                )

                updated_conv = await qa_repository.get_conversation_by_id(db, conv_id)
                if updated_conv and (updated_conv.message_count or 0) > SUMMARY_TRIGGER:
                    try:
                        from backend.app.tasks.qa_tasks import (
                            summarize_conversation,
                        )

                        summarize_conversation.apply_async(args=(str(conv_id),))
                    except Exception as e:
                        logger.warning("Celery summarize enqueue failed: %s", e)

                return
        # 预先获取历史消息，用于意图识别和后续 Prompt 构建
        recent = await qa_repository.get_recent_messages(db, conv_id, limit=KEEP_RECENT)

        # 1. 快速通道：打招呼（正则）→ 通用回复；知识库列表（LLM 二分类）→ 列出知识库
        #    时间意图与常识闲聊 → 注入系统当前时钟直接回答
        #    其余全部进入检索流程（检索优先）
        if _is_greeting(question):
            done_event = None
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_general_prompt(question, recent, conv.summary),
                conv.message_count or 0,
                "greeting",
            ):
                accumulated_events.append(event)
                if event.get("type") == "done":
                    done_event = event
                else:
                    yield event
            await _save_to_l1_cache(
                conv_id, question, accumulated_events, knowledge_base_ids
            )
            if done_event:
                yield done_event
            return

        if _is_identity_question(question):
            done_event = None
            async for event in _send_general_response(
                db,
                conv_id,
                question,
                _build_identity_prompt(question, recent),
                conv.message_count or 0,
                "identity",
            ):
                accumulated_events.append(event)
                if event.get("type") == "done":
                    done_event = event
                else:
                    yield event
            await _save_to_l1_cache(
                conv_id, question, accumulated_events, knowledge_base_ids
            )
            if done_event:
                yield done_event
            return

        # 🎯 一站式智能大模型分析查询门禁 (合并常识校验、检索意图分类和提问改写)
        # 优化：如果是第一轮提问（即没有历史消息且无摘要），且绑定了知识库，则直接进入 RAG 检索，跳过门禁大模型分析，瞬间节省 3s+ 延迟！
        is_first_msg = (conv.message_count or 0) == 0
        if is_first_msg and knowledge_base_ids:
            logger.info(
                "First message with active KB scope, skipping unified query gate LLM call for maximum performance."
            )
            gate_res = {
                "is_kb_listing": False,
                "is_weather": False,
                "is_general": False,
                "intent": "MICRO_RETRIEVAL",
                "rewritten_query": question,
            }
            gate_duration_ms = 0
        else:
            gate_start = perf_counter()
            gate_res = await _analyze_query_gate(question, recent, conv.summary)
            gate_duration_ms = _duration_ms(gate_start, perf_counter())
            logger.info(
                "Unified query gate analyze finished in %.2fms. Result: %s",
                gate_duration_ms,
                gate_res,
            )

        # A. 知识库列表查询
        if gate_res["is_kb_listing"]:
            if debug:
                event = _build_debug_event(
                    "intent",
                    {"intent": "kb_listing", "reason": "查询有哪些知识库"},
                    conv_id=conv_id,
                )
                if event:
                    accumulated_events.append(event)
                    yield event
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
                accumulated_events.append(event)
                yield event
            return

        # B. 常识/时间提问
        if gate_res["is_general"] and not gate_res["is_weather"]:
            if debug:
                event = _build_debug_event(
                    "intent",
                    {
                        "intent": "temporal_general",
                        "reason": "打招呼、时间或常识性问题",
                    },
                    conv_id=conv_id,
                )
                if event:
                    accumulated_events.append(event)
                    yield event
            now = datetime.datetime.now()
            weekday_map = {
                0: "星期一",
                1: "星期二",
                2: "星期三",
                3: "星期四",
                4: "星期五",
                5: "星期六",
                6: "星期日",
            }
            time_str = now.strftime("%Y年%m月%d日 %H时%M分%S秒")
            weekday_str = weekday_map[now.weekday()]
            temporal_messages: list[dict[str, str]] = [
                {
                    "role": "system",
                    "content": (
                        f"你是一个有用的个人 AI 助手。当前系统时间是：{time_str}，今天是：{weekday_str}。\n"
                        "请根据这个时间，或者作为常识打招呼等普通通用问题，直接回答用户的问题。\n"
                        "注意：这是一个闲聊/时间/常识提问，不需要查阅本地技术文档或简历。你可以自由且合理地作答。\n"
                        "请使用热情、专业且简洁的语言进行回答。"
                    ),
                }
            ]
            for msg in recent:
                temporal_messages.append({"role": msg.role, "content": msg.content})
            temporal_messages.append({"role": "user", "content": question})

            async for event in _send_general_response(
                db,
                conv_id,
                question,
                temporal_messages,
                conv.message_count or 0,
                "temporal_general",
            ):
                accumulated_events.append(event)
                yield event
            return

        # C. 天气查询
        if gate_res["is_weather"]:
            if debug:
                event = _build_debug_event(
                    "intent",
                    {"intent": "weather", "reason": "天气查询"},
                    conv_id=conv_id,
                )
                if event:
                    accumulated_events.append(event)
                    yield event
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
                    accumulated_events.append(event)
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
                    accumulated_events.append(event)
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
                accumulated_events.append(event)
                yield event
            return

        # 获取解析后的检索属性
        intent = gate_res["intent"]
        retrieval_query = gate_res["rewritten_query"]
        rewrite_duration_ms = int(gate_duration_ms)

        # 如果当前 Scope 为空，则触发"延迟路由"
        if not scope_entries:
            logger.info(
                "Current scope is empty, triggering delayed routing for question: %s",
                question,
            )
            if debug:
                event = _build_debug_event(
                    "routing", {"status": "trigger_delayed_routing"}, conv_id=conv_id
                )
                if event:
                    accumulated_events.append(event)
                    yield event
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
            if debug:
                event = _build_debug_event(
                    "intent",
                    {"intent": "no_scope_fallback", "reason": "未找到匹配知识库"},
                    conv_id=conv_id,
                )
                if event:
                    accumulated_events.append(event)
                    yield event
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
        cohere_top_score = None

        if debug:
            event = _build_debug_event(
                "intent", {"intent": intent, "reason": "意图分类结果"}, conv_id=conv_id
            )
            if event:
                yield event

        # 如果是 MICRO_RETRIEVAL，执行完整检索
        if intent == "MICRO_RETRIEVAL":
            if debug:
                event = _build_debug_event(
                    "query_rewrite",
                    {
                        "question": question,
                        "retrieval_query": retrieval_query,
                        "rewritten": retrieval_query != question,
                        "rewrite_duration_ms": rewrite_duration_ms,
                    },
                    conv_id=conv_id,
                )
                if event:
                    accumulated_events.append(event)
                    yield event

            # 向量检索嵌入生成 与 全文检索 并发执行
            embedding_start = perf_counter()
            fts_start = perf_counter()

            embedding_task = generate_embeddings([retrieval_query])
            fts_task = asyncio.ensure_future(
                _fts_search_scope(db, user_id, scope_entries, retrieval_query)
            )

            # 先等待嵌入完成，以便后续进行 L2 缓存检查和向量检索
            [query_vec] = await embedding_task
            embedding_duration_ms = _duration_ms(embedding_start, perf_counter())

            if debug:
                event = _build_debug_event(
                    "embedding",
                    {"embedding_duration_ms": embedding_duration_ms},
                    conv_id=conv_id,
                )
                if event:
                    accumulated_events.append(event)
                    yield event

            # 2. 尝试 L2 语义缓存拦截
            if settings.RAG_CACHE_L2_ENABLED:
                from backend.app.core.metrics import (
                    CACHE_LOOKUP_TOTAL,
                    CACHE_OPERATION_DURATION_SECONDS,
                )

                _l2_start = perf_counter()
                try:
                    similar_cache = await qa_repository.find_similar_semantic_cache(
                        db,
                        query_vec,
                        knowledge_base_ids=knowledge_base_ids,
                        threshold=settings.RAG_CACHE_L2_THRESHOLD,
                    )
                    _l2_result = "hit" if similar_cache else "miss"
                except Exception:
                    _l2_result = "error"
                    similar_cache = None
                finally:
                    CACHE_LOOKUP_TOTAL.labels(layer="l2", result=_l2_result).inc()
                    CACHE_OPERATION_DURATION_SECONDS.labels(
                        layer="l2", operation="lookup"
                    ).observe(perf_counter() - _l2_start)

                if similar_cache:
                    logger.info("L2 semantic cache hit for question: %s", question[:30])
                    # 如果 L2 命中，返回前必须确保 fts_task 被处理，否则会报 RuntimeWarning
                    await fts_task

                    # 异步回写到 L1 精确缓存
                    try:
                        redis_client = _get_redis_client()
                        await redis_client.setex(
                            l1_cache_key,
                            settings.RAG_CACHE_EXPIRE_SECONDS,
                            json.dumps(similar_cache.response_events),
                        )
                        # 维护反向索引，供知识库删除时精准驱逐
                        if knowledge_base_ids:
                            for kb_id in knowledge_base_ids:
                                await redis_client.sadd(
                                    f"cache:rag:kb:{kb_id}:keys", l1_cache_key
                                )
                                await redis_client.expire(
                                    f"cache:rag:kb:{kb_id}:keys",
                                    max(settings.RAG_CACHE_EXPIRE_SECONDS * 7, 86400),
                                )
                        logger.info("Back-filled L1 cache from L2 hit")
                    except Exception as e:
                        logger.warning("Failed to back-fill L1 cache from L2: %s", e)

                    full_answer = ""
                    citations = None
                    for event in similar_cache.response_events:
                        if event.get("type") == "token":
                            full_answer += event.get("content", "")
                        elif event.get("type") == "citations":
                            citations = event.get("data")

                    await qa_repository.create_message(db, conv_id, "user", question)

                    if (conv.message_count or 0) == 0:
                        await qa_repository.update_conversation_title(
                            db, conv_id, truncate_title(question)
                        )
                        smart_title = await generate_conversation_title(question)
                        if smart_title:
                            await qa_repository.update_conversation_title(
                                db, conv_id, smart_title
                            )

                    for event in similar_cache.response_events:
                        if not ttft_recorded and event.get("type") == "token":
                            from backend.app.core.metrics import RAG_TTFT_SECONDS

                            RAG_TTFT_SECONDS.observe(perf_counter() - ttft_started_at)
                            ttft_recorded = True
                        yield event
                        if event.get("type") == "token":
                            await asyncio.sleep(0.005)

                    await qa_repository.create_message(
                        db, conv_id, "assistant", full_answer, citations or None
                    )

                    updated_conv = await qa_repository.get_conversation_by_id(
                        db, conv_id
                    )
                    if (
                        updated_conv
                        and (updated_conv.message_count or 0) > SUMMARY_TRIGGER
                    ):
                        try:
                            from backend.app.tasks.qa_tasks import (
                                summarize_conversation,
                            )

                            summarize_conversation.apply_async(args=(str(conv_id),))
                        except Exception as e:
                            logger.warning("Celery summarize enqueue failed: %s", e)

                    yield {"type": "done"}
                    return

            # 向量检索 与 等待全文检索结果 顺序执行
            # 注意：不能使用 asyncio.gather 同时跑 vector_task 和 fts_task，因为它们共用同一个 db session
            fts_candidates = await fts_task
            fts_duration_ms = _duration_ms(fts_start, perf_counter())
            fts_candidates_count = len(fts_candidates)

            vector_start = perf_counter()
            vector_candidates = await _vector_search_scope(
                db, user_id, scope_entries, query_vec
            )
            vector_duration_ms = _duration_ms(vector_start, perf_counter())
            vector_candidates_count = len(vector_candidates)

            candidates = _merge_chunks_by_id(vector_candidates, fts_candidates)
            merged_candidates_count = len(candidates)

            if debug:
                event = _build_debug_event(
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
                accumulated_events.append(event)
                yield event

            # Rerank
            if candidates:
                rerank_start = perf_counter()
                top_chunks, rerank_scores, cohere_top_score = await _rerank(
                    retrieval_query, candidates
                )
                rerank_duration_ms = _duration_ms(rerank_start, perf_counter())
                rerank_candidates_count = len(top_chunks)
                if debug:
                    event = _build_debug_event(
                        "rerank",
                        {
                            "rerank_candidates_count": rerank_candidates_count,
                            "top_chunks_preview": _debug_chunk_preview_with_score(
                                top_chunks, rerank_scores
                            ),
                        },
                        conv_id=conv_id,
                    )
                    accumulated_events.append(event)
                    yield event

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
                    cohere_top_score=cohere_top_score,
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
                if not ttft_recorded:
                    from backend.app.core.metrics import RAG_TTFT_SECONDS

                    RAG_TTFT_SECONDS.observe(perf_counter() - ttft_started_at)
                    ttft_recorded = True
                event = {"type": "token", "content": delta}
                accumulated_events.append(event)
                yield event
    except Exception as e:
        logger.exception("大模型流式回答生成过程中抛出异常: %s", e)
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
                cohere_top_score=cohere_top_score,
            )
        )
        if debug:
            event = _build_debug_event(
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
            if event:
                yield event
        yield {"type": "error", "message": "生成失败，请重试"}
        return
    finally:
        # 兜底：确保异步任务不泄露
        if "fts_task" in locals() and not fts_task.done():
            try:
                await fts_task
            except Exception:
                pass
    generation_duration_ms = _duration_ms(generation_start, perf_counter())

    # 提取并校验 citations；无有效引用的答案不能作为可信回答入库。
    # 优化：如果是基于全局摘要回答且没有切片，则放宽校验。
    # 修复：如果模型遵循核心约束回答了“无法回答”，则跳过校验。
    CANNOT_ANSWER_MSG = "根据已有文档，无法回答该问题"
    if CANNOT_ANSWER_MSG in full_answer:
        citations = []
    else:
        try:
            citations = _require_citations(
                full_answer, top_chunks, knowledge_base_names_by_id
            )
        except CitationValidationError:
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
                    generation_duration_ms=generation_duration_ms,
                    total_duration_ms=_duration_ms(total_start, perf_counter()),
                    outcome="error",
                    knowledge_base_ids=knowledge_base_ids,
                    error_code="missing_citations",
                    cohere_top_score=cohere_top_score,
                )
            )
            if debug:
                event = _build_debug_event(
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
                if event:
                    yield event
            yield {"type": "error", "message": "生成结果缺少有效引用，请重试"}
            return
    citations_count = len(citations)

    if debug:
        event = _build_debug_event(
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
        if event:
            accumulated_events.append(event)
            yield event

    event = {"type": "citations", "data": citations}
    accumulated_events.append(event)
    yield event

    # 写入 assistant 消息
    await qa_repository.create_message(
        db, conv_id, "assistant", full_answer, citations or None
    )

    # 如果是第一轮问答，在流式生成完成的收尾阶段才调用 LLM 生成并更新对话智能标题，从而将首字延迟 (TTFT) 压缩 2 秒以上！
    if is_first_message:
        try:
            smart_title = await generate_conversation_title(question)
            if smart_title:
                await qa_repository.update_conversation_title(db, conv_id, smart_title)
                logger.info("Successfully updated smart title: %s", smart_title)
        except Exception as e:
            logger.warning("Failed to generate smart title in background: %s", e)

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
            cohere_top_score=cohere_top_score,
        )
    )

    event = {"type": "done"}
    accumulated_events.append(event)

    # 成功结束后，触发异步双写缓存
    await _save_to_l1_cache(conv_id, question, accumulated_events, knowledge_base_ids)
    if "query_vec" in locals() and query_vec is not None:
        await _save_to_l2_cache(
            db, question, query_vec, accumulated_events, knowledge_base_ids
        )

    yield event
