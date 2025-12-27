"""
模块注册中心。

提供数据模块的装饰器注册机制和数据库配置访问功能。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar

from loguru import logger

from deepsearch.infrastructure.providers.managers.module_source_config import (
    ModuleSourceConfig as ModuleSourceConfigDTO,
)
from deepsearch.infrastructure.providers.managers.module_source_config import ModuleSourceResolver
from deepsearch.ports.data_sources import DataSourceType

if TYPE_CHECKING:
    from deepsearch.infrastructure.persistence.module_source_repository import (
        ModuleSourceRepository,
    )


@dataclass
class ModuleInfo:
    """数据模块信息。"""

    name: str  # 唯一标识 e.g. "block_trade_detector"
    label: str  # 显示名称 e.g. "市场大单检测"
    description: str = ""  # 描述
    category: str = "general"  # 分类 e.g. "market_analysis"
    default_source: DataSourceType = DataSourceType.AMAZINGDATA
    default_fallback: List[DataSourceType] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）。"""
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "defaultConfig": {
                "primary": self.default_source.value,
                "fallback": [s.value for s in self.default_fallback],
            },
        }


@dataclass
class CategoryInfo:
    """模块分类信息。"""

    key: str
    label: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
        }


# 默认分类（简化为两个）
DEFAULT_CATEGORIES = {
    "market_analysis": CategoryInfo("market_analysis", "行情分析", "实时行情分析与数据同步模块"),
    "general": CategoryInfo("general", "通用", "其他通用模块"),
}


