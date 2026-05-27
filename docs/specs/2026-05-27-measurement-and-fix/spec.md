# Spec：测量驱动的修复与可观测性建设

| 字段 | 值 |
|---|---|
| **Spec ID** | `2026-05-27-measurement-and-fix` |
| **作者** | 任孟雪 |
| **创建日期** | 2026-05-27 |
| **预计工时** | 5 个工作日 |
| **状态** | 待 review |
| **关联 review** | Codex 前端 review（3 项）、Claude session 后端 review（4 Critical + 4 Informational） |

---

## 0. 目的与故事主线

### 0.1 项目定位

本项目（offer-copilot）的 README/简历用途主线是**面试讲述**。这次 spec 不追求生产级可观测性的完整性，**追求"测量 → 发现 → 修复 → 验证"的故事闭环**——这是面试官最容易被打动的工程能力叙事。

### 0.2 故事金线（面试 5 分钟可讲完）

> "我给项目加了一套量化指标：rag_telemetry 接 Prometheus + 缓存命中率 + HTTP p95/p99/错误率。**建立指标的过程中**，用这些数据发现了 4 个生产级 bug：L1 缓存命中率接近零（key 把 conv_id 当成隔离维度，违背设计意图）、L2 语义缓存缺向量索引会在数据量上来后全表扫描、流式问答某条分支因为协程对象错误处理直接断流、refresh token 在 5xx 时反而把用户错误登出。我都修了，再回头看指标确认改进。**这就是我做可观测性的真正价值——不是埋点本身，是能持续发现这种问题的能力。**"

### 0.3 输出物

- 3 张 Grafana 看板（RAG / HTTP / Cache），共 14 个 panel
- 5 个 bug 修复（A 堆）
- 评估集（20 道人工 + 50–100 道 LLM 生成）
- 一次 Locust 阶梯压测（修复前 + 修复后两轮）
- `final-report.md`：测量 → 修复 → 验证三段式对比报告
- README "性能与可观测性"一节

---

## 1. 范围与不做项

### 1.1 这次做

**修复（A 堆 5 项，必修）**：

| ID | 问题 | 严重度 |
|---|---|---|
| F1 | 后端 `fts_task.done()` 协程错误（SSE 断流） | P0 |
| F2 | 后端 `Text` 未导入 + `LIKE %{kb_id}%` 误删邻居缓存（合并修） | P0+P1 |
| F3 | 后端 L1 缓存 key 含 `conv_id`，命中率≈0 | INFO（实际影响大） |
| F4 | 后端 `semantic_cache` 缺向量索引 | INFO |
| F5 | 前端 `refreshAccessToken` 5xx 误登出 | P1 |

**测量**：

- `rag_telemetry` 出口接 Prometheus + Grafana
- 缓存命中率埋点（L1 / L2 各一）
- HTTP 层 p95/p99/QPS/错误率（FastAPI middleware）
- 评估集（20 道人工 + 50–100 LLM 生成）
- 一次 Locust 阶梯压测（50/100/200 并发）
- "测量发现 → 修复 → 验证"对比报告

### 1.2 这次不做（YAGNI 边界）

| 不做项 | 理由 |
|---|---|
| **告警系统**（Alertmanager / 通知通道） | 面试故事不靠告警；展示 Grafana 看板就够 |
| **SLO 数字硬承诺**（如"承诺 p95 < 2s"） | 第一版没 baseline，承诺数字是凭空；spec 只定"采集 + 后续如何根据 baseline 定阈值"。面试时讲"我能给出 SLO 框架，但数字必须基于真实数据"反而是加分 |
| **B 堆 5 项背景修复** | 不进这次故事线；写进 `follow-up.md`，spec ship 后单开 PR |
| 生产部署 / CI/CD / Railway | 跑题 |
| OpenTelemetry / Jaeger / Tempo | 单体后端 + Celery，Sentry trace_id 够用；引入 OTel 是过度设计 |
| 限流 / 熔断 | 不是这次故事；且和评估/压测会互相干扰 |
| 多租户压测 / 长尾压测 / 混沌测试 | 单环境单数据集已够讲故事 |

### 1.3 B 堆（背景修复，列入 `follow-up.md`）

| ID | 问题 |
|---|---|
| B1 | `_build_debug_event` None 被 yield 到 SSE |
| B2 | `REFRESH_TOKEN_COOKIE_PATH` 改回 `/api/v1/auth/` |
| B3 | `RAG_DEBUG_ENABLED` 默认 False |
| B4 | chat-page trace 合并 client_id 关联 |
| B5 | askConversation 测试断言滞后 |

---

## 2. 架构总图

