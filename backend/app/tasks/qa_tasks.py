import asyncio
import uuid

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.config import settings
from backend.app.repositories import qa_repository
from backend.app.tasks import celery_app

SUMMARY_TRIGGER = 20
KEEP_RECENT = 4


async def _run_summarize(conv_id_str: str) -> None:
    conv_id = uuid.UUID(conv_id_str)
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with session_factory() as db:
        try:
            conv = await qa_repository.get_conversation_by_id(db, conv_id)
            if conv is None or (conv.message_count or 0) <= SUMMARY_TRIGGER:
                return

            old_messages = await qa_repository.get_old_messages_for_summary(db, conv_id, keep_recent=KEEP_RECENT)
            if not old_messages:
                return

            history = "\n".join(f"{m.role}: {m.content}" for m in old_messages)
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "请将以下对话历史压缩为简洁摘要，保留关键信息。"},
                    {"role": "user", "content": history},
                ],
            )
            summary = resp.choices[0].message.content or ""
            await qa_repository.update_conversation_summary(db, conv_id, summary)
        finally:
            await engine.dispose()


@celery_app.task(name="qa.summarize", bind=True, max_retries=0)
def summarize_conversation(self, conv_id: str) -> None:
    asyncio.run(_run_summarize(conv_id))
