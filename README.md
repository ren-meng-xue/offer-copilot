# OfferPilot

OfferPilot 是一个从 0 到 1 搭建中的 AI 求职副驾项目。

当前项目聚焦三条核心能力：

- JD 分析
- 简历优化
- 面试准备

## 项目目标

OfferPilot 不是单纯的简历润色工具，而是围绕目标岗位展开的 AI 求职辅助系统。

希望帮助用户完成这样一条主链路：

`JD 输入 -> 岗位分析 -> 简历评分 -> 简历优化 -> 面试准备`

## 当前目录

```text
offer-copilot/
├── backend/
├── frontend/
├── deploy/
└── skills/
```

- `backend/`：后端服务目录
- `frontend/`：前端目录
- `deploy/`：部署相关配置目录
- `skills/`：项目自定义 skill 目录

## 当前 skills

- `offerpilot-product`
- `offerpilot-tech`
- `offerpilot-delivery`
- `skill-creator`

## 当前状态

- 已初始化 Git 仓库
- 已配置 GitHub 远程仓库
- 已搭建后端 Python 基础环境
- 已整理项目初期 skill 体系

## 本地开发

### 后端启动

后端服务目录在 `backend/`，当前使用 `uv` 初始化 Python 3.12 项目。

后端服务建议在项目根目录启动。

首次启动前，先确认本地配置文件已经存在：

```bash
cp backend/.env.example backend/.env
```

然后在 `offer-copilot/` 根目录执行：

```bash
uvicorn backend.app.main:app --reload
```

补充说明：

- 当前后端入口是 `backend.app.main:app`
- 更详细的后端目录说明和迁移命令见 [backend/README.md](/Users/xuebao/python/offer-copilot/backend/README.md)

### Docker 开发

Docker 相关配置统一放在 `deploy/` 目录下，当前使用 [deploy/docker-compose.yml](/Users/xuebao/python/offer-copilot/deploy/docker-compose.yml)。

首次启动前，先确认本地配置文件已经存在：

```bash
cp backend/.env.example backend/.env
```

然后进入 `deploy/` 目录执行：

```bash
cd deploy
docker compose up --build
```

当前会一起启动：

- `backend`
- `postgres`

补充说明：

- PostgreSQL 会在容器内自动创建 `offercopilot` 数据库
- `backend` 服务会读取 `backend/.env`
- 容器内数据库连接地址会由 `docker-compose.yml` 覆盖为 `postgres` 服务地址

## 后续计划

1. 继续拆解产品文档
2. 完善后端服务结构
3. 创建前端项目
4. 补充部署和发布流程
