"""
市场数据服务层
封装 AkShare API 调用，提供市场概览、板块行情、异动监控等功能
"""
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from loguru import logger

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None


class MarketService:
    """市场数据服务"""

    def __init__(self, data_provider=None):
        """
        初始化市场服务
        
        Args:
            data_provider: AkShare 数据提供者实例
        """
        self.data_provider = data_provider

        # 内存缓存
        self._cache = {}
        self._cache_ttl = {
            "overview": 5,  # 大盘概览 5 秒
            "sectors": 60,  # 板块数据 60 秒
            "anomalies": 20,  # 异动数据 20 秒
            "intraday": 30,  # 分时数据 30 秒
        }

        # 异动去重集合（避免重复推送）
        self._anomaly_history = {}
        self._anomaly_history_ttl = 300  # 5分钟内不重复

        # 统计信息
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_errors": 0,
            "last_update": None
        }

    def _get_cache_key(self, category: str, **kwargs) -> str:
        """生成缓存键"""
        params_str = json.dumps(kwargs, sort_keys=True)
        return f"{category}:{hashlib.md5(params_str.encode()).hexdigest()}"

    def _get_from_cache(self, category: str, **kwargs) -> Optional[Any]:
        """从缓存获取数据"""
        key = self._get_cache_key(category, **kwargs)

        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] < self._cache_ttl.get(category, 60):
                self.stats["cache_hits"] += 1
                logger.debug(f"缓存命中: {key}")
                return entry["data"]

        self.stats["cache_misses"] += 1
        return None

    def _set_cache(self, category: str, data: Any, **kwargs) -> None:
        """设置缓存"""
        key = self._get_cache_key(category, **kwargs)
        self._cache[key] = {
            "data": data,
            "timestamp": time.time()
        }

        # 清理过期缓存
        self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []

        for key, entry in self._cache.items():
            category = key.split(":")[0]
            ttl = self._cache_ttl.get(category, 60)
            if current_time - entry["timestamp"] > ttl * 2:  # 2倍TTL后删除
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

    async def get_market_overview(self) -> Dict:
        """
        获取市场概览数据
        包括主要指数、市场宽度、资金流向等
        """
        self.stats["total_requests"] += 1

        # 尝试从缓存获取
        cached = self._get_from_cache("overview")
        if cached:
            return cached

        try:
            # 获取指数数据
            indices = await self._fetch_indices()

            # 获取市场宽度
            breadth = await self._fetch_market_breadth()

            # 获取资金流向（暂时模拟）
            capital = await self._fetch_capital_flow()

            result = {
                "indices": indices,
                "breadth": breadth,
                "capital": capital,
                "timestamp": datetime.now().isoformat(),
                "stale": False
            }

            # 缓存结果
            self._set_cache("overview", result)
            self.stats["last_update"] = datetime.now()

            return result

        except Exception as e:
            logger.error(f"获取市场概览失败: {e}")
            self.stats["api_errors"] += 1

            # 返回缓存数据（如果有）
            cached = self._get_from_cache("overview", ignore_ttl=True)
            if cached:
                cached["stale"] = True
                return cached

            # 返回空数据
            return {
                "indices": [],
                "breadth": {},
                "capital": {},
                "timestamp": datetime.now().isoformat(),
                "stale": True,
                "error": str(e)
            }

    async def _fetch_indices(self) -> List[Dict]:
        """获取主要指数数据"""
        indices_config = [
            {"code": "000001", "name": "上证指数", "market": "sh"},
            {"code": "399001", "name": "深证成指", "market": "sz"},
            {"code": "399006", "name": "创业板指", "market": "sz"},
            {"code": "899050", "name": "北证50", "market": "bj"},
        ]

        indices_data = []

        if self.data_provider:
            # 通过 AkShare 代理获取
            try:
                # 调用 stock_zh_index_spot_em 接口
                response = await self.data_provider._fetch_with_fallback(
                    "stock_zh_index_spot_em",
                    {"symbol": "上证系列指数"}
                )

                if response and "data" in response:
                    df = pd.DataFrame(response["data"])

                    for idx_cfg in indices_config:
                        # 在返回的数据中查找对应指数
                        idx_data = df[df["代码"].str.contains(idx_cfg["code"])]
                        if not idx_data.empty:
                            row = idx_data.iloc[0]
                            indices_data.append({
                                "code": idx_cfg["code"],
                                "name": idx_cfg["name"],
                                "price": float(row.get("最新价", 0)),
                                "change": float(row.get("涨跌额", 0)),
                                "change_pct": float(row.get("涨跌幅", 0)),
                                "volume": float(row.get("成交量", 0)),
                                "amount": float(row.get("成交额", 0))
                            })
            except Exception as e:
                logger.error(f"获取指数数据失败: {e}")

        # 如果没有数据，返回模拟数据
        if not indices_data:
            import random
            for idx_cfg in indices_config:
                base_price = {"000001": 3000, "399001": 10000, "399006": 2000, "899050": 1000}
                price = base_price.get(idx_cfg["code"], 1000) + random.uniform(-50, 50)
                change_pct = random.uniform(-2, 2)
                indices_data.append({
                    "code": idx_cfg["code"],
                    "name": idx_cfg["name"],
                    "price": round(price, 2),
                    "change": round(price * change_pct / 100, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": random.randint(1000000, 10000000),
                    "amount": random.randint(10000000, 100000000)
                })

        return indices_data

    async def _fetch_market_breadth(self) -> Dict:
        """获取市场宽度数据"""
        breadth = {
            "advancers": 0,
            "decliners": 0,
            "unchanged": 0,
            "limit_up": 0,
            "limit_down": 0,
            "total": 0
        }

        if self.data_provider:
            try:
                # 获取全市场快照
                response = await self.data_provider._fetch_with_fallback(
                    "stock_zh_a_spot_em",
                    {}
                )

                if response and "data" in response:
                    df = pd.DataFrame(response["data"])

                    # 计算涨跌家数
                    breadth["total"] = len(df)
                    breadth["advancers"] = len(df[df["涨跌幅"] > 0])
                    breadth["decliners"] = len(df[df["涨跌幅"] < 0])
                    breadth["unchanged"] = len(df[df["涨跌幅"] == 0])

                    # 计算涨停跌停（简化判断：涨跌幅接近10%）
                    breadth["limit_up"] = len(df[df["涨跌幅"] >= 9.9])
                    breadth["limit_down"] = len(df[df["涨跌幅"] <= -9.9])

            except Exception as e:
                logger.error(f"获取市场宽度失败: {e}")

        # 如果没有数据，返回模拟数据
        if breadth["total"] == 0:
            import random
            breadth = {
                "advancers": random.randint(1500, 2500),
                "decliners": random.randint(1500, 2500),
                "unchanged": random.randint(50, 150),
                "limit_up": random.randint(20, 80),
                "limit_down": random.randint(5, 30),
                "total": 5000
            }

        return breadth

    async def _fetch_capital_flow(self) -> Dict:
        """获取资金流向数据"""
        # 暂时返回模拟数据
        import random
        return {
            "north_net_flow": random.uniform(-5000000000, 5000000000),  # 北向资金净流入
            "turnover": random.uniform(500000000000, 1000000000000),  # 总成交额
            "active_ratio": random.uniform(0.3, 0.7)  # 活跃度
        }

    async def get_sectors(self, sector_type: str = "industry", limit: int = 20, sort_by: str = "change_pct") -> List[
        Dict]:
        """
        获取板块排行数据
        
        Args:
            sector_type: 板块类型 (industry/concept)
            limit: 返回数量限制
            sort_by: 排序字段 (change_pct/amount/volume)
        """
        self.stats["total_requests"] += 1

        # 尝试从缓存获取
        cached = self._get_from_cache("sectors", type=sector_type, limit=limit, sort_by=sort_by)
        if cached:
            return cached

        try:
            sectors_data = []

            if self.data_provider:
                # 根据类型选择接口
                if sector_type == "industry":
                    # 获取行业板块
                    response = await self.data_provider._fetch_with_fallback(
                        "stock_board_industry_name_em",
                        {}
                    )
                else:
                    # 获取概念板块
                    response = await self.data_provider._fetch_with_fallback(
                        "stock_board_concept_name_em",
                        {}
                    )

                if response and "data" in response:
                    df = pd.DataFrame(response["data"])

                    # 处理数据
                    for _, row in df.head(limit).iterrows():
                        sectors_data.append({
                            "code": row.get("板块代码", ""),
                            "name": row.get("板块名称", ""),
                            "change_pct": float(row.get("涨跌幅", 0)),
                            "amount": float(row.get("成交额", 0)),
                            "leader": {
                                "symbol": row.get("领涨股票代码", ""),
                                "name": row.get("领涨股票", ""),
                                "change_pct": float(row.get("领涨股票涨跌幅", 0))
                            }
                        })

            # 如果没有数据，返回模拟数据
            if not sectors_data:
                import random
                sector_names = ["新能源", "半导体", "人工智能", "医药", "金融", "消费", "军工", "汽车", "房地产",
                                "有色金属"]
                for i, name in enumerate(sector_names[:limit]):
                    sectors_data.append({
                        "code": f"BK{1000 + i}",
                        "name": name,
                        "change_pct": round(random.uniform(-3, 3), 2),
                        "amount": random.randint(1000000000, 10000000000),
                        "leader": {
                            "symbol": f"{600000 + i}",
                            "name": f"{name}龙头",
                            "change_pct": round(random.uniform(-5, 5), 2)
                        }
                    })

            # 排序
            if sort_by == "change_pct":
                sectors_data.sort(key=lambda x: x["change_pct"], reverse=True)
            elif sort_by == "amount":
                sectors_data.sort(key=lambda x: x["amount"], reverse=True)

            # 缓存结果
            self._set_cache("sectors", sectors_data, type=sector_type, limit=limit, sort_by=sort_by)

            return sectors_data

        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            self.stats["api_errors"] += 1
            return []

    async def get_anomalies(self, kind: str = "all", min_change: float = 0, min_amount: float = 0) -> List[Dict]:
        """
        获取异动股票数据
        
        Args:
            kind: 异动类型 (all/limit_up/limit_down/price_surge/volume_spike)
            min_change: 最小涨跌幅过滤
            min_amount: 最小成交额过滤
        """
        self.stats["total_requests"] += 1

        # 尝试从缓存获取
        cached = self._get_from_cache("anomalies", kind=kind)
        if cached:
            return self._filter_anomalies(cached, min_change, min_amount)

        try:
            anomalies = []
            current_time = datetime.now()

            if self.data_provider:
                # 根据类型获取数据
                if kind in ["all", "limit_up"]:
                    # 获取涨停池
                    response = await self.data_provider._fetch_with_fallback(
                        "stock_zt_pool_em",
                        {"date": current_time.strftime("%Y%m%d")}
                    )
                    if response and "data" in response:
                        df = pd.DataFrame(response["data"])
                        for _, row in df.iterrows():
                            anomalies.append({
                                "symbol": row.get("代码", ""),
                                "name": row.get("名称", ""),
                                "price": float(row.get("最新价", 0)),
                                "change_pct": float(row.get("涨跌幅", 0)),
                                "amount": float(row.get("成交额", 0)),
                                "reason": "涨停",
                                "timestamp": current_time.isoformat(),
                                "extra": {"封板时间": row.get("涨停时间", "")}
                            })

                if kind in ["all", "limit_down"]:
                    # 获取跌停池
                    response = await self.data_provider._fetch_with_fallback(
                        "stock_zt_pool_dtgc_em",
                        {"date": current_time.strftime("%Y%m%d")}
                    )
                    if response and "data" in response:
                        df = pd.DataFrame(response["data"])
                        for _, row in df.iterrows():
                            anomalies.append({
                                "symbol": row.get("代码", ""),
                                "name": row.get("名称", ""),
                                "price": float(row.get("最新价", 0)),
                                "change_pct": float(row.get("涨跌幅", 0)),
                                "amount": float(row.get("成交额", 0)),
                                "reason": "跌停",
                                "timestamp": current_time.isoformat(),
                                "extra": {"封板时间": row.get("跌停时间", "")}
                            })

            # 如果没有数据，返回模拟数据
            if not anomalies:
                import random
                reasons = ["涨停", "跌停", "急速拉升", "大单买入", "放量突破"]
                for i in range(10):
                    anomalies.append({
                        "symbol": f"{600000 + i:06d}",
                        "name": f"异动股{i + 1}",
                        "price": round(random.uniform(5, 50), 2),
                        "change_pct": round(random.uniform(-10, 10), 2),
                        "amount": random.randint(100000000, 1000000000),
                        "reason": random.choice(reasons),
                        "timestamp": current_time.isoformat(),
                        "extra": {}
                    })

            # 去重处理
            anomalies = self._deduplicate_anomalies(anomalies)

            # 缓存结果
            self._set_cache("anomalies", anomalies, kind=kind)

            return self._filter_anomalies(anomalies, min_change, min_amount)

        except Exception as e:
            logger.error(f"获取异动数据失败: {e}")
            self.stats["api_errors"] += 1
            return []

    def _filter_anomalies(self, anomalies: List[Dict], min_change: float, min_amount: float) -> List[Dict]:
        """过滤异动数据"""
        filtered = []
        for anomaly in anomalies:
            if abs(anomaly.get("change_pct", 0)) >= min_change and anomaly.get("amount", 0) >= min_amount:
                filtered.append(anomaly)
        return filtered

    def _deduplicate_anomalies(self, anomalies: List[Dict]) -> List[Dict]:
        """异动数据去重"""
        current_time = time.time()
        deduplicated = []

        # 清理过期历史记录
        expired_keys = []
        for key, timestamp in self._anomaly_history.items():
            if current_time - timestamp > self._anomaly_history_ttl:
                expired_keys.append(key)
        for key in expired_keys:
            del self._anomaly_history[key]

        # 去重处理
        for anomaly in anomalies:
            key = f"{anomaly['symbol']}:{anomaly['reason']}"
            if key not in self._anomaly_history:
                self._anomaly_history[key] = current_time
                deduplicated.append(anomaly)

        return deduplicated

    async def get_stock_intraday(self, symbol: str, period: int = 1, limit: int = 240) -> List[Dict]:
        """
        获取个股分时数据
        
        Args:
            symbol: 股票代码
            period: 时间周期（分钟）
            limit: 数据点数量
        """
        self.stats["total_requests"] += 1

        # 尝试从缓存获取
        cached = self._get_from_cache("intraday", symbol=symbol, period=period, limit=limit)
        if cached:
            return cached

        try:
            intraday_data = []

            # 这里暂时返回模拟数据
            # 实际应该调用 stock_zh_a_hist_min_em 等接口
            import random
            base_price = 10
            current_time = datetime.now()

            for i in range(limit):
                time_point = current_time - timedelta(minutes=period * (limit - i - 1))
                price = base_price + random.uniform(-0.5, 0.5)
                intraday_data.append({
                    "time": time_point.strftime("%H:%M"),
                    "price": round(price, 2),
                    "volume": random.randint(1000, 10000)
                })

            # 缓存结果
            self._set_cache("intraday", intraday_data, symbol=symbol, period=period, limit=limit)

            return intraday_data

        except Exception as e:
            logger.error(f"获取分时数据失败: {e}")
            self.stats["api_errors"] += 1
            return []

    def get_statistics(self) -> Dict:
        """获取服务统计信息"""
        cache_hit_rate = 0
        if self.stats["total_requests"] > 0:
            cache_hit_rate = self.stats["cache_hits"] / self.stats["total_requests"] * 100

        return {
            "total_requests": self.stats["total_requests"],
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "cache_hit_rate": round(cache_hit_rate, 2),
            "api_errors": self.stats["api_errors"],
            "cache_size": len(self._cache),
            "last_update": self.stats["last_update"].isoformat() if self.stats["last_update"] else None
        }
