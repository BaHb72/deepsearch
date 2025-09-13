"""
QMT网关组件优化版本
提供更好的数据处理和错误恢复能力
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional, List

from loguru import logger

from deepsearch.core.interfaces.component import Component
from deepsearch.data_providers.datafeed.qmt.gateway import (
    EVENT_QMT_TICK,
    EVENT_QMT_ORDERBOOK,
    EVENT_QMT_TRADE,
    EVENT_QMT_CONNECTION
)
from deepsearch.data_providers.datafeed.qmt.models import TickData, OrderBook, TradeData
from deepsearch.data_providers.datafeed.qmt.receiver import QMTReceiver
from deepsearch.event.engine.engine import EventEngine
from deepsearch.event.schema import Event
from deepsearch.messaging.bus import MessageBus


class QMTGatewayComponent(Component):
    """优化的QMT网关组件"""

    def __init__(self, event_engine: EventEngine, message_bus: MessageBus, config: Dict):
        super().__init__()
        self.event_engine = event_engine
        self.message_bus = message_bus
        self.config = config
        
        # 从配置读取优先级，而不是硬编码
        self.priority = config.get('priority', 1)

        # 接收器
        self.receiver: Optional[QMTReceiver] = None

        # 数据缓存（优化的缓存结构）
        self._tick_cache = {}  # symbol -> TickData
        self._orderbook_cache = {}  # symbol -> OrderBook
        self._cache_timestamps = {}  # symbol -> timestamp
        self._cache_ttl = config.get('data', {}).get('cache_ttl', 60)

        # 订阅管理
        self.subscribed_symbols = set()

        # 性能统计
        self.stats = {
            'tick_count': 0,
            'orderbook_count': 0,
            'trade_count': 0,
            'last_update': None,
            'start_time': None,
            'processing_times': [],  # 记录处理时间
            'error_count': 0
        }

        # 批量处理缓冲
        self._batch_buffer = []
        self._batch_size = config.get('data', {}).get('batch_size', 100)
        self._flush_interval = config.get('data', {}).get('flush_interval', 0.1)
        self._last_flush_time = time.time()

        # 异步任务
        self._receiver_task = None
        self._flush_task = None
        self._cleanup_task = None

    async def initialize(self):
        """初始化网关"""
        logger.info("初始化优化的QMT网关...")

        try:
            # 创建接收器
            self.receiver = QMTReceiver(
                host=self.config.get('receiver', {}).get('host', '0.0.0.0'),
                port=self.config.get('receiver', {}).get('tcp_port', 9999),
                auth_enabled=self.config.get('security', {}).get('enable_auth', False),
                auth_token=self.config.get('security', {}).get('token', '')
            )

            # 注册优化的消息处理器
            self.receiver.register_handler('TICK', self._handle_tick_batch)
            self.receiver.register_handler('LEVEL2', self._handle_level2_batch)
            self.receiver.register_handler('TRADE', self._handle_trade_batch)
            self.receiver.register_handler('BATCH', self._handle_batch_data)

            self.stats['start_time'] = time.time()

            logger.info("优化的QMT网关初始化完成")

        except Exception as e:
            logger.error(f"初始化QMT网关失败: {e}")
            raise

    async def start(self):
        """启动网关"""
        logger.info("启动优化的QMT网关...")

        if not self.receiver:
            await self.initialize()

        # 获取当前事件循环
        loop = asyncio.get_running_loop()

        # 启动接收器
        self._receiver_task = loop.create_task(self.receiver.start())

        # 启动批量刷新任务
        self._flush_task = loop.create_task(self._flush_loop())

        # 启动缓存清理任务
        self._cleanup_task = loop.create_task(self._cleanup_loop())

        # 发布连接事件
        self._publish_connection_event(True)

        logger.info("优化的QMT网关已启动")

    async def stop(self):
        """停止网关"""
        logger.info("停止优化的QMT网关...")

        # 发布断开事件
        self._publish_connection_event(False)

        # 刷新剩余数据
        try:
            await self._flush_batch()
        except Exception as e:
            logger.warning(f"刷新批量数据时出错: {e}")

        # 停止接收器
        if self.receiver:
            try:
                await self.receiver.stop()
            except Exception as e:
                logger.warning(f"停止接收器时出错: {e}")

        # 取消异步任务
        tasks = [self._receiver_task, self._flush_task, self._cleanup_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()

        # 等待所有任务完成
        if any(tasks):
            await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)

        logger.info("优化的QMT网关已停止")

    def is_running(self) -> bool:
        """检查网关是否运行中"""
        return self.receiver and self.receiver.running

    def get_status(self) -> Dict:
        """获取网关状态"""
        uptime = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0

        # 计算平均处理时间
        avg_processing_time = 0
        if self.stats['processing_times']:
            recent_times = self.stats['processing_times'][-100:]  # 最近100次
            avg_processing_time = sum(recent_times) / len(recent_times)

        return {
            'running': self.is_running(),
            'uptime': uptime,
            'subscribed_symbols': len(self.subscribed_symbols),
            'cached_ticks': len(self._tick_cache),
            'cached_orderbooks': len(self._orderbook_cache),
            'batch_buffer_size': len(self._batch_buffer),
            'stats': {
                'tick_count': self.stats['tick_count'],
                'orderbook_count': self.stats['orderbook_count'],
                'trade_count': self.stats['trade_count'],
                'error_count': self.stats['error_count'],
                'tick_rate': self.stats['tick_count'] / uptime if uptime > 0 else 0,
                'avg_processing_time_ms': avg_processing_time * 1000,
                'last_update': self.stats['last_update']
            },
            'receiver': self.receiver.get_stats() if self.receiver else {}
        }

    async def _handle_tick_batch(self, client_id: str, msg: Dict):
        """批量处理Tick数据（增强错误处理）"""
        start_time = time.time()

        try:
            data = msg.get('data', {})
            
            # 数据验证
            symbol = data.get('symbol', '')
            if not symbol:
                logger.warning(f"收到无效的Tick数据（缺少symbol）: {data}")
                self.stats['error_count'] += 1
                return
            
            # 安全地获取数值，提供默认值
            def safe_float(value, default=0.0):
                try:
                    return float(value) if value is not None else default
                except (ValueError, TypeError):
                    return default
            
            def safe_int(value, default=0):
                try:
                    return int(value) if value is not None else default
                except (ValueError, TypeError):
                    return default

            # 创建TickData对象（安全处理）
            tick = TickData(
                symbol=symbol,
                name=data.get('name', ''),
                exchange=data.get('exchange', ''),
                timestamp=safe_float(data.get('timestamp', time.time())),
                datetime=datetime.fromtimestamp(safe_float(data.get('timestamp', time.time()))),
                last_price=safe_float(data.get('last_price')),
                pre_close=safe_float(data.get('pre_close')),
                open_price=safe_float(data.get('open')),
                high_price=safe_float(data.get('high')),
                low_price=safe_float(data.get('low')),
                volume=safe_int(data.get('volume')),
                amount=safe_float(data.get('amount')),
                trades_count=safe_int(data.get('trades_count')),
                change=safe_float(data.get('change')),
                pct_change=safe_float(data.get('pct_change')),
                bid_price=data.get('bid_price', []) or [],
                ask_price=data.get('ask_price', []) or [],
                bid_volume=data.get('bid_volume', []) or [],
                ask_volume=data.get('ask_volume', []) or []
            )

            # 更新缓存
            self._tick_cache[tick.symbol] = tick
            self._cache_timestamps[tick.symbol] = time.time()
            self.subscribed_symbols.add(tick.symbol)

            # 添加到批量缓冲
            self._batch_buffer.append(('tick', tick))

            # 更新统计
            self.stats['tick_count'] += 1
            self.stats['last_update'] = time.time()

            # 记录处理时间
            processing_time = time.time() - start_time
            self.stats['processing_times'].append(processing_time)
            
            # 限制处理时间记录数量，避免内存增长
            if len(self.stats['processing_times']) > 1000:
                self.stats['processing_times'] = self.stats['processing_times'][-1000:]

            # 检查是否需要立即刷新
            if len(self._batch_buffer) >= self._batch_size:
                await self._flush_batch()

        except Exception as e:
            logger.error(f"处理Tick数据失败: {e}", exc_info=True)
            self.stats['error_count'] += 1
            
            # 记录详细错误信息用于调试
            logger.debug(f"错误数据内容: {msg}")

    async def _handle_level2_batch(self, client_id: str, msg: Dict):
        """批量处理Level2数据"""
        start_time = time.time()

        try:
            data = msg.get('data', {})
            symbol = data.get('symbol', '')

            logger.info(f"处理Level2数据: {symbol} from {client_id}")

            # 创建OrderBook对象
            orderbook = OrderBook(
                symbol=symbol,
                timestamp=data.get('timestamp', time.time())
            )

            # 构建盘口数据（优化版本）
            bid_prices = data.get('bid_price', [])
            bid_volumes = data.get('bid_volume', [])
            ask_prices = data.get('ask_price', [])
            ask_volumes = data.get('ask_volume', [])

            # 使用列表推导式优化
            from deepsearch.data_providers.datafeed.qmt.models import OrderBookLevel
            orderbook.bid_levels = [
                OrderBookLevel(price=p, volume=v)
                for p, v in zip(bid_prices, bid_volumes)
                if p > 0
            ]

            orderbook.ask_levels = [
                OrderBookLevel(price=p, volume=v)
                for p, v in zip(ask_prices, ask_volumes)
                if p > 0
            ]

            # 更新缓存 - 使用多个键确保兼容性
            self._orderbook_cache[orderbook.symbol] = orderbook
            self._cache_timestamps[f"orderbook_{orderbook.symbol}"] = time.time()

            # 如果symbol包含后缀，也存储不带后缀的版本以支持多种查询格式
            if '.' in orderbook.symbol:
                pure_code = orderbook.symbol.split('.')[0]
                self._orderbook_cache[pure_code] = orderbook
                logger.debug(f"同时缓存纯代码版本: {pure_code}")

            logger.info(
                f"更新盘口缓存: {orderbook.symbol}, 买一={bid_prices[0] if bid_prices else 0}, 卖一={ask_prices[0] if ask_prices else 0}, 缓存键数量={len(self._orderbook_cache)}")

            # 添加到批量缓冲
            self._batch_buffer.append(('orderbook', orderbook))

            # 更新统计
            self.stats['orderbook_count'] += 1
            self.stats['last_update'] = time.time()

            # 记录处理时间
            processing_time = time.time() - start_time
            self.stats['processing_times'].append(processing_time)

            # 检查是否需要立即刷新
            if len(self._batch_buffer) >= self._batch_size:
                await self._flush_batch()

        except Exception as e:
            logger.error(f"处理Level2数据失败: {e}")
            self.stats['error_count'] += 1

    async def _handle_trade_batch(self, client_id: str, msg: Dict):
        """批量处理逐笔成交数据"""
        try:
            data = msg.get('data', {})

            # 创建TradeData对象
            from deepsearch.data_providers.datafeed.qmt.models import OrderSide
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

            # 添加到批量缓冲
            self._batch_buffer.append(('trade', trade))

            # 更新统计
            self.stats['trade_count'] += 1
            self.stats['last_update'] = time.time()

            # 检查是否需要立即刷新
            if len(self._batch_buffer) >= self._batch_size:
                await self._flush_batch()

        except Exception as e:
            logger.error(f"处理逐笔成交数据失败: {e}")
            self.stats['error_count'] += 1

    async def _handle_batch_data(self, client_id: str, msg: Dict):
        """处理批量数据"""
        batch_data = msg.get('data', [])

        for item in batch_data:
            if isinstance(item, dict):
                msg_type = item.get('type')
                if msg_type == 'TICK':
                    await self._handle_tick_batch(client_id, item)
                elif msg_type == 'LEVEL2':
                    await self._handle_level2_batch(client_id, item)
                elif msg_type == 'TRADE':
                    await self._handle_trade_batch(client_id, item)

    async def _flush_batch(self):
        """刷新批量数据"""
        if not self._batch_buffer:
            return

        try:
            # 按类型分组
            tick_batch = []
            orderbook_batch = []
            trade_batch = []

            for data_type, data in self._batch_buffer:
                if data_type == 'tick':
                    tick_batch.append(data)
                elif data_type == 'orderbook':
                    orderbook_batch.append(data)
                elif data_type == 'trade':
                    trade_batch.append(data)

            # 批量发布事件
            if tick_batch:
                event = Event(
                    type=EVENT_QMT_TICK,
                    data={'batch': [tick.to_dict() for tick in tick_batch]}
                )
                self.event_engine.put(event)

                # 批量发布到消息总线
                for tick in tick_batch:
                    self.message_bus.publish(
                        topic=f"QMT.TICK.{tick.symbol}",
                        message=tick.to_dict()
                    )

            if orderbook_batch:
                event = Event(
                    type=EVENT_QMT_ORDERBOOK,
                    data={'batch': [self._orderbook_to_dict(ob) for ob in orderbook_batch]}
                )
                self.event_engine.put(event)

                # 批量发布到消息总线
                for orderbook in orderbook_batch:
                    self.message_bus.publish(
                        topic=f"QMT.ORDERBOOK.{orderbook.symbol}",
                        message=self._orderbook_to_dict(orderbook)
                    )

            if trade_batch:
                event = Event(
                    type=EVENT_QMT_TRADE,
                    data={'batch': [trade.to_dict() for trade in trade_batch]}
                )
                self.event_engine.put(event)

                # 批量发布到消息总线
                for trade in trade_batch:
                    self.message_bus.publish(
                        topic=f"QMT.TRADE.{trade.symbol}",
                        message=trade.to_dict()
                    )

            # 清空缓冲
            self._batch_buffer = []
            self._last_flush_time = time.time()

        except Exception as e:
            logger.error(f"刷新批量数据失败: {e}")
            self.stats['error_count'] += 1

    async def _flush_loop(self):
        """定期刷新批量数据"""
        while True:
            try:
                await asyncio.sleep(self._flush_interval)

                # 检查是否需要刷新
                if self._batch_buffer and (time.time() - self._last_flush_time >= self._flush_interval):
                    await self._flush_batch()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"刷新循环异常: {e}")

    async def _cleanup_loop(self):
        """定期清理过期缓存"""
        cleanup_interval = 60  # 每分钟清理一次

        while True:
            try:
                await asyncio.sleep(cleanup_interval)

                current_time = time.time()
                expired_keys = []

                # 查找过期的缓存项
                for key, timestamp in self._cache_timestamps.items():
                    if current_time - timestamp > self._cache_ttl:
                        expired_keys.append(key)

                # 清理过期缓存
                for key in expired_keys:
                    if key.startswith('orderbook_'):
                        symbol = key.replace('orderbook_', '')
                        self._orderbook_cache.pop(symbol, None)
                    else:
                        self._tick_cache.pop(key, None)
                    del self._cache_timestamps[key]

                if expired_keys:
                    logger.debug(f"清理了{len(expired_keys)}个过期缓存项")

                # 限制处理时间列表大小
                if len(self.stats['processing_times']) > 1000:
                    self.stats['processing_times'] = self.stats['processing_times'][-100:]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循环异常: {e}")

    def _orderbook_to_dict(self, orderbook: OrderBook) -> Dict:
        """将OrderBook转换为字典"""
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
        """订阅股票"""
        for symbol in symbols:
            self.subscribed_symbols.add(symbol)
        logger.info(f"订阅股票: {symbols}")

    def unsubscribe(self, symbols: List[str]):
        """取消订阅股票"""
        for symbol in symbols:
            self.subscribed_symbols.discard(symbol)
            self._tick_cache.pop(symbol, None)
            self._orderbook_cache.pop(symbol, None)
            self._cache_timestamps.pop(symbol, None)
            self._cache_timestamps.pop(f"orderbook_{symbol}", None)
        logger.info(f"取消订阅股票: {symbols}")

    def get_latest_tick(self, symbol: str) -> Optional[Dict]:
        """获取最新的Tick数据"""
        # 先尝试直接查找
        tick = self._tick_cache.get(symbol)

        # 如果没找到，尝试添加交易所后缀
        if not tick and '.' not in symbol:
            # 尝试上海和深圳的后缀
            for suffix in ['.SH', '.SZ']:
                test_symbol = symbol + suffix
                tick = self._tick_cache.get(test_symbol)
                if tick:
                    logger.info(f"通过添加后缀找到Tick数据: {symbol} -> {test_symbol}")
                    break
        
        return tick.to_dict() if tick else None

    def get_latest_orderbook(self, symbol: str) -> Optional[Dict]:
        """获取最新的盘口数据"""
        # 先尝试直接查找
        orderbook = self._orderbook_cache.get(symbol)

        # 如果没找到，尝试添加交易所后缀
        if not orderbook and '.' not in symbol:
            # 尝试上海和深圳的后缀
            for suffix in ['.SH', '.SZ']:
                test_symbol = symbol + suffix
                orderbook = self._orderbook_cache.get(test_symbol)
                if orderbook:
                    logger.info(f"通过添加后缀找到盘口数据: {symbol} -> {test_symbol}")
                    break

        if orderbook:
            logger.info(f"从缓存获取盘口数据: {symbol}, 缓存中有 {len(self._orderbook_cache)} 个股票")
            return self._orderbook_to_dict(orderbook)
        else:
            logger.info(f"缓存中没有 {symbol} 的盘口数据, 缓存股票: {list(self._orderbook_cache.keys())}")
            return None
    
    def is_qmt_connected(self) -> bool:
        """检查QMT采集器是否真正连接"""
        # 检查是否有最近的数据更新（30秒内）
        if self._cache_timestamps:
            latest_update = max(self._cache_timestamps.values())
            if time.time() - latest_update < 30:
                return True
        
        # 检查是否有接收到消息
        if hasattr(self, 'receiver') and self.receiver:
            # 这里可以添加更多的连接检查逻辑
            return self.receiver.is_connected() if hasattr(self.receiver, 'is_connected') else False
        
        return False
