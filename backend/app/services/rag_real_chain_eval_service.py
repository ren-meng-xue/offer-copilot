from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.repositories import knowledge_repository
from backend.app.services import qa_service
from backend.app.services.rag_eval_service import (
    RagEvalCase,
    RagEvalObserved,
    RagEvalRunSummary,
    load_eval_cases,
    run_eval_cases_async,
)


@dataclass(frozen=True)
class _EvalMessage:
    role: str
    content: str


def _history_to_messages(case: RagEvalCase) -> list[_EvalMessage]:
    return [_EvalMessage(role=turn.role, content=turn.content) for turn in case.history]


async def _resolve_knowledge_base_for_case(
    db: AsyncSession, case: RagEvalCase
) -> KnowledgeBase | None:
    if case.knowledge_base_source_url:
        return await knowledge_repository.get_knowledge_base_by_source_url(
            db, case.knowledge_base_source_url
        )

    if case.knowledge_base_name:
        return await knowledge_repository.get_latest_knowledge_base_by_name(
            db, case.knowledge_base_name
        )

    if case.knowledge_base_id is not None:
        return await knowledge_repository.get_knowledge_base_by_id(
            db, case.knowledge_base_id
        )

    return None


async def observe_eval_case(db: AsyncSession, case: RagEvalCase) -> RagEvalObserved:
    kb = await _resolve_knowledge_base_for_case(db, case)
    if kb is None:
        return RagEvalObserved(
            knowledge_base_id=None,
            expected_knowledge_base_id=None,
            retrieval_query=case.question,
            answer="评测用例未解析到知识库",
            citations=[],
            outcome="error",
            error_code="fixture_scope_unresolved",
        )
    if kb.status.value != "done":
        return RagEvalObserved(
            knowledge_base_id=kb.id,
            expected_knowledge_base_id=kb.id,
            retrieval_query=case.question,
            answer="知识库尚未完成索引",
            citations=[],
            outcome="error",
            error_code="knowledge_base_not_ready",
        )

    recent_messages = _history_to_messages(case)
    retrieval_query = await qa_service._rewrite_query(
        case.question, recent_messages, None
    )
    [query_vec] = await qa_service.generate_embeddings([retrieval_query])

    vector_candidates = await qa_service._vector_search(
        db, kb.user_id, kb.id, query_vec
    )
    try:
        fts_candidates = await qa_service._fts_search(
            db, kb.user_id, kb.id, retrieval_query
        )
    except Exception:
        fts_candidates = []
    candidates = qa_service._merge_chunks_by_id(vector_candidates, fts_candidates)
    if not candidates:
        return RagEvalObserved(
            knowledge_base_id=kb.id,
            expected_knowledge_base_id=kb.id,
            retrieval_query=retrieval_query,
            answer="根据已有文档，无法回答该问题",
            citations=[],
            outcome="error",
            error_code="no_knowledge_base",
        )

    rerank_result = await qa_service._rerank(retrieval_query, candidates)
    top_chunks = rerank_result[0] if isinstance(rerank_result, tuple) else rerank_result
    if not top_chunks:
        return RagEvalObserved(
            knowledge_base_id=kb.id,
            expected_knowledge_base_id=kb.id,
            retrieval_query=retrieval_query,
            answer="根据已有文档，无法回答该问题",
            citations=[],
            outcome="error",
            error_code="no_relevant_context",
        )

    prompt_messages = qa_service._build_prompt(
        case.question, top_chunks, recent_messages, None
    )
    client = qa_service._openai_client()
    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=prompt_messages,  # type: ignore[arg-type]
    )
    answer = resp.choices[0].message.content or ""
    try:
        citations = qa_service._require_citations(answer, top_chunks)
    except qa_service.CitationValidationError:
        return RagEvalObserved(
            knowledge_base_id=kb.id,
            expected_knowledge_base_id=kb.id,
            retrieval_query=retrieval_query,
            answer=answer,
            citations=[],
            outcome="error",
            error_code="missing_citations",
        )

    return RagEvalObserved(
        knowledge_base_id=kb.id,
        expected_knowledge_base_id=kb.id,
        retrieval_query=retrieval_query,
        answer=answer,
        citations=citations,
        outcome="success",
        error_code=None,
    )


async def run_real_chain_eval(
    db: AsyncSession,
    fixture_path: str | Path,
) -> RagEvalRunSummary:
    cases = load_eval_cases(fixture_path)
    return await run_eval_cases_async(cases, lambda case: observe_eval_case(db, case))
