# Spec：测量数据质量修复 v2

| 字段 | 值 |
|---|---|
| **Spec ID** | `2026-05-28-measurement-v2-data-quality` |
| **作者** | 任孟雪 |
| **创建日期** | 2026-05-28 |
| **预计工时** | 1.5d（P0 1d + P1 stretch 0.5d） |
| **状态** | Draft |
| **上游依赖** | `2026-05-27-measurement-and-fix`（已完成） |

---

## 0. 背景：v1 的 4 个数据质量硬伤

v1（`2026-05-27-measurement-and-fix`）完成了指标体系搭建 + 5 个 bug 修复，但最终报告的数据量化全部不理想：

| # | 问题 | 影响 |
|---|---|---|
| 1 | **Grafana Cache 看板 "No data"**：L1/L2 命中率、lookup p95 全部无数据 | F3/F4 修复无法量化，故事缺最硬的一块证据 |
| 2 | **评估集 baseline = after = 100%**：20 题 `expected_citations: []` + `expected_answer_keywords: []` 全空，评分公式对空数组默认 pass | 无法证明修复改善了 RAG 质量 |
| 3 | **p95 TTFT/Total 反而上升 14-15%**：报告说"波动范围内"但数字不好看 | 面试故事难讲 |
| 4 | **Locust 并发失败率从 43% 涨到 55%**：根因是 B6（SSE 并发断流）未修 | after 数据反而更差 |

**v2 目标**：修复数据质量问题，让量化对比真正有说服力。不新增功能，只修数据采集和评估集。

---

## 1. 范围与不做项

### 1.1 这次做

| ID | 内容 | 优先级 | 工时 |
|---|---|---|---|
| P0-1 | Grafana Cache 数据修复：排查 `/metrics` 端点确认埋点是否上报 → 修复 → Grafana 出数 | P0 | 0.5d |
| P0-2 | 评估集重做：手工补标 20 道 `expected_citations` + `keywords`，新增 10 道对抗题 | P0 | 0.5d |
| P1 | B6 SSE 并发断流修复（stretch，时间不够则写入 follow-up） | P1 | 1-2d |

### 1.2 这次不做

| 不做项 | 理由 |
|---|---|
| 新增功能 / API | 纯数据质量修复 |
| LLM-as-judge 评估 | 工作量太大，留到后续 spec |
| 全自动评估集生成 | 自循环偏差风险 |
| Alertmanager / 告警 | v1 已明确不做 |

---

## 2. P0-1：Grafana Cache 数据修复

### 2.1 已知事实

- `metrics.py` 中 `CACHE_LOOKUP_TOTAL`、`CACHE_OPERATION_DURATION_SECONDS` 正确定义
- `qa_service.py:1763,2143` 在 `finally` 块中调用 `.labels().inc()`，异常安全
- `RAG_CACHE_L1_ENABLED` / `RAG_CACHE_L2_ENABLED` 默认 `True`
- Prometheus scrape 对 HTTP/RAG 看板正常出数，说明 scrape 链路通
- Cache 看板 PromQL（`cache_lookup_total{l1/l2,hit/miss}`）语义正确

### 2.2 诊断结论（2026-05-27）

**代码无 Bug。** 排查确认：
- `curl /metrics | grep cache_` → HELP/TYPE 行存在，Counter 正确注册
- Prometheus `up{job="backend"}=1` → scrape 正常
- `cache_lookup_total` 无数据点 → 单纯因为后端刚启动，从未有请求经过 cache 路径

**真根因：运维时序问题。** v1 时大概率是 Prometheus 在评估/locust 跑完后才启动，或后端在检查 Grafana 前重启（Counter 归零）。

**修复：无需改代码。** 只需确保启动顺序——Prometheus 先于评估运行，后端不在中途重启。

### 2.3 验证脚本

```
Step 1: curl localhost:8000/metrics | grep cache_
        → 有输出 = 埋点上报正常，问题在 PromQL/Grafana
        → 无输出 = 埋点未上报，问题在 Python/Prometheus client

Step 2: 如果无输出 → 检查 prometheus_client REGISTRY
        → 在 metrics.py 末尾加 print(list(REGISTRY._collector_to_names.keys()))
        → 确认 Counter 是否注册到默认 registry

Step 3: 如果有输出但 Grafana 无数据 → 检查 Prometheus scrape 状态
        → curl localhost:9090/api/v1/query?query=cache_lookup_total
        → 确认 Prometheus 是否抓到了这些指标

Step 4: 如果 Prometheus 有数据但 Grafana 无 → 检查 Grafana data source / PromQL
```

### 2.4 验证标准

