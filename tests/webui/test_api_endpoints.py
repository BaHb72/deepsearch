"""
WebUI API 端点测试

测试主要的API端点功能
"""

import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from core.config import get_config, reload_config
from core.constants import YAML_ENCODING
from core.domain.market_data import StockListRecord
from core.infrastructure.providers.managers.data_source_manager import StockListFetchResult
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from apps.api.api.services.system_data_service import ComponentNotFoundError
from apps.api.server import app


class TestHealthEndpoints:
    """健康检查端点测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        """创建测试客户端"""
        return TestClient(app)

    def test_health_check(self, client: TestClient):
        """测试基本健康检查"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_detailed(self, client: TestClient):
        """测试详细健康检查"""
        response = client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "components" in data
        assert "overall_status" in data

    @pytest.mark.asyncio
    async def test_health_async(self):
        """测试异步健康检查"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200


class TestSystemEndpoints:
    """系统信息端点测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_system_info(self, client: TestClient):
        """测试系统信息获取"""
        response = client.get("/api/system/info")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "uptime" in data
        assert "environment" in data

    def test_system_config(self, client: TestClient):
        """测试系统配置获取"""
        response = client.get("/api/system/config")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    @patch("apps.api.api.endpoints.system.system.system_data_service.get_metrics")
    def test_system_metrics(self, mock_metrics, client: TestClient):
        """系统指标接口返回聚合数据。"""
        mock_metrics.return_value = {"cpu": {"usage_percent": 10.5}}
        response = client.get("/api/system/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["cpu"]["usage_percent"] == 10.5

    @patch("apps.api.api.endpoints.system.system.system_data_service.list_components")
    def test_system_components(self, mock_list, client: TestClient):
        """组件列表接口使用聚合服务。"""
        mock_list.return_value = {"components": {}}
        response = client.get("/api/system/components")
        assert response.status_code == 200
        assert "components" in response.json()

    @patch("apps.api.api.endpoints.system.system.system_data_service.get_component")
    def test_system_component_not_found(self, mock_get_component, client: TestClient):
        """组件不存在时返回 404。"""
        mock_get_component.side_effect = ComponentNotFoundError("missing")
        response = client.get("/api/system/components/missing")
        assert response.status_code == 404

    @patch("apps.api.api.endpoints.system.config.get_config")
    def test_system_config_error(self, mock_config, client: TestClient):
        """测试配置获取错误处理"""
        mock_config.side_effect = Exception("Config error")
        response = client.get("/api/system/config")
        assert response.status_code == 500

    def test_system_config_save_refreshes_runtime(self, client: TestClient):
        """保存配置后应重新加载并在后续读取中返回最新值。"""

        current_env = get_config().app.env
        config_path = Path("deepsearch/config") / f"settings.{current_env}.yaml"
        config_path = config_path.resolve()
        backup_path = config_path.with_suffix(config_path.suffix + ".autotest")

        shutil.copy2(config_path, backup_path)
        try:
            # 准备基础配置，确保测试字段处于确定状态
            baseline = yaml.safe_load(config_path.read_text(encoding=YAML_ENCODING)) or {}
            baseline.setdefault("app", {})
            baseline["app"].setdefault("env", current_env)
            baseline.setdefault("database", {}).setdefault("main", {})
            baseline["database"]["main"].update(
                {
                    "host": "initial-host",
                    "password": "initial-secret",
                    "username": baseline["database"]["main"].get("username", "tester"),
                    "database": baseline["database"]["main"].get("database", "deepsearch"),
                    "type": baseline["database"]["main"].get("type", "postgresql"),
                    "port": baseline["database"]["main"].get("port", 5432),
                    "auto_connect": True,
                    "enabled": True,
                }
            )

            baseline["database"].setdefault("cache", {})
            baseline["database"]["cache"].update(
                {
                    "enabled": True,
                    "host": "cache-host",
                    "port": 6379,
                    "username": "cache-user",
                    "password": "initial-cache-secret",
                    "db": 0,
                }
            )

            config_path.write_text(
                yaml.safe_dump(baseline, allow_unicode=True, sort_keys=False),
                encoding=YAML_ENCODING,
            )

            reload_config()

            response = client.get("/api/system/config")
            assert response.status_code == 200
            payload = response.json()

            save_payload = {
                "app": payload["app"],
                "log": payload.get("log"),
                "database": {
                    "main": {
                        k: v
                        for k, v in payload["database"]["main"].items()
                        if k != "has_saved_password"
                    },
                    "cache": {
                        k: v
                        for k, v in payload["database"]["cache"].items()
                        if k != "has_saved_password"
                    },
                },
                "message_bus": payload.get("message_bus"),
                "webui": payload.get("webui"),
                "notifications": payload.get("notifications"),
            }

            save_payload["database"]["main"].update(
                {
                    "host": "updated-host",
                    "password": "updated-secret",
                    "rememberPassword": True,
                }
            )
            save_payload["database"]["cache"].update({"password": "updated-cache"})

            save_response = client.post("/api/system/config/save", json=save_payload)
            assert save_response.status_code == 200
            save_data = save_response.json()
            assert save_data["success"] is True
            assert save_data.get("config") is not None
            assert save_data["config"]["database"]["main"]["host"] == "updated-host"

            # 新一次读取应立即反映刚刚保存的主机名
            refreshed = client.get("/api/system/config")
            assert refreshed.status_code == 200
            refreshed_payload = refreshed.json()
            assert refreshed_payload["database"]["main"]["host"] == "updated-host"

            stored = yaml.safe_load(config_path.read_text(encoding=YAML_ENCODING))
            assert stored["database"]["main"]["host"] == "updated-host"
        finally:
            shutil.copy2(backup_path, config_path)
            backup_path.unlink(missing_ok=True)
            reload_config()


class TestDataEndpoints:
    """数据相关端点测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.fixture
    def mock_data_service(self):
        """模拟数据服务"""
        with patch("apps.api.api.endpoints.data.data.get_data_service") as mock:
            service = Mock()
            service.get_stock_list = AsyncMock(
                return_value=StockListFetchResult(
                    source="test",
                    records=(
                        StockListRecord(symbol="000001", name="平安银行"),
                        StockListRecord(symbol="000002", name="万科A"),
                    ),
                    legacy=(
                        {"symbol": "000001", "name": "平安银行"},
                        {"symbol": "000002", "name": "万科A"},
                    ),
                    mismatch=0,
                )
            )
            service.get_kline_data = AsyncMock(
                return_value=[
                    {
                        "timestamp": datetime.now().isoformat(),
                        "open": 100.0,
                        "high": 105.0,
                        "low": 99.0,
                        "close": 103.0,
                        "volume": 1000000,
                    }
                ]
            )
            mock.return_value = service
            yield service

    @pytest.mark.asyncio
    async def test_get_stock_list(self, mock_data_service):
        """测试获取股票列表"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/data/stocks")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) > 0

    @pytest.mark.asyncio
    async def test_get_kline_data(self, mock_data_service):
        """测试获取K线数据"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/data/kline",
                params={
                    "symbol": "000001",
                    "period": "1d",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_data_source_status(self, client: TestClient):
        """测试数据源状态"""
        response = client.get("/api/data/source/status")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)


class TestTradingEndpoints:
    """交易相关端点测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.fixture
    def mock_market_service(self):
        """模拟市场服务"""
        with patch("apps.api.api.endpoints.trading.market.get_market_service") as mock:
            service = Mock()
            service.get_market_overview = AsyncMock(
                return_value={
                    "total_market_cap": 1000000000000,
                    "total_volume": 100000000000,
                    "market_sentiment": "neutral",
                }
            )
            service.get_top_gainers = AsyncMock(
                return_value=[{"symbol": "000001", "change_percent": 10.0}]
            )
            service.get_top_losers = AsyncMock(
                return_value=[{"symbol": "000002", "change_percent": -8.0}]
            )
            mock.return_value = service
            yield service

    @pytest.mark.asyncio
    async def test_market_overview(self, mock_market_service):
        """测试市场概览"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/trading/market/overview")
            assert response.status_code == 200
            data = response.json()
            assert "total_market_cap" in data

    @pytest.mark.asyncio
    async def test_top_movers(self, mock_market_service):
        """测试涨跌幅排行"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 测试涨幅榜
            response = await client.get("/api/trading/market/top-gainers")
            assert response.status_code == 200
            gainers = response.json()
            assert isinstance(gainers, list)

            # 测试跌幅榜
            response = await client.get("/api/trading/market/top-losers")
            assert response.status_code == 200
            losers = response.json()
            assert isinstance(losers, list)


