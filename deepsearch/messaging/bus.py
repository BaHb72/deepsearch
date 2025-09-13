"""
Base message bus interface and composite implementation.
"""
from __future__ import annotations

import asyncio
import logging
import pickle
import zlib
import hashlib
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from datetime import datetime, timedelta
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar, Awaitable, DefaultDict, Tuple

from deepsearch.config.models import RouteConfig

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)
T = TypeVar("T")  # Data / Event / Command payload
R = TypeVar("R")  # Response payload


class MessageCompressor:
    """消息压缩器"""
    
    # 压缩阈值（字节）
    COMPRESSION_THRESHOLD = 1024  # 1KB
    
    @staticmethod
    def compress(data: Any) -> Tuple[bytes, bool]:
        """
        压缩消息
        
        Returns:
            (压缩后的数据, 是否压缩)
        """
        # 序列化
        serialized = pickle.dumps(data)
        
        # 检查是否需要压缩
        if len(serialized) < MessageCompressor.COMPRESSION_THRESHOLD:
            return serialized, False
        
        # 使用zlib压缩（速度和压缩率的平衡）
        compressed = zlib.compress(serialized, level=1)  # 使用较低的压缩级别以提高速度
        
        # 只有压缩后更小才使用压缩
        if len(compressed) < len(serialized):
            return compressed, True
        return serialized, False
    
    @staticmethod
    def decompress(data: bytes, is_compressed: bool) -> Any:
        """
        解压缩消息
        """
        if is_compressed:
            data = zlib.decompress(data)
        return pickle.loads(data)


