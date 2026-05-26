import logging
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"
SENSITIVE_KEYWORDS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "secret",
    "key",
)


def is_sensitive_key(key: str) -> bool:
    """判断字段名是否可能包含敏感凭据。"""

    normalized = key.lower().replace("-", "_")
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def sanitize_sentry_value(value: Any) -> Any:
    """递归脱敏 Sentry 事件中的敏感字段。"""

    if isinstance(value, dict):
        return {
            key: REDACTED if is_sensitive_key(str(key)) else sanitize_sentry_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [sanitize_sentry_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(sanitize_sentry_value(item) for item in value)

    return value


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """发送到 Sentry 前统一脱敏。"""

    return sanitize_sentry_value(event)


def setup_sentry() -> None:
    """按环境变量初始化 Sentry，未配置 DSN 时跳过。"""

    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN 未配置，跳过错误追踪初始化")
        return

    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT or settings.APP_ENV,
            integrations=[FastApiIntegration(), StarletteIntegration()],
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
            before_send=before_send,
        )
        logger.info("Sentry 错误追踪初始化完成")
    except Exception:
        logger.exception("Sentry 错误追踪初始化失败，应用将继续启动")
