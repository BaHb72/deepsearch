"""
数据源配置模型

整合数据提供者和数据源的配置
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProxyConfigModel(BaseModel):
    """代理配置模型"""

    enabled: bool = Field(default=False, description="是否启用代理")
    pool_size: int = Field(default=10, description="代理池大小")
    rotation_strategy: str = Field(
        default="round-robin", description="轮换策略: round-robin, random, weighted, least-used"
    )
    health_check_interval: int = Field(default=60, description="健康检查间隔（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout: int = Field(default=10, description="请求超时时间（秒）")
    proxy_list: List[str] = Field(default_factory=list, description="静态代理列表")
    proxy_api_url: Optional[str] = Field(default=None, description="动态代理API")
    proxy_api_key: Optional[str] = Field(default=None, description="API密钥")
    blacklist_threshold: int = Field(default=5, description="黑名单阈值")
    blacklist_duration: int = Field(default=300, description="黑名单持续时间（秒）")


class WorkerNode(BaseModel):
    """Worker 节点配置"""

    url: str
    region: str
    weight: int = 1
    enabled: bool = True


class CloudflareConfig(BaseModel):
    """Cloudflare Workers 配置"""

    api_key: str = Field(default="", description="API 密钥")
    secret_key: str = Field(default="", description="签名密钥")
    workers: List[str] = Field(
        default_factory=lambda: ["https://akshare-proxy.934073514.workers.dev"],
        description="Worker 节点列表",
    )
    worker_url: Optional[str] = Field(default=None, description="单个 Worker URL（向后兼容）")


class AkShareConfigModel(BaseModel):
    """AkShare配置模型"""

    enabled: bool = Field(default=True, description="是否启用")
    cache_ttl: int = Field(default=300, description="缓存过期时间（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    use_cache: bool = Field(default=True, description="是否使用缓存")
    proxy: Optional[ProxyConfigModel] = Field(default=None, description="代理配置")


class DataSourceConfig(BaseModel):
    """数据源配置"""

    name: str
    provider: str  # akshare, cloudflare, qmt, etc.
    enabled: bool = True
    priority: int = 0  # 优先级，数字越小优先级越高
    config: Optional[Dict] = None


class DataFeedConfig(BaseModel):
    """数据源总配置"""

    default: str = Field(default="akshare", description="默认数据源")
    sources: List[DataSourceConfig] = Field(default_factory=list, description="数据源列表")
    akshare: Optional[AkShareConfigModel] = Field(default=None, description="AkShare配置")
    cloudflare: Optional[CloudflareConfig] = Field(default=None, description="Cloudflare配置")
    proxy: Optional[ProxyConfigModel] = Field(default=None, description="全局代理配置")
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl: int = Field(default=300, description="默认缓存时间（秒）")
    fallback_enabled: bool = Field(default=True, description="是否启用故障转移")
