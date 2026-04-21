# 拆分方式

## 什么时候拆成多个 skill

如果内容分别回答不同问题，就拆开：

- 产品：回答做什么
- 技术：回答怎么做
- 部署：回答怎么上线

这样后面调用时更准，也更容易维护。

## 什么时候放进一个 skill

如果这些内容总是一起出现，而且总量不大，可以放在一个 skill 里。

比如：

- 一个很小的内部工具
- 一个只给当前项目使用的临时规范

## 推荐做法

对于当前 OfferPilot 项目，建议至少分这两类：

- `offerpilot-product`
- `offerpilot-tech`

如果后面部署内容越来越多，再单独拆：

- `offerpilot-deploy`

## SKILL.md 和 references 的分工

### `SKILL.md`

放：

- skill 是做什么的
- 什么时候用
- 先看哪几个文件
- 使用时的约束

### `references/`

放：

- 产品文档摘要
- 技术栈说明
- 目录约定
- 部署说明
- 术语或规则

一句话：

`SKILL.md` 是入口，`references/` 是正文。
