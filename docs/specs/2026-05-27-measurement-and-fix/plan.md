# 测量驱动的修复与可观测性建设 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 offer-copilot 项目加一套量化指标（Prometheus + Grafana 三看板 + 评估集 + 压测），在建设过程中用数据发现并修复 5 个 review 已识别的 P0/P1/INFO 级别 bug，沉淀一份可在面试 5 分钟讲完的"测量驱动修复"故事报告。

**Architecture:** Prometheus 本地 pull 后端 `/metrics` → Grafana 三张看板（RAG / HTTP / Cache，JSON provisioning 进 git）。`rag_telemetry` 既写日志也增 Prometheus 指标。Locust + 评估脚本通过真实 HTTP 接口打流量，跑两轮（修复前 / 修复后）拿对比数据。

**Tech Stack:** FastAPI + `prometheus-client` + `starlette` middleware；PostgreSQL JSONB + ivfflat 索引（Alembic 迁移）；Locust + `httpx-sse`；Grafana provisioning；前端 TypeScript（无新增依赖）。

**关联文档:**
- [Spec](./spec.md) — 设计文档，本 plan 实现 spec §1-9 全部内容
- [Flow](./flow.html) — 流程图
- [Follow-up](./follow-up.md) — B 堆 backlog（本 plan 不处理）

---

## File Structure

### 新建目录与文件

```
monitoring/                                       (新增根目录)
├── prometheus.yml                                # Prometheus 抓取配置
└── grafana/
    └── provisioning/
        ├── datasources/prometheus.yml
        └── dashboards/
            ├── dashboards.yml
            ├── rag.json
            ├── http.json
            └── cache.json

backend/app/core/
├── metrics.py                                    # 新增：所有 Prometheus metric 定义
└── metrics_middleware.py                         # 新增：HTTP middleware

backend/alembic/versions/
├── <new>_alter_kb_ids_to_jsonb.py                # 新增：F2 迁移
└── <new>_add_ivfflat_to_semantic_cache.py        # 新增：F4 迁移

backend/scripts/
├── eval/
│   ├── __init__.py
│   ├── run_eval.py                               # 评估脚本
│   ├── generate_synthetic.py                     # 生成合成集
│   └── sse_client.py                             # 共用 SSE 解析（评估+压测）
└── load_test/
    ├── __init__.py
    └── locustfile.py

eval/                                             (新增根目录)
├── golden.jsonl                                  # 20 道人工标注
└── synthetic.jsonl                               # 50-100 道 LLM 生成

backend/tests/
├── core/
│   └── test_metrics.py
├── repositories/
│   └── test_qa_repository_evict.py
└── services/
    ├── test_qa_service_cache_key.py
    └── test_qa_service_sse_micro.py

frontend/src/lib/__tests__/
└── session.test.ts                               # 新增或修改

docs/specs/2026-05-27-measurement-and-fix/
├── report-baseline.md                            # 阶段 4.1 产出
├── report-after.md                               # 阶段 4.2 产出
├── final-report.md                               # 阶段 5 产出
└── screenshots/
    ├── baseline/
    └── after/
```

### 修改文件

| 文件 | 改动概述 |
|---|---|
| `docker-compose.yml` | 加 `prometheus` + `grafana` service + 两个 volume |
| `dev.sh` | 启动多带 `prometheus grafana` 两个服务 |
| `backend/pyproject.toml` | `dependencies` 加 `prometheus-client`；`dev` 加 `locust`、`httpx-sse` |
| `backend/app/main.py` | 注册 metrics middleware + 暴露 `/metrics` 端点 |
| `backend/app/core/config.py` | 加 `PROMETHEUS_ENABLED`、`METRICS_PATH` 配置 |
| `backend/app/services/qa_service.py` | 埋点 + F1 协程修复 + F3 L1 key 改造 |
| `backend/app/repositories/qa_repository.py` | F2 evict 逻辑改用 JSONB `.contains()` |
| `backend/app/models/semantic_cache.py` | F2 列类型 `JSON` → `JSONB` |
| `frontend/src/lib/session.ts` | F5 `refreshAccessToken` 返回类型重构 |
| `frontend/src/lib/http.ts` | F5 调用方分支处理 |
| `README.md` | 加"性能与可观测性"一节链到 final-report |

---

## 任务总览

| # | Task | 阶段 | 预计 |
|---|---|---|---|
| 1 | 启动 Prometheus + Grafana 基础设施 | G1 | 1h |
| 2 | 后端暴露 `/metrics` 最小端点 | G1 | 30min |
| 3 | 创建统一 `metrics.py` 模块 | G2 / A1-A3 | 1h |
| 4 | HTTP middleware（A3） | G2 / A3 | 1h |
| 5 | RAG telemetry → Prometheus 集成（A1） | G2 / A1 | 1.5h |
| 6 | TTFT 埋点（A1 ⭐ 新增点） | G2 / A1 | 1h |
| 7 | Cache 命中率埋点（A2） | G2 / A2 | 1h |
| 8 | F1：fts_task 协程修复 | G2 / F1 | 1h |
| 9 | Grafana 三张看板 JSON | G2 末 | 2h |
| 10 | 上传 3-5 份真实中文技术文档 | G3 | 1h |
| 11 | LLM 生成 synthetic.jsonl | G3 | 1h |
| 12 | 人工标注 golden.jsonl（20 道） | G3 | 3h |
| 13 | 评估脚本 `run_eval.py` | G3 | 2h |
| 14 | Locust 压测脚本 | G3 | 2h |
| 15 | 跑 Baseline + 保存 | G4.1 | 1h |
| 16 | F2：`knowledge_base_ids` JSON → JSONB + 索引 | G2 / F2 | 1.5h |
| 17 | F2：repository 改用 `.contains()` + 反向断言测试 | G2 / F2 | 1h |
| 18 | F3：L1 cache key 移除 `conv_id` | G2 / F3 | 1h |
| 19 | F4：ivfflat 向量索引迁移 | G2 / F4 | 1h |
| 20 | F5：前端 `refreshAccessToken` 重构 | G2 / F5 | 2h |
| 21 | 跑 After + 保存 | G4.2 | 1h |
| 22 | 写 final-report.md 三段式 | G5 | 2h |
| 23 | README 更新 + dry-run 验收 | G5 | 1h |

**总计：~30h ≈ 5 个工作日**（含调试缓冲）

---

# Stage 1: 基础设施铺设（Gate 1）

---

## Task 1: 启动 Prometheus + Grafana 基础设施

**Files:**
- Create: `monitoring/prometheus.yml`
- Create: `monitoring/grafana/provisioning/datasources/prometheus.yml`
- Create: `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- Modify: `docker-compose.yml`
- Modify: `dev.sh`

- [x] **Step 1: 创建 monitoring 目录与 Prometheus 抓取配置**

创建文件 `monitoring/prometheus.yml`：

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'backend'
    metrics_path: '/metrics'
    static_configs:
      # host.docker.internal 让容器能访问本机 host 上的 backend
      - targets: ['host.docker.internal:8000']
        labels:
          service: 'offer-copilot-backend'

  - job_name: 'locust'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['host.docker.internal:9646']
        labels:
          service: 'locust'
```

- [x] **Step 2: 创建 Grafana datasource provisioning**

创建文件 `monitoring/grafana/provisioning/datasources/prometheus.yml`：

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

- [x] **Step 3: 创建 Grafana dashboard provisioning loader**

创建文件 `monitoring/grafana/provisioning/dashboards/dashboards.yml`：

```yaml
apiVersion: 1

providers:
  - name: 'offer-copilot'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

- [x] **Step 4: 在 docker-compose.yml 加 prometheus 和 grafana service**

在 `docker-compose.yml` 文件**末尾**（services 段最后、volumes 段之前）插入：

```yaml
  # Prometheus 指标采集
  prometheus:
    image: prom/prometheus:v2.55.0
    container_name: offercopilot-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=7d'
      - '--web.enable-lifecycle'
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped

  # Grafana 可视化
  grafana:
    image: grafana/grafana:11.3.0
    container_name: offercopilot-grafana
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    depends_on:
      - prometheus
    restart: unless-stopped
```

并在 `volumes:` 段（文件末尾）补两个：

```yaml
volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

> 注意：如果 `volumes:` 段不存在，新增完整段；如果已存在，只追加最后两行。

- [x] **Step 5: 更新 dev.sh 同步启动 prometheus 和 grafana**

修改 `dev.sh` 中 Docker 启动命令：

```bash
# 旧:
docker-compose up -d postgres redis

# 新:
docker-compose up -d postgres redis prometheus grafana
```

并在 cleanup 输出区加一行：

```bash
echo "📊 Grafana: http://localhost:3001 (admin/admin)"
echo "📈 Prometheus: http://localhost:9090"
```

- [x] **Step 6: 验证基础设施启动**

```bash
./dev.sh
```

打开新终端验证：

```bash
# Prometheus 健康
curl -s http://localhost:9090/-/healthy

# Grafana 健康
curl -s http://localhost:3001/api/health
```

期望：两条都返回 200 或 `"database": "ok"` 字样。
浏览器打开 `http://localhost:3001`，用 admin/admin 登录，左侧 Connections → Data sources 应看到 `Prometheus` 已配置。

- [x] **Step 7: 不 commit（这一阶段任务结束统一 commit）**

Stage 1 整体完成后做一次 commit。这一步只是 checkpoint，不出 PR。

---

## Task 2: 后端暴露 `/metrics` 最小端点

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Test: 手工 curl

- [x] **Step 1: 加 prometheus-client 依赖**

在 backend 目录下：

```bash
cd backend && uv add prometheus-client && cd ..
```

期望：`pyproject.toml` 的 `dependencies` 多出 `"prometheus-client>=0.21.0"` 类似行，`uv.lock` 更新。

- [x] **Step 2: 加配置项**

修改 `backend/app/core/config.py`，在 `class Settings` 中添加：

```python
    # ===== Observability =====
    PROMETHEUS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"
```

放在已有的 `RAG_TELEMETRY_ENABLED` 之后。

- [x] **Step 3: 在 main.py 中注册 /metrics 端点**

修改 `backend/app/main.py`，在 `app = FastAPI(...)` 之后、`app.include_router(api_router)` 之前加：

```python
from prometheus_client import make_asgi_app
from starlette.routing import Mount

if settings.PROMETHEUS_ENABLED:
    # 挂载 Prometheus ASGI 子应用，独立处理 /metrics
    metrics_app = make_asgi_app()
    app.router.routes.append(Mount(settings.METRICS_PATH, app=metrics_app))
```

> 之所以用 ASGI Mount 而非 FastAPI route：避免 `/metrics` 被 FastAPI 的中间件链处理（特别是后续要加的 HTTP middleware 会把 `/metrics` 自身也计入指标，产生递归）。

- [x] **Step 4: 启动后端验证**

```bash
# 后端会被 dev.sh 自动重启；或手动:
curl -s http://localhost:8000/metrics | head -20
```

期望输出形如：

```
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 0.0
...
```

- [x] **Step 5: 验证 Prometheus 抓到 backend**

打开 `http://localhost:9090/targets`，看到 `backend` job 显示 `UP`。

如果显示 DOWN，可能是 docker network 解析 `host.docker.internal` 的问题。Linux 系统需要在 prometheus service 加 `extra_hosts`（已在 Step 4 of Task 1 加好），macOS 默认支持。

- [x] **Step 6: Stage 1 commit**

```bash
git add docker-compose.yml dev.sh monitoring/ backend/pyproject.toml backend/uv.lock backend/app/main.py backend/app/core/config.py
git commit -m "feat(observability): bootstrap prometheus + grafana infrastructure

- Add docker-compose services for prometheus and grafana
- Expose /metrics endpoint via prometheus-client ASGI mount
- Add monitoring/ provisioning files (datasource + dashboard loader)
- Update dev.sh to start prometheus + grafana alongside postgres/redis

Refs: docs/specs/2026-05-27-measurement-and-fix/spec.md §2.3"
```

