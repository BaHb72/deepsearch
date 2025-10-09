"""

BaseStrategy - 统一的策略基类

设计同时支持回测和实盘的策略框架

"""

from __future__ import annotations

from abc import ABC, abstractmethod

from dataclasses import dataclass

from datetime import datetime

from logging import Logger

from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING, Type, cast

from deepsearch.observability import get_logger

from deepsearch.strategies.interfaces.protocols import BacktestStrategy

from deepsearch.strategies.interfaces.types import (

    MarketBarData,

    StrategyBusEnvelope,

    StrategyCancelPayload,

    StrategyDataCache,

    StrategyMetrics,

    StrategyOrder,

    StrategyParams,

    StrategyPosition,

    StrategyTrade,

    TickData,

)

if TYPE_CHECKING:

    from backtrader import Cerebro, Strategy as BacktraderStrategyBase

    from deepsearch.event.engine.engine import EventEngine

bt: Any

try:

    import backtrader as _backtrader

    HAS_BACKTRADER = True

    bt = _backtrader

except ImportError:

    HAS_BACKTRADER = False

    bt = None

def _default_metrics() -> "StrategyMetrics":

    """����Ĭ�ϵĲ������ݱ�׼ָ��."""

    return {

        "total_trades": 0,

        "winning_trades": 0,

        "losing_trades": 0,

        "total_pnl": 0.0,

        "max_drawdown": 0.0,

        "sharpe_ratio": 0.0,

    }

@dataclass(init=False)

