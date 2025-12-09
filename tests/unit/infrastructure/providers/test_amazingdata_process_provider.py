import asyncio
import os
import time
from types import MethodType
from typing import Any

import pandas as pd
import pytest

os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process import (  # noqa: E402
    DEFAULT_HIST_CODE_LIST_START,
    ProcessIsolatedAmazingDataProvider,
    SnapshotAlignPolicy,
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
            assert "local_path" not in kwargs
            assert "is_local" not in kwargs
            return ["000001.SZ"]
        if command.method == "InfoData.get_stock_basic":
            return []
        if command.method == "BaseData.get_code_info":
            return []
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
    assert "BaseData.get_hist_code_list" in executed_methods


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
        if command.method == "InfoData.get_stock_basic":
            return []
        if command.method == "BaseData.get_code_info":
            return []
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
    hist_calls = [entry for entry in call_history if entry[0] == "BaseData.get_hist_code_list"]
    assert len(hist_calls) == 1
    assert "is_local" not in hist_calls[0][2]


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

    class _LoginManagerStub:
        def __init__(self, adapter: _StubAdapter) -> None:
            self.adapter = adapter

        async def ensure_ready(self):
            return self.adapter

        def record_success(self) -> None:
            pass

        async def handle_authentication_failure(self, reason: str) -> None:  # pragma: no cover - not expected
            raise AssertionError("authentication handler should not be triggered in this test")

    provider._login_manager = _LoginManagerStub(stub_adapter)  # type: ignore[attr-defined]
    provider._reset_connection_state = MethodType(lambda self, **_: None, provider)  # type: ignore[assignment]

    command = ProcessCommand(method="dummy")
    result = await provider._execute(command)

    assert result == "OK"
    assert stub_adapter.calls == 2


@pytest.mark.asyncio
async def test_process_provider_subscription_polling():
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
    provider._subscription_poll_interval = 0.05

    received: list[dict[str, object]] = []
    event = asyncio.Event()

    async def callback(payload):
        received.append(payload)
        event.set()

    try:
        await provider.subscribe_stock_snapshot(["000001.SZ"], callback)
        await asyncio.wait_for(event.wait(), timeout=2.5)
        assert received, "订阅回调应收到至少一条数据"
        payload = received[0]
        assert isinstance(payload, dict)
        data = payload.get("data", {})
        assert isinstance(data, dict)
        assert data.get("code") == "000001.SZ"
        await provider.unsubscribe_quote(["000001.SZ"])
    finally:
        await provider.close()
        shutdown_pool()


@pytest.mark.asyncio
async def test_get_realtime_quote_skips_non_trading_day(monkeypatch):
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    provider._current_date_int = MethodType(lambda self: 20251102, provider)  # type: ignore[assignment]

    async def fake_trading_days(self, market: str) -> set[int]:
        return {20251101}

    provider._get_trading_days = MethodType(fake_trading_days, provider)  # type: ignore[assignment]

    async def fail_execute(self, command):  # pragma: no cover - should not run
        raise AssertionError("execute should not be invoked on non-trading day")

    provider._execute = MethodType(fail_execute, provider)  # type: ignore[assignment]

    result = await provider.get_realtime_quote(["000001.SZ"])
    assert result == {}


@pytest.mark.asyncio
async def test_query_snapshot_adjusts_trading_range():
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    async def fake_trading_days(self, market: str) -> set[int]:
        return {20251101, 20251104, 20251105}

    provider._get_trading_days = MethodType(fake_trading_days, provider)  # type: ignore[assignment]

    captured: dict[str, Any] = {}

    async def fake_execute(self, command):
        captured["method"] = command.method
        captured["kwargs"] = dict(command.kwargs)
        return {"000001.SZ": pd.DataFrame([{"close": 10.5}])}

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    result = await provider.query_snapshot(["000001.SZ"], 20251102, 20251106)
    assert "000001.SZ" in result
    assert captured["method"] == "MarketData.query_snapshot"
    assert captured["kwargs"]["begin_date"] == 20251104
    assert captured["kwargs"]["end_date"] == 20251105


@pytest.mark.asyncio
async def test_query_snapshot_strict_requires_trading_day():
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    async def fake_trading_days(self, market: str) -> set[int]:
        return {20251101, 20251105}

    provider._get_trading_days = MethodType(fake_trading_days, provider)  # type: ignore[assignment]

    async def fake_execute(self, command):  # pragma: no cover - strict 模式不应执行
        raise AssertionError("strict policy should not call execute")

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    result = await provider.query_snapshot(
        ["000001.SZ"],
        20251102,
        20251106,
        align_policy=SnapshotAlignPolicy.STRICT,
    )
    assert result == {}


@pytest.mark.asyncio
async def test_query_snapshot_passthrough_keeps_range():
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    async def fake_trading_days(self, market: str) -> set[int]:
        return {20251101, 20251104, 20251105}

    provider._get_trading_days = MethodType(fake_trading_days, provider)  # type: ignore[assignment]

    captured: dict[str, Any] = {}

    async def fake_execute(self, command):
        captured["kwargs"] = dict(command.kwargs)
        return {"000001.SZ": pd.DataFrame([{"close": 10.5}])}

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    result = await provider.query_snapshot(
        ["000001.SZ"],
        20251102,
        20251106,
        align_policy=SnapshotAlignPolicy.PASSTHROUGH,
    )
    assert "000001.SZ" in result
    assert captured["kwargs"]["begin_date"] == 20251102
    assert captured["kwargs"]["end_date"] == 20251106


@pytest.mark.asyncio
async def test_query_snapshot_serializes_nested_payload():
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    async def fake_trading_days(self, market: str) -> set[int]:
        return {20251104}

    provider._get_trading_days = MethodType(fake_trading_days, provider)  # type: ignore[assignment]

    sample_df = pd.DataFrame(
        {
            "datetime": [pd.Timestamp("2025-11-04 10:00:00")],
            "close": [10.5],
            "volume": [123456],
        }
    )

    async def fake_execute(self, command):
        return {20251104: {"000001.SZ": sample_df}}

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    result = await provider.query_snapshot(["000001.SZ"], 20251104, 20251104)
    assert "000001.SZ" in result
    payload = result["000001.SZ"]
    assert payload["columns"]
    assert payload["records"]
    first_record = payload["records"][0]
    assert first_record["close"] == 10.5
    assert first_record["volume"] == 123456
    assert isinstance(first_record["datetime"], str)
    assert first_record["datetime"].startswith("2025-11-04")


@pytest.mark.asyncio
async def test_query_snapshot_nearest_prev_single_day_falls_back():
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    async def fake_trading_days(self, market: str) -> set[int]:
        # 模拟 2025-11-01 为最近的交易日，2025-11-02 为周末
        return {20251030, 20251031, 20251101, 20251103}

    provider._get_trading_days = MethodType(fake_trading_days, provider)  # type: ignore[assignment]

    captured: dict[str, Any] = {}

    async def fake_execute(self, command):
        captured["kwargs"] = dict(command.kwargs)
        return {"000001.SZ": pd.DataFrame([{"close": 10.5}])}

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    result = await provider.query_snapshot(
        ["000001.SZ"],
        20251102,
        20251102,
        align_policy=SnapshotAlignPolicy.NEAREST_PREV,
    )
    assert "000001.SZ" in result
    assert captured["kwargs"]["begin_date"] == 20251101
    assert captured["kwargs"]["end_date"] == 20251101


@pytest.mark.asyncio
async def test_get_trading_days_falls_back_to_cache_on_failure():
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    provider._initialized = True
    provider._connected = True

    cached_days = {20251101, 20251104}
    async with provider._calendar_cache_lock:
        provider._calendar_cache["SH"] = (
            cached_days,
            time.monotonic() - provider._TRADING_CALENDAR_TTL_SECONDS - 5,
        )

    async def fake_execute(self, command):
        raise DataProviderError("calendar unavailable")

    provider._execute = MethodType(fake_execute, provider)  # type: ignore[assignment]

    result = await provider._get_trading_days("SH")
    assert result == cached_days


def test_merge_board_metadata_prefers_listplate():
    from deepsearch.infrastructure.providers.implementations.amazingdata.helpers import (  # noqa: PLC0415
        _merge_board_metadata,
    )

    records = [
        {
            "code": "300001.SZ",
            "board": "主板",
        }
    ]
    metadata = [
        {
            "symbol": "300001.SZ",
            "LISTPLATE_NAME": "创业板",
        }
    ]

    _merge_board_metadata(records, metadata)

    assert records[0]["LISTPLATE_NAME"] == "创业板"
    assert records[0]["board"] == "创业板"


@pytest.mark.asyncio
async def test_subscribe_stock_snapshot_period_validation():
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
    }
    provider = ProcessIsolatedAmazingDataProvider(config_payload)

    async def fake_initialize(self) -> bool:
        return True

    provider.initialize = MethodType(fake_initialize, provider)  # type: ignore[assignment]
    provider.is_connected = MethodType(lambda self: True, provider)  # type: ignore[assignment]

    async def noop_dispatch(self, codes, callbacks):
        return None

    provider._subscription.dispatch_payloads = MethodType(  # type: ignore[attr-defined]
        noop_dispatch,
        provider._subscription,
    )

    with pytest.raises(DataProviderError):
        await provider.subscribe_stock_snapshot(["000001.SZ"], lambda *_: None, data_type="snapshotfuture",
                                                period="snapshot")

    assert await provider.subscribe_stock_snapshot(
        ["000001.SZ"],
        lambda *_: None,
        data_type="snapshotfuture",
        period="snapshotfuture",
    )
    await asyncio.sleep(0)
    await provider._stop_subscription_loop()


