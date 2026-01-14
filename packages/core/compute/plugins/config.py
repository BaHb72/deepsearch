"""Dask Worker Plugin 配置模型

使用 Pydantic 提供类型安全的配置验证。
"""

from pydantic import BaseModel, Field


class BasePluginConfig(BaseModel):
    """Plugin 配置基类"""

    redis_url: str = Field(default="redis://localhost:6379")
    only_on_windows: bool = Field(default=True)


class AmazingDataPluginConfig(BasePluginConfig):
    """AmazingData Plugin 配置

    注意: 此配置模型只包含 Plugin 层需要的字段。
    Actor 配置由 Plugin 内部从 settings.yaml 的 connection 内层提取。
    """

    # Plugin 层配置（从外部传入）
    redis_url: str = Field(default="redis://localhost:6379")
    only_on_windows: bool = Field(default=True)


class MiniQMTPluginConfig(BasePluginConfig):
    """MiniQMT Plugin 配置"""

    cache_ttl: int = Field(default=300)
    failure_threshold: int = Field(default=5)
    recovery_timeout: int = Field(default=60)
