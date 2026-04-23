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

    # 基础设施配置，后续 auth、数据库和任务系统都会依赖这些变量。
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/offercopilot"



    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # 鉴权相关配置，后续 JWT 生成和校验会使用。
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 小时

    # 预留给 AI 和对象存储能力，避免后面继续改配置模型。
    OPENAI_API_KEY: str | None = None
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET_NAME: str | None = None

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
