"""
数据源配置模型定义。

该模块为 ``settings.<env>.yaml`` 中 ``data_sources`` 区块提供
结构化的 Pydantic 支持，确保配置项的可验证性与补全能力。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CircuitBreakerConfig(BaseModel):
    """数据源熔断器配置。"""

    enabled: bool = Field(default=True, description="是否启用熔断")
    failure_threshold: int = Field(
        default=5, ge=1, description="连续失败阈值，触发熔断"
    )
    recovery_timeout: int = Field(
        default=60, ge=1, description="熔断后的恢复等待时间（秒）"
    )
    half_open_attempts: int = Field(
        default=3, ge=1, description="半开状态下的重试次数"
    )


class FailoverConfig(BaseModel):
    """数据源故障转移控制。"""

    enabled: bool = Field(default=True, description="是否启用故障转移")
    timeout: float = Field(default=5.0, gt=0, description="单次请求超时时间（秒）")
    retry_count: int = Field(default=3, ge=0, description="最大重试次数")
    backoff_factor: float = Field(
        default=2.0, gt=0, description="指数退避因子（每次重试乘以该因子）"
    )
    jitter: Optional[float] = Field(
        default=None, ge=0, description="可选的随机抖动，用于避免雪崩"
    )


class DataSourceProviderConfig(BaseModel):
    """单个数据源提供者的配置。"""

    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=True, description="是否启用该数据源")
    priority: int = Field(default=100, ge=0, description="优先级，值越小越优先")
    timeout: Optional[float] = Field(
        default=None, gt=0, description="覆盖默认的超时时间（秒）"
    )
    retry_count: Optional[int] = Field(
        default=None, ge=0, description="覆盖默认的重试次数"
    )
    fallback_enabled: bool = Field(default=False, description="是否为该源启用兜底")
    fallback_sources: List[str] = Field(
        default_factory=list, description="该源可回退的数据源列表"
    )
    has_saved_credential: Optional[bool] = Field(
        default=None, description="后端是否已保存凭据"
    )
    provider_name: Optional[str] = Field(
        default=None, description="覆盖注册表中的 provider 名称"
    )
    type: Optional[str] = Field(default=None, description="显式声明的数据源类型")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="提供者特定的嵌套配置"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="用于 UI 展示的附加元信息"
    )

    @field_validator("fallback_sources", mode="after")
    @classmethod
    def _normalise_fallback_sources(
            cls, value: Iterable[str] | None
    ) -> List[str]:
        """去重并清洗兜底数据源列表。"""
        if not value:
            return []
        normalised: List[str] = []
        seen: set[str] = set()
        for item in value:
            name = str(item).strip()
            if not name:
                continue
            lowered = name.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalised.append(name)
        return normalised


class DataSourcesConfig(BaseModel):
    """``data_sources`` 顶层配置。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    default: Optional[str] = Field(
        default="amazingdata", description="默认首选数据源"
    )
    fallback_order: List[str] = Field(
        default_factory=lambda: ["amazingdata", "cloudflare", "akshare"],
        description="全局回退顺序",
    )
    circuit_breaker: CircuitBreakerConfig = Field(
        default_factory=CircuitBreakerConfig
    )
    failover: FailoverConfig = Field(default_factory=FailoverConfig)
    providers: Dict[str, DataSourceProviderConfig] = Field(
        default_factory=dict, description="已声明的数据源提供者集合"
    )

    @field_validator("fallback_order", mode="after")
    @classmethod
    def _deduplicate_fallback_order(cls, value: Iterable[str]) -> List[str]:
        """保证回退顺序唯一且保持原有次序。"""
        result: List[str] = []
        seen: set[str] = set()
        for item in value:
            name = str(item).strip()
            if not name:
                continue
            lowered = name.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            result.append(name)
        return result

    def get_provider(self, name: str) -> Optional[DataSourceProviderConfig]:
        """根据名称读取配置。"""
        key = str(name).strip()
        return self.providers.get(key)

    def iter_enabled_provider_items(self) -> Iterable[tuple[str, DataSourceProviderConfig]]:
        """遍历已启用的数据源。"""
        for name, cfg in self.providers.items():
            if cfg.enabled:
                yield name, cfg
