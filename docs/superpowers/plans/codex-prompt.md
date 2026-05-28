你是一个熟练的 Python 后端工程师。请在当前项目 offer-copilot 中完成可观测性补齐任务。

## 项目背景

- FastAPI + Celery + Prometheus + Grafana 的 RAG 知识库问答系统
- 已有 15 个 Prometheus 指标和 3 个 Grafana Dashboard
- 后端在 `backend/` 下，用 `uv run` 管理依赖
- Prometheus 指标统一定义在 `backend/app/core/metrics.py`
- Grafana Dashboard JSON 在 `monitoring/grafana/provisioning/dashboards/`

## 要做什么

补齐 Celery 任务监控指标 + Embedding 独立指标 + 细化 RAG 和新增 Celery Dashboard。纯埋点 + 面板配置，不碰业务逻辑。

## 具体任务（按顺序执行）

### 任务 1：metrics.py 追加 Celery 4 个指标

文件：`backend/app/core/metrics.py`，在文件末尾（第 118 行 `APP_INFO` 之后）追加：

```python
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
```

验证：`cd backend && uv run python -c "from backend.app.core.metrics import CELERY_TASK_DURATION_SECONDS, CELERY_TASK_TOTAL, CELERY_QUEUE_LENGTH, CELERY_ACTIVE_TASKS; print('OK')"` 输出 OK。

### 任务 2：tasks/__init__.py 注册 Celery signals

文件：`backend/app/tasks/__init__.py`

先在文件顶部现有 import 之后（`from celery import Celery` 那行之后）插入：

```python
from celery import signals

from backend.app.core.metrics import (
    CELERY_ACTIVE_TASKS,
    CELERY_QUEUE_LENGTH,
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASK_TOTAL,
)
```

然后在文件末尾追加：

```python
# ===== Prometheus metrics — Celery signals =====
@signals.task_prerun.connect
def _on_task_prerun(sender=None, **_kwargs):
    task_name = sender.name if sender else "unknown"
    CELERY_ACTIVE_TASKS.inc()
    CELERY_QUEUE_LENGTH.labels(queue=task_name).dec()


@signals.task_postrun.connect
def _on_task_postrun(sender=None, state=None, runtime=None, **_kwargs):
    task_name = sender.name if sender else "unknown"
    CELERY_ACTIVE_TASKS.dec()
    if runtime is not None:
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(runtime)
    CELERY_TASK_TOTAL.labels(task_name=task_name, status="success" if state == "SUCCESS" else "failure").inc()


@signals.task_failure.connect
def _on_task_failure(sender=None, **_kwargs):
    task_name = sender.name if sender else "unknown"
    CELERY_ACTIVE_TASKS.dec()
    CELERY_TASK_TOTAL.labels(task_name=task_name, status="failure").inc()
```

验证：`cd backend && uv run python -c "import backend.app.tasks; print('OK')"` 输出 OK。

### 任务 3：metrics.py 追加 Embedding 指标

文件：`backend/app/core/metrics.py`，在 Celery 指标块之后追加：

```python
# ===== Embedding =====
EMBEDDING_DURATION_SECONDS = Histogram(
    "embedding_duration_seconds",
    "Embedding 调用耗时",
    ["model"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
```

验证：`cd backend && uv run python -c "from backend.app.core.metrics import EMBEDDING_DURATION_SECONDS; print('OK')"`。

### 任务 4：embedding_service.py 加耗时埋点

文件：`backend/app/services/embedding_service.py`

在文件顶部现有 import 后插入 `import time`。然后把 `generate_embeddings()` 函数改写为带计时 + finally 埋点的版本。具体：函数体用 `t0 = time.perf_counter()` 开始计时 → `try:` 包裹原有的 batch embedding 循环 → `finally:` 中用 `EMBEDDING_DURATION_SECONDS.labels(model=EMBEDDING_MODEL).observe(time.perf_counter() - t0)` 记录耗时。同时从 `backend.app.core.metrics` import `EMBEDDING_DURATION_SECONDS`。

