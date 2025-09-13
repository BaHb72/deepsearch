"""
东方财富数据服务

直接调用东方财富API，快速获取真实市场数据。
"""
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

import requests
from loguru import logger


class EastMoneyService:
    """东方财富市场数据服务 - 快速获取真实数据"""
    
    def __init__(self):
        """初始化"""
        self.name = "eastmoney_service"
        self._cache = {}
        self._cache_ttl = 60
        self._executor = ThreadPoolExecutor(max_workers=2)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        logger.info("EastMoneyService initialized")
    
    async def get_market_overview(self) -> Dict:
        """获取市场概览"""
        # 检查缓存
        cache_key = "market_overview"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["time"] < self._cache_ttl:
                return cached["data"]
        
        try:
            loop = asyncio.get_event_loop()
            
            # 并行获取数据
            indices_task = loop.run_in_executor(self._executor, self._fetch_indices)
            breadth_task = loop.run_in_executor(self._executor, self._fetch_market_breadth)
            
            indices, breadth = await asyncio.gather(indices_task, breadth_task)
            
            result = {
                "indices": indices,
                "breadth": breadth,
                "capital": {},
                "timestamp": datetime.now().isoformat(),
                "stale": False,
                "data_source": "eastmoney"
            }
            
            # 缓存结果
            self._cache[cache_key] = {"data": result, "time": time.time()}
            
            return result
            
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return {
                "indices": [],
                "breadth": {},
                "capital": {},
                "timestamp": datetime.now().isoformat(),
                "stale": True,
                "data_source": "eastmoney",
                "error": str(e)
            }
    
    def _fetch_indices(self) -> List[Dict]:
        """获取指数数据"""
        try:
            # 东方财富指数接口
            url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
            params = {
                "fltt": "2",
                "fields": "f2,f3,f4,f12,f13,f14",
                "secids": "1.000001,0.399001,0.399006",  # 上证、深证、创业板
                "_": str(int(time.time() * 1000))
            }
            
            resp = self.session.get(url, params=params, timeout=5)
            data = resp.json()
            
            indices = []
            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    indices.append({
                        "code": item.get("f12", ""),
                        "name": self._get_index_name(item.get("f12", "")),
                        "price": float(item.get("f2", 0)),
                        "change": float(item.get("f4", 0)),
                        "change_pct": float(item.get("f3", 0)),
                        "volume": 0,
                        "amount": 0
                    })
            
            return indices
            
        except Exception as e:
            logger.error(f"获取指数失败: {e}")
            # 返回默认数据
            return [
                {"code": "000001", "name": "上证指数", "price": 0, "change": 0, "change_pct": 0, "volume": 0, "amount": 0},
                {"code": "399001", "name": "深证成指", "price": 0, "change": 0, "change_pct": 0, "volume": 0, "amount": 0},
                {"code": "399006", "name": "创业板指", "price": 0, "change": 0, "change_pct": 0, "volume": 0, "amount": 0}
            ]
    
    def _get_index_name(self, code: str) -> str:
        """获取指数名称"""
        names = {
            "000001": "上证指数",
            "399001": "深证成指",
            "399006": "创业板指",
            "899050": "北证50"
        }
        return names.get(code, code)
    
    def _fetch_market_breadth(self) -> Dict:
        """获取市场宽度 - 简化版本"""
        try:
            # 东方财富涨跌统计接口
            url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
            params = {
                "fltt": "2",
                "fields": "f3",  # 涨跌幅
                "fid": "f3",
                "fs": "m:0+m:1",  # 沪深A股
                "pn": "1",
                "pz": "5000",  # 获取5000只
                "_": str(int(time.time() * 1000))
            }
            
            resp = self.session.get(url, params=params, timeout=5)
            data = resp.json()
            
            if data.get("data") and data["data"].get("diff"):
                stocks = data["data"]["diff"]
                total = len(stocks)
                
                advancers = sum(1 for s in stocks if float(s.get("f3", 0)) > 0)
                decliners = sum(1 for s in stocks if float(s.get("f3", 0)) < 0)
                unchanged = total - advancers - decliners
                
                # 涨跌停简单判断
                limit_up = sum(1 for s in stocks if float(s.get("f3", 0)) >= 9.9)
                limit_down = sum(1 for s in stocks if float(s.get("f3", 0)) <= -9.9)
                
                return {
                    "total": total,
                    "advancers": advancers,
                    "decliners": decliners,
                    "unchanged": unchanged,
                    "limit_up": limit_up,
                    "limit_down": limit_down
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"获取市场宽度失败: {e}")
            return {}
    
    async def get_sectors(self, sector_type: str = "industry", limit: int = 20, sort_by: str = "change_pct", level: str = None) -> List[Dict]:
        """获取板块数据"""
        try:
            loop = asyncio.get_event_loop()
            
            # 东方财富板块接口
            url = "https://push2.eastmoney.com/api/qt/clist/get"
            
            # 根据板块类型设置参数
            if sector_type == "industry":
                # 行业板块 - 支持申万分级
                if level == "sw2":
                    fs = "m:90+t:2+f:!50"  # 申万二级
                elif level == "sw3":
                    fs = "m:90+t:2+f:!50"  # 申万三级（与二级使用相同接口，通过名称区分）
                else:
                    fs = "m:90+t:2"  # 申万一级（默认）
            elif sector_type == "concept":
                fs = "m:90+t:3"  # 概念板块
            elif sector_type == "region":
                fs = "m:90+t:1"  # 地域板块
            else:
                fs = "m:90+t:2"  # 默认行业板块
            
            params = {
                "pn": "1",
                "pz": str(limit),
                "po": "1",
                "np": "1",
                "fltt": "2",
                "invt": "2",
                "fid": "f3" if sort_by == "change_pct" else "f6",  # f3=涨跌幅 f6=成交额
                "fs": fs,
                "fields": "f2,f3,f4,f6,f12,f13,f14,f104,f105",  # 增加更多字段
                "_": str(int(time.time() * 1000))
            }
            
            result = await loop.run_in_executor(
                self._executor,
                lambda: self.session.get(url, params=params, timeout=5)
            )
            
            data = result.json()
            sectors = []
            
            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    # 获取领涨股信息（如果有）
                    leader_info = {}
                    if item.get("f13"):
                        leader_info = {
                            "code": item.get("f13", ""),
                            "name": item.get("f14", "")[:4] if item.get("f14") else ""  # 只取前4个字符作为股票名称
                        }
                    
                    sectors.append({
                        "code": item.get("f12", ""),
                        "name": item.get("f14", ""),
                        "change_pct": float(item.get("f3", 0)),
                        "amount": float(item.get("f6", 0)),
                        "leader": leader_info,
                        "advancers": int(item.get("f104", 0)),  # 上涨家数
                        "decliners": int(item.get("f105", 0))   # 下跌家数
                    })
            
            # 按照指定字段排序
            if sort_by == "change_pct":
                sectors.sort(key=lambda x: x["change_pct"], reverse=True)
            elif sort_by == "amount":
                sectors.sort(key=lambda x: x["amount"], reverse=True)
            
            return sectors[:limit]
            
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            return []
    
    async def get_anomalies(self, kind: str = "all", min_change: float = 0, min_amount: float = 0) -> List[Dict]:
        """获取异动股票"""
        return []  # 暂时返回空列表
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
        if hasattr(self, 'session'):
            self.session.close()