@pytest.mark.asyncio
async def test_process_provider_resumes_subscriptions_after_disconnect(monkeypatch):
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
        "config": {"subscription_poll_interval": 0.05},
    }

    provider = ProcessIsolatedAmazingDataProvider(config_payload)
    dispatch_calls: list[tuple[tuple[str, ...], dict[str, int]]] = []

    async def fake_dispatch(self, codes, callbacks_map):
        dispatch_calls.append((tuple(codes), {code: len(cb) for code, cb in callbacks_map.items()}))

    monkeypatch.setattr(
        provider._subscription,
        "dispatch_payloads",
        MethodType(fake_dispatch, provider._subscription),
    )

    def sample_callback(_: Any) -> None:
        return None

    try:
        await provider.initialize()
        await provider.subscribe_stock_snapshot(["000001", "000002"], sample_callback)
        await asyncio.sleep(0.1)

        initial_dispatch_count = len(dispatch_calls)
        assert initial_dispatch_count >= 1
        assert provider._subscription.has_active()
        assert provider._subscription._pending_snapshot is None  # type: ignore[attr-defined]

        provider._mark_connected(False, error="simulated disconnect")
        await asyncio.sleep(0.1)

        assert provider._subscription._pending_snapshot is not None  # type: ignore[attr-defined]
        assert not (await provider.snapshot_subscriptions())
        assert provider._subscription._task is None  # type: ignore[attr-defined]

        provider._mark_connected(True)
        await asyncio.sleep(0.1)

        assert provider._subscription._pending_snapshot is None  # type: ignore[attr-defined]
        assert await provider.snapshot_subscriptions()
        assert len(dispatch_calls) > initial_dispatch_count
    finally:
        await provider.close()
        shutdown_pool()
