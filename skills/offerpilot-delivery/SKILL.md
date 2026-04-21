---
name: offerpilot-delivery
description: 用于处理 OfferPilot 的部署、发布和环境约定，适合讨论本地运行、环境变量、上线流程和 deploy 目录边界。
---

# offerpilot-delivery

这个 skill 用来处理 OfferPilot 的交付和部署问题。

适用场景：

- 讨论本地开发怎么跑起来
- 讨论环境变量怎么管理
- 讨论测试、预发、正式环境的差异
- 讨论发布流程和上线检查项
- 讨论 `deploy/` 目录后面该放什么

使用顺序：

1. 先看 `references/delivery-scope.md`
2. 再看 `references/env.md`
3. 如果讨论发布流程，再看 `references/release-checklist.md`

约束：

- 默认先服务 MVP，不做过重的发布体系
- 环境变量命名要直接，不做花哨抽象
- 本地开发、测试、生产的边界要清楚
- `deploy/` 只放部署和环境相关文件，不放业务代码
- 输出尽量落到流程、目录、文件和检查项
