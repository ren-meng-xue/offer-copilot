from fastapi import APIRouter
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.response import Response
from backend.app.db import get_db
from backend.app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from backend.app.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["认证模块"])


@router.post('/login', response_model=Response[LoginResponse], description="用户登录接口，接受邮箱和密码，返回访问令牌")
async def login(payload: LoginRequest,db:AsyncSession=Depends(get_db)) -> Response[LoginResponse]:
    """用户登陆接口"""
    result = await login_user(db,payload)
    return Response.success(data=result,msg="登录成功")


@router.post('/register', response_model=Response[None])
async def register(payload: RegisterRequest,db:AsyncSession = Depends(get_db)) -> Response[None]:
    """用户注册接口"""
    await register_user(db, payload)
    return Response.success(msg="注册成功")
