"""基于已上传的 KB 内容，用 gpt-4o-mini 生成压测用问题集。

输出：eval/synthetic.jsonl
每行：{"question": "...", "kb_id": int}

仅用于压测（看延迟/吞吐/缓存命中率），不验证答案质量。
"""

import asyncio
import json
import sys
from pathlib import Path

# 允许从 backend/ 目录用 python -m scripts.eval.generate_synthetic 启动。
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT))

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.session import async_session_factory
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_base import KnowledgeBase

OUTPUT_PATH = REPO_ROOT / "eval" / "synthetic.jsonl"
KB_IDS_PATH = (
    REPO_ROOT / "docs" / "specs" / "2026-05-27-measurement-and-fix" / "kb-ids.txt"
)

# 每个 KB 生成多少道题
QUESTIONS_PER_KB = 20


PROMPT_TEMPLATE = """你是一个技术面试问题生成助手。下面是一份技术文档的若干段落，请基于这些内容生成 {n} 道有代表性的技术问题。

要求：
1. 每道题都必须能从下面段落中找到答案；
2. 问题要短、自然，像开发者会问的；
3. 覆盖事实查询、概念解释、对比、用法示例等不同类型；
4. 用中文。

输出格式：每行一个问题，不带编号、不带标点。

文档段落：
---
{context}
---

请直接输出 {n} 个问题："""


def _load_target_kb_ids() -> list[int] | None:
    """读取 Task 10 记录的目标 KB ID，避免把个人简历等非技术文档混入压测集。"""

    if not KB_IDS_PATH.exists():
        return None

    kb_ids: list[int] = []
    for line in KB_IDS_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        kb_ids.append(int(stripped.split()[0]))
    return kb_ids or None


async def fetch_kb_sample(
    db: AsyncSession, kb_id: int, sample_chunks: int = 12
) -> tuple[str, str]:
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    ).scalar_one()
    chunks = (
        (
            await db.execute(
                select(DocumentChunk.content)
                .where(DocumentChunk.knowledge_base_id == kb_id)
                .limit(sample_chunks)
            )
        )
        .scalars()
        .all()
    )
    return kb.name, "\n\n".join(chunks)


async def generate_for_kb(
    client: AsyncOpenAI, kb_name: str, context: str, n: int
) -> list[str]:
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.format(n=n, context=context[:8000]),
            },
        ],
        temperature=0.7,
    )
    text = resp.choices[0].message.content or ""
    questions = [line.strip() for line in text.splitlines() if line.strip()]
    return questions[:n]


async def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL
    )
    target_kb_ids = _load_target_kb_ids()

    async with async_session_factory() as db:
        stmt = select(KnowledgeBase.id, KnowledgeBase.name).order_by(
            KnowledgeBase.id.asc()
        )
        if target_kb_ids:
            stmt = stmt.where(KnowledgeBase.id.in_(target_kb_ids))
        kb_rows = (await db.execute(stmt)).all()

        with OUTPUT_PATH.open("w", encoding="utf-8") as f:
            for kb_id, kb_name in kb_rows:
                print(f"Generating for KB {kb_id} ({kb_name})...")
                try:
                    _, context = await fetch_kb_sample(db, kb_id)
                    questions = await generate_for_kb(
                        client, kb_name, context, QUESTIONS_PER_KB
                    )
                    for q in questions:
                        f.write(
                            json.dumps(
                                {"question": q, "kb_id": kb_id}, ensure_ascii=False
                            )
                            + "\n"
                        )
                    print(f"  -> {len(questions)} questions")
                except Exception as e:
                    print(f"  Error for KB {kb_id}: {e}")

    print(f"Done. Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
