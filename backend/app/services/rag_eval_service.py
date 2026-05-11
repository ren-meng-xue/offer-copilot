import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RagEvalTurn:
    role: str
    content: str


@dataclass(frozen=True)
class RagEvalCase:
    id: str
    category: str
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    knowledge_base_source_url: str | None
    history: list[RagEvalTurn]
    question: str
    expected_mode: str
    expected_retrieval_query_contains: list[str]
    expected_answer_contains: list[str]
    expected_citation_urls: list[str]


@dataclass(frozen=True)
class RagEvalObserved:
    knowledge_base_id: int | None
    expected_knowledge_base_id: int | None
    retrieval_query: str
    answer: str
    citations: list[dict[str, Any]]
    outcome: str
    error_code: str | None


@dataclass(frozen=True)
class RagEvalScore:
    passed: bool
    checks: dict[str, bool]
    failed_checks: list[str]


@dataclass(frozen=True)
class RagEvalCaseResult:
    case_id: str
    category: str
    passed: bool
    failed_checks: list[str]


@dataclass(frozen=True)
class RagEvalRunSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    failed_check_counts: dict[str, int]
    results: list[RagEvalCaseResult]


def load_eval_cases(path: str | Path) -> list[RagEvalCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases: list[RagEvalCase] = []
    for item in raw:
        knowledge_base_id = item.get("knowledge_base_id")
        knowledge_base_name = item.get("knowledge_base_name")
        knowledge_base_source_url = item.get("knowledge_base_source_url")
        if knowledge_base_id is None and not knowledge_base_name and not knowledge_base_source_url:
            raise ValueError(f"RAG eval case {item['id']} is missing knowledge base scope")

        cases.append(
            RagEvalCase(
                id=item["id"],
                category=item["category"],
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=knowledge_base_name,
                knowledge_base_source_url=knowledge_base_source_url,
                history=[RagEvalTurn(role=turn["role"], content=turn["content"]) for turn in item["history"]],
                question=item["question"],
                expected_mode=item["expected_mode"],
                expected_retrieval_query_contains=item.get("expected_retrieval_query_contains", []),
                expected_answer_contains=item.get("expected_answer_contains", []),
                expected_citation_urls=item.get("expected_citation_urls", []),
            )
        )

    return cases


def score_eval_case(case: RagEvalCase, observed: RagEvalObserved) -> RagEvalScore:
    observed_query = observed.retrieval_query.lower()
    observed_answer = observed.answer.lower()
    observed_citation_urls = {item.get("source_url", "") for item in observed.citations}
    expected_knowledge_base_id = observed.expected_knowledge_base_id
    if expected_knowledge_base_id is None:
        expected_knowledge_base_id = case.knowledge_base_id

    checks = {
        "knowledge_scope_match": observed.knowledge_base_id == expected_knowledge_base_id,
        "mode_match": (
            observed.outcome == "success" if case.expected_mode == "answer" else observed.outcome == "error"
        ),
        "retrieval_query_match": all(
            expected.lower() in observed_query for expected in case.expected_retrieval_query_contains
        ),
        "answer_match": (
            True
            if case.expected_mode != "answer"
            else all(expected.lower() in observed_answer for expected in case.expected_answer_contains)
        ),
        "citation_match": all(url in observed_citation_urls for url in case.expected_citation_urls),
    }

    failed_checks = [name for name, ok in checks.items() if not ok]
    return RagEvalScore(
        passed=not failed_checks,
        checks=checks,
        failed_checks=failed_checks,
    )


def run_eval_cases(
    cases: list[RagEvalCase],
    observer: Any,
) -> RagEvalRunSummary:
    if not cases:
        return RagEvalRunSummary(
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            pass_rate=0.0,
            failed_check_counts={},
            results=[],
        )

    results: list[RagEvalCaseResult] = []
    failed_check_counts: dict[str, int] = {}
    passed_cases = 0

    for case in cases:
        try:
            observed = observer(case)
            score = score_eval_case(case, observed)
            failed_checks = score.failed_checks
            passed = score.passed
        except Exception:
            failed_checks = ["observer_error"]
            passed = False

        if passed:
            passed_cases += 1
        else:
            for check in failed_checks:
                failed_check_counts[check] = failed_check_counts.get(check, 0) + 1

        results.append(
            RagEvalCaseResult(
                case_id=case.id,
                category=case.category,
                passed=passed,
                failed_checks=failed_checks,
            )
        )

    total_cases = len(cases)
    failed_cases = total_cases - passed_cases
    pass_rate = passed_cases / total_cases

    return RagEvalRunSummary(
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=pass_rate,
        failed_check_counts=failed_check_counts,
        results=results,
    )


async def run_eval_cases_async(
    cases: list[RagEvalCase],
    observer: Callable[[RagEvalCase], Awaitable[RagEvalObserved]],
) -> RagEvalRunSummary:
    if not cases:
        return RagEvalRunSummary(
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            pass_rate=0.0,
            failed_check_counts={},
            results=[],
        )

    results: list[RagEvalCaseResult] = []
    failed_check_counts: dict[str, int] = {}
    passed_cases = 0

    for case in cases:
        try:
            observed = await observer(case)
            score = score_eval_case(case, observed)
            failed_checks = score.failed_checks
            passed = score.passed
        except Exception:
            failed_checks = ["observer_error"]
            passed = False

        if passed:
            passed_cases += 1
        else:
            for check in failed_checks:
                failed_check_counts[check] = failed_check_counts.get(check, 0) + 1

        results.append(
            RagEvalCaseResult(
                case_id=case.id,
                category=case.category,
                passed=passed,
                failed_checks=failed_checks,
            )
        )

    total_cases = len(cases)
    failed_cases = total_cases - passed_cases
    pass_rate = passed_cases / total_cases

    return RagEvalRunSummary(
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=pass_rate,
        failed_check_counts=failed_check_counts,
        results=results,
    )
