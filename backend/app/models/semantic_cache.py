import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SemanticCache(Base):
    __tablename__ = "semantic_query_caches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # 原始提问文本，建立普通文本索引以便于部分文字比对或清理
    question: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    # 问题文本的 1536维 Embedding 向量 (对应 OpenAI text-embedding-3-small)
    query_vector: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    # 缓存的所有 SSE 事件列表，序列化为 JSON 数组保存，包含 token、citations 等事件
    response_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    # 关联的知识库 ID 列表，序列化为 JSONB 数组保存，支持 GIN 索引和包含查询
    knowledge_base_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    # 创建时间，支持时区
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
