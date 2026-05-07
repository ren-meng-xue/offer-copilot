from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Text, Integer, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.knowledge_base import KnowledgeBase


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"

    # chunk 主键。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 所属知识库；知识库删除时级联删除 chunks。
    knowledge_base_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 切分后的文档正文。
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector 列；1536 对应 text-embedding-3-small，改模型需迁移并重建索引。
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    # 原始文档 URL，用于引用溯源。
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Markdown 标题路径，用于定位 chunk 所在章节。
    heading_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # chunk 在原文切分结果中的顺序。
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # chunk token 数，便于控制上下文长度。
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 反向关联到知识库对象。
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase", back_populates="chunks"
    )
