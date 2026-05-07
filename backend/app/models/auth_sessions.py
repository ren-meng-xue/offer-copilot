# -*- coding: utf-8 -*-
"""
Time           : 2026/4/23 11:39
Author         : xuebao
File           : auth_sessions.py
"""
from datetime import datetime

from sqlalchemy import Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base
from backend.app.db.base import TimestampMixin


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_sessions"

    # 主键id
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # 用户id，外键关联到users表的id字段【 这条登陆会话属于谁】
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # refresh token 的哈希值，数据库不存明文 token
    refresh_token_hash:Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True
    )

    #这条 refresh 会话的自然过期时间【每一条refresh session 都必须知道什么时候过期】
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # 主动撤销时间；为空表示当前仍未被撤销
    revoked_at: Mapped[datetime | None] = mapped_column(
          DateTime(timezone=True),
          nullable=True,
    )
