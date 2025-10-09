"""
API响应格式化工具

提供统一的API响应格式、错误代码定义和异常处理
"""

from enum import IntEnum
from typing import Any, Dict, Optional

# 从exception_handlers导入APIException以便重新导出
from deepsearch.webui.api.exception_handlers import APIException


class ErrorCodes(IntEnum):
    """错误代码枚举"""

    # 通用错误
    SUCCESS = 0
    INTERNAL_ERROR = 500
    INVALID_PARAMETERS = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404

    # 数据库相关错误
    DATABASE_NOT_FOUND = 4001
    DATABASE_ALREADY_EXISTS = 4002
    DATABASE_CONNECTION_FAILED = 4003
    DATABASE_OPERATION_FAILED = 4004

    # 数据源相关错误
    DATA_SOURCE_ERROR = 5001
    DATA_SOURCE_NOT_FOUND = 5002
    DATA_SOURCE_UNAVAILABLE = 5003
    DATA_SOURCE_TIMEOUT = 5004
    DATASOURCE_NOT_FOUND = 5005
    DATASOURCE_CONNECTION_FAILED = 5006
    DATASOURCE_TEST_FAILED = 5007
    DATASOURCE_NOT_ENABLED = 5008
    DATASOURCE_NOT_ONLINE = 5009

    # 业务逻辑错误
    BUSINESS_ERROR = 6001
    VALIDATION_ERROR = 6002
    OPERATION_NOT_ALLOWED = 6003


class APIResponse:
    """统一的API响应格式类"""

    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """
        创建成功响应

        Args:
            data: 响应数据
            message: 成功消息

        Returns:
            格式化的成功响应字典
        """
        return {"code": ErrorCodes.SUCCESS, "message": message, "data": data, "success": True}

    @staticmethod
    def error(
        code: ErrorCodes = ErrorCodes.INTERNAL_ERROR,
        message: str = "Error occurred",
        data: Optional[Any] = None,
        details: Optional[Any] = None,
        status_code: int = 500,
    ) -> Dict[str, Any]:
        """
        创建错误响应

        Args:
            code: 错误代码（使用ErrorCodes枚举）
            message: 错误消息
            data: 额外的错误详情
            details: 详细错误信息（兼容旧版本）
            status_code: HTTP状态码（用于FastAPI响应）

        Returns:
            格式化的错误响应字典
        """
        response = {
            "code": int(code),  # 转换为整数
            "message": message,
            "success": False,
            "status_code": status_code,  # 添加状态码
        }
        # 优先使用data，如果没有则使用details
        if data is not None:
            response["data"] = data
        elif details is not None:
            response["details"] = details
        return response


def success_response(data: Any, message: str = "Success") -> Dict[str, Any]:
    """
    格式化成功响应（兼容旧版本）

    Args:
        data: 响应数据
        message: 成功消息

    Returns:
        格式化的响应字典
    """
    return APIResponse.success(data, message)


def error_response(message: str, code: int = 1, data: Optional[Any] = None) -> Dict[str, Any]:
    """
    格式化错误响应（兼容旧版本）

    Args:
        message: 错误消息
        code: 错误代码
        data: 额外的错误数据

    Returns:
        格式化的响应字典
    """
    # 将整数代码转换为ErrorCodes，如果不存在则使用INTERNAL_ERROR
    error_code = ErrorCodes.INTERNAL_ERROR
    for ec in ErrorCodes:
        if int(ec) == code:
            error_code = ec
            break

    return APIResponse.error(error_code, message, data)


# 导出所有需要的类和函数
__all__ = ["APIResponse", "APIException", "ErrorCodes", "success_response", "error_response"]
