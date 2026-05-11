# RAG 系统架构深度解析 (ARCHITECTURAL NOTES)

本文档作为你的技术备忘录，详细记录了项目中 RAG 链路的设计细节，建议在面试前复习。

## 1. 检索链路 (Retrieval Pipeline)
系统采用了工业界标准的 **两阶段检索** 架构：

### 第一阶段：混合召回 (Hybrid Retrieval)
- **向量检索 (Vector Search)**：
    - 模型：`text-embedding-3-small` (1536维)。
    - 数据库：PostgreSQL + `pgvector`。
    - 优点：擅长处理语义相似性，即使关键词不匹配也能找回。
- **全文检索 (FTS)**：
    - 技术：Postgres `tsvector`。
    - 优点：擅长处理专业术语、API 名称、缩写（如检索 `id_token`）。

### 第二阶段：重排序 (Rerank)
- **模型**：`Cohere Rerank v3.5`。
- **逻辑**：将混合召回的 Top-20 候选片段再次打分，只取分数 > 0.3 的前 5 个分片。
- **价值**：极大降低了 LLM 处理无关信息的成本，提升了答案的精确度。

## 2. 知识库处理 (Ingestion Flow)
- **网页抓取**：Firecrawl (支持动态加载，输出 Markdown)。
- **切片策略**：
    - **Markdown 标题感知**：使用 `MarkdownHeaderTextSplitter`。
    - **元数据注入**：每个分片都包含 `heading_path`（如：`入门指南 > 快速开始 > 环境变量`）。
    - **原子性保护**：代码块、列表、表格通过 `_split_structured_section` 逻辑尽量保持完整。

## 3. 核心约束：引用溯源 (Citations)
- **原理**：LLM 在生成的答案中必须标注 `[1]`、`[2]`。
- **校验**：后端 `_require_citations` 方法会通过正则提取索引，并去检索到的 `top_chunks` 中匹配。
- **安全性**：如果 LLM 生成的答案中引用了不存在的编号，或者完全没有引用，系统会将其判定为“幻觉”并拒绝入库。

## 4. 异步架构
- **任务分发**：FastAPI 发送任务。
- **执行环境**：Celery Worker + Redis。
- **状态同步**：通过 Redis 实时同步 `PROCESSING` / `DONE` 状态，前端轮询展示。