### 2.1 实时指标数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户 / Locust 压测流量                       │
└───────────────┬─────────────────────────────────────────────────┘
                │ HTTP / SSE
                ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI (backend, :8000)                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 新增: prometheus_client + middleware                    │    │
│  │  ├─ HTTP 层: 请求数/延迟/状态码 → http_*                │    │
│  │  ├─ RAG 层: 复用现有 rag_telemetry → rag_*              │    │
│  │  └─ Cache 层: L1/L2 命中率 → cache_*                    │    │
│  └────────────────┬────────────────────────────────────────┘    │
│                   │ GET /metrics (Prometheus 格式)               │
└───────────────────┼─────────────────────────────────────────────┘
                    │ pull every 15s
                    ▼
            ┌─────────────────────┐
            │  Prometheus (:9090) │  ← 新增 docker-compose service
            │  本地 TSDB 存 7 天   │
            └──────────┬──────────┘
                       │ PromQL 查询
                       ▼
            ┌─────────────────────┐
            │  Grafana (:3001)    │  ← 新增 docker-compose service
            │  3 张看板（见 §6）   │
            └─────────────────────┘
```

### 2.2 离线评估数据流

```
┌─────────────────────────┐
│  评估集 (JSONL)         │
│  ├─ eval/golden.jsonl   │  ← 20 道人工标注（质量评估）
│  └─ eval/synthetic.jsonl│  ← 50~100 道 LLM 生成（压测用）
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│  backend/scripts/eval/run_eval.py               │  ← 新增
│  ├─ 调用真实 /ask 接口（不 mock）                │
│  ├─ 计算: 引用正确率 / 答案相似度 / 延迟分布     │
│  └─ 输出: docs/specs/<spec-id>/eval-report.md   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  backend/scripts/load_test/locustfile.py        │  ← 新增
│  ├─ 50/100/200 阶梯并发，每档跑 5 分钟           │
│  ├─ SSE client（用 httpx-sse）                  │
│  └─ Locust Web UI :8089 + Prometheus exporter   │
└─────────────────────────────────────────────────┘
            │
            │ HTTP 流量（同时被 Prometheus 抓走）
            ▼
        FastAPI ──► Prometheus ──► Grafana 看板
```

### 2.3 新增基础设施

**`docker-compose.yml` 新增 2 个 service**：

- `prometheus`（端口 `9090`）：本地 TSDB，retention 7 天
- `grafana`（端口 `3001`，避开前端 `3000`）：admin/admin 默认登录

**`dev.sh` 同步更新**（CLAUDE.md 第 10 条强制）：混合模式下 prometheus + grafana 走 Docker。

**新增 `monitoring/` 目录（项目根）**：

```
monitoring/
├── prometheus.yml                          # 抓取配置
└── grafana/
    └── provisioning/
        ├── datasources/prometheus.yml      # 自动连 Prometheus
        └── dashboards/
            ├── dashboards.yml              # 自动加载
            ├── rag.json                    # 看板 1
            ├── http.json                   # 看板 2
            └── cache.json                  # 看板 3
```

Grafana provisioning 的关键作用：**看板用 JSON 描述，随代码进 git；重启容器看板还在**。面试讲点："看板是 IaC，不是手画的"。

### 2.4 关键技术决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 指标采集模式 | Prometheus pull | 业界标准；不需要 push gateway |
| 数据持久化 | 本地 volume，retention 7 天 | 演示够用；不引入云依赖 |
| Grafana 看板分布 | 3 张（RAG / HTTP / Cache） | 一张面试讲一个故事 |
| Locust 跑法 | 本机 CLI，不进 docker-compose | 一次性工具，不需要常驻 |
| 评估脚本调用方式 | HTTP 调真实接口，不 mock | 故事完整：评估用的就是线上链路 |
| 列类型迁移（F2） | JSON → JSONB + GIN 索引 | 故事完整：可讲"为什么从 JSON 升 JSONB" |

---

## 3. 阶段拆分

### 3.1 关键执行策略：先采 baseline，再修复，再对比

故事金线要求"修复前 vs 修复后"的对比数据。两种执行路径：

| 思路 | 描述 | 选择 |
|---|---|---|
| A. **先量化，再修复，再验证** | 埋点完先跑一次 baseline（带 bug 的数据），修复后再跑一次 | ✅ 采用 |
| B. **边修边量** | 看时间序列趋势 | ❌ 面试官追问"修复有效吗"对比不直观 |

多花 30 分钟跑两轮评估/压测，换来一份"前后对比"的硬证据。

### 3.2 五个阶段

```
阶段 1 (0.5d) ──► 阶段 2 (2d) ──► 阶段 3 (1d) ──► 阶段 4 (1d) ──► 阶段 5 (0.5d)
基础设施          埋点+修复        数据准备         评估+压测       故事沉淀
                                                  (跑两轮)
