"""
DeepSearch核心组件模块

将原unified_components.py拆分为多个模块，提高可维护性
"""

# 基础设施组件
from .infrastructure_components import (
    EventEngineComponent,
    MessageBusComponent
)

# 数据组件
from .data_components import (
    DatabaseComponent,
    CacheComponent
)

# 监控组件
from .monitoring_components import (
    MonitorComponent
)

# 网关组件
from .gateway_components import (
    GatewayComponent,
    QMTGatewayComponent
)

# 分析组件
from .analytics_components import (
    AnalyticsComponent
)

# UI组件
from .ui_components import (
    WebUIComponent
)

# 回测组件
from .backtest_components import (
    BacktestComponent
)

# 导出所有组件
__all__ = [
    # 基础设施
    'EventEngineComponent',
    'MessageBusComponent',
    # 数据存储
    'DatabaseComponent',
    'CacheComponent',
    # 监控
    'MonitorComponent',
    # 网关
    'GatewayComponent',
    'QMTGatewayComponent',
    # 分析
    'AnalyticsComponent',
    # UI
    'WebUIComponent',
    # 业务
    'BacktestComponent',
]