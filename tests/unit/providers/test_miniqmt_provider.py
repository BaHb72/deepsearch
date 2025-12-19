"""
MiniQMT Provider 测试套件

测试 MiniQMTProvider 的核心功能：
- 初始化和配置
- 能力声明
- 连接管理
- 数据获取

依赖：
- xtquant SDK（已安装）
- MiniQMT 终端（可选，真实连接测试需要）
"""

from typing import Any, Dict, List, Optional

import pytest

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProviderConfig,
    DataRequest,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability


def _create_testable_provider(config: Optional[DataProviderConfig] = None):
    """创建可测试的 MiniQMTProvider 实例
    
    由于 MiniQMTProvider 继承自 DataProvider 但未实现所有抽象方法，
    我们创建一个测试子类来实现这些方法
    """
    from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import (
        MiniQMTProvider,
    )

    class TestMiniQMT(MiniQMTProvider):
        async def initialize(self) -> bool:
            return True

        async def get_stock_list(
                self, limit: Optional[int] = None, **kwargs
        ) -> Optional[List[Dict[str, Any]]]:
            return []

        async def get_kline_data(
                self,
                symbol: str,
                period: str = "1d",
                start_date: Optional[str] = None,
                end_date: Optional[str] = None,
                limit: int = 100,
                adjust: str = "none",
                **kwargs,
        ) -> Optional[List[Dict[str, Any]]]:
            return []

    return TestMiniQMT(config) if config else TestMiniQMT()


class TestMiniQMTProviderInit:
    """MiniQMTProvider 初始化测试"""

    def test_provider_init_default_config(self):
        """测试默认配置初始化"""
        provider = _create_testable_provider()

        assert provider.config is not None
        assert provider.config.name == "miniqmt"
        assert provider.config.source_type == DataSourceType.QMT
        assert provider.config.enabled is True
        assert provider.host == "127.0.0.1"
        assert provider.port == 7777

    def test_provider_init_custom_config(self):
        """测试自定义配置初始化"""
        config = DataProviderConfig(
            name="custom_miniqmt",
            source_type=DataSourceType.QMT,
            enabled=True,
            timeout=30,
            config={
                "max_concurrent": 20,
                "rate_limit": 200,
            },
        )

        provider = _create_testable_provider(config)

        assert provider.config.name == "custom_miniqmt"
        assert provider.config.timeout == 30

    def test_get_capabilities(self):
        """测试能力声明"""
        provider = _create_testable_provider()
        capabilities = provider.get_capabilities()

        expected = {
            # 基础行情能力
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.TICK_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.KLINE_DATA,
            # 基础信息能力
            DataCapability.STOCK_LIST,
            DataCapability.STOCK_INFO,
            DataCapability.ORDER_BOOK,
            DataCapability.TRADING_CALENDAR,
            # 特色数据能力
            DataCapability.CAPITAL_FLOW,
            DataCapability.DRAGON_TIGER,
            DataCapability.NORTH_FLOW,
            DataCapability.FINANCIAL_DATA,
            DataCapability.SECTOR_DATA,
            # 扩展数据能力
            DataCapability.INDEX_DATA,
            DataCapability.INDUSTRY_DATA,
            DataCapability.ORDER_FLOW,
        }

        assert capabilities == expected


class TestMiniQMTProviderConnection:
    """MiniQMTProvider 连接管理测试"""

    def test_connection_status_initial(self):
        """测试初始连接状态"""
        provider = _create_testable_provider()
        status = provider.get_connection_status()

        assert status["connected"] is False
        assert status["host"] == "127.0.0.1"
        assert status["port"] == 7777
        assert status["subscribed_symbols"] == []
        assert status["reconnect_attempts"] == 0

    @pytest.mark.asyncio
    async def test_connect_without_server(self):
        """测试没有服务器时的连接（预期失败）"""
        provider = _create_testable_provider()
        # 使用不存在的端口
        provider.port = 59999

        result = await provider._connect()

        assert result is False
        assert provider.connected is False


class TestMiniQMTProviderSubscription:
    """MiniQMTProvider 订阅管理测试"""

    def test_add_symbol_callback(self):
        """测试添加回调函数"""
        provider = _create_testable_provider()

        callback_called = False

        def my_callback(data: Dict[str, Any]) -> None:
            nonlocal callback_called
            callback_called = True

        provider.add_symbol_callback("000001.SZ", my_callback)

        assert "000001.SZ" in provider.symbol_callbacks
        assert len(provider.symbol_callbacks["000001.SZ"]) == 1

    def test_remove_symbol_callback(self):
        """测试移除回调函数"""
        provider = _create_testable_provider()

        def my_callback(data: Dict[str, Any]) -> None:
            pass

        provider.add_symbol_callback("000001.SZ", my_callback)
        provider.remove_symbol_callback("000001.SZ", my_callback)

        assert len(provider.symbol_callbacks["000001.SZ"]) == 0


class TestMiniQMTProviderDataRequest:
    """MiniQMTProvider 数据请求测试"""

    @pytest.mark.asyncio
    async def test_get_data_not_connected(self):
        """测试未连接时获取数据"""
        provider = _create_testable_provider()
        # 使用不存在的端口，确保连接失败
        provider.port = 59999

        request = DataRequest(
            symbol="000001.SZ",
            period="1d",
            request_type="kline",
        )

        response = await provider.get_data(request)

        assert response.success is False
        assert response.error is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
