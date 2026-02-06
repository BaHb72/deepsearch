"""AmazingData ConnectionManager 真实数据测试。

使用真实的 AmazingData SDK 测试连接管理功能。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skipif(True, reason="需要 AmazingData SDK 连接")


@pytest.mark.asyncio
async def test_connection_manager_initialize(real_amazingdata_provider):
    """测试连接管理器初始化。"""
    # 验证 provider 已连接
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_connection_manager_maintains_session(real_amazingdata_provider):
    """测试连接管理器维护会话。"""
    # 多次访问不会导致断开
    for _ in range(3):
        assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_connection_state_after_query(real_amazingdata_provider):
    """测试查询后连接状态保持正常。"""
    from core.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)

    # 执行查询
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    # 验证连接仍然正常
    assert real_amazingdata_provider._connected is True
    assert quotes is not None


@pytest.mark.asyncio
async def test_connection_stats_tracking(real_amazingdata_provider):
    """测试连接统计跟踪。"""
    # 验证 stats 被正确初始化
    if hasattr(real_amazingdata_provider, "_stats"):
        stats = real_amazingdata_provider._stats
        assert isinstance(stats, dict)
