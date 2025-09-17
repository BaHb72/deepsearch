"""
重构后的统一组件模块

注意：这是一个过渡文件，用于标记unified_components.py需要进一步拆分。
实际的拆分工作将分阶段进行，以确保向后兼容性。

计划的模块拆分：
- infrastructure_components.py: EventEngineComponent, MessageBusComponent
- data_components.py: DatabaseComponent, CacheComponent
- monitoring_components.py: MonitorComponent
- gateway_components.py: GatewayComponent, QMTGatewayComponent
- analytics_components.py: AnalyticsComponent
- ui_components.py: WebUIComponent
- backtest_components.py: BacktestComponent

当前状态：
- 已拆分: EventEngineComponent, MessageBusComponent (在components/infrastructure_components.py中)
- 待拆分: 其他组件
"""

# 从新模块导入已拆分的组件
from deepsearch.core.components.infrastructure_components import (
    EventEngineComponent,
    MessageBusComponent
)

# 从原始文件导入尚未拆分的组件（临时措施）
# 注意：这会导致循环导入，所以我们需要直接定义这些类
# 或者保持原始文件不变，直到完全迁移

# 导出所有组件（保持向后兼容）
__all__ = [
    'EventEngineComponent',
    'MessageBusComponent',
    # 其他组件待添加
]

# TODO: 完成所有组件的拆分后，删除此文件并更新所有导入路径