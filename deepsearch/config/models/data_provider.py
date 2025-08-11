"""
数据提供者配置模型

定义数据源和代理相关的配置结构。
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ProxyConfigModel(BaseModel):
    """代理配置模型"""
    enabled: bool = Field(default=False, description="是否启用代理")
    pool_size: int = Field(default=10, description="代理池大小")
    rotation_strategy: str = Field(
        default="round-robin",
        description="轮换策略: round-robin, random, weighted, least-used"
    )
    health_check_interval: int = Field(default=60, description="健康检查间隔（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout: int = Field(default=10, description="请求超时时间（秒）")
    proxy_list: List[str] = Field(default_factory=list, description="静态代理列表")
    proxy_api_url: Optional[str] = Field(default=None, description="动态代理API")
    proxy_api_key: Optional[str] = Field(default=None, description="API密钥")
    blacklist_threshold: int = Field(default=5, description="黑名单阈值")
    blacklist_duration: int = Field(default=300, description="黑名单持续时间（秒）")


class AkShareConfigModel(BaseModel):
    """AkShare配置模型"""
    enabled: bool = Field(default=False, description="是否启用")
    max_concurrent: int = Field(default=5, description="最大并发数")
    rate_limit: float = Field(default=0, description="请求速率限制（请求/秒）")
    retry_times: int = Field(default=3, description="重试次数")
    retry_delay: float = Field(default=1.0, description="重试延迟（秒）")
    timeout: int = Field(default=30, description="超时时间（秒）")
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl: int = Field(default=300, description="缓存过期时间（秒）")
    proxy: ProxyConfigModel = Field(default_factory=ProxyConfigModel, description="代理配置")

    # AkShare特定配置
    use_cdn: bool = Field(default=False, description="是否使用CDN加速")
    fallback_sources: List[str] = Field(
        default_factory=lambda: ["sina", "eastmoney"],
        description="备用数据源"
    )


class TushareConfigModel(BaseModel):
    """Tushare配置模型"""
    enabled: bool = Field(default=False, description="是否启用")
    token: Optional[str] = Field(default=None, description="Tushare token")
    use_pro: bool = Field(default=True, description="是否使用Pro接口")
    max_concurrent: int = Field(default=3, description="最大并发数")
    rate_limit: float = Field(default=0.5, description="请求速率限制（请求/秒）")
    retry_times: int = Field(default=3, description="重试次数")
    retry_delay: float = Field(default=2.0, description="重试延迟（秒）")
    timeout: int = Field(default=30, description="超时时间（秒）")
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl: int = Field(default=600, description="缓存过期时间（秒）")

    # Tushare特定配置
    point_threshold: int = Field(default=100, description="积分使用阈值")
    prefer_basic: bool = Field(default=True, description="优先使用基础接口")


class DataProviderConfigModel(BaseModel):
    """数据提供者总配置"""
    enabled: bool = Field(default=True, description="是否启用数据提供者模块")
    default_source: str = Field(default="auto", description="默认数据源")

    # 各数据源配置
    akshare: AkShareConfigModel = Field(
        default_factory=AkShareConfigModel,
        description="AkShare配置"
    )
    tushare: TushareConfigModel = Field(
        default_factory=TushareConfigModel,
        description="Tushare配置"
    )

    # 全局代理配置（可被各数据源覆盖）
    global_proxy: ProxyConfigModel = Field(
        default_factory=ProxyConfigModel,
        description="全局代理配置"
    )

    # 性能配置
    max_cache_size: int = Field(default=1000, description="最大缓存条目数")
    cache_cleanup_interval: int = Field(default=3600, description="缓存清理间隔（秒）")

    class Config:
        schema_extra = {
            "example": {
                "enabled": True,
                "default_source": "auto",
                "akshare": {
                    "enabled": True,
                    "max_concurrent": 5,
                    "proxy": {
                        "enabled": True,
                        "proxy_list": [
                            "http://proxy1.example.com:8080",
                            "http://proxy2.example.com:8080"
                        ],
                        "rotation_strategy": "weighted"
                    }
                },
                "tushare": {
                    "enabled": True,
                    "token": "your_token_here",
                    "use_pro": True
                }
            }
        }