```

> 注：阶段 2 实际呈"循环"结构——A1/A2/A3 + F1 在阶段 3 之前完成，F2/F3/F4/F5 在阶段 4.1 baseline 之后才修。详见 §3.4 执行顺序图。

### 3.3 阶段 1：基础设施铺设（~0.5 天）

**做**：

- `docker-compose.yml` 加 prometheus + grafana service
- `dev.sh` 同步更新
- 后端依赖加 `prometheus-client`
- 写 `monitoring/prometheus.yml`（抓 backend + 占位 locust 端口）
- 写 Grafana provisioning（datasource + 空 dashboard 占位）
- 后端加最小 `/metrics` 端点（先返回默认 Python 指标）

**Gate 1**：

- ✅ `./dev.sh` 起来后 `http://localhost:3001` 能登 Grafana
- ✅ `http://localhost:9090/targets` 显示 backend up
- ✅ `curl http://localhost:8000/metrics` 返回 Prometheus 格式

### 3.4 阶段 2：埋点 + 修复（~2 天，**核心阶段**）

**埋点子任务（A）**：

- A1：现有 `rag_telemetry` 改为 Prometheus metrics（Histogram + Counter）
- A2：缓存命中率埋点（L1 / L2）
- A3：HTTP middleware（请求数 / 延迟 / 状态码）

**修复子任务（F，A 堆 5 项）**：

- F1：后端 `fts_task.done()` 协程错误（改用 `asyncio.ensure_future`）
- F2：后端 `Text` 未导入 + LIKE 误删（合并修：列迁移 JSONB + `.contains([kb_id])`）
- F3：后端 L1 cache key 去掉 `conv_id`
- F4：后端 `semantic_cache` 补 ivfflat 向量索引（新 Alembic 迁移）
- F5：前端 `refreshAccessToken` 返回类型重构

**执行顺序**：

```
A1 → A2 → A3 → F1（先修 SSE，否则没法跑 baseline）
                ↓
   [→ 阶段 3 数据准备]
   [→ 阶段 4.1 baseline]
                ↓
F2 → F3 → F4 → F5（修完后跑 4.2 after）
```

**为什么 F1 不跟 F2–F5 一起放后面**：F1 不修的话 baseline 跑评估时大量 SSE 异常，数据全是噪声，没法当对比基线。

**Gate 2**：

- ✅ Grafana 三张看板都有数据
- ✅ MICRO_RETRIEVAL 路径走通，SSE done 事件正常
- ✅ cache evict 单元测试 + 反向断言通过
- ✅ Alembic 迁移 head 与模型一致
- ✅ `black` / `isort` / `prettier` 跑过

### 3.5 阶段 3：数据准备（~1 天）

**做**：

- 选 3-5 份真实中文技术文档（候选：FastAPI 中文、Pydantic、Next.js 中文、pgvector、Tailwind）
- 通过项目现有上传接口导入
- **人工标注 20 道 Q&A** → `eval/golden.jsonl`：

  ```json
  {"question": "...", "expected_citations": ["doc_id:chunk_id"], "expected_answer_keywords": ["..."], "category": "fact|summary|comparison"}
  ```

- 用 gpt-4o 基于已上传文档生成 50-100 道 → `eval/synthetic.jsonl`（只有 question）

**Gate 3**：

- ✅ `knowledge_bases` 表有 3-5 条记录
- ✅ `eval/golden.jsonl` 行数 ≥ 20
- ✅ `eval/synthetic.jsonl` 行数 50-100
- ✅ 抽查 golden 集 5 条，引用真实存在

### 3.6 阶段 4：评估 + 压测（两轮，~1 天）

**4.1 Baseline 跑（修 F2-F5 之前）**：

- 跑 `run_eval.py` → `report-baseline.md`
- 跑 Locust 50/100/200 阶梯，每档 5 分钟 → 截图保存 `screenshots/baseline/`

**→ 回阶段 2 做 F2-F5**

**4.2 After 跑（修复完成后）**：

- 同样跑评估 + Locust → `report-after.md` + `screenshots/after/`

**评估脚本计算的指标**：

- 引用正确率（expected_citations 至少命中 1 个的比例）
- 答案关键词覆盖率
- 各阶段延迟 p50/p95/p99
- Outcome 分布

**压测看的指标**：

- HTTP p95/p99/throughput/error rate
- L1/L2 缓存命中率（关键：修复前 L1 ≈ 0%，修复后 ≥ 30%）
- RAG 各阶段延迟分布
- 并发上升时哪个阶段先饱和

**Gate 4**：

- ✅ 两轮报告齐全
- ✅ baseline vs after 至少 3 组数字差异显著（必有：L1 命中率、outcome 成功率、L2 lookup p95）
- ✅ 看板截图清晰可作面试材料

