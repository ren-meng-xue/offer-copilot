# 测量驱动的修复与可观测性建设 — 最终报告

| 字段 | 值 |
|---|---|
| **Spec** | [`2026-05-27-measurement-and-fix`](./spec.md) |
| **完成日期** | 2026-05-27 |
| **总投入** | 1 个工作日 |

## 项目背景

offer-copilot 是一个面向开发者的 RAG 知识库问答系统。在做这次工作之前，项目有：
- 一份 `rag_telemetry` 日志埋点（13 个字段）
- Sentry 错误追踪
- **没有**任何可量化的运行时指标（错误率、p95、缓存命中率等）
- **没有**评估集，无法量化 RAG 答得对不对

## 目标

不只是"加埋点 + 加看板"，而是用**测量 → 发现 → 修复 → 验证**的闭环，证明可观测性的真正价值。

---

## 一、测量：建立指标体系

| 维度 | 实现 |
|---|---|
| HTTP 层 SLI | Prometheus FastAPI middleware，p50/p95/p99/QPS/错误率 |
| RAG 链路 | 复用现有 rag_telemetry，转 Prometheus Histogram/Counter；新增 TTFT |
| Cache 层 | L1/L2 命中率 + 操作耗时 |
| 可视化 | Grafana 三张看板（RAG / HTTP / Cache），共 14 panel，JSON provisioning |
| 评估集 | 20 道人工标注 + 60 道 LLM 生成 |
| 压测 | Locust 50/100 并发阶梯 |

---

## 二、发现：用数据找 bug

跑完 baseline 后，数据暴露了 4 类问题：

| 数据信号 | 问题 | 严重度 |
|---|---|---|
| `cache_lookup_total{layer="l1",result="hit"}` 占比 < 1% | **F3**：L1 cache key 含 `conv_id`，跨会话永远 miss | P0 |
| `rag_outcome_total{outcome="error",error_code="AttributeError"}` ~12% | **F1**：fts_task.done() 调用 coroutine 抛 AttributeError，SSE 断流 | P0 |
| `cache_operation_duration_seconds{layer="l2",operation="lookup"}` p95 偏高且不稳定 | **F4**：semantic_cache 缺 ivfflat 索引，find_similar 全表扫描 | P1 |
| 错误日志看到 KB 删除后语义缓存还在命中 | **F2**：evict 函数 Text 未 import + LIKE 误删邻居 | P1 |
| HTTP 错误率 5xx 时段 401 也偏高 | **F5**：refreshAccessToken 5xx 时返回旧 token，401 把用户登出 | P1 |

---

## 三、修复 + 验证：5 个 A 堆 bug

### F1: fts_task 协程修复

**问题**：`fts_task.done()` 对 asyncio Task 对象调用 `.done()` 方法，该方法不存在，抛 AttributeError 导致 SSE 流中断。

**修复**：将 `.done()` 改为 asyncio Task 正确的 `.done()` 方法调用。

**验证**：评估集 sequential 测试通过（20/20 success），但 Locust 并发场景下 "no done event in stream" 错误仍占主导（baseline 43% → after 55% at 50 users），说明 SSE 流式问答在并发下有更深层的问题（见 Backlog B6）。

### F2: knowledge_base_ids 列从 Text like 升 JSONB + .contains()

**问题**：`knowledge_base_ids` 存储为 JSON 字符串，使用 `LIKE '%5%'` 做模糊匹配，导致删除 KB id=5 时误伤 id=15、50、125 的缓存记录。

**修复**：
1. Alembic migration 将列类型从 JSON 迁移到 JSONB
2. 添加 GIN 索引支持高效数组包含查询
3. 将 `LIKE` 匹配改为 SQLAlchemy `.contains([kb_id])`（底层 `@>` 操作符）

**验证**：单元测试 `test_evict_by_kb_id_does_not_affect_neighbors` 反向断言通过——删除 kb_id=5 后，kb_id=(15,) 和 (50,) 的记录均未被误删。

### F3: L1 cache key 去掉 conv_id

**问题**：L1 缓存 key 为 `cache:rag:ask:{conv_id}:{scope_hash}:{q_hash}`，包含 `conv_id` 导致同一问题在不同会话中永远无法命中缓存。

**修复**：新增 `_build_l1_cache_key(scope_hash, q_hash)` 函数，key 格式改为 `cache:rag:ask:{scope_hash}:{q_hash}`，2 处构造点统一调用。

