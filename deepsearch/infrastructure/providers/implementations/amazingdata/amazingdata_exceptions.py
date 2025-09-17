#!/usr/bin/env python
# encoding:utf-8
"""
AmazingData 自定义异常类
提供详细的错误分类和处理机制
"""

from enum import Enum
from typing import Optional

from deepsearch.infrastructure.providers.base import DataProviderError


class AmazingDataErrorCode(Enum):
    """AmazingData 错误代码枚举"""

    # 连接相关错误 (1xxx)
    CONNECTION_FAILED = 1001
    LOGIN_FAILED = 1002
    AUTHENTICATION_ERROR = 1003
    NETWORK_TIMEOUT = 1004
    CONNECTION_LOST = 1005
    HEARTBEAT_FAILED = 1006

    # 数据查询错误 (2xxx)
    QUERY_FAILED = 2001
    INVALID_SYMBOL = 2002
    INVALID_PERIOD = 2003
    INVALID_DATE_RANGE = 2004
    NO_DATA_AVAILABLE = 2005
    DATA_FORMAT_ERROR = 2006

    # 订阅相关错误 (3xxx)
    SUBSCRIPTION_FAILED = 3001
    SUBSCRIPTION_LIMIT_EXCEEDED = 3002
    INVALID_SUBSCRIPTION_TYPE = 3003
    SUBSCRIPTION_NOT_FOUND = 3004

    # 系统错误 (4xxx)
    SDK_NOT_INSTALLED = 4001
    SDK_VERSION_MISMATCH = 4002
    CONFIGURATION_ERROR = 4003
    INTERNAL_ERROR = 4999

    # 限流错误 (5xxx)
    RATE_LIMIT_EXCEEDED = 5001
    QUOTA_EXCEEDED = 5002
    CONCURRENT_LIMIT_EXCEEDED = 5003