### 3.7 阶段 5：故事沉淀（~0.5 天）

**做**：

- 写 `final-report.md`：测量发现 → 修复 → 验证三段式
- 准备 5 个核心截图（命名规范，方便面试时调出）
- README 加一节"性能与可观测性"链到 final-report
- B 堆 backlog 单列 `follow-up.md`

**Gate 5**：

- ✅ Final report 包含至少 3 组"修复前 vs 修复后"的数字
- ✅ 任何同事拉项目按 README 步骤能起来看到 Grafana 看板

---

## 4. 修复清单（A 堆 5 项细节）

### 4.1 F1：MICRO_RETRIEVAL 路径 SSE 断流 [P0]

**定位**：`backend/app/services/qa_service.py:1952`（fts_task 创建）+ `:2231-2237`（finally 块）

**根因**：`_fts_search_scope` 是 `async def`，直接调用返回 coroutine 对象而非 `asyncio.Task`，`fts_task.done()` 抛 `AttributeError`。

**方案 B**：把 `fts_task = _fts_search_scope(...)` 改为 `fts_task = asyncio.ensure_future(_fts_search_scope(...))`，使其真正是 Task，finally 的 `.done()` 生效，保留"防止异步任务泄露"的原始意图。

**测试**：

- 单元：构造 micro_retrieval 场景，断言完整 SSE 流包含 citations + done 事件
- 集成：跑评估集，确认 `outcome=error` 比例 < 1%

**面试故事点**：

> "在 baseline 压测里看到 outcome=error 占了 12%，error_code 显示是 AttributeError。回看代码发现把 coroutine 当 Task 用——这种 bug 没有指标根本看不到，因为前端的体感只是'转圈卡住'。"

### 4.2 F2：删除知识库时缓存清不掉 + 误删邻居缓存 [P0+P1]

**定位**：`backend/app/repositories/qa_repository.py:309-317`

**根因**：两个问题叠加——`Text` 未 import 抛 NameError；`LIKE '%5%'` 会匹配 `[15]`、`[50]`、`[125]` 等无关 KB。

**方案 Y**：将 `knowledge_base_ids` 列类型从 `JSON` 迁移到 `JSONB`，并加 GIN 索引。

**新增 Alembic 迁移要点**：

```python
# upgrade:
#   op.alter_column('semantic_query_caches', 'knowledge_base_ids',
#                   type_=postgresql.JSONB,
#                   postgresql_using='knowledge_base_ids::jsonb')
#   op.create_index('ix_semantic_caches_kb_ids_gin',
#                   'semantic_query_caches', ['knowledge_base_ids'],
#                   postgresql_using='gin')
# downgrade: 反向操作
```

**模型层同步**：`backend/app/models/semantic_cache.py` 的列类型从 `JSON` 改为 `JSONB`，import 改为 `from sqlalchemy.dialects.postgresql import JSONB`。

**Repository 层改写要点**：删除 `func.cast(..., Text).like(f"%{kb_id}%")`，改为 `SemanticCache.knowledge_base_ids.contains([kb_id])`（列已是 JSONB 类型，直接用 contains）。

**测试（关键）**：

- 单元：建 3 条 cache 记录 kb_ids 分别为 `[5]`、`[15]`、`[50]`，调用 `evict_caches_by_kb_id(5)`，断言**只删 [5]，留下 [15] 和 [50]**
- 集成：删 KB 后再问同样问题，验证 L2 不命中

**面试故事点**：

> "原本写的是 LIKE 模糊匹配——这种 bug 测试覆盖不到，因为单元测试只验证'删 [5] 时 [5] 被删'，不会验证'删 [5] 时 [15] 没被删'。我加了'误伤检查'的反向断言。"

### 4.3 F3：L1 缓存命中率≈0 [INFO]

**定位**：`backend/app/services/qa_service.py:1063 / 1641 / 1988`（三处构造同一个 key）

**根因**：key 含 `conv_id`，不同会话相同问题各自一个 key，违背"按问题缓存"的设计意图。

**方案**：key 去掉 `conv_id`，与 L2 对齐：

```
旧：cache:rag:ask:{conv_id}:{scope_hash}:{q_hash}
新：cache:rag:ask:{scope_hash}:{q_hash}
```

**关键考量**：`scope_hash` 已包含 KB ids，而 KB 是 user 私有的，**不需要再加 user_id**。如果不同用户共享同一组 KB（团队场景），scope_hash 相同 → 缓存共享，符合预期复用。

**测试**：

- 单元：构造两个不同 conv_id、相同 scope + question 的请求，第二个应命中 L1
- 集成：跑评估集，看 `cache_lookup_total{layer="l1",result="hit"}` 占比从 0% → > 30%

