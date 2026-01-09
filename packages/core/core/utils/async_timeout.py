from __future__ import annotations

import asyncio
import functools
import inspect
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Optional,
    ParamSpec,
    TypeAlias,
    TypeVar,
    cast,
    overload,
)

from loguru import logger

from .timeout_config import TimeoutCategory, get_timeout_manager

P = ParamSpec("P")
T = TypeVar("T")

TimeoutSpec: TypeAlias = float | int | TimeoutCategory

CallableWithOptionalAwait = Callable[P, Awaitable[T] | T]


@overload
def with_timeout(
    awaitable: Awaitable[T],
    timeout: TimeoutSpec,
    default: Optional[T] = None,
    *,
    operation_name: str | None = None,
) -> Coroutine[Any, Any, Optional[T]]: ...


# 新增：装饰器模式（不带default），保留原始返回类型T
@overload
def with_timeout(
    timeout: TimeoutSpec,
    *,
    operation_name: str | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Coroutine[Any, Any, T]]]: ...


@overload
def with_timeout(
    timeout: TimeoutSpec,
    default: Optional[T] = None,
    *,
    operation_name: str | None = None,
) -> Callable[[CallableWithOptionalAwait], Callable[P, Coroutine[Any, Any, Optional[T]]]]: ...


@overload
def with_timeout(
    func: CallableWithOptionalAwait,
    timeout: TimeoutSpec,
    default: Optional[T] = None,
    *,
    operation_name: str | None = None,
) -> Callable[P, Coroutine[Any, Any, Optional[T]]]: ...


def with_timeout(*args: Any, **kwargs: Any) -> Any:
    """Support three forms: awaitable, decorator factory, and direct decorator usage."""

    timeout_kw = kwargs.pop("timeout", None)
    default = kwargs.pop("default", None)
    operation_name = kwargs.pop("operation_name", None)

    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
        raise TypeError(f"with_timeout got unexpected keyword arguments: {unexpected}")

    first_arg = args[0] if args else None

    if inspect.isawaitable(first_arg):
        timeout_spec = (
            timeout_kw if timeout_kw is not None else (args[1] if len(args) >= 2 else None)
        )
        if timeout_spec is None:
            raise TypeError("with_timeout expects a timeout when used with awaitables")
        seconds = _resolve_timeout_spec(cast(TimeoutSpec, timeout_spec))
        return _await_with_timeout(
            cast(Awaitable[Any], first_arg), seconds, cast(Optional[Any], default), operation_name
        )

    if callable(first_arg):
        timeout_spec = (
            timeout_kw if timeout_kw is not None else (args[1] if len(args) >= 2 else None)
        )
        if timeout_spec is not None:
            seconds = _resolve_timeout_spec(cast(TimeoutSpec, timeout_spec))
            return _wrap_callable(
                cast(CallableWithOptionalAwait, first_arg),
                seconds,
                cast(Optional[Any], default),
                operation_name,
            )

    timeout_spec = timeout_kw if timeout_kw is not None else first_arg
    if timeout_spec is None:
        raise TypeError("with_timeout requires an awaitable, callable, or timeout spec")
    if len(args) > 1:
        raise TypeError("with_timeout decorator form accepts only a single timeout spec")

    seconds = _resolve_timeout_spec(cast(TimeoutSpec, timeout_spec))

    def decorator(
        func: CallableWithOptionalAwait,
    ) -> Callable[P, Coroutine[Any, Any, Optional[Any]]]:
        return _wrap_callable(func, seconds, cast(Optional[Any], default), operation_name)

    return decorator


async def run_with_timeout(
    target: Any,
    *args: Any,
    timeout: TimeoutSpec | None = None,
    default: Optional[T] = None,
    operation_name: str | None = None,
    **kwargs: Any,
) -> Optional[T]:
    """Run an awaitable or callable with a timeout and optional default fallback."""

    timeout_spec = timeout
    remaining_args = list(args)
    if timeout_spec is None:
        if remaining_args:
            timeout_spec = cast(TimeoutSpec, remaining_args.pop(0))
        else:
            raise TypeError("run_with_timeout is missing a timeout value")

    seconds = _resolve_timeout_spec(timeout_spec)
    op_name = operation_name

    if inspect.isawaitable(target):
        awaited = await _await_with_timeout(
            cast(Awaitable[Any], target), seconds, cast(Optional[Any], default), op_name
        )
        return cast(Optional[T], awaited)

    if callable(target):
        callable_target = cast(Callable[..., Any], target)
        if op_name is None:
            op_name = getattr(callable_target, "__name__", None)

        if inspect.iscoroutinefunction(callable_target):
            coroutine = cast(Awaitable[Any], callable_target(*remaining_args, **kwargs))
            awaited = await _await_with_timeout(
                coroutine, seconds, cast(Optional[Any], default), op_name
            )
            return cast(Optional[T], awaited)

        loop = asyncio.get_running_loop()
        bound_call = functools.partial(callable_target, *remaining_args, **kwargs)
        try:
            outcome = await asyncio.wait_for(
                loop.run_in_executor(None, bound_call), timeout=seconds
            )
        except asyncio.TimeoutError:
            _log_timeout(op_name, seconds)
            return default

        if inspect.isawaitable(outcome):
            awaited = await _await_with_timeout(
                cast(Awaitable[Any], outcome), seconds, cast(Optional[Any], default), op_name
            )
            return cast(Optional[T], awaited)

        return cast(Optional[T], outcome)

    raise TypeError("run_with_timeout requires an awaitable or callable target")


