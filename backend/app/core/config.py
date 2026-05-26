from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator, model_validator
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
    SENTRY_DSN: str | None = None
    SENTRY_ENVIRONMENT: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    # Web 服务运行配置。
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    BACKEND_CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "https://offer-copilot-frontend.vercel.app,"
        "https://offer-copilot-git-main-ren-meng-xues-projects.vercel.app,"
        "https://offer-copilot.vercel.app"
    )
    BACKEND_CORS_ORIGIN_REGEX: str | None = r"https://offer-copilot.*\.vercel\.app"

    # 基础设施配置，后续 auth、数据库和任务系统都会依赖这些变量。
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5433/offercopilot"
    )
    ALEMBIC_DATABASE_URL: Optional[str] = None

    # Redis 基础配置
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # 鉴权相关配置，后续 JWT 生成和校验会使用。
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
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
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    FIRECRAWL_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    COHERE_API_KEY: str | None = None
    COHERE_BASE_URL: str | None = None
    AMAP_API_KEY: str | None = None  # 高德开放平台 Web 服务 Key
    RAG_VECTOR_TOP_K: int = 20
    RAG_FTS_TOP_K: int = 20
    RAG_MIN_RERANK_SCORE: float = 0.15
    RAG_QUERY_REWRITE_ENABLED: bool = True
    RAG_QUERY_REWRITE_MODEL: str = "gpt-4o-mini"
    RAG_TELEMETRY_ENABLED: bool = True
    RAG_DEBUG_ENABLED: bool = False  # 是否开启 RAG debug 输出
    RAG_SCOPE_MAX_KNOWLEDGE_BASES: int = 3
    RAG_SCOPE_ROUTE_MIN_SCORE: float = 0.2
    RAG_VECTOR_TOP_K_PER_KB: int = 10
    RAG_FTS_TOP_K_PER_KB: int = 10
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None

    @staticmethod
    def _normalize_postgres_url(value: str, driver_scheme: str) -> str:
        """统一处理 Postgres URL，确保带上指定的驱动前缀（如 postgresql+asyncpg）。
        主要兼容 Railway 等平台提供的原始 postgres:// 格式。
        """
        if "://" not in value:
            return value

        # 统一把所有以 postgres 或 postgresql 开头的 scheme 都替换为目标 driver_scheme
        scheme, rest = value.split("://", 1)
        if scheme.startswith("postgres"):
            return f"{driver_scheme}://{rest}"

        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        return cls._normalize_postgres_url(str(value), "postgresql+asyncpg")

    @model_validator(mode="after")
    def validate_infrastructure_urls(self) -> "Settings":
        """在所有字段加载后，处理跨字段的 fallback 逻辑。"""

        # 1. 自动推导 ALEMBIC_DATABASE_URL (同步驱动)
        if not self.ALEMBIC_DATABASE_URL:
            self.ALEMBIC_DATABASE_URL = self._normalize_postgres_url(
                self.DATABASE_URL, "postgresql+psycopg2"
            )

        # 自动处理 Redis 相关的 fallback
        if self.REDIS_URL:
            if not self.CELERY_BROKER_URL:
                self.CELERY_BROKER_URL = self.REDIS_URL
        else:
            if not self.CELERY_BROKER_URL:
                self.CELERY_BROKER_URL = (
                    f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/1"
                )
                if self.REDIS_PASSWORD:
                    self.CELERY_BROKER_URL = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/1"

        return self

    @property
    def cors_allow_origins(self) -> list[str]:
        """把逗号分隔的前端来源转成 CORS 白名单。"""
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def cors_allow_origin_regex(self) -> str | None:
        """返回可选的 CORS 来源正则，空值统一折叠为 None。"""
        if self.BACKEND_CORS_ORIGIN_REGEX is None:
            return None

        regex = self.BACKEND_CORS_ORIGIN_REGEX.strip()
        return regex or None

    model_config = SettingsConfigDict(
        # 确保环境变量优先级最高，忽略本地可能存在的 .env 干扰
        env_file=BASE_DIR / ".env" if (BASE_DIR / ".env").exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例，避免在整个应用中重复读取环境变量。"""

    return Settings()


# 作为全局单例配置入口直接复用。
settings = get_settings()
