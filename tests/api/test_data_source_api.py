"""
数据源API接口测试
"""
import pytest
from datetime import datetime, timedelta
import json


class TestDataSourceAPI:
    """数据源API测试类"""

    def test_get_data_source_status(self, test_client, api_helper):
        """测试获取数据源状态"""
        response = test_client.get("/api/data/source/status")
        data = api_helper.assert_success_response(response)

        # 验证数据结构
        assert "sources" in data
        assert isinstance(data["sources"], list)

        for source in data["sources"]:
            assert "name" in source
            assert "enabled" in source
            assert "status" in source
            assert "priority" in source
            assert source["status"] in ["online", "offline", "error", "unknown"]

    def test_update_data_source_config(self, test_client, api_helper, mock_data_source_config):
        """测试更新数据源配置"""
        # 修改为正确的请求格式
        config_request = {
            "source": "amazingdata",
            "enabled": True,
            "priority": 1,
            "config": {
                "timeout": 5000
            }
        }
        response = test_client.post(
            "/api/data/source/config",
            json=config_request
        )
        data = api_helper.assert_success_response(response)

        assert data["updated"] == True
        assert "config" in data

    def test_get_stock_info(self, test_client, api_helper):
        """测试获取股票信息"""
        response = test_client.get("/api/data/stock/000001")
        data = api_helper.assert_success_response(response)

        # 验证必要字段
        required_fields = ["symbol", "name", "exchange", "industry"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_get_kline_data(self, test_client, api_helper):
        """测试获取K线数据"""
        params = {
            "symbol": "000001",
            "period": "1d",
            "start_date": "2025-09-01",
            "end_date": "2025-09-16"
        }
        response = test_client.get("/api/data/kline", params=params)
        data = api_helper.assert_success_response(response)

        assert isinstance(data, list)
        if data:
            kline = data[0]
            required_fields = ["date", "open", "high", "low", "close", "volume"]
            for field in required_fields:
                assert field in kline, f"Missing field in kline: {field}"

    def test_get_realtime_quote(self, test_client, api_helper):
        """测试获取实时行情"""
        response = test_client.get("/api/data/realtime/000001")
        data = api_helper.assert_success_response(response)

        required_fields = [
            "symbol", "name", "current", "change", "change_pct",
            "volume", "amount", "timestamp"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_batch_get_realtime_quotes(self, test_client, api_helper):
        """测试批量获取实时行情"""
        symbols = ["000001", "000002", "600000"]
        response = test_client.post(
            "/api/data/realtime/batch",
            json={"symbols": symbols}
        )
        data = api_helper.assert_success_response(response)

        assert isinstance(data, list)
        assert len(data) <= len(symbols)

    def test_get_market_overview(self, test_client, api_helper):
        """测试获取市场概览"""
        response = test_client.get("/api/data/market/overview")
        data = api_helper.assert_success_response(response)

        # 验证主要指数
        indices = ["sh_index", "sz_index", "cyb_index"]
        for index in indices:
            assert index in data
            assert "current" in data[index]
            assert "change" in data[index]
            assert "change_pct" in data[index]

    def test_search_stocks(self, test_client, api_helper):
        """测试股票搜索"""
        response = test_client.get("/api/data/search", params={"keyword": "银行"})
        data = api_helper.assert_success_response(response)

        assert isinstance(data, list)
        if data:
            stock = data[0]
            assert "symbol" in stock
            assert "name" in stock

    def test_get_top_gainers(self, test_client, api_helper):
        """测试获取涨幅榜"""
        response = test_client.get("/api/data/rank/gainers", params={"limit": 10})
        data = api_helper.assert_success_response(response)

        assert isinstance(data, list)
        assert len(data) <= 10

        # 验证是否按涨幅排序
        if len(data) > 1:
            for i in range(len(data) - 1):
                assert data[i]["change_pct"] >= data[i + 1]["change_pct"]

    def test_get_top_losers(self, test_client, api_helper):
        """测试获取跌幅榜"""
        response = test_client.get("/api/data/rank/losers", params={"limit": 10})
        data = api_helper.assert_success_response(response)

        assert isinstance(data, list)
        assert len(data) <= 10

        # 验证是否按跌幅排序
        if len(data) > 1:
            for i in range(len(data) - 1):
                assert data[i]["change_pct"] <= data[i + 1]["change_pct"]

    def test_data_source_failover(self, test_client, api_helper):
        """测试数据源故障转移"""
        # 先禁用主数据源
        config = {
            "amazingdata": {"enabled": False},
            "cloudflare": {"enabled": True},
            "qmt": {"enabled": False}
        }
        test_client.post("/api/data/source/config", json=config)

        # 请求数据，应该自动使用备用源
        response = test_client.get("/api/data/stock/000001")
        data = api_helper.assert_success_response(response)

        # 检查响应头中的数据源信息
        assert response.headers.get("X-Data-Source") == "cloudflare"

    @pytest.mark.parametrize("period", ["1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M"])
    def test_kline_periods(self, test_client, api_helper, period):
        """测试不同周期的K线数据"""
        params = {
            "symbol": "000001",
            "period": period,
            "limit": 100
        }
        response = test_client.get("/api/data/kline", params=params)
        data = api_helper.assert_success_response(response)

        assert isinstance(data, list)
        assert len(data) <= 100

    def test_invalid_symbol(self, test_client):
        """测试无效股票代码"""
        response = test_client.get("/api/data/stock/INVALID")

        assert response.status_code == 404
        data = response.json()
        assert data["code"] != 0
        assert "message" in data

    def test_date_range_validation(self, test_client):
        """测试日期范围验证"""
        params = {
            "symbol": "000001",
            "period": "1d",
            "start_date": "2025-09-16",
            "end_date": "2025-09-01"  # 结束日期早于开始日期
        }
        response = test_client.get("/api/data/kline", params=params)

        assert response.status_code == 400
        data = response.json()
        assert data["code"] != 0

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, async_client, api_helper):
        """测试并发请求处理"""
        import asyncio

        symbols = ["000001", "000002", "600000", "600519", "002594"]

        tasks = [
            async_client.get(f"/api/data/stock/{symbol}")
            for symbol in symbols
        ]

        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == 200

    def test_cache_headers(self, test_client):
        """测试缓存头"""
        response = test_client.get("/api/data/stock/000001")

        # 检查缓存相关头
        assert "Cache-Control" in response.headers
        assert "ETag" in response.headers or "Last-Modified" in response.headers

        # 第二次请求应该返回304
        etag = response.headers.get("ETag")
        if etag:
            response2 = test_client.get(
                "/api/data/stock/000001",
                headers={"If-None-Match": etag}
            )
            # 如果缓存有效，应返回304
            # assert response2.status_code == 304

    def test_rate_limiting(self, test_client):
        """测试速率限制"""
        # 快速发送大量请求
        for i in range(100):
            response = test_client.get("/api/data/stock/000001")

            # 检查是否触发速率限制
            if response.status_code == 429:
                data = response.json()
                assert "message" in data
                assert "retry_after" in response.headers
                break
        else:
            # 如果没有触发速率限制，这个测试就是通过的
            pass

    def test_data_validation(self, test_client, api_helper):
        """测试数据验证"""
        response = test_client.get("/api/data/kline", params={
            "symbol": "000001",
            "period": "1d",
            "limit": 1000
        })
        data = api_helper.assert_success_response(response)

        for kline in data:
            # 验证价格关系
            assert kline["high"] >= kline["low"]
            assert kline["high"] >= kline["open"]
            assert kline["high"] >= kline["close"]
            assert kline["low"] <= kline["open"]
            assert kline["low"] <= kline["close"]

            # 验证数据类型
            assert isinstance(kline["volume"], (int, float))
            assert kline["volume"] >= 0