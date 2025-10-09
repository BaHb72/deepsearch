"""Standard logging templates and utilities"""

import time
from traceback import format_exception
from typing import Any, Optional


class LogTemplates:
    """Standard log message templates"""

    SYSTEM_START = "System starting: {mode} mode, version: {version}"
    SYSTEM_READY = "System ready in {elapsed:.2f}s"
    SYSTEM_SHUTDOWN = "System shutting down"

    COMPONENT_INITIALIZED = "Component {component} initialized"
    COMPONENT_STARTED = "Component {component} started"
    COMPONENT_STOPPED = "Component {component} stopped"
    COMPONENT_ERROR = "Component {component} error: {error}"

    CONNECTION_ESTABLISHED = "Connection established to {target}"
    CONNECTION_FAILED = "Connection failed to {target}: {error}"
    CONNECTION_CLOSED = "Connection closed to {target}"

    REQUEST_STARTED = "Request started: {method} {url}"
    REQUEST_COMPLETED = "Request completed: {method} {url} - {status}"
    REQUEST_FAILED = "Request failed: {method} {url} - {error}"

    DATA_RECEIVED = "Data received: {count} items from {source}"
    DATA_SENT = "Data sent: {count} items to {target}"
    DATA_ERROR = "Data error: {error}"


class LogStandard:
    """Standard logging utilities"""

    @staticmethod
    def component_lifecycle(component_name: str, state: str, **kwargs: Any) -> str:
        """Log component lifecycle events"""
        return f"Component [{component_name}] {state}"

    @staticmethod
    def connection_event(target: str, event: str, **kwargs: Any) -> str:
        """Log connection events"""
        return f"Connection [{target}] {event}"

    @staticmethod
    def request_event(method: str, url: str, event: str, **kwargs: Any) -> str:
        """Log request events"""
        return f"Request [{method} {url}] {event}"

    @staticmethod
    def data_event(source: str, event: str, **kwargs: Any) -> str:
        """Log data events"""
        return f"Data [{source}] {event}"

    @staticmethod
    def format_duration(start_time: float, end_time: Optional[float] = None) -> str:
        """Format duration in human-readable format"""
        if end_time is None:
            end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        if duration_ms < 1000:
            return f"{duration_ms:.1f}ms"
        else:
            return f"{duration_ms/1000:.2f}s"

    @staticmethod
    def format_error(error: Exception | str, include_traceback: bool = True) -> str:
        """格式化异常信息，可选附带堆栈"""
        if isinstance(error, str):
            return error
        if include_traceback and getattr(error, "__traceback__", None) is not None:
            return "".join(format_exception(type(error), error, error.__traceback__))
        return str(error)
