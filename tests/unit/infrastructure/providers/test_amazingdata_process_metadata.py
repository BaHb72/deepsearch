"""AmazingData Process Metadata 真实数据测试。

使用真实的 AmazingData SDK 测试元数据获取功能。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_stock_list_metadata(real_amazingdata_provider):
    """测试获取股票列表元数据。"""
    stock_list = await real_amazingdata_provider.get_stock_list(limit=5)

    assert stock_list is not None
    if stock_list:
        first = stock_list[0]
        assert isinstance(first, dict)
        # 验证包含基本元数据字段
        assert "code" in first or "symbol" in first


@pytest.mark.asyncio
async def test_stock_metadata_structure(real_amazingdata_provider):
    """测试股票元数据结构。"""
    stock_list = await real_amazingdata_provider.get_stock_list(limit=3)

    if stock_list:
        for stock in stock_list:
            assert isinstance(stock, dict)
            # 验证是有效记录
            assert len(stock) > 0


@pytest.mark.asyncio
async def test_metadata_query_successful(real_amazingdata_provider):
    """测试元数据查询成功。"""
    # 验证 provider 可以执行查询
    stock_list = await real_amazingdata_provider.get_stock_list(limit=1)
    assert stock_list is not None
    assert real_amazingdata_provider._connected is True
