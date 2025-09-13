"""
直接使用AkShare的市场数据服务

快速、直接、无代理，获取真实市场数据。
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

try:
    import akshare as ak
    import pandas as pd
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    ak = None
    pd = None
    logger.error("AkShare not installed! Please install: pip install akshare")


class AkShareDirectService:
    """直接使用AkShare的市场数据服务"""
    
    def __init__(self):
        """初始化 - 非常快速，无复杂依赖"""
        self.name = "akshare_direct_service"
        self._cache = {}
        self._cache_ttl = 60  # 60秒缓存
        self._executor = ThreadPoolExecutor(max_workers=4)
        logger.info("AkShareDirectService initialized (direct akshare access)")
        
        if not HAS_AKSHARE:
            raise ImportError("AkShare is required but not installed")
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] < self._cache_ttl:
                return entry["data"]
        return None
    
    def _set_cache(self, key: str, data: Any):
        """设置缓存"""
        self._cache[key] = {
            "data": data,
            "timestamp": time.time()
        }
    
    async def get_market_overview(self) -> Dict:
        """
        获取真实的市场概览数据
        """
        # 检查缓存
        cached = self._get_cached("market_overview")
        if cached:
            return cached
        
        try:
            # 使用线程池执行同步的akshare调用
            loop = asyncio.get_event_loop()
            
            # 并行获取各种数据
            indices_task = loop.run_in_executor(self._executor, self._fetch_indices_sync)
            breadth_task = loop.run_in_executor(self._executor, self._fetch_breadth_sync)
            
            # 等待所有任务完成
            indices, breadth = await asyncio.gather(indices_task, breadth_task)
            
            # 获取北向资金（单独处理，因为可能失败）
            try:
                capital = await loop.run_in_executor(self._executor, self._fetch_capital_sync)
            except Exception as e:
                logger.warning(f"获取资金流向失败: {e}")
                capital = {}
            
            result = {
                "indices": indices,
                "breadth": breadth,
                "capital": capital,
                "timestamp": datetime.now().isoformat(),
                "stale": False,
                "data_source": "akshare_direct"
            }
            
            # 缓存结果
            self._set_cache("market_overview", result)
            
            return result
            
        except Exception as e:
            logger.error(f"获取市场概览失败: {e}")
            # 返回基础结构
            return {
                "indices": [],
                "breadth": {},
                "capital": {},
                "timestamp": datetime.now().isoformat(),
                "stale": True,
                "data_source": "akshare_direct",
                "error": str(e)
            }
    
    def _fetch_indices_sync(self) -> List[Dict]:
        """同步获取指数数据 - 优化版本，只获取需要的指数"""
        indices_data = []
        
        # 主要指数，单独获取每个指数以提高速度
        indices_info = [
            ("000001", "上证指数", "sh000001"),
            ("399001", "深证成指", "sz399001"),
            ("399006", "创业板指", "sz399006"),
        ]
        
        for code, name, symbol in indices_info:
            try:
                # 使用更快的单个指数获取方法
                df = ak.stock_zh_index_daily_em(symbol=symbol, period="1")
                if not df.empty:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2] if len(df) > 1 else latest
                    
                    current_price = float(latest['close'])
                    prev_close = float(prev['close'])
                    change = current_price - prev_close
                    change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
                    
                    indices_data.append({
                        "code": code,
                        "name": name,
                        "price": current_price,
                        "change": change,
                        "change_pct": change_pct,
                        "volume": float(latest.get('volume', 0)),
                        "amount": float(latest.get('amount', 0))
                    })
            except Exception as e:
                # 如果失败，添加默认值
                logger.warning(f"获取指数 {name} 失败: {e}")
                indices_data.append({
                    "code": code,
                    "name": name,
                    "price": 0,
                    "change": 0,
                    "change_pct": 0,
                    "volume": 0,
                    "amount": 0
                })
        
        return indices_data
    
    def _fetch_breadth_sync(self) -> Dict:
        """同步获取市场宽度数据"""
        try:
            # 获取A股实时行情
            df = ak.stock_zh_a_spot_em()
            
            if df.empty:
                return {}
            
            # 计算涨跌统计
            total = len(df)
            df['涨跌幅_num'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
            
            advancers = len(df[df['涨跌幅_num'] > 0])
            decliners = len(df[df['涨跌幅_num'] < 0])
            unchanged = len(df[df['涨跌幅_num'] == 0])
            
            # 涨停跌停（简单判断：涨跌幅接近10%）
            limit_up = len(df[df['涨跌幅_num'] >= 9.9])
            limit_down = len(df[df['涨跌幅_num'] <= -9.9])
            
            return {
                "total": total,
                "advancers": advancers,
                "decliners": decliners,
                "unchanged": unchanged,
                "limit_up": limit_up,
                "limit_down": limit_down
            }
            
        except Exception as e:
            logger.error(f"获取市场宽度失败: {e}")
            return {}
    
    def _fetch_capital_sync(self) -> Dict:
        """同步获取资金流向数据"""
        try:
            # 获取北向资金
            df_north = ak.stock_hsgt_north_net_flow_in_em(indicator="北向")
            
            if not df_north.empty:
                latest = df_north.iloc[-1]  # 最新一条
                north_inflow = float(latest.get('value', 0)) / 100  # 转换为亿元
            else:
                north_inflow = 0
            
            return {
                "north_inflow": north_inflow,
                "south_inflow": 0,  # 南向资金需要另外获取
                "main_inflow": 0,  # 主力资金需要另外计算
                "total_amount": 0  # 总成交额需要另外计算
            }
            
        except Exception as e:
            logger.warning(f"获取资金流向失败: {e}")
            return {}
    
    async def get_sectors(
        self,
        sector_type: str = "industry",
        limit: int = 20,
        sort: str = "change_pct"
    ) -> List[Dict]:
        """获取真实板块数据"""
        cache_key = f"sectors_{sector_type}_{limit}_{sort}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            loop = asyncio.get_event_loop()
            
            if sector_type == "industry":
                # 获取行业板块
                df = await loop.run_in_executor(
                    self._executor,
                    ak.stock_board_industry_name_em
                )
            else:
                # 获取概念板块
                df = await loop.run_in_executor(
                    self._executor,
                    ak.stock_board_concept_name_em
                )
            
            if df.empty:
                return []
            
            # 处理数据
            sectors = []
            for _, row in df.head(limit).iterrows():
                sectors.append({
                    "code": str(row.get('板块代码', '')),
                    "name": str(row.get('板块名称', '')),
                    "change_pct": float(row.get('涨跌幅', 0)),
                    "amount": float(row.get('总成交额', 0)),
                    "leader": {
                        "symbol": str(row.get('领涨股票代码', '')),
                        "name": str(row.get('领涨股票', '')),
                        "change_pct": float(row.get('领涨股票涨跌幅', 0))
                    }
                })
            
            # 排序
            if sort == "change_pct":
                sectors.sort(key=lambda x: x["change_pct"], reverse=True)
            elif sort == "amount":
                sectors.sort(key=lambda x: x["amount"], reverse=True)
            
            self._set_cache(cache_key, sectors)
            return sectors
            
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            return []
    
    async def get_anomalies(
        self,
        kind: str = "all",
        min_change: float = 0,
        min_amount: float = 0
    ) -> List[Dict]:
        """获取真实异动股票"""
        try:
            loop = asyncio.get_event_loop()
            
            # 获取涨跌幅榜
            if kind == "up":
                df = await loop.run_in_executor(
                    self._executor,
                    ak.stock_zh_a_spot_em
                )
                # 筛选涨幅最大的
                df = df.nlargest(50, '涨跌幅')
            elif kind == "down":
                df = await loop.run_in_executor(
                    self._executor,
                    ak.stock_zh_a_spot_em
                )
                # 筛选跌幅最大的
                df = df.nsmallest(50, '涨跌幅')
            else:
                # 获取全部，按成交额排序
                df = await loop.run_in_executor(
                    self._executor,
                    ak.stock_zh_a_spot_em
                )
                df = df.nlargest(50, '成交额')
            
            if df.empty:
                return []
            
            anomalies = []
            for _, row in df.head(20).iterrows():
                change_pct = float(row.get('涨跌幅', 0))
                amount = float(row.get('成交额', 0))
                
                # 应用过滤条件
                if abs(change_pct) < min_change or amount < min_amount:
                    continue
                
                # 判断异动原因
                reason = "成交活跃"
                if change_pct >= 9.9:
                    reason = "涨停"
                elif change_pct <= -9.9:
                    reason = "跌停"
                elif change_pct > 7:
                    reason = "大幅上涨"
                elif change_pct < -7:
                    reason = "大幅下跌"
                elif amount > 5000000000:  # 50亿
                    reason = "巨额成交"
                
                anomalies.append({
                    "symbol": str(row.get('代码', '')),
                    "name": str(row.get('名称', '')),
                    "price": float(row.get('最新价', 0)),
                    "change_pct": change_pct,
                    "amount": amount,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                    "extra": {
                        "volume_ratio": float(row.get('量比', 0)),
                        "turnover_rate": float(row.get('换手率', 0))
                    }
                })
            
            return anomalies
            
        except Exception as e:
            logger.error(f"获取异动数据失败: {e}")
            return []
    
    async def get_market_activity(self) -> Dict:
        """获取赚钱效应分析数据"""
        cache_key = "market_activity"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            loop = asyncio.get_event_loop()
            
            # 使用线程池执行AkShare同步函数
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_market_activity
            )
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"获取赚钱效应数据失败: {e}")
            # 返回默认数据
            return self._get_default_market_activity()
    
    def _fetch_market_activity(self) -> Dict:
        """获取赚钱效应数据 - 同步方法"""
        try:
            # 调用AkShare接口
            df = ak.stock_market_activity_legu()
            
            # 转换为字典格式
            activity_data = {}
            for _, row in df.iterrows():
                activity_data[row['item']] = row['value']
            
            # 计算涨跌比
            total = activity_data.get('上涨', 0) + activity_data.get('下跌', 0) + activity_data.get('平盘', 0)
            rise_ratio = (activity_data.get('上涨', 0) / total * 100) if total > 0 else 0
            
            result = {
                "rise": int(activity_data.get('上涨', 0)),
                "fall": int(activity_data.get('下跌', 0)),
                "flat": int(activity_data.get('平盘', 0)),
                "limit_up": int(activity_data.get('涨停', 0)),
                "limit_down": int(activity_data.get('跌停', 0)),
                "real_limit_up": int(activity_data.get('真实涨停', 0)),
                "real_limit_down": int(activity_data.get('真实跌停', 0)),
                "st_limit_up": int(activity_data.get('st st*涨停', 0)),
                "st_limit_down": int(activity_data.get('st st*跌停', 0)),
                "halt": int(activity_data.get('停牌', 0)),
                "activity_rate": activity_data.get('活跃度', '0%'),
                "rise_ratio": f"{rise_ratio:.2f}%",
                "statistics_time": str(activity_data.get('统计日期', '')),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"_fetch_market_activity error: {e}")
            return self._get_default_market_activity()
    
    def _get_default_market_activity(self) -> Dict:
        """获取默认的赚钱效应数据"""
        return {
            "rise": 0,
            "fall": 0,
            "flat": 0,
            "limit_up": 0,
            "limit_down": 0,
            "real_limit_up": 0,
            "real_limit_down": 0,
            "st_limit_up": 0,
            "st_limit_down": 0,
            "halt": 0,
            "activity_rate": "0%",
            "rise_ratio": "0%",
            "statistics_time": "",
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_stock_changes(self, change_type: str = "大笔买入") -> List[Dict]:
        """获取盘口异动数据"""
        cache_key = f"stock_changes_{change_type}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            loop = asyncio.get_event_loop()
            
            # 使用线程池执行AkShare同步函数
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_stock_changes,
                change_type
            )
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"获取盘口异动数据失败: {e}")
            return []
    
    def _fetch_stock_changes(self, change_type: str) -> List[Dict]:
        """获取盘口异动数据 - 同步方法"""
        try:
            # 调用AkShare接口
            df = ak.stock_changes_em(symbol=change_type)
            
            if df.empty:
                return []
            
            # 转换为列表格式，取前50条
            changes = []
            for _, row in df.head(50).iterrows():
                changes.append({
                    "time": str(row['时间']),
                    "symbol": str(row['代码']),
                    "name": str(row['名称']),
                    "sector": str(row.get('板块', '')),
                    "info": str(row['相关信息']),
                    "change_type": change_type
                })
            
            return changes
            
        except Exception as e:
            logger.error(f"_fetch_stock_changes error: {e}")
            return []
    
    async def get_zt_pool(self, date: str = None) -> List[Dict]:
        """获取涨停股池数据"""
        if date is None:
            # 使用今天的日期
            date = datetime.now().strftime('%Y%m%d')
        
        cache_key = f"zt_pool_{date}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            loop = asyncio.get_event_loop()
            
            # 使用线程池执行AkShare同步函数
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_zt_pool,
                date
            )
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"获取涨停股池失败: {e}")
            return []
    
    def _fetch_zt_pool(self, date: str) -> List[Dict]:
        """获取涨停股池数据 - 同步方法"""
        try:
            # 调用AkShare接口
            df = ak.stock_zt_pool_em(date=date)
            
            if df.empty:
                return []
            
            # 转换为列表格式，取前30条
            zt_stocks = []
            for _, row in df.head(30).iterrows():
                zt_stocks.append({
                    "rank": int(row['序号']),
                    "symbol": str(row['代码']),
                    "name": str(row['名称']),
                    "change_pct": float(row.get('涨跌幅', 0)),
                    "price": float(row.get('最新价', 0)),
                    "amount": int(row.get('成交额', 0)),
                    "turnover_rate": float(row.get('换手率', 0)),
                    "seal_funds": int(row.get('封板资金', 0)),
                    "first_seal_time": str(row.get('首次封板时间', '')),
                    "last_seal_time": str(row.get('最后封板时间', '')),
                    "open_times": int(row.get('炸板次数', 0)),
                    "zt_stats": str(row.get('涨停统计', '')),
                    "continuous_days": int(row.get('连板数', 0)),
                    "industry": str(row.get('所属行业', ''))
                })
            
            return zt_stocks
            
        except Exception as e:
            logger.error(f"_fetch_zt_pool error: {e}")
            return []
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)