class AmazingDataException(DataProviderError):
    """AmazingData 基础异常类"""

    def __init__(
            self,
            message: str,
            error_code: AmazingDataErrorCode,
            details: Optional[dict] = None,
            original_exception: Optional[Exception] = None
    ):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
            details: 详细信息字典
            original_exception: 原始异常
        """
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception

    def __str__(self):
        """格式化错误消息"""
        msg = f"[{self.error_code.name}] {super().__str__()}"
        if self.details:
            msg += f" | Details: {self.details}"
        if self.original_exception:
            msg += f" | Original: {str(self.original_exception)}"
        return msg


class AmazingDataConnectionError(AmazingDataException):
    """连接相关异常"""

    def __init__(
            self,
            message: str = "连接失败",
            error_code: AmazingDataErrorCode = AmazingDataErrorCode.CONNECTION_FAILED,
            **kwargs
    ):
        super().__init__(message, error_code, **kwargs)


class AmazingDataAuthenticationError(AmazingDataException):
    """认证相关异常"""

    def __init__(
            self,
            message: str = "认证失败",
            error_code: AmazingDataErrorCode = AmazingDataErrorCode.AUTHENTICATION_ERROR,
            **kwargs
    ):
        super().__init__(message, error_code, **kwargs)


class AmazingDataQueryError(AmazingDataException):
    """查询相关异常"""

    def __init__(
            self,
            message: str = "查询失败",
            error_code: AmazingDataErrorCode = AmazingDataErrorCode.QUERY_FAILED,
            **kwargs
    ):
        super().__init__(message, error_code, **kwargs)


class AmazingDataSubscriptionError(AmazingDataException):
    """订阅相关异常"""

    def __init__(
            self,
            message: str = "订阅失败",
            error_code: AmazingDataErrorCode = AmazingDataErrorCode.SUBSCRIPTION_FAILED,
            **kwargs
    ):
        super().__init__(message, error_code, **kwargs)


class AmazingDataRateLimitError(AmazingDataException):
    """限流相关异常"""

    def __init__(
            self,
            message: str = "请求频率超限",
            error_code: AmazingDataErrorCode = AmazingDataErrorCode.RATE_LIMIT_EXCEEDED,
            retry_after: Optional[int] = None,
            **kwargs
    ):
        details = kwargs.get('details', {})
        if retry_after:
            details['retry_after'] = retry_after
        kwargs['details'] = details
        super().__init__(message, error_code, **kwargs)


class ErrorHandler:
    """错误处理器"""

    @staticmethod
    def handle_login_error(error: Exception) -> AmazingDataException:
        """处理登录错误"""
        error_msg = str(error).lower()

        if "timeout" in error_msg:
            return AmazingDataConnectionError(
                "登录超时",
                AmazingDataErrorCode.NETWORK_TIMEOUT,
                original_exception=error
            )
        elif "authentication" in error_msg or "password" in error_msg:
            return AmazingDataAuthenticationError(
                "用户名或密码错误",
                AmazingDataErrorCode.AUTHENTICATION_ERROR,
                original_exception=error
            )
        elif "network" in error_msg or "connection" in error_msg:
            return AmazingDataConnectionError(
                "网络连接失败",
                AmazingDataErrorCode.CONNECTION_FAILED,
                original_exception=error
            )
        else:
            return AmazingDataConnectionError(
                f"登录失败: {error}",
                AmazingDataErrorCode.LOGIN_FAILED,
                original_exception=error
            )

    @staticmethod
    def handle_query_error(error: Exception, query_type: str = None) -> AmazingDataException:
        """处理查询错误"""
        error_msg = str(error).lower()

        if "no data" in error_msg or "empty" in error_msg:
            return AmazingDataQueryError(
                f"无可用数据{f' ({query_type})' if query_type else ''}",
                AmazingDataErrorCode.NO_DATA_AVAILABLE,
                details={'query_type': query_type},
                original_exception=error
            )
        elif "invalid symbol" in error_msg:
            return AmazingDataQueryError(
                "无效的股票代码",
                AmazingDataErrorCode.INVALID_SYMBOL,
                original_exception=error
            )
        elif "invalid period" in error_msg:
            return AmazingDataQueryError(
                "无效的周期参数",
                AmazingDataErrorCode.INVALID_PERIOD,
                original_exception=error
            )
        elif "rate limit" in error_msg:
            return AmazingDataRateLimitError(
                "查询频率超限",
                retry_after=60,  # 默认60秒后重试
                original_exception=error
            )
        else:
            return AmazingDataQueryError(
                f"查询失败: {error}",
                AmazingDataErrorCode.QUERY_FAILED,
                details={'query_type': query_type},
                original_exception=error
            )

    @staticmethod
    def handle_subscription_error(error: Exception, symbols: list = None) -> AmazingDataException:
        """处理订阅错误"""
        error_msg = str(error).lower()

        if "limit" in error_msg or "exceed" in error_msg:
            return AmazingDataSubscriptionError(
                f"订阅数量超限（尝试订阅 {len(symbols) if symbols else 0} 个）",
                AmazingDataErrorCode.SUBSCRIPTION_LIMIT_EXCEEDED,
                details={'symbols': symbols},
                original_exception=error
            )
        elif "not found" in error_msg:
            return AmazingDataSubscriptionError(
                "订阅不存在",
                AmazingDataErrorCode.SUBSCRIPTION_NOT_FOUND,
                original_exception=error
            )
        elif "invalid" in error_msg:
            return AmazingDataSubscriptionError(
                "无效的订阅类型",
                AmazingDataErrorCode.INVALID_SUBSCRIPTION_TYPE,
                original_exception=error
            )
        else:
            return AmazingDataSubscriptionError(
                f"订阅失败: {error}",
                AmazingDataErrorCode.SUBSCRIPTION_FAILED,
                details={'symbols': symbols},
                original_exception=error
            )

    @staticmethod
    def is_retryable(exception: AmazingDataException) -> bool:
        """判断错误是否可重试"""
        retryable_codes = [
            AmazingDataErrorCode.NETWORK_TIMEOUT,
            AmazingDataErrorCode.CONNECTION_LOST,
            AmazingDataErrorCode.HEARTBEAT_FAILED,
            AmazingDataErrorCode.RATE_LIMIT_EXCEEDED,
        ]
        return exception.error_code in retryable_codes

    @staticmethod
    def get_retry_delay(exception: AmazingDataException) -> int:
        """获取重试延迟时间（秒）"""
        if exception.error_code == AmazingDataErrorCode.RATE_LIMIT_EXCEEDED:
            return exception.details.get('retry_after', 60)
        elif exception.error_code == AmazingDataErrorCode.NETWORK_TIMEOUT:
            return 5
        else:
            return 10  # 默认延迟
