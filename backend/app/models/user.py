from datetime import datetime

from sqlalchemy import String, Enum, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base
from backend.app.db.base import TimestampMixin
from backend.app.models.enums import UserStatus


class User(Base,TimestampMixin):
    __tablename__ = "users"

    # 用户id自增
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 邮箱
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,  # 不能为空
        index=True,  # 索引
        unique=True,  # 唯一索引
    )

    # 用户名字【必填】
    username: Mapped[str] = mapped_column(
        String(50), unique=True,  # 唯一索引
        index=True
    )

    # 当前身份，例如求职中、在职、在校等，先作为可选的用户画像信息。
    current_identity: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # 密码哈希
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False  # 不能为空
    )

    # 用户状态
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus),
        nullable=False,
        default=UserStatus.ACTIVE
    )

    # 邮箱是否验证
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    # 上次登陆时间
    last_login_at: Mapped[datetime | None]=mapped_column(
        DateTime,
        nullable=True# 允许为空
    )

    #  登陆失败次数
    failed_login_count:Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    # 锁定时间
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
