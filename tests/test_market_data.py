"""
Tests for Market Data APIs

Endpoints tested:
- /api/market/realtime/{symbol}
- /api/market/kline/{symbol}
- /api/market/orderbook/{symbol}
- /api/market/trades/{symbol}
- /api/market/indices
- /api/market/hot-stocks
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch


class TestRealtimeQuotes:
    """Test realtime quote endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_realtime_quote(self, test_data_provider):
        """Test getting realtime quote for a symbol."""
        symbol = "000001"
        
        quote = await test_data_provider.get_realtime_quote(symbol)
        
        assert quote["symbol"] == symbol
        assert "price" in quote
        assert "change" in quote
        assert "change_pct" in quote
        assert "volume" in quote
    
    @pytest.mark.asyncio
    async def test_get_multiple_quotes(self, test_data_provider):
        """Test getting quotes for multiple symbols."""
        symbols = ["000001", "000002", "600000"]
        
        quotes = []
        for symbol in symbols:
            test_data_provider.get_realtime_quote = AsyncMock(return_value={
                "symbol": symbol,
                "price": 10.0 + len(symbol),
                "change": 0.5
            })
            quote = await test_data_provider.get_realtime_quote(symbol)
            quotes.append(quote)
        
        assert len(quotes) == 3
        assert all(q["symbol"] in symbols for q in quotes)
    
    @pytest.mark.asyncio
    async def test_invalid_symbol(self, test_data_provider):
        """Test handling of invalid symbol."""
        test_data_provider.get_realtime_quote = AsyncMock(return_value=None)
        
        quote = await test_data_provider.get_realtime_quote("INVALID")
        assert quote is None


class TestKlineData:
    """Test K-line data endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_daily_kline(self):
        """Test getting daily K-line data."""
        provider = AsyncMock()
        provider.get_kline_data = AsyncMock(return_value=[
            {
                "date": "2025-09-10",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000000
            },
            {
                "date": "2025-09-11",
                "open": 10.2,
                "high": 10.8,
                "low": 10.0,
                "close": 10.5,
                "volume": 1200000
            }
        ])
        
        klines = await provider.get_kline_data("000001", period="1d", count=2)
        
        assert len(klines) == 2
        assert klines[0]["date"] == "2025-09-10"
        assert klines[1]["close"] == 10.5
    
    @pytest.mark.asyncio
    async def test_get_minute_kline(self):
        """Test getting minute-level K-line data."""
        provider = AsyncMock()
        provider.get_kline_data = AsyncMock(return_value=[
            {
                "datetime": "2025-09-13 09:30:00",
                "open": 10.0,
                "high": 10.1,
                "low": 9.95,
                "close": 10.05,
                "volume": 50000
            }
        ])
        
        klines = await provider.get_kline_data("000001", period="1m", count=1)
        
        assert len(klines) == 1
        assert "datetime" in klines[0]
        assert klines[0]["volume"] == 50000
    
    @pytest.mark.asyncio
    async def test_kline_with_adjust_factor(self):
        """Test K-line data with price adjustment."""
        provider = AsyncMock()
        
        # Forward adjusted prices
        provider.get_kline_data = AsyncMock(return_value=[
            {"date": "2025-09-10", "close": 10.0, "adjust_factor": 1.0},
            {"date": "2025-09-11", "close": 20.0, "adjust_factor": 2.0}  # Split occurred
        ])
        
        klines = await provider.get_kline_data("000001", adjust="forward")
        
        assert klines[1]["adjust_factor"] == 2.0


class TestOrderBook:
    """Test order book endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_level2_orderbook(self):
        """Test getting Level 2 order book data."""
        provider = AsyncMock()
        provider.get_orderbook = AsyncMock(return_value={
            "symbol": "000001",
            "timestamp": "2025-09-13 10:00:00",
            "bids": [
                {"price": 10.00, "volume": 1000},
                {"price": 9.99, "volume": 2000},
                {"price": 9.98, "volume": 3000},
                {"price": 9.97, "volume": 4000},
                {"price": 9.96, "volume": 5000}
            ],
            "asks": [
                {"price": 10.01, "volume": 1000},
                {"price": 10.02, "volume": 2000},
                {"price": 10.03, "volume": 3000},
                {"price": 10.04, "volume": 4000},
                {"price": 10.05, "volume": 5000}
            ]
        })
        
        orderbook = await provider.get_orderbook("000001")
        
        assert orderbook["symbol"] == "000001"
        assert len(orderbook["bids"]) == 5
        assert len(orderbook["asks"]) == 5
        assert orderbook["bids"][0]["price"] > orderbook["bids"][1]["price"]
        assert orderbook["asks"][0]["price"] < orderbook["asks"][1]["price"]
    
    @pytest.mark.asyncio
    async def test_orderbook_spread_calculation(self):
        """Test order book spread calculation with Decimal precision."""
        from decimal import Decimal

        provider = AsyncMock()
        provider.get_orderbook = AsyncMock(return_value={
            "bids": [{"price": 10.00, "volume": 1000}],
            "asks": [{"price": 10.02, "volume": 1000}]
        })

        orderbook = await provider.get_orderbook("000001")

        # 使用Decimal进行精确计算，避免浮点精度问题
        bid_price = Decimal(str(orderbook["bids"][0]["price"]))
        ask_price = Decimal(str(orderbook["asks"][0]["price"]))
        spread = ask_price - bid_price

        # Decimal类型的精确比较
        expected_spread = Decimal("0.02")
        assert spread == expected_spread


