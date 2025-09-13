"""
BaseStrategy - 统一的策略基类

设计同时支持回测和实盘的策略框架
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import backtrader as bt

    HAS_BACKTRADER = True
except ImportError:
    HAS_BACKTRADER = False
    bt = None


class BaseStrategy(ABC):
    """
    DeepSearch 统一策略基类
    
    这个基类定义了策略的标准接口，可以同时用于：
    1. Backtrader 回测
    2. 实盘交易（通过事件系统）
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        初始化策略
        
        Args:
            params: 策略参数字典
        """
        self.params = params or {}
        self.logger = logging.getLogger(f"strategy.{self.__class__.__name__}")
        self.positions = {}
        self.orders = {}
        self.is_backtest = False
        self.event_engine = None

    @abstractmethod
    def on_init(self):
        """策略初始化，设置指标等"""
        pass

    @abstractmethod
    def on_start(self):
        """策略启动时调用"""
        pass

    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]):
        """
        处理新的K线数据
        
        Args:
            bar: K线数据字典，包含 open, high, low, close, volume 等
        """
        pass

    @abstractmethod
    def on_tick(self, tick: Dict[str, Any]):
        """
        处理Tick数据
        
        Args:
            tick: Tick数据字典
        """
        pass

    @abstractmethod
    def on_order(self, order: Dict[str, Any]):
        """
        订单状态更新
        
        Args:
            order: 订单信息字典
        """
        pass

    @abstractmethod
    def on_trade(self, trade: Dict[str, Any]):
        """
        成交回报
        
        Args:
            trade: 成交信息字典
        """
        pass

    @abstractmethod
    def on_stop(self):
        """策略停止时调用"""
        pass

    def buy(self, symbol: str, size: float, price: Optional[float] = None,
            order_type: str = 'MARKET', **kwargs) -> str:
        """
        买入订单
        
        Args:
            symbol: 标的代码
            size: 数量
            price: 价格（限价单需要）
            order_type: 订单类型
            **kwargs: 其他参数
            
        Returns:
            str: 订单ID
        """
        order_id = self._generate_order_id()
        order = {
            'id': order_id,
            'symbol': symbol,
            'side': 'BUY',
            'size': size,
            'price': price,
            'type': order_type,
            'status': 'PENDING',
            'create_time': datetime.now(),
            **kwargs
        }

        if self.is_backtest:
            # 回测模式：直接返回订单ID，由回测引擎处理
            return order_id
        else:
            # 实盘模式：通过事件系统发送订单
            self._send_order_event(order)
            return order_id

    def sell(self, symbol: str, size: float, price: Optional[float] = None,
             order_type: str = 'MARKET', **kwargs) -> str:
        """
        卖出订单
        
        Args:
            symbol: 标的代码
            size: 数量
            price: 价格（限价单需要）
            order_type: 订单类型
            **kwargs: 其他参数
            
        Returns:
            str: 订单ID
        """
        order_id = self._generate_order_id()
        order = {
            'id': order_id,
            'symbol': symbol,
            'side': 'SELL',
            'size': size,
            'price': price,
            'type': order_type,
            'status': 'PENDING',
            'create_time': datetime.now(),
            **kwargs
        }

        if self.is_backtest:
            return order_id
        else:
            self._send_order_event(order)
            return order_id

    def cancel_order(self, order_id: str):
        """取消订单"""
        if self.is_backtest:
            pass  # 回测引擎处理
        else:
            self._send_cancel_event(order_id)

    def get_position(self, symbol: str) -> Dict[str, Any]:
        """获取持仓"""
        return self.positions.get(symbol, {
            'symbol': symbol,
            'size': 0,
            'avg_cost': 0,
            'market_value': 0,
            'pnl': 0
        })

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有持仓"""
        return self.positions.copy()

    def _generate_order_id(self) -> str:
        """生成订单ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    def _send_order_event(self, order: Dict[str, Any]):
        """发送订单事件（实盘用）"""
        if self.event_engine:
            from deepsearch.event.engine.engine import Event
            event = Event(
                type="ORDER_SUBMIT",
                data=order
            )
            self.event_engine.put(event)

    def _send_cancel_event(self, order_id: str):
        """发送取消订单事件（实盘用）"""
        if self.event_engine:
            from deepsearch.event.engine.engine import Event
            event = Event(
                type="ORDER_CANCEL",
                data={'order_id': order_id}
            )
            self.event_engine.put(event)

    def log(self, message: str, level: str = 'INFO'):
        """记录日志"""
        if level == 'DEBUG':
            self.logger.debug(message)
        elif level == 'INFO':
            self.logger.info(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        elif level == 'ERROR':
            self.logger.error(message)
        else:
            self.logger.info(message)


class BacktraderStrategyAdapter:
    """
    Backtrader 策略适配器
    
    将 DeepSearch 策略适配为 Backtrader 策略
    """

    @staticmethod
    def create_backtrader_strategy(base_strategy: BaseStrategy):
        """
        创建 Backtrader 策略类
        
        Args:
            base_strategy: DeepSearch 策略实例
            
        Returns:
            Backtrader 策略类
        """
        if not HAS_BACKTRADER:
            raise ImportError("请先安装 backtrader: pip install backtrader")

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
                bar = {
                    'datetime': self.datas[0].datetime.datetime(0),
                    'open': self.datas[0].open[0],
                    'high': self.datas[0].high[0],
                    'low': self.datas[0].low[0],
                    'close': self.datas[0].close[0],
                    'volume': self.datas[0].volume[0],
                }

                # 更新持仓信息
                self._update_positions()

                # 调用策略的 on_bar 方法
                self.deepsearch_strategy.on_bar(bar)

                # 处理策略产生的订单
                self._process_strategy_orders()

            def notify_order(self, order):
                """订单通知"""
                order_info = {
                    'id': order.ref,
                    'status': self._get_order_status(order),
                    'size': order.size,
                    'price': order.price,
                    'executed_size': order.executed.size,
                    'executed_price': order.executed.price,
                    'commission': order.executed.comm
                }

                self.deepsearch_strategy.on_order(order_info)

            def notify_trade(self, trade):
                """成交通知"""
                trade_info = {
                    'symbol': trade.data._name,
                    'size': trade.size,
                    'price': trade.price,
                    'value': trade.value,
                    'commission': trade.commission,
                    'pnl': trade.pnl,
                    'pnlcomm': trade.pnlcomm
                }

                self.deepsearch_strategy.on_trade(trade_info)

            def stop(self):
                """策略停止"""
                self.deepsearch_strategy.on_stop()

            def _update_positions(self):
                """更新持仓信息"""
                position = self.getposition(self.datas[0])
                if position:
                    self.deepsearch_strategy.positions[self.datas[0]._name] = {
                        'symbol': self.datas[0]._name,
                        'size': position.size,
                        'price': position.price,
                        'value': position.value,
                        'pnl': position.pnl,
                        'pnlcomm': position.pnlcomm
                    }

            def _process_strategy_orders(self):
                """处理策略产生的订单"""
                # 这里可以检查策略的 buy/sell 调用
                # 并转换为 Backtrader 订单
                pass

            def _get_order_status(self, order):
                """获取订单状态"""
                if order.status == order.Submitted:
                    return 'SUBMITTED'
                elif order.status == order.Accepted:
                    return 'ACCEPTED'
                elif order.status == order.Partial:
                    return 'PARTIAL'
                elif order.status == order.Completed:
                    return 'COMPLETED'
                elif order.status == order.Canceled:
                    return 'CANCELED'
                elif order.status == order.Expired:
                    return 'EXPIRED'
                elif order.status == order.Rejected:
                    return 'REJECTED'
                else:
                    return 'UNKNOWN'

        return BTStrategy


class SimpleMovingAverageStrategy(BaseStrategy):
    """
    简单移动平均线策略示例
    
    当短期均线上穿长期均线时买入
    当短期均线下穿长期均线时卖出
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)

        # 策略参数
        self.short_period = self.params.get('short_period', 10)
        self.long_period = self.params.get('long_period', 30)

        # 数据存储
        self.prices = []
        self.short_ma = []
        self.long_ma = []

        # 信号状态
        self.in_position = False

    def on_init(self):
        """初始化策略"""
        self.log(f"初始化 SMA 策略: 短期={self.short_period}, 长期={self.long_period}")

    def on_start(self):
        """策略启动"""
        self.log("SMA 策略启动")

    def on_bar(self, bar: Dict[str, Any]):
        """处理K线数据"""
        # 记录收盘价
        self.prices.append(bar['close'])

        # 计算移动平均线
        if len(self.prices) >= self.short_period:
            short_ma = sum(self.prices[-self.short_period:]) / self.short_period
            self.short_ma.append(short_ma)

        if len(self.prices) >= self.long_period:
            long_ma = sum(self.prices[-self.long_period:]) / self.long_period
            self.long_ma.append(long_ma)

        # 生成交易信号
        if len(self.short_ma) >= 2 and len(self.long_ma) >= 2:
            # 金叉：短期均线上穿长期均线
            if (self.short_ma[-2] <= self.long_ma[-2] and
                    self.short_ma[-1] > self.long_ma[-1] and
                    not self.in_position):

                self.log(f"金叉信号: 买入 @ {bar['close']}")
                self.buy('default', size=100)
                self.in_position = True

            # 死叉：短期均线下穿长期均线
            elif (self.short_ma[-2] >= self.long_ma[-2] and
                  self.short_ma[-1] < self.long_ma[-1] and
                  self.in_position):

                self.log(f"死叉信号: 卖出 @ {bar['close']}")
                self.sell('default', size=100)
                self.in_position = False

    def on_tick(self, tick: Dict[str, Any]):
        """处理Tick数据"""
        pass  # 该策略不使用tick数据

    def on_order(self, order: Dict[str, Any]):
        """处理订单更新"""
        self.log(f"订单更新: {order['id']} - {order['status']}")

    def on_trade(self, trade: Dict[str, Any]):
        """处理成交回报"""
        self.log(f"成交: {trade['size']} @ {trade['price']}, PnL: {trade.get('pnl', 0)}")

    def on_stop(self):
        """策略停止"""
        self.log("SMA 策略停止")