验证：`cd backend && uv run python -c "from backend.app.services.embedding_service import generate_embeddings; print('OK')"`。

### 任务 5：新建 Celery Dashboard JSON

新建文件：`monitoring/grafana/provisioning/dashboards/celery.json`

这是 Grafana 11.3.0 的 Dashboard JSON，uid 为 `offer-copilot-celery`，title 为 "Celery 任务"，refresh 30s，tags ["celery", "observability"]。

包含 4 个 panel：
1. id=1 "队列长度" stat，PromQL: `celery_queue_length`
2. id=2 "活跃任务数" stat，PromQL: `celery_active_tasks`
3. id=3 "任务成功率" stat，PromQL: `sum(rate(celery_task_total{status="success"}[5m])) / sum(rate(celery_task_total[5m])) or vector(0)`，红色<95% 绿色>=95%
4. id=4 "任务耗时 P95" timeseries，PromQL: `histogram_quantile(0.95, sum by (le, task_name)(rate(celery_task_duration_seconds_bucket[5m])))`，legend `{{task_name}}`

所有 panel 的数据源是 `{"type": "prometheus", "uid": "Prometheus"}`。JSON 结构参考项目中已有的 `monitoring/grafana/provisioning/dashboards/http.json` 格式（annotations/editable/panels/refresh/schemaVersion/tags/time/title/uid/version）。

验证：`python3 -m json.tool monitoring/grafana/provisioning/dashboards/celery.json > /dev/null && echo "OK"`

### 任务 6：细化 RAG Dashboard (rag.json)

文件：`monitoring/grafana/provisioning/dashboards/rag.json`

保留已有 5 个 panel（id 1-5，含告警规则），在 panels 数组末尾追加 4 个新 panel：

**6-10: 5 个 stage 独立 P95 stat panels**
- id=6 title="rewrite"，gridPos {0,16,2,6}，PromQL `histogram_quantile(0.95, sum by (le)(rate(rag_stage_duration_seconds_bucket{stage="rewrite"}[5m])))`
- id=7 title="vector"，gridPos {2,16,2,6}，stage="vector"
- id=8 title="fts"，gridPos {4,16,3,6}，stage="fts"
- id=9 title="rerank"，gridPos {7,16,3,6}，stage="rerank"
- id=10 title="generation"，gridPos {10,16,2,6}，stage="generation"

所有 stat panel 结构同上，unit "s"，colorMode "value"。

**id=11 "error_code 分布" timeseries**，gridPos {12,8,6,8}，PromQL `sum by (error_code)(rate(rag_outcome_total{outcome="error"}[5m]))`，legend `{{error_code}}`。

**id=12 "retrieval hit rate" stat**，gridPos {0,22,4,6}，PromQL `sum(rate(rag_citations_count_sum[5m])) / sum(rate(rag_candidates_count_sum{stage="merged"}[5m])) or vector(0)`，阈值红<10% 黄<30% 绿>=30%。

**id=13 "总耗时 P50/P95/P99" timeseries**，gridPos {4,22,8,8}，3 条 target：P50/P95/P99 分别 legendFormat "p50"/"p95"/"p99"。

验证：`python3 -m json.tool monitoring/grafana/provisioning/dashboards/rag.json > /dev/null && echo "OK"`

### 任务 7：格式化和最终验证

运行：
```bash
cd backend && uv run black app/core/metrics.py app/tasks/__init__.py app/services/embedding_service.py
cd backend && uv run isort app/core/metrics.py app/tasks/__init__.py app/services/embedding_service.py
```

然后确认 `/metrics` 端点有新增指标：
```bash
curl -s localhost:8000/metrics | grep -E "celery_|embedding_"
```

## 重要约束

1. 不改动业务逻辑，只加埋点和面板
2. `rag.json` 的已有 5 个 panel 必须保留（panel id=1 上有告警规则）
3. 所有 Prometheus 指标定义必须放在 `metrics.py` 统一定义
4. Celery signals 必须从 `celery` 包导入，不是从 `celery_app` 实例
5. embedding 埋点必须放在 `finally` 块中，确保异常时也能记录耗时
