"""基于已上传的 KB 内容，用 gpt-4o-mini 生成压测用问题集。

输出：eval/synthetic.jsonl
每行：{"question": "...", "kb_id": int}

仅用于压测（看延迟/吞吐/缓存命中率），不验证答案质量。
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.session import async_session_factory
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.models.document_chunk import DocumentChunk

OUTPUT_PATH = Path(__file__).resolve().parents[3] / "eval" / "synthetic.jsonl"

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


async def fetch_kb_sample(db: AsyncSession, kb_id: int, sample_chunks: int = 12) -> tuple[str, str]:
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one()
    chunks = (
        await db.execute(
            select(DocumentChunk.content)
            .where(DocumentChunk.knowledge_base_id == kb_id)
            .limit(sample_chunks)
        )
    ).scalars().all()
    return kb.name, "\n\n".join(chunks)


async def generate_for_kb(client: AsyncOpenAI, kb_name: str, context: str, n: int) -> list[str]:
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": PROMPT_TEMPLATE.format(n=n, context=context[:8000])},
        ],
        temperature=0.7,
    )
    text = resp.choices[0].message.content or ""
    questions = [line.strip() for line in text.splitlines() if line.strip()]
    return questions[:n]


async def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)

    async with async_session_factory() as db:
        kb_rows = (await db.execute(select(KnowledgeBase.id, KnowledgeBase.name))).all()

        with OUTPUT_PATH.open("w", encoding="utf-8") as f:
            for kb_id, kb_name in kb_rows:
                # 只针对新上传的 KB ID (4, 5, 6, 7) 或者全部 KB
                # 这里为了数据质量，我们生成全部已有的
                print(f"Generating for KB {kb_id} ({kb_name})...")
                try:
                    _, context = await fetch_kb_sample(db, kb_id)
                    questions = await generate_for_kb(client, kb_name, context, QUESTIONS_PER_KB)
                    for q in questions:
                        f.write(json.dumps({"question": q, "kb_id": kb_id}, ensure_ascii=False) + "\n")
                    print(f"  -> {len(questions)} questions")
                except Exception as e:
                    print(f"  Error for KB {kb_id}: {e}")

    print(f"Done. Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
