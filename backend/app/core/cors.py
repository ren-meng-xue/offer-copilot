from typing import Any

from backend.app.core.config import Settings


def build_cors_middleware_options(settings: Settings) -> dict[str, Any]:
    """集中生成 CORS 中间件配置，避免在应用入口散落判断逻辑。"""
    options: dict[str, Any] = {
        "allow_origins": settings.cors_allow_origins,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "allow_credentials": True,
    }
    if settings.cors_allow_origin_regex is not None:
        options["allow_origin_regex"] = settings.cors_allow_origin_regex
    return options
