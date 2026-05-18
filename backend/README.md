# Backend

Dev RAG backend 承载认证、知识库摄入、RAG 检索问答、SSE 流式输出、异步任务与评估调试能力。
当前项目重点是让开发者文档 / 项目资料能够被导入、索引、检索并以可追溯引用的方式回答问题。

## 项目结构说明

```text
backend/
├── app/
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   ├── core/
│   ├── db/
│   ├── models/
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
- `core`：放配置、异常处理、日志初始化等全局基础能力
- `db`：放数据库引擎、Session、ORM Base 和后续数据库依赖注入
- `models`：放 SQLAlchemy 模型定义
- `repositories`：放数据访问层
- `schemas`：放请求和响应模型
- `services`：放业务编排和服务逻辑
- `tasks`：放异步任务入口
- `modules/auth`：处理注册、登录和鉴权
- `modules/knowledge`：处理知识库导入、状态查询、删除等能力
- `services`：承载 RAG 问答、检索、rerank、citation guard、eval 等业务逻辑

路由统一通过 `app/api/router.py` 暴露 `router`，再按版本拆到 `app/api/v1/`。
业务模块以 `auth`、`users`、`knowledge`、`conversations`、`qa` 等 Dev RAG 能力为主。

## 当前结构补充建议

- `db` 不属于业务模块，应该继续放在 `app/db/` 作为基础设施层
- `repositories/` 依赖 `db` 提供的 Session 做数据访问
- `models/` 放表结构，`alembic/` 放迁移脚本
- 日志模块建议放在 `app/core/logging.py`
- 如果后续有“系统配置扫描 / 环境诊断 / RAG 链路分析”能力，建议新增 `app/modules/system/`
  - `router.py`：对外暴露扫描或诊断接口
  - `service.py`：编排配置检查、依赖探测、健康检查
  - 具体扫描过程中统一复用 `app.core.logging`

## 接口响应规范

当前后端统一使用 `code + msg + data` 的响应结构。

成功响应示例：

```json
{
  "code": 200,
  "msg": "注册成功",
  "data": {
    "id": 1,
    "email": "917596600@qq.com",
    "username": "xuebao"
  }
}
```

失败响应示例：

```json
{
  "code": 422,
  "msg": "请求参数校验失败",
  "data": []
}
```

当前约定：

- 成功响应默认 `code=200`
- 响应体里的 `code` 当前默认与 HTTP 状态码保持一致
- 参数校验失败：`422`
- 未登录或登录失效：`401`
- 无权限：`403`
- 资源不存在：`404`
- 资源冲突：`409`
- 服务器异常：`500`

## Alembic 迁移

执行前先确认数据库已经启动，并且 `backend/.env` 里的 `DATABASE_URL` 可连接；否则 Alembic 在自动生成或升级时会直接报连接错误。

推荐在仓库根目录执行：

```bash
uv run --directory backend alembic current
uv run --directory backend alembic history
uv run --directory backend alembic upgrade head
```

如果你已经 `cd backend`，也可以直接执行：

```bash
uv run alembic current
uv run alembic history
uv run alembic upgrade head
```

如果你刚新增或修改了 `app/models/user.py` 里的 ORM 字段，先生成迁移文件：

```bash
uv run --directory backend alembic revision --autogenerate -m "update users table"
```

如果是第一次给 `User` 表建表，也可以这样命名：

```bash
uv run --directory backend alembic revision --autogenerate -m "create users table"
```

生成后执行迁移，把表结构真正应用到数据库：

```bash
uv run --directory backend alembic upgrade head
```

常用排查命令：

```bash
uv run --directory backend alembic current
uv run --directory backend alembic history
```

如果需要回滚最近一次迁移：

```bash
uv run --directory backend alembic downgrade -1
```

说明：

- 推荐用 `uv run --directory backend alembic ...`，这样在仓库根目录执行也不会受当前工作目录影响
- Alembic 自动生成依赖 `app/models/__init__.py` 暴露模型，新增模型后记得在这里导入
- 生成迁移后要检查 `backend/alembic/versions/` 下的脚本是否符合预期，再执行 `upgrade`

## RAG 相关文档

主要 spec 位于仓库根目录的 `spec/`：

- `spec/backend/knowledge-ingestion.md`：知识库导入、切分、embedding、入库主链路
- `spec/backend/qa.md`：RAG 问答、会话知识库范围、SSE 流式输出主链路
- `spec/backend/addenda/*.md`：query rewrite、hybrid retrieval、citation guard、telemetry、eval 等增量设计
