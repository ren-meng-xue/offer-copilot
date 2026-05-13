import enum
from typing import TYPE_CHECKING

from sqlalchemy import String, Enum, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.document_chunk import DocumentChunk


class KnowledgeBaseStatus(str, enum.Enum):
    # 等待异步索引任务开始。
    PENDING = "pending"
    # 正在爬取、切分和写入向量。
    PROCESSING = "processing"
    # 索引完成，可用于问答。
    DONE = "done"
    # 索引失败，详情见 error_message。
    FAILED = "failed"


class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"

    # 知识库主键。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 所属用户；创建知识库必须鉴权，user_id 不可为空。
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 用户可见的知识库名称。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 来源类型，如 url 或 pdf。
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="url")
    # 原始文档地址或上传文件地址。
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    # 当前索引任务状态。
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(KnowledgeBaseStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=KnowledgeBaseStatus.PENDING,
    )
    # 失败时记录错误原因。
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 文档的全局摘要，用于提供上下文和前台展示。
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 知识库下的 chunks；删除知识库时一并删除。
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        #DocumentChunk 这个是ORM模型类名
        # chunks 是这个列表里面的每一项都是一个DocumentChunk对象 1 vs 多 个
        #back_populates="knowledge_base", 这个是和DocumentChunk里面的knowledge_base属性相对应的，表示双向关系
        #放到我们这个场景的理解就是 删掉一个KnowledgeBase，它下面的DocumentChunk也应该一起删除
        "DocumentChunk", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
