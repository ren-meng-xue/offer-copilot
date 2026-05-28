# 可观测性补齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 Celery + embedding 指标埋点，细化 RAG Grafana 面板，新增 Celery Dashboard

**Architecture:** 纯埋点 + 面板配置，不碰业务逻辑。在 `metrics.py` 新增 5 个指标定义，在 `tasks/__init__.py` 和 `embedding_service.py` 加埋点，在 Grafana provisioning JSON 中新增/修改面板

**Tech Stack:** Python 3.12, Celery 5.x, prometheus-client, Grafana 11.3.0

**Spec:** `docs/specs/2026-05-28-observability-enhancement/spec.md`

---

## File Map

| 文件 | 职责 | 变更类型 |
|---|---|---|
| `backend/app/core/metrics.py` | 新增 5 个指标定义（Celery ×4 + embedding ×1） | Modify |
| `backend/app/tasks/__init__.py` | 注册 Celery signals，埋点 task 生命周期 | Modify |
| `backend/app/services/embedding_service.py` | 在 `generate_embeddings()` 中加耗时埋点 | Modify |
| `monitoring/grafana/provisioning/dashboards/celery.json` | 新 Dashboard：Celery 队列/耗时/成功率 | Create |
| `monitoring/grafana/provisioning/dashboards/rag.json` | 细化面板：stage 独立 + error_code + hit rate + P50/P99 | Modify |

---

### Task 1: metrics.py — 新增 Celery 4 个指标定义

**Files:**
- Modify: `backend/app/core/metrics.py` (append after line 118)

- [ ] **Step 1: 在 `metrics.py` 末尾追加 Celery 指标定义**

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

- [ ] **Step 2: 验证指标注册**

```bash
cd backend && uv run python -c "from backend.app.core.metrics import CELERY_TASK_DURATION_SECONDS, CELERY_TASK_TOTAL, CELERY_QUEUE_LENGTH, CELERY_ACTIVE_TASKS; print('OK')"
```

Expected: `OK`

---

### Task 2: tasks/__init__.py — 注册 Celery signals 埋点

**Files:**
- Modify: `backend/app/tasks/__init__.py` (append after line 38)

- [ ] **Step 1: 在 `tasks/__init__.py` 末尾追加 signals 注册代码**

