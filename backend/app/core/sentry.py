import logging
import re
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
)

NON_SENSITIVE_KEYWORDS = (
    "tokenizer",
    "vector",
    "chunk",
    "keyboard",
    "hotkey",
    "keymap",
)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
SENSITIVE_ASSIGN_REGEX = re.compile(
    r"(authorization|cookie|password|passwd|token|api_key|secret|private_key|secret_key)[\s:=\'\"]+([^\s\'\",&]+)",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    """判断字段名是否可能包含敏感凭据。"""
    normalized = key.lower().replace("-", "_")

    # 1. 首先检查是否包含白名单（非敏感）关键字，如果有，直接判定为非敏感
    if any(ns in normalized for ns in NON_SENSITIVE_KEYWORDS):
        return False

    # 2. 检查是否包含明确的敏感字眼或 key 字眼
    if any(keyword in normalized for keyword in SENSITIVE_KEYWORDS):
        return True

    if "key" in normalized:
        return True

    return False


def sanitize_sentry_string(val: str) -> str:
    """脱敏字符串中可能存在的敏感信息，如 Email 或 password=xxx。"""
    val = EMAIL_REGEX.sub("[EMAIL_REDACTED]", val)
    val = SENSITIVE_ASSIGN_REGEX.sub(r"\1=[REDACTED]", val)
    return val


def sanitize_sentry_value(value: Any) -> Any:
    """递归脱敏 Sentry 事件中的敏感字段，支持基本类型、复杂对象与异常文本。"""
    if value is None:
        return None

    if isinstance(value, dict):
        return {
            key: REDACTED if is_sensitive_key(str(key)) else sanitize_sentry_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [sanitize_sentry_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(sanitize_sentry_value(item) for item in value)

    if isinstance(value, str):
        return sanitize_sentry_string(value)

    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        try:
            return sanitize_sentry_value(value.model_dump())
        except Exception:
            pass

    if hasattr(value, "dict") and callable(getattr(value, "dict")):
        try:
            return sanitize_sentry_value(value.dict())
        except Exception:
            pass

    if hasattr(value, "__dataclass_fields__"):
        try:
            import dataclasses

            return sanitize_sentry_value(dataclasses.asdict(value))
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return sanitize_sentry_value(value.__dict__)
        except Exception:
            pass

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
