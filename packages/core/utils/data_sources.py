# mypy: ignore-errors
"""数据源工具函数，保证测试环境也能加载真实实现。"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, cast

from core.ports.data_sources import DataSourceType as PortDataSourceType

_MODULE_NAME = "deepsearch.infrastructure.providers.managers.data_source_manager"


def _is_stub_module(module: ModuleType | None) -> bool:
    if module is None:
        return True

    manager_cls = getattr(module, "DataSourceManager", None)
    if not isinstance(manager_cls, type):
        return True

    return not hasattr(manager_cls, "execute_with_fallback")


def _load_real_module() -> ModuleType:
    module: ModuleType | None = sys.modules.get(_MODULE_NAME)
    if module is None or _is_stub_module(module):
        module_path = (
            Path(__file__).resolve().parent.parent
            / "infrastructure"
            / "providers"
            / "managers"
            / "data_source_manager.py"
        )
        spec = importlib.util.spec_from_file_location(_MODULE_NAME, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载数据源管理模块: {_MODULE_NAME}")

        real_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(real_module)
        sys.modules[_MODULE_NAME] = real_module
        module = real_module

    if module is None:
        raise ImportError(f"模块 {_MODULE_NAME} 加载失败")

    return module


def _call(module_attr: str, *args: Any, **kwargs: Any) -> Any:
    module = _load_real_module()
    target: Callable[..., Any] = getattr(module, module_attr)
    return target(*args, **kwargs)


def get_data_source_manager() -> "DataSourceManager":
    """获取真实的数据源管理器实例。"""

    manager = _call("get_data_source_manager")
    return cast("DataSourceManager", manager)


async def initialize_data_sources():
    """初始化数据源系统，代理真实模块的同名函数。"""

    module = _load_real_module()
    initializer = getattr(module, "initialize_data_sources")
    return await initializer()


if TYPE_CHECKING:  # pragma: no cover - 仅用于类型提示
    from core.infrastructure.providers.managers.data_source_manager import (
        DataSourceConfig as _DataSourceConfig,
    )
    from core.infrastructure.providers.managers.data_source_manager import (
        DataSourceLifecycleStatus as _DataSourceLifecycleStatus,
    )
    from core.infrastructure.providers.managers.data_source_manager import (
        DataSourceManager as _DataSourceManager,
    )

    DataSourceConfig = _DataSourceConfig
    DataSourceLifecycleStatus = _DataSourceLifecycleStatus
    DataSourceManager = _DataSourceManager
else:
    # 重新导出模型与类型，供运行时调用方直接使用。
    _module = _load_real_module()

    DataSourceConfig = getattr(_module, "DataSourceConfig")
    DataSourceLifecycleStatus = getattr(_module, "DataSourceLifecycleStatus")
    DataSourceManager = getattr(_module, "DataSourceManager")

DataSourceType = PortDataSourceType

__all__ = [
    "DataSourceConfig",
    "DataSourceLifecycleStatus",
    "DataSourceManager",
    "DataSourceType",
    "get_data_source_manager",
    "initialize_data_sources",
]
