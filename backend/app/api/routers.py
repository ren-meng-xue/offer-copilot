from fastapi import FastAPI
from app.modules.auth.router import router as auth_router


def register_routers(app: FastAPI) -> None:
    """
    将各个模块的路由注册到 FastAPI 应用中

    """

    app.include_router(
        auth_router,
        prefix="/api/v1",  # 统一接口前缀（版本 + 模块）

    )
