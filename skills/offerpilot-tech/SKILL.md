---
name: offerpilot-tech
description: 用于处理 OfferPilot 的技术方案、系统结构和项目约定，适合讨论前后端拆分、接口设计和目录组织。
---

# offerpilot-tech

这个 skill 用来处理 OfferPilot 的技术方案、系统结构和工程约定。

它不是泛泛地聊“技术选型”，而是要围绕 OfferPilot 这个 AI 求职产品，给出能落地的默认技术决策。

## 适用场景

- 讨论后端技术栈、服务边界和模块拆分
- 讨论前端技术栈、页面组织和交互层选型
- 讨论 `FastAPI + Celery + Redis + Postgres` 这套基线怎么落地
- 设计 JD 解析、简历解析、匹配评分、AI 改写、模拟面试等能力的系统结构
- 设计接口协议、异步任务流、文件处理流和状态流转
- 规划前端、后端、存储、部署的职责边界
- 讨论项目目录结构、代码组织和工程约定

## 使用顺序

1. 先看 `references/stack-recommendation.md`
2. 再看 `references/project-structure.md`
3. 如果问题涉及部署、环境变量或上线边界，再看 `references/deployment-boundary.md`
4. 输出时优先回答：
   - 这个产品当前阶段到底需要哪些技术组件
   - 哪些是 MVP 必需，哪些可以后置
   - 每个组件解决什么问题，放在哪一层

## 产品背景默认理解

把 OfferPilot 视为一个围绕具体 JD 展开的 AI 求职副驾，而不是单一的“简历润色工具”。

默认会包含这些技术特征：

- 用户会上传 `JD / 简历 / 项目经历` 等文本或文件
- 系统需要做解析、结构化、评分、改写和问答生成
- 系统需要支持基于用户材料和岗位上下文的 `RAG`
- 部分任务耗时较长，不能全部同步阻塞在请求里
- 会存在生成状态、任务状态、历史记录和结果回看
- 后续大概率会有套餐、额度、订阅或调用次数限制

## 默认技术基线

如果用户没有特别指定，OfferPilot 默认按下面这套来设计：

- 前端：`Next.js + TypeScript + Tailwind CSS + shadcn/ui`
- 后端 API：`FastAPI`
- 后端语言：`Python`
- 数据库：`PostgreSQL`
- 缓存 / broker：`Redis`
- 异步任务：`Celery`
- 检索增强：`RAG`
- AI 接入：`OpenAI API`
- 对象存储：兼容 `S3` 的存储

## 后端推荐补齐项

当用户已经确定 `Celery + Redis + Python + FastAPI + Postgres` 时，默认继续推荐这些配套：

- ORM / 数据访问：`SQLAlchemy 2.0`
- 数据迁移：`Alembic`
- 配置管理：`pydantic-settings`
- API 校验：`Pydantic v2`
- HTTP 客户端：`httpx`
- 文件存储：`S3 / R2 / MinIO` 兼容方案
- 向量检索：优先 `pgvector + PostgreSQL`
- Embedding：与主模型分离，单独维护 embedding 调用
- 日志与错误追踪：结构化日志 + `Sentry`
- 测试：`pytest`

如果讨论任务调度，再补充：

- 定时任务：`Celery Beat`
- 任务监控：`Flower`

## 前端推荐补齐项

当用户讨论 OfferPilot 的前端选型时，默认继续推荐这些配套：

- UI 框架：`React`
- 路由与应用框架：`Next.js App Router`
- 样式：`Tailwind CSS`
- 组件基线：`shadcn/ui`
- 表单：`react-hook-form`
- 校验：`zod`
- 服务端数据获取：`SWR`
- 图标：`lucide-react`

如果产品需要简历内容继续编辑，再补充：

- 富文本编辑：`Tiptap`

## 前端各层职责

回答前端问题时，尽量把这些职责说清楚：

- `Next.js`
  - 负责路由、页面组织、SEO 页面和应用工作台承载
- `TypeScript`
  - 负责接口类型、页面状态和复杂结果对象的可维护性
- `Tailwind CSS`
  - 负责快速构建工作台、步骤流、分析卡片和响应式布局
