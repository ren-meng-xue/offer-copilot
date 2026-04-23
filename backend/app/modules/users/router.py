from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundException
from backend.app.core.response import Response
from backend.app.core.security import get_current_user
from backend.app.db import get_db
from backend.app.repositories.user_repository import get_user_by_id
from backend.app.schemas.auth import UserInfoResponse

router = APIRouter(prefix="/users", tags=["用户模块"])


@router.get("", response_model=Response[UserInfoResponse], description="获取当前登录用户信息，需要在请求头传递 Bearer Token")
async def get_current_user_info(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[UserInfoResponse]:
    """获取当前登录用户信息。"""
    user = await get_user_by_id(db, int(current_user_id))
    if user is None:
        raise NotFoundException(msg="用户不存在")

    return Response.success(
        data=UserInfoResponse.model_validate(user),
        msg="获取当前用户成功",
    )