**面试故事点**：

> "L1 缓存命中率埋点上线后，第一天看到的数字是 0.3%。一开始以为是埋点 bug，后来发现是 key 里塞了 conv_id——这就是为什么要做指标的最直接的例子，单看代码看不出问题，看数字一眼就知道。"

### 4.4 F4：semantic_cache 缺向量索引 [INFO]

**定位**：`backend/alembic/versions/9881eb1b28f5_create_semantic_cache_table.py`

**根因**：建表迁移只建了 question / id 普通索引，没建 `query_vector` 的向量索引。

**方案**：**新增**一个 Alembic 迁移（不修改既有迁移），创建 ivfflat 索引：

```python
# upgrade:
#   op.execute(
#       "CREATE INDEX ix_semantic_caches_query_vector "
#       "ON semantic_query_caches USING ivfflat (query_vector vector_cosine_ops) "
#       "WITH (lists = 100)"
#   )
# downgrade: DROP INDEX
```

**ivfflat vs hnsw 决策**：

- ivfflat 建索引快、查询稍慢、需要预先填一些数据效果才好
- hnsw 建索引慢但查询稳
- **选 ivfflat**——semantic_cache 数据量小（最多几千条），且与现有 `document_chunks` 索引方案保持一致

**前置确认**：执行前 grep `document_chunks` 的索引迁移，确认两者方案一致。如不一致，spec 实施时记录决策原因。

**`lists` 参数**：默认 100，对小表够用；面试可讲"按数据规模调"。

**测试**：

- 性能验证：在 1k / 5k 条记录下分别跑 `find_similar_semantic_cache`，记录 p95
- 关键证据图：Grafana `cache_operation_duration_seconds{layer="l2",operation="lookup"}` 修复前后对比

**面试故事点**：

> "做语义缓存最容易忽略的是——建了 pgvector 列但忘了建索引。我用压测把表灌到 5000 条，p95 查询从 X ms 降到 Y ms（数字以实际跑出来为准）。"

### 4.5 F5：refreshAccessToken 5xx 误登出 [P1]

**定位**：`frontend/src/lib/session.ts:198-203` + 调用方 `frontend/src/lib/http.ts:86`

**根因**：5xx 时返回 `getAccessToken()`（旧 token），调用方把它当**刷新成功**继续重试。如果旧 token 真的过期，后端返回 401，触发 `handleUnauthorizedSession()`，用户被无辜登出。

**方案**：用明确状态区分"刷新临时失败"和"刷新成功"。

**类型重构要点**：

```typescript
// 旧签名：Promise<string | null>
// 新签名：
type RefreshResult =
  | { status: "ok"; token: string }
  | { status: "refresh_failed_retry_later" }
  | { status: "unauthorized" };
```

**调用方 `http.ts` 改动**：

- 收到 `ok` → 用新 token 重试原请求
- 收到 `refresh_failed_retry_later` → **不重试**原请求，让原请求失败上抛
- 收到 `unauthorized` → 走登出流程

**影响面排查**：spec 实施前先 `grep -r "refreshAccessToken" frontend/src` 找出所有调用点，确认每处都正确处理新返回类型。这是 breaking change，需要全量覆盖。

**测试**：

- 单元：mock fetch 返回 500，断言不调 `handleUnauthorizedSession`，原请求得到合理失败
- 集成：手工触发后端 5xx，观察用户不被踢

**面试故事点**：

> "这是一个'用户体验 bug 被错误率指标暴露'的故事——加了 HTTP 错误率埋点后，看到 401 比例偏高的时间窗口和 5xx 完全重合。一查就是 token 刷新逻辑把'临时失败'当'失败'处理了。"

---

## 5. 指标清单（SLI 详单）

### 5.1 设计原则

1. **标签基数控制**：path 用路由模板（`/conversations/{id}`）不用真实 URL；status 用 status_class（`2xx/4xx/5xx`）而非具体 code
2. **Counter / Histogram / Gauge 分明**
3. **命名遵循 Prometheus 官方建议**：Counter 必须 `_total` 结尾，Histogram 单位用秒
4. **不重复埋点**：能从 PromQL 推出来的不单独埋

### 5.2 HTTP 层（FastAPI middleware）

| 指标 | 类型 | Labels | 用途 |
|---|---|---|---|
| `http_requests_total` | Counter | `method`, `path_template`, `status_class` | QPS、错误率 |
| `http_request_duration_seconds` | Histogram | `method`, `path_template` | p50/p95/p99 |
| `http_requests_in_progress` | Gauge | `method`, `path_template` | 并发数 |

**实现要点**：

- `path_template` 取自 `request.scope["route"].path`
- `/metrics` 端点本身**不计入**
- SSE 长连接的 duration **从请求开始到流结束**计