def timeout_decorator(
    seconds: float, default: Any = None
) -> Callable[[CallableWithOptionalAwait], Callable[P, Coroutine[Any, Any, Optional[Any]]]]:
    """Provide decorator-style usage for synchronous or asynchronous callables."""

    def decorator(
        func: CallableWithOptionalAwait,
    ) -> Callable[P, Coroutine[Any, Any, Optional[Any]]]:
        return _wrap_callable(func, seconds, default, getattr(func, "__name__", None))

    return decorator


@asynccontextmanager
async def timeout_context(seconds: float) -> AsyncIterator[None]:
    """Context manager that cancels the current task when the timeout elapses."""

    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("timeout_context requires an active asyncio task")

    def timeout_callback() -> None:
        task.cancel()

    handle = asyncio.get_event_loop().call_later(seconds, timeout_callback)

    try:
        yield
    finally:
        handle.cancel()


class TimeoutError(Exception):
    """Explicit timeout exception for callers that need a typed error."""

    def __init__(self, message: str = "Operation timed out") -> None:
        super().__init__(message)
        self.message = message


async def wait_for(coro: Coroutine[Any, Any, T], timeout: float) -> T:
    """Thin wrapper around asyncio.wait_for used in legacy call sites."""

    return await asyncio.wait_for(coro, timeout=timeout)


timeout = timeout_context


def _resolve_timeout_spec(spec: TimeoutSpec) -> float:
    """Convert TimeoutSpec variants into a float number of seconds."""

    if isinstance(spec, TimeoutCategory):
        manager = get_timeout_manager()
        return manager.get_timeout(spec)

    if isinstance(spec, (int, float)):
        if spec <= 0:
            raise ValueError("timeout seconds must be positive")
        return float(spec)

    raise TypeError(f"Unsupported timeout spec: {spec!r}")


async def _await_with_timeout(
    awaitable: Awaitable[Any],
    seconds: float,
    default: Optional[Any],
    operation_name: str | None,
) -> Optional[Any]:
    """Await a coroutine with timeout handling and optional default fallback."""

    try:
        return await asyncio.wait_for(awaitable, timeout=seconds)
    except asyncio.TimeoutError:
        _log_timeout(operation_name, seconds)
        return default


def _wrap_callable(
    func: CallableWithOptionalAwait,
    seconds: float,
    default: Optional[Any],
    operation_name: str | None,
) -> Callable[P, Coroutine[Any, Any, Optional[Any]]]:
    """Wrap a callable so the returned coroutine applies timeout enforcement."""

    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[Any]:
        op_name = operation_name or getattr(func, "__name__", None)

        if inspect.iscoroutinefunction(func):
            coroutine = cast(Awaitable[Any], func(*args, **kwargs))
            result = await _await_with_timeout(coroutine, seconds, default, op_name)
            return result

        loop = asyncio.get_running_loop()
        bound_call = functools.partial(cast(Callable[..., Any], func), *args, **kwargs)
        try:
            outcome = await asyncio.wait_for(
                loop.run_in_executor(None, bound_call), timeout=seconds
            )
        except asyncio.TimeoutError:
            _log_timeout(op_name, seconds)
            return default

        if inspect.isawaitable(outcome):
            return await _await_with_timeout(
                cast(Awaitable[Any], outcome), seconds, default, op_name
            )

        return cast(Optional[Any], outcome)

    return wrapper


def _log_timeout(operation_name: str | None, seconds: float) -> None:
    """Log timeout warnings with a consistent format."""

    if operation_name:
        logger.warning(f"Operation '{operation_name}' timed out after {seconds:.2f}s")
    else:
        logger.warning(f"Operation timed out after {seconds:.2f}s")
