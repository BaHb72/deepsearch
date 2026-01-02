"""
DeepSearch 应用程序的自定义异常。

本模块定义了一套异常层次结构，用于在整个应用程序中
提供更好的错误处理和调试支持。

增强功能：
1. 支持异常链和原因追踪
2. 自动捕获异常上下文
3. 提供结构化的错误信息
4. 支持错误处理上下文管理器
"""

import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional


class DeepSearchError(Exception):
    """
    所有 DeepSearch 错误的基类。

    所有自定义异常都应该继承自这个类，这样可以通过
    单个 except 语句捕获所有 DeepSearch 特定的错误。

    增强功能：
    - 支持异常链（cause）
    - 自动记录时间戳
    - 结构化的上下文信息
    - 堆栈跟踪捕获
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        """
        初始化 DeepSearch 错误。

        参数：
            message: 错误消息
            error_code: 可选的错误码，用于程序化处理
            details: 可选的字典，包含额外的错误详情
            cause: 导致此错误的原始异常
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now()
        self.traceback_str = (
            traceback.format_exc() if traceback.format_exc() != "NoneType: None\n" else None
        )

        # 如果有原因异常，添加到详情中
        if cause:
            self.details["cause"] = {"type": type(cause).__name__, "message": str(cause)}

    def __str__(self) -> str:
        """错误的字符串表示。"""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """将错误转换为字典以便序列化。"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback_str,
        }

    def with_context(self, **kwargs) -> "DeepSearchError":
        """添加额外的上下文信息"""
        self.details.update(kwargs)
        return self


# ==============================================================================
# 配置错误
# ==============================================================================


class ConfigurationError(DeepSearchError):
    """配置存在问题时引发。"""

    pass


class InvalidConfigError(ConfigurationError):
    """配置值无效时引发。"""

    pass


class MissingConfigError(ConfigurationError):
    """缺少必需的配置时引发。"""

    pass


# ==============================================================================
# 验证错误
# ==============================================================================


class ValidationError(DeepSearchError):
    """数据验证失败时引发。"""

    pass


class SchemaValidationError(ValidationError):
    """事件数据不符合模式时引发。"""

    pass


class FieldValidationError(ValidationError):
    """特定字段验证失败时引发。"""

    def __init__(self, field: str, value: Any, reason: str, **kwargs):
        super().__init__(
            f"字段 '{field}' 验证失败：{reason}",
            details={"field": field, "value": value, "reason": reason},
            **kwargs,
        )


# ==============================================================================
# 连接错误
# ==============================================================================


class ConnectionError(DeepSearchError):
    """连接到外部服务失败时引发。"""

    pass


class NetworkError(ConnectionError):
    """网络通信失败时引发。"""

    pass


class TimeoutError(ConnectionError):
    """操作超时时引发。"""

    pass


class AuthenticationError(ConnectionError):
    """认证失败时引发。"""

    pass


# ==============================================================================
# 事件系统错误
# ==============================================================================


class EventError(DeepSearchError):
    """事件系统错误的基类。"""

    pass


class EventQueueFullError(EventError):
    """事件队列已满时引发。"""

    pass


class EventHandlerError(EventError):
    """事件处理器失败时引发。"""

    def __init__(self, handler_name: str, event_type: str, original_error: Exception, **kwargs):
        super().__init__(
            f"处理器 '{handler_name}' 处理事件 '{event_type}' 失败：{original_error}",
            details={
                "handler": handler_name,
                "event_type": event_type,
                "original_error": str(original_error),
            },
            **kwargs,
        )


class EventValidationError(EventError):
    """事件验证失败时引发。"""

    pass


# ==============================================================================
# 存储错误
# ==============================================================================


class StorageError(DeepSearchError):
    """存储相关错误的基类。"""

    pass


class StorageConnectionError(StorageError):
    """连接到存储失败时引发。"""

    pass


class StorageReadError(StorageError):
    """从存储读取失败时引发。"""

    pass


class StorageWriteError(StorageError):
    """写入存储失败时引发。"""

    pass


class StorageNotFoundError(StorageError):
    """在存储中找不到请求的数据时引发。"""

    pass


# ==============================================================================
# 网关错误
# ==============================================================================


class GatewayError(DeepSearchError):
    """网关相关错误的基类。"""

    pass


class GatewayConnectionError(GatewayError):
    """网关连接失败时引发。"""

    pass


class GatewayAuthError(GatewayError):
    """网关认证失败时引发。"""

    pass


class GatewayOrderError(GatewayError):
    """订单提交失败时引发。"""

    def __init__(self, order_id: str, reason: str, **kwargs):
        super().__init__(
            f"订单 '{order_id}' 失败：{reason}",
            details={"order_id": order_id, "reason": reason},
            **kwargs,
        )


class GatewayDataError(GatewayError):
    """市场数据接收失败时引发。"""

    pass


# ==============================================================================
# 交易错误
# ==============================================================================


class TradingError(DeepSearchError):
    """交易相关错误的基类。"""

    pass


class InsufficientBalanceError(TradingError):
    """账户余额不足时引发。"""

    def __init__(self, required: float, available: float, currency: str, **kwargs):
        super().__init__(
            f"{currency} 余额不足：需要 {required}，可用 {available}",
            details={"required": required, "available": available, "currency": currency},
            **kwargs,
        )


class PositionLimitError(TradingError):
    """超出持仓限制时引发。"""

    pass


class RiskLimitError(TradingError):
    """超出风险限制时引发。"""

    pass


class InvalidOrderError(TradingError):
    """订单参数无效时引发。"""

    pass


# ==============================================================================
# 系统错误
# ==============================================================================


class SystemError(DeepSearchError):
    """系统级错误的基类。"""

    pass


class StartupError(SystemError):
    """系统启动失败时引发。"""

    pass


class ShutdownError(SystemError):
    """系统关闭失败时引发。"""

    pass


class ResourceError(SystemError):
    """系统资源不可用时引发。"""

    pass


# ==============================================================================
# 组件相关错误
# ==============================================================================


class ComponentError(DeepSearchError):
    """组件相关的基础异常"""

    def __init__(
        self,
        component_name: str,
        message: str,
        error_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        details["component"] = component_name
        super().__init__(message, error_code, details, cause)
        self.component_name = component_name


class ComponentLifecycleError(ComponentError):
    """组件生命周期管理异常"""

    def __init__(
        self,
        component_name: str,
        lifecycle_phase: str,
        message: str,
        cause: Optional[Exception] = None,
    ):
        details = {"lifecycle_phase": lifecycle_phase}
        super().__init__(
            component_name,
            f"Component {component_name} lifecycle error in {lifecycle_phase}: {message}",
            details=details,
            cause=cause,
        )
        self.lifecycle_phase = lifecycle_phase


class ComponentNotFoundError(ComponentError):
    """组件未找到异常"""

    pass


class ComponentAlreadyExistsError(ComponentError):
    """组件已存在异常"""

    pass


class ComponentDependencyError(ComponentError):
    """组件依赖异常"""

    def __init__(
        self,
        component_name: str,
        dependency_name: str,
        message: str,
        cause: Optional[Exception] = None,
    ):
        details = {"dependency": dependency_name}
        super().__init__(
            component_name,
            f"Component {component_name} dependency error with {dependency_name}: {message}",
            details=details,
            cause=cause,
        )
        self.dependency_name = dependency_name


# ==============================================================================
# 数据库相关错误
# ==============================================================================


class DatabaseError(DeepSearchError):
    """数据库相关异常基类"""

    pass


class DatabaseConnectionError(DatabaseError):
    """数据库连接异常"""

    def __init__(self, database_url: str, message: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Database connection error: {message}",
            details={"database_url": database_url},
            cause=cause,
        )


class DatabaseQueryError(DatabaseError):
    """数据库查询异常"""

    def __init__(self, query: str, message: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Database query error: {message}",
            details={"query": query[:200]},  # 限制查询长度
            cause=cause,
        )


# ==============================================================================
# 工具函数
# ==============================================================================


class ErrorHandler:
    """统一的错误处理器"""

    @staticmethod
    def handle_error(
        error: Exception, component_name: Optional[str] = None, operation: Optional[str] = None
    ) -> DeepSearchError:
        """
        将任意异常转换为DeepSearch异常

        Args:
            error: 原始异常
            component_name: 组件名称
            operation: 正在执行的操作

        Returns:
            DeepSearchError: 转换后的异常
        """
        # 如果已经是DeepSearchError，添加上下文后返回
        if isinstance(error, DeepSearchError):
            if component_name and "component" not in error.details:
                error.details["component"] = component_name
            if operation and "operation" not in error.details:
                error.details["operation"] = operation
            return error

        # 转换为合适的DeepSearchError子类
        details = {}
        if component_name:
            details["component"] = component_name
        if operation:
            details["operation"] = operation

        # 根据异常类型选择合适的包装类
        error_message = str(error)

        if "connection" in error_message.lower():
            if "database" in error_message.lower():
                return DatabaseConnectionError("unknown", error_message, cause=error)
            else:
                return ConnectionError(error_message, details=details, cause=error)

        if "timeout" in error_message.lower():
            return TimeoutError(error_message, details=details, cause=error)

        if component_name:
            return ComponentError(component_name, error_message, details=details, cause=error)

        # 默认包装
        return DeepSearchError(error_message, details=details, cause=error)


@contextmanager
def error_context(component_name: str, operation: str):
    """
    错误上下文管理器

    使用示例：
        with error_context('database', 'query_execution'):
            # 执行可能出错的代码
            pass
    """
    try:
        yield
    except Exception as e:
        # 转换并重新抛出异常
        wrapped_error = ErrorHandler.handle_error(e, component_name, operation)
        raise wrapped_error from e


def reraise_with_context(original_error: Exception, context: str, **details) -> None:
    """
    重新引发异常并附加额外的上下文信息。

    参数：
        original_error: 原始异常
        context: 额外的上下文消息
        **details: 要包含的额外详情
    """
    error_class = type(original_error)

    # 如果已经是 DeepSearchError，保留其详情
    if isinstance(original_error, DeepSearchError):
        original_error.message = f"{context}：{original_error.message}"
        original_error.details.update(details)
        raise original_error

    # 否则，将其包装在 DeepSearchError 中
    raise DeepSearchError(
        f"{context}：{original_error}",
        details={
            "original_error": str(original_error),
            "original_type": error_class.__name__,
            **details,
        },
        cause=original_error,
    ) from original_error
