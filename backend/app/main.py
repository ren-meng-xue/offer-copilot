from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
import logging

from starlette.middleware.cors import CORSMiddleware

from backend.app.api.router import router as api_router
from backend.app.core.config import settings
from backend.app.core.cors import build_cors_middleware_options
from backend.app.core.exception_handlers import register_exception_handlers
from backend.app.core.logging import setup_logging
from backend.app.db import engine

# 1启动阶段先完成日志等基础设施初始化。
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"应用启动中，监听端口: {settings.APP_PORT}")
    logger.info(f"CORS 允许域: {settings.cors_allow_origins}")
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
    openapi_tags=[],
    lifespan=lifespan,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"收到请求: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"请求完成: {request.method} {request.url.path} - {response.status_code}")
    return response

@app.get("/")
async def root():
    return {"message": "OfferPilot API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# 配置 CORS 中间件，允许显式声明的前端来源访问。
app.add_middleware(CORSMiddleware, **build_cors_middleware_options(settings))
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