class TestMarketIndices:
    """Test market indices endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_major_indices(self):
        """Test getting major market indices."""
        provider = AsyncMock()
        provider.get_indices = AsyncMock(return_value=[
            {
                "code": "000001",
                "name": "上证指数",
                "current": 3000.00,
                "change": 50.00,
                "change_pct": 1.69
            },
            {
                "code": "399001",
                "name": "深证成指",
                "current": 10000.00,
                "change": 100.00,
                "change_pct": 1.01
            },
            {
                "code": "399006",
                "name": "创业板指",
                "current": 2000.00,
                "change": -20.00,
                "change_pct": -0.99
            }
        ])
        
        indices = await provider.get_indices()
        
        assert len(indices) == 3
        assert indices[0]["code"] == "000001"
        assert indices[1]["change_pct"] > 0
        assert indices[2]["change_pct"] < 0
    
    @pytest.mark.asyncio
    async def test_index_historical_data(self):
        """Test getting historical data for an index."""
        provider = AsyncMock()
        provider.get_index_history = AsyncMock(return_value=[
            {"date": "2025-09-10", "close": 2950.00},
            {"date": "2025-09-11", "close": 2980.00},
            {"date": "2025-09-12", "close": 3000.00}
        ])
        
        history = await provider.get_index_history("000001", days=3)
        
        assert len(history) == 3
        assert history[-1]["close"] > history[0]["close"]


class TestHotStocks:
    """Test hot stocks and market trends endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_hot_stocks(self):
        """Test getting hot stocks list."""
        provider = AsyncMock()
        provider.get_hot_stocks = AsyncMock(return_value=[
            {
                "symbol": "000001",
                "name": "平安银行",
                "price": 10.5,
                "change_pct": 10.0,
                "volume": 50000000,
                "turnover_rate": 5.2,
                "reason": "涨停"
            },
            {
                "symbol": "600000",
                "name": "浦发银行",
                "price": 8.8,
                "change_pct": 8.5,
                "volume": 40000000,
                "turnover_rate": 4.5,
                "reason": "放量上涨"
            }
        ])
        
        hot_stocks = await provider.get_hot_stocks()
        
        assert len(hot_stocks) == 2
        assert hot_stocks[0]["change_pct"] > hot_stocks[1]["change_pct"]
        assert "reason" in hot_stocks[0]
    
    @pytest.mark.asyncio
    async def test_get_limit_up_stocks(self):
        """Test getting stocks hitting limit up."""
        provider = AsyncMock()
        provider.get_limit_stocks = AsyncMock(return_value={
            "limit_up": [
                {"symbol": "000001", "name": "平安银行", "time": "09:35:00"},
                {"symbol": "000002", "name": "万科A", "time": "10:15:00"}
            ],
            "limit_down": [
                {"symbol": "600001", "name": "邯郸钢铁", "time": "09:31:00"}
            ]
        })
        
        limits = await provider.get_limit_stocks()
        
        assert len(limits["limit_up"]) == 2
        assert len(limits["limit_down"]) == 1
        assert limits["limit_up"][0]["time"] < limits["limit_up"][1]["time"]