from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 指向 backend 根目录，便于统一定位 .env。
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """项目配置，优先从环境变量加载，本地开发时回退到 backend/.env。"""

    # 应用基础配置。
    APP_NAME: str = "OfferPilot API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # Web 服务运行配置。
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # 基础设施配置，后续 auth、数据库和任务系统都会依赖这些变量。
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/offercopilot"
    ALEMBIC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5433/offercopilot"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # 鉴权相关配置，后续 JWT 生成和校验会使用。
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60
    # 密码重置链接有效期，单位分钟。
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    # 发邮件时拼接的前端重置密码页面地址。
    PASSWORD_RESET_URL_BASE: str = "http://localhost:3000/auth/reset-password"
    # SMTP 邮件配置。默认值按 QQ 邮箱本地联调场景给出。
    SMTP_HOST: str = "smtp.qq.com"
    SMTP_PORT: int = 465
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_SSL: bool = True
    SMTP_USE_STARTTLS: bool = False
    SMTP_TIMEOUT_SECONDS: int = 15
    MAIL_FROM: str | None = None
    MAIL_FROM_NAME: str = "OfferPilot"
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    # 只让 refresh 接口自动携带该 cookie，减少不必要的请求暴露面。
    REFRESH_TOKEN_COOKIE_PATH: str = "/api/v1/auth/"
    # 本地开发通常没有 HTTPS，默认关闭；生产环境应改为 true。
    REFRESH_TOKEN_COOKIE_SECURE: bool = False
    # 前后端同站开发时先用 lax，后续跨站部署再按实际情况调整。
    REFRESH_TOKEN_COOKIE_SAMESITE: str = "lax"

    # Celery broker/backend 都指向 Redis，DB 编号与主 Redis 隔离。
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    FIRECRAWL_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    COHERE_API_KEY: str | None = None
    RAG_DEBUG_ENABLED: bool = False  # 是否开启 RAG debug 输出
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None

    @property
    def cors_allow_origins(self) -> list[str]:
        """把逗号分隔的前端来源转成 CORS 白名单。"""
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        # 本地开发默认读取 backend/.env，容器环境下可直接由环境变量覆盖。
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例，避免在整个应用中重复读取环境变量。"""

    return Settings()


# 作为全局单例配置入口直接复用。
settings = get_settings()
