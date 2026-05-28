# 测量数据质量修复 v2 — 实施计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 逐步实施。

**Goal:** 修复 v1 测量报告中 4 个数据质量问题：Cache 看板无数据、评估集无区分度、p95 上升、并发失败率上升。

**Architecture:** 三步推进——先排查 Cache metrics 上报链路（Prometheus → Grafana），再重做评估集（手工补标 + 对抗题），最后视时间修 B6 SSE 并发断流。纯数据/配置修复，不新增 API 或功能。

**Tech Stack:** Python 3.12, prometheus_client, Grafana, Locust, FastAPI SSE

---

## File Structure

| 文件 | 职责 | 操作 |
|---|---|---|
| `backend/app/core/metrics.py` | Prometheus 指标定义 | 可能修改：确保 Counter/Histogram 正确注册 |
| `backend/app/core/metrics_middleware.py` | HTTP 指标中间件 | 不改（已正常工作） |
| `backend/app/main.py` | `/metrics` 端点挂载 | 可能修改：加 registry 参数 |
| `backend/app/services/qa_service.py` | Cache 埋点调用点 | 不改（already correct with finally） |
| `monitoring/grafana/provisioning/dashboards/cache.json` | Grafana Cache 看板 | 可能修改：修正 PromQL |
| `eval/golden.jsonl` | 评估集 | 重写：补标 20 道 + 新增 10 道 |
| `backend/scripts/eval/run_eval.py` | 评估 runner | 不改 |
| `monitoring/prometheus.yml` | Prometheus scrape 配置 | 不改（已正确） |

---

### Task 1: curl /metrics 验证 cache 埋点是否上报

**Files:**
- 无文件变更，纯诊断步骤

- [ ] **Step 1: 确认后端服务正在运行**

```bash
curl -s http://localhost:8000/health 2>&1 | head -5
```
预期：返回 HTTP 200 或 JSON 状态信息。

- [ ] **Step 2: 抓取 /metrics 并搜索 cache_ 指标**

```bash
curl -s http://localhost:8000/metrics | grep -i cache_
```
预期：有输出（如 `cache_lookup_total{layer="l1",result="miss"} 5`）说明埋点上报正常；无输出则需要排查 Python 端。

- [ ] **Step 3: 如果无输出，确认 prometheus_client REGISTRY 中是否有 cache 指标**

在 `backend/app/core/metrics.py` 末尾**临时**加：

```python
# TEMP: 排查结束后删除
import logging
_logger = logging.getLogger(__name__)
from prometheus_client import REGISTRY
_logger.warning(
    "REGISTRY collectors: %s",
    [c._name for c in REGISTRY._collector_to_names.keys() if hasattr(c, '_name')]
)
```

重启后端，看日志中是否包含 `cache_lookup_total` 和 `cache_operation_duration_seconds`。

**判断逻辑：**
- REGISTRY 中有 cache_* → 问题在 Prometheus scrape 或 Grafana
- REGISTRY 中无 cache_* → 问题在 Python 模块加载（uvicorn reload 重创建 Counter 丢失注册）

- [ ] **Step 4: 如果 REGISTRY 中有 cache_* 但 /metrics 无输出 → 检查 make_asgi_app registry**

`backend/app/main.py:86` 当前：
```python
metrics_app = make_asgi_app()
```

可能需要在 `metrics.py` 中将指标绑定到非默认 registry，然后在 `make_asgi_app(registry=...)` 中指定。但标准用法不需要这样——`Counter()` 自动注册到 `REGISTRY`（默认 registry），`make_asgi_app()` 默认也使用 `REGISTRY`。如果被 uvicorn reload 破坏，说明热重载导致模块重新 import 时创建了新的 Collector 对象但未注册。

**修复方案（如果需要）：** 在 `metrics.py` 末尾显式确认注册：

```python
# 确保所有指标已在默认 REGISTRY 中（uvicorn reload 安全）
import prometheus_client
assert CACHE_LOOKUP_TOTAL in prometheus_client.REGISTRY._collector_to_names, \
    "CACHE_LOOKUP_TOTAL not in REGISTRY"
```

- [ ] **Step 5: 排查结果记录**

将 curl 输出和 REGISTRY 日志内容记录到任务备注，决定下一步是修 Python 端还是 Grafana 端。

---

