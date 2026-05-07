# -*- coding: utf-8 -*-
"""
Time           : 2026/4/23 16:20
Author         : xuebao
File           : password_reset_tokens.py
"""
from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base

class PasswordResetToken(Base):
    """密码重置令牌表。

    用于支撑“忘记密码 -> 邮件链接 -> 重置密码”链路。
    数据库只保存 token 的哈希值，不保存明文，避免数据库泄露时直接暴露重置链接。
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 关联发起密码重置的用户；用户被删除时，这类临时令牌也一起清理。
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 只保存 reset token 的哈希值，邮件里的明文 token 不直接落库。
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # token到哪一个具体时间点失效。
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # 如果这个值为有时间，表示这个连接已经成功过一次，后续不能在用
    # 如果为空，则表示没有用过
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 让系统能主动让旧链接提前失效
    # - 保证“最新一封重置邮件”才是有效的
    # - 避免用户邮箱里多封旧邮件都还能拿来改密码
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 记录令牌创建时间，便于审计、排查和清理过期数据。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

