# -*- coding: utf-8 -*-
"""
Time           : 2026/4/22 11:20
Author         : xuebao
File           : auth_service.py
"""
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import User
from backend.app.models.enums import UserStatus
from backend.app.repositories.user_repository import get_user_by_email, get_user_by_username, create_user
from backend.app.core.exceptions import ConflictException, UnauthorizedException

from backend.app.core.security import get_password_hash, verify_password, create_access_token
from backend.app.schemas import RegisterRequest, LoginRequest, LoginResponse


async def register_user(
        db: AsyncSession,
        payload: RegisterRequest
) -> None:
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


async def login_user(db:AsyncSession,payload:LoginRequest)->LoginResponse:
    """用户登陆"""
    user = await get_user_by_email(db, payload.email)
    if not user:
        raise UnauthorizedException(msg="用户不存在")

    if not verify_password(payload.password, user.password_hash):
        raise UnauthorizedException(msg="密码错误")

    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedException(msg="当前账户不可登录")

    access_token = create_access_token(data={"sub": str(user.id)})
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
    )
