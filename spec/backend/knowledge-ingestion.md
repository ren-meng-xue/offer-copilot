# Knowledge Ingestion Spec

> 分类：后端（Backend）

## 1. 背景与目标

### 1.1 功能目标

用户提交技术文档 URL 后，系统异步抓取文档内容，切分为 chunk，生成 embedding，并存入 PostgreSQL（pgvector）中，供后续问答检索使用。

### 1.2 范围

本期仅支持 URL 文档接入，不包含 PDF 上传。

本期目标是打通知识库构建链路，不包含问答生成。

### 1.3 非目标

- 不实现聊天问答接口
- 不实现 rerank
- 不实现 PDF 上传
- 不实现复杂前端交互，仅支持最小状态查询

## 2. 用户流程

1. 用户提交文档 URL。
2. 系统创建 `knowledge_base` 记录，返回 `knowledge_base_id` 和 `task_id`。
3. 后台异步任务调用 Firecrawl 抓取文档。
4. 抓取结果转换为 Markdown。
5. 系统对 Markdown 进行 chunk 拆分。
6. 系统为 chunk 批量生成 embedding。
7. 系统将 chunk、metadata、embedding 写入 `document_chunks`。
8. 用户通过状态接口轮询，看到 `pending / processing / done / failed`。

## 3. API 设计

### 3.1 创建知识库

`POST /api/v1/knowledge`

请求体：

- `name: string | null`
- `source_url: string`

响应：

- `knowledge_base_id: string`
- `task_id: string`
- `status: "pending"`

说明：

- `name` 可选；若未传，后端根据 URL 或页面标题生成默认名称。
- 本期允许重复提交相同 URL，系统将创建新的知识库记录，不做去重。

### 3.2 查询知识库状态

`GET /api/v1/knowledge/{id}/status`

响应：

- `knowledge_base_id: string`
- `status: "pending" | "processing" | "done" | "failed"`
- `error_message: string | null`

## 4. 数据结构

### 4.1 knowledge_bases

字段建议：

- `id`
- `user_id`
- `name`
- `source_type`，固定为 `url`
- `source_url`
- `status`
- `error_message`
- `created_at`
- `updated_at`

说明：

- `status` 同时存在于数据库和 Redis。
- 数据库中的 `status` 作为业务状态来源。
- Redis 中的状态用于异步任务过程追踪和快速读取。

### 4.2 document_chunks

字段建议：

- `id`
- `knowledge_base_id`
- `content`
- `embedding`（`Vector(1536)`）
- `source_url`
- `heading_path`
- `chunk_index`
- `token_count`（可选）
- `created_at`

说明：

- 每个 chunk 必须携带以下 metadata：
  - `source_url`
  - `heading_path`
  - `chunk_index`

## 5. 核心处理规则

### 5.1 抓取

- 使用 Firecrawl 获取网页正文。
- 输出格式为 Markdown。
- 若抓取失败，`knowledge_base.status` 置为 `failed`。

### 5.2 Chunking

- 按 Markdown 标题递归拆分。
- `chunk_size = 512`
- `chunk_overlap = 64`
- 每个 chunk 必须保留 metadata：
  - `source_url`
  - `heading_path`
  - `chunk_index`

说明：

- 按标题拆分是为了提升后续检索片段的语义完整性和引用可读性。
- overlap 保留相邻上下文，降低边界截断造成的信息损失。

### 5.3 Embedding

- 使用 `text-embedding-3-small`
- 批量处理，`batch_size = 100`

### 5.4 存储

- 向量写入 PostgreSQL pgvector。
- 所有 chunk 通过 `knowledge_base_id` 关联知识库。
- 数据表及索引必须通过 Alembic 建表和迁移，不允许直接修改数据库 schema。

### 5.5 任务状态

Redis 中保存：

- `task:{task_id}:status = pending | processing | done | failed`

数据库中 `knowledge_bases.status` 也同步更新。

状态流转：

- 创建任务后：`pending`
- 开始抓取或索引：`processing`
- 全部完成：`done`
- 任一步骤失败：`failed`

## 6. 边界情况

- URL 非法
- URL 可访问但内容为空
- Firecrawl 抓取失败
- Markdown 解析后无有效 chunk
- Embedding API 失败
- 数据库写入失败
- 重复提交同一 URL
- 超长文档导致 chunk 数量过多

本期策略：

- 重复 URL：允许重复创建，不做去重。
- 超长文档：设置最大 chunk 数限制；超过阈值则任务失败并返回错误信息。

## 7. 错误处理

- 接口参数错误：直接返回 4xx。
- 异步任务失败：状态置为 `failed`。
- `error_message` 保存失败原因摘要。
- 单个知识库任务失败不影响其他知识库任务。

## 8. 测试点

### 8.1 API

- 成功创建 knowledge base
- 非法 URL 返回校验错误
- 可正确查询状态

### 8.2 任务

- 抓取成功后状态从 `pending -> processing -> done`
- 抓取失败后状态变为 `failed`

### 8.3 数据

- `document_chunks` 正确入库
- 每个 chunk 均带有：
  - `source_url`
  - `heading_path`
  - `chunk_index`
- embedding 维度正确为 1536

### 8.4 回归

- 不影响现有 `auth` / `users` 模块

## 9. 验收标准

满足以下条件视为完成：

- 提交 URL 后能创建知识库任务
- 后台能完成抓取、chunk、embedding、入库
- 状态接口可查询任务结果
- chunk metadata 完整
- 数据可供后续检索使用

---

## 10. 流程图

正式图片：

![Knowledge Ingestion Flow](./assets/knowledge-ingestion-flow.png)
