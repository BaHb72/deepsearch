"""
股票信息缓存服务（兼容层）

为了向后兼容，保留原有接口但内部使用数据库服务
"""
from typing import Dict, Any, Optional, List

from loguru import logger

# 使用新的数据库服务
from deepsearch.services.stock_info_service import get_stock_info_service


class StockInfoCache:
    """股票信息缓存管理器（兼容层）"""

    def __init__(self, cache_file: Optional[str] = None):
        """
        初始化缓存管理器
        
        Args:
            cache_file: 缓存文件路径（忽略，仅为兼容）
        """
        # 使用数据库服务
        self._service = get_stock_info_service()
        logger.info("股票信息缓存使用数据库服务")

    def get(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典，如果不存在则返回None
        """
        return self._service.get(symbol)

    def set(self, symbol: str, info: Dict[str, Any]):
        """
        设置股票信息
        
        Args:
            symbol: 股票代码
            info: 股票信息字典
        """
        self._service.set(symbol, info)

    def update(self, stock_info_dict: Dict[str, Dict[str, Any]]):
        """
        批量更新股票信息
        
        Args:
            stock_info_dict: 股票信息字典 {symbol: info}
        """
        self._service.update_batch(stock_info_dict)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """获取所有股票信息"""
        return self._service.get_all()

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索股票
        
        Args:
            keyword: 搜索关键词（代码、名称）
            
        Returns:
            匹配的股票列表
        """
        return self._service.search(keyword)

    def clear(self):
        """清空缓存"""
        self._service.clear_cache()

    def size(self) -> int:
        """获取缓存大小"""
        all_stocks = self._service.get_all()
        return len(all_stocks)


# 全局缓存实例
_global_cache: Optional[StockInfoCache] = None


def get_stock_info_cache() -> StockInfoCache:
    """获取全局股票信息缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = StockInfoCache()
    return _global_cache
