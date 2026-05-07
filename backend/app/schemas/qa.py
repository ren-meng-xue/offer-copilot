import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateConversationResponse(BaseModel):
    conv_id: uuid.UUID
    created_at: datetime


class ConversationListItem(BaseModel):
    conv_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class MessageItem(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list | None
    created_at: datetime
