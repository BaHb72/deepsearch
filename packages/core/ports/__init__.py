"""Ports 模块，集中维护跨层协议定义。"""

from .concept_engine import ConceptDataProviderPort
from .data_sources import (
    DataAccessType,
    DataSourceRuntimeSnapshot,
    DataSourceType,
    ProviderConfigSnapshot,
    ProviderConfigUpdate,
)

__all__ = [
    "DataSourceType",
    "DataAccessType",
    "ConceptDataProviderPort",
    "ProviderConfigSnapshot",
    "ProviderConfigUpdate",
    "DataSourceRuntimeSnapshot",
]
