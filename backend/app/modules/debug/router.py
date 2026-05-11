import logging

import redis as sync_redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["诊断"])


@router.get("/health-check")
async def debug_health_check(db: AsyncSession = Depends(get_db)):
    """诊断端点：检查 DB、Redis、KB #9 状态。不需要认证。"""

    results: dict = {}

    # 1. 数据库连通性
    try:
        await db.execute(text("SELECT 1"))
        results["database"] = "ok"
    except Exception as exc:
        results["database"] = f"失败: {exc}"

    # 2. Redis / Celery broker 连通性（使用 CELERY_BROKER_URL）
    try:
        broker_url = settings.CELERY_BROKER_URL
        if broker_url:
            r = sync_redis.from_url(
                broker_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            if r.ping():
                results["redis"] = "ok"
                try:
                    queue_len = r.llen("celery")
                    results["celery_queue_pending_tasks"] = queue_len
                except Exception:
                    results["celery_queue_pending_tasks"] = "无法读取"
            else:
                results["redis"] = "ping 返回 False"
            r.close()
        else:
            results["redis"] = "CELERY_BROKER_URL 未设置"
    except Exception as exc:
        results["redis"] = f"失败: {exc}"
        results["celery_queue_pending_tasks"] = "N/A（Redis 不可达）"

    # 3. 检查 knowledge_base 表是否存在
    try:
        row = await db.execute(
            text(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = 'knowledge_base')"
            )
        )
        table_exists = row.scalar()
        results["knowledge_base_table_exists"] = table_exists
    except Exception as exc:
        await db.rollback()
        results["knowledge_base_table_exists"] = f"检查失败: {exc}"

    # 4. 知识库 #9 状态
    try:
        row = await db.execute(
            text(
                "SELECT id, name, status, source_url, error_message, created_at, updated_at "
                "FROM knowledge_base WHERE id = 9"
            )
        )
        kb = row.fetchone()
        if kb is None:
            results["kb_9"] = "不存在"
        else:
            results["kb_9"] = {
                "id": kb[0],
                "name": kb[1],
                "status": kb[2],
                "source_url": kb[3],
                "error_message": kb[4],
                "created_at": str(kb[5]) if kb[5] else None,
                "updated_at": str(kb[6]) if kb[6] else None,
            }
    except Exception as exc:
        await db.rollback()
        results["kb_9"] = f"查询失败: {exc}"

    # 5. 所有知识库列表
    try:
        row = await db.execute(
            text("SELECT id, name, status, created_at FROM knowledge_base ORDER BY id DESC LIMIT 20")
        )
        all_kbs = row.fetchall()
        results["all_knowledge_bases_count"] = len(all_kbs)
        results["all_knowledge_bases"] = [
            {"id": r[0], "name": r[1], "status": r[2], "created_at": str(r[3]) if r[3] else None}
            for r in all_kbs
        ]
    except Exception as exc:
        await db.rollback()
        results["all_knowledge_bases"] = f"查询失败: {exc}"

    # 6. 环境变量摘要
    results["env"] = {
        "DATABASE_URL_type": "已设置" if settings.DATABASE_URL else "未设置",
        "REDIS_HOST": settings.REDIS_HOST,
        "REDIS_PORT": settings.REDIS_PORT,
        "CELERY_BROKER_URL": settings.CELERY_BROKER_URL,
        "APP_ENV": settings.APP_ENV,
    }

    return results


@router.post("/run-migrations")
async def debug_run_migrations():
    """手动触发数据库迁移（建表）。"""

    from backend.app.db import engine as db_engine
    from backend.app.db import Base
    import backend.app.models  # noqa: F401 确保所有模型注册到 Base.metadata

    try:
        tables_before = Base.metadata.tables.keys()
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return {
            "status": "成功",
            "tables_created": list(Base.metadata.tables.keys()),
        }
    except Exception as exc:
        return {"status": "失败", "error": str(exc)[:500]}
