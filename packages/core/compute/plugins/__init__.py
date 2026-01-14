"""Dask Worker Plugin 基础架构

提供统一的 Plugin 配置模型和基类，消除代码重复。
"""

from core.compute.plugins.base_plugin import BaseWorkerPlugin
from core.compute.plugins.config import (
    AmazingDataPluginConfig,
    BasePluginConfig,
    MiniQMTPluginConfig,
)

__all__ = [
    "BaseWorkerPlugin",
    "BasePluginConfig",
    "AmazingDataPluginConfig",
    "MiniQMTPluginConfig",
]