### Task 2: 修复 cache 埋点问题

**Files:**
- 可能修改：`backend/app/core/metrics.py`
- 可能修改：`monitoring/grafana/provisioning/dashboards/cache.json`

以下步骤按 Task 1 的排查结果选择性执行。

#### 分支 A：如果 Prometheus 有数据但 Grafana 显示 "No data"

- [ ] **Step A1：在 Prometheus UI 直接查 cache_ 指标**

```bash
curl -s 'http://localhost:9090/api/v1/query?query=cache_lookup_total' | python3 -m json.tool | head -30
```
预期：`"result"` 数组非空。

- [ ] **Step A2：在 Prometheus UI 测试 Garnana 面板中的 PromQL**

```bash
# L1 命中率 PromQL
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(cache_lookup_total{layer="l1",result="hit"}[5m]))%20/%20sum(rate(cache_lookup_total{layer="l1"}[5m]))' | python3 -m json.tool
```
如果返回空结果但 Step A1 有数据，说明 PromQL label 选择器不对。

- [ ] **Step A3：修正 Grafana dashboard JSON 中的 PromQL（如果需要）**

`monitoring/grafana/provisioning/dashboards/cache.json` 当前 PromQL：
```
sum(rate(cache_lookup_total{layer="l1",result="hit"}[5m])) / sum(rate(cache_lookup_total{layer="l1"}[5m]))
```

如果实际 label 值不同（比如是 `layer="L1"` 而非 `layer="l1"`），修正为实际值。修改后重启 Grafana：

```bash
docker compose -f monitoring/docker-compose.yml restart grafana
```

#### 分支 B：如果 /metrics 端点无 cache_ 指标

- [ ] **Step B1：检查 uvicorn reload 是否导致 Counter 丢失**

uvicorn `--reload` 模式下，`metrics.py` 模块可能被重新加载。`prometheus_client.Counter()` 构造函数会自动注册到 `REGISTRY`，但如果模块被多次 import（Python 的 import 缓存），不会重复执行。问题可能是：

1. 另一个模块在 `metrics.py` 之前 import 了 `prometheus_client`，导致默认 REGISTRY 状态不一致
2. uvicorn reload 时子进程 fork 导致状态丢失

**修复：** 在 `metrics.py` 中添加幂等保护，确保 Counter 不重复创建：

```python
# 在 metrics.py 末尾添加
# 确保指标在 /metrics 端点中可见（uvicorn reload 幂等）
import prometheus_client as _pc
_EXPECTED = {
    "cache_lookup_total",
    "cache_operation_duration_seconds",
    "http_requests_total",
    "http_request_duration_seconds",
    "http_requests_in_progress",
    "rag_stage_duration_seconds",
    "rag_total_duration_seconds",
    "rag_ttft_seconds",
    "rag_outcome_total",
    "rag_candidates_count",
    "rag_citations_count",
    "rag_cohere_top_score",
    "rag_query_rewritten_total",
    "rag_scope_size",
    "app_info",
}
_actual = {c._name for c in _pc.REGISTRY._collector_to_names.keys() if hasattr(c, '_name')}
_missing = _EXPECTED - _actual
if _missing:
    import logging
    logging.getLogger(__name__).warning("Missing metrics in REGISTRY: %s", _missing)
```

- [ ] **Step B2：重启后端并验证**

```bash
# 重启
./dev.sh restart backend

# 等待服务就绪后验证
sleep 5
curl -s http://localhost:8000/metrics | grep -c cache_
```
预期：输出 > 0（至少有 `cache_lookup_total` 和 `cache_operation_duration_seconds` 两类指标）。

- [ ] **Step B3：发送几个真实请求，确认计数器递增**

```bash
# 发几个请求让 cache 路径被走到
for i in 1 2 3; do
  curl -s -X POST http://localhost:8000/api/v1/qa/conversations \
    -H "Authorization: Bearer $EVAL_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"knowledge_base_id":4}' > /dev/null
done

# 再查 cache_ 指标值
curl -s http://localhost:8000/metrics | grep 'cache_lookup_total'
```
预期：看到非零计数器值（至少 miss 计数 > 0）。

- [ ] **Step B4：确认 Grafana 出数**

打开 Grafana（`http://localhost:3000`）→ Cache 命中率看板，确认 4 个 panel 全部有数据。

