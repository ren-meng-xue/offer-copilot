# DevDoc RAG

开发者技术文档问答助手 — 粘贴文档 URL 或上传 PDF，系统异步爬取建立向量知识库，支持自然语言问答，每条答案附带原文引用溯源。

## 技术栈

- **前端**：Next.js 16 + TypeScript + Tailwind CSS
- **后端**：Python 3.12 + FastAPI
- **向量检索**：PostgreSQL + pgvector
- **异步任务**：Celery + Redis
- **AI**：OpenAI gpt-4o（生成）+ text-embedding-3-small（向量化）
- **爬虫**：Firecrawl API

## 本地开发

```bash
# 复制环境变量配置
cp backend/.env.example backend/.env
# 填写 OPENAI_API_KEY 和 FIRECRAWL_API_KEY

# 启动所有服务
docker compose up -d

# 执行数据库迁移
docker compose exec api alembic upgrade head

# 前端（本地运行，不走 Docker）
cd frontend && npm run dev
```

## 目录

```
├── backend/        # FastAPI 后端
├── frontend/       # Next.js 前端
├── docker-compose.yml
└── CLAUDE.md       # 开发约定和架构决策
```