class MessageDeduplicator:
    """消息去重器"""
    
    def __init__(self, ttl_seconds: int = 60, max_size: int = 10000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self.seen_messages = {}  # message_id -> timestamp
        self.message_queue = deque()  # 用于LRU淘汰
        self.stats = {
            'total_messages': 0,
            'duplicates_filtered': 0,
            'unique_messages': 0
        }
    
    def generate_message_id(self, topic: str, message: Any) -> str:
        """生成消息 ID"""
        msg_str = f"{topic}:{str(message)}"
        return hashlib.md5(msg_str.encode()).hexdigest()[:16]
    
    def is_duplicate(self, message_id: str) -> bool:
        """检查是否为重复消息"""
        self.stats['total_messages'] += 1
        now = datetime.now()
        
        # 清理过期消息
        self._cleanup_expired(now)
        
        # 检查是否见过
        if message_id in self.seen_messages:
            self.stats['duplicates_filtered'] += 1
            return True
        
        # 记录新消息
        self.seen_messages[message_id] = now
        self.message_queue.append((message_id, now))
        self.stats['unique_messages'] += 1
        
        # LRU淘汰
        if len(self.seen_messages) > self.max_size:
            oldest_id, _ = self.message_queue.popleft()
            if oldest_id in self.seen_messages:
                del self.seen_messages[oldest_id]
        
        return False
    
    def _cleanup_expired(self, now: datetime):
        """清理过期消息"""
        cutoff = now - timedelta(seconds=self.ttl_seconds)
        
        # 从队列头部开始清理过期消息
        while self.message_queue:
            msg_id, timestamp = self.message_queue[0]
            if timestamp > cutoff:
                break
            self.message_queue.popleft()
            if msg_id in self.seen_messages:
                del self.seen_messages[msg_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return dict(self.stats)


class MessageBus(ABC):
    """
    Abstract base class for message bus implementations.
    
    A message bus facilitates communication between different parts of the system
    by allowing publishers to send messages and subscribers to receive them.
    """

    @abstractmethod
    def publish(self, topic: str, message: T) -> None:
        """
        Publish a message to a specific topic.
        
        Args:
            topic: The topic to publish to
            message: The message to publish
        """
        pass

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Subscribe to messages on a specific topic.
        
        Args:
            topic: The topic pattern to subscribe to (supports wildcards)
            handler: Callback function to handle received messages
        """
        pass

    @abstractmethod
    def unsubscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Unsubscribe a handler from a topic.
        
        Args:
            topic: The topic pattern to unsubscribe from
            handler: The handler to remove
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the message bus."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the message bus."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the message bus is running."""
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the message bus.
        
        Returns:
            Dictionary containing bus statistics
        """
        return {
            "running": self.is_running(),
            "type": self.__class__.__name__
        }


class CompositeMessageBus(MessageBus):
    """
    Composite message bus that routes messages to multiple underlying buses.
    
    This implementation allows for flexible routing of messages based on
    topic patterns to different message bus implementations.
    """

    def __init__(self, buses: Optional[Dict[str, MessageBus]] = None,
                 routes: Optional[List[RouteConfig]] = None,
                 enable_compression: bool = True,
                 enable_deduplication: bool = True,
                 dedup_ttl: int = 60):
        """
        Initialize composite message bus.
        
        Args:
            buses: Dictionary mapping bus names to bus instances
            routes: List of routing configurations
            enable_compression: 启用消息压缩
            enable_deduplication: 启用消息去重
            dedup_ttl: 去重TTL（秒）
        """
        self._buses: Dict[str, MessageBus] = buses or {}
        self._routes: List[RouteConfig] = routes or []
        self._running = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # 维护 async handler -> sync wrapper 的映射，按 topic 分组
        self._async_wrappers: DefaultDict[str, Dict[Callable, Callable]] = defaultdict(dict)
        
        # 消息压缩和去重
        self.enable_compression = enable_compression
        self.compressor = MessageCompressor() if enable_compression else None
        self.deduplicator = MessageDeduplicator(ttl_seconds=dedup_ttl) if enable_deduplication else None
        
        # 性能统计
        self.stats = {
            'messages_published': 0,
            'messages_compressed': 0,
            'messages_deduplicated': 0,
            'bytes_sent': 0,
            'bytes_compressed': 0,
            'routing_decisions': defaultdict(int),
            'publish_times': deque(maxlen=1000),  # 最近1000次发布时间
            'errors': defaultdict(int)
        }

    def add_bus(self, name: str, bus: MessageBus) -> None:
        """
        Add a message bus to the composite.
        
        Args:
            name: Name for the bus
            bus: The bus instance to add
        """
        if self._running:
            raise RuntimeError("Cannot add bus while running")
        self._buses[name] = bus
        self.logger.debug(f"添加消息总线：{name} ({type(bus).__name__})")

    def add_route(self, route: RouteConfig) -> None:
        """
        Add a routing rule.
        
        Args:
            route: The routing configuration to add
        """
        self._routes.append(route)
        self.logger.debug(f"添加路由规则：{route.match} -> {route.buses}")

    def publish(self, topic: str, message: T) -> None:
        """Publish message to appropriate buses based on routing rules."""
        if not self._running:
            raise RuntimeError("Message bus is not running")
        
        start_time = time.time()
        self.stats['messages_published'] += 1
        
        # 消息去重
        if self.deduplicator:
            msg_id = self.deduplicator.generate_message_id(topic, message)
            if self.deduplicator.is_duplicate(msg_id):
                self.stats['messages_deduplicated'] += 1
                self.logger.debug(f"Duplicate message filtered for topic '{topic}'")
                return
        
        # 消息压缩
        processed_message = message
        is_compressed = False
        
        if self.compressor:
            try:
                compressed_data, is_compressed = self.compressor.compress(message)
                if is_compressed:
                    self.stats['messages_compressed'] += 1
                    self.stats['bytes_compressed'] += len(compressed_data)
                    processed_message = {'_compressed': True, '_data': compressed_data}
                else:
                    processed_message = {'_compressed': False, '_data': compressed_data}
                self.stats['bytes_sent'] += len(compressed_data)
            except Exception as e:
                self.logger.error(f"Message compression failed: {e}")
                self.stats['errors']['compression'] += 1

        target_buses = self._get_target_buses(topic)
        
        # 记录路由决策
        for bus_name in target_buses:
            self.stats['routing_decisions'][bus_name] += 1

        if not target_buses:
            self.logger.warning(f"主题 '{topic}' 没有配置任何消息总线")
            return

        for bus_name in target_buses:
            bus = self._buses.get(bus_name)
            if bus and bus.is_running():
                try:
                    bus.publish(topic, processed_message)
                except Exception as e:
                    self.logger.error(f"发送消息到 '{bus_name}' 失败：{e}")
                    self.stats['errors'][f'publish_{bus_name}'] += 1
        
        # 记录发布时间
        publish_time = time.time() - start_time
        self.stats['publish_times'].append(publish_time)

    def subscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """Subscribe to all buses."""
        for name, bus in self._buses.items():
            try:
                bus.subscribe(topic, handler)
                self.logger.debug(f"订阅主题 '{topic}' - 总线：{name}")
            except Exception as e:
                self.logger.error(f"订阅失败 - 总线：{name}，错误：{e}")

    def unsubscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """Unsubscribe from all buses."""
        for name, bus in self._buses.items():
            try:
                bus.unsubscribe(topic, handler)
                self.logger.debug(f"取消订阅 '{topic}' - 总线：{name}")
            except Exception as e:
                self.logger.error(f"取消订阅失败 - 总线：{name}，错误：{e}")

    def start(self) -> None:
        """Start all configured buses."""
        if self._running:
            return

        self.logger.debug("启动复合消息总线")

        for name, bus in self._buses.items():
            try:
                bus.start()
                self.logger.debug(f"启动消息总线：{name}")
            except Exception as e:
                self.logger.error(f"启动 '{name}' 失败：{e}")
                # Stop already started buses
                self._stop_buses()
                raise

        self._running = True
        self.logger.debug("复合消息总线启动完成")

    def stop(self) -> None:
        """Stop all buses."""
        if not self._running:
            return

        self.logger.debug("停止复合消息总线")
        self._stop_buses()
        self._running = False
        self.logger.debug("复合消息总线停止完成")

    def is_running(self) -> bool:
        """Check if the composite bus is running."""
        return self._running

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from all buses."""
        stats = super().get_statistics()
        stats["buses"] = {}

        for name, bus in self._buses.items():
            try:
                stats["buses"][name] = bus.get_statistics()
            except Exception as e:
                stats["buses"][name] = {"error": str(e)}

        stats["routes"] = len(self._routes)
        
        # 添加性能统计
        stats["performance"] = {
            'messages_published': self.stats['messages_published'],
            'messages_compressed': self.stats['messages_compressed'],
            'messages_deduplicated': self.stats['messages_deduplicated'],
            'compression_ratio': self._calculate_compression_ratio(),
            'deduplication_ratio': self._calculate_dedup_ratio(),
            'avg_publish_time': self._calculate_avg_publish_time(),
            'routing_decisions': dict(self.stats['routing_decisions']),
            'errors': dict(self.stats['errors'])
        }
        
        # 去重器统计
        if self.deduplicator:
            stats["deduplicator"] = self.deduplicator.get_stats()
        
        return stats
    
    def _calculate_compression_ratio(self) -> float:
        """计算压缩率"""
        if self.stats['bytes_sent'] == 0:
            return 0.0
        return self.stats['bytes_compressed'] / self.stats['bytes_sent']
    
    def _calculate_dedup_ratio(self) -> float:
        """计算去重率"""
        total = self.stats['messages_published']
        if total == 0:
            return 0.0
        return self.stats['messages_deduplicated'] / total
    
    def _calculate_avg_publish_time(self) -> float:
        """计算平均发布时间"""
        if not self.stats['publish_times']:
            return 0.0
        return sum(self.stats['publish_times']) / len(self.stats['publish_times'])
    
    def reset_statistics(self):
        """重置统计信息"""
        self.stats['messages_published'] = 0
        self.stats['messages_compressed'] = 0
        self.stats['messages_deduplicated'] = 0
        self.stats['bytes_sent'] = 0
        self.stats['bytes_compressed'] = 0
        self.stats['routing_decisions'].clear()
        self.stats['publish_times'].clear()
        self.stats['errors'].clear()
        
        if self.deduplicator:
            self.deduplicator.stats = {
                'total_messages': 0,
                'duplicates_filtered': 0,
                'unique_messages': 0
            }

    def _get_target_buses(self, topic: str) -> List[str]:
        """
        Get list of target buses for a topic based on routing rules.
        
        Args:
            topic: The topic to route
            
        Returns:
            List of bus names to route the message to
        """
        target_buses = set()

        for route in self._routes:
            if fnmatch(topic, route.match):
                for bus_name in route.buses:
                    # Convert BusName enum to string if needed
                    bus_str = bus_name.value if hasattr(bus_name, 'value') else str(bus_name)
                    if bus_str in self._buses:
                        target_buses.add(bus_str)

        return list(target_buses)

    def _stop_buses(self) -> None:
        """Stop all buses, logging any errors."""
        for name, bus in self._buses.items():
            try:
                bus.stop()
                self.logger.debug(f"停止消息总线：{name}")
            except Exception as e:
                self.logger.debug(f"停止 '{name}' 时出错：{e}")

    async def publish_async(self, topic: str, message: T) -> None:
        """
        Async wrapper for publish. 与同步行为一致并校验运行状态。
        
        Args:
            topic: The topic to publish to
            message: The message to publish
        """
        # 保持与 publish 一致的运行状态语义
        if not self._running:
            raise RuntimeError("Message bus is not running")
        # 直接使用同步路径，确保在当前线程内操作底层 ZeroMQ socket（线程安全）
        self.publish(topic, message)

    async def subscribe_async(self, topic: str, async_handler: Callable[[str, T], Awaitable[None]]) -> None:
        """
        允许以异步 handler 订阅；内部包装为同步 handler 并把执行调度回事件循环。
        
        Args:
            topic: The topic pattern to subscribe to (supports wildcards)
            async_handler: Async callback function to handle received messages
            
        Raises:
            RuntimeError: If called outside of a running event loop
        """
        try:
            # 在订阅时捕获当前事件循环（主循环）
            loop = asyncio.get_running_loop()
        except RuntimeError as e:
            # 如果调用点不在协程上下文中，明确报错
            self.logger.error(
                "subscribe_async() must be called from within a running async event loop. "
                "Use 'await subscribe_async()' from an async function or coroutine."
            )
            raise RuntimeError(
                "subscribe_async() requires a running event loop. "
                "It must be called from within an async context (async function or coroutine)."
            ) from e

        def _sync_wrapper(t: str, msg: T) -> None:
            # 注意：这里运行在 ZeroMQ 订阅线程（或其他非事件循环线程）
            try:
                # 确保事件循环仍在运行
                if loop.is_closed():
                    self.logger.error(f"Event loop is closed, cannot schedule handler for topic '{t}'")
                    return

                # 使用 call_soon_threadsafe 安全地调度异步任务
                loop.call_soon_threadsafe(asyncio.create_task, async_handler(t, msg))
            except RuntimeError as e:
                # 事件循环可能已停止
                self.logger.error(f"Event loop no longer running for topic '{t}': {e}")
            except Exception as e:
                self.logger.error(f"Failed to schedule async handler for topic '{t}': {e}", exc_info=True)

        # 保存映射用于取消订阅
        self._async_wrappers[topic][async_handler] = _sync_wrapper

        # 复用现有同步订阅到所有底层总线
        self.subscribe(topic, _sync_wrapper)

    async def unsubscribe_async(self, topic: str, async_handler: Callable[[str, T], Awaitable[None]]) -> None:
        """
        按 topic 和 async_handler 取消订阅。
        
        Args:
            topic: The topic pattern to unsubscribe from
            async_handler: The async handler to remove
        """
        wrapper = self._async_wrappers.get(topic, {}).pop(async_handler, None)
        if wrapper is None:
            # 没找到匹配包装器：可能未订阅或已取消；可选择告警但不抛错
            self.logger.debug(f"No async subscription found for topic '{topic}' to remove")
            return
        # 调用同步取消订阅，使之在所有底层总线上移除
        self.unsubscribe(topic, wrapper)
