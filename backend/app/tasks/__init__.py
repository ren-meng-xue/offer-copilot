from celery import Celery

from backend.app.core.config import settings

# Celery 应用实例，供 worker 和业务代码共同引用。
celery_app = Celery(
    # 应用名，用于 worker 日志和任务命名空间。
    "offer_copilot",
    broker=settings.CELERY_BROKER_URL, #表示任务消息发到哪里，通常是redis
    backend=settings.CELERY_RESULT_BACKEND,# 表示任务结果和状态存到哪里
    # 显式加载知识库异步任务，避免 worker 启动后找不到任务。
    include=["backend.app.tasks.knowledge_tasks", "backend.app.tasks.qa_tasks"],
)

celery_app.conf.update(
    # 任务参数统一用 JSON，避免 pickle 带来的安全风险。
    task_serializer="json",
    # 任务结果也用 JSON，便于接口读取和调试。
    result_serializer="json",
    # worker 只接受 JSON 格式消息。
    accept_content=["json"],
    # 后台任务统一使用 UTC，避免跨环境时区偏差。
    timezone="UTC",
    enable_utc=True,
)