### 5.3 RAG 链路（复用并扩展现有 `rag_telemetry`）

| 指标 | 类型 | Labels | 来源 |
|---|---|---|---|
| `rag_stage_duration_seconds` | Histogram | `stage`（rewrite/vector/fts/rerank/generation） | `*_duration_ms` |
| `rag_total_duration_seconds` | Histogram | `outcome` | `total_duration_ms` |
| `rag_ttft_seconds` ⭐ 新增 | Histogram | — | SSE 首 token 延迟 |
| `rag_outcome_total` | Counter | `outcome`, `error_code` | `outcome` + `error_code` |
| `rag_candidates_count` | Histogram | `stage`（vector/fts/merged/rerank） | `*_candidates_count` |
| `rag_citations_count` | Histogram | — | `citations_count` |
| `rag_cohere_top_score` | Histogram | — | `cohere_top_score` |
| `rag_query_rewritten_total` | Counter | `rewritten` | `retrieval_query_rewritten` |
| `rag_scope_size` | Histogram | — | `scope_size` |

**TTFT 是这次新增**：现有 telemetry 里没有"首 token 延迟"，但这是 RAG 体验的核心指标。实现要点：在 SSE handler 里捕获第一个 token chunk 发出的时刻，记录与请求开始的差值。

**保留原有日志输出**：`_emit_rag_telemetry` 既写日志也增指标，日志用于调试单条请求，指标用于聚合统计。

### 5.4 Cache 层

| 指标 | 类型 | Labels | 用途 |
|---|---|---|---|
| `cache_lookup_total` | Counter | `layer`（l1/l2）, `result`（hit/miss/error） | 命中率（**故事核心**） |
| `cache_operation_duration_seconds` | Histogram | `layer`, `operation`（lookup/set/evict） | L2 索引前后对比 |

**埋点要包裹 lookup 全流程**：包括"L1 miss → 查 L2"的两次 lookup 都各自计 1。

### 5.5 应用元信息

| 指标 | 类型 | Labels | 用途 |
|---|---|---|---|
| `app_info` | Gauge=1 | `version`, `commit_sha`, `env` | 看板顶部展示部署版本 |
| `app_build_timestamp` | Gauge | — | 启动时间 |

### 5.6 衍生 SLI（PromQL 算出来）

| SLI | 公式 | 预期阈值 |
|---|---|---|
| **HTTP 错误率** | `5xx/total` | < 1% |
| **HTTP p95 延迟** | `histogram_quantile(0.95, http_request_duration_seconds)` | < 2s（普通）/ < 8s（/ask） |
| **RAG p95 总耗时** | `histogram_quantile(0.95, rag_total_duration_seconds)` | < 8s |
| **TTFT p95** | `histogram_quantile(0.95, rag_ttft_seconds)` | < 3s |
| **L1 命中率** | `l1_hit / l1_total` | > 30%（修复后） |
| **L2 命中率** | `l2_hit / l2_total` | > 15%（修复后） |
| **RAG 成功率** | `outcome=success / outcome=all` | > 95% |
| **平均引用数** | `avg_over_time(rag_citations_count[5m])` | ≥ 2 |

**阈值列里的数字是预期，不是承诺**。Gate 4.2 后回填 baseline 实测值，按实际分布定 SLO 阈值。

### 5.7 不做的指标

| 不做 | 理由 |
|---|---|
| Celery 队列指标 | 这次故事不讲异步任务 |
| 数据库连接池 | 单实例小规模没意义 |
| OpenAI / Cohere 第三方耗时单独埋 | 已包含在 `rag_stage_duration_seconds` |
| 用户级 / KB 级 cardinality 指标 | 标签基数会爆 |
| `system_*`（CPU/内存/磁盘） | 不是这次故事 |

---

## 6. Grafana 看板设计（精简版，共 14 panel）

### 6.1 共同设计原则

- **顶部摘要、中部分布、底部细节** 三段式
- **同时段对比**：时间轴用 Annotation 标注"修复前/修复后"
- **看板间不重叠**：每张看板讲独立一个故事
- **JSON 化、Provision**：`monitoring/grafana/provisioning/dashboards/*.json` 进 git
- **时间范围默认 1h、刷新 30s**

### 6.2 看板 1：RAG 链路（`rag.json`，5 panel）

**故事主线**：RAG 链路各环节健康度和性能分布

| Panel | 查询 | 类型 |
|---|---|---|
| 成功率 | `sum(rate(rag_outcome_total{outcome="success"}[5m])) / sum(rate(rag_outcome_total[5m]))` | Stat |
| TTFT p95 | `histogram_quantile(0.95, sum by (le)(rate(rag_ttft_seconds_bucket[5m])))` | Stat |
| Total p95 | `histogram_quantile(0.95, sum by (le)(rate(rag_total_duration_seconds_bucket[5m])))` | Stat |
| 5 阶段 p95 主图 | `histogram_quantile(0.95, sum by (le,stage)(rate(rag_stage_duration_seconds_bucket[5m])))` | Time series（多线） |
| outcome 分布 | `sum by (outcome)(rate(rag_outcome_total[5m]))` | Pie |

### 6.3 看板 2：HTTP & SLI（`http.json`，5 panel）

**故事主线**：系统整体可用性、稳定性、扛量能力

| Panel | 查询 | 类型 |
|---|---|---|
| 当前 QPS | `sum(rate(http_requests_total[1m]))` | Stat |
| 错误率 5xx | `sum(rate(http_requests_total{status_class="5xx"}[5m])) / sum(rate(http_requests_total[5m]))` | Stat |
| p95 延迟 | `histogram_quantile(0.95, sum by (le)(rate(http_request_duration_seconds_bucket[5m])))` | Stat |
| QPS 按 status_class 主图 | `sum by (status_class)(rate(http_requests_total[1m]))` | Time series（堆叠） |
| 延迟 p50/p95/p99 三线 | 三个 `histogram_quantile` 查询 | Time series |

### 6.4 看板 3：缓存命中率（`cache.json`，4 panel）

**故事主线**：双层缓存效果（**故事最强**）

| Panel | 查询 | 类型 |
|---|---|---|
| L1 命中率 | `sum(rate(cache_lookup_total{layer="l1",result="hit"}[5m])) / sum(rate(cache_lookup_total{layer="l1"}[5m]))` | Stat |
| L2 命中率 | 同上 `layer="l2"` | Stat |
| 命中率时间序列主图 ★ | L1 + L2 两条线 | Time series（带 annotation） |
| lookup p95 时间序列 | L1 + L2 两条 p95 线 | Time series（带 annotation） |

### 6.5 Annotation 列表

由阶段 5 整理面试材料时手动添加：

| Annotation | 时间点 | 看板 |
|---|---|---|
| `F1 fts_task 修复` | 提交时刻 | RAG |
| `F2 evict bug 修复` | 提交时刻 | RAG / Cache |
| `F3 L1 key 修复` | **关键事件** | **Cache** |
| `F4 ivfflat 索引上线` | **关键事件** | **Cache** |
| `F5 refresh token 修复` | 提交时刻 | HTTP |
| `Baseline 压测开始` | 阶段 4.1 | 三张 |
| `After 压测开始` | 阶段 4.2 | 三张 |

Annotation 不进 JSON 模板（容易失效）；阶段 5 截图时带标注保存到 `screenshots/`。

---

## 7. 验收 / 风险 / 时间

### 7.1 五阶段 Gate（统一汇总）

| Gate | 验收点 |
|---|---|
| **G1 基础设施** | ✅ Grafana :3001 能登录<br>✅ Prometheus targets 显示 backend up<br>✅ `dev.sh` 已同步加 prometheus + grafana 启动逻辑<br>✅ `curl :8000/metrics` 返回 Prometheus 格式 |
| **G2 埋点+修复**（在阶段 4.2 开始前验收，因为 F2-F5 是 baseline 跑完后才修） | ✅ 三张看板都能看到数据<br>✅ MICRO_RETRIEVAL 路径 SSE done 事件正常（F1）<br>✅ `evict_caches_by_kb_id` 单元 + 反向断言通过（F2）<br>✅ L1 lookup 在跨 conv_id 同问题命中（F3）<br>✅ Alembic 迁移 head 与模型一致（F2 + F4）<br>✅ 前端 refreshAccessToken 单元测试覆盖 5xx 不踢人（F5）<br>✅ `black` / `isort` / `prettier` 通过 |
| **G3 数据准备** | ✅ `knowledge_bases` 表 3-5 条<br>✅ `eval/golden.jsonl` ≥ 20 行<br>✅ `eval/synthetic.jsonl` 50-100 行<br>✅ 抽查 golden 集 5 条，引用真实存在 |
| **G4.1 Baseline** | ✅ `report-baseline.md` 生成<br>✅ `screenshots/baseline/` 截图齐全<br>✅ Locust 阶梯压测无中断<br>✅ baseline 数据能明显看到 bug 影响 |
| **G4.2 After** | ✅ `report-after.md` 生成<br>✅ `screenshots/after/` 截图齐全<br>✅ baseline vs after 至少 3 组数字差异显著 |
| **G5 故事沉淀** | ✅ `final-report.md` 三段式完成<br>✅ `follow-up.md` B 堆 5 项列清单<br>✅ README "性能与可观测性"一节链到 final-report<br>✅ 同事拉项目按 README 步骤能起来看到 Grafana 看板 |

