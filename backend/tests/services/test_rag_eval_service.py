from pathlib import Path

import pytest

from backend.app.services.rag_eval_service import (
    RagEvalObserved,
    load_eval_cases,
    run_eval_cases_async,
    run_eval_cases,
    score_eval_case,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "rag_eval_cases.json"
)


def test_load_eval_cases_reads_fixture_contract() -> None:
    cases = load_eval_cases(FIXTURE_PATH)

    assert len(cases) >= 10
    assert cases[0].id == "langchain_overview_exact_term"
    assert (
        cases[0].knowledge_base_source_url
        == "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
    )
    assert cases[2].history[0].role == "user"


def test_score_eval_case_passes_answer_case() -> None:
    case = load_eval_cases(FIXTURE_PATH)[0]
    observed = RagEvalObserved(
        knowledge_base_id=3,
        expected_knowledge_base_id=3,
        retrieval_query="LangChain 的定义和功能是什么？",
        answer="LangChain 是一个“搭积木”的 AI 应用框架，它的核心目标是将大语言模型（LLM）和外部工具、数据、工作流连接起来。",
        citations=[
            {
                "source_url": "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
            }
        ],
        outcome="success",
        error_code=None,
    )

    score = score_eval_case(case, observed)

    assert score.passed is True
    assert score.failed_checks == []


def test_score_eval_case_passes_refusal_case() -> None:
    case = load_eval_cases(FIXTURE_PATH)[3]
    observed = RagEvalObserved(
        knowledge_base_id=3,
        expected_knowledge_base_id=3,
        retrieval_query="LangChain tool agent capabilities",
        answer="根据已有文档，无法回答该问题",
        citations=[],
        outcome="error",
        error_code="no_relevant_context",
    )

    score = score_eval_case(case, observed)

    assert score.passed is True
    assert score.checks["mode_match"] is True


def test_score_eval_case_fails_when_scope_mismatches() -> None:
    case = load_eval_cases(FIXTURE_PATH)[3]
    observed = RagEvalObserved(
        knowledge_base_id=999,
        expected_knowledge_base_id=3,
        retrieval_query="company annual revenue",
        answer="根据已有文档，无法回答该问题",
        citations=[],
        outcome="error",
        error_code="no_relevant_context",
    )

    score = score_eval_case(case, observed)

    assert score.passed is False
    assert "knowledge_scope_match" in score.failed_checks


def test_score_eval_case_fails_when_rewrite_terms_missing() -> None:
    case = load_eval_cases(FIXTURE_PATH)[1]
    observed = RagEvalObserved(
        knowledge_base_id=3,
        expected_knowledge_base_id=3,
        retrieval_query="framework overview",
        answer="LangChain is a framework for connecting LLMs with tools and data.",
        citations=[
            {
                "source_url": "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
            }
        ],
        outcome="success",
        error_code=None,
    )

    score = score_eval_case(case, observed)

    assert score.passed is False
    assert "retrieval_query_match" in score.failed_checks


def test_run_eval_cases_builds_summary_for_mixed_results() -> None:
    cases = load_eval_cases(FIXTURE_PATH)[:4]

    observed_by_case = {
        "langchain_overview_exact_term": RagEvalObserved(
            knowledge_base_id=3,
            expected_knowledge_base_id=3,
            retrieval_query="LangChain 的定义和功能是什么？",
            answer="LangChain 是一个“搭积木”的 AI 应用框架，它的核心目标是将大语言模型（LLM）和外部工具、数据、工作流连接起来。",
            citations=[
                {
                    "source_url": "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
                }
            ],
            outcome="success",
            error_code=None,
        ),
        "langchain_rag_definition": RagEvalObserved(
            knowledge_base_id=3,
            expected_knowledge_base_id=3,
            retrieval_query="RAG 的定义及其在技术中的应用。",
            answer="RAG，即 Retrieval-Augmented Generation，是一种通过结合检索与生成的流程来回答用户问题的技术方法。这个过程包括：从用户问题开始，通过向量检索找到相关文档，拼接得到的文档与初始问题，最后通过大型语言模型（LLM）生成答案。这种方法通常应用于AI知识库、企业问答和文档助手等领域。LangChain 是一个支持构建 RAG 应用的“搭积木”框架，能够轻松集成LLM、管理Prompt和接入数据库等功能。",
            citations=[
                {
                    "source_url": "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
                }
            ],
            outcome="success",
            error_code=None,
        ),
        "langchain_followup_tools": RagEvalObserved(
            knowledge_base_id=3,
            expected_knowledge_base_id=3,
            retrieval_query="LangChain 可以用于构建对话系统、自动化文档处理、数据增强和信息检索等应用场景。",
            answer="LangChain 可以进行以下操作：调用 LLM（例如 OpenAI、Claude、Gemini、本地模型），管理 Prompt，接入数据库或文档，执行 RAG（知识库问答），让 AI 使用工具，支持多步骤推理的 Agent，记忆上下文，构建 AI 工作流。",
            citations=[
                {
                    "source_url": "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
                }
            ],
            outcome="success",
            error_code=None,
        ),
        "langchain_out_of_scope_product_question": RagEvalObserved(
            knowledge_base_id=3,
            expected_knowledge_base_id=3,
            retrieval_query="company annual revenue",
            answer="根据已有文档，无法回答该问题",
            citations=[],
            outcome="error",
            error_code="no_relevant_context",
        ),
    }

    summary = run_eval_cases(cases, lambda case: observed_by_case[case.id])

    assert summary.total_cases == 4
    assert summary.passed_cases == 4
    assert summary.failed_cases == 0
    assert summary.pass_rate == 1.0


