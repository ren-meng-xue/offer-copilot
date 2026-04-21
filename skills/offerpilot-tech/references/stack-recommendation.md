# 技术栈建议

## 推荐基线

- 前端：`Next.js + TypeScript + Tailwind CSS + shadcn/ui`
- 后端：`FastAPI + Python`
- 数据库：`PostgreSQL`
- 缓存 / 队列：`Redis`
- 异步任务：`Celery`
- RAG / 向量检索：`pgvector + PostgreSQL`
- ORM：`SQLAlchemy 2.0`
- 数据迁移：`Alembic`
- 配置管理：`pydantic-settings`
- AI 接入：OpenAI API
- 对象存储：兼容 S3 的存储
- 监控告警：结构化日志 + `Sentry`
- 测试：`pytest`

## 为什么适合 OfferPilot

- 后端会有较多 AI 调用和文本处理，Python 更顺手
- 前端既要做应用页，也可能要做可被搜索的介绍页
- 产品需要支持流式返回、文件上传和异步任务
- 简历解析、JD 解析、评分和改写都需要稳定的任务队列和状态管理
- 产品后续需要基于 `JD / 简历 / 项目经历 / 面试上下文` 做检索增强生成
- 后面如果要做套餐、额度、历史记录，`PostgreSQL` 会比轻量 KV 更稳
- 这套栈对 MVP 足够实用，后面扩展也还有余地

## 前端定位

后端如果用 `FastAPI`，前端默认就是：

- `React + Next.js App Router`

原因：

- 适合做 AI 产品界面
- 同时兼顾 SEO 页面和应用页面
- 也适合作为一个完整项目去展示

## 前端推荐配套

- `Tailwind CSS`：快速搭建页面和工作台布局
- `shadcn/ui`：作为可改造的组件底座
- `react-hook-form`：处理表单输入、校验联动和提交
- `zod`：负责 schema 和校验
- `SWR`：负责查询类数据获取、缓存和重取
- `lucide-react`：图标

## 为什么前端这样选

- OfferPilot 不是纯内容站，也不是纯后台系统，而是“官网 + AI 应用工作台”的组合
- 主链路里有 `JD 输入 -> 分析 -> 上传 -> 评分 -> 改写 -> 面试准备`
- 每一步都需要清楚的中间结果展示，而不是只有聊天窗口
- 前端会同时面对表单、文件上传、结构化结果卡片、长任务状态、可编辑生成结果
- 所以前端更适合选择灵活、可控、适合演进的组合，而不是重型封装方案

## 前端各工具负责什么

- `Next.js`
  - 页面路由、营销页、工作台页面、服务端渲染能力
- `TypeScript`
  - 管理 API 类型、复杂结果对象和前端状态
- `Tailwind CSS`
  - 页面样式、布局、响应式设计
- `shadcn/ui`
  - 按需生成组件代码，作为 UI 起点
- `react-hook-form`
  - 管理输入、提交、错误状态
- `zod`
  - 定义和校验表单、接口参数、AI 结构化输出
- `SWR`
  - 管理列表、详情、状态查询等查询型数据

## 架构风格

- 前后端分成两个应用
- 接口通信默认用 `REST`
- 长耗时或流式输出用 `SSE`
- 文件解析、长文本生成、批处理放到异步任务里
- 检索增强优先使用 `Postgres + pgvector`，避免过早引入独立向量基础设施

## 后端推荐配套

- `FastAPI` 负责 API、鉴权、同步查询和流式响应
- `Celery + Redis` 负责解析、生成、批处理和重试任务
- `PostgreSQL` 负责用户、岗位、简历、分析结果、生成记录、任务状态
- `pgvector` 负责 embedding 向量存储和相似度检索
- `S3` 兼容对象存储负责原始文件、导出文件和中间产物
- `SQLAlchemy + Alembic` 负责数据模型和迁移
- `Sentry` 负责错误追踪

## RAG 建议

- 检索源优先放在：
  - `JD`
  - 简历结构化内容
  - 项目经历素材
  - 历史分析和生成结果
  - 面试题与回答记录
- 基础流程：
  - 文本清洗
  - chunk 切片
  - embedding
  - 向量入库
  - 召回
  - 上下文组装
- 第一版先做“场景化检索”：
  - 为简历改写提供证据片段
  - 为面试问答提供项目经历和岗位要求上下文
  - 为匹配评分提供可引用的文本依据
- 第一版不要做：
  - 通用知识库后台
  - 多路复杂 rerank 编排
  - 独立向量数据库集群

## MVP 必需

- `Next.js`
- `TypeScript`
- `Tailwind CSS`
- `shadcn/ui`
- `react-hook-form`
- `zod`
- `FastAPI`
- `PostgreSQL`
- `pgvector`
- `Redis`
- `Celery`
- `SQLAlchemy`
- `Alembic`
- OpenAI API
- S3 兼容对象存储

## 第二阶段建议补齐

- `SWR`
- 富文本编辑器
- 更完善的设计 token 和主题体系
- 更细的埋点和用户行为分析
- `Celery Beat`：定时任务
- `Flower`：任务监控
- 更细的 RAG 评估与召回质量指标
- 额度 / 订阅计费
- Prompt 和模型调用的审计能力
- 更细的观测指标和告警

## 第一版先不要做

- `Redux`
- 过度抽象的 design system
- 很重的企业后台组件体系
- 复杂拖拽式页面编辑器
- 微服务
- Kubernetes
- Elasticsearch
- 复杂 agent 编排
- 语音模拟面试
