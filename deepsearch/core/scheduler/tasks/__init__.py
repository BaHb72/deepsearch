"""
缓存任务模块
"""

from deepsearch.core.scheduler.tasks.base import CacheTask
from deepsearch.core.scheduler.tasks.stock_list import StockListTask

__all__ = ["CacheTask", "StockListTask"]
