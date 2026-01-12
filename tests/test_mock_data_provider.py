"""
Mock Data Provider Tests

此文件展示如何在pytest测试中正确使用Mock数据。
Mock数据仅限于测试环境（env=test）使用。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.config import get_config


class MockDataProvider:
    """仅用于测试的Mock数据提供者"""

    def __init__(self):
        # 确保只在测试环境中使用
        config = get_config()
        if config.app.env != "test":
            raise RuntimeError("MockDataProvider只能在测试环境中使用")
        self.is_mock = True
        self.test_only = True

    def get_stock_info(self, symbol: str):
        """返回模拟的股票信息"""
        return {
            "symbol": symbol,
            "name": f"测试股票{symbol}",
            "price": 100.0,
            "mock": True,
            "test_only": True,
            "environment": "test",
        }

    def get_realtime_quote(self, symbol: str):
        """返回模拟的实时行情"""
        return {
            "symbol": symbol,
            "current": 100.0,
            "change": 1.0,
            "change_pct": 1.0,
            "volume": 1000000,
            "mock": True,
            "test_only": True,
        }

    def get_kline_data(self, symbol: str, period: str = "1d"):
        """返回模拟的K线数据"""
        return [
            {
                "date": "2025-09-17",
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 102.0,
                "volume": 1000000,
                "mock": True,
                "test_only": True,
            }
        ]


@pytest.fixture
def mock_config():
    """确保测试在 test 环境中运行"""
    with patch("tests.test_mock_data_provider.get_config") as mock_get_config:
        config = MagicMock()
        config.app.env = "test"
        mock_get_config.return_value = config
        yield config


@pytest.fixture
def mock_data_provider(mock_config):
    """创建Mock数据提供者fixture"""
    return MockDataProvider()


class TestMockDataProvider:
    """测试Mock数据提供者"""

    def test_mock_provider_only_in_test_env(self):
        """测试Mock Provider只能在测试环境中创建"""
        with patch("core.config.get_config") as mock_get_config:
            # 模拟生产环境
            config = MagicMock()
            config.app.env = "prod"
            mock_get_config.return_value = config

            # 应该抛出异常
            with pytest.raises(RuntimeError, match="只能在测试环境中使用"):
                MockDataProvider()

            # 模拟开发环境
            config.app.env = "dev"
            # 也应该抛出异常
            with pytest.raises(RuntimeError, match="只能在测试环境中使用"):
                MockDataProvider()

    def test_get_stock_info(self, mock_data_provider):
        """测试获取股票信息"""
        result = mock_data_provider.get_stock_info("000001")
        assert result["symbol"] == "000001"
        assert result["mock"] is True
        assert result["test_only"] is True
        assert result["environment"] == "test"

    def test_get_realtime_quote(self, mock_data_provider):
        """测试获取实时行情"""
        result = mock_data_provider.get_realtime_quote("000001")
        assert result["symbol"] == "000001"
        assert result["current"] == 100.0
        assert result["mock"] is True
        assert result["test_only"] is True

    def test_get_kline_data(self, mock_data_provider):
        """测试获取K线数据"""
        result = mock_data_provider.get_kline_data("000001")
        assert len(result) > 0
        assert result[0]["mock"] is True
        assert result[0]["test_only"] is True


class TestAPIWithMockData:
    """测试API端点使用Mock数据（仅在测试环境）"""

    @pytest.mark.asyncio
    async def test_api_endpoint_with_mock(self, mock_config):
        """测试 API 工厂在测试环境返回可用的数据源实例"""
        from core.infrastructure.providers.implementations.amazingdata.amazingdata import (
            AmazingDataProvider,
        )

        from apps.api.api.providers import DataProviderFactory

        # 清除现有实例
        DataProviderFactory.clear_all()

        # 在测试环境中获取 provider 应返回 AmazingDataProvider，并由桩模块托底
        provider = await DataProviderFactory.get_provider_async("amazingdata")

        assert isinstance(provider, AmazingDataProvider)
        capabilities = provider.get_capabilities()
        assert "stock_info" in {cap.value for cap in capabilities}

        # 访问一次行情接口，确认桩模块能返回稳定结构
        stock = await provider.get_stock_info("000001")
        if stock is not None:
            assert stock.get("symbol") == "000001"
            assert stock.get("source") == "amazingdata"

    @pytest.mark.asyncio
    async def test_api_fallback_in_production(self):
        """测试生产环境中API降级到真实数据源"""
        with patch("core.config.get_config") as mock_get_config:
            # 模拟生产环境
            config = MagicMock()
            config.app.env = "prod"
            mock_get_config.return_value = config

            from apps.api.api.providers import DataProviderFactory

            # 清除现有实例
            DataProviderFactory.clear_all()

            # 在生产环境中应在 AmazingData 初始化失败时降级到 AkShare
            with patch(
                "core.infrastructure.providers.implementations.amazingdata.amazingdata.ensure_amazingdata_provider_config",
                side_effect=RuntimeError("invalid config"),
            ) as mock_ensure:
                with patch(
                    "core.infrastructure.providers.implementations.akshare.akshare.AkShareProxyProvider"
                ) as MockAkShare:
                    mock_akshare = MagicMock()
                    mock_akshare.initialize = AsyncMock(return_value=None)
                    MockAkShare.return_value = mock_akshare

                    provider = await asyncio.wait_for(
                        DataProviderFactory.get_provider_async("amazingdata"), timeout=2
                    )

                    mock_ensure.assert_called_once()
                    MockAkShare.assert_called_once()
                    assert provider == mock_akshare


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
