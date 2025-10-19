"""AmazingData 子进程通信协议定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Generic, Mapping, Protocol, Sequence, TypeVar

TResult = TypeVar("TResult")
TResult_co = TypeVar("TResult_co", covariant=True)


class ProcessCommandType(str, Enum):
    """IPC 指令类型枚举。"""

    LOGIN = "login"
    LOGOUT = "logout"
    DATA = "data"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    HEALTH = "health"
    SHUTDOWN = "shutdown"


@dataclass(slots=True, frozen=True)
class ProcessCommand(Generic[TResult]):
    """描述一次 IPC 调用的参数与上下文。"""

    method: str
    args: Sequence[object] = field(default_factory=tuple)
    kwargs: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    timeout: float = 30.0
    command_type: ProcessCommandType = ProcessCommandType.DATA


@dataclass(slots=True)
class ProcessCallResult(Generic[TResult_co]):
    """子进程执行结果。"""

    success: bool
    result: TResult_co | None = None
    error: str | None = None
    error_type: str | None = None
    metadata: Mapping[str, object] | None = None

    def unwrap(self) -> TResult_co:
        """在确保成功时返回结果，否则抛出运行时异常。"""

        if not self.success or self.result is None:
            raise RuntimeError(self.error or "Process call failed")
        return self.result


@dataclass(slots=True, frozen=True)
class AmazingDataLoginRequest:
    """登录请求参数。"""

    username: str
    password: str
    host: str
    port: int
    timeout: float = 10.0
    api_mode: str | None = None


@dataclass(slots=True, frozen=True)
class AmazingDataLogoutRequest:
    """注销请求参数。"""

    username: str | None = None
    timeout: float = 5.0


class AmazingDataProcessPort(Protocol):
    """AmazingData 子进程通信 Port 协议。"""

    async def ensure_started(self) -> bool:
        """确保子进程已经启动。"""
        ...

    async def execute(self, command: ProcessCommand[TResult]) -> ProcessCallResult[TResult]:
        """执行任意 IPC 调用。"""
        ...

    async def login(self, request: AmazingDataLoginRequest) -> ProcessCallResult[int]:
        """执行登录流程。"""
        ...

    async def logout(
        self, request: AmazingDataLogoutRequest | None = None
    ) -> ProcessCallResult[bool | None]:
        """执行注销流程。"""
        ...

    async def health_check(self) -> bool:
        """探测子进程健康状态。"""
        ...

    async def stop(self, *, force: bool = False, with_logout: bool = True) -> None:
        """关闭子进程。"""
        ...

    def get_stats(self) -> Mapping[str, object]:
        """获取即时统计信息。"""
        ...


__all__ = [
    "AmazingDataLoginRequest",
    "AmazingDataLogoutRequest",
    "AmazingDataProcessPort",
    "ProcessCallResult",
    "ProcessCommand",
    "ProcessCommandType",
]