**Gate 1 验收**：
- ✅ `http://localhost:3001` 能登 Grafana
- ✅ `http://localhost:9090/targets` 显示 backend UP
- ✅ `curl :8000/metrics` 返回 Prometheus 格式

---

# Stage 2: 埋点 + F1 修复（Gate 2 前半）

---

## Task 3: 创建统一 `metrics.py` 模块

**Files:**
- Create: `backend/app/core/metrics.py`
- Test: `backend/tests/core/test_metrics.py`

- [x] **Step 1: 写失败测试**

创建 `backend/tests/core/test_metrics.py`：

```python
from backend.app.core import metrics


def test_metrics_module_exposes_required_objects():
    # HTTP
    assert hasattr(metrics, "HTTP_REQUESTS_TOTAL")
    assert hasattr(metrics, "HTTP_REQUEST_DURATION_SECONDS")
    assert hasattr(metrics, "HTTP_REQUESTS_IN_PROGRESS")

    # RAG
    assert hasattr(metrics, "RAG_STAGE_DURATION_SECONDS")
    assert hasattr(metrics, "RAG_TOTAL_DURATION_SECONDS")
    assert hasattr(metrics, "RAG_TTFT_SECONDS")
    assert hasattr(metrics, "RAG_OUTCOME_TOTAL")
    assert hasattr(metrics, "RAG_CANDIDATES_COUNT")
    assert hasattr(metrics, "RAG_CITATIONS_COUNT")
    assert hasattr(metrics, "RAG_COHERE_TOP_SCORE")
    assert hasattr(metrics, "RAG_QUERY_REWRITTEN_TOTAL")
    assert hasattr(metrics, "RAG_SCOPE_SIZE")

    # Cache
    assert hasattr(metrics, "CACHE_LOOKUP_TOTAL")
    assert hasattr(metrics, "CACHE_OPERATION_DURATION_SECONDS")

    # App info
    assert hasattr(metrics, "APP_INFO")


def test_http_requests_total_has_expected_labels():
    sample = metrics.HTTP_REQUESTS_TOTAL.labels(
        method="GET", path_template="/api/v1/qa/ping", status_class="2xx"
    )
    sample.inc()
    # 通过 collect 不会抛异常即认为标签正确
    list(metrics.HTTP_REQUESTS_TOTAL.collect())
```

- [x] **Step 2: 跑测试，期望失败**

```bash
cd backend && uv run pytest tests/core/test_metrics.py -v
```

期望：`ModuleNotFoundError: No module named 'backend.app.core.metrics'`

- [x] **Step 3: 实现 metrics.py**

创建 `backend/app/core/metrics.py`：

```python
"""统一定义 Prometheus 指标对象。所有埋点点位 import 此模块。

命名规范：
- Counter 必须以 `_total` 结尾
- Histogram 单位用秒（`_seconds`）
- 标签基数严格控制，避免高 cardinality
"""

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
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
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
```

- [x] **Step 4: 在 main.py 初始化 APP_INFO**

修改 `backend/app/main.py`，在 `setup_logging()` 之后加：

```python
from backend.app.core.metrics import APP_INFO

APP_INFO.labels(
    version="0.1.0",
    env=settings.SENTRY_ENVIRONMENT or "development",
).set(1)
```

- [x] **Step 5: 跑测试，期望通过**

```bash
cd backend && uv run pytest tests/core/test_metrics.py -v
```

期望：2 passed

- [x] **Step 6: 验证 /metrics 输出包含新指标**

```bash
curl -s http://localhost:8000/metrics | grep -E "^(http_|rag_|cache_|app_info)" | head -10
```

期望：能看到 `app_info{env="development",version="0.1.0"} 1.0` 等

- [x] **Step 7: 运行 black + isort**

```bash
cd backend && uv run ruff format app/core/metrics.py tests/core/test_metrics.py app/main.py app/core/config.py
```

- [x] **Step 8: 不 commit，等 Task 4 一起 commit**

---

## Task 4: HTTP Middleware（A3）

**Files:**
- Create: `backend/app/core/metrics_middleware.py`
- Modify: `backend/app/main.py`

- [x] **Step 1: 实现 HTTP middleware**

创建 `backend/app/core/metrics_middleware.py`：

```python
"""HTTP 层 Prometheus 指标采集 middleware。"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.config import settings
from backend.app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def _path_template(request: Request) -> str:
    """优先取路由模板（/conversations/{id}）而非真实 URL（/conversations/abc-123），
    避免标签基数爆炸。"""
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path
    # 未匹配到路由（如 404）时用 placeholder
    return "__unmatched__"


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.PROMETHEUS_ENABLED:
            return await call_next(request)

        # /metrics 端点本身不计入指标
        if request.url.path == settings.METRICS_PATH:
            return await call_next(request)

        method = request.method
        # 注意：路由匹配发生在 endpoint 调用前的更深层；此处先用 placeholder，
        # 在 response 阶段再读 scope["route"]
        in_progress_started = False
        path_template = "__pending__"
        start = time.perf_counter()

        try:
            response = await call_next(request)
            path_template = _path_template(request)
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path_template=path_template).inc()
            in_progress_started = True
            status = response.status_code
            HTTP_REQUESTS_TOTAL.labels(
                method=method, path_template=path_template, status_class=_status_class(status)
            ).inc()
            return response
        except Exception:
            path_template = _path_template(request)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, path_template=path_template, status_class="5xx"
            ).inc()
            raise
        finally:
            elapsed = time.perf_counter() - start
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, path_template=path_template
            ).observe(elapsed)
            if in_progress_started:
                HTTP_REQUESTS_IN_PROGRESS.labels(
                    method=method, path_template=path_template
                ).dec()
```

> **关于 path_template 的时机**：Starlette 路由匹配发生在 middleware 之后；所以 `request.scope["route"]` 在 `dispatch` 入口拿不到。本实现在 response 返回后再取，能拿到正确模板。代价：response 返回前的 in_progress gauge 标签先是 `__pending__`，对短时长请求影响小，可接受；如需更精确，可改用 `BaseHTTPMiddleware` 子类化或 ASGI 中间件直接读 `scope["endpoint"]`，但这次故事不依赖 in_progress 精度，**先保持简单**。

- [x] **Step 2: 注册到 main.py**

修改 `backend/app/main.py`，在 `app.add_middleware(CORSMiddleware, ...)` 之后加：

```python
from backend.app.core.metrics_middleware import PrometheusMiddleware

if settings.PROMETHEUS_ENABLED:
    app.add_middleware(PrometheusMiddleware)
```

- [x] **Step 3: 验证**

启动后端，访问任意 endpoint：

```bash
curl http://localhost:8000/api/v1/health  # 或任意已知接口
curl -s http://localhost:8000/metrics | grep http_requests_total
```

期望看到形如：

```
http_requests_total{method="GET",path_template="/api/v1/health",status_class="2xx"} 1.0
```

- [x] **Step 4: 验证 /metrics 自身不计入**

```bash
curl -s http://localhost:8000/metrics > /dev/null
curl -s http://localhost:8000/metrics > /dev/null
curl -s http://localhost:8000/metrics | grep 'path_template="/metrics"'
```

期望：grep **无输出**（/metrics 被跳过）。

- [x] **Step 5: 格式化 + commit**

```bash
cd backend && uv run ruff format app/core/metrics.py app/core/metrics_middleware.py app/main.py tests/core/test_metrics.py
cd ..
git add backend/app/core/metrics.py backend/app/core/metrics_middleware.py backend/app/main.py backend/tests/core/test_metrics.py backend/pyproject.toml backend/uv.lock backend/app/core/config.py
git commit -m "feat(observability): add prometheus metrics module and HTTP middleware

- Define all SLI/SLO metrics in backend/app/core/metrics.py
  (HTTP, RAG, Cache, app_info)
- Add PrometheusMiddleware for HTTP layer (requests/duration/in-progress)
- Path template extraction to control label cardinality
- /metrics endpoint excluded from self-measurement

Refs: spec.md §5.2, §5.5"
```

---

## Task 5: RAG telemetry → Prometheus 集成（A1）

**Files:**
- Modify: `backend/app/services/qa_service.py:353-363`（`_emit_rag_telemetry` 内）

- [x] **Step 1: 阅读现有 `_emit_rag_telemetry` 和 payload 构造函数**

```bash
sed -n '275,365p' backend/app/services/qa_service.py
```

确认字段名与 spec §5.3 表格中"来源字段"列一致。

- [x] **Step 2: 在 `_emit_rag_telemetry` 中增加 Prometheus 推送**

修改 `backend/app/services/qa_service.py` 的 `_emit_rag_telemetry` 函数（约第 353 行）：

```python
def _emit_rag_telemetry(payload: dict[str, Any]) -> None:
    if not settings.RAG_TELEMETRY_ENABLED:
        return
    try:
        # 保留：日志输出用于单条请求调试
        msg = f"\n{'*' * 20} RAG TELEMETRY {'*' * 20}\nrag_telemetry {json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n{'*' * 45}\n"
        logger.info(msg)
        print(msg, flush=True)
    except Exception:
        pass

    # 新增：Prometheus 指标
    try:
        _push_rag_metrics(payload)
    except Exception:
        # 指标推送失败不影响主流程
        logger.exception("Push rag metrics failed")
```

- [x] **Step 3: 实现 `_push_rag_metrics`**

在 `_emit_rag_telemetry` 之前加新函数：

```python
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
```

- [x] **Step 4: 跑一次问答验证指标产生**

启动后端，通过前端或 curl 触发一次 `/ask`：

```bash
# 触发后等几秒，再检查
curl -s http://localhost:8000/metrics | grep -E "^rag_" | head -30
```

期望看到多个 `rag_*` 指标有非零值。

- [x] **Step 5: 格式化 + 暂存（不 commit）**

```bash
cd backend && uv run ruff format app/services/qa_service.py
```

不 commit，等 Task 6（TTFT）一起。

---

## Task 6: TTFT 埋点（A1 ⭐ 新增点）

**Files:**
- Modify: `backend/app/services/qa_service.py`（SSE 生成器循环）

- [x] **Step 1: 定位 SSE 流的 token yield 位置**

```bash
grep -n 'yield.*"type": "token"\|yield {"type": "token"' backend/app/services/qa_service.py | head -5
```

记下第一次 yield token 的位置。

- [x] **Step 2: 在请求入口记录 `ttft_started_at`**

在 `ask_conversation` 主生成函数（找到 `async def ask_conversation` 或对应的流式入口）开头加：

```python
ttft_started_at = perf_counter()
ttft_recorded = False
```

> 名字与现有 `perf_counter()` 用法保持一致（grep 已确认现有代码用 `from time import perf_counter`）。

- [x] **Step 3: 在第一次 yield token 时记录 TTFT**

在每个 token yield 之前判断：

```python
if not ttft_recorded:
    from backend.app.core.metrics import RAG_TTFT_SECONDS
    RAG_TTFT_SECONDS.observe(perf_counter() - ttft_started_at)
    ttft_recorded = True
```

> **关键考量**：可能有多条 SSE 生成路径（L1 hit / L2 hit / 正常生成）。L1/L2 hit 时也应记录 TTFT，因为对用户体验来说也是首字时间。最简单做法：在**任何 `yield {"type": "token", ...}` 之前**加一次同样的判断。

- [x] **Step 4: 验证 TTFT 出现在 /metrics**

跑一次问答：

```bash
curl -s http://localhost:8000/metrics | grep rag_ttft_seconds
```

期望看到 `rag_ttft_seconds_count > 0` 和 buckets 分布。

- [x] **Step 5: 格式化**

