"""
监控模块API端点
提供系统监控、性能指标、健康检查等功能
"""

from .monitor_api import router as monitor_router

__all__ = ["monitor_router"]