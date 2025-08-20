"""
AmazingData 配置模型
"""
from pydantic import BaseModel, Field


class AmazingDataConnectionConfig(BaseModel):
    """AmazingData 连接配置"""
    username: str = Field(default="", description="用户名")
    password: str = Field(default="", description="密码")
    host: str = Field(default="localhost", description="服务器地址")
    port: int = Field(default=8888, description="服务端口")
    timeout: int = Field(default=10, description="连接超时（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    heartbeat_interval: int = Field(default=30, description="心跳间隔（秒）")
    auto_reconnect: bool = Field(default=True, description="自动重连")


class AmazingDataCacheConfig(BaseModel):
    """AmazingData 缓存配置"""
    enabled: bool = Field(default=True, description="是否启用缓存")
    ttl: int = Field(default=300, description="缓存过期时间（秒）")
    max_size: int = Field(default=10000, description="最大缓存条目数")
    clear_on_disconnect: bool = Field(default=False, description="断连时是否清除缓存")


class AmazingDataSubscriptionConfig(BaseModel):
    """AmazingData 订阅配置"""
    enabled: bool = Field(default=True, description="是否启用订阅")
    batch_size: int = Field(default=100, description="批量订阅大小")
    heartbeat_interval: int = Field(default=30, description="订阅心跳间隔（秒）")
    max_symbols: int = Field(default=500, description="最大订阅股票数")
    auto_resubscribe: bool = Field(default=True, description="断线后自动重新订阅")


class AmazingDataQualityConfig(BaseModel):
    """AmazingData 数据质量配置"""
    check_enabled: bool = Field(default=True, description="启用数据质量检查")
    min_completeness: float = Field(default=0.95, description="最小完整性要求")
    alert_on_error: bool = Field(default=True, description="错误时告警")
    validate_timestamps: bool = Field(default=True, description="验证时间戳")


class AmazingDataPerformanceConfig(BaseModel):
    """AmazingData 性能配置"""
    batch_requests: bool = Field(default=True, description="启用批量请求")
    max_concurrent_requests: int = Field(default=10, description="最大并发请求数")
    request_queue_size: int = Field(default=1000, description="请求队列大小")
    use_connection_pool: bool = Field(default=True, description="使用连接池")
    pool_size: int = Field(default=5, description="连接池大小")


class AmazingDataMonitoringConfig(BaseModel):
    """AmazingData 监控配置"""
    enabled: bool = Field(default=True, description="是否启用监控")
    report_interval: int = Field(default=60, description="状态报告间隔（秒）")
    metrics_enabled: bool = Field(default=True, description="启用指标收集")
    log_slow_requests: bool = Field(default=True, description="记录慢请求")
    slow_request_threshold: int = Field(default=1000, description="慢请求阈值（毫秒）")


class AmazingDataConfig(BaseModel):
    """AmazingData 主配置"""
    enabled: bool = Field(default=False, description="是否启用")
    priority: int = Field(default=1, description="优先级")

    connection: AmazingDataConnectionConfig = Field(
        default_factory=AmazingDataConnectionConfig,
        description="连接配置"
    )
    cache: AmazingDataCacheConfig = Field(
        default_factory=AmazingDataCacheConfig,
        description="缓存配置"
    )
    subscription: AmazingDataSubscriptionConfig = Field(
        default_factory=AmazingDataSubscriptionConfig,
        description="订阅配置"
    )
    data_quality: AmazingDataQualityConfig = Field(
        default_factory=AmazingDataQualityConfig,
        description="数据质量配置"
    )
    performance: AmazingDataPerformanceConfig = Field(
        default_factory=AmazingDataPerformanceConfig,
        description="性能配置"
    )
    monitoring: AmazingDataMonitoringConfig = Field(
        default_factory=AmazingDataMonitoringConfig,
        description="监控配置"
    )
