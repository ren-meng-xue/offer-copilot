---
name: offerpilot-frontend
description: 用于处理 OfferPilot 的前端页面、目录结构、组件使用、状态管理和接口接入，适合讨论前端如何落地实现。
---

# offerpilot-frontend

这个 skill 用来处理 OfferPilot 的前端落地问题。

适用场景：

- 规划前端页面和主链路
- 设计 `src/` 下的目录结构
- 讨论 `Next.js App Router` 怎么组织页面
- 讨论 `shadcn/ui` 组件怎么使用
- 讨论表单、状态和接口怎么接
- 判断哪些前端能力现在该做，哪些可以后置

使用顺序：

1. 先看 `references/page-structure.md`
2. 再看 `references/frontend-architecture.md`
3. 涉及组件复用时看 `references/component-rules.md`
4. 涉及表单、请求和登录态时看 `references/state-and-api.md`

约束：

- 这个 skill 只处理前端落地，不负责产品取舍
- 产品范围和链路判断优先参考 `offerpilot-product`
- 后端模块边界和整体技术选型优先参考 `offerpilot-tech`
- 默认围绕主链路实现：`JD 输入 -> 岗位分析 -> 简历上传 -> 匹配评分 -> 简历优化 -> 面试准备`
- 默认使用 `Next.js + TypeScript + Tailwind CSS + shadcn/ui`
- 默认优先 MVP，不做过重的前端抽象
