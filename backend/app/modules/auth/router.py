from fastapi import APIRouter, Response as FastAPIResponse, Request
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.response import Response
from backend.app.db import get_db
from backend.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ForgotPasswordRequest,
)
from backend.app.services.auth_service import (
    register_user,
    login_user,
    refresh_access_token,
    logout_user,
    request_password_reset,
    reset_password_by_token,
)

router = APIRouter(prefix="/auth", tags=["认证模块"])


def set_refresh_token_cookie(response: FastAPIResponse, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/login",
    response_model=Response[LoginResponse],
    summary="登陆接口",
    description="用户登录接口，接受邮箱和密码，返回访问令牌",
)
async def login(
    payload: LoginRequest, response: FastAPIResponse, db: AsyncSession = Depends(get_db)
) -> Response[LoginResponse]:
    """用户登陆接口"""
    result, refresh_token = await login_user(db, payload)
    # refresh token 属于长期凭证，不再放到响应体里暴露给前端 JS。
    # 这里改为写入 HttpOnly cookie，这样浏览器后续调用 refresh 接口时会自动携带，
    # 同时前端脚本无法直接读取，能降低 XSS 场景下 refresh token 被窃取的风险。
    #
    # 这一步放在路由层而不是 service 层，是因为 cookie 本质上是 HTTP 响应的一部分，
    # service 负责业务编排，router 负责具体的响应细节（如 set_cookie、header、status code）。
    set_refresh_token_cookie(response, refresh_token)
    return Response.success(data=result, msg="登录成功")


@router.post(
    "/register",
    response_model=Response[None],
    summary="注册接口",
    description="用户注册接口，接受用户名、邮箱和密码，创建新用户",
)
async def register(
    payload: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> Response[None]:
    """用户注册接口"""
    await register_user(db, payload)
    return Response.success(msg="注册成功")


@router.post(
    "/refresh-token",
    summary="刷新访问令牌接口",
    response_model=Response[LoginResponse],
    description="用户刷新访问令牌接口，接受 refresh token cookie，返回新的访问令牌",
)
async def refresh_token(
    request: Request, response: FastAPIResponse, db: AsyncSession = Depends(get_db)
) -> Response[LoginResponse]:
    """用户刷新访问令牌接口"""
    incoming_refresh_token = request.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME
    )  # 从浏览器自动带过来的cookie里取明文refresh token
    result, new_refresh_token = await refresh_access_token(
        db, incoming_refresh_token
    )  # 传递给了这个函数
    # 调用service，校验旧refresh token 合法后，生成新的访问令牌和refresh token

    set_refresh_token_cookie(response, new_refresh_token)
    return Response.success(data=result, msg="刷新成功")


@router.post(
    "/forgot-password",
    response_model=Response[None],
    summary="忘记密码接口",
    description="用户提交邮箱后，系统发送重置密码链接",
)
async def forgot_password(
    payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
) -> Response[None]:
    """用户忘记密码接口"""
    await request_password_reset(db, payload)
    return Response.success(msg="如果邮箱已注册，我们已发送重置指引")


@router.post(
    "/reset-password",
    response_model=Response[None],
    summary="重置密码接口",
    description="用户提交重置令牌和新密码后，完成密码重置",
)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> Response[None]:
    """用户重置密码接口"""
    await reset_password_by_token(db, payload)
    return Response.success(msg="密码已重置")


def clear_refresh_token_cookie(response: FastAPIResponse) -> None:
    """清除 refresh token cookie，
    通常在用户退出登录时调用
    通过设置相同的 cookie 名称和路径，并将过期时间设置为过去的时间来实现。"""
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )


@router.post(
    "/logout",
    summary="退出登陆",
    description="用户退出登录接口，清除 refresh token cookie",
)
async def logout(
    request: Request, response: FastAPIResponse, db: AsyncSession = Depends(get_db)
):
    """用户退出登陆接口"""
    incoming_refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    await logout_user(db, incoming_refresh_token)
    clear_refresh_token_cookie(response)
    return Response.success(msg="退出成功")
