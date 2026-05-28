from celery import Celery, signals

from backend.app.core.config import settings
from backend.app.core.metrics import (
    CELERY_ACTIVE_TASKS,
    CELERY_QUEUE_LENGTH,
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASK_TOTAL,
)

# Celery 应用实例，供 worker 和业务代码共同引用。
celery_app = Celery(
    # 应用名，用于 worker 日志和任务命名空间。
    "offer_copilot",
    broker=settings.CELERY_BROKER_URL,  # 表示任务消息发到哪里，通常是redis
    backend=settings.CELERY_RESULT_BACKEND,  # 显式加载知识库异步任务，避免 worker 启动后找不到任务。
    include=["backend.app.tasks.knowledge_tasks", "backend.app.tasks.qa_tasks"],
)

celery_app.conf.update(
    # 生产环境容器内存有限，限制并发数避免 OOM。
    worker_concurrency=1,
    # 任务参数统一用 JSON，避免 pickle 带来的安全风险。
    task_serializer="json",
    # 任务结果也用 JSON，便于接口读取和调试。
    result_serializer="json",
    # worker 只接受 JSON 格式消息。
    accept_content=["json"],
    # 后台任务统一使用 UTC，避免跨环境时区偏差。
    timezone="UTC",
    enable_utc=True,
    # 稳定性增强：启动时如果 broker 不可用，自动重试而不是直接报错退出。
    # 兼容 Celery 5.x 及后续版本。
    broker_connection_retry_on_startup=True,
    # 稳定性增强：由于我们手动在业务库/Redis 中维护状态，默认关闭 Celery 自带的 result backend 以节省开销和防止重连问题。
    task_ignore_result=False,
    # Redis 稳定性配置：定期健康检查，防止连接池中的长连接因超时被服务端关闭。
    redis_backend_health_check_interval=30,
    # 传输层配置。
    broker_transport_options={
        "visibility_timeout": 3600,  # 1小时未确认的任务会重回队列（避免长任务被误判为失败）
        "max_retries": 10,
    },
)


# ===== Prometheus metrics — Celery signals =====
@signals.task_prerun.connect
def _on_task_prerun(sender=None, **_kwargs):
    task_name = sender.name if sender else "unknown"
    CELERY_ACTIVE_TASKS.inc()
    CELERY_QUEUE_LENGTH.labels(queue=task_name).dec()


@signals.task_postrun.connect
def _on_task_postrun(sender=None, state=None, runtime=None, **_kwargs):
    task_name = sender.name if sender else "unknown"
    CELERY_ACTIVE_TASKS.dec()
    if runtime is not None:
        CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name).observe(runtime)
    CELERY_TASK_TOTAL.labels(
        task_name=task_name, status="success" if state == "SUCCESS" else "failure"
    ).inc()