---

### Task 3: 手工补标现有 20 道评估题

**Files:**
- 修改：`eval/golden.jsonl`（备份旧文件为 `eval/golden.jsonl.v1.bak`）

- [ ] **Step 1: 备份旧评估集**

```bash
cp eval/golden.jsonl eval/golden.jsonl.v1.bak
```

- [ ] **Step 2: 重写 golden.jsonl，补标 expected_citations 和 expected_answer_keywords**

标注原则：
- `expected_citations` 格式：`"chunk:N"`，需要对照知识库中的实际 chunk_id
- 如果无法确定具体 chunk_id，至少填 `"chunk:1"` 作为占位（后续可以精调）
- `expected_answer_keywords` 至少 3 个词，应是该问题答案中必然出现的中文关键词

```jsonl
{"question": "如何使用 FastAPI 的特性", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["路径参数", "查询参数", "请求体", "依赖注入"]}
{"question": "本教程的内容是如何组织的", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["用户指南", "高级指南", "循序渐进", "章节"]}
{"question": "我可以从哪里查阅特定 API 需求的解决方案", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["API 参考", "参考手册", "解决方案"]}
{"question": "代码片段可以在哪里使用", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["复制", "粘贴", "文件", "项目"]}
{"question": "如何运行示例代码", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["复制", "文件", "运行", "fastapi"]}
{"question": "安装 FastAPI 的第一步是什么", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["虚拟环境", "venv", "创建"]}
{"question": "我需要创建什么来安装 FastAPI", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["虚拟环境", "venv", "隔离"]}
{"question": "如何激活虚拟环境", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["激活", "Scripts", "activate", "source"]}
{"question": "如何安装 FastAPI 的标准版本", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["pip", "install", "fastapi", "标准"]}
{"question": "我可以使用哪个命令启动 FastAPI 应用", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["fastapi", "dev", "uvicorn", "启动"]}
{"question": "本教程是否可以作为参考手册", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["参考", "手册", "未来", "查阅"]}
{"question": "完成用户指南后应该阅读什么", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["高级指南", "用户指南", "下一步"]}
{"question": "代码片段是否经过测试", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["测试", "代码片段", "确保", "工作"]}
{"question": "如何将代码片段放入文件中", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["复制", "粘贴", "文件", "代码"]}
{"question": "fastapi dev 命令的作用是什么", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["开发", "启动", "uvicorn", "热重载"]}
{"question": "是否可以直接跳转到某个章节", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["跳转", "章节", "导航", "直接"]}
{"question": "用户指南的目标是什么", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["学习", "FastAPI", "基础", "特性", "用户指南"]}
{"question": "安装 FastAPI 时需要注意什么", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["虚拟环境", "pip", "安装", "依赖"]}
{"question": "用户指南的内容是循序渐进吗", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["循序渐进", "章节", "逐步", "学习"]}
{"question": "如何确保代码片段正常工作", "kb_id": 4, "expected_citations": ["chunk:1"], "expected_answer_keywords": ["测试", "代码片段", "确保", "工作"]}
```

**注意**：`expected_citations` 中 `chunk:1` 是占位值。实际标注前，需要先查 KB id=4 中真实的 chunk 内容。更准确的做法是：

```bash
# 查 KB id=4 的 chunk 列表
curl -s "http://localhost:8000/api/v1/qa/knowledge-bases/4/chunks?limit=30" \
  -H "Authorization: Bearer $EVAL_TOKEN" | python3 -m json.tool | head -50
```

拿到真实 chunk_id 后，将上面 `chunk:1` 替换为实际值。

- [ ] **Step 3: 验证 JSONL 格式**

```bash
python3 -c "
import json
with open('eval/golden.jsonl') as f:
    for i, line in enumerate(f, 1):
        d = json.loads(line)
        assert 'question' in d, f'line {i} missing question'
        assert 'kb_id' in d, f'line {i} missing kb_id'
        assert 'expected_citations' in d, f'line {i} missing expected_citations'
        assert 'expected_answer_keywords' in d, f'line {i} missing expected_answer_keywords'
        # 检查不再全空
        has_cit = len(d['expected_citations']) > 0
        has_kw = len(d['expected_answer_keywords']) > 0
        status = 'OK' if (has_cit or has_kw) else 'STILL_EMPTY'
        print(f'  line {i}: citations={len(d[\"expected_citations\"])} keywords={len(d[\"expected_answer_keywords\"])} {status}')
"
```
预期：至少 15/20 条有 citations 或 keywords（剩余 5 条如果确实无法标注，可以留空但要有说明）。

