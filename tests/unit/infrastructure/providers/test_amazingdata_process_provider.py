import os
from types import MethodType

import pytest

os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process import (  # noqa: E402
    DEFAULT_HIST_CODE_LIST_START,
    DEFAULT_LOCAL_DATA_PATH,
    ProcessIsolatedAmazingDataProvider,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (  # noqa: E402
    shutdown_pool,
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError  # noqa: E402
from deepsearch.ports.amazingdata_process import ProcessCallResult, ProcessCommand  # noqa: E402


@pytest.mark.asyncio
async def test_process_provider_basic_flow():
    config_payload = {
        "enabled": True,
        "implementation_mode": "process",
        "connection": {
            "username": "stub_user",
            "password": "stub_pass",
            "host": "stub.amazingdata.local",
            "port": 8600,
            "timeout": 5,
        },
        "worker_env": {"DEEPSEARCH_AMAZINGDATA_STUB": "tests.stubs.amazingdata_stub"},
    }

    provider = ProcessIsolatedAmazingDataProvider(config_payload)

    try:
        initialized = await provider.initialize()
        assert initialized is True

        stock_list = await provider.get_stock_list(limit=2)
        assert stock_list is not None
        assert len(stock_list) <= 2

        kline = await provider.get_kline_data(
            symbol="000001",
            period="1d",
            start_date="2025-01-01",
            end_date="2025-01-05",
            limit=1,
        )
        assert kline is not None
        assert len(kline) <= 1

        quote = await provider.get_realtime_quote("000001")
        assert quote is not None
        assert quote.get("code") == "000001"
    finally:
        await provider.close()
        shutdown_pool()


@pytest.mark.asyncio
async def test_process_provider_stock_list_hist_fallback():
    config_payload = {
        "enabled": True,
        "implementation_mode": "process",
        "connection": {
            "username": "stub_user",
            "password": "stub_pass",
            "host": "stub.amazingdata.local",
            "port": 8600,
            "timeout": 5,
        },
        "worker_env": {"DEEPSEARCH_AMAZINGDATA_STUB": "tests.stubs.amazingdata_stub"},
    }

    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    executed_methods: list[str] = []
    security_attempts: list[str] = []

    async def fake_execute(self, command):
        executed_methods.append(command.method)
        if command.method == "BaseData.get_code_list":
            security_attempts.append(str(command.kwargs.get("security_type")))
            raise DataProviderError("BaseData.get_code_list: 'NoneType' object is not subscriptable")
        if command.method == "BaseData.get_hist_code_list":
            kwargs = dict(command.kwargs)
            assert kwargs["security_type"] == security_attempts[0]
            assert kwargs["start_date"] == DEFAULT_HIST_CODE_LIST_START
            assert isinstance(kwargs["end_date"], int)
            assert kwargs["end_date"] >= kwargs["start_date"]
            assert kwargs["local_path"] == DEFAULT_LOCAL_DATA_PATH
            assert kwargs["is_local"] is False
            return ["000001.SZ"]
        raise AssertionError(f"Unexpected method {command.method}")

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    try:
        stock_list = await provider.get_stock_list(security_type="extra__stock_a")
        assert stock_list is not None
        assert stock_list[0]["code"] == "000001.SZ"
    finally:
        await provider.close()
        shutdown_pool()

    assert security_attempts == ["EXTRA_STOCK_A", "EXTRA_STOCK_A_SH_SZ"]
    assert executed_methods[-1] == "BaseData.get_hist_code_list"


@pytest.mark.asyncio
async def test_process_provider_stock_list_hist_fallback_is_local_incompatible():
    config_payload = {
        "enabled": True,
        "implementation_mode": "process",
        "connection": {
            "username": "stub_user",
            "password": "stub_pass",
            "host": "stub.amazingdata.local",
            "port": 8600,
            "timeout": 5,
        },
        "worker_env": {"DEEPSEARCH_AMAZINGDATA_STUB": "tests.stubs.amazingdata_stub"},
    }

    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    call_history: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def fake_execute(self, command):
        snapshot = (command.method, tuple(command.args), dict(command.kwargs))
        call_history.append(snapshot)
        if command.method == "BaseData.get_code_list":
            raise DataProviderError("BaseData.get_code_list: 'NoneType' object is not subscriptable")
        if command.method == "BaseData.get_hist_code_list":
            if "is_local" in command.kwargs:
                raise DataProviderError(
                    "BaseData.get_hist_code_list: BaseData.get_hist_code_list() got an unexpected keyword argument 'is_local'"
                )
            return ["000002.SZ"]
        raise AssertionError(f"Unexpected method {command.method}")

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    try:
        stock_list = await provider.get_stock_list(security_type="EXTRA_STOCK_A")
        assert stock_list is not None
        assert stock_list[0]["code"] == "000002.SZ"
    finally:
        await provider.close()
        shutdown_pool()

    assert call_history[0][0] == "BaseData.get_code_list"
    assert call_history[1][0] == "BaseData.get_code_list"
    # 第三次调用尝试 hist_code_list 含 is_local，第四次兼容调用移除 is_local
    assert call_history[2][0] == "BaseData.get_hist_code_list"
    assert "is_local" in call_history[2][2]
    assert call_history[3][0] == "BaseData.get_hist_code_list"
    assert "is_local" not in call_history[3][2]


@pytest.mark.asyncio
async def test_process_provider_retry_after_recoverable_error():
    config_payload = {
        "enabled": True,
        "implementation_mode": "process",
        "connection": {
            "username": "stub_user",
            "password": "stub_pass",
            "host": "stub.amazingdata.local",
            "port": 8600,
            "timeout": 5,
        },
        "worker_env": {"DEEPSEARCH_AMAZINGDATA_STUB": "tests.stubs.amazingdata_stub"},
    }

    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    class _StubAdapter:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, command):
            self.calls += 1
            if self.calls == 1:
                return ProcessCallResult(
                    success=False,
                    result=None,
                    error="Worker process crashed during request",
                    error_type="RuntimeError",
                )
            return ProcessCallResult(success=True, result="OK")

    stub_adapter = _StubAdapter()
    provider._adapter = stub_adapter

    async def ensure_ready_stub(self):
        return stub_adapter

    provider._ensure_ready = MethodType(ensure_ready_stub, provider)  # type: ignore[assignment]

    command = ProcessCommand(method="dummy")
    result = await provider._execute(command)

    assert result == "OK"
    assert stub_adapter.calls == 2
