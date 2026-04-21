---
name: skill-creator
description: 用于在当前项目里创建或整理 skill。适合处理 skill 命名、目录结构、SKILL.md 写法、references 拆分和中文化整理。
---

# skill-creator

这个 skill 用来处理当前项目里的 skill。

适用场景：

- 新建 skill
- 调整 skill 目录
- 修改 SKILL.md
- 拆分 references
- 把内容改成中文
- 去掉过重的模板腔和 AI 味道

使用顺序：

1. 先看 [references/rules.md](references/rules.md)
2. 需要命名时看 [references/naming.md](references/naming.md)
3. 需要拆文档时看 [references/structure.md](references/structure.md)

约束：

- skill 放在项目自己的 `skills/` 目录下
- 不修改系统内置的 `.system/skill-creator`
- `SKILL.md` 只写入口信息和使用规则
- 长内容放到 `references/`
- 命名优先朴素、直接、可维护
- 默认使用中文

