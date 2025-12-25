"""
股票列表缓存任务

定时获取完整股票列表并缓存
"""

import asyncio
from typing import Any, Dict, List

from loguru import logger

from deepsearch.core.scheduler.tasks.base import CacheTask


class StockListTask(CacheTask):
    """
    股票列表缓存任务
    
    从 xtdata 获取完整股票列表（代码、名称、拼音）
    """
    
    name = "stock_list"
    cache_key_prefix = "stock_list"
    refresh_interval = 86400  # 每天刷新一次
    persist_to_db = True
    cache_ttl = 86400 * 2  # 缓存 2 天
    description = "股票列表（沪深A股）"
    
    def __init__(self, sector: str = "沪深A股"):
        super().__init__()
        self.sector = sector
    
    @property
    def cache_key(self) -> str:
        return f"{self.cache_key_prefix}:{self.sector}"
    
    async def fetch_data(self) -> List[Dict[str, str]]:
        """从 xtdata 获取股票列表"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync)
    
    def _fetch_sync(self) -> List[Dict[str, str]]:
        """同步获取股票列表"""
        try:
            from xtquant import xtdata
            
            logger.info(f"[StockListTask] 开始获取 {self.sector} 股票列表...")
            
            # 获取股票代码列表
            stock_codes = xtdata.get_stock_list_in_sector(self.sector)
            if not stock_codes:
                logger.warning(f"[StockListTask] 未获取到 {self.sector} 股票列表")
                return []
            
            logger.info(f"[StockListTask] 获取到 {len(stock_codes)} 个股票代码")
            
            # 获取拼音生成器
            try:
                from pypinyin import lazy_pinyin
                has_pinyin = True
            except ImportError:
                has_pinyin = False
                logger.warning("[StockListTask] pypinyin 未安装")
            
            result = []
            success_count = 0
            
            for i, code in enumerate(stock_codes):
                try:
                    detail = xtdata.get_instrument_detail(code)
                    if detail and detail.get("InstrumentName"):
                        name = detail["InstrumentName"]
                        
                        # 修复编码问题
                        try:
                            if isinstance(name, bytes):
                                name = name.decode('gbk', errors='ignore')
                        except Exception:
                            pass
                        
                        # 生成拼音
                        pinyin = ""
                        if has_pinyin and name:
                            try:
                                pinyin = ''.join([p[0] for p in lazy_pinyin(name) if p]).lower()
                            except Exception:
                                pass
                        
                        result.append({
                            "symbol": code,
                            "name": name,
                            "pinyin": pinyin,
                            "sector": self.sector,
                        })
                        success_count += 1
                except Exception as e:
                    if success_count < 5:
                        logger.warning(f"[StockListTask] 获取 {code} 详情失败: {e}")
                
                # 每 500 个打印进度
                if (i + 1) % 500 == 0:
                    logger.info(f"[StockListTask] 进度: {i + 1}/{len(stock_codes)}")
            
            logger.info(f"[StockListTask] 完成! 成功: {success_count}/{len(stock_codes)}")
            return result
            
        except ImportError:
            logger.warning("[StockListTask] xtquant 未安装")
            return []
        except Exception as e:
            logger.error(f"[StockListTask] 获取失败: {e}")
            return []
    
    def get_db_records(self, data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """转换为数据库记录"""
        return data  # 直接返回，DBStore 会处理
