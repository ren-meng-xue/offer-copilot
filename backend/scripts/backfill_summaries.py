import asyncio
import logging
import sys
from pathlib import Path

# 将项目根目录加入 python 路径，确保能导入 backend 模块
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from firecrawl import V1FirecrawlApp
import httpx

from backend.app.core.config import settings
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.services.summary_service import generate_knowledge_base_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")
from sqlalchemy import select, or_
...
async def backfill():
    # 1. 初始化数据库连接
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    success_count = 0
    fail_count = 0

    async with session_factory() as db:
        # 2. 查询摘要缺失的记录 (包括 NULL 和 空字符串)
        stmt = select(KnowledgeBase).where(
            or_(KnowledgeBase.summary == None, KnowledgeBase.summary == "")
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        if not items:
            logger.info("🎉 所有知识库都已有摘要，无需补全。")
            return

        logger.info(f"发现 {len(items)} 条待补全记录。")

        for kb in items:
            try:
                logger.info(f"正在为知识库 [{kb.name}] (ID: {kb.id}) 生成摘要...")

                # 获取原文内容
                markdown = ""
                if kb.source_type == "url":
                    firecrawl = V1FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
                    scrape_result = firecrawl.scrape_url(kb.source_url, formats=["markdown"])
                    markdown = scrape_result.markdown
                else:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(kb.source_url)
                        resp.raise_for_status()
                        markdown = resp.text

                if not markdown:
                    logger.warning(f"⚠️ 无法获取知识库 {kb.id} 的内容，跳过。")
                    fail_count += 1
                    continue

                # 生成摘要
                summary = await generate_knowledge_base_summary(markdown)
                if summary:
                    kb.summary = summary
                    await db.commit()
                    success_count += 1
                    logger.info(f"✅ 知识库 {kb.id} 摘要补全成功。")
                else:
                    fail_count += 1

            except Exception as e:
                logger.error(f"❌ 知识库 {kb.id} 补全失败: {e}")
                fail_count += 1
                await db.rollback()

    logger.info(f"----------------------------------------")
    logger.info(f"任务结束！成功: {success_count}, 失败: {fail_count}")
    if fail_count > 0:
        logger.info(f"提示：对于失败的记录，你可以稍后再次运行脚本进行重试。")
    logger.info(f"----------------------------------------")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(backfill())