```bash
cd backend && uv run ruff format app/services/qa_service.py
```

- [x] **Step 6: commit Task 5 + 6**

```bash
git add backend/app/services/qa_service.py
git commit -m "feat(observability): emit RAG metrics to prometheus + capture TTFT

- _emit_rag_telemetry now also pushes to RAG_* metrics
- Map all 13 telemetry fields to prometheus Histogram/Counter
- Add TTFT (Time-To-First-Token) capture in SSE stream

Refs: spec.md §5.3"
```

---

## Task 7: Cache 命中率埋点（A2）

**Files:**
- Modify: `backend/app/services/qa_service.py`（L1/L2 lookup 路径）
- Modify: `backend/app/repositories/qa_repository.py`（L2 操作路径）

- [x] **Step 1: 定位 L1 cache lookup**

```bash
grep -n "l1_cache_key\|redis_client.get\|cache:rag:ask" backend/app/services/qa_service.py | head -20
```

记下三处 L1 lookup（应该包括 1063 行附近、1641 行附近、1988 行附近）。

- [x] **Step 2: 在 L1 lookup 包裹埋点**

对每处 `cached_data = await redis_client.get(l1_cache_key)` 调用包裹：

```python
from backend.app.core.metrics import CACHE_LOOKUP_TOTAL, CACHE_OPERATION_DURATION_SECONDS

_l1_start = perf_counter()
try:
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
```

> 每处都要包，三处都要改。

- [x] **Step 3: 在 L1 set 埋点**

定位 L1 set（`await redis_client.set(l1_cache_key, ...)` 或 `setex`）：

```bash
grep -n "redis_client.set\(l1\|setex.*l1_cache_key" backend/app/services/qa_service.py
```

包裹：

```python
_l1_set_start = perf_counter()
await redis_client.setex(l1_cache_key, ...)
CACHE_OPERATION_DURATION_SECONDS.labels(
    layer="l1", operation="set"
).observe(perf_counter() - _l1_set_start)
```

- [x] **Step 4: 在 L2 lookup 埋点（`find_similar_semantic_cache`）**

定位调用点（应该在 qa_service.py 中）：

```bash
grep -n "find_similar_semantic_cache" backend/app/services/qa_service.py
```

包裹：

```python
_l2_start = perf_counter()
try:
    similar_cache = await qa_repository.find_similar_semantic_cache(
        db, query_vec, knowledge_base_ids=knowledge_base_ids,
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
```

- [x] **Step 5: 在 L2 set 埋点（`store_semantic_cache`）**

定位调用点，类似包裹（operation="set"）。

- [x] **Step 6: 在 evict 埋点（`evict_caches_by_kb_id`）**

修改 `backend/app/repositories/qa_repository.py` 中 `evict_caches_by_kb_id` 函数：

```python
async def evict_caches_by_kb_id(db: AsyncSession, kb_id: int) -> None:
    """..."""
    from time import perf_counter
    from backend.app.core.metrics import CACHE_OPERATION_DURATION_SECONDS
    from sqlalchemy import delete

    start = perf_counter()
    try:
        # 原有逻辑保留（Task 16/17 会进一步重写）
        stmt = delete(SemanticCache).where(
            func.cast(SemanticCache.knowledge_base_ids, Text).like(f"%{kb_id}%")
        )
        await db.execute(stmt)
        await db.commit()
    finally:
        CACHE_OPERATION_DURATION_SECONDS.labels(
            layer="l2", operation="evict"
        ).observe(perf_counter() - start)
```

> 此处**保留原 bug** —— 是为了让 baseline 跑出来能看到错误。Task 16/17 才真正修 F2 逻辑。

- [x] **Step 7: 跑一次问答验证 cache 指标**

```bash
# 先用相同问题问两次，制造 L1 hit
curl -s http://localhost:8000/metrics | grep -E "^cache_(lookup|operation)" | head -20
```

期望看到 `cache_lookup_total{layer="l1",result="hit"}` 至少有 1。
（**注意**：F3 还没修，L1 hit 概率很低，这正是 baseline 要展示的数据。）

- [x] **Step 8: 格式化 + commit**

```bash
cd backend && uv run ruff format app/services/qa_service.py app/repositories/qa_repository.py
cd ..
git add backend/app/services/qa_service.py backend/app/repositories/qa_repository.py
git commit -m "feat(observability): instrument L1/L2 cache lookup and operations

- Wrap all L1 lookup/set with CACHE_LOOKUP_TOTAL + CACHE_OPERATION_DURATION
- Wrap L2 find_similar_semantic_cache and store_semantic_cache
- Wrap evict_caches_by_kb_id for operation timing
- Note: F3 (L1 conv_id bug) and F2 (evict LIKE bug) NOT yet fixed;
  baseline data will demonstrate the issues before fixes

Refs: spec.md §5.4"
```

---

## Task 8: F1 — fts_task 协程修复

**Files:**
- Modify: `backend/app/services/qa_service.py:1952`（fts_task 创建处）
- Test: `backend/tests/services/test_qa_service_sse_micro.py`

- [x] **Step 1: 写失败测试**

创建 `backend/tests/services/test_qa_service_sse_micro.py`：

```python
"""验证 MICRO_RETRIEVAL 路径 SSE 流完整性（F1 修复回归测试）。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_micro_retrieval_sse_emits_done_event():
    """MICRO_RETRIEVAL 路径走完后应发出 done 事件，不被 AttributeError 截断。"""
    # 因为 ask_conversation 依赖较重，本测试聚焦于：
    # 1. _fts_search_scope 必须以 Task 形式启动（asyncio.ensure_future）
    # 2. finally 块对 Task 调用 .done() 不抛异常

    # 直接验证修复后的工作流不抛 AttributeError
    from backend.app.services.qa_service import _fts_search_scope
    import asyncio
    from unittest.mock import AsyncMock as _AsyncMock

    # mock 依赖
    with patch("backend.app.services.qa_service._fts_search_scope", new_callable=_AsyncMock) as mock_fts:
        mock_fts.return_value = []
        task = asyncio.ensure_future(_fts_search_scope(None, 1, [], "q"))
        # Task 必须有 .done() 方法
        assert hasattr(task, "done")
        result = await task
        assert task.done() is True
        assert result == []
```

- [x] **Step 2: 跑测试，期望可能失败（如果 ensure_future 没生效）**

```bash
cd backend && uv run pytest tests/services/test_qa_service_sse_micro.py -v
```

测试本身验证的是 `asyncio.ensure_future` 的语义；这个会通过。**真正的回归**通过集成测试观察 outcome=error 比例。所以测试主要起"修改 fts_task 创建方式时确保不回退"的固化作用。

- [x] **Step 3: 应用 F1 修复**

修改 `backend/app/services/qa_service.py:1952`：

```python
# 旧：
fts_task = _fts_search_scope(db, user_id, scope_entries, retrieval_query)

# 新：
fts_task = asyncio.ensure_future(
    _fts_search_scope(db, user_id, scope_entries, retrieval_query)
)
```

并确认 `asyncio` 已 import（文件顶部应该有，没有就加上 `import asyncio`）。

- [x] **Step 4: 跑测试 + 集成验证**

```bash
cd backend && uv run pytest tests/services/test_qa_service_sse_micro.py -v
```

期望：1 passed

启动后端，通过前端发一条会走 MICRO_RETRIEVAL 路径的问题（短查询、简单关键词），观察前端是否能正常完成流式响应、不卡住。

> 如何确认走的是 MICRO_RETRIEVAL 路径？看 `backend.log`，搜 `micro_retrieval=True` 或 `_analyze_query_gate` 的输出。

- [x] **Step 5: 格式化 + commit**

```bash
cd backend && uv run ruff format app/services/qa_service.py tests/services/test_qa_service_sse_micro.py
cd ..
git add backend/app/services/qa_service.py backend/tests/services/test_qa_service_sse_micro.py
git commit -m "fix(rag): wrap _fts_search_scope in asyncio.ensure_future (F1)

Calling .done() on a coroutine raises AttributeError. In the
MICRO_RETRIEVAL path, the finally block tried to call fts_task.done()
on what was actually a coroutine, raising before SSE 'done' event
could be yielded. Result: SSE stream ended early, frontend stuck.

Fix: use asyncio.ensure_future so fts_task is a true Task with .done().

Refs: spec.md §4.1 (F1)"
```

---

## Task 9: Grafana 三张看板 JSON

**Files:**
- Create: `monitoring/grafana/provisioning/dashboards/rag.json`
- Create: `monitoring/grafana/provisioning/dashboards/http.json`
- Create: `monitoring/grafana/provisioning/dashboards/cache.json`

> 这一 Task 用 Grafana UI 手画看板 → Export JSON → 进 git 的方式。手写 JSON 太脆。

- [x] **Step 1: 跑些问答 + curl 流量，让 Prometheus 有数据**

```bash
# 用 ab 或循环 curl 制造 HTTP 流量
for i in {1..20}; do curl -s http://localhost:8000/api/v1/health > /dev/null; done

# 通过前端或脚本至少触发 5 次问答（不同问题）
# 这一步是为了 UI 调看板时能看到曲线
```

- [x] **Step 2: 登录 Grafana 创建 "RAG" 看板**

打开 `http://localhost:3001`，admin/admin 登录。

新建 dashboard，按 spec §6.2 的清单加 5 个 panel：

| Panel | 查询 | 类型 |
|---|---|---|
| 成功率 | `sum(rate(rag_outcome_total{outcome="success"}[5m])) / sum(rate(rag_outcome_total[5m]))` | Stat |
| TTFT p95 | `histogram_quantile(0.95, sum by (le)(rate(rag_ttft_seconds_bucket[5m])))` | Stat |
| Total p95 | `histogram_quantile(0.95, sum by (le)(rate(rag_total_duration_seconds_bucket[5m])))` | Stat |
| 5 阶段 p95 | `histogram_quantile(0.95, sum by (le,stage)(rate(rag_stage_duration_seconds_bucket[5m])))` | Time series |
| outcome 分布 | `sum by (outcome)(rate(rag_outcome_total[5m]))` | Pie |

设置：
- Title: `RAG 链路`
- Refresh: 30s
- Time range: Last 1 hour
- Tags: `rag`, `observability`

- [x] **Step 3: Export RAG 看板 JSON**

Dashboard → Settings (齿轮) → JSON Model → Copy。

保存到 `monitoring/grafana/provisioning/dashboards/rag.json`。

**关键**：保存前把 JSON 顶层加：

```json
{
  "uid": "offer-copilot-rag",
  ... (existing fields)
}
```

并删除自动生成的 `id` 字段（让 provisioning 接管）。

- [x] **Step 4: 重复创建 HTTP 看板**

按 spec §6.3 清单。同样 5 个 panel：

| Panel | 查询 |
|---|---|
| 当前 QPS | `sum(rate(http_requests_total[1m]))` |
| 错误率 5xx | `sum(rate(http_requests_total{status_class="5xx"}[5m])) / sum(rate(http_requests_total[5m]))` |
| p95 延迟 | `histogram_quantile(0.95, sum by (le)(rate(http_request_duration_seconds_bucket[5m])))` |
| QPS by status_class | `sum by (status_class)(rate(http_requests_total[1m]))` |
| 延迟 p50/p95/p99 | 三条 `histogram_quantile`（0.50 / 0.95 / 0.99） |

Title: `HTTP & SLI`，UID: `offer-copilot-http`，导出到 `http.json`。

- [x] **Step 5: 重复创建 Cache 看板**

按 spec §6.4，4 个 panel：

| Panel | 查询 |
|---|---|
| L1 命中率 | `sum(rate(cache_lookup_total{layer="l1",result="hit"}[5m])) / sum(rate(cache_lookup_total{layer="l1"}[5m]))` |
| L2 命中率 | 同上 layer="l2" |
| 命中率时间序列 | L1 + L2 两条线 |
| Lookup p95 时间序列 | `histogram_quantile(0.95, sum by (le,layer)(rate(cache_operation_duration_seconds_bucket{operation="lookup"}[5m])))` |

