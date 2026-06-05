# DevDoc RAG

面向开发者的技术文档 RAG 问答系统。用户可以导入技术文档 URL、Markdown/TXT 文件或 PDF，系统异步解析、结构化切分、生成向量并入库；随后在 Chat 中进行多轮问答，答案必须带有可追溯 citations。

> 仓库名仍为 `offer-copilot`，但当前产品定位和主要实现是 DevDoc RAG。对外展示、简历和 README 统一使用 DevDoc RAG。

## 核心能力

- 文档摄入：支持 URL、Markdown/TXT、PDF；URL 通过 Firecrawl 获取 Markdown，PDF 通过 PyMuPDF 提取文本。
- 结构化 Chunking：按 Markdown 标题路径切分，并保护代码块、表格、列表等结构。
- 向量与全文检索：PostgreSQL + pgvector 做向量召回，PostgreSQL FTS 做关键词召回，融合后用 Cohere Rerank 重排。
- 会话级知识路由：首个检索类问题自动选择 Top 3 相关知识库，后续追问沿用同一 scope。
- 引用校验：回答必须返回可追溯 citations；无有效依据时返回明确错误，避免幻觉入库。
- 实时反馈：Celery 执行文档处理，前端通过状态接口与 SSE/流式回答展示进度和答案。
- 生产化配套：认证、知识库 CRUD、多轮会话、Sentry、Prometheus/Grafana、本地 Docker Compose。

## 技术栈

- 后端：FastAPI、SQLAlchemy async、Alembic、Celery、Redis、PostgreSQL、pgvector、OpenAI、Cohere、Firecrawl、PyMuPDF
- 前端：Next.js、React、TypeScript、Tailwind CSS、Base UI、SWR、Vitest
- 运维：Docker Compose、Prometheus、Grafana、Sentry、Vercel/Railway 部署配置

## 项目结构

```text
offer-copilot/
├── backend/          # FastAPI 后端、RAG 链路、异步任务、监控
├── frontend/         # Next.js 前端工作台
├── spec/             # 当前主 spec 与流程图
├── docs/             # 阶段文档、观测性和评估资料
├── eval/             # RAG 评估数据
├── monitoring/       # Prometheus / Grafana 配置
├── docker-compose.yml
├── dev.sh
├── CLAUDE.md         # 工程规范单一来源
└── README.md
```

## RAG 主链路

```text
导入文档
  -> 创建 knowledge_base
  -> Celery 解析 URL / File / PDF
  -> 生成知识库摘要和标题
  -> Markdown 结构感知 chunking
  -> Embedding 入库 document_chunks
  -> Chat 首问触发知识库 scope 路由
  -> Query rewrite
  -> Vector + FTS 混合召回
  -> Cohere Rerank
  -> LLM 流式生成
  -> Citation Guard 校验并存储消息
```

## 本地启动

首次启动前准备环境变量：

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

需要配置 OpenAI、Cohere、Firecrawl、数据库、Redis 等变量。不要提交真实密钥。

一键启动：

```bash
./dev.sh
```

默认地址：

- 前端：`http://localhost:3005`
- 后端：`http://localhost:8080`
- Swagger：`http://localhost:8080/docs`
- Grafana：`http://localhost:3009`
- Prometheus：`http://localhost:9099`

## 常用命令

后端：

```bash
cd backend
uv run ruff check .
uv run pytest
uv run alembic upgrade head
```

前端：

```bash
cd frontend
pnpm dev
pnpm lint
pnpm test
pnpm build
```

## 当前工程状态

- 核心 RAG 链路、知识库摄入、会话问答、引用校验、监控与评估脚本均已有实现。
- `frontend pnpm lint` 当前仍有少量历史 `any` 类型问题，需要在工程质量整理时修复。
- `backend uv run ruff check .` 当前主要在 Alembic 和运维脚本上有历史格式问题，核心业务模块可继续按分层规范收敛。

## 对外展示重点

- 项目定位是“开发者技术文档问答助手”，不要再称为求职 OfferPilot。
- 简历可强调：文档解析、语义 chunking、hybrid retrieval、rerank、citation guard、SSE/异步处理和部署闭环。
- 面试讲解时建议以 `spec/backend/knowledge-ingestion.md` 和 `spec/backend/qa.md` 作为架构依据。
