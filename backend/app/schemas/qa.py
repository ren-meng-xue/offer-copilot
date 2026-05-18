import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CreateConversationRequest(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    knowledge_base_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_question_or_legacy_scope(self) -> "CreateConversationRequest":
        """创建会话必须提供首问，旧客户端可继续提供单知识库 ID。"""

        if self.question is None and self.knowledge_base_id is None:
            raise ValueError("question 或 knowledge_base_id 至少提供一个")
        return self


class KnowledgeScopeItem(BaseModel):
    knowledge_base_id: int | None
    name: str
    source_url: str
    route_score: float | None = None
    route_reason: str | None = None
    deleted: bool = False


class KnowledgeScope(BaseModel):
    type: str = "question_routed"
    items: list[KnowledgeScopeItem]


class CreateConversationResponse(BaseModel):
    conv_id: uuid.UUID
    knowledge_base_id: int | None
    knowledge_base_ids: list[int]
    knowledge_scope: KnowledgeScope | None
    created_at: datetime


class ConversationListItem(BaseModel):
    conv_id: uuid.UUID
    knowledge_base_id: int | None
    knowledge_base_ids: list[int]
    knowledge_scope: KnowledgeScope | None
    title: str | None
    created_at: datetime
    updated_at: datetime


class LocationInput(BaseModel):
    lat: float
    lng: float


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    location: LocationInput | None = None


class MessageItem(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list | None
    created_at: datetime
