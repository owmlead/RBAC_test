"""
全局异常处理模块。
定义业务异常类和 FastAPI 异常处理器。

异常类层次结构：
    AppError（基类）
    ├── UnauthorizedError（401 未认证）
    ├── LockedError（401 账号锁定）
    ├── ForbiddenError（403 无权限）
    ├── NotFoundError（404 资源不存在）
    └── ConflictError（409 数据冲突）

所有业务异常通过 register_exception_handlers 注册后，
统一返回 JSON 格式 {"code": 业务码, "message": 描述, "data": null}。
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("rbac")


class AppError(Exception):
    """
    业务异常基类，所有业务异常均继承此类。

    通过 status_code 控制 HTTP 响应码，code 为业务错误码，
    便于前端根据 code 做差异化处理。

    :param message: 错误信息描述
    :param code: 业务错误码（与 HTTP 状态码对应）
    :param status_code: HTTP 状态码
    """

    def __init__(self, message: str, code: int = 400, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code


class ConflictError(AppError):
    """
    数据冲突异常（409 Conflict）。

    使用场景：唯一键重复（如用户名已存在）、数据版本冲突等。

    :param message: 错误信息
    """

    def __init__(self, message: str = "数据冲突"):
        super().__init__(message, code=409, status_code=409)


class ForbiddenError(AppError):
    """
    无权限异常（403 Forbidden）。

    使用场景：用户已认证但缺少所需权限、访问被拒绝等。

    :param message: 错误信息
    """

    def __init__(self, message: str = "无权限访问"):
        super().__init__(message, code=403, status_code=403)


class NotFoundError(AppError):
    """
    资源不存在异常（404 Not Found）。

    使用场景：查询的记录不存在、路由未找到等。

    :param message: 错误信息
    """

    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=404, status_code=404)


class UnauthorizedError(AppError):
    """
    未认证异常（401 Unauthorized）。

    使用场景：Token 缺失/无效/过期、未登录访问受保护资源等。

    :param message: 错误信息
    """

    def __init__(self, message: str = "未认证或Token无效"):
        super().__init__(message, code=401, status_code=401)


class LockedError(AppError):
    """
    账号锁定异常（401 Unauthorized）。

    使用场景：连续登录失败超过阈值导致账号被临时锁定。

    :param message: 错误信息
    """

    def __init__(self, message: str = "账号已锁定,请稍后重试"):
        super().__init__(message, code=401, status_code=401)


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器到 FastAPI 应用。

    注册两个异常处理器：
    1. AppError 及其子类 → 统一 JSON 响应（{"code", "message", "data"}）
    2. 未捕获的 Exception → 500 兜底响应，并记录错误日志

    :param app: FastAPI 应用实例
    :return: None
    """
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        """
        业务异常统一处理。

        将 AppError 及其所有子类异常转为统一的 JSON 响应格式，
        前端可通过 code 字段判断具体错误类型。

        :param _request: HTTP 请求对象（下划线前缀表示未使用）
        :param exc: 业务异常实例
        :return: JSON 响应，格式为 {"message": str, "code": int, "data": null}
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "message": exc.message,
                "code": exc.code,
                "data": None
            })

    @app.exception_handler(Exception)
    async def exception_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """
        未知异常兜底处理（500 Internal Server Error）。

        捕获所有未预期的 Python 异常，记录完整错误日志（含堆栈），
        向前端返回友好的错误提示，避免暴露内部实现细节。

        :param _request: HTTP 请求对象
        :param exc: 未捕获的异常实例
        :return: JSON 响应，HTTP 状态码 500
        """
        # 记录完整异常日志用于排查
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "message": "服务器开小差了",
                "code": 500,
                "data": None
            })
