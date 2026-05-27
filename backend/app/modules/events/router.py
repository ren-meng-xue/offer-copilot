import asyncio
import json
import logging
import redis.asyncio as redis
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.app.core.config import settings
from backend.app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["事件"])


@router.get("/events")
async def sse_events(current_user_id: str = Depends(get_current_user)):
    """SSE 终端：订阅 Redis 频道并向前端推送实时更新。"""

    user_id = int(current_user_id)

    async def event_generator():
        # 使用与 Celery 相同的 Redis 实例
        r = redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"user:{user_id}:events"
        await pubsub.subscribe(channel)

        logger.info(f"User {user_id} connected to SSE, subscribed to {channel}")

        try:
            # 发送初始连接成功消息，前端 listenToEvents 会处理 type: "connected"
            yield f"data: {json.dumps({'type': 'connected', 'data': {'user_id': user_id}}, ensure_ascii=False)}\n\n"

            while True:
                # 定期检查消息，同时保持连接活跃
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=30
                )
                if message:
                    yield f"data: {message['data']}\n\n"
                else:
                    # 发送空注释作为 keep-alive，防止中转代理或浏览器超时
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            logger.info(f"User {user_id} disconnected from SSE")
            await pubsub.unsubscribe(channel)
        except Exception as e:
            logger.error(f"SSE error for user {user_id}: {e}")
        finally:
            await pubsub.close()
            await r.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )

