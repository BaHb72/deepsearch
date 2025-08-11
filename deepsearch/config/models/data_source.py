"""
数据源配置模型
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WorkerNode(BaseModel):
    """Worker 节点配置"""
    url: str
    region: str
    weight: int = 1
    enabled: bool = True


class CloudflareConfig(BaseModel):
    """Cloudflare 配置"""
    api_key: str = Field(default="", description="API 密钥")
    secret_key: str = Field(default="", description="签名密钥")
    workers: List[str] = Field(default_factory=lambda: [
        "https://wandering-sea-d394.934073514.workers.dev"
    ], description="Worker 节点列表")
    worker_url: Optional[str] = Field(default=None, description="单个 Worker URL（向后兼容）")
    tunnel_id: Optional[str] = Field(default=None, description="Tunnel ID")
    zone_id: Optional[str] = Field(default=None, description="Zone ID")
    api_token: Optional[str] = Field(default=None, description="API Token")


class DataSourceConfig(BaseModel):
    """数据源配置"""
    name: str
    provider: str  # akshare, akshare_proxy, etc.
    display_name: Optional[str] = None

    # 代理配置
    use_proxy: bool = False
    worker_nodes: List[WorkerNode] = Field(default_factory=list)

    # 认证配置
    api_key: Optional[str] = None
    secret_key: Optional[str] = None

    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: Dict[str, int] = Field(default_factory=lambda: {
        "realtime": 5,
        "minute": 60,
        "daily": 3600,
        "history": 86400
    })

    # 限流配置
    rate_limit: Dict[str, int] = Field(default_factory=lambda: {
        "max_requests": 100,
        "time_window": 60
    })

    # 重试配置
    retry_config: Dict[str, int] = Field(default_factory=lambda: {
        "max_retries": 3,
        "initial_delay": 1,
        "max_delay": 30
    })

    # 是否启用
    enabled: bool = True


class DataProviderSettings(BaseModel):
    """数据提供者设置"""
    providers: List[DataSourceConfig] = Field(default_factory=list)
    default_provider: str = "akshare_proxy"

    # 全局缓存设置
    global_cache: bool = True
    cache_backend: str = "memory"  # memory, redis

    # 全局限流设置
    global_rate_limit: bool = False
    max_concurrent_requests: int = 10
