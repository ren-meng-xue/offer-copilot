# Backend Spec Index

后端 spec 分为两层：

- 主 spec：描述当前应被视为真实实现基线的完整能力
- 增量 spec：记录某次 feature 补充、收敛过程中的专题约束与设计决策

## 主 spec

- `knowledge-ingestion.md`：知识库导入、切分、embedding、入库主链路
- `qa.md`：问答、检索、citations、scope、评测与 telemetry 主链路

说明：

- 这两份文档是当前后端行为的 canonical spec
- 新协作、新实现、新 review 默认先读这两份

## 增量 spec

增量 spec 统一归档在 `addenda/`：

- `chunk-structure-aware.md`
- `conversation-knowledge-scope.md`
- `delayed-routing.md`
- `hybrid-retrieval.md`
- `knowledge-scoped-qa.md`
- `query-rewrite.md`
- `rag-citation-guard.md`
- `rag-eval-fixtures.md`
- `rag-eval-runner.md`
- `rag-real-chain-eval.md`
- `rag-relevance-threshold.md`
- `rag-telemetry.md`

说明：

- 这些文档保留 feature 演进过程中的专题设计与验收点
- 当主 spec 与增量 spec 不一致时，以主 spec 为准
- 后续如果某个增量 spec 的内容已完全吸收进主 spec，可以继续保留归档，不再单独维护

## 维护规则

1. 新增后端 feature 时，先写增量 spec。
2. feature 落地并稳定后，把结果合并回主 spec。
3. 合并完成后，将该增量 spec 视为归档文档，保留上下文，不再作为主入口。
