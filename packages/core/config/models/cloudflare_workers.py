"""
Cloudflare Workers 配置模型
"""

from pydantic import AliasChoices, BaseModel, Field


class CloudflareWorkersConfig(BaseModel):
    """Cloudflare Workers 代理配置"""

    # 基本配置
    url: str = Field(default="", description="Worker URL，例如: your-worker.workers.dev")

    # 认证配置
    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("api_key", "auth_key"),
        description="API 密钥，用于 Worker 认证（兼容 auth_key）",
    )

    # 故障转移配置
    fallback_to_direct: bool = Field(default=True, description="Worker 不可用时是否回退到直连模式")

    # 请求配置
    timeout: int = Field(default=30, description="请求超时时间（秒）")

    retry_count: int = Field(default=3, description="请求重试次数")

    use_system_proxy: bool = Field(
        default=True, description="是否使用系统代理（环境变量 + Windows 系统代理）"
    )

    prefer_ipv4_fallback: bool = Field(
        default=True, description="代理请求连接超时时是否自动回退为 IPv4 重试"
    )

    # 缓存配置
    cache_enabled: bool = Field(default=True, description="是否启用本地缓存")

    cache_ttl: int = Field(default=300, description="缓存过期时间（秒）")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "my-worker.workers.dev",
                    "api_key": "",
                    "fallback_to_direct": True,
                    "timeout": 30,
                    "retry_count": 3,
                    "use_system_proxy": True,
                    "prefer_ipv4_fallback": True,
                    "cache_enabled": True,
                    "cache_ttl": 300,
                }
            ]
        }
    }

    def is_configured(self) -> bool:
        """检查是否已配置 Worker"""
        return bool(self.url)

    def get_full_url(self) -> str:
        """获取完整的 Worker URL"""
        if not self.url:
            return ""

        if self.url.startswith(("http://", "https://")):
            return self.url

        # 默认使用 HTTPS
        return f"https://{self.url}"

    def get_proxy_url(self) -> str:
        """获取代理端点 URL"""
        base_url = self.get_full_url()
        if not base_url:
            return ""

        # 确保 URL 末尾没有斜杠
        base_url = base_url.rstrip("/")
        return f"{base_url}/proxy"

    def __str__(self) -> str:
        """字符串表示"""
        if self.is_configured():
            return f"CloudflareWorkers(url={self.url}, fallback={self.fallback_to_direct})"
        return "CloudflareWorkers(not configured)"

    @property
    def auth_key(self) -> str:
        """兼容旧字段名 auth_key。"""
        return self.api_key
