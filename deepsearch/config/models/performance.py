"""
Performance configuration models.
"""

from typing import Optional

from pydantic import BaseModel, Field

from deepsearch.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_WORKERS,
    DEFAULT_QUEUE_SIZE,
)


class EventEngineConfig(BaseModel):
    """事件引擎性能配置"""

    queue_size: int = Field(default=50000, description="事件队列大小")
    max_workers: Optional[int] = Field(default=None, description="线程池大小，None表示自动")
    batch_size: int = Field(default=200, description="批处理大小")
    batch_timeout: float = Field(default=0.05, description="批处理超时（秒）")
    enable_dedup: bool = Field(default=True, description="启用事件去重")
    dedup_ttl: int = Field(default=60, description="去重TTL（秒）")
    num_workers: int = Field(default=4, description="工作线程数量")


class MessageBusConfig(BaseModel):
    """消息总线性能配置"""

    enable_compression: bool = Field(default=True, description="启用消息压缩")
    compression_threshold: int = Field(default=1024, description="压缩阈值（字节）")
    enable_deduplication: bool = Field(default=True, description="启用消息去重")
    dedup_ttl: int = Field(default=60, description="去重TTL（秒）")
    dedup_max_size: int = Field(default=10000, description="去重缓存最大大小")


class CacheConfig(BaseModel):
    """缓存性能配置"""

    max_memory_mb: int = Field(default=2048, description="内存缓存大小（MB）")
    enable_redis: bool = Field(default=True, description="启用Redis二级缓存")
    enable_query_cache: bool = Field(default=True, description="启用查询结果缓存")
    query_cache_ttl: int = Field(default=300, description="查询缓存TTL（秒）")
    warmup_enabled: bool = Field(default=True, description="启用缓存预热")


class DatabasePerfConfig(BaseModel):
    """数据库性能配置"""

    pool_size: int = Field(default=50, description="连接池大小")
    max_overflow: int = Field(default=20, description="最大溢出连接数")
    pool_timeout: int = Field(default=30, description="连接池超时（秒）")
    pool_recycle: int = Field(default=3600, description="连接回收时间（秒）")


class WebSocketConfig(BaseModel):
    """WebSocket性能配置"""

    batch_enabled: bool = Field(default=True, description="启用批量发送")
    batch_size: int = Field(default=50, description="批量大小")
    batch_timeout: float = Field(default=0.1, description="批量超时（秒）")
    compression_enabled: bool = Field(default=True, description="启用压缩")
    send_timeout: float = Field(default=0.5, description="单连接发送超时（秒）")
    broadcast_interval: float = Field(default=2.0, description="广播间隔（秒）")


class DataProviderConfig(BaseModel):
    """数据提供者性能配置"""

    request_batch_size: int = Field(default=20, description="请求批处理大小")
    request_batch_timeout: float = Field(default=0.2, description="请求批处理超时（秒）")
    circuit_breaker_threshold: int = Field(default=5, description="断路器阈值")
    circuit_breaker_timeout: int = Field(default=30, description="断路器恢复时间（秒）")
    cache_enabled: bool = Field(default=True, description="启用智能缓存")
    cache_ttl: int = Field(default=60, description="缓存TTL（秒）")


class PerformanceConfig(BaseModel):
    """Performance configuration."""

    # 保留原有字段以保持向后兼容
    max_workers: int = DEFAULT_MAX_WORKERS
    queue_size: int = DEFAULT_QUEUE_SIZE
    batch_size: int = DEFAULT_BATCH_SIZE

    # 新增细分配置
    event_engine: EventEngineConfig = Field(default_factory=EventEngineConfig)
    message_bus: MessageBusConfig = Field(default_factory=MessageBusConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    database: DatabasePerfConfig = Field(default_factory=DatabasePerfConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    data_provider: DataProviderConfig = Field(default_factory=DataProviderConfig)
