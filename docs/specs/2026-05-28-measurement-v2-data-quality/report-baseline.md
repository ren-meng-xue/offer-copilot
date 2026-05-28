# 评估报告 — baseline

**时间**: 2026-05-27 19:27:27
**评估集**: `../eval/golden.jsonl` (30 道)

## 核心指标

| 指标 | 值 |
|---|---|
| 总成功率 | **29/30 = 96.7%** |
| 引用命中率 | **25/30 = 83.3%** |
| 平均关键词覆盖率 | **0.85** |
| TTFT p50 / p95 | 15331.0 / 24155.9 ms |
| Total p50 / p95 | 17642.5 / 31034.4 ms |

## Outcome 分布

- success: 29
- error: 1

## 失败样本

- KB 4 / Q: 本教程的内容是如何组织的
  outcome=success citation_ok=False err=None
- KB 4 / Q: 如何激活虚拟环境
  outcome=success citation_ok=False err=None
- KB 4 / Q: fastapi dev 命令的作用是什么
  outcome=success citation_ok=False err=None
- KB 4 / Q: FastAPI 中 WebSocket 的实现原理是什么
  outcome=error citation_ok=True err=None
- KB 4 / Q: FastAPI 的依赖注入系统如何处理 SQLAlchemy 会话
  outcome=success citation_ok=False err=None
- KB 4 / Q: 完整说明 FastAPI 用户指南中提到的所有学习路径和后续资源
  outcome=success citation_ok=False err=None