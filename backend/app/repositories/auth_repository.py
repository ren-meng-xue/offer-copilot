# -*- coding: utf-8 -*-
"""
Time           : 2026/4/23 12:03
Author         : xuebao
File           : auth_repository.py
"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.auth_sessions import AuthSession


async def create_auth_session(
        db: AsyncSession,
        user_id: int,
        refresh_token_hash: str,
        expires_at: datetime
) -> AuthSession:
    """创建新的认证会话"""
    auth_session = AuthSession(
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
    )
    db.add(auth_session)
    await db.commit()
    await db.refresh(auth_session)
    return auth_session


async def get_auth_session_by_refresh_token_hash(
        db: AsyncSession,
        refresh_token_hash: str
) -> AuthSession | None:
    """通过 refresh_token_hash 查询认证会话"""
    # 前端传来 明文 refresh_token
    # - 后端对这个明文执行一次 hash_token(refresh_token)
    # - 得到一个 hash 值
    # - 再拿这个 hash 值 去和数据库字段 refresh_token_hash 比较

    stmt = select(AuthSession).where(AuthSession.refresh_token_hash == refresh_token_hash)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_auth_session_token(
        db: AsyncSession,
        auth_session: AuthSession,
        refresh_token_hash: str,
        expires_at: datetime
) -> AuthSession:
    """更新认证会话的 refresh token 和过期时间"""
    # 这个是前端发现access token 过期了会调用/refresh接口
    # 我们要在当前记录上创建一个新的refresh token
    # 要知道当前的refreshtoken还能用的情况下 ，允许前端调用/refresh接口
    auth_session.refresh_token_hash = refresh_token_hash
    auth_session.expires_at = expires_at
    auth_session.revoked_at = None  # 重置撤销状态
    await db.commit()
    await db.refresh(auth_session)
    return auth_session


async def revoke_auth_session(
        db: AsyncSession,
        auth_session: AuthSession,
        revoked_at: datetime,
) -> AuthSession:
    """一般是前端退出登陆的时候，会用这个，前端会把它的refresh token 传过来，
    后端根据这个refresh token 找到对应的 auth session 记录，然后把它撤销掉"""
    auth_session.revoked_at = revoked_at #这条refresh session 从传递的这个datetime时间失效
    await db.commit()
    await db.refresh(auth_session)
    return auth_session
