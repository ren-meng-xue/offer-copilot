import uuid

from sqlalchemy import Float, Text, Integer, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    """会话模型，保存用户多轮问答和锁定后的知识范围入口。"""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    scope_items: Mapped[list["ConversationKnowledgeScopeItem"]] = relationship(
        "ConversationKnowledgeScopeItem",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationKnowledgeScopeItem.position",
    )


class ConversationKnowledgeScopeItem(Base, TimestampMixin):
    """会话知识范围成员，记录问题路由选中的知识库快照。"""

    __tablename__ = "conversation_knowledge_scope_items"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "knowledge_base_id",
            name="uq_conversation_scope_conversation_knowledge_base",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    knowledge_base_name_snapshot: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    source_url_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="scope_items",
    )


class Message(Base, TimestampMixin):
    """消息模型，保存用户与助手消息以及可追溯 citations。"""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
