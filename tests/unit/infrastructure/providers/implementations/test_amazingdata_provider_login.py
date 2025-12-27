"""AmazingData Provider 登录真实数据测试。

使用真实的 AmazingData SDK 测试登录和认证功能。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_success_state(real_amazingdata_provider):
    """测试登录成功后的状态。"""
    # Provider 已经通过 fixture 登录
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_provider_sdk_available(real_amazingdata_provider):
    """测试 SDK 可用状态。"""
    # 验证 SDK 可用
    if hasattr(real_amazingdata_provider, "_sdk_available"):
        assert real_amazingdata_provider._sdk_available is True


@pytest.mark.asyncio
async def test_provider_not_in_degraded_mode(real_amazingdata_provider):
    """测试 Provider 不在降级模式。"""
    if hasattr(real_amazingdata_provider, "_degraded_mode"):
        assert real_amazingdata_provider._degraded_mode is False


@pytest.mark.asyncio
async def test_provider_can_execute_queries(real_amazingdata_provider):
    """测试登录后可以执行查询。"""
    from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)

    # 执行简单查询验证登录有效
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    assert quotes is not None
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_provider_stats_initialized(real_amazingdata_provider):
    """测试统计信息已初始化。"""
    if hasattr(real_amazingdata_provider, "_stats"):
        stats = real_amazingdata_provider._stats
        assert isinstance(stats, dict)
        # 验证没有错误
        if "query_errors" in stats:
            assert stats["query_errors"] == 0
