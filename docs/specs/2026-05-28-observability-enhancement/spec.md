# Spec：可观测性补齐 — Celery 指标 + Embedding 指标 + 面板细化

| 字段 | 值 |
|---|---|
| **Spec ID** | `2026-05-28-observability-enhancement` |
| **作者** | 任孟雪 |
| **创建日期** | 2026-05-28 |
| **预计工时** | 1d |
| **状态** | Draft |

---

## 0. 背景：当前可观测性缺口

系统已有 15 个 Prometheus 指标 + 3 个 Grafana Dashboard（HTTP & SLI、Cache 命中率、RAG 链路），但存在三个盲区：

| # | 缺口 | 影响 |
|---|---|---|
| 1 | **Celery 零指标**：无任务耗时、队列长度、成功率 | 无法回答"队列是否堆积""摄入任务多久完成" |
| 2 | **Embedding 无独立指标**：embedding 耗时和向量检索耗时混在 `stage="vector"` | 无法拆分 embedding 慢还是 pgvector 检索慢 |
| 3 | **RAG 面板粗粒度**：5 阶段堆一条线、无 error_code 分布、无 P50/P99、无 retrieval hit rate 代理指标 | 已有数据但看不到细节，无法下钻定位 |

---

## 1. 范围与不做项

### 1.1 这次做

| ID | 内容 | 优先级 | 工时 |
|---|---|---|---|
| P0-1 | Celery 指标：4 个新 Prometheus 指标 + signals 埋点 | P0 | 0.3d |
| P0-2 | Embedding 独立指标：1 个新 Histogram + `embedding_service.py` 埋点 | P0 | 0.1d |
| P0-3 | 新增 Grafana Celery Dashboard（4 panel） | P0 | 0.1d |
| P0-4 | RAG Dashboard 细化：stage 独立面板、error_code 分布、P50/P99、retrieval hit rate | P0 | 0.2d |
| P0-5 | HTTP Dashboard 补全：已有 P50/P95/P99，确认无误即可 | P0 | 0.05d |
| P0-6 | 跑 eval 验证所有面板出数 | P0 | 0.15d |

### 1.2 这次不做

| 不做项 | 理由 |
|---|---|
| ground truth retrieval hit rate（标注数据） | 成本高，先用 `citations_count / merged_candidates` 代理 |
| Alertmanager / 告警通知 | 已有 2 条 alert rule，不新增 |
| 按知识库维度拆分视图 | 需要 payload 加 kb_id 标签，本次不改业务逻辑 |
| DB 连接池 / Redis 连接数 / 内存等系统级指标 | 量大，单独 spec |
| Sentry 集成变更 | 已有，不动 |

---

## 2. P0-1：Celery 指标

### 2.1 技术方案

在 `tasks/__init__.py` 中注册 Celery signals，零外部依赖。

**新增 4 个指标**（定义在 `backend/app/core/metrics.py`）：

| 指标名 | 类型 | 标签 | 含义 |
|---|---|---|---|
| `celery_task_duration_seconds` | Histogram | `task_name` | 任务执行耗时 |
| `celery_task_total` | Counter | `task_name`, `status` (success/failure) | 任务成功/失败数 |
| `celery_queue_length` | Gauge | `queue` | 当前队列待处理任务数 |
| `celery_active_tasks` | Gauge | 无 | 当前正在执行的任务数 |

**signals 绑定**（在 `tasks/__init__.py` 中）：

```python
from celery import signals

@signals.task_prerun.connect
def _on_task_prerun(sender=None, **kwargs):
    CELERY_ACTIVE_TASKS.inc()
    CELERY_QUEUE_LENGTH.labels(queue=sender.name).dec()

@signals.task_postrun.connect
def _on_task_postrun(sender=None, state=None, runtime=None, **kwargs):
    CELERY_ACTIVE_TASKS.dec()
    CELERY_TASK_DURATION_SECONDS.labels(task_name=sender.name).observe(runtime)
    CELERY_TASK_TOTAL.labels(task_name=sender.name, status="success").inc()

@signals.task_failure.connect
def _on_task_failure(sender=None, **kwargs):
    CELERY_ACTIVE_TASKS.dec()
    CELERY_TASK_TOTAL.labels(task_name=sender.name, status="failure").inc()
```

