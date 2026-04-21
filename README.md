# OfferPilot

OfferPilot 是一个从 0 到 1 搭建中的 AI 求职副驾项目。

当前项目聚焦三条核心能力：

- JD 分析
- 简历优化
- 面试准备

## 项目目标

OfferPilot 不是单纯的简历润色工具，而是围绕目标岗位展开的 AI 求职辅助系统。

希望帮助用户完成这样一条主链路：

`JD 输入 -> 岗位分析 -> 简历评分 -> 简历优化 -> 面试准备`

## 当前目录

```text
offer-copilot/
├── backend/
├── frontend/
├── deploy/
└── skills/
```

### `backend/`

后端服务目录，当前使用 `uv` 初始化 Python 3.12 项目。

### `frontend/`

前端目录，当前预留，后续用于真正的前端项目实现。

### `deploy/`

部署相关目录，后续用于环境变量模板、部署脚本和发布配置。

### `skills/`

项目自定义 skill 目录，用来沉淀产品、技术、交付和 skill 规范。

## 当前 skills

- `offerpilot-product`
- `offerpilot-tech`
- `offerpilot-delivery`
- `skill-creator`

## 当前状态

- 已初始化 Git 仓库
- 已配置 GitHub 远程仓库
- 已搭建后端 Python 基础环境
- 已整理项目初期 skill 体系

## 后续计划

1. 继续拆解产品文档
2. 完善后端服务结构
3. 创建前端项目
4. 补充部署和发布流程

