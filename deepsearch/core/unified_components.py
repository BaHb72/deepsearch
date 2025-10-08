"""
统一的系统组件实现 - 向后兼容层

此文件现在作为向后兼容层，所有组件已拆分到独立模块中。
保留此文件以避免破坏现有导入。

重构日期: 2025-09-14
"""

# 导入所有已拆分的组件
from .components import (  # 基础设施组件; 数据组件; 监控组件; 网关组件; 分析组件; UI组件; 业务组件
    AnalyticsComponent,
    BacktestComponent,
    CacheComponent,
    DatabaseComponent,
    EventEngineComponent,
    GatewayComponent,
    MessageBusComponent,
    MonitorComponent,
    QMTGatewayComponent,
    WebUIComponent,
)

# 导出所有组件，保持向后兼容
__all__ = [
    "EventEngineComponent",
    "MessageBusComponent",
    "DatabaseComponent",
    "CacheComponent",
    "MonitorComponent",
    "GatewayComponent",
    "QMTGatewayComponent",
    "AnalyticsComponent",
    "WebUIComponent",
    "BacktestComponent",
]

# 添加弃用警告
import warnings


def _show_deprecation_warning():
    warnings.warn(
        "直接从 'unified_components' 导入组件已弃用。"
        "请使用 'from deepsearch.core.components import XXXComponent' 代替。"
        "此兼容层将在未来版本中移除。",
        DeprecationWarning,
        stacklevel=2,
    )


# 在模块导入时显示警告
_show_deprecation_warning()