队列长度的初始值在 Celery app 启动时从 broker 查询：

```python
# 在 celery_app 创建后
try:
    from celery import current_app
    inspect = current_app.control.inspect()
    reserved = inspect.reserved() or {}
    active = inspect.active() or {}
    for queue_name in current_app.conf.task_routes or {}:
        CELERY_QUEUE_LENGTH.labels(queue=queue_name).set(0)
except Exception:
    pass  # broker 不可达时跳过，Gauge 从 0 开始
```

### 2.2 现有任务清单

| 任务 | task_name | 来源 |
|---|---|---|
| `ingest_knowledge` | `knowledge.ingest` | `knowledge_tasks.py` |
| `summarize_conversation` | `qa.summarize` | `qa_tasks.py` |

### 2.3 注意事项

- `worker_concurrency=1`，所以 `CELERY_ACTIVE_TASKS` 最大值为 1
- 队列长度的 Gauge 精度取决于 broker 查询频率，signals 只做增减修正
- signals 在 worker 进程内生效，`celery_app` 所在文件需要被 worker import

---

## 3. P0-2：Embedding 独立指标

### 3.1 技术方案

在 `backend/app/core/metrics.py` 新增 1 个指标，在 `embedding_service.py` 埋点。

**新增指标**：

| 指标名 | 类型 | 标签 | 含义 |
|---|---|---|---|
| `embedding_duration_seconds` | Histogram | `model` | embedding 调用耗时 |

**埋点位置**：`embedding_service.py` 的 embed 方法，在调用 OpenAI embedding API 前后用 `time.perf_counter()` 计时。

```python
# embedding_service.py 伪变更
import time
from backend.app.core.metrics import EMBEDDING_DURATION_SECONDS

async def embed(self, texts: list[str], model: str = "text-embedding-3-small"):
    t0 = time.perf_counter()
    try:
        result = await self._call_api(texts, model)
        return result
    finally:
        EMBEDDING_DURATION_SECONDS.labels(model=model).observe(time.perf_counter() - t0)
```

### 3.2 与现有 stage="vector" 的关系

`rag_stage_duration_seconds{stage="vector"}` 记录的是整个向量检索阶段耗时（含 embedding + pgvector 查询），新增的 `embedding_duration_seconds` 是它的子集。两者不冲突。

---

## 4. P0-3：新增 Celery Dashboard

### 4.1 文件

新增 `monitoring/grafana/provisioning/dashboards/celery.json`

### 4.2 面板设计

| Panel | Title | Type | PromQL |
|---|---|---|---|
| 1 | 队列长度 | stat | `celery_queue_length` |
| 2 | 活跃任务数 | stat | `celery_active_tasks` |
| 3 | 任务成功率 | stat | `sum(rate(celery_task_total{status="success"}[5m])) / sum(rate(celery_task_total[5m]))` |
| 4 | 任务耗时 P95 | timeseries | `histogram_quantile(0.95, sum by (le, task_name)(rate(celery_task_duration_seconds_bucket[5m])))` |

时间范围默认 now-1h，refresh 30s。

---

## 5. P0-4：RAG Dashboard 细化

### 5.1 文件

修改 `monitoring/grafana/provisioning/dashboards/rag.json`

### 5.2 面板设计

**替换现有 5 阶段合图**为 5 个独立 stat panel：

