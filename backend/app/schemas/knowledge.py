from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from datetime import datetime

from backend.app.models.knowledge_base import KnowledgeBaseStatus


class CreateKnowledgeRequest(BaseModel):
    """创建知识库请求，只接收用户提交的最小必要信息。"""

    source_url: HttpUrl = Field(..., description="要抓取的文档 URL")
    name: str | None = Field(
        default=None,
        max_length=255,
        description="知识库名称，不传则由后端根据 URL 生成",
    )


class CreateKnowledgeResponse(BaseModel):
    """创建知识库后的同步返回值。

    接口本身不等待爬取和索引完成，只返回知识库主键和当前状态，
    前端后续通过 knowledge_base_id 轮询状态接口即可。
    """

    knowledge_base_id: int
    task_id: str
    status: KnowledgeBaseStatus

    # 允许直接从 ORM 对象构造响应模型，减少路由层手动映射字段。
    model_config = ConfigDict(from_attributes=True)


class KnowledgeStatusResponse(BaseModel):
    """知识库状态查询响应。

    `error_message` 仅在异步任务失败时返回，便于前端展示失败原因。
    """

    knowledge_base_id: int
    status: KnowledgeBaseStatus
    error_message: str | None = None

    # 状态查询通常直接返回数据库实体，开启 from_attributes 保持与其他 schema 一致。
    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseListItem(BaseModel):
    """知识库列表项，用于前端知识库页面展示当前用户的导入记录。"""

    knowledge_base_id: int
    name: str
    source_url: str
    status: KnowledgeBaseStatus
    error_message: str | None = None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
