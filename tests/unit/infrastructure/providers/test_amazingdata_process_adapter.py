from typing import Any

import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_adapter import (
    AmazingDataProcessAdapter,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
    ProxyResponse,
)
from deepsearch.ports.amazingdata_process import ProcessCommand, ProcessCommandType


class _StubProxy:
    def __init__(self, response: ProxyResponse) -> None:
        self._response = response
        self.is_running = True

    def is_worker_alive(self) -> bool:
        return True

    async def start_async(self) -> bool:
        self.is_running = True
        return True

    def execute(self, method: str, *args, **kwargs) -> ProxyResponse:
        return self._response

    def get_stats(self):
        return {}


@pytest.mark.asyncio
async def test_adapter_none_payload_returns_error():
    response = ProxyResponse(request_id="1", success=True, result=None)
    adapter = AmazingDataProcessAdapter(_StubProxy(response))

    command = ProcessCommand[Any](
        method="BaseData.get_code_list",
        command_type=ProcessCommandType.DATA,
    )

    result = await adapter.execute(command)

    assert result.success is False
    assert result.error == "BaseData.get_code_list: SDK returned None"
    assert result.error_type == "SDKEmptyResponse"


@pytest.mark.asyncio
async def test_adapter_unexpected_payload_type_returns_error():
    response = ProxyResponse(request_id="2", success=True, result="invalid-payload")
    adapter = AmazingDataProcessAdapter(_StubProxy(response))

    command = ProcessCommand[Any](
        method="BaseData.get_code_list",
        command_type=ProcessCommandType.DATA,
    )

    result = await adapter.execute(command)

    assert result.success is False
    assert result.error_type == "SDKUnexpectedPayload"
    assert "unexpected payload type" in (result.error or "")
