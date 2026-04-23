import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from backend.app.core.exceptions import AppException
from backend.app.core.response import Response

logger = logging.getLogger(__name__)


def _json_safe_errors(errors: list[dict]) -> list[dict]:
    # Pydantic 校验错误里可能带有不可直接序列化的对象。
    return jsonable_encoder(errors)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        # 业务层主动抛出的可预期异常统一在这里收口。
        logger.error("AppException: %s", exc.msg)
        return JSONResponse(
            status_code=exc.status_code,
            content=Response.fail(
                code=exc.code,
                msg=exc.msg,
                data=exc.data,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # 请求参数在进入路由前校验失败时，由 FastAPI 自动抛出。
        logger.error("RequestValidationError: %s", exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=Response.fail(
                code=422,
                msg="请求参数校验失败",
                data=_json_safe_errors(exc.errors()),
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        # 兼容框架层或手动抛出的 HTTPException，保持返回格式一致。
        logger.error("HTTPException: %s", exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=Response.fail(
                code=exc.status_code,
                msg=str(exc.detail),
                data=None,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # 最终兜底，避免把 Python 原始报错直接暴露给前端。
        logger.exception("Unhandled Exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=Response.fail(
                code=500,
                msg="服务器出现异常，请稍后重试",
                data=None,
            ).model_dump(),
        )