class TestMonitoringEndpoints:
    """监控相关端点测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_metrics(self, client: TestClient):
        """测试指标获取"""
        response = client.get("/api/monitoring/metrics")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_cache_stats(self, client: TestClient):
        """测试缓存统计"""
        response = client.get("/api/monitoring/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert "hit_rate" in data
        assert "total_requests" in data
        assert "memory_usage" in data

    @pytest.mark.asyncio
    async def test_analytics(self):
        """测试分析数据"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/monitoring/analytics")
            assert response.status_code == 200
            data = response.json()
            assert "summary" in data


class TestQMTEndpoints:
    """QMT相关端点测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_qmt_status_disabled(self, client: TestClient):
        """在未配置QMT时应返回禁用状态"""
        response = client.get("/api/qmt/status")
        assert response.status_code == 503
        data = response.json()
        assert data.get("status") == "error"
        assert data.get("data", {}).get("enabled") is False

    @pytest.mark.asyncio
    async def test_qmt_account_disabled(self):
        """在未配置QMT时查询账户应返回错误"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/qmt/account")
            assert response.status_code == 503
            data = response.json()
            assert data.get("detail") in ("QMT网关未启动", "QMT unavailable")


class TestWebSocketEndpoints:
    """WebSocket端点测试"""

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """测试WebSocket连接"""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect("/ws") as websocket:
            # 发送消息
            websocket.send_json({"type": "ping"})

            # 接收响应
            data = websocket.receive_json()
            assert data["type"] == "pong"

    @pytest.mark.asyncio
    async def test_websocket_subscribe(self):
        """测试WebSocket订阅"""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect("/ws") as websocket:
            # 订阅市场数据
            websocket.send_json(
                {"type": "subscribe", "channel": "market", "symbols": ["000001", "000002"]}
            )

            # 接收确认
            data = websocket.receive_json()
            assert data["type"] == "subscribed"
            assert data["channel"] == "market"


