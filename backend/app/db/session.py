from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 全局异步引擎，统一复用连接池配置。
engine = create_async_engine(
settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# 统一的异步 Session 工厂，Repository / Service 层都从这里拿会话。
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入入口，按请求提供数据库会话。"""

    async with async_session_factory() as session:
        yield session
