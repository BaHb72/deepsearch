"""
能力矩阵及相关响应结构的 TypedDict 定义。

这些类型在多个 WebUI API 模块之间共享，确保能力矩阵、差异对比、
推荐等结构在 mypy 校验时保持一致。
"""

from __future__ import annotations

from typing import Final, Literal, NotRequired, Sequence, TypedDict

from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability

CapabilityStatus = Literal["success"]
CAPABILITY_STATUS_SUCCESS: Final[CapabilityStatus] = "success"

# --------------------------- 基础结构定义 --------------------------- #

DataSourceSlug = Literal[
    "amazingdata",
    "cloudflare",
    "akshare",
    "akshare_proxy",
    "akshare_direct",
    "qmt",
    "miniqmt",
    "unified",
    "tushare",
    "eastmoney",
    "sina",
    "direct_api",
    "database",
    "default",
    "custom",
]


class SourceMetadata(TypedDict, total=False):
    """数据源元信息。"""

    name: str
    label: str
    description: str
    badge: str
    color: str
    priority: int
    unique_features: list[str]
    connection_type: Literal["remote", "local"]
    requires_auth: bool
    cost: Literal["paid", "free"]
    enabled: NotRequired[bool]


class CapabilityCategoryMeta(TypedDict):
    """能力分类的配置元数据。"""

    name: str
    capabilities: Sequence[DataCapability]


class CapabilityInfo(TypedDict):
    """单项能力描述。"""

    supported: bool
    name: str


class CapabilityLabel(TypedDict):
    """用于能力矩阵分类展示的标签。"""

    id: str
    name: str


class CapabilityItem(TypedDict):
    """包含能力状态的分类条目。"""

    id: str
    name: str
    supported: bool


class CapabilityCategorySummary(TypedDict):
    """能力分类统计摘要。"""

    name: str
    capabilities: list[CapabilityItem]
    support_rate: str


class SourceCapabilitySummary(SourceMetadata):
    """单个数据源能力矩阵汇总。"""

    supported_count: int
    total_count: int
    coverage_rate: str
    capabilities: dict[str, CapabilityInfo]


class SourceOverview(SourceMetadata, total=False):
    """能力对比场景下的源信息概览。"""

    id: DataSourceSlug


class CapabilityMatrixCategory(TypedDict):
    """能力矩阵中分类板块的展示形态。"""

    name: str
    capabilities: list[CapabilityLabel]


class CapabilityMatrix(TypedDict):
    """能力矩阵主体结构。"""

    sources: dict[DataSourceSlug, SourceCapabilitySummary]
    categories: dict[str, CapabilityMatrixCategory]


class CapabilitySummary(TypedDict):
    """能力支持情况摘要数字。"""

    total: int
    supported: int
    unsupported: int


class CapabilitySummaryData(SourceMetadata, total=False):
    """单个数据源能力详情响应的 data 部分。"""

    categorized_capabilities: dict[str, CapabilityCategorySummary]
    summary: CapabilitySummary


class CapabilityMatrixResponse(TypedDict):
    """能力矩阵接口统一响应结构。"""

    status: CapabilityStatus
    data: CapabilityMatrix


class CapabilitySummaryResponse(TypedDict):
    """单个数据源能力详情接口响应结构。"""

    status: CapabilityStatus
    data: CapabilitySummaryData


# --------------------------- 差异分析结构 --------------------------- #

DiffType = Literal["all_support", "partial_support", "none_support"]


class CapabilityComparisonEntry(TypedDict):
    """不同数据源之间能力对比记录。"""

    name: str
    sources: dict[DataSourceSlug, bool]
    diff_type: DiffType


class CapabilityDiffStats(TypedDict):
    """能力差异统计信息。"""

    all_support: list[str]
    partial_support: list[str]
    none_support: list[str]
    unique_features: dict[DataSourceSlug, list[str]]


class CapabilityRecommendation(TypedDict):
    """能力推荐列表条目。"""

    source: DataSourceSlug
    name: str
    label: str
    cost: str
    score: int
    reason: str


class CapabilityAlternative(TypedDict):
    """当能力不支持时的备选数据源。"""

    source: DataSourceSlug
    name: str
    cost: str


class CapabilityComparisonData(TypedDict):
    """能力对比接口的数据结构。"""

    sources: dict[DataSourceSlug, SourceOverview]
    comparison: dict[str, CapabilityComparisonEntry]
    statistics: CapabilityDiffStats


class CapabilityComparisonResponse(TypedDict):
    """能力对比接口响应。"""

    status: CapabilityStatus
    data: CapabilityComparisonData


class CapabilityDescriptor(TypedDict):
    """能力的基础描述信息。"""

    id: str
    name: str


class CapabilityRecommendationData(TypedDict, total=False):
    """能力推荐接口的数据结构。"""

    capability: CapabilityDescriptor
    recommendations: list[CapabilityRecommendation]
    best_choice: CapabilityRecommendation | None
    message: NotRequired[str]


class CapabilityRecommendationResponse(TypedDict):
    """能力推荐接口响应。"""

    status: CapabilityStatus
    data: CapabilityRecommendationData


class CapabilitySourceInfo(TypedDict):
    """能力可用性接口中的源信息。"""

    id: DataSourceSlug
    name: str


class CapabilityAvailabilityData(TypedDict):
    """能力可用性接口数据。"""

    source: CapabilitySourceInfo
    feature: CapabilityDescriptor
    available: bool
    alternatives: list[CapabilityAlternative]
    message: str


class CapabilityAvailabilityResponse(TypedDict):
    """能力可用性接口响应。"""

    status: CapabilityStatus
    data: CapabilityAvailabilityData


__all__ = [
    "CAPABILITY_STATUS_SUCCESS",
    "CapabilityStatus",
    "CapabilityAlternative",
    "CapabilityAvailabilityData",
    "CapabilityAvailabilityResponse",
    "CapabilityCategoryMeta",
    "CapabilityCategorySummary",
    "CapabilityComparisonEntry",
    "CapabilityComparisonData",
    "CapabilityComparisonResponse",
    "CapabilityDiffStats",
    "CapabilityInfo",
    "CapabilityItem",
    "CapabilityLabel",
    "CapabilityMatrix",
    "CapabilityMatrixCategory",
    "CapabilityMatrixResponse",
    "CapabilityRecommendation",
    "CapabilityRecommendationData",
    "CapabilityRecommendationResponse",
    "CapabilitySummary",
    "CapabilitySummaryResponse",
    "CapabilitySummaryData",
    "CapabilityDescriptor",
    "DataSourceSlug",
    "DiffType",
    "SourceCapabilitySummary",
    "SourceOverview",
    "SourceMetadata",
    "CapabilitySourceInfo",
]
