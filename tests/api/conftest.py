"""
API测试配置和fixtures
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from deepsearch.observability import get_logger, logger_manager

# 配置日志
logger_manager.start()
logger = get_logger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_client() -> Generator[TestClient, None, None]:
    """创建测试客户端"""
    from deepsearch.webui.server import app

    headers = {"X-Test-Mode": "true"}
    with TestClient(app, headers=headers) as client:
        yield client


@pytest.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """创建异步测试客户端"""
    from deepsearch.webui.server import app

    transport = ASGITransport(app=app)
    headers = {"X-Test-Mode": "true"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client


@pytest.fixture(scope="function")
def api_headers():
    """API请求头"""
    return {"Content-Type": "application/json", "Accept": "application/json", "X-Test-Mode": "true"}


@pytest.fixture(scope="function")
def auth_headers():
    """认证请求头"""
    return {"Authorization": "Bearer test-token-123456", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def test_data_dir():
    """测试数据目录"""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="function")
def mock_stock_data():
    """模拟股票数据"""
    return {
        "symbol": "000001",
        "name": "平安银行",
        "price": 12.34,
        "change": 0.56,
        "change_pct": 4.75,
        "volume": 123456789,
        "amount": 1523456789.12,
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture(scope="function")
def mock_kline_data():
    """模拟K线数据"""
    return [
        {
            "date": "2025-09-16",
            "open": 12.10,
            "high": 12.50,
            "low": 12.00,
            "close": 12.34,
            "volume": 10000000,
            "amount": 123000000,
        },
        {
            "date": "2025-09-15",
            "open": 12.00,
            "high": 12.30,
            "low": 11.90,
            "close": 12.10,
            "volume": 9500000,
            "amount": 115000000,
        },
    ]


@pytest.fixture(scope="function")
def mock_market_overview():
    """模拟市场概览数据"""
    return {
        "sh_index": {
            "code": "000001",
            "name": "上证指数",
            "current": 3124.56,
            "change": 12.34,
            "change_pct": 0.40,
        },
        "sz_index": {
            "code": "399001",
            "name": "深证成指",
            "current": 9876.54,
            "change": -23.45,
            "change_pct": -0.24,
        },
        "cyb_index": {
            "code": "399006",
            "name": "创业板指",
            "current": 2345.67,
            "change": 34.56,
            "change_pct": 1.50,
        },
    }


@pytest.fixture(scope="function")
def mock_data_source_config():
    """模拟数据源配置"""
    return {
        "amazingdata": {"enabled": True, "priority": 1, "timeout": 5000},
        "cloudflare": {"enabled": True, "priority": 2, "timeout": 3000},
        "qmt": {"enabled": False, "priority": 3, "timeout": 10000},
    }


@pytest.fixture(autouse=True)
def reset_test_state():
    """每个测试前后重置状态"""
    # 测试前准备
    logger.info("Setting up test state...")

    yield

    # 测试后清理
    logger.info("Cleaning up test state...")


class APITestHelper:
    """API测试辅助类"""

    @staticmethod
    def assert_success_response(response, expected_code=200):
        """断言成功响应"""
        assert response.status_code == expected_code
        data = response.json()
        assert "code" in data
        assert data["code"] == 0
        assert "data" in data
        return data["data"]

    @staticmethod
    def assert_error_response(response, expected_code=400):
        """断言错误响应"""
        assert response.status_code == expected_code
        data = response.json()
        assert "code" in data
        assert data["code"] != 0
        assert "message" in data
        return data

    @staticmethod
    def assert_pagination(data):
        """断言分页数据"""
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)

    @staticmethod
    def compare_json(actual, expected, ignore_fields=None):
        """比较JSON数据"""
        ignore_fields = ignore_fields or []

        if isinstance(expected, dict) and isinstance(actual, dict):
            for key, value in expected.items():
                if key in ignore_fields:
                    continue
                assert key in actual, f"Missing key: {key}"
                APITestHelper.compare_json(actual[key], value, ignore_fields)
        elif isinstance(expected, list) and isinstance(actual, list):
            assert len(actual) == len(expected), "List length mismatch"
            for a, e in zip(actual, expected):
                APITestHelper.compare_json(a, e, ignore_fields)
        else:
            assert actual == expected, f"Value mismatch: {actual} != {expected}"


@pytest.fixture
def api_helper():
    """提供API测试辅助功能"""
    return APITestHelper()
