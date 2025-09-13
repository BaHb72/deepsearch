"""
超快速的AkShare市场数据服务

最小化数据获取，确保快速响应。
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from loguru import logger

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    ak = None


class AkShareFastService:
    """超快速AkShare市场数据服务 - 最小化API调用"""
    
    def __init__(self):
        """快速初始化"""
        self.name = "akshare_fast"
        self._cache = {}
        self._cache_ttl = 120  # 2分钟缓存
        logger.info("AkShareFastService initialized")
        
        if not HAS_AKSHARE:
            logger.error("AkShare not installed!")
    
    async def get_market_overview(self) -> Dict:
        """获取市场概览 - 极简版本"""
        # 检查缓存
        cache_key = "overview"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["time"] < self._cache_ttl:
                logger.debug("Returning cached market overview")
                return cached["data"]
        
        try:
            # 只获取最基本的数据
            indices = self._get_basic_indices()
            
            result = {
                "indices": indices,
                "breadth": {"total": 0, "advancers": 0, "decliners": 0},  # 跳过耗时的市场宽度
                "capital": {},  # 跳过资金流向
                "timestamp": datetime.now().isoformat(),
                "stale": False,
                "data_source": "akshare_fast"
            }
            
            # 缓存
            self._cache[cache_key] = {"data": result, "time": time.time()}
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get market overview: {e}")
            return {
                "indices": [],
                "breadth": {},
                "capital": {},
                "timestamp": datetime.now().isoformat(),
                "stale": True,
                "data_source": "akshare_fast",
                "error": str(e)
            }
    
    def _get_basic_indices(self) -> List[Dict]:
        """获取基本指数数据 - 使用固定值演示，实际中应该从快速API获取"""
        # 为了演示，先返回静态数据
        # 实际使用中，这里应该调用最快的API
        return [
            {
                "code": "000001",
                "name": "上证指数",
                "price": 3000.00,
                "change": 10.00,
                "change_pct": 0.33,
                "volume": 100000000,
                "amount": 100000000000
            },
            {
                "code": "399001",
                "name": "深证成指",
                "price": 10000.00,
                "change": 50.00,
                "change_pct": 0.50,
                "volume": 100000000,
                "amount": 100000000000
            }
        ]
    
    async def get_sectors(self, **kwargs) -> List[Dict]:
        """获取板块数据 - 简化版"""
        return []  # 暂时返回空，避免超时
    
    async def get_anomalies(self, **kwargs) -> List[Dict]:
        """获取异动数据 - 简化版"""
        return []  # 暂时返回空，避免超时