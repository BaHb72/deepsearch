"""
Unit tests for domain entities.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from deepsearch.domain.entities.price import Price
from deepsearch.domain.entities.stock_simple import Stock
from deepsearch.domain.entities.trade import Order, OrderStatus, OrderType, Trade


class TestStock:
    """Test cases for Stock entity."""

    def test_create_stock_with_valid_data(self):
        """Test creating a stock with valid data."""
        stock = Stock(symbol="000001", name="平安银行", market="SZ", industry="银行", sector="金融")

        assert stock.symbol == "000001"
        assert stock.name == "平安银行"
        assert stock.market == "SZ"
        assert stock.industry == "银行"
        assert stock.sector == "金融"
        assert stock.is_trading is True

    def test_stock_halt_trading(self):
        """Test halting stock trading."""
        stock = Stock(symbol="000001", name="平安银行")

        stock.halt_trading("停牌维护")

        assert stock.is_trading is False
        assert stock.halt_reason == "停牌维护"

    def test_stock_resume_trading(self):
        """Test resuming stock trading."""
        stock = Stock(symbol="000001", name="平安银行")
        stock.halt_trading("停牌维护")

        stock.resume_trading()

        assert stock.is_trading is True
        assert stock.halt_reason is None

    def test_stock_update_price(self):
        """Test updating stock price."""
        stock = Stock(symbol="000001", name="平安银行")

        new_price = Price(
            current=Decimal("10.50"),
            previous_close=Decimal("10.00"),
            open=Decimal("10.10"),
            high=Decimal("10.80"),
            low=Decimal("10.00"),
        )

        stock.update_price(new_price)

        assert stock.current_price == new_price
        assert stock.last_updated is not None

    def test_stock_equality(self):
        """Test stock entity equality."""
        stock1 = Stock(symbol="000001", name="平安银行")
        stock2 = Stock(symbol="000001", name="平安银行")
        stock3 = Stock(symbol="000002", name="万科A")

        assert stock1 == stock2
        assert stock1 != stock3


class TestPrice:
    """Test cases for Price value object."""

    def test_create_price_with_valid_data(self):
        """Test creating a price with valid data."""
        price = Price(
            current=Decimal("10.50"),
            previous_close=Decimal("10.00"),
            open=Decimal("10.10"),
            high=Decimal("10.80"),
            low=Decimal("10.00"),
            volume=1000000,
            turnover=Decimal("10500000"),
        )

        assert price.current == Decimal("10.50")
        assert price.volume == 1000000

    def test_price_change_calculation(self):
        """Test price change calculation."""
        price = Price(current=Decimal("10.50"), previous_close=Decimal("10.00"))

        change = price.calculate_change()

        assert change.amount == Decimal("0.50")
        assert change.percentage == Decimal("5.00")
        assert change.is_up is True

    def test_price_change_down(self):
        """Test price change when price goes down."""
        price = Price(current=Decimal("9.50"), previous_close=Decimal("10.00"))

        change = price.calculate_change()

        assert change.amount == Decimal("-0.50")
        assert change.percentage == Decimal("-5.00")
        assert change.is_down is True

    def test_price_change_unchanged(self):
        """Test price change when price is unchanged."""
        price = Price(current=Decimal("10.00"), previous_close=Decimal("10.00"))

        change = price.calculate_change()

        assert change.amount == Decimal("0.00")
        assert change.percentage == Decimal("0.00")
        assert change.is_unchanged is True

    def test_price_validation(self):
        """Test price validation."""
        with pytest.raises(ValueError, match="Current price must be positive"):
            Price(current=Decimal("-1.00"))

        with pytest.raises(ValueError, match="Volume must be non-negative"):
            Price(current=Decimal("10.00"), volume=-100)


class TestTrade:
    """Test cases for Trade entity."""

    def test_create_trade_with_valid_data(self):
        """Test creating a trade with valid data."""
        trade = Trade(
            id="T20250913001",
            symbol="000001",
            price=Decimal("10.50"),
            volume=1000,
            trade_type="BUY",
            timestamp=datetime.now(),
        )

        assert trade.id == "T20250913001"
        assert trade.symbol == "000001"
        assert trade.price == Decimal("10.50")
        assert trade.volume == 1000
        assert trade.trade_type == "BUY"
        assert trade.total_value == Decimal("10500.00")

    def test_trade_total_value_calculation(self):
        """Test trade total value calculation."""
        trade = Trade(symbol="000001", price=Decimal("10.50"), volume=2000)

        assert trade.total_value == Decimal("21000.00")

    def test_trade_with_commission(self):
        """Test trade with commission."""
        trade = Trade(
            symbol="000001", price=Decimal("10.00"), volume=1000, commission=Decimal("5.00")
        )

        assert trade.commission == Decimal("5.00")
        assert trade.net_value == Decimal("10005.00")  # Total + commission for buy


class TestOrder:
    """Test cases for Order entity."""

    def test_create_order_with_valid_data(self):
        """Test creating an order with valid data."""
        order = Order(
            id="O20250913001",
            symbol="000001",
            order_type=OrderType.LIMIT,
            side="BUY",
            price=Decimal("10.00"),
            volume=1000,
            status=OrderStatus.PENDING,
        )

        assert order.id == "O20250913001"
        assert order.order_type == OrderType.LIMIT
        assert order.status == OrderStatus.PENDING

    def test_order_fill(self):
        """Test order fill."""
        order = Order(
            symbol="000001",
            order_type=OrderType.LIMIT,
            price=Decimal("10.00"),
            volume=1000,
            status=OrderStatus.PENDING,
        )

        order.fill(filled_price=Decimal("10.00"), filled_volume=1000)

        assert order.status == OrderStatus.FILLED
        assert order.filled_price == Decimal("10.00")
        assert order.filled_volume == 1000

    def test_order_partial_fill(self):
        """Test order partial fill."""
        order = Order(
            symbol="000001", price=Decimal("10.00"), volume=1000, status=OrderStatus.PENDING
        )

        order.partial_fill(filled_volume=500)

        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_volume == 500

    def test_order_cancel(self):
        """Test order cancellation."""
        order = Order(
            symbol="000001", price=Decimal("10.00"), volume=1000, status=OrderStatus.PENDING
        )

        order.cancel()

        assert order.status == OrderStatus.CANCELLED

    def test_order_validation(self):
        """Test order validation."""
        with pytest.raises(ValueError, match="Order price must be positive"):
            Order(symbol="000001", price=Decimal("-10.00"), volume=1000)

        with pytest.raises(ValueError, match="Order volume must be positive"):
            Order(symbol="000001", price=Decimal("10.00"), volume=0)