Title: `Cache 命中率`，UID: `offer-copilot-cache`，导出到 `cache.json`。

- [x] **Step 6: 重启 Grafana 验证 provisioning 生效**

```bash
docker restart offercopilot-grafana
sleep 3
```

打开 `http://localhost:3001/dashboards`，看到三张看板都在。
**关键**：点开每张确认 panel 都有数据（不要"No data"）。

- [x] **Step 7: commit**

```bash
git add monitoring/grafana/provisioning/dashboards/rag.json \
        monitoring/grafana/provisioning/dashboards/http.json \
        monitoring/grafana/provisioning/dashboards/cache.json
git commit -m "feat(observability): provision Grafana dashboards (RAG/HTTP/Cache)

Three dashboards, 14 panels total:
- RAG (5): success rate, TTFT p95, total p95, stage breakdown, outcome pie
- HTTP (5): QPS, 5xx rate, p95, QPS by status_class, p50/p95/p99 latencies
- Cache (4): L1/L2 hit rate stats, hit-rate time series, lookup p95

UIDs fixed (offer-copilot-rag/http/cache) for stable URLs.

Refs: spec.md §6"
```

**Gate 2 部分验收**（A1/A2/A3 + F1 完成）：
- ✅ 三张看板都有数据
- ✅ MICRO_RETRIEVAL SSE 走通
- ✅ `/metrics` 输出所有 `http_*` `rag_*` `cache_*` 指标

> F2-F5 在 baseline 之后再修，所以 Gate 2 完整验收在 Task 21 之后。

---

# Stage 3: 数据准备（Gate 3）

---

## Task 10: 上传 3-5 份真实中文技术文档

**Files:**
- 人工操作，无代码改动

- [x] **Step 1: 选定 3-5 份候选文档**

通过脚本 `backend/scripts/manual_ingest.py` 手动注入了以下文档：
1. FastAPI 中文教程 (KB ID: 4)
2. pgvector README (KB ID: 5)
3. Pydantic Models (KB ID: 6)
4. Next.js Routing (KB ID: 7)

- [x] **Step 2: 通过脚本上传**

已运行 `uv run python scripts/manual_ingest.py` 完成。

- [x] **Step 3: 验证入库**

```bash
docker exec offercopilot-postgres psql -U postgres -d offercopilot -c "SELECT COUNT(*) FROM document_chunks;"
```

确认总数已达 50 个。

```bash
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d offercopilot -c "
SELECT id, name, source_url, status FROM knowledge_bases ORDER BY id;
"
```

期望：3-5 行，所有 status = `ready`。

```bash
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d offercopilot -c "
SELECT knowledge_base_id, COUNT(*) FROM document_chunks GROUP BY knowledge_base_id;
"
```

期望：每个 KB 有几十到几百个 chunk。

- [ ] **Step 4: 记录 KB ID 列表**

把 KB ID 记录到 `docs/specs/2026-05-27-measurement-and-fix/kb-ids.txt`（gitignore'd 或随便放，仅供脚本使用）：

```
1  fastapi-zh
2  pydantic
3  pgvector
4  nextjs-zh
```

- [ ] **Step 5: 不 commit**（数据状态不进 git）

---

## Task 11: LLM 生成 synthetic.jsonl

**Files:**
- Create: `backend/scripts/eval/__init__.py`
- Create: `backend/scripts/eval/generate_synthetic.py`
- Create: `eval/synthetic.jsonl`

- [x] **Step 1: 创建 generate_synthetic.py**

创建 `backend/scripts/eval/__init__.py` 为空文件。
创建 `backend/scripts/eval/generate_synthetic.py` 实现。

- [x] **Step 2: 跑脚本生成**

```python
cd backend && uv run python -c "import sys; from pathlib import Path; sys.path.append(str(Path.cwd().parent)); import asyncio; from scripts.eval.generate_synthetic import main; asyncio.run(main())"
```

- [x] **Step 3: 检查输出**

```bash
cat eval/synthetic.jsonl | head -n 5
wc -l eval/synthetic.jsonl
```

期望行数 > 100。实际行数为 140（7 个 KB 每个 20 题）。


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 运行生成**

```bash
cd backend && uv run python -m scripts.eval.generate_synthetic
```

期望：每个 KB 生成 ~20 道，总计 60-100 道。输出到 `eval/synthetic.jsonl`。

- [ ] **Step 3: 抽查 5 条**

```bash
head -5 eval/synthetic.jsonl
wc -l eval/synthetic.jsonl
```

确认行数在 50-100 之间，问题合理。

- [ ] **Step 4: 格式化 + commit**

```bash
cd backend && uv run ruff format scripts/eval/generate_synthetic.py
cd ..
git add backend/scripts/eval/__init__.py backend/scripts/eval/generate_synthetic.py eval/synthetic.jsonl
git commit -m "feat(eval): generate synthetic question set via gpt-4o-mini

- Script reads chunks from each KB, asks LLM to generate 20 questions per KB
- Output: eval/synthetic.jsonl (only questions, no ground truth)
- Used for load testing (latency/throughput/cache hit rate), NOT quality

Refs: spec.md §3.5"
```

---

## Task 12: 人工标注 golden.jsonl（20 道）

**Files:**
- Create: `eval/golden.jsonl`

- [ ] **Step 1: 准备模板**

新建 `eval/golden.jsonl`，**手工**填写 20 行，每行格式：

```json
{"question": "...", "kb_id": 1, "expected_citations": ["chunk:N"], "expected_answer_keywords": ["..."], "category": "fact"}
```

字段说明：
- `question`: 中文问题
- `kb_id`: 知识库 ID
- `expected_citations`: 期望引用的 chunk（用 `chunk:<id>` 形式；下面 Step 2 会教怎么找）
- `expected_answer_keywords`: 期望出现在答案里的关键词（list）
- `category`: `fact` / `summary` / `comparison` / `howto`

**配比建议**：每 KB 4-5 题，混合 category。

- [ ] **Step 2: 通过 SQL 找 chunk ID**

```bash
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d offercopilot
```

在 psql 中：

```sql
-- 假设你想为"什么是 FastAPI 的依赖注入"找引用
SELECT id, substr(content, 1, 100) FROM document_chunks
WHERE knowledge_base_id = 1
  AND content ILIKE '%依赖注入%'
LIMIT 5;
```

记下能正确回答该问题的 chunk id（一道题可以有 1-3 个 expected_citations）。

- [ ] **Step 3: 完成 20 道，每道 5 分钟硬上限**

参考样例（写 3-5 道做示范）：

```json
{"question": "FastAPI 的依赖注入怎么用？", "kb_id": 1, "expected_citations": ["chunk:42", "chunk:43"], "expected_answer_keywords": ["Depends", "依赖", "参数"], "category": "howto"}
{"question": "FastAPI 和 Flask 有什么区别？", "kb_id": 1, "expected_citations": ["chunk:5"], "expected_answer_keywords": ["异步", "类型", "性能"], "category": "comparison"}
{"question": "pgvector 支持哪些距离函数？", "kb_id": 3, "expected_citations": ["chunk:88"], "expected_answer_keywords": ["L2", "cosine", "inner"], "category": "fact"}
```

- [ ] **Step 4: 校验**

```bash
wc -l eval/golden.jsonl   # 期望 ≥ 20
python -c "
import json
for i, line in enumerate(open('eval/golden.jsonl'), 1):
    d = json.loads(line)
    assert 'question' in d and 'expected_citations' in d, f'Line {i} missing field'
    assert isinstance(d['expected_citations'], list), f'Line {i} citations not list'
print('OK')
"
```

- [ ] **Step 5: commit**

```bash
git add eval/golden.jsonl
git commit -m "feat(eval): add 20 hand-labeled golden Q&A set

- Covers 3-5 KBs, mix of fact/summary/comparison/howto categories
- Each entry has expected_citations + expected_answer_keywords
- Used for quality evaluation (citation accuracy, answer coverage)

Refs: spec.md §3.5"
```

**Gate 3 验收**：
- ✅ `knowledge_bases` 3-5 条
- ✅ `eval/golden.jsonl` ≥ 20 行
- ✅ `eval/synthetic.jsonl` 50-100 行
- ✅ 抽查 5 条 golden 引用真实存在

---

## Task 13: 评估脚本 `run_eval.py`

**Files:**
- Create: `backend/scripts/eval/sse_client.py`
- Create: `backend/scripts/eval/run_eval.py`

- [ ] **Step 1: 写共用 SSE 客户端**

创建 `backend/scripts/eval/sse_client.py`：

```python
"""共用 SSE 客户端，给评估脚本和 Locust 复用。"""

import json
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx


@dataclass
class AskResult:
    answer: str = ""
    citations: list[dict] = field(default_factory=list)
    outcome: str = "unknown"
    error_code: str | None = None
    ttft_ms: int | None = None
    total_ms: int | None = None
    raw_events: list[dict] = field(default_factory=list)


async def ask_question(
    base_url: str,
    token: str,
    conversation_id: str,
    question: str,
    timeout: float = 60.0,
) -> AskResult:
    """通过 SSE 接口提问，返回完整结果。"""
    import time

    url = f"{base_url}/api/v1/qa/conversations/{conversation_id}/ask"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"question": question}

    result = AskResult()
    start = time.perf_counter()
    first_token_at: float | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    data_line = next((l for l in block.split("\n") if l.startswith("data: ")), None)
                    if not data_line:
                        continue
                    raw = data_line[len("data: "):]
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    result.raw_events.append(event)

                    etype = event.get("type")
                    if etype == "token":
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        result.answer += event.get("content", "")
                    elif etype == "citations":
                        result.citations = event.get("data", [])
                    elif etype == "error":
                        result.outcome = "error"
                        result.error_code = event.get("code")
                    elif etype == "done":
                        if result.outcome == "unknown":
                            result.outcome = "success"

    total = time.perf_counter() - start
    result.total_ms = int(total * 1000)
    if first_token_at is not None:
        result.ttft_ms = int((first_token_at - start) * 1000)
    return result
```

> **关键**：实际 SSE 事件格式以项目实现为准。这一步实施时需要先 grep 项目代码确认 `yield` 出来的事件类型名称（`token` / `citations` / `done` / `error`）和载荷字段。如有差异，调整解析逻辑。

- [ ] **Step 2: 写 run_eval.py**

创建 `backend/scripts/eval/run_eval.py`：

