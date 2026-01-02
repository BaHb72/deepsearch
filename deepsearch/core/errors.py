"""
核心错误类定义

定义系统中所有基础错误类型
"""

from typing import Any, Dict, Optional


class BaseError(Exception):
    """
    基础错误类
    所有自定义错误都继承自此类
    """

    def __init__(
        self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None
    ):
        """
        初始化错误

        Args:
            message: 错误消息
            code: 错误代码
            details: 详细信息
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class ConfigurationError(BaseError):
    """配置错误"""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(message, code="CONFIG_ERROR", **kwargs)
        if config_key:
            self.details["config_key"] = config_key


class DatabaseConnectionError(BaseError):
    """数据库连接错误"""

    def __init__(self, message: str, database: Optional[str] = None, **kwargs):
        super().__init__(message, code="DB_CONNECTION_ERROR", **kwargs)
        if database:
            self.details["database"] = database


class DataProviderError(BaseError):
    """数据提供者错误"""

    def __init__(self, message: str, provider: Optional[str] = None, **kwargs):
        super().__init__(message, code="DATA_PROVIDER_ERROR", **kwargs)
        if provider:
            self.details["provider"] = provider


class NetworkError(BaseError):
    """网络错误"""

    def __init__(
        self, message: str, url: Optional[str] = None, status_code: Optional[int] = None, **kwargs
    ):
        super().__init__(message, code="NETWORK_ERROR", **kwargs)
        if url:
            self.details["url"] = url
        if status_code:
            self.details["status_code"] = status_code


class ValidationError(BaseError):
    """验证错误"""

    def __init__(
        self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs
    ):
        super().__init__(message, code="VALIDATION_ERROR", **kwargs)
        if field:
            self.details["field"] = field
        if value is not None:
            self.details["value"] = value


class AuthenticationError(BaseError):
    """认证错误"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="AUTH_ERROR", **kwargs)


class AuthorizationError(BaseError):
    """授权错误"""

    def __init__(self, message: str, required_permission: Optional[str] = None, **kwargs):
        super().__init__(message, code="AUTHZ_ERROR", **kwargs)
        if required_permission:
            self.details["required_permission"] = required_permission


class TimeoutError(BaseError):
    """超时错误"""

    def __init__(self, message: str, timeout_seconds: Optional[float] = None, **kwargs):
        super().__init__(message, code="TIMEOUT_ERROR", **kwargs)
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


class RateLimitError(BaseError):
    """限流错误"""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, code="RATE_LIMIT_ERROR", **kwargs)
        if retry_after:
            self.details["retry_after"] = retry_after


class BusinessLogicError(BaseError):
    """业务逻辑错误"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="BUSINESS_ERROR", **kwargs)


class ResourceNotFoundError(BaseError):
    """资源未找到错误"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, code="NOT_FOUND", **kwargs)
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id


class DuplicateResourceError(BaseError):
    """资源重复错误"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, code="DUPLICATE", **kwargs)
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id


class ServiceUnavailableError(BaseError):
    """服务不可用错误"""

    def __init__(self, message: str, service_name: Optional[str] = None, **kwargs):
        super().__init__(message, code="SERVICE_UNAVAILABLE", **kwargs)
        if service_name:
            self.details["service_name"] = service_name