- Grafana Cache 看板 4 个 panel 全部出数
- L1 命中率能跑出非零值（修复 F3 后理论上应有命中）
- L2 lookup p95 有时间序列数据

---

## 3. P0-2：评估集重做

### 3.1 根因

`eval/golden.jsonl` 20 道题全部：
```json
{"expected_citations": [], "expected_answer_keywords": []}
```

`run_eval.py` 评分公式：
```python
def citation_match(expected, actual):
    if not expected:
        return True  # 注释自认"指标会失真"

def keyword_coverage(keywords, answer):
    if not keywords:
        return 1.0
```

→ baseline=100% 是评分伪阳性，不是 RAG 真的好。

### 3.2 修复方案

**Step 1：手工补标 20 道现有题**

逐条标注 `expected_citations`（格式 `"chunk:N"`）和 `expected_answer_keywords`（至少 3 个关键词）。标注时对照 KB id=4（FastAPI 文档）的实际 chunk 内容。

格式：
```json
{"question": "如何使用 FastAPI 的特性", "kb_id": 4, "expected_citations": ["chunk:12", "chunk:15"], "expected_answer_keywords": ["路径参数", "依赖注入", "数据验证"]}
```

**Step 2：新增 10 道对抗题**

| 类型 | 数量 | 预期行为 | 验证点 |
|---|---|---|---|
| 无答案题 | 3 | 引用为空 / 回答表示不知道 | `expected_citations: []`，outcome 仍 success |
| 跨 KB 题 | 3 | 仅引用 KB=4 的 chunk | citation 不串到其他 KB |
| 歧义题 | 2 | 回答覆盖多种解释 | 关键词覆盖至少 1 种 |
| 超长上下文截断 | 2 | 引用 chunk 完整 | 不丢尾部 chunk |

**Step 3：跑 baseline + after 对比**

- 用新评估集跑 `run_eval.py --label baseline`（当前代码）
- 跑 `run_eval.py --label after`（确认无回归）
- 预期：baseline 不再 100%（对抗题会把成功率拉下来），after ≥ baseline

### 3.3 验证标准

- baseline 成功率 < 100%（对抗题生效）
- baseline citation 命中率 < 100%
- after 各指标 ≥ baseline
- 失败样本能对应到具体对抗题类型

---

## 4. P1（Stretch）：B6 SSE 并发断流

### 4.1 现象

Locust 并发场景下 "no done event in stream" 错误占比 50-80%，sequential 评估不触发。

### 4.2 根因假设

- SSE 流控在并发下有 anyio task group 竞争
- httpx stream 取消时未正确清理 Redis Pub/Sub 订阅
- `asyncio.Task` 对象生命周期管理问题（F1 修了 `.done()` 但可能有更多同类问题）

### 4.3 排查思路

1. 单独 Locust 跑 `/api/v1/conversations/*/ask`，对照 fts_task / SSE done 日志
2. 加 `RAG_DEBUG_ENABLED=True` 看 debug event 流是否完整
3. 检查 anyio task group 取消传播路径

### 4.4 决策

时间充裕则修；时间不够则在 final-report 中诚实写"并发场景 SSE 有更深问题，列为 B6 后续修复"。

---

## 5. 技术方案

- **采用方案**：手工排查 + 补标（非自动化生成）
- **关键决策理由**：
  - P0-1：先 curl 拿证据再修，避免盲目改代码
  - P0-2：手工标注质量可控，30 道足够讲面试故事；LLM 自动生成有自循环偏差风险
- **依赖的现有模块**：`metrics.py`、`qa_service.py`、`run_eval.py`、`golden.jsonl`、Grafana provisioning JSON

---

## 6. 数据模型

无新增表/字段。仅修改 `eval/golden.jsonl` 内容。

---

## 7. TODO 清单

- [ ] P0-1a：curl /metrics 验证 cache 埋点是否上报 ⚠️ 风险：可能需要在 uvicorn reload 模式下手动验证
- [ ] P0-1b：修复 cache metrics 上报问题并验证 Grafana 出数
- [ ] P0-2a：手工补标 20 道现有题目
- [ ] P0-2b：新增 10 道对抗题
- [ ] P0-2c：跑 baseline + after 评估并生成对比报告
- [ ] P1（stretch）：排查 B6 SSE 并发断流根因并修复

---

## 8. 测试计划

- P0-1：`curl /metrics | grep cache_` 有输出；Grafana Cache 看板 4 panel 全部出数
- P0-2：baseline 成功率 < 100%；after ≥ baseline；失败样本可追溯
- P1：Locust 50 并发 "no done event" 错误率显著下降