class BaseStrategy(ABC):

    """

    DeepSearch 统一策略基类

    这个基类定义了策略的标准接口，可以同时用于：

    1. Backtrader 回测

    2. 实盘交易（通过事件系统）

    """

    strategy_id: str

    params: StrategyParams

    logger: Logger

    positions: Dict[str, StrategyPosition]

    orders: Dict[str, StrategyOrder]

    metrics: "StrategyMetrics"

    data_cache: "StrategyDataCache"

    is_backtest: bool

    event_engine: "EventEngine | None"

    def __init__(

        self,

        params: Optional[StrategyParams] = None,

        *,

        strategy_id: Optional[str] = None,

    ) -> None:

        """

        ��ʼ������

        Args:

            params: ���Գ��������ֵ�

            strategy_id: ������ʶ����Ϊ�ձ�����ʹ���ඨ����

        """

        self.strategy_id = strategy_id or self.__class__.__name__

        self.params = dict(params or {})

        self.logger = get_logger(f"strategy.{self.strategy_id}")

        self.positions = cast(Dict[str, StrategyPosition], {})

        self.orders = cast(Dict[str, StrategyOrder], {})

        self.metrics = _default_metrics()

        self.data_cache = cast(StrategyDataCache, {})

        self.is_backtest = False

        self.event_engine = None

    @abstractmethod

    def on_init(self) -> None:

        """策略初始化，设置指标等"""

        pass

    @abstractmethod

    def on_start(self) -> None:

        """策略启动时调用"""

        pass

    @abstractmethod

    def on_bar(self, bar: MarketBarData) -> None:

        """处理K线数据"""

        raise NotImplementedError

    def on_tick(self, tick: TickData) -> None:

        """

        处理Tick数据

        Args:

            tick: Tick数据字典

        """

        pass

    @abstractmethod

    def on_order(self, order: StrategyOrder) -> None:

        """

        订单状态更新

        Args:

            order: 订单信息字典

        """

        pass

    @abstractmethod

    def on_trade(self, trade: StrategyTrade) -> None:

        """

        成交回报

        Args:

            trade: 成交信息字典

        """

        pass

    @abstractmethod

    def on_stop(self) -> None:

        """策略停止时调用"""

        pass

    def buy(

        self,

        symbol: str,

        size: float,

        price: Optional[float] = None,

        order_type: str = "MARKET",

        **kwargs: object,

    ) -> str:

        """

        ���붩��

        Args:

            symbol: ��Ĵ���

            size: ����

            price: �۸��޼۵���Ҫ��

            order_type: ��������

            **kwargs: ��������

        Returns:

            str: ����ID

        """

        size_value = float(size)

        order_id = self._generate_order_id()

        order: StrategyOrder = {

            "id": order_id,

            "order_id": order_id,

            "strategy_id": self.strategy_id,

            "symbol": symbol,

            "side": "BUY",

            "size": size_value,

            "price": price,

            "type": order_type,

            "status": "PENDING",

            "create_time": datetime.now(),

            "filled": 0.0,

            "remaining": size_value,

        }

        extra_kwargs: Dict[str, object] = dict(kwargs)

        metadata_obj = extra_kwargs.pop("metadata", None)

        if metadata_obj is not None:

            if isinstance(metadata_obj, Mapping):

                order["metadata"] = dict(metadata_obj)

            else:

                order["metadata"] = {"extra": metadata_obj}

        if extra_kwargs:

            extra_meta = dict(order.get("metadata", {}))

            extra_meta.update(extra_kwargs)

            order["metadata"] = extra_meta

        self.orders[order_id] = order

        if not self.is_backtest:

            self._send_order_event(order)

        return order_id

    def sell(

        self,

        symbol: str,

        size: float,

        price: Optional[float] = None,

        order_type: str = "MARKET",

        **kwargs: object,

    ) -> str:

        """

        ��������

        Args:

            symbol: ��Ĵ���

            size: ����

            price: �۸��޼۵���Ҫ��

            order_type: ��������

            **kwargs: ��������

        Returns:

            str: ����ID

        """

        size_value = float(size)

        order_id = self._generate_order_id()

        order: StrategyOrder = {

            "id": order_id,

            "order_id": order_id,

            "strategy_id": self.strategy_id,

            "symbol": symbol,

            "side": "SELL",

            "size": size_value,

            "price": price,

            "type": order_type,

            "status": "PENDING",

            "create_time": datetime.now(),

            "filled": 0.0,

            "remaining": size_value,

        }

        extra_kwargs: Dict[str, object] = dict(kwargs)

        metadata_obj = extra_kwargs.pop("metadata", None)

        if metadata_obj is not None:

            if isinstance(metadata_obj, Mapping):

                order["metadata"] = dict(metadata_obj)

            else:

                order["metadata"] = {"extra": metadata_obj}

        if extra_kwargs:

            extra_meta = dict(order.get("metadata", {}))

            extra_meta.update(extra_kwargs)

            order["metadata"] = extra_meta

        self.orders[order_id] = order

        if not self.is_backtest:

            self._send_order_event(order)

        return order_id

    def cancel_order(self, order_id: str) -> None:

        """ȡ������"""

        if self.is_backtest:

            return

        self._send_cancel_event(order_id)

    def get_position(self, symbol: str) -> StrategyPosition:

        """��ȡ�ֲ�"""

        default_position: StrategyPosition = {

            "symbol": symbol,

            "size": 0.0,

            "avg_cost": 0.0,

            "market_value": 0.0,

            "unrealized_pnl": 0.0,

            "realized_pnl": 0.0,

        }

        return cast(StrategyPosition, self.positions.get(symbol, default_position))

    def get_all_positions(self) -> Dict[str, StrategyPosition]:

        """��ȡ���гֲ�"""

        return {symbol: cast(StrategyPosition, position) for symbol, position in self.positions.items()}

    def _generate_order_id(self) -> str:

        """���ɶ���ID"""

        import uuid

        return f"{self.strategy_id}_{uuid.uuid4().hex[:8]}"

    def _send_order_event(self, order: StrategyOrder) -> None:

        """���Ͷ����¼���ʵ���ã�"""

        if not self.event_engine:

            return

        from deepsearch.event.engine.engine import Event

        envelope: StrategyBusEnvelope = {

            "topic": f"strategy.{self.strategy_id}.orders",

            "type": "STRATEGY_ORDER_SUBMIT",

            "timestamp": datetime.now().timestamp(),

            "payload": order,

            "metadata": {"source": "backtest" if self.is_backtest else "live"},

            "headers": {"strategy_id": self.strategy_id},

        }

        self.event_engine.put(Event(type="STRATEGY_ORDER_SUBMIT", data=envelope))

    def _send_cancel_event(self, order_id: str) -> None:

        """����ȡ�������¼���ʵ���ã�"""

        if not self.event_engine:

            return

        from deepsearch.event.engine.engine import Event

        payload: StrategyCancelPayload = {"order_id": order_id, "strategy_id": self.strategy_id}

        envelope: StrategyBusEnvelope = {

            "topic": f"strategy.{self.strategy_id}.orders",

            "type": "STRATEGY_ORDER_CANCEL",

            "timestamp": datetime.now().timestamp(),

            "payload": payload,

            "headers": {"strategy_id": self.strategy_id},

            "metadata": {"source": "backtest" if self.is_backtest else "live"},

        }

        self.event_engine.put(Event(type="STRATEGY_ORDER_CANCEL", data=envelope))

    def log(self, message: str, level: str = "INFO") -> None:

        """记录日志"""

        if level == "DEBUG":

            self.logger.debug(message)

        elif level == "INFO":

            self.logger.info(message)

        elif level == "WARNING":

            self.logger.warning(message)

        elif level == "ERROR":

            self.logger.error(message)

        else:

            self.logger.info(message)

