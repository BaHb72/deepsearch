"""
AmazingData Web API 模块

提供AmazingData SDK功能的RESTful API封装
包含全部37个AmazingData接口
"""

from .amazingdata_api import router as main_router

__all__ = ['main_router']