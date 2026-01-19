"""AmazingData 配置模型"""

from typing import Dict, List, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field, model_validator

_PLACEHOLDER_VALUES = {
    "your_amazingdata_username",
    "your_amazingdata_password",
}
_DEFAULT_HOSTS = {"localhost", "127.0.0.1"}
_DEFAULT_PORT = 8888


class AmazingDataProviderConfigPayload(TypedDict, total=False):
    """AmazingData Provider 构造参数的类型定义。"""

    username: str
    password: str
    host: str
    port: int
    enabled: bool
    priority: int
    timeout: float
    heartbeat_interval: int
    auto_reconnect: bool
    subscription_enabled: bool
    subscription_batch_size: int
    max_subscriptions: int
    cache_enabled: bool
    cache_ttl: int
    reconnect_interval: NotRequired[int]
    tgw_log_path: NotRequired[str]
    worker_env: NotRequired[Dict[str, str]]


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
    python_interpreter_path: str = Field(
        default="", description="指定 Python 解释器路径（用于 AmazingData Worker）"
    )
    tgw_log_path: str = Field(
        default="",
        description="TGW 日志所在路径（可为目录或文件，用于自检与告警增强）",
    )

    def _collect_activation_errors(self) -> List[str]:
        """在启用模式下收集所有显著的配置错误。"""

        errors: List[str] = []

        username = (self.username or "").strip()
        if not username or username in _PLACEHOLDER_VALUES:
            errors.append("用户名未配置或仍为占位符")

        password = (self.password or "").strip()
        if not password or password in _PLACEHOLDER_VALUES:
            errors.append("密码未配置或仍为占位符")

        host = (self.host or "").strip().lower()
        if not host or host in _DEFAULT_HOSTS:
            errors.append("host 不能使用默认的 localhost/127.0.0.1")

        if not isinstance(self.port, int) or self.port <= 0 or self.port > 65535:
            errors.append("端口需要在 1-65535 之间")
        elif self.port == _DEFAULT_PORT:
            errors.append("端口仍为默认的 8888，需要填写实际服务端口")

        return errors


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
    """AmazingData 配置"""

    enabled: bool = Field(default=False, description="是否启用")
    implementation_mode: Literal["optimized", "process"] = Field(
        default="optimized",
        description="指定实现模式：optimized 为增强实现，process 为子进程隔离方案",
    )
    mode: Literal["local", "distributed"] = Field(
        default="local",
        description="运行模式: local=直接SDK调用, distributed=通过Dask分布式调用",
    )
    dask_scheduler_address: str | None = Field(
        default=None,
        description="Dask Scheduler 地址 (distributed 模式必需，如 tcp://localhost:8786)",
    )
    priority: int = Field(default=1, description="优先级")
    worker_env: Dict[str, str] = Field(
        default_factory=dict, description="AmazingData Worker 环境变量覆盖"
    )
    prewarm: bool = Field(
        default=True,
        description="启动时同步预热登录，消除首次调用延迟（distributed 模式）",
    )

    connection: AmazingDataConnectionConfig = Field(
        default_factory=AmazingDataConnectionConfig, description="连接配置"
    )
    cache: AmazingDataCacheConfig = Field(
        default_factory=AmazingDataCacheConfig, description="缓存配置"
    )
    subscription: AmazingDataSubscriptionConfig = Field(
        default_factory=AmazingDataSubscriptionConfig, description="订阅配置"
    )
    data_quality: AmazingDataQualityConfig = Field(
        default_factory=AmazingDataQualityConfig, description="数据质量配置"
    )
    performance: AmazingDataPerformanceConfig = Field(
        default_factory=AmazingDataPerformanceConfig, description="性能配置"
    )
    monitoring: AmazingDataMonitoringConfig = Field(
        default_factory=AmazingDataMonitoringConfig, description="监控配置"
    )

    def to_provider_payload(self) -> AmazingDataProviderConfigPayload:
        """将 Pydantic 配置转换为 AmazingDataProvider 构造参数"""

        payload: AmazingDataProviderConfigPayload = {
            "username": self.connection.username,
            "password": self.connection.password,
            "host": self.connection.host,
            "port": self.connection.port,
            "enabled": self.enabled,
            "priority": self.priority,
            "timeout": float(self.connection.timeout),
            "heartbeat_interval": self.connection.heartbeat_interval,
            "auto_reconnect": self.connection.auto_reconnect,
            "subscription_enabled": self.subscription.enabled,
            "subscription_batch_size": self.subscription.batch_size,
            "max_subscriptions": self.subscription.max_symbols,
            "cache_enabled": self.cache.enabled,
            "cache_ttl": self.cache.ttl,
        }

        if self.worker_env:
            payload["worker_env"] = dict(self.worker_env)

        if self.connection.tgw_log_path:
            payload["tgw_log_path"] = self.connection.tgw_log_path

        return payload

    @model_validator(mode="after")
    def _validate_connection_when_enabled(self) -> "AmazingDataConfig":
        """确保启用 AmazingData 时连接参数有效"""

        if not self.enabled:
            return self

        errors = self.connection._collect_activation_errors()
        if errors:
            joined = "；".join(errors)
            raise ValueError(
                f"AmazingData 连接配置无效：{joined}。请检查 settings.<env>.yaml 中 amazingdata.connection 的必填字段"
            )

        return self

    @model_validator(mode="after")
    def _validate_distributed_mode(self) -> "AmazingDataConfig":
        """确保 distributed 模式时 dask_scheduler_address 已配置"""

        if self.mode == "distributed" and not self.dask_scheduler_address:
            raise ValueError(
                "AmazingData distributed 模式需要配置 dask_scheduler_address，"
                "请设置为 Dask Scheduler 地址，如 tcp://localhost:8786"
            )

        return self

    def ensure_connection_ready(self) -> None:
        """显式触发连接配置校验（供运行期二次校验使用）。"""

        if self.enabled:
            errors = self.connection._collect_activation_errors()
            if errors:
                joined = "；".join(errors)
                raise ValueError(joined)
