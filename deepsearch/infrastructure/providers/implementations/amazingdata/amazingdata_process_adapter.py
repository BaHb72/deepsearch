"""AmazingData 子进程适配器，实现 ports/AmazingDataProcessPort 协议。"""

from __future__ import annotations

import asyncio
from types import MappingProxyType
from typing import Mapping, TypeVar, cast

from deepsearch.ports.amazingdata_process import (
    AmazingDataLoginRequest,
    AmazingDataLogoutRequest,
    AmazingDataProcessPort,
    ProcessCallResult,
    ProcessCommand,
    ProcessCommandType,
)

from .amazingdata_process_proxy import (
    AmazingDataProcessProxy,
    ProxyResponse,
    RequestType,
)

TExec = TypeVar("TExec")

_REQUEST_TYPE_MAPPING: dict[ProcessCommandType, RequestType] = {
    ProcessCommandType.LOGIN: RequestType.LOGIN,
    ProcessCommandType.LOGOUT: RequestType.LOGOUT,
    ProcessCommandType.DATA: RequestType.GET_DATA,
    ProcessCommandType.SUBSCRIBE: RequestType.SUBSCRIBE,
    ProcessCommandType.UNSUBSCRIBE: RequestType.UNSUBSCRIBE,
    ProcessCommandType.HEALTH: RequestType.HEALTH_CHECK,
    ProcessCommandType.SHUTDOWN: RequestType.SHUTDOWN,
}


class AmazingDataProcessAdapter(AmazingDataProcessPort):
    """封装 AmazingDataProcessProxy，提供异步化接口。"""

    def __init__(self, proxy: AmazingDataProcessProxy) -> None:
        self._proxy = proxy

    async def ensure_started(self) -> bool:
        if self._proxy.is_running and self._proxy.is_worker_alive():
            return True
        return await self._proxy.start_async()

    async def execute(self, command: ProcessCommand[TExec]) -> ProcessCallResult[TExec]:
        request_type = _REQUEST_TYPE_MAPPING.get(command.command_type, RequestType.GET_DATA)

        def _call() -> ProxyResponse:
            return self._proxy.execute(
                command.method,
                *tuple(command.args),
                request_type=request_type,
                timeout=command.timeout,
                **dict(command.kwargs),
            )

        response = await asyncio.to_thread(_call)
        metadata: Mapping[str, object] | None = None
        if response.timestamp:
            metadata = MappingProxyType({"timestamp": response.timestamp})

        result: TExec | None = None
        if response.success:
            result = cast(TExec | None, response.result)

        return ProcessCallResult(
            success=response.success,
            result=result,
            error=response.error,
            error_type=response.error_type,
            metadata=metadata,
        )

    async def login(self, request: AmazingDataLoginRequest) -> ProcessCallResult[int]:
        if request.api_mode:
            command = ProcessCommand[int](
                method="login",
                args=(request.username, request.password, request.host, request.port),
                kwargs={"api_mode": request.api_mode},
                timeout=request.timeout,
                command_type=ProcessCommandType.LOGIN,
            )
        else:
            command = ProcessCommand[int](
                method="login",
                args=(request.username, request.password, request.host, request.port),
                timeout=request.timeout,
                command_type=ProcessCommandType.LOGIN,
            )
        return await self.execute(command)

    async def logout(
        self, request: AmazingDataLogoutRequest | None = None
    ) -> ProcessCallResult[bool | None]:
        username = request.username if request and request.username else None
        timeout = request.timeout if request else 5.0
        args: tuple[object, ...] = (username,) if username else ()

        command = ProcessCommand[bool | None](
            method="logout",
            args=args,
            timeout=timeout,
            command_type=ProcessCommandType.LOGOUT,
        )
        return await self.execute(command)

    async def health_check(self) -> bool:
        command = ProcessCommand[Mapping[str, object]](
            method="health_check",
            timeout=5.0,
            command_type=ProcessCommandType.HEALTH,
        )
        result = await self.execute(command)
        return result.success

    async def stop(self, *, force: bool = False, with_logout: bool = True) -> None:
        await asyncio.to_thread(
            self._proxy.stop,
            timeout=5.0,
            force=force,
            with_logout=with_logout,
        )

    def get_stats(self) -> Mapping[str, object]:
        return self._proxy.get_stats()