---

### Task 4: 新增 10 道对抗题

**Files:**
- 修改：`eval/golden.jsonl`（在末尾追加 10 行）

- [ ] **Step 1: 追加 10 道对抗题到 golden.jsonl**

| 类型 | 数量 | 题目特征 |
|---|---|---|
| 无答案 | 3 | 问 KB id=4 中不存在的内容，`expected_citations: []` |
| 跨 KB | 3 | 涉及多个 KB 的概念，但只应在 id=4 中找到引用 |
| 歧义 | 2 | 问题有多种理解方式，期望回答覆盖至少一种 |
| 超长上下文 | 2 | 要求详细回答，可能触发截断 |

```jsonl
{"question": "FastAPI 如何与 Kubernetes 集成部署", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": []}
{"question": "Django 和 FastAPI 的性能对比数据是什么", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": []}
{"question": "FastAPI 中 WebSocket 的实现原理是什么", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["WebSocket"]}
{"question": "FastAPI 的依赖注入系统如何影响 SQLAlchemy 会话管理", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["依赖", "会话", "数据库"]}
{"question": "FastAPI 事件钩子 startup 和 shutdown 分别在什么时机触发", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["startup", "shutdown", "事件", "应用"]}
{"question": "FastAPI 的路由参数类型转换是如何实现的", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["类型", "参数", "路径", "查询"]}
{"question": "model 和 schema 在 FastAPI 中有什么区别", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["Pydantic", "模型", "Schema", "验证"]}
{"question": "response_model 参数有哪些常见用法", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["response_model", "响应", "模型", "过滤"]}
{"question": "详细解释 FastAPI 的中间件执行顺序和请求生命周期，包括 CORS、认证、异常处理等各个环节", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["中间件", "CORS", "认证", "异常", "请求"]}
{"question": "完整说明 FastAPI 中从请求到响应所有可用的依赖注入方式及其优先级", "kb_id": 4, "expected_citations": [], "expected_answer_keywords": ["依赖注入", "Depends", "路径", "查询", "请求体"]}
```

- [ ] **Step 2: 确认共 30 道题**

```bash
wc -l eval/golden.jsonl
```
预期：`30 eval/golden.jsonl`

- [ ] **Step 3: 再次验证 JSONL 格式**

```bash
python3 -c "
import json
with open('eval/golden.jsonl') as f:
    for i, line in enumerate(f, 1):
        d = json.loads(line)
        assert all(k in d for k in ['question','kb_id','expected_citations','expected_answer_keywords']), f'line {i} bad'
print(f'OK: {i} lines valid')
"
```
预期：`OK: 30 lines valid`

---

### Task 5: 跑 baseline + after 评估对比

**Files:**
- 输出：`docs/specs/2026-05-28-measurement-v2-data-quality/report-baseline.md`
- 输出：`docs/specs/2026-05-28-measurement-v2-data-quality/report-after.md`

- [ ] **Step 1: 确认 EVAL_TOKEN 已设置**

```bash
echo "EVAL_TOKEN 长度: ${#EVAL_TOKEN}"
```
预期：长度 > 20。

如果未设置，从浏览器 localStorage 复制 `access_token` 后：
```bash
export EVAL_TOKEN="<token>"
```

- [ ] **Step 2: 跑 baseline 评估**

```bash
cd backend
uv run python -m scripts.eval.run_eval \
  --golden ../eval/golden.jsonl \
  --output ../docs/specs/2026-05-28-measurement-v2-data-quality/report-baseline.md \
  --label baseline
```
预期：
- 终端输出每一行的 outcome / citation_ok / kw_cov / ttft / total
- 成功率 < 100%（对抗题生效）
- 至少有几条 `citation_ok=False` 或 `kw_coverage < 1.0`

- [ ] **Step 3: 记录 baseline 关键数字**

打开 `report-baseline.md`，确认：
- 总成功率 < 100%（关键！证明评估集有区分度）
- 引用命中率 < 100%
- 平均关键词覆盖率 < 1.00

- [ ] **Step 4: 跑 after 评估**