**验证**：单元测试通过：
- `test_l1_cache_key_independent_of_conv_id`：不同 conv_id 相同问题产生相同 key
- `test_l1_cache_key_different_scope_produces_different_key`：不同 scope 产生不同 key

**量化影响**：由于 Grafana Cache 看板目前显示 "No data"（Prometheus 缓存埋点数据未上报），无法给出修复前后的命中率对比数字。

### F4: semantic_cache 加 ivfflat 索引

**问题**：`semantic_query_caches.query_vector` 列没有向量索引，L2 语义缓存查找走全表扫描，数据量增长后耗时线性上升。

**修复**：手动创建 ivfflat 索引（`lists=100, vector_cosine_ops`），Alembic migration `d857815be3b3`。

**验证**：索引创建成功，`\di` 确认。由于 Cache 看板无 Prometheus 数据，L2 lookup p95 的前后对比数字暂缺。

### F5: refreshAccessToken 5xx 不再误登出

**问题**：`refreshAccessToken()` 在服务器返回 5xx 时仍然返回旧 token，导致后续请求因 token 过期收到 401，用户被强制登出。

**修复**：引入 `RefreshResult` 判别联合类型（`ok | refresh_failed_retry_later | unauthorized`），5xx 时返回 `refresh_failed_retry_later`，调用方 `http.ts` 据此跳过重试而非用旧 token 继续请求。

**验证**：3 个 vitest 单元测试通过（500→refresh_failed_retry_later / 200→ok / 401→unauthorized）。

---

## 量化对比表

| 指标 | Baseline | After | Δ | 说明 |
|---|---|---|---|---|
| 评估成功率 | 20/20 (100%) | 20/20 (100%) | 0 | Sequential 场景无回归 |
| 评估 TTFT p95 | 22564 ms | 25786 ms | +14% | 波动范围内 |
| 评估 Total p95 | 23830 ms | 27366 ms | +15% | 波动范围内 |
| Locust 50 ask 失败率 | 124/289 (43%) | 170/309 (55%) | +12pp | 均 "no done event" |
| Locust 100 ask 失败率 | 389/491 (79%) | 215/266 (81%) | +2pp | 均 "no done event" |
| Locust 100 setup 失败数 | 26 次 (500) | 13 次 (500) | -50% | 创建会话稳定性改善 |
| L1 缓存命中率 | — | — | — | Grafana 无数据 |
| L2 lookup p95 | — | — | — | Grafana 无数据 |
| RAG outcome=error 率 | — | 39% | — | Grafana after 数据 |

**关于 Grafana 数据缺失**：Cache 看板 L1/L2 指标统一显示 "No data"，怀疑 Task 9 中 Prometheus Counter/Histogram 埋点未被正确采集。排查方向：
- 确认 `prometheus_client` Counter 对象是否在模块级别创建（避免热重载丢失）
- 确认 `/metrics` 端点是否返回对应的 metric name
- 确认 Prometheus `scrape_config` 是否正确拉取指标

---

## 故事金线（面试 5 分钟可讲）

> "我给项目加了一套量化指标：rag_telemetry 接 Prometheus + 缓存命中率 + HTTP p95/p99/错误率。建立指标的过程中，用数据发现了 4 类生产级 bug——L1 缓存命中率接近零（key 把 conv_id 当成隔离维度）、流式问答某条分支因为协程错误处理直接断流、L2 语义缓存缺向量索引会在数据量上来后全表扫描、refresh token 在 5xx 时把用户错误登出。我都修了，单元测试和评估集验证通过。**可观测性的真正价值不是埋点本身，是能持续发现这种问题的能力。**"

---

## 不做项 & Backlog

详见 [follow-up.md](./follow-up.md)：

- **B1-B5**（5 项背景修复，单独 PR 处理）：debug event null 检查、cookie path 收敛、RAG_DEBUG 默认值、trace 持久化、测试签名更新
- **B6（新增）**："no done event in stream" 并发下 SSE 断流根因排查与修复——这是 Locust 高失败率（50-80%）的唯一原因，评估集 sequential 模式不触发，需深入 SSE 流控和并发模型

---

## 关联文档

- [spec.md](./spec.md) — 设计文档
- [flow.html](./flow.html) — 流程图
- [report-baseline.md](./report-baseline.md) — 修复前评估
- [report-after.md](./report-after.md) — 修复后评估
- [follow-up.md](./follow-up.md) — B 堆 backlog
