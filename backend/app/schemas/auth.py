# -*- coding: utf-8 -*-
"""
Time           : 2026/4/22 10:09
Author         : xuebao
File           : auth.py
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr

from backend.app.models.enums import UserStatus


class LoginRequest(BaseModel):
    """前端登陆请求体"""
    email: EmailStr = Field(..., description="用户邮箱")

    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="用户密码，长度要求8-128个字符",
    )


class LoginResponse(BaseModel):
    """前端成功后返回的数据"""

    access_token: str = Field(..., description="访问令牌，JWT格式")
    token_type: str = Field(default="bearer", description="令牌类型，默认为bearer")
    expires_in: int = Field(..., description="令牌过期时间，单位为秒")
    model_config = ConfigDict(from_attributes=True)  # 启用从属性加载数据的功能，允许直接从ORM模型实例创建Pydantic模型实例，而不需要手动转换为字典。


class RegisterRequest(BaseModel):
    """前端注册请求体"""
    email: EmailStr = Field(..., description="用户邮箱")
    username: str = Field(..., description="用户名")
    current_identity: str | None = Field(default=None, description="当前身份")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="登录密码",
    )


class UserInfoResponse(BaseModel):
    """获取当前登录用户信息的返回数据。"""

    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: EmailStr = Field(..., description="用户邮箱")
    status: UserStatus = Field(..., description="用户状态")
    current_identity: str | None = Field(default=None, description="当前身份")

    model_config = ConfigDict(from_attributes=True)


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求体"""
    email: EmailStr = Field(..., description="用户邮箱")


class ResetPasswordRequest(BaseModel):
    """重置密码请求体"""
    token: str = Field(..., description="重置密码令牌")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="新密码，长度要求8-128个字符",
    )