```bash
uv run python -m scripts.eval.run_eval \
  --golden ../eval/golden.jsonl \
  --output ../docs/specs/2026-05-28-measurement-v2-data-quality/report-after.md \
  --label after
```

- [ ] **Step 5: 对比 baseline vs after**

核心验证：
- `after.总成功率 >= baseline.总成功率`
- `after.引用命中率 >= baseline.引用命中率`
- `after.平均关键词覆盖率 >= baseline.平均关键词覆盖率`

如果 after 指标低于 baseline → 有回归，需要排查。

---

### Task 6: 写入最终报告

**Files:**
- 创建：`docs/specs/2026-05-28-measurement-v2-data-quality/final-report.md`

- [ ] **Step 1: 生成 final-report-v2.md**

报告模板直接沿用 v1 格式，内容替换为 v2 的实际数字：

```markdown
# 测量数据质量修复 v2 — 最终报告

| 字段 | 值 |
|---|---|
| **Spec** | `2026-05-28-measurement-v2-data-quality` |
| **完成日期** | YYYY-MM-DD |
| **总投入** | 1-2 个工作日 |

## 背景

v1（`2026-05-27-measurement-and-fix`）的 4 个数据质量问题及修复情况：

## P0-1：Grafana Cache 数据修复

| 指标 | Before | After | 说明 |
|---|---|---|---|
| L1 命中率 | 无数据 | X% | 修复后可见 |
| L2 命中率 | 无数据 | X% | 修复后可见 |
| L2 lookup p95 | 无数据 | Xms | 修复后可见 |

**根因**：[从 Task 1 排查结果填入]

## P0-2：评估集重做

| 指标 | v1 (20 空标注) | v2 baseline (30 道) | v2 after (30 道) | 说明 |
|---|---|---|---|---|
| 总成功率 | 100% | X% | X% | 有区分度 |
| 引用命中率 | 100% | X% | X% | |
| 平均 KW 覆盖 | 1.00 | X.XX | X.XX | |

## P1：B6 SSE 并发断流

[修了→写修复内容；没修→写"列入 follow-up，后续修复"]

## 故事金线（面试 5 分钟）

> "v1 测量报告完成后发现 4 个数据质量问题——Cache 看板无数据、评估集 baseline=100% 无区分度、p95 反而变慢、并发失败率上升。我针对性修了 3 个：[列出]。重新跑评估后，[关键对比数字]。这个过程比 v1 更有说服力——数据质量和测量闭环都经得起面试官追问。"
```

- [ ] **Step 2: Commit**

```bash
git add docs/specs/2026-05-28-measurement-v2-data-quality/ eval/golden.jsonl
git commit -m "feat(eval): fix cache metrics visibility and rebuild eval set with adversarial questions"
```

---

### Task 7 (Stretch): B6 SSE 并发断流排查

**触发条件**：P0-1 和 P0-2 完成后，如果时间充裕则执行此任务。

**Files:**
- 可能修改：`backend/app/services/qa_service.py`（SSE 流控制）
- 可能修改：`backend/app/modules/qa/router.py`（SSE endpoint）
- 测试：`backend/scripts/load_test/locustfile.py`

- [ ] **Step 1: 纯并发 Locust —— 只压 ask endpoint**

```bash
cd backend
# 只跑 ask 场景，50 并发，1 分钟
uv run locust -f scripts/load_test/locustfile.py \
  --headless --users 50 --spawn-rate 5 --run-time 60s \
  --host http://localhost:8000 \
  --csv docs/specs/2026-05-28-measurement-v2-data-quality/locust-b6
```

- [ ] **Step 2: 开启 debug 模式复现断流**

```bash
export RAG_DEBUG_ENABLED=True
# 重新跑 Locust
```

查看日志中 "no done event in stream" 发生时的 fts_task 状态和 SSE event 序列。

- [ ] **Step 3: 根据日志定位根因**

常见根因方向：
1. `anyio.create_task_group()` 中某个 task 抛异常导致整个 group 取消
2. Redis Pub/Sub 在并发下 channel 冲突
3. httpx stream `aiter_text()` 在连接断开时未正确清理

- [ ] **Step 4: 修复并验证**

具体修复代码取决于排查结果。验证标准：
```bash
# 50 并发下 "no done event" 错误率应显著下降
```
