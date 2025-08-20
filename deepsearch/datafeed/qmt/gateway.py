"""
QMT网关组件

负责处理QMT数据并发布到事件系统
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional, List

from loguru import logger

from deepsearch.core.interfaces import Component
from deepsearch.datafeed.qmt.models import TickData, OrderBook, TradeData
from deepsearch.event.engine import EventEngine
from deepsearch.event.schema import Event
from deepsearch.messaging.bus import MessageBus
from .receiver import QMTReceiver

# 定义QMT相关事件类型
EVENT_QMT_TICK = "EVENT_QMT_TICK"
EVENT_QMT_ORDERBOOK = "EVENT_QMT_ORDERBOOK"
EVENT_QMT_TRADE = "EVENT_QMT_TRADE"
EVENT_QMT_ACCOUNT = "EVENT_QMT_ACCOUNT"
EVENT_QMT_POSITION = "EVENT_QMT_POSITION"
EVENT_QMT_ORDER = "EVENT_QMT_ORDER"
EVENT_QMT_CONNECTION = "EVENT_QMT_CONNECTION"


class QMTGateway(Component):
    """QMT数据网关"""

    def __init__(self, event_engine: EventEngine, message_bus: MessageBus, config: Dict):
        """
        初始化网关
        
        Args:
            event_engine: 事件引擎
            message_bus: 消息总线
            config: 配置信息
        """
        super().__init__()
        self.event_engine = event_engine
        self.message_bus = message_bus
        self.config = config

        # QMT接收器
        self.receiver: Optional[QMTReceiver] = None

        # 订阅的股票
        self.subscribed_symbols = set()

        # 数据缓存
        self.latest_ticks: Dict[str, TickData] = {}
        self.latest_orderbooks: Dict[str, OrderBook] = {}

        # 统计信息
        self.stats = {
            'tick_count': 0,
            'orderbook_count': 0,
            'trade_count': 0,
            'last_update': None,
            'start_time': None
        }

    async def initialize(self):
        """初始化网关"""
        logger.info("初始化QMT网关...")

        # 创建接收器
        self.receiver = QMTReceiver(
            host=self.config.get('receiver', {}).get('host', '0.0.0.0'),
            port=self.config.get('receiver', {}).get('tcp_port', 9999),
            auth_enabled=self.config.get('security', {}).get('enable_auth', False),
            auth_token=self.config.get('security', {}).get('token', '')
        )

        # 注册消息处理器
        self.receiver.register_handler('TICK', self._handle_tick_data)
        self.receiver.register_handler('LEVEL2', self._handle_level2_data)
        self.receiver.register_handler('TRADE', self._handle_trade_data)
        self.receiver.register_handler('BATCH', self._handle_batch_data)

        self.stats['start_time'] = time.time()

        logger.info("QMT网关初始化完成")

    async def start(self):
        """启动网关"""
        logger.info("启动QMT网关...")

        if not self.receiver:
            await self.initialize()

        # 启动接收器（在后台任务中运行）
        self._receiver_task = asyncio.create_task(self.receiver.start())

        # 发布连接事件
        self._publish_connection_event(True)

        logger.info("QMT网关已启动")

    async def stop(self):
        """停止网关"""
        logger.info("停止QMT网关...")

        # 发布断开事件
        self._publish_connection_event(False)

        # 停止接收器
        if self.receiver:
            await self.receiver.stop()

        # 取消接收器任务
        if hasattr(self, '_receiver_task'):
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass

        logger.info("QMT网关已停止")

    def is_running(self) -> bool:
        """检查网关是否运行中"""
        return self.receiver and self.receiver.running

    def get_status(self) -> Dict:
        """获取网关状态"""
        uptime = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0

        return {
            'running': self.is_running(),
            'uptime': uptime,
            'subscribed_symbols': len(self.subscribed_symbols),
            'cached_ticks': len(self.latest_ticks),
            'cached_orderbooks': len(self.latest_orderbooks),
            'stats': {
                'tick_count': self.stats['tick_count'],
                'orderbook_count': self.stats['orderbook_count'],
                'trade_count': self.stats['trade_count'],
                'tick_rate': self.stats['tick_count'] / uptime if uptime > 0 else 0,
                'last_update': self.stats['last_update']
            },
            'receiver': self.receiver.get_stats() if self.receiver else {}
        }

    async def _handle_tick_data(self, client_id: str, msg: Dict):
        """处理Tick数据"""
        try:
            data = msg.get('data', {})

            # 创建TickData对象
            tick = TickData(
                symbol=data.get('symbol', ''),
                name=data.get('name', ''),
                exchange=data.get('exchange', ''),
                timestamp=data.get('timestamp', time.time()),
                datetime=datetime.fromtimestamp(data.get('timestamp', time.time())),
                last_price=data.get('last_price', 0),
                pre_close=data.get('pre_close', 0),
                open_price=data.get('open', 0),
                high_price=data.get('high', 0),
                low_price=data.get('low', 0),
                volume=data.get('volume', 0),
                amount=data.get('amount', 0),
                trades_count=data.get('trades_count', 0),
                change=data.get('change', 0),
                pct_change=data.get('pct_change', 0),
                bid_price=data.get('bid_price', []),
                ask_price=data.get('ask_price', []),
                bid_volume=data.get('bid_volume', []),
                ask_volume=data.get('ask_volume', [])
            )

            # 更新缓存
            self.latest_ticks[tick.symbol] = tick
            self.subscribed_symbols.add(tick.symbol)

            # 发布事件
            self._publish_tick_event(tick)

            # 更新统计
            self.stats['tick_count'] += 1
            self.stats['last_update'] = time.time()

        except Exception as e:
            logger.error(f"处理Tick数据失败: {e}")

    async def _handle_level2_data(self, client_id: str, msg: Dict):
        """处理Level2十档盘口数据"""
        try:
            data = msg.get('data', {})
            symbol = data.get('symbol', '')

            logger.info(f"[LEVEL2] 收到盘口数据: symbol={symbol}, client={client_id}, data_keys={list(data.keys())}")

            # 创建OrderBook对象
            orderbook = OrderBook(
                symbol=symbol,
                timestamp=data.get('timestamp', time.time())
            )

            # 构建盘口数据
            bid_prices = data.get('bid_price', [])
            bid_volumes = data.get('bid_volume', [])
            ask_prices = data.get('ask_price', [])
            ask_volumes = data.get('ask_volume', [])

            # 添加买盘
            for i in range(min(len(bid_prices), len(bid_volumes))):
                if bid_prices[i] > 0:
                    from deepsearch.qmt.models.tick import OrderBookLevel
                    orderbook.bid_levels.append(OrderBookLevel(
                        price=bid_prices[i],
                        volume=bid_volumes[i]
                    ))

            # 添加卖盘
            for i in range(min(len(ask_prices), len(ask_volumes))):
                if ask_prices[i] > 0:
                    from deepsearch.qmt.models.tick import OrderBookLevel
                    orderbook.ask_levels.append(OrderBookLevel(
                        price=ask_prices[i],
                        volume=ask_volumes[i]
                    ))

            # 更新缓存 - 存储多个键以支持不同格式的查询
            self.latest_orderbooks[orderbook.symbol] = orderbook

            # 如果包含后缀，也存储不带后缀的版本
            if '.' in orderbook.symbol:
                pure_code = orderbook.symbol.split('.')[0]
                self.latest_orderbooks[pure_code] = orderbook
                logger.debug(f"同时缓存纯代码: {pure_code}")

            logger.info(
                f"[LEVEL2] 缓存更新成功: {orderbook.symbol}, 买档数={len(orderbook.bid_levels)}, 卖档数={len(orderbook.ask_levels)}, 缓存总数={len(self.latest_orderbooks)}")

            # 发布事件
            self._publish_orderbook_event(orderbook)

            # 更新统计
            self.stats['orderbook_count'] += 1
            self.stats['last_update'] = time.time()

        except Exception as e:
            logger.error(f"处理Level2数据失败: {e}")

    async def _handle_trade_data(self, client_id: str, msg: Dict):
        """处理逐笔成交数据"""
        try:
            data = msg.get('data', {})

            # 创建TradeData对象
            from deepsearch.qmt.models.trade import OrderSide
            trade = TradeData(
                symbol=data.get('symbol', ''),
                exchange=data.get('exchange', ''),
                timestamp=data.get('timestamp', time.time()),
                datetime=datetime.fromtimestamp(data.get('timestamp', time.time())),
                price=data.get('price', 0),
                volume=data.get('volume', 0),
                amount=data.get('amount', 0),
                trade_id=data.get('trade_id', ''),
                side=OrderSide.BUY if data.get('side') == 'BUY' else OrderSide.SELL
            )

            # 发布事件
            self._publish_trade_event(trade)

            # 更新统计
            self.stats['trade_count'] += 1
            self.stats['last_update'] = time.time()

        except Exception as e:
            logger.error(f"处理逐笔成交数据失败: {e}")

    async def _handle_batch_data(self, client_id: str, msg: Dict):
        """处理批量数据"""
        batch_data = msg.get('data', [])

        for item in batch_data:
            if isinstance(item, dict):
                msg_type = item.get('type')
                if msg_type == 'TICK':
                    await self._handle_tick_data(client_id, item)
                elif msg_type == 'LEVEL2':
                    await self._handle_level2_data(client_id, item)
                elif msg_type == 'TRADE':
                    await self._handle_trade_data(client_id, item)

    def _publish_tick_event(self, tick: TickData):
        """发布Tick事件"""
        event = Event(
            type=EVENT_QMT_TICK,
            data=tick.to_dict()
        )
        self.event_engine.put(event)

        # 同时发布到消息总线
        self.message_bus.publish(
            topic=f"QMT.TICK.{tick.symbol}",
            message=tick.to_dict()
        )

    def _publish_orderbook_event(self, orderbook: OrderBook):
        """发布盘口事件"""
        event = Event(
            type=EVENT_QMT_ORDERBOOK,
            data={
                'symbol': orderbook.symbol,
                'timestamp': orderbook.timestamp,
                'bid_levels': [
                    {'price': level.price, 'volume': level.volume}
                    for level in orderbook.bid_levels
                ],
                'ask_levels': [
                    {'price': level.price, 'volume': level.volume}
                    for level in orderbook.ask_levels
                ]
            }
        )
        self.event_engine.put(event)

        # 同时发布到消息总线
        self.message_bus.publish(
            topic=f"QMT.ORDERBOOK.{orderbook.symbol}",
            message=event.data
        )

    def _publish_trade_event(self, trade: TradeData):
        """发布成交事件"""
        event = Event(
            type=EVENT_QMT_TRADE,
            data=trade.to_dict()
        )
        self.event_engine.put(event)

        # 同时发布到消息总线
        self.message_bus.publish(
            topic=f"QMT.TRADE.{trade.symbol}",
            message=trade.to_dict()
        )

    def _publish_connection_event(self, connected: bool):
        """发布连接状态事件"""
        event = Event(
            type=EVENT_QMT_CONNECTION,
            data={
                'connected': connected,
                'timestamp': time.time()
            }
        )
        self.event_engine.put(event)

    def subscribe(self, symbols: List[str]):
        """订阅股票并通知采集器"""
        import uuid

        # 添加到本地订阅列表
        for symbol in symbols:
            self.subscribed_symbols.add(symbol)
            logger.debug(f"添加到订阅列表: {symbol}")

        # 向所有连接的采集器发送订阅请求
        if self.receiver and hasattr(self.receiver, 'client_writers'):
            request_id = f"req_{uuid.uuid4().hex[:8]}"
            subscribe_msg = {
                'type': 'SUBSCRIBE',
                'symbols': symbols,
                'data_types': ['TICK', 'LEVEL2'],
                'request_id': request_id
            }

            # 发送给所有客户端
            asyncio.create_task(self._broadcast_to_collectors(subscribe_msg))
            logger.info(
                f"发送订阅请求到采集器: {symbols}, request_id: {request_id}, 客户端数量: {len(self.receiver.client_writers)}")
        else:
            logger.warning(f"无法发送订阅请求，接收器未就绪或无客户端连接")

        logger.info(f"订阅股票完成: {symbols}, 当前订阅总数: {len(self.subscribed_symbols)}")

    async def _broadcast_to_collectors(self, message: Dict):
        """向所有采集器广播消息"""
        if not self.receiver:
            return

        try:
            # 获取所有客户端writer
            for client_id, writer in self.receiver.client_writers.items():
                try:
                    await self.receiver._send_message(writer, message)
                    logger.debug(f"发送消息到采集器 {client_id}: {message.get('type')}")
                except Exception as e:
                    logger.error(f"发送消息到 {client_id} 失败: {e}")
        except Exception as e:
            logger.error(f"广播消息失败: {e}")
    
    def unsubscribe(self, symbols: List[str]):
        """取消订阅股票并通知采集器"""
        import uuid

        # 从本地订阅列表移除
        for symbol in symbols:
            self.subscribed_symbols.discard(symbol)
            self.latest_ticks.pop(symbol, None)
            self.latest_orderbooks.pop(symbol, None)

        # 向所有连接的采集器发送取消订阅请求
        if self.receiver and hasattr(self.receiver, 'client_writers'):
            request_id = f"req_{uuid.uuid4().hex[:8]}"
            unsubscribe_msg = {
                'type': 'UNSUBSCRIBE',
                'symbols': symbols,
                'request_id': request_id
            }

            # 发送给所有客户端
            asyncio.create_task(self._broadcast_to_collectors(unsubscribe_msg))
            logger.info(f"发送取消订阅请求到采集器: {symbols}, request_id: {request_id}")
        
        logger.info(f"取消订阅股票: {symbols}")

    def get_latest_tick(self, symbol: str) -> Optional[Dict]:
        """获取最新的Tick数据"""
        tick = self.latest_ticks.get(symbol)
        return tick.to_dict() if tick else None

    def get_latest_orderbook(self, symbol: str) -> Optional[Dict]:
        """获取最新的盘口数据"""
        orderbook = self.latest_orderbooks.get(symbol)
        if orderbook:
            return {
                'symbol': orderbook.symbol,
                'timestamp': orderbook.timestamp,
                'bid_levels': [
                    {'price': level.price, 'volume': level.volume}
                    for level in orderbook.bid_levels
                ],
                'ask_levels': [
                    {'price': level.price, 'volume': level.volume}
                    for level in orderbook.ask_levels
                ]
            }
        return None
