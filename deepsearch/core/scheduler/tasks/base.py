"""
缓存任务基类

定义缓存任务的通用接口和行为
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class CacheTask(ABC):
    """
    缓存任务基类
    
    所有缓存任务都应继承此类并实现 fetch_data 方法
    """
    
    # 任务名称（唯一标识）
    name: str = "base_task"
    
    # 缓存键前缀
    cache_key_prefix: str = "cache"
    
    # 刷新间隔（秒），0 表示不自动刷新
    refresh_interval: int = 0
    
    # 是否持久化到数据库
    persist_to_db: bool = False
    
    # 缓存过期时间（秒），0 表示永不过期
    cache_ttl: int = 86400  # 默认 24 小时
    
    # 任务描述
    description: str = ""
    
    def __init__(self):
        self.last_refresh: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.data_count: int = 0
        
    @property
    def cache_key(self) -> str:
        """完整的缓存键"""
        return f"{self.cache_key_prefix}:{self.name}"
    
    @abstractmethod
    async def fetch_data(self) -> Any:
        """
        获取数据的具体逻辑
        
        子类必须实现此方法
        
        Returns:
            要缓存的数据
        """
        pass
    
    def transform_data(self, data: Any) -> Any:
        """
        数据转换（可选覆盖）
        
        在存储前对数据进行转换处理
        """
        return data
    
    def get_db_records(self, data: Any) -> List[Dict[str, Any]]:
        """
        将数据转换为数据库记录（可选覆盖）
        
        仅当 persist_to_db=True 时调用
        
        Returns:
            数据库记录列表
        """
        return []
    
    async def on_refresh_success(self, data: Any, count: int):
        """刷新成功回调"""
        self.last_refresh = datetime.now()
        self.data_count = count
        self.last_error = None
        logger.info(f"[{self.name}] 刷新成功, 共 {count} 条数据")
    
    async def on_refresh_error(self, error: Exception):
        """刷新失败回调"""
        self.last_error = str(error)
        logger.error(f"[{self.name}] 刷新失败: {error}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        return {
            "name": self.name,
            "cache_key": self.cache_key,
            "refresh_interval": self.refresh_interval,
            "persist_to_db": self.persist_to_db,
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "data_count": self.data_count,
            "last_error": self.last_error,
        }