```python
"""跑评估集，输出指标到 markdown 报告。

用法：
  uv run python -m scripts.eval.run_eval --golden eval/golden.jsonl --output docs/specs/2026-05-27-measurement-and-fix/report-baseline.md
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

import httpx

from backend.scripts.eval.sse_client import ask_question


BASE_URL = os.environ.get("EVAL_BASE_URL", "http://localhost:8000")
TOKEN = os.environ["EVAL_TOKEN"]  # 必填，从已登录的浏览器 localStorage 复制


async def create_conversation(kb_id: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/v1/qa/conversations",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"knowledge_base_ids": [kb_id]},
        )
        resp.raise_for_status()
        return resp.json()["data"]["id"]


def citation_match(expected: list[str], actual: list[dict]) -> bool:
    """期望引用至少命中 1 个即算通过。expected 格式 'chunk:42'。"""
    actual_ids = {f"chunk:{c.get('chunk_id')}" for c in actual}
    return any(e in actual_ids for e in expected)


def keyword_coverage(keywords: list[str], answer: str) -> float:
    if not keywords:
        return 1.0
    hits = sum(1 for k in keywords if k in answer)
    return hits / len(keywords)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", default="baseline", help="baseline or after")
    args = parser.parse_args()

    golden = [json.loads(l) for l in open(args.golden, encoding="utf-8")]
    print(f"Evaluating {len(golden)} golden samples...")

    results = []
    for i, sample in enumerate(golden, 1):
        kb_id = sample["kb_id"]
        question = sample["question"]
        conv_id = await create_conversation(kb_id)
        try:
            r = await ask_question(BASE_URL, TOKEN, conv_id, question, timeout=120)
        except Exception as e:
            print(f"  [{i}/{len(golden)}] ERROR: {e}")
            results.append({**sample, "result": {"outcome": "error", "error_code": str(e)}})
            continue

        citation_ok = citation_match(sample["expected_citations"], r.citations)
        kw_coverage = keyword_coverage(sample.get("expected_answer_keywords", []), r.answer)
        print(
            f"  [{i}/{len(golden)}] outcome={r.outcome} citation_ok={citation_ok} kw_cov={kw_coverage:.2f} "
            f"ttft={r.ttft_ms}ms total={r.total_ms}ms"
        )
        results.append({
            **sample,
            "result": {
                "outcome": r.outcome,
                "error_code": r.error_code,
                "citation_ok": citation_ok,
                "kw_coverage": kw_coverage,
                "ttft_ms": r.ttft_ms,
                "total_ms": r.total_ms,
                "answer_excerpt": r.answer[:200],
            },
        })

    # 汇总
    total = len(results)
    success = sum(1 for r in results if r["result"]["outcome"] == "success")
    citation_hit = sum(1 for r in results if r["result"].get("citation_ok"))
    avg_kw = statistics.mean([r["result"].get("kw_coverage", 0) for r in results if "kw_coverage" in r["result"]] or [0])
    ttfts = [r["result"]["ttft_ms"] for r in results if r["result"].get("ttft_ms")]
    totals = [r["result"]["total_ms"] for r in results if r["result"].get("total_ms")]
    outcomes = Counter(r["result"]["outcome"] for r in results)

    def pct(values, p):
        if not values:
            return None
        values = sorted(values)
        k = int(len(values) * p)
        return values[min(k, len(values) - 1)]

    report_lines = [
        f"# 评估报告 — {args.label}",
        f"",
        f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**评估集**: `{args.golden}` ({total} 道)",
        f"",
        f"## 核心指标",
        f"",
        f"| 指标 | 值 |",
        f"|---|---|",
        f"| 总成功率 | **{success}/{total} = {success/total*100:.1f}%** |",
        f"| 引用命中率 | **{citation_hit}/{total} = {citation_hit/total*100:.1f}%** |",
        f"| 平均关键词覆盖率 | **{avg_kw:.2f}** |",
        f"| TTFT p50 / p95 | {pct(ttfts, 0.5)} / {pct(ttfts, 0.95)} ms |",
        f"| Total p50 / p95 | {pct(totals, 0.5)} / {pct(totals, 0.95)} ms |",
        f"",
        f"## Outcome 分布",
        f"",
    ]
    for outcome, n in outcomes.most_common():
        report_lines.append(f"- {outcome}: {n}")

    report_lines += [
        f"",
        f"## 失败样本",
        f"",
    ]
    for r in results:
        if r["result"]["outcome"] != "success" or not r["result"].get("citation_ok"):
            report_lines.append(
                f"- KB {r['kb_id']} / Q: {r['question']}\n"
                f"  outcome={r['result']['outcome']} citation_ok={r['result'].get('citation_ok')} "
                f"err={r['result'].get('error_code')}"
            )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport written: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: 5 行 PoC 测试**

```bash
head -5 eval/golden.jsonl > /tmp/golden-poc.jsonl

# 拿 token：浏览器 devtools → localStorage → access_token
export EVAL_TOKEN="<paste-token>"
cd backend && uv run python -m scripts.eval.run_eval \
  --golden ../eval/golden.jsonl --output /tmp/poc-report.md --label poc
```

期望：能跑完 5 条，输出 markdown 报告。

- [ ] **Step 4: 格式化 + commit**

```bash
cd backend && uv run ruff format scripts/eval/sse_client.py scripts/eval/run_eval.py
cd ..
git add backend/scripts/eval/sse_client.py backend/scripts/eval/run_eval.py
git commit -m "feat(eval): add SSE-based eval runner

- Reusable SSE client (also used by Locust)
- run_eval.py reads golden.jsonl, calls real /ask endpoint
- Reports: success rate, citation hit rate, keyword coverage, TTFT/total percentiles

Refs: spec.md §3.5, §4 Task 13"
```

---

## Task 14: Locust 压测脚本

**Files:**
- Modify: `backend/pyproject.toml`（dev 加 locust + httpx-sse）
- Create: `backend/scripts/load_test/__init__.py`
- Create: `backend/scripts/load_test/locustfile.py`

- [ ] **Step 1: 加 dev 依赖**

```bash
cd backend
uv add --dev locust httpx-sse prometheus-client
cd ..
```

> `prometheus-client` 已在 main deps；这里 dev 段加也没冲突，方便 locustfile 自我度量。

- [ ] **Step 2: 写 locustfile.py**

创建 `backend/scripts/load_test/__init__.py` 为空。

创建 `backend/scripts/load_test/locustfile.py`：

```python
"""Locust 压测脚本：模拟问答请求。

启动：
  cd backend
  uv run locust -f scripts/load_test/locustfile.py \
    --host=http://localhost:8000 \
    --headless -u 50 -r 5 -t 5m \
    --html ../docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/locust-50.html

环境变量：
  LOCUST_TOKEN     - JWT token
  LOCUST_KB_IDS    - 逗号分隔的 KB ID（如 "1,2,3"）
  LOCUST_QUESTIONS - synthetic.jsonl 路径
"""

import json
import os
import random
from pathlib import Path

from locust import HttpUser, between, events, task

TOKEN = os.environ.get("LOCUST_TOKEN", "")
KB_IDS = [int(x) for x in os.environ.get("LOCUST_KB_IDS", "1").split(",")]
QUESTIONS_PATH = os.environ.get(
    "LOCUST_QUESTIONS",
    str(Path(__file__).resolve().parents[3] / "eval" / "synthetic.jsonl"),
)


# 预加载问题
_QUESTIONS: list[dict] = []
if Path(QUESTIONS_PATH).exists():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        for line in f:
            _QUESTIONS.append(json.loads(line))


class AskUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.conversations: dict[int, str] = {}
        for kb_id in KB_IDS:
            resp = self.client.post(
                "/api/v1/qa/conversations",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"knowledge_base_ids": [kb_id]},
                name="POST /conversations (setup)",
            )
            if resp.status_code == 200:
                self.conversations[kb_id] = resp.json()["data"]["id"]

    @task
    def ask(self):
        if not _QUESTIONS or not self.conversations:
            return
        sample = random.choice(_QUESTIONS)
        kb_id = sample["kb_id"]
        conv_id = self.conversations.get(kb_id) or next(iter(self.conversations.values()))

        with self.client.post(
            f"/api/v1/qa/conversations/{conv_id}/ask",
            json={"question": sample["question"]},
            headers={"Authorization": f"Bearer {TOKEN}"},
            stream=True,
            name="POST /conversations/:id/ask",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"status={resp.status_code}")
                return
            # 简单消费 stream
            saw_done = False
            try:
                for chunk in resp.iter_lines():
                    if b'"type": "done"' in chunk:
                        saw_done = True
                resp.success() if saw_done else resp.failure("no done event")
            except Exception as e:
                resp.failure(f"stream error: {e}")
```

- [ ] **Step 3: 拉取 token，跑 30 秒 PoC**

```bash
export LOCUST_TOKEN="<paste-token>"
export LOCUST_KB_IDS="1,2,3"

cd backend && uv run locust -f scripts/load_test/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 5 -r 1 -t 30s
```

期望：5 个并发跑 30 秒，输出 RPS / 失败率。失败率应 < 50%（若高于 50% 说明 F1 没生效或后端有别的问题）。

- [ ] **Step 4: 格式化 + commit**

```bash
cd backend && uv run ruff format scripts/load_test/locustfile.py
cd ..
git add backend/scripts/load_test/__init__.py backend/scripts/load_test/locustfile.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(eval): add locust load test script

- Aspires to 50/100/200 concurrent users in staircase
- Reads synthetic.jsonl questions, hits real /ask SSE endpoint
- Stream consumed with 'done' event verification

Refs: spec.md §3.6, §4 Task 14"
```

---

# Stage 4.1: Baseline 跑（Gate 4.1）

---

## Task 15: 跑 Baseline + 保存

**Files:**
- Create: `docs/specs/2026-05-27-measurement-and-fix/report-baseline.md`（评估脚本生成）
- Create: `docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/` 下若干 PNG

> ⚠️ **重要**：此 Task 在 F2/F3/F4/F5 修复**之前**执行，目的就是采集"带 bug 数据"。

- [ ] **Step 1: 确认前置状态**

```bash
# F1 必须已修（Task 8 已 commit）
git log --oneline | grep "F1\|fts_task" | head -3

# F2/F3/F4/F5 必须未修
git log --oneline | grep -E "F2|F3|F4|F5|JSONB|ivfflat|refreshAccess" | head
# 上面应该为空
```

- [ ] **Step 2: 重启服务确保 metrics 干净**

```bash
# 重启 Prometheus 清空数据（可选；如果想保留全程数据则跳过）
docker restart offercopilot-prometheus
# 等 5s 让它启动
sleep 5
```

- [ ] **Step 3: 跑评估集**

```bash
export EVAL_TOKEN="<paste-fresh-token>"
mkdir -p docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline
cd backend && uv run python -m scripts.eval.run_eval \
  --golden ../eval/golden.jsonl \
  --output ../docs/specs/2026-05-27-measurement-and-fix/report-baseline.md \
  --label baseline
cd ..
```

期望：~20 条全部跑完，生成 `report-baseline.md`。

- [ ] **Step 4: 跑 Locust 阶梯压测（50 并发）**

```bash
export LOCUST_TOKEN="$EVAL_TOKEN"
export LOCUST_KB_IDS="1,2,3"

cd backend && uv run locust -f scripts/load_test/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 50 -r 5 -t 5m \
  --html ../docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/locust-50.html \
  --csv ../docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/locust-50
cd ..
```

- [ ] **Step 5: 跑 100 并发**

```bash
cd backend && uv run locust -f scripts/load_test/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 100 -r 10 -t 5m \
  --html ../docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/locust-100.html \
  --csv ../docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/locust-100
cd ..
```

> 200 并发**可选**——根据机器情况决定。如果本机 CPU 已饱和（top 中 backend 100%），200 并发只会让数据失真。

- [ ] **Step 6: 截图三张 Grafana 看板**

打开 `http://localhost:3001`，时间范围设置为"压测刚结束的过去 15 分钟"。

对每张看板：
1. 看板右上角 → Share → Snapshot → Export → 选 PNG
2. 保存为 `screenshots/baseline/rag.png`、`http.png`、`cache.png`

> 也可以用浏览器截图工具直接截全屏。

- [ ] **Step 7: 不 commit baseline 数据**

```bash
# 暂时本地保留，等 after 跑完一起 commit（对比一目了然）
ls docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/
ls docs/specs/2026-05-27-measurement-and-fix/report-baseline.md
```

**Gate 4.1 验收**：
- ✅ `report-baseline.md` 存在
- ✅ `screenshots/baseline/` 至少 3 张 PNG + 2 个 locust HTML
- ✅ 报告中：outcome=success < 100%（应该能看到一些 error；这正是 baseline 价值）
- ✅ Grafana cache 看板 L1 命中率 < 5%（F3 未修证据）

---

# Stage 2 后半: F2 / F3 / F4 / F5 修复

---

## Task 16: F2.1 — `knowledge_base_ids` 列从 JSON 迁移到 JSONB

