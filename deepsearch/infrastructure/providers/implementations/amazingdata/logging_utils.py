"""Logging helpers for AmazingData provider implementations."""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, Sequence

from .common import datasource_logger


@dataclass(frozen=True)
class LogContext:
    action: str
    symbol: str | None = None
    metadata: Mapping[str, Any] | None = None

    def render_suffix(self) -> str:
        parts: list[str] = [f"action={self.action}"]
        if self.symbol:
            parts.append(f"symbol={self.symbol}")
        if self.metadata:
            for key, value in sorted(self.metadata.items()):
                parts.append(f"{key}={value}")
        parts.append(f"timestamp={datetime.now().isoformat()}")
        return " | " + ", ".join(parts)


def _log(
    level: str,
    message: str,
    *,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    suffix = LogContext(action=action, symbol=symbol, metadata=metadata).render_suffix()
    getattr(datasource_logger, level)(f"{message}{suffix}")


def _format_message(message: str, args: Sequence[object]) -> str:
    if not args:
        return message
    try:
        return message % tuple(args)
    except Exception:
        # fall back to simple join to avoid raising
        joined = " ".join(str(arg) for arg in args)
        return f"{message} {joined}".strip()


def log_debug(
    message: str,
    *args: object,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    formatted = _format_message(message, args)
    _log("debug", formatted, action=action, symbol=symbol, metadata=metadata)


def log_info(
    message: str,
    *args: object,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    formatted = _format_message(message, args)
    _log("info", formatted, action=action, symbol=symbol, metadata=metadata)


def log_warning(
    message: str,
    *args: object,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    formatted = _format_message(message, args)
    _log("warning", formatted, action=action, symbol=symbol, metadata=metadata)


def log_error(
    message: str,
    *args: object,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    formatted = _format_message(message, args)
    _log("error", formatted, action=action, symbol=symbol, metadata=metadata)


def log_critical(
    message: str,
    *args: object,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    formatted = _format_message(message, args)
    _log("critical", formatted, action=action, symbol=symbol, metadata=metadata)


def log_exception(
    message: str,
    *,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    suffix = LogContext(action=action, symbol=symbol, metadata=metadata).render_suffix()
    datasource_logger.exception(f"{message}{suffix}")


def log_iterable(
    level: str,
    items: Iterable[str],
    *,
    action: str = "general",
    symbol: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    _log(level, ", ".join(items), action=action, symbol=symbol, metadata=metadata)


def log_exceptions(action: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    log_exception(str(exc), action=action, metadata={"fn": func.__name__})
                    raise

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                log_exception(str(exc), action=action, metadata={"fn": func.__name__})
                raise

        return sync_wrapper

    return decorator


class ProcessLoggerAdapter:
    def __init__(self, action: str = "process") -> None:
        self.action = action

    @staticmethod
    def _fmt(message: str, args: tuple[Any, ...]) -> str:
        if not args:
            return message
        try:
            return message.format(*args)
        except Exception:
            return " ".join([message, *(str(arg) for arg in args)])

    def _emit(
        self,
        emitter: Callable[..., None],
        message: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        action = kwargs.pop("action", self.action)
        metadata = kwargs.pop("metadata", None)
        if kwargs:
            merged = dict(metadata or {})
            merged.update(kwargs)
            metadata = merged
        emitter(self._fmt(message, args), action=action, metadata=metadata)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(log_debug, message, args, kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(log_info, message, args, kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(log_warning, message, args, kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(log_error, message, args, kwargs)

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._emit(log_critical, message, args, kwargs)


__all__ = [
    "LogContext",
    "log_debug",
    "log_info",
    "log_warning",
    "log_error",
    "log_critical",
    "log_exception",
    "log_iterable",
    "log_exceptions",
    "ProcessLoggerAdapter",
]
