"""
AmazingData Web API 模块

提供AmazingData SDK功能的RESTful API封装
模块化设计，包含全部37个AmazingData接口

模块结构：
- base.py: 基础工具和共享函数
- basic_data.py: 基础数据接口（10个）
- realtime.py: 实时行情接口（9个）
- history.py: 历史数据接口（3个）
- financial.py: 财务数据接口（6个）
- router.py: 主路由器
- amazingdata_api.py: 原始完整实现（保留兼容性）
"""

# 导入新的模块化路由器
from .router import router as modular_router

# 保留原始路由器以确保兼容性
from .amazingdata_api import router as legacy_router

# 默认导出模块化路由器
main_router = modular_router

__all__ = ['main_router', 'modular_router', 'legacy_router']