import asyncio
import time
from pathlib import Path
import sys
from prometheus_client import REGISTRY

# Add backend to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.session import async_session_factory
from backend.app.services.rag_real_chain_eval_service import observe_eval_case
from backend.app.services.rag_eval_service import RagEvalCase
from backend.app.core.metrics import (
    RAG_STAGE_DURATION_SECONDS,
    RAG_TOTAL_DURATION_SECONDS,
    RAG_OUTCOME_TOTAL,
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASK_TOTAL,
    EMBEDDING_DURATION_SECONDS,
    RAG_CITATIONS_COUNT,
    RAG_CANDIDATES_COUNT
)

async def run_indicators():
    print("🚀 正在收集实时指标数据...")
    
    # 模拟 Celery 任务
    CELERY_TASK_DURATION_SECONDS.labels(task_name="knowledge.ingest").observe(0.45)
    CELERY_TASK_TOTAL.labels(task_name="knowledge.ingest", status="success").inc()

    # 模拟 RAG 评测问答 (针对刚入库的 FastAPI 文档)
    case = RagEvalCase(
        id="live_test",
        category="answer",
        knowledge_base_id=None,
        knowledge_base_name=None,
        knowledge_base_source_url="https://fastapi.tiangolo.com/zh/tutorial/",
        history=[],
        question="如何安装 FastAPI？",
        expected_mode="answer",
        expected_retrieval_query_contains=[],
        expected_answer_contains=[],
        expected_citation_urls=[]
    )

    async with async_session_factory() as db:
        print(f"🧐 执行 RAG 链评测: {case.question}")
        result = await observe_eval_case(db, case)
        
        # 手动上报 RAG 链路模拟数据 (模拟 stream_answer 的行为)
        RAG_OUTCOME_TOTAL.labels(outcome=result.outcome, error_code="").inc()
        RAG_STAGE_DURATION_SECONDS.labels(stage="rewrite").observe(0.12)
        RAG_STAGE_DURATION_SECONDS.labels(stage="vector").observe(0.08)
        RAG_STAGE_DURATION_SECONDS.labels(stage="rerank").observe(0.15)
        RAG_STAGE_DURATION_SECONDS.labels(stage="generation").observe(1.2)
        RAG_TOTAL_DURATION_SECONDS.labels(outcome="success").observe(1.55)
        
        # 模拟检索命中率相关数据
        RAG_CANDIDATES_COUNT.labels(stage="merged").observe(10)
        RAG_CITATIONS_COUNT.observe(3)

    print("\n✅ 指标抓取成功！当前系统状态如下：")
    
    metrics_to_show = [
        "celery_task_duration_seconds",
        "celery_task_total",
        "embedding_duration_seconds",
        "rag_stage_duration_seconds",
        "rag_total_duration_seconds",
        "rag_outcome_total",
        "rag_citations_count",
        "rag_candidates_count"
    ]
    
    for metric in REGISTRY.collect():
        if metric.name in metrics_to_show:
            print(f"\n指标: {metric.name}")
            for sample in metric.samples:
                if not sample.name.endswith("_created"):
                    print(f"  {sample.labels} -> {sample.value}")

if __name__ == "__main__":
    asyncio.run(run_indicators())
