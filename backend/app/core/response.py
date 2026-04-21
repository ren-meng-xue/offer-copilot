from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """统一响应结构。"""

    code: int = 0
    msg: str = "success"
    data: Optional[T] = None

    @staticmethod
    def success(data: Optional[T] = None, msg: str = "success") -> "Response[T]":
        # 成功响应统一走 code=0，便于前端按固定结构处理。
        return Response(code=0, msg=msg, data=data)

    @staticmethod
    def fail(code: int, msg: str, data: Optional[T] = None) -> "Response[T]":
        return Response(code=code, msg=msg, data=data)
