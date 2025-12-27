"""AmazingData 子进程适配器，实现 ports/AmazingDataProcessPort 协议。"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from types import MappingProxyType
from typing import Callable, Mapping, TypeVar, cast

import pandas as pd

from deepsearch.ports.amazingdata_process import (
    AmazingDataLoginRequest,
    AmazingDataLogoutRequest,
    AmazingDataProcessPort,
    ProcessCallResult,
    ProcessCommand,
    ProcessCommandType,
)

from .amazingdata_process_proxy import AmazingDataProcessProxy, ProxyResponse, RequestType

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
        self._payload_validators: dict[str, Callable[[object], bool]] = {
            "BaseData.get_code_info": self._is_code_info_payload,
            "BaseData.get_code_list": self._is_iterable_payload,
            "BaseData.get_hist_code_list": self._is_iterable_payload,
        }

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
                alt_methods=tuple(command.alt_methods),
                alt_args=tuple(command.alt_args),
                kwargs_patches=tuple(dict(patch) for patch in command.kwargs_patches),
                **dict(command.kwargs),
            )

        response = await asyncio.to_thread(_call)
        metadata: Mapping[str, object] | None = None
        if response.timestamp:
            metadata = MappingProxyType({"timestamp": response.timestamp})

        result: TExec | None = None
        if response.success:
            result_obj = cast(TExec | None, response.result)
            if result_obj is None:
                return ProcessCallResult(
                    success=False,
                    result=None,
                    error=f"{command.method}: SDK returned None",
                    error_type="SDKEmptyResponse",
                    metadata=metadata,
                )
            validator = self._payload_validators.get(command.method)
            if validator and not validator(result_obj):
                return ProcessCallResult(
                    success=False,
                    result=None,
                    error=f"{command.method}: unexpected payload type={type(result_obj)}",
                    error_type="SDKUnexpectedPayload",
                    metadata=metadata,
                )
            result = result_obj

        return ProcessCallResult(
            success=response.success,
            result=result,
            error=response.error,
            error_type=response.error_type,
            metadata=metadata,
        )

    @staticmethod
    def _is_code_info_payload(payload: object) -> bool:
        if isinstance(payload, MappingABC):
            return True
        if isinstance(payload, pd.DataFrame):
            return True
        return False

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

    @staticmethod
    def _is_iterable_payload(payload: object) -> bool:
        if isinstance(payload, MappingABC):
            return True
        if isinstance(payload, SequenceABC) and not isinstance(payload, (str, bytes, bytearray)):
            return True
        return False
