"""
模块级数据源配置解析器。

支持按模块(module)或访问类型(access_type)指定数据源优先级，
覆盖全局默认配置。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from loguru import logger

from deepsearch.ports.data_sources import DataAccessType, DataSourceType


@dataclass
class ModuleSourceConfig:
    """单个模块的数据源配置。"""

    primary: Optional[DataSourceType] = None
    fallback: List[DataSourceType] = field(default_factory=list)

    def get_source_order(self) -> List[DataSourceType]:
        """获取该配置的数据源顺序列表。"""
        sources: List[DataSourceType] = []
        if self.primary:
            sources.append(self.primary)
        sources.extend(self.fallback)
        return sources


class ModuleSourceResolver:
    """
    模块级数据源解析器。
    
    优先级（从高到低）：
    1. module_overrides[module_name]
    2. access_type_overrides[access_type]
    3. 全局 fallback_order / default
    """

    def __init__(
            self,
            module_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
            access_type_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
            global_default: Optional[str] = None,
            global_fallback_order: Optional[Sequence[str]] = None,
    ) -> None:
        self._module_configs: Dict[str, ModuleSourceConfig] = {}
        self._access_type_configs: Dict[DataAccessType, ModuleSourceConfig] = {}
        self._global_default = self._parse_source_type(global_default)
        self._global_fallback_order = self._parse_source_list(global_fallback_order or [])

        # 解析 module_overrides
        if module_overrides:
            for module_name, config in module_overrides.items():
                self._module_configs[module_name] = self._parse_module_config(config)

        # 解析 access_type_overrides
        if access_type_overrides:
            for access_type_str, config in access_type_overrides.items():
                try:
                    access_type = DataAccessType(access_type_str)
                    self._access_type_configs[access_type] = self._parse_module_config(config)
                except ValueError:
                    logger.warning(f"Unknown access_type in overrides: {access_type_str}")

    @staticmethod
    def _parse_source_type(value: Any) -> Optional[DataSourceType]:
        """解析单个数据源类型。"""
        if value is None:
            return None
        if isinstance(value, DataSourceType):
            return value
        if isinstance(value, str):
            try:
                return DataSourceType(value.lower())
            except ValueError:
                logger.warning(f"Unknown data source type: {value}")
                return None
        return None

    @classmethod
    def _parse_source_list(cls, values: Sequence[Any]) -> List[DataSourceType]:
        """解析数据源类型列表。"""
        result: List[DataSourceType] = []
        for v in values:
            parsed = cls._parse_source_type(v)
            if parsed:
                result.append(parsed)
        return result

    @classmethod
    def _parse_module_config(cls, config: Mapping[str, Any]) -> ModuleSourceConfig:
        """解析单个模块配置。"""
        primary = cls._parse_source_type(config.get("primary"))
        fallback_raw = config.get("fallback", [])
        if isinstance(fallback_raw, str):
            fallback_raw = [fallback_raw]
        fallback = cls._parse_source_list(fallback_raw)
        return ModuleSourceConfig(primary=primary, fallback=fallback)

    def resolve(
            self,
            module: Optional[str] = None,
            access_type: Optional[DataAccessType] = None,
    ) -> List[DataSourceType]:
        """
        解析特定上下文的数据源顺序。
        
        Args:
            module: 模块名称（如 "market_strength"）
            access_type: 数据访问类型
        
        Returns:
            数据源类型列表（按优先级排序）
        """
        # 1. 首先检查 module_overrides
        if module and module in self._module_configs:
            sources = self._module_configs[module].get_source_order()
            if sources:
                logger.debug(f"Using module override for '{module}': {sources}")
                return sources

        # 2. 然后检查 access_type_overrides
        if access_type and access_type in self._access_type_configs:
            sources = self._access_type_configs[access_type].get_source_order()
            if sources:
                logger.debug(f"Using access_type override for '{access_type}': {sources}")
                return sources

        # 3. 回退到全局配置
        if self._global_fallback_order:
            return list(self._global_fallback_order)

        if self._global_default:
            return [self._global_default]

        return []

    def get_module_names(self) -> List[str]:
        """获取所有已配置的模块名称。"""
        return list(self._module_configs.keys())

    def get_access_types(self) -> List[DataAccessType]:
        """获取所有已配置覆盖的访问类型。"""
        return list(self._access_type_configs.keys())


def create_resolver_from_config(data_sources_config: Mapping[str, Any]) -> ModuleSourceResolver:
    """
    从 data_sources 配置创建解析器。
    
    Args:
        data_sources_config: settings.yaml 中的 data_sources 配置块
    
    Returns:
        ModuleSourceResolver 实例
    """
    return ModuleSourceResolver(
        module_overrides=data_sources_config.get("module_overrides"),
        access_type_overrides=data_sources_config.get("access_type_overrides"),
        global_default=data_sources_config.get("default"),
        global_fallback_order=data_sources_config.get("fallback_order"),
    )


__all__ = [
    "ModuleSourceConfig",
    "ModuleSourceResolver",
    "create_resolver_from_config",
]