class BacktraderStrategyAdapter:

    """

    Backtrader 策略适配器

    将 DeepSearch 策略适配为 Backtrader 策略

    """

    @staticmethod

    def create_backtrader_strategy(

        base_strategy: BacktestStrategy,

    ) -> "Type[BacktraderStrategyBase]":

        """

        创建 Backtrader 策略类

        Args:

            base_strategy: DeepSearch 策略实例

        Returns:

            Backtrader 策略类

        """

        if not HAS_BACKTRADER:

            raise ImportError("请先安装 backtrader: pip install backtrader")

        assert bt is not None

        class BTStrategy(bt.Strategy):

            """动态生成的 Backtrader 策略"""

            def __init__(self):

                super().__init__()

                self.deepsearch_strategy = base_strategy

                self.deepsearch_strategy.is_backtest = True

                # 调用策略初始化

                self.deepsearch_strategy.on_init()

            def start(self):

                """策略启动"""

                self.deepsearch_strategy.on_start()

            def next(self):

                """处理新的K线"""

                # 构造K线数据字典

                bar: MarketBarData = {

                    "symbol": self.datas[0]._name,

                    "datetime": self.datas[0].datetime.datetime(0),

                    "open": float(self.datas[0].open[0]),

                    "high": float(self.datas[0].high[0]),

                    "low": float(self.datas[0].low[0]),

                    "close": float(self.datas[0].close[0]),

                    "volume": float(self.datas[0].volume[0]),

                }

                # 更新持仓信息

                self._update_positions()

                # 调用策略的 on_bar 方法

                self.deepsearch_strategy.on_bar(bar)

                # 处理策略产生的订单

                self._process_strategy_orders()

            def notify_order(self, order):

                """订单通知"""

                size_value = float(order.size)

                executed_size = float(getattr(order.executed, "size", 0.0))

                remaining = max(size_value - executed_size, 0.0)

                order_type = getattr(getattr(order, "info", {}), "get", lambda *args, **kwargs: "UNKNOWN")("order_type", "UNKNOWN")

                order_symbol = getattr(getattr(order, "data", None), "_name", "")

                order_info: StrategyOrder = {

                    "id": str(order.ref),

                    "order_id": str(order.ref),

                    "strategy_id": self.deepsearch_strategy.strategy_id,

                    "symbol": order_symbol,

                    "side": "BUY" if order.isbuy() else "SELL",

                    "size": size_value,

                    "price": float(order.price) if order.price is not None else None,

                    "type": str(order_type),

                    "status": self._get_order_status(order),

                    "filled": executed_size,

                    "remaining": remaining,

                    "update_time": datetime.now(),

                    "metadata": {

                        "executed_price": float(getattr(order.executed, "price", 0.0) or 0.0),

                        "commission": float(getattr(order.executed, "comm", 0.0) or 0.0),

                    },

                }

                self.deepsearch_strategy.on_order(order_info)

            def notify_trade(self, trade):

                """成交通知"""

                trade_order = getattr(trade, "order", None)

                order_id = str(getattr(trade_order, "ref", ""))

                trade_id = str(getattr(trade, "ref", order_id or f"trade_{datetime.now().timestamp():.0f}"))

                side = "BUY" if float(trade.size) >= 0 else "SELL"

                trade_info: StrategyTrade = {

                    "trade_id": trade_id,

                    "order_id": order_id,

                    "strategy_id": self.deepsearch_strategy.strategy_id,

                    "symbol": getattr(trade.data, "_name", ""),

                    "side": side,

                    "size": abs(float(trade.size)),

                    "price": float(trade.price),

                    "pnl": float(trade.pnl),

                    "fee": float(trade.commission or 0.0),

                    "timestamp": datetime.now(),

                    "metadata": {

                        "value": float(trade.value),

                        "pnl_comm": float(trade.pnlcomm),

                    },

                }

                self.deepsearch_strategy.on_trade(trade_info)

            def stop(self):

                """策略停止"""

                self.deepsearch_strategy.on_stop()

            def _update_positions(self):

                """更新持仓信息"""

                position = self.getposition(self.datas[0])

                if position:

                    position_data: StrategyPosition = {

                        "symbol": self.datas[0]._name,

                        "size": float(position.size),

                        "avg_cost": float(position.price),

                        "market_value": float(position.value),

                        "unrealized_pnl": float(position.pnl),

                        "metadata": {

                            "pnl_comm": float(position.pnlcomm),

                        },

                        "last_update": datetime.now(),

                    }

                    self.deepsearch_strategy.positions[self.datas[0]._name] = position_data

            def _process_strategy_orders(self):

                """处理策略产生的订单"""

                # 这里可以检查策略的 buy/sell 调用

                # 并转换为 Backtrader 订单

                pass

            def _get_order_status(self, order):

                """获取订单状态"""

                if order.status == order.Submitted:

                    return "SUBMITTED"

                elif order.status == order.Accepted:

                    return "ACCEPTED"

                elif order.status == order.Partial:

                    return "PARTIAL"

                elif order.status == order.Completed:

                    return "COMPLETED"

                elif order.status == order.Canceled:

                    return "CANCELED"

                elif order.status == order.Expired:

                    return "EXPIRED"

                elif order.status == order.Rejected:

                    return "REJECTED"

                else:

                    return "UNKNOWN"

        return BTStrategy

