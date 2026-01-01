"""
数据管道协调器。

实现 Branching 模式，由 PipelineManager 协调不同的数据消费者：
- Archiver: 写入 L1 Arrow 缓存
- SharedMemoryWriter: 写入 L2 NumPy Ring Buffer
- SignalDispatcher: 分发给策略引擎

用法:
    from deepsearch.application.data.pipeline import PipelineManager, Archiver
    
    pipeline = PipelineManager()
    pipeline.register(Archiver(cache_manager))
    
    await pipeline.dispatch(kline_response)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from .handlers import KlineDataHandler

if TYPE_CHECKING:
    from deepsearch.infrastructure.cache.arrow_cache import ArrowCacheManager
    from deepsearch.ports.data.responses import KlineResponse


class DataSink(Protocol):
    """数据消费者协议。"""
    
    async def consume(self, handler: KlineDataHandler) -> None:
        """消费数据。"""
        ...


class BaseSink(ABC):
    """数据消费者基类。"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """消费者名称。"""
        ...
    
    @abstractmethod
    async def consume(self, handler: KlineDataHandler) -> None:
        """消费数据。"""
        ...


class Archiver(BaseSink):
    """
    L1 存档器 - 写入 Arrow 缓存。
    
    使用 handler.to_arrow() 获取 Arrow Table 并写入缓存。
    """
    
    def __init__(self, cache: "ArrowCacheManager"):
        self._cache = cache
    
    @property
    def name(self) -> str:
        return "Archiver"
    
    async def consume(self, handler: KlineDataHandler) -> None:
        """将数据写入 L1 Arrow 缓存。"""
        key = self._generate_key(handler)
        table = handler.to_arrow()
        self._cache.set(key, table)
        logger.debug(f"[Archiver] 写入缓存: {key}, {len(handler)} bars")
    
    def _generate_key(self, handler: KlineDataHandler) -> str:
        """生成缓存键。"""
        return self._cache.generate_cache_key(
            symbol=handler.asset.symbol,
            exchange=handler.asset.exchange.value if handler.asset.exchange else "",
            period=handler.timeframe.value,
        )


class SharedMemoryWriter(BaseSink):
    """
    L2 共享内存写入器 - 写入 NumPy Ring Buffer。
    
    使用 handler.to_numpy() 获取数组并写入预分配的共享内存。
    """
    
    def __init__(self, buffer_registry: dict):
        """
        Args:
            buffer_registry: symbol -> RingBuffer 的映射
        """
        self._buffers = buffer_registry
    
    @property
    def name(self) -> str:
        return "SharedMemoryWriter"
    
    async def consume(self, handler: KlineDataHandler) -> None:
        """将数据写入 L2 共享内存。"""
        symbol = handler.asset.to_standard()
        buffer = self._buffers.get(symbol)
        
        if buffer is None:
            logger.debug(f"[SharedMemory] {symbol} 未订阅，跳过 L2 写入")
            return
        
        data = handler.to_numpy()
        buffer.write(data)
        logger.debug(f"[SharedMemory] 写入 L2: {symbol}, shape={data.shape}")


class SignalDispatcher(BaseSink):
    """
    信号引擎分发器 - 分发给策略。
    
    使用 handler.to_dataframe() 获取 DataFrame 并调用策略的 next()。
    """
    
    def __init__(self, strategy_callback=None):
        """
        Args:
            strategy_callback: async def callback(symbol, df) -> None
        """
        self._callback = strategy_callback
    
    @property
    def name(self) -> str:
        return "SignalDispatcher"
    
    async def consume(self, handler: KlineDataHandler) -> None:
        """分发给策略引擎。"""
        if self._callback is None:
            return
        
        df = handler.to_dataframe()
        symbol = handler.asset.to_standard()
        await self._callback(symbol, df)
        logger.debug(f"[SignalDispatcher] 分发给策略: {symbol}, {len(df)} rows")


class PipelineManager:
    """
    管道协调器。
    
    负责将 KlineResponse 转换为 Handler 并分发给所有注册的消费者。
    采用 Branching 模式，各消费者独立处理数据。
    """
    
    def __init__(self):
        self._sinks: list[DataSink] = []
    
    def register(self, sink: DataSink) -> "PipelineManager":
        """
        注册数据消费者。
        
        Args:
            sink: 实现 DataSink 协议的消费者
        
        Returns:
            self (支持链式调用)
        """
        self._sinks.append(sink)
        sink_name = getattr(sink, "name", sink.__class__.__name__)
        logger.info(f"[Pipeline] 注册消费者: {sink_name}")
        return self
    
    def unregister(self, sink: DataSink) -> bool:
        """注销消费者。"""
        if sink in self._sinks:
            self._sinks.remove(sink)
            return True
        return False
    
    async def dispatch(self, response: "KlineResponse") -> None:
        """
        分发数据到所有消费者。
        
        Args:
            response: K线响应数据 (Decimal 精度)
        """
        handler = KlineDataHandler(response=response)
        
        for sink in self._sinks:
            try:
                await sink.consume(handler)
            except Exception as e:
                sink_name = getattr(sink, "name", sink.__class__.__name__)
                logger.error(f"[Pipeline] {sink_name} 消费失败: {e}")
    
    @property
    def sink_count(self) -> int:
        """已注册的消费者数量。"""
        return len(self._sinks)


__all__ = [
    "DataSink",
    "BaseSink",
    "Archiver",
    "SharedMemoryWriter",
    "SignalDispatcher",
    "PipelineManager",
]
