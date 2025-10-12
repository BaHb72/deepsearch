"""
API异常处理模块

提供统一的异常处理机制，避免500错误暴露内部信息
"""

import traceback
from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger


class APIException(Exception):
    """API异常基类"""

    def __init__(self, message: str, status_code: int = 500, details: Any = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class DataNotFoundError(APIException):
    """数据未找到异常"""

    def __init__(self, message: str = "请求的数据不存在"):
        super().__init__(message, status_code=404)


class InvalidParameterError(APIException):
    """参数无效异常"""

    def __init__(self, message: str = "请求参数无效"):
        super().__init__(message, status_code=400)


class ServiceUnavailableError(APIException):
    """服务不可用异常"""

    def __init__(self, message: str = "服务暂时不可用，请稍后重试"):
        super().__init__(message, status_code=503)


class DataProviderError(APIException):
    """数据提供者异常"""

    def __init__(self, message: str = "数据源访问失败"):
        super().__init__(message, status_code=502)


def handle_api_exceptions(func: Callable) -> Callable:
    """
    API异常处理装饰器

    将内部异常转换为用户友好的错误响应
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)

        except APIException as e:
            # 自定义API异常，记录并返回
            logger.warning(f"API异常: {e.message}, 状态码: {e.status_code}")
            raise HTTPException(
                status_code=e.status_code, detail={"error": e.message, "details": e.details}
            )

        except HTTPException as e:
            # FastAPI HTTP异常，直接抛出
            raise e

        except ValueError as e:
            # 值错误通常是参数问题
            logger.warning(f"参数错误: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "请求参数无效", "details": str(e)},
            )

        except KeyError as e:
            # 键错误通常是缺少必要字段
            logger.warning(f"缺少必要字段: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": f"缺少必要字段: {str(e)}", "details": None},
            )

        except ConnectionError as e:
            # 连接错误
            logger.error(f"连接错误: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": "服务连接失败，请稍后重试", "details": None},
            )

        except TimeoutError as e:
            # 超时错误
            logger.error(f"请求超时: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"error": "请求超时，请稍后重试", "details": None},
            )

        except Exception as e:
            # 未知异常，记录详细错误但不暴露给用户
            error_trace = traceback.format_exc()
            logger.error(f"未处理的异常: {str(e)}\n{error_trace}")

            # 开发环境返回详细错误，生产环境返回通用错误
            import os

            if os.getenv("APP__ENV", "prod") == "dev":
                detail = {
                    "error": "服务器内部错误",
                    "details": str(e),
                    "trace": error_trace.split("\n")[-5:],  # 只返回最后5行堆栈
                }
            else:
                detail = {"error": "服务器内部错误，请联系管理员", "details": None}

            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

    return wrapper


def setup_global_exception_handlers(app):
    """
    设置全局异常处理器

    Args:
        app: FastAPI应用实例
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        """处理FastAPI的请求验证错误"""
        errors = exc.errors()
        # 格式化错误消息
        error_messages = []
        for error in errors:
            loc = " -> ".join(str(part) for part in error.get("loc", []))
            msg = error.get("msg", "验证错误")
            error_messages.append(f"{loc}: {msg}")

        error_detail = "; ".join(error_messages) if error_messages else "请求参数验证失败"

        logger.warning(f"请求验证错误 [{request.url}]: {error_detail}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "请求参数验证失败",
                "detail": error_detail,
                "validation_errors": errors,
            },
        )

    @app.exception_handler(APIException)
    async def api_exception_handler(request, exc: APIException):
        """处理自定义API异常"""
        logger.warning(f"API异常 [{request.url}]: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "details": exc.details, "path": str(request.url)},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc: ValueError):
        """处理值错误"""
        logger.warning(f"值错误 [{request.url}]: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "请求参数无效", "details": str(exc), "path": str(request.url)},
        )


    @app.exception_handler(500)
    async def internal_error_handler(request, exc):
        """处理500错误"""
        logger.error(f"服务器内部错误 [{request.url}]: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "服务器内部错误，请稍后重试", "path": str(request.url)},
        )


class ErrorResponse:
    """统一的错误响应格式"""

    @staticmethod
    def bad_request(message: str = "请求参数无效", details: Any = None):
        """400 错误响应"""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"error": message, "details": details}
        )

    @staticmethod
    def unauthorized(message: str = "未授权访问"):
        """401 错误响应"""
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": message})

    @staticmethod
    def forbidden(message: str = "禁止访问"):
        """403 错误响应"""
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": message})

    @staticmethod
    def not_found(message: str = "资源未找到"):
        """404 错误响应"""
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": message})

    @staticmethod
    def internal_error(message: str = "服务器内部错误"):
        """500 错误响应"""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": message}
        )

    @staticmethod
    def service_unavailable(message: str = "服务暂时不可用"):
        """503 错误响应"""
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"error": message}
        )