class ModuleRegistry:
    """
    模块注册中心 - 单例模式。

    负责：
    - 模块自注册（装饰器方式）
    - 通过数据库访问配置（支持热更新）
    - 提供模块元数据查询
    """

    _instance: Optional["ModuleRegistry"] = None
    _initialized: bool

    def __new__(cls) -> "ModuleRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._modules: Dict[str, ModuleInfo] = {}
        self._categories: Dict[str, CategoryInfo] = dict(DEFAULT_CATEGORIES)
        self._repository: Optional["ModuleSourceRepository"] = None

    def set_repository(self, repository: "ModuleSourceRepository") -> None:
        """设置数据库 Repository（由应用启动时注入）。"""
        self._repository = repository
        logger.info("ModuleRegistry: 已设置数据库 Repository")

    @property
    def has_repository(self) -> bool:
        """检查是否已设置 Repository。"""
        return self._repository is not None

    def register(self, module_info: ModuleInfo) -> None:
        """注册模块（同步，用于装饰器）。"""
        self._modules[module_info.name] = module_info
        logger.debug(f"注册数据模块: {module_info.name} ({module_info.label})")

    def get_module(self, name: str) -> Optional[ModuleInfo]:
        """获取模块信息。"""
        return self._modules.get(name)

    def get_all_modules(self) -> List[ModuleInfo]:
        """获取所有已注册模块。"""
        return list(self._modules.values())

    def get_modules_by_category(self, category: str) -> List[ModuleInfo]:
        """按分类获取模块。"""
        return [m for m in self._modules.values() if m.category == category]

    def get_all_categories(self) -> List[CategoryInfo]:
        """获取所有分类。"""
        return list(self._categories.values())

    async def get_module_config(self, module_name: str) -> ModuleSourceConfigDTO:
        """获取模块的当前数据源配置（从数据库）。"""
        # 1. 尝试从数据库获取
        if self._repository:
            db_config = await self._repository.get_by_module(module_name)
            if db_config:
                primary = self._parse_source_type(db_config.get("primary_source"))
                fallback = self._parse_source_list(db_config.get("fallback_sources", []))
                return ModuleSourceConfigDTO(primary=primary, fallback=fallback)

        # 2. 使用装饰器注册的默认值
        module_info = self._modules.get(module_name)
        if module_info:
            return ModuleSourceConfigDTO(
                primary=module_info.default_source,
                fallback=list(module_info.default_fallback),
            )

        # 3. 使用全局默认值
        return ModuleSourceConfigDTO(
            primary=DataSourceType.AMAZINGDATA,
            fallback=[DataSourceType.AKSHARE],
        )

    async def get_all_configs(self) -> List[Dict[str, Any]]:
        """获取所有模块配置（用于 API）。"""
        result = []

        # 从数据库获取已保存的配置
        db_configs: Dict[str, Dict] = {}
        if self._repository:
            configs = await self._repository.get_all()
            db_configs = {c["module_name"]: c for c in configs}

        # 合并装饰器注册的模块信息和数据库配置
        all_module_names = set(self._modules.keys()) | set(db_configs.keys())

        for name in sorted(all_module_names):
            module_info = self._modules.get(name)
            db_config = db_configs.get(name)

            entry = {
                "module_name": name,
                "label": db_config.get("label") if db_config else None,
                "description": db_config.get("description") if db_config else None,
                "category": db_config.get("category") if db_config else "general",
                "primary_source": db_config.get("primary_source") if db_config else None,
                "fallback_sources": db_config.get("fallback_sources", []) if db_config else [],
                "enabled": db_config.get("enabled", True) if db_config else True,
            }

            # 填充来自装饰器的默认信息
            if module_info:
                entry["label"] = entry["label"] or module_info.label
                entry["description"] = entry["description"] or module_info.description
                entry["category"] = entry["category"] or module_info.category
                entry["default_config"] = {
                    "primary": module_info.default_source.value,
                    "fallback": [s.value for s in module_info.default_fallback],
                }

            result.append(entry)

        return result

    async def update_module_config(
        self,
        module_name: str,
        *,
        label: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        primary_source: Optional[str] = None,
        fallback_sources: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> bool:
        """更新模块数据源配置（写入数据库，立即生效）。"""
        if not self._repository:
            logger.error("Repository 未设置，无法更新配置")
            return False

        # 如果没有提供 label，尝试从已注册模块获取
        if not label:
            module_info = self._modules.get(module_name)
            if module_info:
                label = module_info.label
                description = description or module_info.description
                category = category or module_info.category

        return await self._repository.upsert(
            module_name=module_name,
            label=label,
            description=description,
            category=category or "general",
            primary_source=primary_source,
            fallback_sources=fallback_sources,
            enabled=enabled,
        )

    async def delete_module_config(self, module_name: str) -> bool:
        """删除模块配置（恢复为默认值）。"""
        if not self._repository:
            logger.error("Repository 未设置，无法删除配置")
            return False

        return await self._repository.delete(module_name)

    def get_resolver(self) -> Optional[ModuleSourceResolver]:
        """获取数据源解析器（同步版，用于兼容）。"""
        # 注意：使用数据库后，解析器需要异步获取配置
        # 这里返回一个空解析器，实际解析由 get_module_config 完成
        return ModuleSourceResolver()

    @staticmethod
    def _parse_source_type(value: Any) -> Optional[DataSourceType]:
        if value is None:
            return None
        if isinstance(value, DataSourceType):
            return value
        try:
            return DataSourceType(str(value).lower())
        except ValueError:
            return None

    @classmethod
    def _parse_source_list(cls, values: Any) -> List[DataSourceType]:
        if not values:
            return []
        if isinstance(values, str):
            values = [values]
        result = []
        for v in values:
            parsed = cls._parse_source_type(v)
            if parsed:
                result.append(parsed)
        return result


# 全局注册表实例
_registry: Optional[ModuleRegistry] = None


def get_module_registry() -> ModuleRegistry:
    """获取全局模块注册表实例。"""
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry


T = TypeVar("T")


def data_module(
    name: str,
    label: str,
    description: str = "",
    category: str = "general",
    default_source: DataSourceType = DataSourceType.AMAZINGDATA,
    default_fallback: Optional[List[DataSourceType]] = None,
) -> Callable[[T], T]:
    """
    装饰器：注册数据模块。

    用法:
        @data_module(
            name="block_trade_detector",
            label="市场大单检测",
            category="market_analysis",
        )
        class BlockTradeDetector:
            ...
    """

    def decorator(cls: T) -> T:
        module_info = ModuleInfo(
            name=name,
            label=label,
            description=description,
            category=category,
            default_source=default_source,
            default_fallback=default_fallback or [],
        )
        get_module_registry().register(module_info)

        # 在类上添加模块信息
        setattr(cls, "_data_module_info", module_info)
        return cls

    return decorator


__all__ = [
    "ModuleInfo",
    "CategoryInfo",
    "ModuleRegistry",
    "get_module_registry",
    "data_module",
]
