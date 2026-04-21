---
name: offerpilot-product
description: 用于处理 OfferPilot 的产品方向、MVP 范围和用户流程，适合讨论功能、PRD、优先级和产品取舍。
---

# offerpilot-product

这个 skill 用来处理 OfferPilot 的产品问题。

适用场景：

- 讨论功能要不要做
- 拆 PRD 或产品模块
- 判断是不是 MVP
- 讨论用户流程、页面顺序、产品路径
- 给功能排优先级

使用顺序：

1. 先看 `references/prd-summary.md`
2. 需要判断范围时看 `references/mvp-scope.md`
3. 需要判断流程时看 `references/user-flow.md`

约束：

- 把 OfferPilot 当成 AI 求职副驾，不是单纯的简历润色工具
- 所有功能都要对齐主链路：`JD 输入 -> 岗位分析 -> 简历评分 -> 简历优化 -> 面试准备`
- 默认优先 MVP，优先最快产生用户价值的方案
- 如果一个功能偏离主链路，要明确指出，不要硬接进去
- 输出尽量直接，少写空泛的产品建议
