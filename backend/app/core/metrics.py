"""统一定义 Prometheus 指标对象，供 HTTP、RAG 和缓存链路复用。"""

from prometheus_client import Counter, Gauge, Histogram

# ===== HTTP 层 =====
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP 请求总数",
    ["method", "path_template", "status_class"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求耗时分布",
    ["method", "path_template"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        30.0,
        60.0,
    ),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "当前在处理的 HTTP 请求数",
    ["method", "path_template"],
)

# ===== RAG 链路 =====
_RAG_STAGE_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

RAG_STAGE_DURATION_SECONDS = Histogram(
    "rag_stage_duration_seconds",
    "RAG 各阶段耗时",
    ["stage"],
    buckets=_RAG_STAGE_BUCKETS,
)

RAG_TOTAL_DURATION_SECONDS = Histogram(
    "rag_total_duration_seconds",
    "RAG 端到端总耗时",
    ["outcome"],
    buckets=(0.5, 1.0, 2.5, 5.0, 8.0, 15.0, 30.0, 60.0),
)

RAG_TTFT_SECONDS = Histogram(
    "rag_ttft_seconds",
    "RAG 首 token 延迟（Time To First Token）",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 15.0),
)

RAG_OUTCOME_TOTAL = Counter(
    "rag_outcome_total",
    "RAG 问答结果分布",
    ["outcome", "error_code"],
)

RAG_CANDIDATES_COUNT = Histogram(
    "rag_candidates_count",
    "RAG 各阶段候选数",
    ["stage"],
    buckets=(0, 1, 3, 5, 10, 20, 50, 100),
)

RAG_CITATIONS_COUNT = Histogram(
    "rag_citations_count",
    "RAG 引用切片数",
    buckets=(0, 1, 2, 3, 5, 8, 13, 20),
)

RAG_COHERE_TOP_SCORE = Histogram(
    "rag_cohere_top_score",
    "Cohere rerank top1 分数",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0),
)

RAG_QUERY_REWRITTEN_TOTAL = Counter(
    "rag_query_rewritten_total",
    "RAG 是否经过 query rewrite",
    ["rewritten"],
)

RAG_SCOPE_SIZE = Histogram(
    "rag_scope_size",
    "RAG 检索 scope 中的 KB 数量",
    buckets=(0, 1, 2, 3, 5, 10),
)

# ===== Cache 层 =====
CACHE_LOOKUP_TOTAL = Counter(
    "cache_lookup_total",
    "缓存查询次数",
    ["layer", "result"],
)

CACHE_OPERATION_DURATION_SECONDS = Histogram(
    "cache_operation_duration_seconds",
    "缓存操作耗时",
    ["layer", "operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# ===== 应用元信息 =====
APP_INFO = Gauge(
    "app_info",
    "应用元信息，值固定为 1",
    ["version", "env"],
)

# ===== Celery 任务 =====
CELERY_TASK_DURATION_SECONDS = Histogram(
    "celery_task_duration_seconds",
    "Celery 任务执行耗时",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

CELERY_TASK_TOTAL = Counter(
    "celery_task_total",
    "Celery 任务成功/失败数",
    ["task_name", "status"],
)

CELERY_QUEUE_LENGTH = Gauge(
    "celery_queue_length",
    "Celery 队列待处理任务数",
    ["queue"],
)

CELERY_ACTIVE_TASKS = Gauge(
    "celery_active_tasks",
    "Celery 当前正在执行的任务数",
)

# ===== Embedding =====
EMBEDDING_DURATION_SECONDS = Histogram(
    "embedding_duration_seconds",
    "Embedding 调用耗时",
    ["model"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
