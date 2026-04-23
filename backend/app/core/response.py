from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """统一响应结构，默认让响应体 code 与 HTTP 状态语义保持一致。"""

    code: int = 200
    msg: str = "success"
    data: Optional[T] = None

    @staticmethod
    def success(
        data: Optional[T] = None,
        msg: str = "success",
        code: int = 200,
    ) -> "Response[T]":
        # 成功响应默认与 HTTP 成功语义对齐，统一返回 code=200。
        return Response(code=code, msg=msg, data=data)

    @staticmethod
    def fail(code: int, msg: str, data: Optional[T] = None) -> "Response[T]":
        # 失败响应默认直接返回业务码，当前约定与 HTTP 状态码保持一致。
        return Response(code=code, msg=msg, data=data)
