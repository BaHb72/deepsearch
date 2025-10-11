"""向后兼容的导出模块。

旧版代码可能仍从 ``deepsearch.core.components.analytics_component``
 导入 ``AnalyticsComponent``。为避免重复实现与类型不一致问题，
 这里直接复用新的 ``analytics_components`` 模块中的实现。
"""

from __future__ import annotations

from .analytics_components import AnalyticsComponent

__all__ = ["AnalyticsComponent"]

