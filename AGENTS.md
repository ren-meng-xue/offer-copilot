# Dev RAG - Codex 主控规范

本文件是从项目 `.claude/CLAUDE.md` 与 `.claude/` 配置同步给 Codex 的项目级规则。Codex CLI 约定读取 `AGENTS.md`，因此本文件是项目内 Codex 的入口规范。

## 全局约束（始终生效，任何情况不可跳过）

1. 始终使用**简体中文**回复。
2. 所有配置走环境变量，**禁止硬编码** Key / Secret。
3. 禁止读取 `.env`、`.env.local`、`.env.production`、`.env.development`、`.env.staging`、`.env.test` 等环境文件；如需变量名，优先查看 `.env.example` 或让用户确认。
4. commit / push 前必须等待用户回复「**1**」，否则不执行。
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

## Skill 路由表

遇到以下情境时，先主动读取对应 `.claude/skills/*.md` 文件，并按其中流程执行。Claude 专用的 `superpowers:*`、`gstack:*`、MCP 配置在 Codex 中不可直接等价时，使用本会话可用的 Codex skill、工具或手工流程替代，并说明替代方式。

| 触发情境 | 读取 Skill | 备注 / 结合能力 |
|---|---|---|
| 讨论产品方向、功能边界、用户价值、竞品对比 | `.claude/skills/product.md` | 结合 Codex 脑暴能力 |
| **开发任何新功能之前**（写 spec + 流程图） | `.claude/skills/spec.md` | 结合 Codex 计划编写能力 |
| 开发新功能、新 API、新模块 | `.claude/skills/feature-dev.md` | 结合 Codex 代码实现能力 |
| 修复 Bug、排查问题、分析报错 | `.claude/skills/bug-fix.md` | 结合 Codex 调查工具 |
| 编写测试、输出测试报告 | `.claude/skills/testing.md` | 结合 Codex TDD 流程 |
| 前端 UI 开发、页面验证、设计审计 | `.claude/skills/frontend.md` | 结合 Codex 浏览器与 UI 审计工具 |
| 部署上线、环境配置、迁移 | `.claude/skills/deploy.md` | 结合 Codex 部署工具 |
| 生成独立 HTML 页面 / 视觉设计 / 海报 / 落地页 | `.claude/skills/frontend-design.md` | 视觉与页面逻辑生成 |
| 代码审查（任意场景） | 按代码审查模式执行 | 优先列问题与风险，结合 Codex review 模式 |
| 并行子任务开发（多模块同步） | 仅在用户明确要求子代理或并行 agent 时使用 Codex 子代理 | 结合并行执行能力 |

## `.claude` 配置映射

- `.claude/settings.json`
  - Claude 配置禁止读取环境文件；Codex 也必须遵守。
  - Claude 的 Bash/Write/Edit hooks 不会在 Codex 中自动执行；Codex 应在执行命令前清楚说明意图，并在编辑后主动运行相应格式化工具。
  - Claude 启用了 `superpowers@claude-plugins-official`；Codex 中按可用 skill/tool 能力替代。
- `.claude/settings.local.json`
  - 其中的本地 `DATABASE_URL` 只作为 Claude 本地环境注入配置，不写入代码、不写入文档、不在回复中展开。
  - 其中的 allow 权限、MCP server 列表是 Claude 专用配置，不代表 Codex 自动获得同等权限。

## 技术栈快速参考

- 后端：FastAPI + **uvicorn**（ASGI）+ Celery + Redis + SQLAlchemy（异步）
- 核心业务：开发者文档 / 项目资料的知识库摄入、切分、向量化、检索增强问答与引用追踪
- RAG 链路：URL / 文件导入 → chunk 结构化 → embedding 入库 → query rewrite → hybrid retrieval → rerank → citation guard → SSE 流式回答
- 前端：Next.js + TypeScript + Tailwind CSS
- LLM：`gpt-4o`（主推理）/ `gpt-4o-mini`（轻量任务）
- 爬取：Firecrawl | 数据库：PostgreSQL + pgvector | 缓存 / 实时通道：Redis
- 包管理：**uv**（后端，Python 3.12，`pyproject.toml` + `uv sync`）/ **pnpm**（前端）
- 目录：`backend/`（FastAPI + Alembic）/ `frontend/`（Next.js）/ `dev.sh`（一键启动）
