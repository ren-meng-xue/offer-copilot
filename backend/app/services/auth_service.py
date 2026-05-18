# -*- coding: utf-8 -*-
"""
Time           : 2026/4/22 11:20
Author         : xuebao
File           : auth_service.py
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models import User, PasswordResetToken, AuthSession
from backend.app.models.enums import UserStatus
from backend.app.repositories.user_repository import (
    get_user_by_email,
    get_user_by_username,
    create_user,
    get_user_by_id,
)
from backend.app.repositories.auth_repository import (
    create_auth_session,
    get_auth_session_by_refresh_token_hash,
    update_auth_session_token,
    revoke_auth_session,
)
from backend.app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
    BadRequestException,
)

from backend.app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    hash_token,
    create_refresh_token,
)
from backend.app.schemas import RegisterRequest, LoginRequest, LoginResponse
from backend.app.schemas.auth import ResetPasswordRequest, ForgotPasswordRequest
from backend.app.services.mail_service import send_password_reset_email


async def register_user(db: AsyncSession, payload: RegisterRequest) -> None:
    """注册用户
    邮箱不能重复
    """
    existing_user = await get_user_by_email(db, payload.email)
    if existing_user:
        raise ConflictException(msg="邮箱已存在")

    existing_username = await get_user_by_username(db, payload.username)
    if existing_username:
        raise ConflictException(msg="用户名已被占用")

    # 把明文密码变成哈希
    hashed_password = get_password_hash(payload.password)

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hashed_password,
        current_identity=payload.current_identity,
        status=UserStatus.ACTIVE,
        email_verified=False,  # 未验证
        failed_login_count=0,
    )
    await create_user(db, user)


async def login_user(
    db: AsyncSession, payload: LoginRequest
) -> tuple[LoginResponse, str]:
    """用户登陆。

    service 层负责生成业务结果和 refresh token 本身；
    路由层再把 refresh token 写入 cookie，因为 cookie 属于 HTTP 响应细节。
    """
    user = await get_user_by_email(db, payload.email)
    if not user:
        raise UnauthorizedException(msg="用户不存在")

    if not verify_password(payload.password, user.password_hash):
        raise UnauthorizedException(msg="密码错误")

    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedException(msg="当前账户不可登录")

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token()
    # 后端存的是密文，前端存的是明文，后端通过hash函数把明文变成密文存数据库，
    # 前端每次发请求时把明文发过来，后端再hash一次和数据库里存的密文比对，如果一样就说明是合法的
    refresh_token_hash = hash_token(refresh_token)
    refresh_expires_at = datetime.now(timezone.utc) + timedelta(
        # refresh token 过期时间改成按分钟配置，方便本地联调和自动续签测试。
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    await create_auth_session(  # 创建新的会话
        db=db,
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        expires_at=refresh_expires_at,  # 存数据库，需要具体时间
    )

    # access token 给前端正常调用接口使用；
    # refresh token 不放响应体，交给路由层写入 HttpOnly cookie。
    login_response = LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒 给前端用
    )
    return login_response, refresh_token


async def refresh_access_token(
    db: AsyncSession, refresh_token: str | None
) -> tuple[LoginResponse, str]:
    """刷新access token，并轮换refresh token"""
    # 先判断前端有没有带 refresh token
    # 2. 把明文 refresh token hash 一次
    # 3. 去 auth_sessions 查对应记录
    # 4. 判断 session 是否已撤销
    # 5. 判断 session 是否已过期
    # 6. 查这条 session 对应的用户是否还有效
    # 7. 生成新的 access token
    # 8. 生成新的 refresh token
    # 9. 更新 auth_sessions 里的 hash 和过期时间
    # 10. 返回新的 LoginResponse 和新的 refresh_token
    if not refresh_token:
        raise UnauthorizedException(msg="刷新令牌不存在，请重新登陆")
    refresh_token_hash = hash_token(refresh_token)
    auth_session = await get_auth_session_by_refresh_token_hash(
        db,
        refresh_token_hash,
    )
    if not auth_session:
        raise UnauthorizedException(msg="刷新令牌无效，请重新登录")
    now = datetime.now(timezone.utc)  # 拿到当前utc时间
    if auth_session.revoked_at is not None:
        raise UnauthorizedException(msg="当前会话已失效，请重新登录")

    if auth_session.expires_at <= now:
        raise UnauthorizedException(msg="刷新令牌已过期，请重新登录")

    user = await get_user_by_id(db, auth_session.user_id)

    if not user:
        raise UnauthorizedException(msg="用户不存在,请重新登陆")

    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedException(msg="当前账户不可登录")
    new_access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token()
    new_refresh_token_hash = hash_token(new_refresh_token)
    new_refresh_expires_at = now + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    await update_auth_session_token(
        db=db,
        auth_session=auth_session,
        refresh_token_hash=new_refresh_token_hash,
        expires_at=new_refresh_expires_at,
    )

    login_response = LoginResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return login_response, new_refresh_token


async def logout_user(db: AsyncSession, refresh_token: str | None) -> None:
    """退出登陆，把cookie的refresh token 撤销掉【当前的】"""
    if not refresh_token:
        return
    #
    # 1. 把明文 refresh token hash 一次
    refresh_token_hash = hash_token(refresh_token)

    # 2. 去 auth_sessions 查对应记录
    auth_session = await get_auth_session_by_refresh_token_hash(
        db,
        refresh_token_hash,
    )

    if not auth_session:
        return

    if auth_session.revoked_at is not None:  # 如果已经撤销了
        return

    await revoke_auth_session(
        db=db,
        auth_session=auth_session,
        revoked_at=datetime.now(timezone.utc),  # 把当前时间作为撤销时间
    )


def _build_password_reset_link(token: str, email: str) -> str:
    """根据传递过来的token去构建一个密码重置链接，发到用户邮箱里"""
    query = urlencode(
        {
            "token": token,
            "email": email,
        }
    )
    return f"{settings.PASSWORD_RESET_URL_BASE}?{query}"


async def request_password_reset(
    db: AsyncSession, payload: ForgotPasswordRequest
) -> None:
    user = await get_user_by_email(db, payload.email)
    # 不暴露邮箱是否存在，防止被枚举。
    if not user or user.status != UserStatus.ACTIVE:
        return
    now = datetime.now(timezone.utc)
    raw_token = create_refresh_token()  # 创建一个随机的token
    token_hash = hash_token(raw_token)  # 把token哈希一下
    expires_at = now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),  # 之前没用过的token
            PasswordResetToken.revoked_at.is_(None),  # 之前没撤销过的
            PasswordResetToken.expires_at > now,
        )
        .values(revoked_at=now)  # 把符合条件的记录的revoked_at置更新为当前时间
    )

    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,  # 存的是hash过后的
            expires_at=expires_at,  # 邮箱连接失效时间
            used_at=None,  # 没被用过
            revoked_at=None,  # 没被撤销过
            created_at=now,
        )
    )

    await db.commit()
    reset_link = _build_password_reset_link(raw_token, user.email)
    await send_password_reset_email(user.email, reset_link)


async def reset_password_by_token(
    db: AsyncSession,
    payload: ResetPasswordRequest,
) -> None:
    """通过 token 来重置密码"""
    now = datetime.now(timezone.utc)
    token_hash = hash_token(payload.token)  # hash过后的token

    result = await db.execute(
        # 首先通过token 先查询出在这个PasswordResetToken表里有没有这个token的记录，如果没有，说明这个链接无效或者过期了
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_record = result.scalar_one_or_none()

    if not reset_record:
        raise BadRequestException(msg="重置链接无效或已过期")

    if reset_record.used_at is not None:
        raise BadRequestException(msg="该重置链接已经使用过了")

    if reset_record.revoked_at is not None:
        raise BadRequestException(msg="该重置链接已经失效")

    if reset_record.expires_at <= now:
        raise BadRequestException(msg="重置链接已过期")

    user = await get_user_by_id(db, reset_record.user_id)
    if not user:
        raise BadRequestException(msg="重置链接无效或已过期")

    if user.status != UserStatus.ACTIVE:
        raise BadRequestException(msg="当前账户不可重置密码")

    if verify_password(payload.new_password, user.password_hash):
        raise BadRequestException(msg="新密码不能与旧密码相同")

    user.password_hash = get_password_hash(payload.new_password)
    reset_record.used_at = now

    # 改完密码后，把该用户现有 refresh session 全部撤销。
    await db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    await db.commit()
