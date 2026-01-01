"""
Arrow IPC File Cache Configuration

提供 Arrow 文件缓存的配置模型，支持：
- 全局配置（base_dir, default_ttl）
- 命名空间级别配置
- 热重载能力
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class ArrowCacheNamespaceConfig(BaseModel):
    """单个命名空间的缓存配置"""

    ttl: int = Field(default=300, description="缓存过期时间（秒）")
    enabled: bool = Field(default=True, description="是否启用此命名空间缓存")


class ArrowCacheConfig(BaseModel):
    """Arrow IPC 文件缓存配置"""

    enabled: bool = Field(default=True, description="是否启用 Arrow 文件缓存")
    base_dir: Optional[str] = Field(
        default=None, description="缓存基础目录，None=自动检测（Linux:/dev/shm, Windows:%TEMP%）"
    )
    default_ttl: int = Field(default=300, description="默认缓存过期时间（秒）")
    namespaces: Dict[str, ArrowCacheNamespaceConfig] = Field(
        default_factory=dict, description="各命名空间的独立配置"
    )

    def get_namespace_ttl(self, namespace: str) -> int:
        """获取指定命名空间的 TTL（支持热重载）"""
        if namespace in self.namespaces:
            return self.namespaces[namespace].ttl
        return self.default_ttl

    def is_namespace_enabled(self, namespace: str) -> bool:
        """检查命名空间是否启用"""
        if not self.enabled:
            return False
        if namespace in self.namespaces:
            return self.namespaces[namespace].enabled
        return True


def get_arrow_cache_config() -> ArrowCacheConfig:
    """
    获取当前 Arrow 缓存配置（热重载）

    每次调用都会重新读取配置文件，实现动态更新。
    """
    try:
        from deepsearch.config import Settings

        settings = Settings()

        # 从 cache.arrow 节读取配置
        cache_config = getattr(settings, "cache", None)
        if cache_config and isinstance(cache_config, dict):
            arrow_config = cache_config.get("arrow", {})
            if arrow_config:
                # 转换 namespaces 格式
                namespaces = {}
                raw_ns = arrow_config.get("namespaces", {})
                if isinstance(raw_ns, dict):
                    for name, ns_config in raw_ns.items():
                        if isinstance(ns_config, dict):
                            namespaces[name] = ArrowCacheNamespaceConfig(**ns_config)

                return ArrowCacheConfig(
                    enabled=arrow_config.get("enabled", True),
                    base_dir=arrow_config.get("base_dir"),
                    default_ttl=arrow_config.get("default_ttl", 300),
                    namespaces=namespaces,
                )
    except Exception:
        pass

    # 返回默认配置
    return ArrowCacheConfig()
