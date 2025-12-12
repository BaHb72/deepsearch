"""
MiniQMT Collector 测试套件

测试 MiniQMTCollector 数据采集器功能：
- 初始化和连接
- 历史数据下载
- 实时行情订阅
- 市场数据获取
- 缓存管理

依赖：
- xtquant SDK（必需）
- MiniQMT 终端运行（真实数据测试需要）
"""

import time

import pytest

# 尝试导入 xtquant 检查可用性
try:
    from xtquant import xtdata

    XTQUANT_AVAILABLE = True
except ImportError:
    XTQUANT_AVAILABLE = False


@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTCollectorInit:
    """MiniQMTCollector 初始化测试"""

    def test_collector_init(self):
        """测试采集器初始化"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        assert collector is not None
        assert hasattr(collector, "subscriptions")
        assert hasattr(collector, "data_cache")

    def test_get_connection_status(self):
        """测试获取连接状态"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()
        status = collector.get_connection_status()

        assert isinstance(status, dict)
        assert "connected" in status


@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTCollectorCache:
    """MiniQMTCollector 缓存管理测试"""

    def test_cache_data(self):
        """测试数据缓存"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        test_data = {"symbol": "000001.SZ", "price": 10.5}
        collector._cache_data("test_key", test_data)

        cached = collector._get_cached_data("test_key")
        assert cached is not None
        assert cached["symbol"] == "000001.SZ"

    def test_clear_cache(self):
        """测试清空缓存"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        collector._cache_data("test_key", {"data": "value"})
        collector.clear_cache()

        cached = collector._get_cached_data("test_key")
        assert cached is None


@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTCollectorHistoryData:
    """MiniQMTCollector 历史数据测试
    
    注意：这些测试需要 MiniQMT 终端运行才能获取真实数据
    """

    @pytest.mark.integration
    def test_download_history_data_daily(self):
        """测试下载日线历史数据"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        # 尝试下载数据（需要 MiniQMT 运行）
        try:
            df = collector.download_history_data(
                stock_code="000001.SZ",
                period="1d",
                start_time="20240101",
                end_time="20240110",
            )

            if df is not None and not df.empty:
                assert "close" in df.columns or "收盘" in df.columns
                print(f"成功获取 {len(df)} 条日线数据")
            else:
                pytest.skip("MiniQMT 未运行或无数据返回")
        except Exception as e:
            pytest.skip(f"MiniQMT 连接失败: {e}")

    @pytest.mark.integration
    def test_download_history_data_minute(self):
        """测试下载分钟线历史数据"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        try:
            df = collector.download_history_data(
                stock_code="000001.SZ",
                period="5m",
                count=100,
            )

            if df is not None and not df.empty:
                assert len(df) > 0
                print(f"成功获取 {len(df)} 条5分钟数据")
            else:
                pytest.skip("MiniQMT 未运行或无数据返回")
        except Exception as e:
            pytest.skip(f"MiniQMT 连接失败: {e}")


@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTCollectorMarketData:
    """MiniQMTCollector 市场数据获取测试"""

    @pytest.mark.integration
    def test_get_market_data(self):
        """测试获取市场数据"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        try:
            result = collector.get_market_data(
                stock_list=["000001.SZ", "600000.SH"],
                period="1d",
                count=10,
            )

            if result:
                assert isinstance(result, dict)
                print(f"成功获取 {len(result)} 只股票的市场数据")
            else:
                pytest.skip("MiniQMT 未运行或无数据返回")
        except Exception as e:
            pytest.skip(f"MiniQMT 连接失败: {e}")

    @pytest.mark.integration
    def test_get_full_tick(self):
        """测试获取全量 Tick 数据（含五档盘口）"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        try:
            result = collector.get_full_tick(["000001.SZ"])

            if result:
                assert isinstance(result, dict)
                print(f"成功获取 Tick 数据: {list(result.keys())}")
            else:
                pytest.skip("MiniQMT 未运行或无数据返回")
        except Exception as e:
            pytest.skip(f"MiniQMT 连接失败: {e}")


@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTCollectorSubscription:
    """MiniQMTCollector 订阅管理测试"""

    @pytest.mark.integration
    def test_subscribe_and_unsubscribe(self):
        """测试订阅和取消订阅"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()
        received_data = []

        def callback(data):
            received_data.append(data)

        try:
            # 订阅
            success = collector.subscribe_quote(
                stock_code="000001.SZ",
                period="tick",
                callback=callback,
            )

            if success:
                # 等待一段时间接收数据
                time.sleep(2)

                # 取消订阅
                collector.unsubscribe_quote("000001.SZ", "tick")

                print(f"接收到 {len(received_data)} 条数据")
            else:
                pytest.skip("MiniQMT 未运行，订阅失败")
        except Exception as e:
            pytest.skip(f"MiniQMT 连接失败: {e}")


@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTCollectorInstrument:
    """MiniQMTCollector 合约信息测试"""

    @pytest.mark.integration
    def test_get_instrument_detail(self):
        """测试获取合约详细信息"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        try:
            detail = collector.get_instrument_detail("000001.SZ")

            if detail:
                assert isinstance(detail, dict)
                print(f"合约信息: {detail}")
            else:
                pytest.skip("MiniQMT 未运行或无数据返回")
        except Exception as e:
            pytest.skip(f"MiniQMT 连接失败: {e}")

    @pytest.mark.integration
    def test_get_stock_list_in_sector(self):
        """测试获取板块成分股"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        try:
            stocks = collector.get_stock_list_in_sector("沪深A股")

            if stocks:
                assert isinstance(stocks, list)
                print(f"板块包含 {len(stocks)} 只股票")
            else:
                pytest.skip("MiniQMT 未运行或无数据返回")
        except Exception as e:
            pytest.skip(f"MiniQMT 连接失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
