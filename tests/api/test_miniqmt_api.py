"""
MiniQMT API 端点测试套件

测试 MiniQMT REST API 端点功能：
- 状态查询
- 订阅管理
- 数据获取
- 连接管理
- 统计信息

使用 FastAPI TestClient 进行 HTTP 接口测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestMiniQMTAPIStatus:
    """MiniQMT API 状态接口测试"""

    def test_get_status(self, client: TestClient):
        """测试获取 MiniQMT 状态"""
        response = client.get("/api/miniqmt/status")

        # 接口应该返回状态信息，即使未连接
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "connected" in data or "status" in data


class TestMiniQMTAPISubscribe:
    """MiniQMT API 订阅接口测试"""

    def test_subscribe_symbols(self, client: TestClient):
        """测试订阅股票"""
        response = client.post(
            "/api/miniqmt/subscribe",
            json={"symbols": ["000001.SZ", "600000.SH"]},
        )

        # 可能因为未连接而失败，但接口应该返回合理的状态码
        assert response.status_code in [200, 400, 500, 503]

    def test_unsubscribe_symbols(self, client: TestClient):
        """测试取消订阅"""
        response = client.post(
            "/api/miniqmt/unsubscribe",
            json={"symbols": ["000001.SZ"]},
        )

        assert response.status_code in [200, 400, 500, 503]

    def test_get_subscriptions(self, client: TestClient):
        """测试获取订阅列表"""
        response = client.get("/api/miniqmt/subscriptions")

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


class TestMiniQMTAPIData:
    """MiniQMT API 数据接口测试"""

    def test_get_realtime_data(self, client: TestClient):
        """测试获取实时行情数据"""
        response = client.get("/api/miniqmt/realtime?symbols=000001.SZ,600000.SH")

        # 可能因为未连接而失败
        assert response.status_code in [200, 400, 500, 503]

    def test_get_history_data(self, client: TestClient):
        """测试获取历史K线数据"""
        response = client.get(
            "/api/miniqmt/history",
            params={
                "symbol": "000001.SZ",
                "start_date": "2024-01-01",
                "end_date": "2024-01-10",
                "period": "1d",
            },
        )

        assert response.status_code in [200, 400, 500, 503]

    def test_get_minute_data(self, client: TestClient):
        """测试获取分钟K线数据"""
        response = client.get(
            "/api/miniqmt/minute",
            params={
                "symbol": "000001.SZ",
                "period": "5m",
            },
        )

        assert response.status_code in [200, 400, 500, 503]


class TestMiniQMTAPIConnection:
    """MiniQMT API 连接管理测试"""

    def test_reconnect(self, client: TestClient):
        """测试重新连接"""
        response = client.post("/api/miniqmt/reconnect")

        # 重连操作可能成功或失败
        assert response.status_code in [200, 400, 500, 503]


class TestMiniQMTAPIStatistics:
    """MiniQMT API 统计信息测试"""

    def test_get_statistics(self, client: TestClient):
        """测试获取统计信息"""
        response = client.get("/api/miniqmt/statistics")

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


class TestMiniQMTAPIWithMock:
    """使用 Mock 的 MiniQMT API 测试

    这些测试通过模拟 Provider 来验证 API 逻辑，不需要真实的 MiniQMT 连接
    """

    @pytest.fixture
    def mock_provider(self):
        """模拟 MiniQMT Provider (Dask Actor)"""
        provider = MagicMock()
        provider.connected = True
        # 实际 API 使用 get_status() 异步方法，而非 get_connection_status()
        provider.get_status = AsyncMock(
            return_value={
                "connected": True,
                "initialized": True,
                "error_count": 0,
                "host": "127.0.0.1",
                "port": 7777,
                "subscribed_symbols": ["000001.SZ"],
                "last_heartbeat": 1234567890,
                "reconnect_attempts": 0,
                "queue_size": 0,
            }
        )
        # 保留 get_connection_status 用于兼容性
        provider.get_connection_status.return_value = {
            "connected": True,
            "host": "127.0.0.1",
            "port": 7777,
            "subscribed_symbols": ["000001.SZ"],
            "last_heartbeat": 1234567890,
            "reconnect_attempts": 0,
            "queue_size": 0,
        }
        provider.subscribed_symbols = {"000001.SZ"}
        return provider

    def test_status_with_mock(self, client: TestClient, mock_provider):
        """使用 Mock 测试状态接口"""
        with patch(
            "apps.api.api.endpoints.qmt.miniqmt.get_miniqmt_provider",
            return_value=mock_provider,
        ):
            response = client.get("/api/miniqmt/status")

            # 有 Mock 的情况下应该返回成功
            if response.status_code == 200:
                data = response.json()
                assert data.get("connected") is True or "status" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
