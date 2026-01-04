"""
共享的测试数据fixtures
为所有测试提供统一的测试数据
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest

# ==================== 市场数据 Fixtures ====================


@pytest.fixture
def sample_stock_symbols():
    """示例股票代码列表"""
    return ["000001", "000002", "600000", "600036", "300001"]


@pytest.fixture
def sample_quote_data():
    """示例行情数据"""
    return {
        "symbol": "000001",
        "name": "平安银行",
        "price": 10.5,
        "open": 10.2,
        "high": 10.8,
        "low": 10.1,
        "close": 10.5,
        "pre_close": 10.3,
        "change": 0.2,
        "change_pct": 1.94,
        "volume": 150000000,
        "amount": 1575000000,
        "bid_price": 10.49,
        "ask_price": 10.50,
        "bid_volume": 10000,
        "ask_volume": 12000,
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_kline_data():
    """示例K线数据"""
    base_date = datetime.now() - timedelta(days=10)
    klines = []

    for i in range(10):
        date = base_date + timedelta(days=i)
        klines.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "open": 10.0 + i * 0.1,
                "high": 10.5 + i * 0.1,
                "low": 9.8 + i * 0.1,
                "close": 10.2 + i * 0.1,
                "volume": 100000000 + i * 1000000,
                "amount": 1020000000 + i * 10000000,
            }
        )

    return klines


@pytest.fixture
def sample_order_book():
    """示例订单簿数据"""
    return {
        "symbol": "000001",
        "timestamp": datetime.now().isoformat(),
        "bids": [
            {"price": 10.49, "volume": 10000},
            {"price": 10.48, "volume": 15000},
            {"price": 10.47, "volume": 20000},
            {"price": 10.46, "volume": 25000},
            {"price": 10.45, "volume": 30000},
        ],
        "asks": [
            {"price": 10.50, "volume": 12000},
            {"price": 10.51, "volume": 18000},
            {"price": 10.52, "volume": 22000},
            {"price": 10.53, "volume": 28000},
            {"price": 10.54, "volume": 35000},
        ],
    }


@pytest.fixture
def sample_tick_data():
    """示例逐笔成交数据"""
    base_time = datetime.now()
    ticks = []

    for i in range(20):
        tick_time = base_time + timedelta(seconds=i)
        ticks.append(
            {
                "time": tick_time.isoformat(),
                "price": 10.5 + (i % 3 - 1) * 0.01,
                "volume": 1000 * (i % 5 + 1),
                "amount": 10500 * (i % 5 + 1),
                "side": "buy" if i % 2 == 0 else "sell",
                "trade_id": f"T{1000000 + i}",
            }
        )

    return ticks


# ==================== 配置 Fixtures ====================


@pytest.fixture
def test_config():
    """测试用配置对象"""
    config = Mock()

    # 数据源配置
    config.data_sources = {
        "providers": {
            "amazingdata": {
                "enabled": True,
                "priority": 1,
                "timeout": 10,
                "retry_count": 3,
                "config": {"api_key": "test_api_key", "base_url": "http://test.api.com"},
            },
            "cloudflare": {
                "enabled": True,
                "priority": 2,
                "timeout": 15,
                "retry_count": 2,
                "config": {"worker_url": "http://worker.test.com", "timeout": 15},
            },
            "akshare": {
                "enabled": True,
                "priority": 3,
                "config": {
                    "mode": "worker",
                    "proxy": {"enabled": True, "worker_url": "http://worker.test.com"},
                },
            },
            "qmt": {"enabled": False, "priority": 3, "timeout": 5, "retry_count": 1},
        }
    }

    # 数据库配置
    config.database = Mock()
    config.database.main = Mock()
    config.database.main.enabled = True
    config.database.main.url = "sqlite:///:memory:"
    config.database.cache = Mock()
    config.database.cache.enabled = True
    config.database.cache.redis_url = "redis://localhost:6379/0"

    # WebUI配置
    config.webui = Mock()
    config.webui.enabled = True
    config.webui.backend_port = 8000
    config.webui.frontend_port = 3000

    # 消息总线配置
    config.message_bus = Mock()
    config.message_bus.buses = {
        "zmq": {"enabled": True, "config": {"pub_port": 5556, "sub_port": 5557}}
    }

    # 监控配置
    config.monitoring = Mock()
    config.monitoring.enabled = True
    config.monitoring.metrics_interval = 60

    return config


# ==================== 数据提供者 Fixtures ====================


@pytest.fixture
def mock_data_provider():
    """模拟数据提供者"""
    provider = AsyncMock()

    # 基础信息
    provider.name = "MockProvider"
    provider.get_name = Mock(return_value="MockProvider")
    provider.is_connected = Mock(return_value=True)

    # 初始化和关闭
    provider.initialize = AsyncMock(return_value=None)
    provider.close = AsyncMock(return_value=None)

    # 健康检查
    provider.health_check = AsyncMock(return_value=True)

    # 数据获取方法
    provider.get_realtime_quotes = AsyncMock(
        return_value=[
            {
                "symbol": "000001",
                "price": 10.5,
                "change": 0.2,
                "change_pct": 1.94,
                "volume": 150000000,
            }
        ]
    )

    provider.get_kline_data = AsyncMock(
        return_value=[
            {
                "date": "2025-09-16",
                "open": 10.2,
                "high": 10.8,
                "low": 10.1,
                "close": 10.5,
                "volume": 150000000,
            }
        ]
    )

    provider.get_order_book = AsyncMock(
        return_value={
            "bids": [{"price": 10.49, "volume": 10000}],
            "asks": [{"price": 10.50, "volume": 12000}],
        }
    )

    provider.get_tick_data = AsyncMock(
        return_value=[
            {"time": datetime.now().isoformat(), "price": 10.5, "volume": 1000, "side": "buy"}
        ]
    )

    return provider


# ==================== 组件 Fixtures ====================


@pytest.fixture
def mock_component():
    """模拟组件"""
    from core.core.interfaces import ComponentStatus, ComponentType

    component = Mock()
    component.name = "test_component"
    component.component_type = ComponentType.DATA
    component.status = ComponentStatus.STOPPED

    # 异步方法
    component.initialize = AsyncMock(return_value=None)
    component.start = AsyncMock(return_value=None)
    component.stop = AsyncMock(return_value=None)

    # 健康检查
    component.health_check = Mock(return_value=True)

    return component


# ==================== 事件 Fixtures ====================


@pytest.fixture
def sample_market_event():
    """示例市场数据事件"""
    from core.event.schema import Event, EventType

    return Event(
        type=EventType.MARKET_DATA,
        data={
            "symbol": "000001",
            "price": 10.5,
            "volume": 1000000,
            "timestamp": datetime.now().isoformat(),
        },
    )


@pytest.fixture
def sample_order_event():
    """示例订单事件"""
    from core.event.schema import Event, EventType

    return Event(
        type=EventType.ORDER,
        data={
            "order_id": "ORD123456",
            "symbol": "000001",
            "side": "buy",
            "quantity": 1000,
            "price": 10.5,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
        },
    )


@pytest.fixture
def sample_trade_event():
    """示例成交事件"""
    from core.event.schema import Event, EventType

    return Event(
        type=EventType.TRADE,
        data={
            "trade_id": "TRD123456",
            "order_id": "ORD123456",
            "symbol": "000001",
            "side": "buy",
            "quantity": 1000,
            "price": 10.5,
            "commission": 2.5,
            "timestamp": datetime.now().isoformat(),
        },
    )


# ==================== 数据库 Fixtures ====================


@pytest.fixture
async def mock_database():
    """模拟数据库连接"""
    db = AsyncMock()

    # 连接管理
    db.connect = AsyncMock(return_value=None)
    db.disconnect = AsyncMock(return_value=None)
    db.is_connected = Mock(return_value=True)

    # 查询执行
    db.execute = AsyncMock(return_value=None)
    db.fetch_one = AsyncMock(return_value={"id": 1, "name": "test"})
    db.fetch_all = AsyncMock(return_value=[{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}])

    # 事务管理
    db.begin = AsyncMock(return_value=None)
    db.commit = AsyncMock(return_value=None)
    db.rollback = AsyncMock(return_value=None)

    return db


# ==================== 缓存 Fixtures ====================


@pytest.fixture
async def mock_cache():
    """模拟缓存"""
    cache = AsyncMock()

    # 基础操作
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)

    # 批量操作
    cache.mget = AsyncMock(return_value=[None, None])
    cache.mset = AsyncMock(return_value=True)

    # TTL操作
    cache.expire = AsyncMock(return_value=True)
    cache.ttl = AsyncMock(return_value=-2)

    # 连接管理
    cache.ping = AsyncMock(return_value=True)
    cache.close = AsyncMock(return_value=None)

    return cache


# ==================== WebSocket Fixtures ====================


@pytest.fixture
def mock_websocket():
    """模拟WebSocket连接"""
    ws = AsyncMock()

    ws.accept = AsyncMock(return_value=None)
    ws.send_text = AsyncMock(return_value=None)
    ws.send_json = AsyncMock(return_value=None)
    ws.receive_text = AsyncMock(return_value='{"type": "ping"}')
    ws.receive_json = AsyncMock(return_value={"type": "ping"})
    ws.close = AsyncMock(return_value=None)

    return ws


# ==================== 测试数据生成器 ====================


def generate_random_quote(symbol: str = "000001") -> Dict[str, Any]:
    """生成随机行情数据"""
    import random

    base_price = 10.0 + random.random() * 5
    change = (random.random() - 0.5) * 0.5

    return {
        "symbol": symbol,
        "price": round(base_price, 2),
        "open": round(base_price - random.random() * 0.2, 2),
        "high": round(base_price + random.random() * 0.3, 2),
        "low": round(base_price - random.random() * 0.3, 2),
        "close": round(base_price, 2),
        "change": round(change, 2),
        "change_pct": round(change / base_price * 100, 2),
        "volume": random.randint(10000000, 200000000),
        "amount": random.randint(100000000, 2000000000),
        "timestamp": datetime.now().isoformat(),
    }


def generate_kline_series(
    symbol: str = "000001", days: int = 30, interval: str = "1d"
) -> List[Dict[str, Any]]:
    """生成K线序列数据"""
    import random

    klines = []
    base_price = 10.0
    base_date = datetime.now() - timedelta(days=days)

    for i in range(days):
        date = base_date + timedelta(days=i)

        # 随机波动
        open_price = base_price + (random.random() - 0.5) * 0.5
        close_price = open_price + (random.random() - 0.5) * 0.3
        high_price = max(open_price, close_price) + random.random() * 0.2
        low_price = min(open_price, close_price) - random.random() * 0.2

        klines.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": random.randint(50000000, 150000000),
                "amount": random.randint(500000000, 1500000000),
            }
        )

        # 下一天的基础价格
        base_price = close_price

    return klines


def generate_order_book(symbol: str = "000001", levels: int = 5) -> Dict[str, Any]:
    """生成订单簿数据"""
    import random

    base_price = 10.0
    spread = 0.01

    bids = []
    asks = []

    for i in range(levels):
        bid_price = base_price - spread * (i + 1)
        ask_price = base_price + spread * (i + 1)

        bids.append(
            {"price": round(bid_price, 2), "volume": random.randint(5000, 50000) * (levels - i)}
        )

        asks.append(
            {"price": round(ask_price, 2), "volume": random.randint(5000, 50000) * (levels - i)}
        )

    return {"symbol": symbol, "timestamp": datetime.now().isoformat(), "bids": bids, "asks": asks}


# ==================== 断言辅助函数 ====================


def assert_quote_valid(quote: Dict[str, Any]):
    """断言行情数据有效"""
    required_fields = ["symbol", "price", "volume"]
    for field in required_fields:
        assert field in quote, f"Missing required field: {field}"

    assert quote["price"] > 0, "Price must be positive"
    assert quote["volume"] >= 0, "Volume must be non-negative"


def assert_kline_valid(kline: Dict[str, Any]):
    """断言K线数据有效"""
    required_fields = ["date", "open", "high", "low", "close", "volume"]
    for field in required_fields:
        assert field in kline, f"Missing required field: {field}"

    assert kline["high"] >= kline["low"], "High must be >= Low"
    assert kline["high"] >= kline["open"], "High must be >= Open"
    assert kline["high"] >= kline["close"], "High must be >= Close"
    assert kline["low"] <= kline["open"], "Low must be <= Open"
    assert kline["low"] <= kline["close"], "Low must be <= Close"
    assert kline["volume"] >= 0, "Volume must be non-negative"


def assert_order_book_valid(order_book: Dict[str, Any]):
    """断言订单簿数据有效"""
    assert "bids" in order_book, "Missing bids"
    assert "asks" in order_book, "Missing asks"

    # 验证买单价格递减
    for i in range(1, len(order_book["bids"])):
        assert (
            order_book["bids"][i]["price"] < order_book["bids"][i - 1]["price"]
        ), "Bid prices must be decreasing"

    # 验证卖单价格递增
    for i in range(1, len(order_book["asks"])):
        assert (
            order_book["asks"][i]["price"] > order_book["asks"][i - 1]["price"]
        ), "Ask prices must be increasing"

    # 验证买一价低于卖一价
    if order_book["bids"] and order_book["asks"]:
        assert (
            order_book["bids"][0]["price"] < order_book["asks"][0]["price"]
        ), "Best bid must be lower than best ask"
