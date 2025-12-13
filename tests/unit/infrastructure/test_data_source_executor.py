import asyncio

import pytest

from deepsearch.infrastructure.providers.executor import DataSourceExecutor
from deepsearch.ports.data_sources import DataAccessType, DataSourceType


class DummyMonitor:
    def __init__(self):
        self.records = []

    def record_access(self, **data):
        self.records.append(data)


class DummyProvider:
    def __init__(self, response, *, raises: bool = False):
        self._response = response
        self._raises = raises

    async def get_data(self, *args, **kwargs):
        if self._raises:
            raise RuntimeError("boom")
        if asyncio.iscoroutine(self._response):
            return await self._response
        return self._response


@pytest.mark.asyncio
async def test_executor_returns_result_and_records_monitor():
    monitor = DummyMonitor()
    executor = DataSourceExecutor(monitor=monitor)
    provider = DummyProvider({"data": 1})

    result, source = await executor.execute(
        providers={DataSourceType.AMAZINGDATA: provider},
        source_order=[DataSourceType.AMAZINGDATA],
        method_name="get_data",
        monitor_symbol="000001",
        monitor_module="test",
    )

    assert result == {"data": 1}
    assert source == DataSourceType.AMAZINGDATA
    assert monitor.records[-1]["symbol"] == "000001"
    assert monitor.records[-1]["success"] is True


@pytest.mark.asyncio
async def test_executor_fallbacks_on_failure():
    monitor = DummyMonitor()
    executor = DataSourceExecutor(monitor=monitor)
    failing = DummyProvider(None, raises=True)
    succeeding = DummyProvider({"value": 2})

    result, source = await executor.execute(
        providers={
            DataSourceType.AMAZINGDATA: failing,
            DataSourceType.AKSHARE: succeeding,
        },
        source_order=[DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE],
        method_name="get_data",
        access_type=DataAccessType.STOCK_LIST,
    )

    assert source == DataSourceType.AKSHARE
    assert result == {"value": 2}
    assert monitor.records[-1]["access_type"] == DataAccessType.STOCK_LIST


@pytest.mark.asyncio
async def test_executor_respects_validator():
    monitor = DummyMonitor()
    executor = DataSourceExecutor(monitor=monitor)
    provider = DummyProvider({"success": False})

    result, source = await executor.execute(
        providers={DataSourceType.AMAZINGDATA: provider},
        source_order=[DataSourceType.AMAZINGDATA],
        method_name="get_data",
        validator=lambda payload: payload.get("success") is True,
        require_result=True,
    )

    assert result is None
    assert source is None
    assert monitor.records[-1]["success"] is False
