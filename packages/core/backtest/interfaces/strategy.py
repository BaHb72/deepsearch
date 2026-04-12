"""

BaseStrategy - 统一的策略基类

设计同时支持回测和实盘的策略框架

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Type, cast

from core.backtest.rules import AShareOrderConstraintInput, evaluate_a_share_order_constraints
from core.observability import get_logger
from core.strategies.interfaces.protocols import BacktestStrategy
from core.strategies.interfaces.types import (
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
from core.strategies.ttrading.backtest_blocked_reasons import get_blocked_reason_label

if TYPE_CHECKING:

    from backtrader import Strategy as BacktraderStrategyBase
    from core.event.engine.engine import EventEngine

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

        return {
            symbol: cast(StrategyPosition, position) for symbol, position in self.positions.items()
        }

    def _generate_order_id(self) -> str:
        """���ɶ���ID"""

        import uuid

        return f"{self.strategy_id}_{uuid.uuid4().hex[:8]}"

    def _send_order_event(self, order: StrategyOrder) -> None:
        """���Ͷ����¼���ʵ���ã�"""

        if not self.event_engine:

            return

        from core.event.engine.engine import Event

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

        from core.event.engine.engine import Event

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

                self._data_by_symbol: dict[str, Any] = {}
                self._last_bar_dt_by_symbol: dict[str, datetime] = {}
                self._strategy_to_bt_order_ref: dict[str, int] = {}
                self._bt_ref_to_strategy_order: dict[int, str] = {}
                self._intraday_bought_qty: dict[tuple[str, str], float] = defaultdict(float)
                self._blocked_summary: dict[str, int] = {}
                self._blocked_events: list[dict[str, object]] = []
                self._executed_trades: list[StrategyTrade] = []
                self._max_blocked_events = int(
                    self.deepsearch_strategy.params.get("max_blocked_events", 200) or 200
                )
                self._enforce_a_share_rules = bool(
                    self.deepsearch_strategy.params.get("enforce_a_share_rules", True)
                )
                self._index_data_feeds()

                # 调用策略初始化

                self.deepsearch_strategy.on_init()

            def start(self):
                """策略启动"""

                self.deepsearch_strategy.on_start()

            def next(self):
                """处理新的K线"""

                self._index_data_feeds()
                self._update_positions()
                active_trade_days: dict[str, str] = {}

                for data in self.datas:
                    symbol = self._resolve_data_symbol(data)
                    current_dt = data.datetime.datetime(0)
                    if self._last_bar_dt_by_symbol.get(symbol) == current_dt:
                        continue

                    self._last_bar_dt_by_symbol[symbol] = current_dt
                    active_trade_days[symbol] = current_dt.date().isoformat()

                    bar: MarketBarData = {
                        "symbol": symbol,
                        "datetime": current_dt,
                        "open": float(data.open[0]),
                        "high": float(data.high[0]),
                        "low": float(data.low[0]),
                        "close": float(data.close[0]),
                        "volume": float(data.volume[0]),
                    }

                    self.deepsearch_strategy.on_bar(bar)
                    self._process_strategy_orders()

                self._cleanup_intraday_bought(active_trade_days)
                self._persist_runtime_state()

            def notify_order(self, order):
                """订单通知"""

                size_value = float(order.size)

                executed_size = float(getattr(order.executed, "size", 0.0))

                remaining = max(size_value - executed_size, 0.0)

                info_getter = getattr(getattr(order, "info", {}), "get", None)
                order_type = (
                    info_getter("order_type", "UNKNOWN") if callable(info_getter) else "UNKNOWN"
                )

                order_symbol = getattr(getattr(order, "data", None), "_name", "")
                strategy_order_id = self._bt_ref_to_strategy_order.get(
                    int(order.ref), str(order.ref)
                )
                status = self._get_order_status(order)
                existing_order = dict(self.deepsearch_strategy.orders.get(strategy_order_id, {}))
                existing_metadata = dict(existing_order.get("metadata", {}))

                order_info: StrategyOrder = {
                    "id": strategy_order_id,
                    "order_id": strategy_order_id,
                    "strategy_id": self.deepsearch_strategy.strategy_id,
                    "symbol": order_symbol,
                    "side": "BUY" if order.isbuy() else "SELL",
                    "size": size_value,
                    "price": float(order.price) if order.price is not None else None,
                    "type": str(order_type),
                    "status": status,
                    "filled": executed_size,
                    "remaining": remaining,
                    "create_time": existing_order.get("create_time"),
                    "update_time": datetime.now(),
                    "metadata": {
                        **existing_metadata,
                        "bt_order_ref": int(order.ref),
                        "executed_price": float(getattr(order.executed, "price", 0.0) or 0.0),
                        "commission": float(getattr(order.executed, "comm", 0.0) or 0.0),
                    },
                }

                self.deepsearch_strategy.orders[strategy_order_id] = order_info
                self.deepsearch_strategy.on_order(order_info)

                if status in {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}:
                    self._strategy_to_bt_order_ref.pop(strategy_order_id, None)
                    self._bt_ref_to_strategy_order.pop(int(order.ref), None)

            def notify_trade(self, trade):
                """成交通知"""

                trade_order = getattr(trade, "order", None)

                bt_order_ref = int(getattr(trade_order, "ref", 0))
                strategy_order_id = self._bt_ref_to_strategy_order.get(
                    bt_order_ref, str(getattr(trade_order, "ref", ""))
                )

                trade_id = str(
                    getattr(
                        trade, "ref", strategy_order_id or f"trade_{datetime.now().timestamp():.0f}"
                    )
                )

                side = "BUY" if float(trade.size) >= 0 else "SELL"
                timestamp = datetime.now()
                symbol = getattr(trade.data, "_name", "")

                trade_info: StrategyTrade = {
                    "trade_id": trade_id,
                    "order_id": strategy_order_id,
                    "strategy_id": self.deepsearch_strategy.strategy_id,
                    "symbol": symbol,
                    "side": side,
                    "size": abs(float(trade.size)),
                    "price": float(trade.price),
                    "pnl": float(trade.pnl),
                    "fee": float(trade.commission or 0.0),
                    "timestamp": timestamp,
                    "metadata": {
                        "value": float(trade.value),
                        "pnl_comm": float(trade.pnlcomm),
                    },
                }
                trade_info["date"] = timestamp.isoformat()
                trade_info["action"] = side
                trade_info["commission"] = float(trade.commission or 0.0)

                self._executed_trades.append(trade_info)
                self.deepsearch_strategy.on_trade(trade_info)
                self._track_intraday_buy_qty(side=side, symbol=symbol, size=abs(float(trade.size)))
                self._persist_runtime_state()

            def stop(self):
                """策略停止"""

                self._persist_runtime_state()
                self.deepsearch_strategy.on_stop()

            def _update_positions(self):
                """更新持仓信息"""

                for data in self.datas:
                    symbol = self._resolve_data_symbol(data)
                    position = self.getposition(data)
                    current_price = float(data.close[0]) if len(data.close) else 0.0
                    position_size = float(getattr(position, "size", 0.0) or 0.0)
                    avg_price = float(getattr(position, "price", 0.0) or 0.0)
                    market_value = position_size * current_price
                    unrealized_pnl = (current_price - avg_price) * position_size
                    position_data: StrategyPosition = {
                        "symbol": symbol,
                        "size": position_size,
                        "avg_cost": avg_price,
                        "market_value": market_value,
                        "unrealized_pnl": unrealized_pnl,
                        "metadata": {
                            "pnl_comm": float(getattr(position, "pnlcomm", unrealized_pnl) or 0.0),
                        },
                        "last_update": datetime.now(),
                    }
                    self.deepsearch_strategy.positions[symbol] = position_data

            def _process_strategy_orders(self):
                """处理策略产生的订单"""

                for strategy_order_id, strategy_order in list(
                    self.deepsearch_strategy.orders.items()
                ):
                    status = str(strategy_order.get("status", "")).upper()
                    if status != "PENDING":
                        continue

                    symbol = str(strategy_order.get("symbol", "")).strip()
                    data_feed = self._data_by_symbol.get(symbol)
                    if data_feed is None:
                        self._reject_local_order(
                            strategy_order_id,
                            reason_code="unknown_symbol",
                            reason_message=f"未找到标的 {symbol} 对应的数据源",
                        )
                        continue

                    try:
                        size = float(strategy_order.get("size", 0.0))
                    except TypeError, ValueError:
                        size = 0.0
                    if size <= 0:
                        self._reject_local_order(
                            strategy_order_id,
                            reason_code="invalid_size",
                            reason_message="订单数量无效",
                        )
                        continue

                    side = str(strategy_order.get("side", "BUY")).upper()
                    order_type = str(strategy_order.get("type", "MARKET")).upper()
                    price_value = strategy_order.get("price")
                    try:
                        price = float(price_value) if price_value is not None else None
                    except TypeError, ValueError:
                        price = None

                    blocked_reason = self._check_a_share_constraints(
                        symbol=symbol,
                        side=side,
                        size=size,
                        data_feed=data_feed,
                    )
                    if blocked_reason is not None:
                        self._block_local_order(strategy_order_id, blocked_reason)
                        continue

                    bt_order = self._submit_bt_order(
                        data_feed=data_feed,
                        side=side,
                        size=size,
                        order_type=order_type,
                        price=price,
                    )
                    if bt_order is None:
                        self._reject_local_order(
                            strategy_order_id,
                            reason_code="submit_failed",
                            reason_message="Backtrader 下单失败",
                        )
                        continue

                    order_ref = int(bt_order.ref)
                    self._strategy_to_bt_order_ref[strategy_order_id] = order_ref
                    self._bt_ref_to_strategy_order[order_ref] = strategy_order_id
                    self._update_local_order(
                        strategy_order_id,
                        status="SUBMITTED",
                        metadata_updates={"bt_order_ref": order_ref, "order_type": order_type},
                    )
                self._persist_runtime_state()

            def _get_order_status(self, order):
                """获取订单状态"""

                if order.status == order.Submitted:

                    return "SUBMITTED"

                elif order.status == order.Accepted:

                    return "ACCEPTED"

                elif order.status == order.Partial:

                    return "PARTIAL"

                elif order.status == order.Completed:

                    return "FILLED"

                elif order.status == order.Canceled:

                    return "CANCELED"

                elif order.status == order.Expired:

                    return "EXPIRED"

                elif order.status == order.Rejected:

                    return "REJECTED"

                else:

                    return "UNKNOWN"

            def _resolve_data_symbol(self, data: Any) -> str:
                symbol = str(getattr(data, "_name", "")).strip()
                if symbol:
                    return symbol
                return f"DATA_{id(data)}"

            def _index_data_feeds(self) -> None:
                self._data_by_symbol = {
                    self._resolve_data_symbol(data): data for data in self.datas
                }

            def _cleanup_intraday_bought(self, active_trade_days: Mapping[str, str]) -> None:
                if not self._intraday_bought_qty:
                    return
                stale_keys = [
                    key
                    for key in self._intraday_bought_qty
                    if active_trade_days.get(key[0]) != key[1]
                ]
                for key in stale_keys:
                    self._intraday_bought_qty.pop(key, None)

            def _safe_numeric_line(self, data_feed: Any, line_name: str) -> float | None:
                line = getattr(data_feed, line_name, None)
                if line is None:
                    return None
                try:
                    raw_value = float(line[0])
                except Exception:
                    return None
                if raw_value != raw_value:  # NaN guard
                    return None
                return raw_value

            def _check_a_share_constraints(
                self,
                *,
                symbol: str,
                side: str,
                size: float,
                data_feed: Any,
            ) -> str | None:
                if not self._enforce_a_share_rules:
                    return None

                high_limited = self._safe_numeric_line(data_feed, "high_limited")
                low_limited = self._safe_numeric_line(data_feed, "low_limited")
                suspended_value = self._safe_numeric_line(data_feed, "is_suspended")
                is_suspended = bool(int(suspended_value)) if suspended_value is not None else False
                current_price = float(getattr(data_feed, "close")[0])
                position_size = float(self.getposition(data_feed).size)
                trade_day = data_feed.datetime.date(0).isoformat()
                intraday_bought_qty = float(self._intraday_bought_qty.get((symbol, trade_day), 0.0))

                constraint_input = AShareOrderConstraintInput(
                    symbol=symbol,
                    side=side,
                    size=size,
                    current_price=current_price,
                    position_size=position_size,
                    intraday_bought_qty=intraday_bought_qty,
                    high_limited=high_limited,
                    low_limited=low_limited,
                    is_suspended=is_suspended,
                )
                return evaluate_a_share_order_constraints(constraint_input)

            def _submit_bt_order(
                self,
                *,
                data_feed: Any,
                side: str,
                size: float,
                order_type: str,
                price: float | None,
            ) -> Any:
                order_type_upper = order_type.upper()
                try:
                    if side == "BUY":
                        if order_type_upper == "LIMIT" and price is not None:
                            return self.buy(
                                data=data_feed, size=size, price=price, exectype=bt.Order.Limit
                            )
                        if order_type_upper == "STOP" and price is not None:
                            return self.buy(
                                data=data_feed, size=size, price=price, exectype=bt.Order.Stop
                            )
                        return self.buy(data=data_feed, size=size)

                    if side == "SELL":
                        if order_type_upper == "LIMIT" and price is not None:
                            return self.sell(
                                data=data_feed, size=size, price=price, exectype=bt.Order.Limit
                            )
                        if order_type_upper == "STOP" and price is not None:
                            return self.sell(
                                data=data_feed, size=size, price=price, exectype=bt.Order.Stop
                            )
                        return self.sell(data=data_feed, size=size)
                except Exception as exc:
                    self.log(f"Backtrader 下单异常: {exc}", level="ERROR")
                return None

            def _update_local_order(
                self,
                strategy_order_id: str,
                *,
                status: str,
                metadata_updates: Mapping[str, object] | None = None,
            ) -> None:
                existing = dict(self.deepsearch_strategy.orders.get(strategy_order_id, {}))
                metadata = dict(existing.get("metadata", {}))
                if metadata_updates:
                    metadata.update(dict(metadata_updates))

                size_value = float(existing.get("size", 0.0) or 0.0)
                filled_value = float(existing.get("filled", 0.0) or 0.0)
                existing.update(
                    {
                        "id": strategy_order_id,
                        "order_id": strategy_order_id,
                        "status": status,
                        "filled": filled_value,
                        "remaining": max(size_value - filled_value, 0.0),
                        "update_time": datetime.now(),
                        "metadata": metadata,
                    }
                )
                typed_order = cast(StrategyOrder, existing)
                self.deepsearch_strategy.orders[strategy_order_id] = typed_order
                self.deepsearch_strategy.on_order(typed_order)

            def _reject_local_order(
                self,
                strategy_order_id: str,
                *,
                reason_code: str,
                reason_message: str,
            ) -> None:
                self._update_local_order(
                    strategy_order_id,
                    status="REJECTED",
                    metadata_updates={
                        "reason_code": reason_code,
                        "reason": reason_message,
                    },
                )

            def _block_local_order(self, strategy_order_id: str, reason_code: str) -> None:
                self._blocked_summary[reason_code] = self._blocked_summary.get(reason_code, 0) + 1
                if len(self._blocked_events) < self._max_blocked_events:
                    event_order = self.deepsearch_strategy.orders.get(strategy_order_id, {})
                    self._blocked_events.append(
                        {
                            "order_id": strategy_order_id,
                            "symbol": event_order.get("symbol"),
                            "side": event_order.get("side"),
                            "reason_code": reason_code,
                            "reason": get_blocked_reason_label(reason_code),
                            "time": datetime.now().isoformat(),
                        }
                    )
                self._update_local_order(
                    strategy_order_id,
                    status="REJECTED",
                    metadata_updates={
                        "reason_code": reason_code,
                        "reason": get_blocked_reason_label(reason_code),
                    },
                )

            def _track_intraday_buy_qty(self, *, side: str, symbol: str, size: float) -> None:
                if side != "BUY" or size <= 0:
                    return
                data_feed = self._data_by_symbol.get(symbol)
                if data_feed is None:
                    return
                trade_day = data_feed.datetime.date(0).isoformat()
                key = (symbol, trade_day)
                self._intraday_bought_qty[key] = self._intraday_bought_qty.get(key, 0.0) + size

            def _persist_runtime_state(self) -> None:
                self.deepsearch_strategy.data_cache["blocked_summary"] = dict(self._blocked_summary)
                self.deepsearch_strategy.data_cache["blocked_events"] = list(self._blocked_events)
                self.deepsearch_strategy.data_cache["executed_trades"] = list(self._executed_trades)

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
