from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
import logging

from starlette.middleware.cors import CORSMiddleware

from backend.app.api.router import router as api_router
from backend.app.core.config import settings
from backend.app.core.exception_handlers import register_exception_handlers
from backend.app.core.logging import setup_logging
from backend.app.db import engine

# 1启动阶段先完成日志等基础设施初始化。
setup_logging()
logger = logging.getLogger(__name__)

openapi_tags = [
    # {
    #     "name": "认证",
    #     "description": "用于处理用户注册、登录、身份校验与账户访问。",
    # },
    #
    # {
    #     "name": "xx",
    #     "description": "用于处理用户注册、登录、身份校验与账户访问。",
    # },
]



@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("应用启动完成")
    yield
    logger.info("应用关闭中")
    await engine.dispose()
    logger.info("数据库连接池已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "OfferPilot backend 当前先聚焦登录与注册能力，"
        "后续再逐步补充 JD、简历、分析和生成等业务模块。"
    ),
    openapi_tags=openapi_tags,
    lifespan=lifespan,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)


#配置CORS中间件，允许所有来源的跨域请求

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
    allow_credentials=True,  # 允许携带凭证（如Cookies）
)
# 应用级基础能力先挂载，再注册具体业务路由。
register_exception_handlers(app)
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
