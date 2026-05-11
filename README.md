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

### 前置准备

```bash
# 复制环境变量配置
cp backend/.env.example backend/.env

# 编辑 backend/.env，至少配置以下关键项：
# - OPENAI_API_KEY（必填）
# - FIRECRAWL_API_KEY（必填）
# - SECRET_KEY（运行 python -c "import secrets; print(secrets.token_urlsafe(32))" 生成）
# - DATABASE_URL（默认已配置为 localhost:5433）
# - REDIS_HOST/REDIS_PORT（默认 localhost:6379）
```

### 方式一：Docker Compose（推荐）

```bash
# 启动所有服务（PostgreSQL、Redis、Backend API、Celery Worker）
docker compose up -d

# 执行数据库迁移
docker compose exec api alembic upgrade head

# 查看服务日志
docker compose logs -f api

# 前端（本地运行，不走 Docker）
cd frontend && npm run dev
```

### 方式二：本地直接运行

#### 1. 启动基础设施（PostgreSQL + Redis）

```bash
# 仅启动数据库和 Redis
docker compose up -d postgres redis
```

#### 2. 执行数据库迁移

```bash
# 在项目根目录执行
uv run --directory backend alembic upgrade head
```

#### 3. 启动后端服务

**注意：以下两种方式任选其一**

```bash
# 方式 A：在项目根目录执行（推荐）
uv run --directory backend uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 方式 B：进入 backend 目录后执行
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 服务默认运行在 http://0.0.0.0:8000
# --reload 参数支持代码修改后自动重启
```

#### 4. 启动 Celery Worker（可选，处理异步任务）

另开一个终端：

```bash
cd backend
uv run celery -A backend.app.tasks.celery_app worker --loglevel=info
```

#### 5. 启动前端

```bash
cd frontend && npm run dev
```

### 访问服务

- **后端 API**: http://localhost:8000
- **API 文档 (Swagger)**: http://localhost:8000/docs
- **API 文档 (ReDoc)**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health
- **前端应用**: http://localhost:3000

### 常用命令

```bash
# 查看当前迁移状态
uv run --directory backend alembic current

# 查看迁移历史
uv run --directory backend alembic history

# 生成新的迁移文件（修改模型后）
uv run --directory backend alembic revision --autogenerate -m "描述变更内容"

# 回滚最近一次迁移
uv run --directory backend alembic downgrade -1

# 停止所有 Docker 服务
docker compose down

# 停止并删除数据卷（谨慎使用）
docker compose down -v
```

## 目录

```
├── backend/        # FastAPI 后端
├── frontend/       # Next.js 前端
├── docker-compose.yml
└── CLAUDE.md       # 开发约定和架构决策
```
