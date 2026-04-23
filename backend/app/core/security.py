# -*- coding: utf-8 -*-
"""
Time           : 2026/4/22 13:01
Author         : xuebao
File           : security.py
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer

from backend.app.core.config import settings


#这个作用不是登陆，而是从请求头里帮拿token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# 🔒 将明文密码加密（注册时使用）
def get_password_hash(password: str) -> str:
    """
    把用户输入的明文密码 → 加密成 hash
    存入数据库的是 hash，而不是原始密码
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


# 🔍 校验密码是否正确（登录时使用）
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    对比：
    - 用户输入的密码（明文）
    - 数据库中存的密码（hash）

    返回：
    - True：密码正确
    - False：密码错误
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# 🎫 创建 JWT 访问令牌（登录成功后生成）
def create_access_token(data: dict) -> str:
    """
    生成 JWT token

    参数：
    - data: 要编码的数据（通常包含 user_id 或 email）

    返回：
    - JWT 字符串（access_token）
    """

    # 📦 复制数据，避免修改原始字典
    to_encode = data.copy()

    # ⏰ 设置过期时间（例如：24小时）
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # 🧾 把过期时间加入 payload（JWT 标准字段：exp）
    to_encode.update({"exp": expire})

    # 🔐 生成 JWT
    return jwt.encode(
        to_encode,                 # payload（数据）
        settings.SECRET_KEY,       # 密钥（必须保密！）
        algorithm=settings.ALGORITHM,  # 加密算法（如 HS256）
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """从请求头中获取并校验 JWT，返回当前登录用户 ID。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失败，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return user_id
