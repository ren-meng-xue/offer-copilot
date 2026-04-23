# OfferPilot Frontend

这是 OfferPilot 的前端项目，基于 `Next.js + TypeScript + Tailwind CSS + pnpm` 初始化。

当前这个前端目录用于承载：

- 官网和产品介绍页
- 登录后的应用工作台
- JD 输入、简历上传、匹配评分、内容改写、面试准备等前端交互

## 启动开发环境

先进入前端目录：

```bash
cd frontend
```

再启动开发服务器：

```bash
cp .env.example .env.local
pnpm dev
```

启动后，在浏览器打开 [http://localhost:3000](http://localhost:3000) 查看页面。

当前前端请求后端时，默认从 `NEXT_PUBLIC_API_BASE_URL` 读取 API 地址。
本地开发建议配置为：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## 当前技术基线

- `Next.js`
- `TypeScript`
- `Tailwind CSS`
- `pnpm`

后续计划补充：

- `shadcn/ui`
- `react-hook-form`
- `zod`
- `SWR`

## 目录说明

当前项目由 `create-next-app` 初始化，主要代码在：

- `src/app/`：页面和路由
- `public/`：静态资源

后续我们会根据 OfferPilot 的实际需求，逐步补充更适合业务的目录结构。

## 开发说明

- 当前使用 `App Router`
- 默认入口页面在 `src/app/page.tsx`
- 全局布局在 `src/app/layout.tsx`
- 修改代码后，页面会自动热更新

## 后续建议

接下来可以按这个顺序继续完善前端：

1. 清理默认首页内容，改成 OfferPilot 的起始页面
2. 安装并初始化 `shadcn/ui`
3. 规划 `src/` 下的业务目录结构
4. 接入后端 API 和任务状态展示
