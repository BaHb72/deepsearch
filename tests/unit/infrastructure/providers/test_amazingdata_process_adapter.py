"""AmazingData Process Adapter 真实数据测试。

使用真实的 AmazingData SDK 测试进程适配器功能。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_process_adapter_connection(real_amazingdata_provider):
    """测试进程适配器连接状态。"""
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_process_adapter_execute_query(real_amazingdata_provider):
    """测试进程适配器执行查询。"""
    from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    assert quotes is not None


@pytest.mark.asyncio
async def test_process_adapter_health(real_amazingdata_provider):
    """测试进程适配器健康状态。"""
    # 验证 provider 健康
    assert real_amazingdata_provider._connected is True
    if hasattr(real_amazingdata_provider, "_initialized"):
        assert real_amazingdata_provider._initialized is True
