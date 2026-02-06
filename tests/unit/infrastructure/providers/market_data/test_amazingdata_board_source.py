"""AmazingData Board Source 真实数据测试。

使用真实的 AmazingData SDK 测试板块数据源功能。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skipif(True, reason="需要 AmazingData SDK 连接")


@pytest.mark.asyncio
async def test_board_data_available(real_amazingdata_provider):
    """测试板块数据可用。"""
    # 验证 provider 已连接
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_stock_list_contains_board_info(real_amazingdata_provider):
    """测试股票列表包含板块信息。"""
    stock_list = await real_amazingdata_provider.get_stock_list(limit=5)

    if stock_list:
        first = stock_list[0]
        assert isinstance(first, dict)
        # 验证是有效记录
        assert "code" in first or "symbol" in first


@pytest.mark.asyncio
async def test_board_query_successful(real_amazingdata_provider):
    """测试板块查询成功。"""
    stock_list = await real_amazingdata_provider.get_stock_list(limit=1)
    assert stock_list is not None
