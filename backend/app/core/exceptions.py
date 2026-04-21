from typing import Any

from fastapi import status


class AppException(Exception):
    """项目基础异常类，用于承接可预期的业务错误。"""

    def __init__(
        self,
        msg: str = "应用发生错误，请稍后重试",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        data: Any = None,
        code: int | None = None,
    ) -> None:
        # code 面向前端返回，status_code 面向 HTTP 语义。
        self.msg = msg
        self.status_code = status_code
        self.data = data
        self.code = code if code is not None else status_code
        super().__init__(msg)


class BadRequestException(AppException):
    def __init__(self, msg: str = "客户端请求错误，请检查后重试", data: Any = None) -> None:
        super().__init__(
            msg=msg,
            status_code=status.HTTP_400_BAD_REQUEST,
            data=data,
            code=400,
        )


class UnauthorizedException(AppException):
    def __init__(self, msg: str = "未登录或登录已失效", data: Any = None) -> None:
        super().__init__(
            msg=msg,
            status_code=status.HTTP_401_UNAUTHORIZED,
            data=data,
            code=401,
        )


class ForbiddenException(AppException):
    def __init__(self, msg: str = "无权限执行当前操作", data: Any = None) -> None:
        super().__init__(
            msg=msg,
            status_code=status.HTTP_403_FORBIDDEN,
            data=data,
            code=403,
        )


class NotFoundException(AppException):
    def __init__(self, msg: str = "资源未找到，请核实后重试", data: Any = None) -> None:
        super().__init__(
            msg=msg,
            status_code=status.HTTP_404_NOT_FOUND,
            data=data,
            code=404,
        )


class ConflictException(AppException):
    def __init__(self, msg: str = "资源冲突，请检查后重试", data: Any = None) -> None:
        super().__init__(
            msg=msg,
            status_code=status.HTTP_409_CONFLICT,
            data=data,
            code=409,
        )
