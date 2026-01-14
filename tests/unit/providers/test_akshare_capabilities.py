"""
AKShareDirectProvider 能力和接口真实测试

使用真实 AkShare 调用，严格控制频率避免封禁
- 每个测试间隔 2 秒
- 仅测试必要的核心功能
"""

import asyncio

import pytest
from core.infrastructure.providers.interfaces.capabilities import DataCapability

# 全局速率限制：每次测试后等待
RATE_LIMIT_SECONDS = 2.0


class TestAKShareDirectProviderCapabilities:
    """测试 AKShareDirectProvider 的能力声明"""

    @pytest.fixture
    def provider(self):
        """创建真实的 Provider 实例"""
        from core.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )

        provider = AKShareDirectProvider(config={})
        return provider

    def test_get_capabilities_returns_set(self, provider):
        """测试 get_capabilities 返回 set 类型"""
        capabilities = provider.get_capabilities()
        assert isinstance(capabilities, set)

    def test_get_capabilities_contains_required_capabilities(self, provider):
        """测试 get_capabilities 包含所有必需的能力"""
        capabilities = provider.get_capabilities()

        required_capabilities = {
            DataCapability.STOCK_LIST,
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.STOCK_INFO,
            DataCapability.CAPITAL_FLOW,
            DataCapability.SECTOR_DATA,
            DataCapability.INDUSTRY_DATA,
            DataCapability.MARGIN_TRADING,
            DataCapability.BLOCK_TRADE,
            DataCapability.NORTH_FLOW,
            DataCapability.DRAGON_TIGER,
            DataCapability.FINANCIAL_DATA,
            DataCapability.TRADING_CALENDAR,
        }

        for cap in required_capabilities:
            assert cap in capabilities, f"缺少能力: {cap}"

    def test_get_capabilities_count(self, provider):
        """测试能力数量"""
        capabilities = provider.get_capabilities()
        # 至少应该有14种能力
        assert len(capabilities) >= 14


class TestAKShareDirectProviderRealAPI:
    """测试真实 AkShare API 调用

    注意：这些测试会发起真实网络请求
    - 每个测试间隔 2 秒
    - 测试日期使用历史日期避免无数据问题
    """

    @pytest.fixture
    async def provider(self):
        """创建并初始化真实的 Provider 实例"""
        from core.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )

        provider = AKShareDirectProvider(config={})
        await provider.initialize()
        yield provider
        # 清理资源
        await provider.close()
        # 测试后等待，遵守速率限制
        await asyncio.sleep(RATE_LIMIT_SECONDS)

    @pytest.mark.asyncio
    async def test_get_trading_calendar_real(self, provider):
        """测试真实交易日历获取"""
        result = await provider.get_trading_calendar(
            start_date="20241201",
            end_date="20241213",
        )

        # 验证返回结果
        assert result is not None, "交易日历返回 None"
        assert isinstance(result, list), "交易日历应返回列表"
        assert len(result) > 0, "交易日历不应为空"

        # 验证日期格式
        for date in result:
            assert len(date) == 8, f"日期格式错误: {date}"
            assert date.isdigit(), f"日期应为数字: {date}"

        print(f"[OK] 获取到 {len(result)} 个交易日")

    @pytest.mark.asyncio
    async def test_get_stock_list_real(self, provider):
        """测试真实股票列表获取"""
        result = await provider.get_stock_list(limit=10)

        assert result is not None, "股票列表返回 None"
        assert len(result) > 0, "股票列表不应为空"

        # 验证第一条记录结构
        first = result[0]
        assert "symbol" in first or "code" in first, "缺少股票代码字段"

        print(f"[OK] 获取到 {len(result)} 只股票")

    @pytest.mark.asyncio
    async def test_get_kline_data_real(self, provider):
        """测试真实K线数据获取"""
        result = await provider.get_kline_data(
            symbol="000001",
            period="1d",
            limit=5,
        )

        assert result is not None, "K线数据返回 None"
        assert isinstance(result, list), "K线数据应返回列表"
        assert len(result) > 0, "K线数据不应为空"

        # 验证K线结构
        first = result[0]
        kline_fields = ["open", "high", "low", "close", "volume"]
        for field in kline_fields:
            assert field in first, f"K线缺少字段: {field}"

        print(f"[OK] 获取到 {len(result)} 条K线数据")


class TestAKShareDirectProviderExtendedAPI:
    """测试扩展接口（龙虎榜、分钟K线等）

    这些接口可能因为时间、日期等原因返回空数据，测试更宽松
    """

    @pytest.fixture
    async def provider(self):
        """创建并初始化真实的 Provider 实例"""
        from core.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )

        provider = AKShareDirectProvider(config={})
        await provider.initialize()
        yield provider
        # 清理资源
        await provider.close()
        # 测试后等待
        await asyncio.sleep(RATE_LIMIT_SECONDS)

    @pytest.mark.asyncio
    async def test_get_dragon_tiger_real(self, provider):
        """测试真实龙虎榜获取

        使用历史日期确保有数据
        """
        # 使用最近的交易日
        result = await provider.get_dragon_tiger(date="20241213")

        # 龙虎榜可能某些日期没有数据
        assert result is not None, "龙虎榜返回 None（接口异常）"
        assert isinstance(result, list), "龙虎榜应返回列表"

        if len(result) > 0:
            first = result[0]
            assert "symbol" in first, "缺少股票代码"
            assert "name" in first, "缺少股票名称"
            print(f"[OK] 获取到 {len(result)} 条龙虎榜数据")
        else:
            print("[OK] 龙虎榜当日无数据（正常情况）")

    @pytest.mark.asyncio
    async def test_get_minute_kline_real(self, provider):
        """测试真实分钟K线获取"""
        result = await provider.get_minute_kline(
            symbol="000001",
            period="5",
        )

        # 分钟数据只在交易时段有效
        assert result is not None, "分钟K线返回 None（接口异常）"
        assert isinstance(result, list), "分钟K线应返回列表"

        if len(result) > 0:
            first = result[0]
            assert "open" in first, "缺少开盘价"
            assert "close" in first, "缺少收盘价"
            print(f"[OK] 获取到 {len(result)} 条分钟K线")
        else:
            print("[OK] 分钟K线暂无数据（可能非交易时段）")
