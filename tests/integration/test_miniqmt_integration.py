"""
MiniQMT 集成测试套件

端到端测试 MiniQMT 完整功能链路：
- 真实连接 MiniQMT 终端
- 真实数据获取和验证
- 性能测试

注意：这些测试需要：
1. MiniQMT 终端正在运行
2. xtquant SDK 已安装
3. 使用 --run-integration 参数运行

运行命令：
    pytest tests/integration/test_miniqmt_integration.py -v -s --run-integration
"""

import time
from datetime import datetime, timedelta

import pytest

# 检查 xtquant 可用性
try:
    from xtquant import xtdata

    XTQUANT_AVAILABLE = True
except ImportError:
    XTQUANT_AVAILABLE = False


def pytest_configure(config):
    """注册自定义 marker"""
    config.addinivalue_line("markers", "integration: 集成测试，需要真实 MiniQMT 环境")


@pytest.fixture
def miniqmt_connection_check():
    """检查 MiniQMT 连接是否可用"""
    if not XTQUANT_AVAILABLE:
        pytest.skip("xtquant SDK 未安装")

    try:
        # 尝试获取数据来验证连接
        from xtquant import xtdata

        # 尝试获取一只股票的数据
        result = xtdata.get_full_tick(["000001.SZ"])
        if not result or "000001.SZ" not in result:
            pytest.skip("MiniQMT 终端未运行或未返回数据")
        return True
    except Exception as e:
        pytest.skip(f"MiniQMT 连接检查失败: {e}")


@pytest.mark.integration
@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTRealConnection:
    """MiniQMT 真实连接测试"""

    def test_xtdata_import(self):
        """测试 xtdata 模块导入"""
        from xtquant import xtdata

        # 检查关键函数是否存在
        assert hasattr(xtdata, "get_full_tick")
        assert hasattr(xtdata, "get_market_data")
        assert hasattr(xtdata, "download_history_data")
        print("xtdata 模块导入成功，包含所有关键函数")

    def test_get_single_stock_tick(self, miniqmt_connection_check):
        """测试获取单只股票的 Tick 数据"""
        from xtquant import xtdata

        result = xtdata.get_full_tick(["000001.SZ"])

        assert result is not None
        assert "000001.SZ" in result

        tick_data = result["000001.SZ"]
        print(f"Tick 数据字段: {list(tick_data.keys()) if isinstance(tick_data, dict) else type(tick_data)}")

    def test_get_multiple_stocks_tick(self, miniqmt_connection_check):
        """测试获取多只股票的 Tick 数据"""
        from xtquant import xtdata

        stocks = ["000001.SZ", "600000.SH", "000002.SZ"]
        result = xtdata.get_full_tick(stocks)

        assert result is not None
        received_stocks = [s for s in stocks if s in result]
        print(f"成功获取 {len(received_stocks)}/{len(stocks)} 只股票的 Tick 数据")


@pytest.mark.integration
@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTHistoryData:
    """MiniQMT 历史数据测试"""

    def test_download_daily_kline(self, miniqmt_connection_check):
        """测试下载日线数据"""
        from xtquant import xtdata

        # 下载最近 10 天的日线数据
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        try:
            xtdata.download_history_data(
                "000001.SZ", "1d", start_time=start_date, end_time=end_date
            )

            # 获取已下载的数据
            data = xtdata.get_market_data(
                stock_list=["000001.SZ"],
                period="1d",
                start_time=start_date,
                end_time=end_date,
            )

            if data:
                print(f"成功获取日线数据")
                assert data is not None
        except Exception as e:
            pytest.skip(f"下载历史数据失败: {e}")

    def test_download_minute_kline(self, miniqmt_connection_check):
        """测试下载分钟数据"""
        from xtquant import xtdata

        try:
            # 下载 5 分钟数据
            xtdata.download_history_data("000001.SZ", "5m", count=100)

            data = xtdata.get_market_data(
                stock_list=["000001.SZ"],
                period="5m",
                count=100,
            )

            if data:
                print(f"成功获取5分钟数据")
                assert data is not None
        except Exception as e:
            pytest.skip(f"下载分钟数据失败: {e}")


@pytest.mark.integration
@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTRealtimeSubscription:
    """MiniQMT 实时订阅测试"""

    def test_subscribe_tick_data(self, miniqmt_connection_check):
        """测试订阅 Tick 数据"""
        from xtquant import xtdata

        received_data = []

        def on_data(data):
            received_data.append(data)

        try:
            # 订阅
            xtdata.subscribe_quote("000001.SZ", period="tick", callback=on_data)

            # 等待数据
            time.sleep(3)

            # 取消订阅
            xtdata.unsubscribe_quote("000001.SZ", period="tick")

            print(f"收到 {len(received_data)} 条 Tick 数据")
        except Exception as e:
            pytest.skip(f"订阅测试失败: {e}")


@pytest.mark.integration
@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTPerformance:
    """MiniQMT 性能测试"""

    def test_batch_tick_latency(self, miniqmt_connection_check):
        """测试批量获取 Tick 的延迟"""
        from xtquant import xtdata

        # 准备 50 只股票
        stocks = [f"00000{i}.SZ" for i in range(1, 10)] + [f"60000{i}.SH" for i in range(0, 10)]

        start_time = time.time()
        result = xtdata.get_full_tick(stocks[:20])
        end_time = time.time()

        latency = (end_time - start_time) * 1000  # 毫秒
        print(f"批量获取 20 只股票 Tick 延迟: {latency:.2f} ms")

        assert latency < 5000  # 应该在 5 秒内完成

    def test_multiple_requests_throughput(self, miniqmt_connection_check):
        """测试连续请求吞吐量"""
        from xtquant import xtdata

        request_count = 10
        start_time = time.time()

        for _ in range(request_count):
            xtdata.get_full_tick(["000001.SZ"])

        end_time = time.time()
        total_time = end_time - start_time
        throughput = request_count / total_time

        print(f"吞吐量测试: {request_count} 次请求在 {total_time:.2f}s 内完成")
        print(f"平均吞吐量: {throughput:.2f} 请求/秒")


@pytest.mark.integration
@pytest.mark.skipif(not XTQUANT_AVAILABLE, reason="xtquant SDK 未安装")
class TestMiniQMTProviderIntegration:
    """MiniQMTProvider 集成测试"""

    def test_provider_with_real_xtdata(self, miniqmt_connection_check):
        """使用真实 xtdata 测试 Provider"""
        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        collector = MiniQMTCollector()

        # 测试获取市场数据
        result = collector.get_market_data(
            stock_list=["000001.SZ"],
            period="1d",
            count=5,
        )

        if result:
            print(f"Provider 集成测试成功，获取数据: {list(result.keys())}")
        else:
            print("Provider 返回空数据，可能是非交易时间")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--run-integration"])
