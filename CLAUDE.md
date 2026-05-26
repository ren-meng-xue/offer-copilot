# Dev RAG — 主控规范

## 全局约束（始终生效，任何情况不可跳过）

1. 始终使用**简体中文**回复。
2. 所有配置走环境变量，**禁止硬编码** Key / Secret。
3. 禁止读取 `.env`、`.env.local`、`.env.production`、`.env.development`、`.env.staging`、`.env.test` 等环境文件；如需变量名，优先查看 `.env.example` 或让用户确认。
4. 只在**功能开发完毕、Bug 修复完毕**等完整任务节点才发起 commit；spec / 设计文档等中间产物不单独 commit，随对应任务统一提交。push 前必须等待用户回复「**1**」。
5. LLM 调用只在 `services/` 层，`api/` 层禁止直接调用。
6. 实时状态用 SSE + Redis Pub/Sub，**禁止轮询**。
7. 数据库变更必须走 Alembic，禁止直接改表结构。
8. commit 前，若新增或修改了 ORM 模型（`models/` 下任意文件），必须完成：
   - `alembic revision --autogenerate -m "描述"` 已执行并 review
   - `alembic upgrade head` 本地运行成功（表/字段与模型一致）
   - 迁移文件已纳入本次 commit
9. 开发新功能前必须先在 `docs/specs/YYYY-MM-DD-<feature>/` 创建 spec 文件（含 `spec.md` + `flow.html` 流程图），经用户确认后方可进入实现阶段。
10. 本地开发环境通过 `./dev.sh` 启动（混合模式：Docker 跑 postgres + redis，其余服务直接在本机跑）。新增或删除服务时，**必须同步更新 `dev.sh`**，保持脚本与实际架构一致。
11. 修改 Python 文件后，按项目习惯运行 `black` 与 `isort`；修改 TS/TSX 文件后，按项目习惯运行 `prettier`。若工具不可用，要在最终回复中说明。
12. 删除任何文件、目录、数据、分支或远程资源前，必须先说明删除目标与影响范围，并等待用户明确允许后再删除。
13. 每次会话开始，扫描 `.claude/tasks/` 下所有文件，检查是否有未完成任务（Gate 未全部 ✅）。若有，在第一条回复中主动提示：
    > 检测到未完成任务：「XXX」，当前状态：「YYY 阶段」
    > 「1」继续  「2」忽略

---

## Skill 路由表

遇到以下情境时，**主动读取**对应 Skill 文件，按其规范执行：

| 触发情境 | 读取 Skill | 备注 / 结合能力 |
|---|---|---|
| 讨论产品方向、功能边界、用户价值、竞品对比 | `.claude/skills/product.md` | 结合 `superpowers: brainstorming` |
| **开发任何新功能之前**（写 spec + 流程图） | `.claude/skills/spec.md` | 结合 `superpowers: writing-plans` |
| 开发新功能、新 API、新模块 | `.claude/skills/feature-dev.md` | 结合 `superpowers: writing-code` |
| 修复 Bug、排查问题、分析报错 | `.claude/skills/bug-fix.md` | 结合 `gstack: /investigate` |
| 编写测试、输出测试报告 | `.claude/skills/testing.md` | 结合 `superpowers: tdd` + `gstack: /qa` |
| 前端 UI 开发、页面验证、设计审计 | `.claude/skills/frontend.md` | 结合 `gstack: /browse /qa /design-review` |
| 部署上线、环境配置、迁移 | `.claude/skills/deploy.md` | 结合 `gstack: /cso /ship` |
| 生成独立 HTML 页面 / 视觉设计 / 海报 / 落地页 | `.claude/skills/frontend-design.md` | 视觉与页面逻辑生成 |
| 代码审查（任意场景） | 按代码审查模式执行 | 优先列问题与风险，结合 `gstack: /review` |
| 并行子任务开发（多模块同步） | 仅在用户明确要求并行 agent 时使用对应能力 | 结合 `superpowers: subagent-driven-development` |

---

## 技术栈（快速参考）

- 后端：FastAPI + **uvicorn**（ASGI）+ Celery + Redis + SQLAlchemy（异步）
- 核心业务：开发者文档 / 项目资料的知识库摄入、切分、向量化、检索增强问答与引用追踪
- RAG 链路：URL / 文件导入 → chunk 结构化 → embedding 入库 → query rewrite → hybrid retrieval → rerank → citation guard → SSE 流式回答
- 前端：Next.js + TypeScript + Tailwind CSS
- LLM：`gpt-4o`（主推理）/ `gpt-4o-mini`（轻量任务）
- 爬取：Firecrawl | 数据库：PostgreSQL + pgvector | 缓存 / 实时通道：Redis
- 包管理：**uv**（后端，Python 3.12，`pyproject.toml` + `uv sync`）/ **pnpm**（前端）
- 目录：`backend/`（FastAPI + Alembic）/ `frontend/`（Next.js）/ `dev.sh`（一键启动）
