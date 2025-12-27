"""AmazingData Process Login Flow 真实数据测试。

使用真实的 AmazingData SDK 测试登录流程。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_flow_success(real_amazingdata_provider):
    """测试登录流程成功。"""
    # Provider 通过 fixture 已登录
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_login_state_maintained(real_amazingdata_provider):
    """测试登录状态保持。"""
    from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)

    # 多次查询后登录状态应保持
    for _ in range(3):
        await manager.fetch_realtime_quote(symbols=["SZ000001"])

    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_login_allows_queries(real_amazingdata_provider):
    """测试登录后允许查询。"""
    from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    assert quotes is not None