- `shadcn/ui`
  - 负责提供可直接改造的组件底座，而不是黑盒组件库
- `react-hook-form`
  - 负责表单交互、输入管理和提交流程
- `zod`
  - 负责表单校验、接口参数校验和 AI 结构化输出兜底
- `SWR`
  - 负责查询类数据缓存、重取和状态同步

## 对 OfferPilot 特别重要的技术点

回答时优先覆盖这些，而不是只列框架名：

- 文件解析链路：
  - 简历通常来自 `PDF / DOCX`
  - 需要有上传、解析、抽取、清洗、结构化几个步骤
- 前端体验链路：
  - 需要承接 `JD 输入 -> 分析结果 -> 简历上传 -> 匹配评分 -> 改写结果 -> 面试准备`
  - 每一步都应该有明确结果页或结果区，而不是只有聊天窗口
- 文件交互：
  - 上传中、解析中、解析完成、解析失败要有明显反馈
- RAG 链路：
  - 需要有切片、embedding、入库、召回、重排或筛选几个步骤
  - 默认优先围绕 `JD / 简历 / 项目经历 / 历史生成记录 / 面试题库` 做检索
  - 第一版不要把 RAG 做成通用知识平台，先服务核心求职场景
- AI 任务链路：
  - JD 解析、简历评分、内容改写、题目生成不一定都同步执行
  - 长耗时任务默认进入 `Celery`
- 状态设计：
  - 需要明确 `job / analysis / generation / interview-session` 等对象的状态
- 流式返回：
  - 同步生成优先考虑 `SSE`
  - 不要一开始就把系统做成复杂 agent runtime
- 前端状态：
  - 查询型数据优先用轻量方式管理，不默认引入重型全局状态
- 可编辑性：
  - 简历改写和项目重写结果默认需要支持用户继续编辑
- 可追踪性：
  - 要能知道一次生成用了哪个 prompt、哪个模型、消耗了多少 token、是否失败
- 可恢复性：
  - Celery 任务要考虑重试、幂等、超时和失败回写
- 检索质量：
  - 要区分结构化过滤和语义检索
  - 要能追踪某次生成命中了哪些 chunks、来自哪些来源

## 建议默认模块

如果要给出后端模块拆分，优先落到这些模块：

- `auth`
- `users`
- `jobs`
- `resumes`
- `applications`
- `analysis`
- `generations`
- `interviews`
- `knowledge` 或 `retrieval`
- `billing` 或 `credits`
- `infra`

其中：

- `jobs` 负责 JD 及岗位目标对象
- `resumes` 负责简历文件、简历结构化内容和版本
- `analysis` 负责匹配评分、能力缺口、关键词提取
- `generations` 负责 AI 改写、项目重写、问题生成
- `interviews` 负责模拟面试会话、提问、回答、评分
- `knowledge` / `retrieval` 负责切片、embedding、索引、召回和检索编排
- `infra` 放 AI client、storage、queue、logging 等基础能力

## 默认架构态度

- 默认采用前后端分离
- 默认单体应用 + 清晰模块边界，不做微服务
- 前端默认采用 `Next.js`，不优先走纯 `Vite SPA`
- 接口优先用 `REST`
- 流式输出优先用 `SSE`
- 长耗时处理优先用 `Celery`
- RAG 默认先走“单库优先”路线，优先 `Postgres + pgvector`
- 前端状态管理默认先轻量化，优先 `React state + SWR`
- 优先简单可落地的 MVP 方案
- 先保证“可用、可追踪、可演进”，再谈复杂编排

## 默认不建议过早引入

- 微服务
- Kubernetes
- Elasticsearch
- 独立向量数据库优先级高于业务闭环
- 重型状态管理
- 重型后台风组件库
- 复杂多 agent 编排
- 事件总线泛化设计
- 为未来而未来的插件系统

## 输出要求

输出不要停留在“可以用某某技术”。

默认要尽量落到这些层面：

- 哪些技术是 MVP 必需
- 哪些技术可以第二阶段再补
- 每个组件解决什么问题
- 推荐放在哪个目录或模块
- 同步接口和异步任务怎么分工
- 前端哪些库是必须理解的，哪些可以先会用
- 哪些设计是当前阶段应该避免的