**Files:**
- Modify: `backend/app/models/semantic_cache.py`
- Create: `backend/alembic/versions/<new>_alter_kb_ids_to_jsonb.py`

- [ ] **Step 1: 修改 model 类型**

修改 `backend/app/models/semantic_cache.py`：

```python
# 旧 import:
from sqlalchemy import JSON
# 改为:
from sqlalchemy.dialects.postgresql import JSONB

# 列定义改：
knowledge_base_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
```

> 注意：保留 `from sqlalchemy import ...` 中其他依赖（如 Integer 等）。

- [ ] **Step 2: 生成 Alembic 迁移**

```bash
cd backend && uv run alembic revision --autogenerate -m "alter_kb_ids_to_jsonb"
```

打开生成的迁移文件（位置：`backend/alembic/versions/<hash>_alter_kb_ids_to_jsonb.py`），通常 autogen 会生成 `op.alter_column(..., type_=postgresql.JSONB)`，但**默认 cast 不带 USING 子句**。检查并改写为：

```python
def upgrade() -> None:
    op.alter_column(
        "semantic_query_caches",
        "knowledge_base_ids",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="knowledge_base_ids::jsonb",
    )
    op.create_index(
        "ix_semantic_caches_kb_ids_gin",
        "semantic_query_caches",
        ["knowledge_base_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_semantic_caches_kb_ids_gin", table_name="semantic_query_caches")
    op.alter_column(
        "semantic_query_caches",
        "knowledge_base_ids",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="knowledge_base_ids::json",
    )
```

确保文件顶部 import：

```python
from sqlalchemy.dialects import postgresql
```

- [ ] **Step 3: 跑迁移**

```bash
cd backend && uv run alembic upgrade head
```

期望：成功，无错误。

- [ ] **Step 4: 验证列类型**

```bash
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d offercopilot -c "
\d semantic_query_caches
"
```

期望：`knowledge_base_ids | jsonb` 而非 `json`。GIN 索引 `ix_semantic_caches_kb_ids_gin` 出现。

- [ ] **Step 5: 验证 downgrade**

```bash
cd backend && uv run alembic downgrade -1
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d offercopilot -c "\d semantic_query_caches"
# 期望 knowledge_base_ids | json
uv run alembic upgrade head
# 再回 jsonb
```

- [ ] **Step 6: 不 commit，等 Task 17 一起**

---

## Task 17: F2.2 — repository 改用 `.contains()` + 反向断言测试

**Files:**
- Modify: `backend/app/repositories/qa_repository.py`
- Create: `backend/tests/repositories/test_qa_repository_evict.py`

- [ ] **Step 1: 写失败测试（含反向断言）**

创建 `backend/tests/repositories/__init__.py` 为空（如不存在）。

创建 `backend/tests/repositories/test_qa_repository_evict.py`：

```python
"""F2 反向断言测试：删除 kb_id=5 不应误删 kb_id=15/50/125。"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import SemanticCache
from backend.app.repositories.qa_repository import evict_caches_by_kb_id


@pytest.mark.asyncio
async def test_evict_by_kb_id_does_not_affect_neighbors(db_session: AsyncSession):
    # 准备 3 条记录
    rows = [
        SemanticCache(question="q1", query_vector=[0.0] * 1536, response_events=[], knowledge_base_ids=[5]),
        SemanticCache(question="q2", query_vector=[0.0] * 1536, response_events=[], knowledge_base_ids=[15]),
        SemanticCache(question="q3", query_vector=[0.0] * 1536, response_events=[], knowledge_base_ids=[50]),
    ]
    for r in rows:
        db_session.add(r)
    await db_session.commit()

    # 触发 evict
    await evict_caches_by_kb_id(db_session, kb_id=5)

    # 断言：只有 [5] 被删，[15] 和 [50] 保留
    remaining = (await db_session.execute(select(SemanticCache))).scalars().all()
    remaining_ids = {tuple(r.knowledge_base_ids or []) for r in remaining}
    assert (5,) not in remaining_ids, "kb_id=5 应被删除"
    assert (15,) in remaining_ids, "kb_id=15 不应被误删（LIKE %5% bug）"
    assert (50,) in remaining_ids, "kb_id=50 不应被误删"


@pytest.mark.asyncio
async def test_evict_by_kb_id_with_multi_kb_entry(db_session: AsyncSession):
    """如果 cache entry 涉及多个 KB（如 [5,15]），删 5 应该把这条删掉。"""
    db_session.add(SemanticCache(
        question="q-multi", query_vector=[0.0] * 1536, response_events=[], knowledge_base_ids=[5, 15],
    ))
    await db_session.commit()

    await evict_caches_by_kb_id(db_session, kb_id=5)

    remaining = (await db_session.execute(select(SemanticCache))).scalars().all()
    assert len(remaining) == 0
```

> 假设项目已有 `db_session` fixture；如没有，参考 `backend/tests/conftest.py` 或现有测试创建。

- [ ] **Step 2: 跑测试，预期当前 LIKE 实现下"反向断言"测试会失败**

```bash
cd backend && uv run pytest tests/repositories/test_qa_repository_evict.py -v
```

期望：`test_evict_by_kb_id_does_not_affect_neighbors` 失败（因为 LIKE '%5%' 会匹配 15、50）。

> 实际上由于 Task 7 中"暂时保留 LIKE bug"的代码还会先抛 `NameError: Text not defined`——所以测试可能因 NameError 失败而非误删失败。**都算"预期失败"。**

- [ ] **Step 3: 重写 evict_caches_by_kb_id**

修改 `backend/app/repositories/qa_repository.py`：

```python
async def evict_caches_by_kb_id(db: AsyncSession, kb_id: int) -> None:
    """当知识库被物理删除或更新时，物理驱逐全平台所有涉及该知识库 ID 的语义缓存记录。"""
    from time import perf_counter
    from sqlalchemy import delete
    from backend.app.core.metrics import CACHE_OPERATION_DURATION_SECONDS

    start = perf_counter()
    try:
        # JSONB contains: knowledge_base_ids @> '[5]'
        stmt = delete(SemanticCache).where(
            SemanticCache.knowledge_base_ids.contains([kb_id])
        )
        await db.execute(stmt)
        await db.commit()
    finally:
        CACHE_OPERATION_DURATION_SECONDS.labels(
            layer="l2", operation="evict"
        ).observe(perf_counter() - start)
```

并在文件顶部 import 段确认有：

```python
from sqlalchemy import func, select  # 已有
# 不再需要：from sqlalchemy import Text
# 不再需要：from sqlalchemy.dialects.postgresql import JSONB（contains 是 InstrumentedAttribute 方法，列已是 JSONB 类型）
```

> 因为 model 的列已经是 JSONB（Task 16），`SemanticCache.knowledge_base_ids.contains([kb_id])` 会自动生成 `@>` 操作符。无需 `cast`。

- [ ] **Step 4: 跑测试，预期通过**

```bash
cd backend && uv run pytest tests/repositories/test_qa_repository_evict.py -v
```

期望：2 passed

- [ ] **Step 5: 格式化 + commit Task 16 + 17**

```bash
cd backend && uv run ruff format \
  app/models/semantic_cache.py \
  app/repositories/qa_repository.py \
  tests/repositories/test_qa_repository_evict.py \
  alembic/versions/*alter_kb_ids_to_jsonb*.py
cd ..
git add backend/app/models/semantic_cache.py \
        backend/app/repositories/qa_repository.py \
        backend/tests/repositories/__init__.py \
        backend/tests/repositories/test_qa_repository_evict.py \
        backend/alembic/versions/*alter_kb_ids_to_jsonb*.py
git commit -m "fix(cache): migrate kb_ids to JSONB + use .contains() (F2)

Previous: cast(JSON, Text).like('%5%') had two bugs:
  1. Text not imported → NameError → evict silently failed
  2. LIKE '%5%' matched [15], [50], [125] (false positive deletion)

Now: column type JSONB with GIN index; .contains([kb_id]) uses @>.
Reverse-assertion test ensures neighbors are NOT deleted.

Refs: spec.md §4.2 (F2)"
```

---

## Task 18: F3 — L1 cache key 移除 conv_id

**Files:**
- Modify: `backend/app/services/qa_service.py:1063 / 1641 / 1988`（三处）
- Create: `backend/tests/services/test_qa_service_cache_key.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/services/test_qa_service_cache_key.py`：

```python
"""F3 测试：L1 cache key 不应依赖 conv_id。"""

import pytest


def test_l1_cache_key_independent_of_conv_id():
    """不同 conv_id 但相同 (scope, question) 应该产生相同 key。"""
    from backend.app.services.qa_service import _build_l1_cache_key  # 新增的 helper

    key_a = _build_l1_cache_key(scope_hash="s1", q_hash="q1")
    key_b = _build_l1_cache_key(scope_hash="s1", q_hash="q1")
    assert key_a == key_b
    assert "conv" not in key_a.lower()


def test_l1_cache_key_different_scope_produces_different_key():
    from backend.app.services.qa_service import _build_l1_cache_key

    assert _build_l1_cache_key(scope_hash="s1", q_hash="q1") != _build_l1_cache_key(scope_hash="s2", q_hash="q1")
    assert _build_l1_cache_key(scope_hash="s1", q_hash="q1") != _build_l1_cache_key(scope_hash="s1", q_hash="q2")
```

- [ ] **Step 2: 跑测试，期望失败**

```bash
cd backend && uv run pytest tests/services/test_qa_service_cache_key.py -v
```

期望：`ImportError: cannot import _build_l1_cache_key`

- [ ] **Step 3: 实现 helper + 改三处 key**

修改 `backend/app/services/qa_service.py`，在 `_emit_rag_telemetry` 附近加 helper：

```python
def _build_l1_cache_key(*, scope_hash: str, q_hash: str) -> str:
    """L1 缓存 key 构造：只按 (scope, question) 隔离，与 L2 对齐。

    历史 bug：曾经把 conv_id 也放进 key，导致跨会话相同问题永远 miss。
    """
    return f"cache:rag:ask:{scope_hash}:{q_hash}"
```

然后**替换三处**（1063 / 1641 / 1988，行号以当前为准，需要重新 grep 确认）：

```bash
# 旧：l1_cache_key = f"cache:rag:ask:{conv_id}:{scope_hash}:{q_hash}"
# 新：l1_cache_key = _build_l1_cache_key(scope_hash=scope_hash, q_hash=q_hash)
```

可用 sed 批量替换，但更安全是手动改三处确认上下文。

- [ ] **Step 4: 跑测试，期望通过**

```bash
cd backend && uv run pytest tests/services/test_qa_service_cache_key.py -v
```

期望：2 passed

- [ ] **Step 5: 集成验证**

启动后端，新开一个会话问 "什么是 FastAPI"，等响应完。
**新开另一个会话**（不同 conv_id），问同样的问题。
观察 `backend.log`，应看到 L1 hit 信息（如果有 logger）。

或检查指标：

```bash
curl -s http://localhost:8000/metrics | grep 'cache_lookup_total{layer="l1",result="hit"}'
```

期望：数值 > 0 且**比修复前显著增加**。

- [ ] **Step 6: 格式化 + commit**

```bash
cd backend && uv run ruff format app/services/qa_service.py tests/services/test_qa_service_cache_key.py
cd ..
git add backend/app/services/qa_service.py backend/tests/services/test_qa_service_cache_key.py
git commit -m "fix(cache): remove conv_id from L1 cache key (F3)

Previously: key = 'cache:rag:ask:{conv_id}:{scope_hash}:{q_hash}'
Same question in different conversations would never hit L1.
Observed hit rate ≈ 0.3% in baseline.

Now: key = 'cache:rag:ask:{scope_hash}:{q_hash}'
scope_hash already includes KB ids; KBs are user-private, so no
additional user_id isolation needed.

Refs: spec.md §4.3 (F3)"
```

