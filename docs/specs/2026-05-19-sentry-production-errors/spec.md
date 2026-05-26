# Spec: Sentry 生产错误追踪

**日期：** 2026-05-19
**状态：** Draft
**关联流程图：** `docs/specs/2026-05-19-sentry-production-errors/flow.html`

---

## 目标

为后端 FastAPI 与前端 Next.js 接入 Sentry，让生产环境未处理异常自动进入 Sentry Issues，便于按错误堆栈、接口路径、页面路径和环境定位问题。

---

## 核心流程

1. Railway 通过环境变量向后端注入 `SENTRY_DSN`。
2. 前端部署环境通过环境变量注入 `NEXT_PUBLIC_SENTRY_DSN`。
3. 后端应用启动时读取配置并初始化 Sentry。
4. 前端 Next.js 启动时读取公开 DSN 并初始化 Sentry。
5. 如果未配置 DSN，则跳过 Sentry，避免本地开发误上报。
6. 后端请求发生未处理异常时，Sentry FastAPI/Starlette 集成自动捕获异常。
7. 前端页面运行时、渲染边界和 API 请求异常进入 Sentry 前端项目。
8. 开发者在 Sentry 项目的 `Issues` 页面查看错误、堆栈、发生次数和环境。

---

## 技术方案

- **采用方案：** 后端 FastAPI 接入 `sentry-sdk`，前端 Next.js 接入 `@sentry/nextjs`，生产环境通过环境变量启用。
- **关键决策理由：**
  - 不把 DSN 写死到代码里，符合项目环境变量规则。
  - `send_default_pii=False`，避免默认上传请求头、Cookie、Token 等敏感信息。
  - 未配置 DSN 时不初始化，避免本地开发和测试污染 Sentry。
  - 前后端分成两个 Sentry project，避免 Python API 错误和浏览器错误混在一起。
- **依赖的现有模块：**
  - `backend/app/core/config.py`
  - `backend/app/main.py`
  - `backend/.env.example`
  - `backend/pyproject.toml`
  - `frontend/next.config.ts`
  - `frontend/src/app/global-error.tsx`
  - `frontend/package.json`

---

## API 设计

本次不新增业务 API。

---

## 数据模型

不涉及数据库表结构变更，不需要 Alembic 迁移。

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `SENTRY_DSN` | 后端 Sentry 项目 DSN，生产环境配置 |
| `SENTRY_ENVIRONMENT` | 后端 Sentry 环境名，默认使用 `APP_ENV` |
| `SENTRY_TRACES_SAMPLE_RATE` | 后端性能追踪采样率，默认 `0.0` |
| `NEXT_PUBLIC_SENTRY_DSN` | 前端 Sentry 项目 DSN，生产环境配置 |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | 前端 Sentry 环境名，默认 `production` |
| `SENTRY_AUTH_TOKEN` | 可选，构建期上传 source map 使用，不暴露到浏览器 |
| `SENTRY_ORG` | 可选，source map 所属组织 |
| `SENTRY_PROJECT` | 可选，source map 所属前端项目 |

---

## 边界 & 不做的事

- ✅ 做：后端未处理异常自动上报 Sentry。
- ✅ 做：前端运行时和渲染错误自动上报 Sentry。
- ✅ 做：Sentry 配置全部来自环境变量。
- ✅ 做：关闭默认 PII 上传。
- ❌ 不做：写本地日志文件，Railway Logs 继续承接 stdout 日志。
- ❌ 不做：自动修复错误，Sentry 只负责记录、聚合和定位。

---

## TODO 清单

- [ ] 增加 Sentry 配置项
- [ ] 新增 Sentry 初始化模块
- [ ] 应用启动时初始化
- [ ] 更新环境变量示例
- [ ] 安装后端依赖
- [ ] 安装前端依赖
- [ ] 增加前端初始化配置
- [ ] 增加前端全局错误边界
- [ ] 增加基础测试

---

## 测试计划

- 正常路径：未配置 Sentry DSN 时应用可正常导入和启动。
- 正常路径：配置 `SENTRY_DSN` 时调用 `sentry_sdk.init`，且 `send_default_pii=False`。
- 正常路径：配置 `NEXT_PUBLIC_SENTRY_DSN` 时前端初始化 Sentry。
- 边界用例：`SENTRY_TRACES_SAMPLE_RATE` 默认值为 `0.0`，避免本地和低流量阶段产生额外事件。
- 错误路径：测试 Sentry 初始化失败不应阻断应用启动。