class SimpleMovingAverageStrategy(BaseStrategy):

    """

    ���ƶ�ƽ���߲���ʾ��

    �����ھ����ϴ����ھ���ʱ����

    �����ھ����´����ھ���ʱ����

    """

    def __init__(self, params: Optional[StrategyParams] = None):

        super().__init__(params)

        # ���Բ���

        self.short_period: int = self._coerce_period(self.params.get("short_period"), 10)

        self.long_period: int = self._coerce_period(self.params.get("long_period"), 30)

        self.params["short_period"] = self.short_period

        self.params["long_period"] = self.long_period

        # ���ݴ洢

        self.prices: List[float] = []

        self.short_ma: List[float] = []

        self.long_ma: List[float] = []

        # �ź�״̬

        self.in_position: bool = False

    @staticmethod

    def _coerce_period(value: Optional[object], default: int) -> int:

        """ʹ�����ֶ�������������ȷ�����."""

        if isinstance(value, bool):

            return default

        if isinstance(value, (int, float)):

            candidate = int(value)

        elif isinstance(value, str):

            try:

                candidate = int(float(value))

            except ValueError:

                return default

        else:

            return default

        return candidate if candidate > 0 else default

    def on_init(self) -> None:

        """初始化策略"""

        self.log(f"初始化 SMA 策略: 短期={self.short_period}, 长期={self.long_period}")

    def on_start(self) -> None:

        """策略启动"""

        self.log("SMA 策略启动")

    def on_bar(self, bar: MarketBarData) -> None:

        """����K������"""

        close_value = bar.get("close")

        if close_value is None:

            return

        close_price = float(close_value)

        self.prices.append(close_price)

        if len(self.prices) >= self.short_period:

            short_ma = sum(self.prices[-self.short_period :]) / self.short_period

            self.short_ma.append(short_ma)

        if len(self.prices) >= self.long_period:

            long_ma = sum(self.prices[-self.long_period :]) / self.long_period

            self.long_ma.append(long_ma)

        if len(self.short_ma) >= 2 and len(self.long_ma) >= 2:

            if (

                self.short_ma[-2] <= self.long_ma[-2]

                and self.short_ma[-1] > self.long_ma[-1]

                and not self.in_position

            ):

                self.log(f"����ź�: ���� @ {close_price}")

                self.buy(bar.get("symbol", "default") or "default", size=100)

                self.in_position = True

            elif (

                self.short_ma[-2] >= self.long_ma[-2]

                and self.short_ma[-1] < self.long_ma[-1]

                and self.in_position

            ):

                self.log(f"�����ź�: ���� @ {close_price}")

                self.sell(bar.get("symbol", "default") or "default", size=100)

                self.in_position = False

    def on_tick(self, tick: TickData) -> None:

        """处理Tick数据"""

        pass  # 该策略不使用tick数据

    def on_order(self, order: StrategyOrder) -> None:

        """处理订单更新"""

        self.log(f"订单更新: {order['id']} - {order['status']}")

    def on_trade(self, trade: StrategyTrade) -> None:

        """处理成交回报"""

        self.log(f"成交: {trade['size']} @ {trade['price']}, PnL: {trade.get('pnl', 0)}")

    def on_stop(self) -> None:

        """策略停止"""

        self.log("SMA 策略停止")

