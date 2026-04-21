from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from app.api.routers import register_routers
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers

openapi_tags = [
    {
        "name": "认证",
        "description": "用于处理用户注册、登录、身份校验与账户访问。",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 预留应用启动和关闭时的资源初始化逻辑。
    yield


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

# 应用级基础能力先挂载，再注册具体业务路由。
register_exception_handlers(app)
register_routers(app)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