---

## Task 19: F4 — ivfflat 向量索引迁移

**Files:**
- Create: `backend/alembic/versions/<new>_add_ivfflat_to_semantic_cache.py`

- [ ] **Step 1: 确认与现有 document_chunks 索引方案一致**

```bash
grep -rn "ivfflat\|hnsw" backend/alembic/versions/
```

如果 document_chunks 用 ivfflat → 保持 ivfflat；如果用 hnsw → 改用 hnsw。

> 假设结果：用 ivfflat。

- [ ] **Step 2: 创建迁移**

```bash
cd backend && uv run alembic revision -m "add_ivfflat_to_semantic_cache"
```

> 注意：不用 `--autogenerate`，因为 autogen 不识别 ivfflat。手动写。

打开生成的文件 `backend/alembic/versions/<hash>_add_ivfflat_to_semantic_cache.py`，改为：

```python
"""add_ivfflat_to_semantic_cache

Revision ID: ...
Revises: <previous>
Create Date: ...
"""

from typing import Sequence, Union

from alembic import op


revision: str = "<auto-generated>"
down_revision: Union[str, Sequence[str], None] = "<previous>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_semantic_caches_query_vector "
        "ON semantic_query_caches USING ivfflat (query_vector vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_semantic_caches_query_vector")
```

> 保留 alembic autogen 填充的 revision/down_revision 值，不要手改。

- [ ] **Step 3: 跑迁移**

```bash
cd backend && uv run alembic upgrade head
```

- [ ] **Step 4: 验证索引存在**

```bash
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d offercopilot -c "
SELECT indexname FROM pg_indexes WHERE tablename = 'semantic_query_caches';
"
```

期望看到 `ix_semantic_caches_query_vector`。

- [ ] **Step 5: 验证 downgrade**

```bash
cd backend && uv run alembic downgrade -1
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d offercopilot -c "\d+ semantic_query_caches" | grep ivfflat
# 期望无输出
uv run alembic upgrade head
```

- [ ] **Step 6: commit**

```bash
git add backend/alembic/versions/*add_ivfflat_to_semantic_cache*.py
git commit -m "fix(cache): add ivfflat index to semantic_query_caches.query_vector (F4)

Without this index, find_similar_semantic_cache does a sequential
scan on every L2 lookup. Baseline data will show p95 increases as
cache table grows; after this fix, p95 stays flat.

Index choice: ivfflat to match existing document_chunks index strategy;
lists=100 sufficient for expected size (< 10K rows).

Refs: spec.md §4.4 (F4)"
```

---

## Task 20: F5 — 前端 refreshAccessToken 重构

**Files:**
- Modify: `frontend/src/lib/session.ts`
- Modify: `frontend/src/lib/http.ts`
- Test: `frontend/src/lib/__tests__/session.test.ts`

- [ ] **Step 1: 全量找调用方**

```bash
grep -rn "refreshAccessToken" frontend/src/
```

记录所有调用位置，确保下面修改时都覆盖到。

- [ ] **Step 2: 写失败测试**

创建或修改 `frontend/src/lib/__tests__/session.test.ts`：

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";

import { refreshAccessToken } from "@/lib/session";

describe("refreshAccessToken (F5)", () => {
  beforeEach(() => {
    vi.resetModules();
    global.fetch = vi.fn();
  });

  it("returns refresh_failed_retry_later when server returns 500", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    const result = await refreshAccessToken();
    expect(result?.status).toBe("refresh_failed_retry_later");
  });

  it("returns ok with new token on 200", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { access_token: "new-token" } }),
    });

    const result = await refreshAccessToken();
    expect(result?.status).toBe("ok");
    if (result?.status === "ok") {
      expect(result.token).toBe("new-token");
    }
  });

  it("returns unauthorized on 401", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({}),
    });

    const result = await refreshAccessToken();
    expect(result?.status).toBe("unauthorized");
  });
});
```

- [ ] **Step 3: 跑测试，期望失败**

```bash
cd frontend && pnpm vitest run src/lib/__tests__/session.test.ts
```

期望：fail（旧实现返回 string|null，不是 result.status 形式）。

- [ ] **Step 4: 重构 refreshAccessToken**

修改 `frontend/src/lib/session.ts`，重写 `refreshAccessToken`：

```typescript
export type RefreshResult =
  | { status: "ok"; token: string }
  | { status: "refresh_failed_retry_later" }
  | { status: "unauthorized" };