| Panel | Title | PromQL |
|---|---|---|
| rewrite P95 | `histogram_quantile(0.95, sum by (le)(rate(rag_stage_duration_seconds_bucket{stage="rewrite"}[5m])))` |
| vector P95 | `histogram_quantile(0.95, sum by (le)(rate(rag_stage_duration_seconds_bucket{stage="vector"}[5m])))` |
| fts P95 | `histogram_quantile(0.95, sum by (le)(rate(rag_stage_duration_seconds_bucket{stage="fts"}[5m])))` |
| rerank P95 | `histogram_quantile(0.95, sum by (le)(rate(rag_stage_duration_seconds_bucket{stage="rerank"}[5m])))` |
| generation P95 | `histogram_quantile(0.95, sum by (le)(rate(rag_stage_duration_seconds_bucket{stage="generation"}[5m])))` |

**新增面板**：

| Panel | Title | Type | PromQL |
|---|---|---|---|
| error_code 分布 | timeseries | `sum by (error_code)(rate(rag_outcome_total{outcome="error"}[5m]))` |
| retrieval hit rate | stat | `sum(rate(rag_citations_count_sum[5m])) / sum(rate(rag_candidates_count_bucket{stage="merged"}[5m]))` |
| 总耗时 P50/P95/P99 | timeseries | `histogram_quantile(0.50/0.95/0.99, ...rag_total_duration_seconds_bucket...)` |

### 5.3 retrieval hit rate 说明

用 `总引用 chunk 数 / 合并后候选 chunk 数` 作为检索质量的代理指标。含义：召回的候选 chunk 中有多大比例最终被实际引用。这不是真正的 precision/recall（需要 ground truth），但能在无标注情况下给出趋势信号。

---

## 6. P0-5：HTTP Dashboard 确认

已有面板包含 P50/P95/P99 时序图，无需修改。确认 `http.json` 正常出数即可。

---

## 7. 技术方案汇总

- **采用方案**：纯埋点 + 面板配置，不碰业务逻辑
- **关键决策理由**：
  - Celery signals 是 Celery 内置机制，零新依赖
  - embedding 埋点在 `finally` 块，异常安全
  - retrieval hit rate 用代理指标而非 ground truth，可立即上线
- **依赖的现有模块**：`metrics.py`、`metrics_middleware.py`、`tasks/__init__.py`、`embedding_service.py`、Grafana provisioning JSON
## 8. 数据模型

无新增表/字段。

---

## 9. 文件变更清单

| 文件 | 变更 |
|---|---|
| `backend/app/core/metrics.py` | 新增 5 个指标定义（Celery 4 个 + embedding 1 个） |
| `backend/app/tasks/__init__.py` | 新增 Celery signals 注册和埋点 |
| `backend/app/services/embedding_service.py` | 新增 embedding 耗时埋点 |
| `monitoring/grafana/provisioning/dashboards/rag.json` | 面板细化：stage 拆分 + error_code + P50/P99 + hit rate |
| `monitoring/grafana/provisioning/dashboards/celery.json` | **新增** Celery Dashboard |

---

## 10. TODO 清单

- [ ] P0-1：`metrics.py` 新增 4 个 Celery 指标定义
- [ ] P0-1：`tasks/__init__.py` 注册 Celery signals 埋点
- [ ] P0-2：`metrics.py` 新增 embedding 指标定义
- [ ] P0-2：`embedding_service.py` 加 embedding 耗时埋点
- [ ] P0-3：新增 `celery.json` Dashboard
- [ ] P0-4：更新 `rag.json` Dashboard（stage 拆分 + error_code + hit rate + P50/P99）
- [ ] P0-5：确认 `http.json` 出数正常
- [ ] P0-6：`dev.sh` 重启全部服务，跑 eval 验证所有面板出数

---

## 11. 测试计划

- P0-1：`curl /metrics | grep celery_` 有 4 个指标输出；触发 ingest 任务后 Prometheus 有数据
- P0-2：`curl /metrics | grep embedding_` 有输出；发一次 QA 请求后 histogram 有 observe
- P0-3：Grafana Celery Dashboard 4 panel 全部出数
- P0-4：Grafana RAG Dashboard 新 panel 出数；5 stage 各自 P95 独立展示
- P0-6：`run_eval.py` 跑完后所有 4 个 Dashboard 面板出数，无 "No data"