### 7.2 风险登记表

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 20 道标注从半天拖到 2 天 | 中 | 阶段 3 顺延 | 模板化、每题 5 分钟硬上限；标注质量 > 数量，凑不齐就 15 道 |
| R2 | Locust SSE 解析意外坑 | 中 | 阶段 4 阻塞 | G1 末写 5 行 PoC 提前验证；备选自写 SSE 客户端 |
| R3 | Baseline 与 after 差异不明显 | 低 | 故事弱 | 故意制造 cache_miss 场景；增大压测样本 |
| R4 | Prometheus 高基数把内存打满 | 低 | 本机卡 | path 用路由模板；retention 限 7 天；标签基数 PR review |
| R5 | Alembic JSONB 迁移数据兼容失败 | 低 | F2 阻塞 | 用 `USING ::jsonb` 显式转换；dev DB 先演练 |
| R6 | Grafana provisioning JSON 写错 | 中 | G1 延 | 用 UI 先手画 → Export JSON → 进 provisioning |
| R7 | F3 修了 L1 key 后命中率仍然低 | 中 | 故事不够强 | 留二次诊断小节；备选讲法：讲埋点发现问题的过程本身 |
| R8 | TTFT 接入需改 SSE handler，触碰流式逻辑 | 中 | F1 周边代码风险 | G2 末做完所有改动后跑一次回归压测 |

### 7.3 时间节点

```
Day 1  ▓▓▓▓▓░░░░░  G1 基础设施 + 阶段 2 启动（A1/A2 埋点）
Day 2  ░░░░░░░░░░  阶段 2：A3 HTTP middleware + F1 SSE 断流修复
Day 3  ░░░░░░░░░░  阶段 3：数据准备（重头：20 道人工标注）
Day 4  ░░░░░▓▓▓▓▓  G4.1 baseline 跑 + F2/F3/F4/F5 修复
Day 5  ░░░░░░░░░░  G4.2 after 跑 + G5 故事沉淀
```

**关键里程碑**：Day 4 中午完成 baseline 截图后，才能放心动 F2-F5。

### 7.4 退出条件

满足以下**全部**才算 ship：

1. ✅ 五个 Gate 都过
2. ✅ A 堆 5 个修复都已 merge（commit 信息引用本 spec）
3. ✅ Alembic 两条迁移（F2 JSONB + F4 ivfflat）在 dev DB 上 `upgrade head` + `downgrade -1` + `upgrade head` 三连成功
4. ✅ `final-report.md` 至少包含 3 组"前后对比"硬数字
5. ✅ 面试自演 dry-run 一次：能用 5 分钟讲完整个故事（计时器为准）

第 5 条是**唯一的主观验收**——这次 spec 的最终目的是面试可讲。

### 7.5 依赖与前置准备

**新增依赖**：

- 后端：`prometheus-client`（`uv add prometheus-client`）
- 工具：`locust`、`httpx-sse`（dev 依赖）

**配置项新增**（`backend/app/core/config.py`）：

- `PROMETHEUS_ENABLED: bool = True`
- `METRICS_PATH: str = "/metrics"`

**docker volume**：

- `prometheus_data`、`grafana_data`

---

## 8. 不收口的开放问题

| Q | 决议时机 |
|---|---|
| SLO 阈值实际数字 | G4.2 后回填到 spec |
| Locust 阶梯并发选 50/100/200 是否合适 | G1 末用 5 并发跑 PoC，看 CPU 占用决定 |
| L2 ivfflat `lists` 参数选 100 还是按规模调 | F4 实施时根据当时 cache 表大小定 |

---

## 9. 附录

### 9.1 关联 Review 报告

- **Codex 前端 review**（2026-05-27）：3 项（1 P1 + 2 P2）
- **Claude session 后端 review**（2026-05-27）：4 Critical（2 P0 + 2 P1）+ 4 Informational

### 9.2 关联文件

- 流程图：[`flow.html`](./flow.html)
- B 堆 backlog：[`follow-up.md`](./follow-up.md)
- 后续生成：`report-baseline.md`、`report-after.md`、`final-report.md`、`screenshots/`

### 9.3 CLAUDE.md 合规检查

- ✅ 第 1 条：简体中文
- ✅ 第 2 条：配置走环境变量
- ✅ 第 7 条：数据库变更走 Alembic（F2 + F4 两条新迁移）
- ✅ 第 8 条：commit 前模型变更同步迁移
- ✅ 第 9 条：spec.md + flow.html 齐备
- ✅ 第 10 条：`dev.sh` 同步更新
- ✅ 第 11 条：black / isort / prettier 进 G2

---

**Spec 状态**：待用户 review。