class TestErrorHandling:
    """错误处理测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_404_error(self, client: TestClient):
        """测试404错误"""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_method_not_allowed(self, client: TestClient):
        """测试方法不允许错误"""
        response = client.post("/api/health")  # 健康检查只支持GET
        assert response.status_code == 405

    def test_validation_error(self, client: TestClient):
        """测试参数验证错误"""
        response = client.get("/api/data/kline", params={"symbol": ""})  # 空symbol应该报错
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestAuthentication:
    """认证测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_public_endpoint(self, client: TestClient):
        """测试公开端点无需认证"""
        response = client.get("/api/health")
        assert response.status_code == 200

    @pytest.mark.skip(reason="认证功能待实现")
    def test_protected_endpoint_without_auth(self, client: TestClient):
        """测试保护端点需要认证"""
        response = client.get("/api/admin/users")
        assert response.status_code == 401

    @pytest.mark.skip(reason="认证功能待实现")
    def test_protected_endpoint_with_auth(self, client: TestClient):
        """测试带认证的保护端点"""
        headers = {"Authorization": "Bearer test_token"}
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code in [200, 403]  # 200成功或403权限不足


class TestRateLimiting:
    """速率限制测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    @pytest.mark.skip(reason="速率限制待优化")
    def test_rate_limit(self, client: TestClient):
        """测试速率限制"""
        # 快速发送多个请求
        for _ in range(100):
            response = client.get("/api/data/stocks")
            if response.status_code == 429:
                # 触发速率限制
                data = response.json()
                assert "detail" in data
                assert "rate limit" in data["detail"].lower()
                break
        else:
            pytest.skip("未触发速率限制")


class TestCORS:
    """CORS测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_cors_headers(self, client: TestClient):
        """测试CORS头"""
        response = client.options(
            "/api/health",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers


class TestAPIDocumentation:
    """API文档测试"""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_openapi_schema(self, client: TestClient):
        """测试OpenAPI架构"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "components" in schema

    def test_swagger_ui(self, client: TestClient):
        """测试Swagger UI"""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_redoc(self, client: TestClient):
        """测试ReDoc"""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()


# 性能测试（可选）
class TestPerformance:
    """性能测试"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """测试并发请求"""
        import asyncio

        async def make_request(client: AsyncClient, index: int):
            response = await client.get("/api/health")
            return response.status_code == 200

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 并发100个请求
            tasks = [make_request(client, i) for i in range(100)]
            results = await asyncio.gather(*tasks)

            # 验证所有请求成功
            assert all(results)
            success_rate = sum(results) / len(results)
            assert success_rate >= 0.95  # 95%成功率

    @pytest.mark.slow
    def test_response_time(self, client: TestClient):
        """测试响应时间"""
        import time

        start = time.time()
        response = client.get("/api/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 0.1  # 响应时间小于100ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
