# 前端结构

## 默认目录

建议前端逐步整理成下面这类结构：

```text
src/
├── app/
├── components/
├── features/
├── lib/
├── services/
└── types/
```

当前项目还在早期，可以按需要逐步引入，不必一次性补全。

## 各目录职责

- `app/`
  放页面路由、布局和页面级组织

- `components/`
  放可复用组件
  其中：
  - `components/ui/` 放 `shadcn/ui` 基础组件
  - 其他目录放项目自己的通用展示组件

- `features/`
  放业务模块
  例如：
  - `auth`
  - `jobs`
  - `resumes`
  - `analysis`
  - `interview`

- `lib/`
  放通用工具函数
  例如：
  - className 合并
  - 日期格式化
  - token 工具

- `services/`
  放接口请求封装
  例如：
  - `auth.ts`
  - `users.ts`
  - `jobs.ts`

- `types/`
  放接口类型和业务对象类型

## 页面和业务代码的边界

- `app/` 只做路由承接和页面拼装
- 业务逻辑不要全部堆在页面文件里
- 可复用的业务块优先放到 `features/`
- 通用视觉组件优先放到 `components/`

## 当前阶段建议

- 不急着做很深的目录层级
- 先保证页面能清楚落位
- 先把通用组件和业务组件分开
- 先把接口请求从页面中分出去

## 当前阶段不建议

- 一开始就做过重的前端分层
- 引入复杂的状态架构
- 每个业务都单独造一套组件风格
