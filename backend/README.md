# Backend

OfferPilot backend 当前先聚焦登录与注册能力。
目录结构先按最小 MVP 组织，后续再按真实业务逐步补充其他模块。

## 项目结构说明

```text
backend/
├── app/
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   ├── core/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── tasks/
│   ├── modules/
│   │   └── auth/
│   └── main.py
├── pyproject.toml
└── README.md
```

- `api`：放 FastAPI 路由入口和接口组织
- `core`：放配置、基础设施初始化和全局能力
- `repositories`：放数据访问层
- `schemas`：放请求和响应模型
- `services`：放业务编排和服务逻辑
- `tasks`：放异步任务入口
- `auth`：处理注册、登录和鉴权

路由统一通过 `app/api/router.py` 管理，再按版本拆到 `app/api/v1/`。
当前先把登录模块跑通，后续再逐步补充 `users`、`jobs`、`resumes`、`analysis` 等业务模块。

## 本地启动

先基于模板创建本地配置文件：

```bash
cp .env.example .env
```

```bash
uv run python main.py
```

## Docker 开发

`deploy/docker-compose.yml` 会一起启动：

- `backend`
- `postgres`

首次启动前可先确认 `backend/.env` 已创建，然后执行：

```bash
cd deploy
docker compose up --build
```

其中，PostgreSQL 会在容器内自动创建 `offercopilot` 数据库，不需要先在本机手动创建。
