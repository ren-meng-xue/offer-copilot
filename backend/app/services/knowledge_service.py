from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus
from backend.app.repositories import knowledge_repository
from backend.app.schemas.knowledge import CreateKnowledgeResponse, KnowledgeStatusResponse

def _default_name(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.rstrip("/")
    return path.split("/")[-1] or parsed.netloc or source_url


# 创建知识库，写入数据库并返回知识库 ID；异步任务由路由层触发。
async def create_knowledge_base(
    db: AsyncSession,
    source_url: str,
    name: str | None,
    user_id: int,
) -> CreateKnowledgeResponse:
    kb = KnowledgeBase(
        user_id=user_id,
        name=name or _default_name(source_url),
        source_url=source_url,
        source_type="url",
        status=KnowledgeBaseStatus.PENDING,
    )
    kb = await knowledge_repository.create_knowledge_base(db, kb)

    return CreateKnowledgeResponse(
        knowledge_base_id=kb.id,
        status=KnowledgeBaseStatus.PENDING,
    )


# 查询知识库状态，返回当前进度和错误信息。
async def get_knowledge_status(db: AsyncSession, kb_id: int) -> KnowledgeStatusResponse | None:
    kb = await knowledge_repository.get_knowledge_base_by_id(db, kb_id)
    if kb is None:
        return None
    return KnowledgeStatusResponse(
        knowledge_base_id=kb.id,
        status=kb.status,
        error_message=kb.error_message,
    )
