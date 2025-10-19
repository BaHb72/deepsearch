import os

import pytest

os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process import (  # noqa: E402
    ProcessIsolatedAmazingDataProvider,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (  # noqa: E402
    shutdown_pool,
)


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