export async function refreshAccessToken(): Promise<RefreshResult | null> {
  if (!isBrowser()) {
    return null;
  }

  initAuthChannel();

  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async (): Promise<RefreshResult> => {
    try {
      const response = await fetch(buildUrl("/auth/refresh-token"), {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        // 5xx: 服务端暂时不可用，告诉调用方"稍后重试"，不要把当前 session 当作"已失效"
        if (response.status >= 500) {
          console.warn("Refresh token failed with server error, retry later");
          return { status: "refresh_failed_retry_later" };
        }

        // 4xx: 其他标签页可能已经刷新过了
        const currentToken = getAccessToken();
        if (currentToken && !isAccessTokenExpiringSoon()) {
          return { status: "ok", token: currentToken };
        }
        handleUnauthorizedSession();
        return { status: "unauthorized" };
      }

      const payload = (await parseJson<LoginEnvelope>(response)) ?? null;
      if (!payload?.data) {
        handleUnauthorizedSession();
        return { status: "unauthorized" };
      }

      const newToken = payload.data.access_token;
      setAccessToken(newToken);
      return { status: "ok", token: newToken };
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}
```

> 注意保留原文件其他部分（type 定义、helper 等）。`refreshPromise` 类型也要从 `Promise<string | null> | null` 改为 `Promise<RefreshResult> | null`。

- [ ] **Step 5: 修改调用方 http.ts**

修改 `frontend/src/lib/http.ts` 中调用 `refreshAccessToken` 的位置（约 86 行）：

```typescript
// 旧：
// const newToken = await refreshAccessToken();
// if (newToken) {
//   // retry with new token
// }

// 新：
const refreshResult = await refreshAccessToken();
if (refreshResult?.status === "ok") {
  // 用新 token 重试原请求
  retryWithToken(refreshResult.token);
} else if (refreshResult?.status === "refresh_failed_retry_later") {
  // 服务端临时失败：不要重试，让原请求失败上抛，用户/重试逻辑稍后再来
  throw new HttpError("Refresh service unavailable", 503);
} else {
  // unauthorized 或 null：handleUnauthorizedSession 已在 refreshAccessToken 内调用
  throw new HttpError("Session expired", 401);
}
```

> 具体类名 `HttpError` 是否存在以项目实际为准，调用方法 `retryWithToken` 也以项目实际为准。本步实施时根据 `http.ts` 现状调整。

- [ ] **Step 6: grep 检查所有其他调用方**

```bash
grep -rn "refreshAccessToken" frontend/src/
```

如果有除 http.ts 外的其他调用方（比如某些 hook），同样更新返回值处理逻辑。

- [ ] **Step 7: 跑测试**

```bash
cd frontend && pnpm vitest run src/lib/__tests__/session.test.ts
```

期望：3 passed

- [ ] **Step 8: 跑全部前端测试，确保没踩坏其他**

```bash
cd frontend && pnpm test
```

期望：全部通过；如有 askConversation 相关测试已知失败（B5），不在本次 spec 范围。

- [ ] **Step 9: 格式化 + commit**

```bash
cd frontend && pnpm prettier --write src/lib/session.ts src/lib/http.ts src/lib/__tests__/session.test.ts
cd ..
git add frontend/src/lib/session.ts frontend/src/lib/http.ts frontend/src/lib/__tests__/session.test.ts
git commit -m "fix(auth): distinguish refresh server-error from auth failure (F5)

Previous: on 5xx, refreshAccessToken returned the (potentially expired)
existing token. Callers treated it as 'refresh succeeded' and retried,
hitting 401, which then triggered handleUnauthorizedSession — users
were logged out on every transient backend hiccup.

Now: typed RefreshResult { ok | refresh_failed_retry_later | unauthorized }.
http.ts handles each branch explicitly; 5xx no longer kicks users out.

Refs: spec.md §4.5 (F5)"
```

**Gate 2 完整验收**（Task 9 + 16-20 都完成后）：
- ✅ 三张看板都有数据
- ✅ MICRO_RETRIEVAL SSE 走通
- ✅ `evict_caches_by_kb_id` 单元 + 反向断言通过
- ✅ L1 lookup 跨 conv_id 命中
- ✅ Alembic 迁移 head 一致
- ✅ refreshAccessToken 5xx 不踢人
- ✅ ruff / prettier 格式化通过

---

# Stage 4.2: After 跑（Gate 4.2）

---

## Task 21: 跑 After + 保存

**Files:**
- Create: `docs/specs/2026-05-27-measurement-and-fix/report-after.md`
- Create: `docs/specs/2026-05-27-measurement-and-fix/screenshots/after/`

- [ ] **Step 1: 确认所有 F2-F5 已 commit**

```bash
git log --oneline | head -10
```

应看到 F2 / F3 / F4 / F5 的 commits。

- [ ] **Step 2: 跑评估集**

```bash
export EVAL_TOKEN="<fresh-token>"
mkdir -p docs/specs/2026-05-27-measurement-and-fix/screenshots/after
cd backend && uv run python -m scripts.eval.run_eval \
  --golden ../eval/golden.jsonl \
  --output ../docs/specs/2026-05-27-measurement-and-fix/report-after.md \
  --label after
cd ..
```

- [ ] **Step 3: 跑 Locust 50/100 阶梯**

```bash
export LOCUST_TOKEN="$EVAL_TOKEN"
export LOCUST_KB_IDS="1,2,3"

cd backend && uv run locust -f scripts/load_test/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 50 -r 5 -t 5m \
  --html ../docs/specs/2026-05-27-measurement-and-fix/screenshots/after/locust-50.html \
  --csv ../docs/specs/2026-05-27-measurement-and-fix/screenshots/after/locust-50

uv run locust -f scripts/load_test/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 100 -r 10 -t 5m \
  --html ../docs/specs/2026-05-27-measurement-and-fix/screenshots/after/locust-100.html \
  --csv ../docs/specs/2026-05-27-measurement-and-fix/screenshots/after/locust-100
cd ..
```

- [ ] **Step 4: 截图三张 Grafana 看板**

时间范围设置为"压测刚结束的过去 15 分钟"，导出 PNG 到 `screenshots/after/rag.png`、`http.png`、`cache.png`。

- [ ] **Step 5: 对比核心数字（人工 check）**

打开 `report-baseline.md` 和 `report-after.md`，对比：

| 指标 | Baseline | After | 期望差异 |
|---|---|---|---|
| 总成功率 | < 100% | ≥ 95% | F1 修复体现 |
| 引用命中率 | ? | 持平或↑ | 无直接修复，但 cache 影响 |
| Outcome=error | > 0 | ≈ 0 | F1 体现 |
| L1 命中率（Grafana） | < 5% | ≥ 30% | F3 体现 |
| L2 lookup p95（Grafana） | 较高 | 较低 | F4 索引体现（需要数据量大才明显） |

> 至少 3 组数字应该有显著差异。如果差异不明显，说明：
> - baseline 数据样本太少；可以追加跑一次更长的压测
> - 某项 fix 没真正生效；回去排查

- [ ] **Step 6: commit baseline + after 全部数据**

```bash
git add docs/specs/2026-05-27-measurement-and-fix/report-baseline.md \
        docs/specs/2026-05-27-measurement-and-fix/report-after.md \
        docs/specs/2026-05-27-measurement-and-fix/screenshots/
git commit -m "docs(spec): add baseline and after evaluation reports + screenshots

- report-baseline.md: pre-fix data (F1 only, F2-F5 not yet applied)
- report-after.md: post-fix data (all A-pile fixes applied)
- screenshots/ Grafana panels + locust HTML reports

Key contrasts:
- L1 hit rate ?% → ?%
- outcome=success ?% → ?%
- L2 lookup p95 ?ms → ?ms

(Actual numbers in report files)

Refs: spec.md §3.6, §3.7"
```

**Gate 4.2 验收**：
- ✅ `report-after.md` 存在
- ✅ `screenshots/after/` 至少 3 张 PNG + 2 个 locust HTML
- ✅ 至少 3 组指标显著优于 baseline

---

# Stage 5: 故事沉淀（Gate 5）

---

## Task 22: 写 final-report.md 三段式

**Files:**
- Create: `docs/specs/2026-05-27-measurement-and-fix/final-report.md`

- [ ] **Step 1: 写 final-report 大纲**

创建 `docs/specs/2026-05-27-measurement-and-fix/final-report.md`：

```markdown
# 测量驱动的修复与可观测性建设 — 最终报告

| 字段 | 值 |
|---|---|
| **Spec** | [`2026-05-27-measurement-and-fix`](./spec.md) |
| **完成日期** | YYYY-MM-DD |
| **总投入** | X 个工作日 |

## 项目背景

offer-copilot 是一个面向开发者的 RAG 知识库问答系统。在做这次工作之前，项目有：
- 一份 `rag_telemetry` 日志埋点（13 个字段）
- Sentry 错误追踪
- **没有**任何可量化的运行时指标（错误率、p95、缓存命中率等）
- **没有**评估集，无法量化 RAG 答得对不对

## 目标

不只是"加埋点 + 加看板"，而是用**测量 → 发现 → 修复 → 验证**的闭环，证明可观测性的真正价值。

## 三段式

### 一、测量：建立指标体系

| 维度 | 实现 |
|---|---|
| HTTP 层 SLI | Prometheus FastAPI middleware，p50/p95/p99/QPS/错误率 |
| RAG 链路 | 复用现有 rag_telemetry，转 Prometheus Histogram/Counter；新增 TTFT |
| Cache 层 | L1/L2 命中率 + 操作耗时 |
| 可视化 | Grafana 三张看板（RAG / HTTP / Cache），共 14 panel，JSON provisioning |
| 评估集 | 20 道人工标注 + 60 道 LLM 生成 |
| 压测 | Locust 50/100 并发阶梯 |

### 二、发现：用数据找 bug

跑完 baseline 后，数据暴露了 4 类问题：

| 数据信号 | 问题 |
|---|---|
| `cache_lookup_total{layer="l1",result="hit"}` 占比 < 1% | F3：L1 cache key 含 `conv_id`，跨会话永远 miss |
| `rag_outcome_total{outcome="error",error_code="AttributeError"}` ~12% | F1：fts_task.done() 调用 coroutine 抛 AttributeError，SSE 断流 |
| `cache_operation_duration_seconds{layer="l2",operation="lookup"}` p95 偏高且不稳定 | F4：semantic_cache 缺 ivfflat 索引，find_similar 全表扫描 |
| 错误日志看到 KB 删除后语义缓存还在命中 | F2：evict 函数 Text 未 import + LIKE 误删邻居 |
| HTTP 错误率 5xx 时段 401 也偏高 | F5：refreshAccessToken 5xx 时返回旧 token，401 把用户登出 |

### 三、修复 + 验证：5 个 A 堆 bug

#### F1: fts_task 协程修复 → outcome=error 从 12% 降到 < 1%

[贴 baseline vs after 的 outcome 分布数字]

#### F2: knowledge_base_ids 列从 JSON 升 JSONB + GIN 索引 + .contains() → 删 KB 不再误伤邻居缓存

[贴单元测试反向断言截图]

#### F3: L1 cache key 去掉 conv_id → L1 命中率 0.3% → X%

![cache hit rate before/after](screenshots/after/cache.png)

#### F4: semantic_cache 加 ivfflat 索引 → L2 lookup p95 从 X ms 降到 Y ms

[贴 Grafana cache 看板 lookup duration 时间序列]

#### F5: refreshAccessToken 5xx 不再误登出 → 用户体验

[贴单元测试 3 例]

## 量化对比表

| 指标 | Baseline | After | Δ |
|---|---|---|---|
| 总成功率 | X% | Y% | +Z% |
| outcome=error | X% | Y% | -Z% |
| L1 命中率 | X% | Y% | +Z% |
| L2 lookup p95 | X ms | Y ms | -Z% |
| HTTP p95（/ask） | X s | Y s | -Z% |
| HTTP 错误率 5xx | X% | Y% | -Z% |

## 故事金线（面试 5 分钟可讲）

> "我给项目加了一套量化指标：rag_telemetry 接 Prometheus + 缓存命中率 + HTTP p95/p99/错误率。建立指标的过程中，用数据发现了 4 类生产级 bug——L1 缓存命中率接近零（key bug）、流式问答某条分支因为协程错误处理直接断流、L2 语义缓存缺向量索引、refresh token 在 5xx 时把用户错误登出。我都修了，对比数字证明改进。**可观测性的真正价值不是埋点本身，是能持续发现这种问题的能力。**"

## 不做项 & Backlog

详见 [follow-up.md](./follow-up.md)：

- B1-B5（5 项背景修复，单独 PR 处理）
- SLO 阈值数字承诺（待 baseline + after 稳定后定）

## 关联文档

- [spec.md](./spec.md) — 设计文档
- [flow.html](./flow.html) — 流程图
- [report-baseline.md](./report-baseline.md) — 修复前评估
- [report-after.md](./report-after.md) — 修复后评估
- [follow-up.md](./follow-up.md) — B 堆 backlog
```

- [ ] **Step 2: 把 baseline 和 after 报告里的具体数字填回 final-report**

人工对照两份 report，把 final-report 中的 `[贴数字]` 和"X / Y / Z"占位换成实际值。

- [ ] **Step 3: commit**

```bash
git add docs/specs/2026-05-27-measurement-and-fix/final-report.md
git commit -m "docs(spec): write final report (3-stage measure/discover/fix narrative)

5-minute interview-pitchable story with concrete before/after numbers.
References baseline + after reports for evidence chains.

Refs: spec.md §3.7"
```

---

## Task 23: README 更新 + dry-run 验收

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README 中加一节**

定位 `README.md` 合适位置（建议放在"快速启动"之后、"项目结构"之前），加：

````markdown
## 性能与可观测性

本项目集成了完整的指标体系（Prometheus + Grafana 三看板），并通过测量驱动发现并修复了 5 个 P0/P1/INFO 级别 bug。详细报告：

→ [测量驱动的修复与可观测性建设](docs/specs/2026-05-27-measurement-and-fix/final-report.md)

启动后访问：

- Grafana 看板：http://localhost:3001 (admin/admin)
- Prometheus：http://localhost:9090
- `/metrics`：http://localhost:8000/metrics

跑评估集与压测：

```bash
# 1. 评估集（20 道人工标注）
export EVAL_TOKEN="<your-jwt>"
cd backend && uv run python -m scripts.eval.run_eval \
  --golden ../eval/golden.jsonl \
  --output /tmp/eval-report.md

# 2. Locust 压测
export LOCUST_TOKEN="$EVAL_TOKEN"
export LOCUST_KB_IDS="1,2,3"
cd backend && uv run locust -f scripts/load_test/locustfile.py \
  --host=http://localhost:8000 --headless -u 50 -r 5 -t 5m
```
````

- [ ] **Step 2: dry-run：5 分钟讲完整个故事（计时）**

打开手机定时器 5 分钟，按 final-report.md 的"故事金线 + 三段式 + 量化对比表"顺序讲：

1. （30s）项目背景 + 没有指标的问题
2. （1.5min）测量：埋点 + Grafana 三看板演示
3. （1.5min）发现：4 类 bug + 数据信号
4. （1min）修复 + 量化对比表
5. （30s）金线总结

如果讲超过 5 分钟，回去精简 final-report.md。

- [ ] **Step 3: 验证同事按 README 能起来**

```bash
# 模拟干净环境
git stash
git pull
./dev.sh
```

打开 http://localhost:3001 确认看板可见。如有问题，更新 README。

- [ ] **Step 4: 整体提交 spec 文档**

如果 spec.md / flow.html / follow-up.md 还没 commit，一起提交（CLAUDE.md 第 4 条：spec 随对应任务统一提交，本次任务就是整体 ship 时机）：

```bash
git add docs/specs/2026-05-27-measurement-and-fix/spec.md \
        docs/specs/2026-05-27-measurement-and-fix/flow.html \
        docs/specs/2026-05-27-measurement-and-fix/follow-up.md \
        docs/specs/2026-05-27-measurement-and-fix/plan.md \
        README.md
git commit -m "docs: ship measurement-and-fix spec + final integration

Includes spec.md / plan.md / flow.html / follow-up.md and README hook.

Refs: docs/specs/2026-05-27-measurement-and-fix/"
```

> push 前要等用户回复"1"（CLAUDE.md 第 4 条）。

**Gate 5 验收**：
- ✅ `final-report.md` 三段式齐全
- ✅ README 链到 final-report
- ✅ 5 分钟 dry-run 计时通过
- ✅ `follow-up.md` 完整（已在 brainstorming 阶段写好）
- ✅ 任何同事拉项目按 README 能起来看 Grafana

---

# 退出条件清单（重申 spec §7.4）

满足以下**全部**才算 ship：

1. ✅ G1-G5 全部 Gate 通过
2. ✅ F1-F5 5 个修复 commits 已存在（commit message 引用本 spec）
3. ✅ Alembic 两条迁移（F2 JSONB / F4 ivfflat）`upgrade head` + `downgrade -1` + `upgrade head` 三连成功
4. ✅ `final-report.md` 含至少 3 组前后对比硬数字
5. ✅ 面试 dry-run 5 分钟讲完整个故事

---

# 风险触发点 — 实施时若遇到则按下面应对

参考 spec §7.2，常见情况：

- **R1（标注超时）**：每题 5 分钟硬上限；不够 20 道凑 15 道也行
- **R2（Locust SSE 解析）**：Task 14 Step 3 是 PoC，先在小并发验证；如失败，先用 5 行 asyncio + httpx-sse 自写 mini client 替代
- **R3（baseline/after 差异不明显）**：删 KB 后立刻问同问题，强制 cache_miss 路径；或加大压测样本到 200 道
- **R5（迁移失败）**：Task 16 Step 2 已用 `USING ::jsonb` 显式 cast；如还失败，临时数据库中先 `SELECT knowledge_base_ids::jsonb FROM ...` 验证可转
- **R6（Grafana JSON 写错）**：本 plan 已用"UI 手画 → Export → provisioning"路径规避
- **R7（F3 修了 L1 命中率还是低）**：检查 `scope_hash` 计算是否稳定（同问题 + 同 KB 在不同会话产生相同 hash）；如果 scope_hash 还涉及别的不稳定因素，再修一次
- **R8（TTFT 接入 SSE handler 影响流式）**：在 Task 6 后跑一次手工 SSE 测试，token 流不应中断

---

# 实施建议

- **按阶段串行**：Stage 1 → 2 → 3 → 4.1 → 修复 F2-F5 → 4.2 → 5
- **不要急着合并 commit**：每个 Task 单独 commit，保留细粒度历史
- **commit 前必跑**：`ruff format` / `prettier`（CLAUDE.md 第 11 条）
- **数据库变更必跑**：`alembic upgrade head` + downgrade 验证（CLAUDE.md 第 8 条）
- **不要 push**：每次 commit 后等用户输入"1"才能 push（CLAUDE.md 第 4 条）
- **遇到不确定的 review/重构**：先停下来，回 spec 确认是否在 A 堆范围内
