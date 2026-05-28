import time

from openai import AsyncOpenAI

from backend.app.core.config import settings
from backend.app.core.metrics import EMBEDDING_DURATION_SECONDS

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100

_client: AsyncOpenAI | None = None


# 获取 OpenAI 异步客户端，用于生成文本 embedding。
def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
    return _client


# 批量生成文本 embedding，返回向量列表。
async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch generate embeddings for a list of texts."""
    client = get_openai_client()
    all_embeddings: list[list[float]] = []
    t0 = time.perf_counter()

    try:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            response = await client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
            )
            all_embeddings.extend([item.embedding for item in response.data])
    finally:
        EMBEDDING_DURATION_SECONDS.labels(model=EMBEDDING_MODEL).observe(
            time.perf_counter() - t0
        )

    return all_embeddings
