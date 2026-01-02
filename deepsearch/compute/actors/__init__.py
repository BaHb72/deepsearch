"""
Compute Actors Package

Dask Actor 实现，用于有状态的长期运行服务。
"""

from .amazingdata_actor import AmazingDataActor

__all__ = ["AmazingDataActor"]