def test_run_eval_cases_marks_observer_errors_without_stopping() -> None:
    cases = load_eval_cases(FIXTURE_PATH)[:2]

    def observer(case):
        if case.id == "langchain_rag_definition":
            raise RuntimeError("boom")
        return RagEvalObserved(
            knowledge_base_id=3,
            expected_knowledge_base_id=3,
            retrieval_query="LangChain 的定义和功能是什么？",
            answer="LangChain 是一个“搭积木”的 AI 应用框架，它的核心目标是将大语言模型（LLM）和外部工具、数据、工作流连接起来。",
            citations=[
                {
                    "source_url": "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
                }
            ],
            outcome="success",
            error_code=None,
        )

    summary = run_eval_cases(cases, observer)

    assert summary.total_cases == 2
    assert summary.failed_check_counts["observer_error"] == 1
    failed_result = next(
        result
        for result in summary.results
        if result.case_id == "langchain_rag_definition"
    )
    assert failed_result.failed_checks == ["observer_error"]


def test_run_eval_cases_returns_empty_summary_for_empty_cases() -> None:
    summary = run_eval_cases([], lambda case: case)

    assert summary.total_cases == 0
    assert summary.pass_rate == 0.0
    assert summary.results == []


@pytest.mark.anyio
async def test_run_eval_cases_async_supports_async_observer() -> None:
    cases = load_eval_cases(FIXTURE_PATH)[:1]

    async def observer(case):
        return RagEvalObserved(
            knowledge_base_id=case.knowledge_base_id,
            expected_knowledge_base_id=case.knowledge_base_id,
            retrieval_query="LangChain 的定义和功能是什么？",
            answer="LangChain 是一个“搭积木”的 AI 应用框架，它的核心目标是将大语言模型（LLM）和外部工具、数据、工作流连接起来。",
            citations=[
                {
                    "source_url": "https://chatgpt.com/share/69fc0a66-d814-83a2-b3df-4204f87e7fe3"
                }
            ],
            outcome="success",
            error_code=None,
        )

    summary = await run_eval_cases_async(cases, observer)

    assert summary.total_cases == 1
    assert summary.passed_cases == 1


@pytest.mark.anyio
async def test_run_eval_cases_async_marks_observer_errors() -> None:
    cases = load_eval_cases(FIXTURE_PATH)[:1]

    async def observer(case):
        raise RuntimeError("boom")

    summary = await run_eval_cases_async(cases, observer)

    assert summary.failed_cases == 1
    assert summary.failed_check_counts["observer_error"] == 1


def test_load_eval_cases_raises_when_scope_is_missing(tmp_path: Path) -> None:
    fixture_path = tmp_path / "invalid_eval_cases.json"
    fixture_path.write_text(
        """
[
  {
    "id": "invalid_case",
    "category": "answer",
    "history": [],
    "question": "test?",
    "expected_mode": "answer",
    "expected_retrieval_query_contains": [],
    "expected_answer_contains": [],
    "expected_citation_urls": []
  }
]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing knowledge base scope"):
        load_eval_cases(fixture_path)
