# -*- coding: utf-8 -*-
"""
Time           : 2026/4/22 11:21
Author         : xuebao
File           : user_repository.py
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import User

async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """按用户 ID 查询用户。"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> User:
    """注册的时候需要先查询一下邮箱存不存在，所以这个函数是判断邮箱存在不存在"""
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalars().one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """查用户名是否已存在"""
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalars().one_or_none()


async def create_user(db: AsyncSession, user: User) -> User:
    """创建新用户并返回落库后的对象。"""
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