```python
# ===== Prometheus metrics — Celery signals =====
from celery import signals

from backend.app.core.config import settings as _settings


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

- [ ] **Step 2: 同步更新文件顶部的 import**

在 `tasks/__init__.py` 的现有导入之后，signals 注册之前，插入：

```python
from backend.app.core.metrics import (
    CELERY_ACTIVE_TASKS,
    CELERY_QUEUE_LENGTH,
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASK_TOTAL,
)
```

放在 `from celery import signals` 这一行之前。

- [ ] **Step 3: 验证语法正确**

```bash
cd backend && uv run python -c "import backend.app.tasks; print('OK')"
```

Expected: `OK`（Celery signals 注册成功，不报 import error）

---

### Task 3: metrics.py — 新增 embedding 指标定义

**Files:**
- Modify: `backend/app/core/metrics.py` (append after Celery 指标块)

- [ ] **Step 1: 追加 embedding 指标定义**

```python
# ===== Embedding =====
EMBEDDING_DURATION_SECONDS = Histogram(
    "embedding_duration_seconds",
    "Embedding 调用耗时",
    ["model"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
```

- [ ] **Step 2: 验证**

```bash
cd backend && uv run python -c "from backend.app.core.metrics import EMBEDDING_DURATION_SECONDS; print('OK')"
```

Expected: `OK`

---

### Task 4: embedding_service.py — 加 embedding 耗时埋点

**Files:**
- Modify: `backend/app/services/embedding_service.py` (lines 22-36)

- [ ] **Step 1: 修改 `generate_embeddings()` 函数加计时**

将 `generate_embeddings()` 函数改为：

```python
import time

from backend.app.core.metrics import EMBEDDING_DURATION_SECONDS


# 批量生成文本 embedding，返回向量列表。
async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch generate embeddings for a list of texts."""
    client = get_openai_client()
    all_embeddings: list[list[float]] = []

    t0 = time.perf_counter()
    try:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            response = await client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
            )
            all_embeddings.extend([item.embedding for item in response.data])
    finally:
        EMBEDDING_DURATION_SECONDS.labels(model=EMBEDDING_MODEL).observe(time.perf_counter() - t0)

    return all_embeddings
```

注意：`import time` 放在文件顶部已有 import 之后、`from openai import AsyncOpenAI` 之前。

- [ ] **Step 2: 验证语法正确**

```bash
cd backend && uv run python -c "from backend.app.services.embedding_service import generate_embeddings; print('OK')"
```

Expected: `OK`

---

### Task 5: 新增 Celery Dashboard (celery.json)

**Files:**
- Create: `monitoring/grafana/provisioning/dashboards/celery.json`

- [ ] **Step 1: 创建 celery.json**

写入以下 JSON（完整内容，包含 4 个面板）：

```json
{
  "annotations": { "list": [] },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "thresholds" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "red", "value": null },
              { "color": "green", "value": 0 }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 4, "x": 0, "y": 0 },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
        "textMode": "auto"
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "Prometheus" },
          "expr": "celery_queue_length",
          "refId": "A"
        }
      ],
      "title": "队列长度",
      "type": "stat"
    },
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "thresholds" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "green", "value": null }]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 4, "x": 4, "y": 0 },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
        "textMode": "auto"
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "Prometheus" },
          "expr": "celery_active_tasks",
          "refId": "A"
        }
      ],
      "title": "活跃任务数",
      "type": "stat"
    },
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "thresholds" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "red", "value": null },
              { "color": "green", "value": 0.95 }
            ]
          },
          "unit": "percentunit"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 4, "x": 8, "y": 0 },
      "id": 3,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
        "textMode": "auto"
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "Prometheus" },
          "expr": "sum(rate(celery_task_total{status=\"success\"}[5m])) / sum(rate(celery_task_total[5m])) or vector(0)",
          "refId": "A"
        }
      ],
      "title": "任务成功率",
      "type": "stat"
    },
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "off" }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "green", "value": null }]
          },
          "unit": "s"
        },
        "overrides": []
      },
      "gridPos": { "h": 10, "w": 12, "x": 0, "y": 8 },
      "id": 4,
      "options": {
        "legend": { "calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true },
        "tooltip": { "mode": "single", "sort": "none" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "Prometheus" },
          "expr": "histogram_quantile(0.95, sum by (le, task_name)(rate(celery_task_duration_seconds_bucket[5m])))",
          "legendFormat": "{{task_name}}",
          "refId": "A"
        }
      ],
      "title": "任务耗时 P95",
      "type": "timeseries"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 39,
  "tags": ["celery", "observability"],
  "templating": { "list": [] },
  "time": { "from": "now-1h", "to": "now" },
  "timepicker": {},
  "timezone": "",
  "title": "Celery 任务",
  "uid": "offer-copilot-celery",
  "version": 1
}
```

- [ ] **Step 2: 确认 JSON 格式合法**

```bash
python3 -m json.tool monitoring/grafana/provisioning/dashboards/celery.json > /dev/null && echo "OK"
```

Expected: `OK`

---

### Task 6: 细化 RAG Dashboard (rag.json)

**Files:**
- Modify: `monitoring/grafana/provisioning/dashboards/rag.json`

> 为了不破坏已有告警规则（panel id=1 上的成功率告警），采用**增量追加**策略：保留已有 5 个 panel，新增 4 个 panel。

- [ ] **Step 1: 新增 5 个 stage 独立 stat panels（id 6-10）**

在 `rag.json` 的 `"panels"` 数组中，现有 5 个 panel（id 1-5）之后追加：

**id=6: rewrite P95 stat**

```json
{
  "datasource": { "type": "prometheus", "uid": "Prometheus" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "mappings": [],
      "thresholds": { "mode": "absolute", "steps": [{ "color": "green", "value": null }] },
      "unit": "s"
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 2, "x": 0, "y": 16 },
  "id": 6,
  "options": {
    "colorMode": "value",
    "graphMode": "area",
    "justifyMode": "auto",
    "orientation": "auto",
    "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
    "textMode": "auto"
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "expr": "histogram_quantile(0.95, sum by (le)(rate(rag_stage_duration_seconds_bucket{stage=\"rewrite\"}[5m])))",
      "refId": "A"
    }
  ],
  "title": "rewrite",
  "type": "stat"
}
```

**id=7: vector P95 stat** — 同上结构，`gridPos: { "h": 6, "w": 2, "x": 2, "y": 16 }`，`expr` 中 `stage=\"vector\"`，`title: "vector"`

**id=8: fts P95 stat** — 同上，`gridPos: { "h": 6, "w": 3, "x": 4, "y": 16 }`，`expr` 中 `stage=\"fts\"`，`title: "fts"`

**id=9: rerank P95 stat** — 同上，`gridPos: { "h": 6, "w": 3, "x": 7, "y": 16 }`，`expr` 中 `stage=\"rerank\"`，`title: "rerank"`

**id=10: generation P95 stat** — 同上，`gridPos: { "h": 6, "w": 2, "x": 10, "y": 16 }`，`expr` 中 `stage=\"generation\"`，`title: "generation"`

- [ ] **Step 2: 新增 error_code 分布 timeseries panel（id=11）**

```json
{
  "datasource": { "type": "prometheus", "uid": "Prometheus" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "drawStyle": "line",
        "fillOpacity": 10,
        "lineWidth": 1,
        "stacking": { "group": "A", "mode": "none" }
      },
      "unit": "reqps"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 6, "x": 12, "y": 8 },
  "id": 11,
  "options": {
    "legend": { "displayMode": "list", "placement": "bottom", "showLegend": true }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "expr": "sum by (error_code)(rate(rag_outcome_total{outcome=\"error\"}[5m]))",
      "legendFormat": "{{error_code}}",
      "refId": "A"
    }
  ],
  "title": "error_code 分布",
  "type": "timeseries"
}
```

- [ ] **Step 3: 新增 retrieval hit rate stat panel（id=12）**

```json
{
  "datasource": { "type": "prometheus", "uid": "Prometheus" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "mappings": [],
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "red", "value": null },
          { "color": "yellow", "value": 0.1 },
          { "color": "green", "value": 0.3 }
        ]
      },
      "unit": "percentunit"
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 4, "x": 0, "y": 22 },
  "id": 12,
  "options": {
    "colorMode": "value",
    "graphMode": "area",
    "justifyMode": "auto",
    "orientation": "auto",
    "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
    "textMode": "auto"
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "expr": "sum(rate(rag_citations_count_sum[5m])) / sum(rate(rag_candidates_count_sum{stage=\"merged\"}[5m])) or vector(0)",
      "legendFormat": "hit rate",
      "refId": "A"
    }
  ],
  "title": "retrieval hit rate",
  "type": "stat"
}
```

- [ ] **Step 4: 新增总耗时 P50/P95/P99 timeseries panel（id=13）**

```json
{
  "datasource": { "type": "prometheus", "uid": "Prometheus" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "drawStyle": "line",
        "fillOpacity": 0,
        "lineWidth": 2
      },
      "unit": "s"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 8, "x": 4, "y": 22 },
  "id": 13,
  "options": {
    "legend": { "displayMode": "list", "placement": "bottom", "showLegend": true }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "expr": "histogram_quantile(0.50, sum by (le)(rate(rag_total_duration_seconds_bucket[5m])))",
      "legendFormat": "p50",
      "refId": "A"
    },
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "expr": "histogram_quantile(0.95, sum by (le)(rate(rag_total_duration_seconds_bucket[5m])))",
      "legendFormat": "p95",
      "refId": "B"
    },
    {
      "datasource": { "type": "prometheus", "uid": "Prometheus" },
      "expr": "histogram_quantile(0.99, sum by (le)(rate(rag_total_duration_seconds_bucket[5m])))",
      "legendFormat": "p99",
      "refId": "C"
    }
  ],
  "title": "总耗时 P50/P95/P99",
  "type": "timeseries"
}
```

- [ ] **Step 5: 确认 JSON 格式合法**

```bash
python3 -m json.tool monitoring/grafana/provisioning/dashboards/rag.json > /dev/null && echo "OK"
```

Expected: `OK`

---

### Task 7: 验证 — 重启服务 + 检查指标

**Files:** 无新建/修改

- [ ] **Step 1: 重启 docker 服务 + backend**

```bash
cd /Users/xuebao/learn/AI项目/offer-copilot
docker-compose restart prometheus grafana
```

然后重启 backend（uvicorn）和 celery worker。

- [ ] **Step 2: 验证 /metrics 端点有新增指标**

```bash
curl -s localhost:8000/metrics | grep -E "celery_|embedding_" | head -20
```

Expected: 能看到 `celery_task_duration_seconds`、`celery_task_total`、`celery_queue_length`、`celery_active_tasks`、`embedding_duration_seconds` 的 HELP/TYPE 行。

- [ ] **Step 3: 触发一个 celery 任务验证埋点**

发一次 QA 请求或知识库导入请求，然后：

```bash
curl -s localhost:8000/metrics | grep 'celery_task_total'
```

Expected: 至少能看到 `celery_task_total{task_name="qa.summarize",status="success"}` 有非零值。

- [ ] **Step 4: 验证 Prometheus 抓取正常**

```bash
curl -s "localhost:9090/api/v1/query?query=celery_task_total" | python3 -m json.tool | grep '"value"'
```

Expected: 有数据点返回。

- [ ] **Step 5: 验证 Grafana 所有 Dashboard 出数**

打开 `http://localhost:3001`，检查：
- HTTP & SLI：5 panel 全出数（已有，确认无回归）
- Cache 命中率：4 panel 全出数（已有，确认无回归）
- RAG 链路：9 panel 全出数（新增 4 个）
- Celery 任务：4 panel 全出数（新增 Dashboard）

- [ ] **Step 6: 运行 `black` + `isort` 格式化 Python 文件**

```bash
cd backend && uv run black app/core/metrics.py app/tasks/__init__.py app/services/embedding_service.py && uv run isort app/core/metrics.py app/tasks/__init__.py app/services/embedding_service.py
```
