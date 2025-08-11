"""
图表数据服务层
提供K线数据获取、聚合、缓存和指标计算功能
"""
import asyncio
import hashlib
import json
import pickle
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

import numpy as np
from loguru import logger

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None


class ChartService:
    """图表数据服务"""

    # A股交易时段
    TRADING_SESSIONS = [
        ("09:30", "11:30"),  # 上午
        ("13:00", "15:00")  # 下午
    ]

    # 支持的时间周期
    TIMEFRAMES = {
        "1m": 1,
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "60m": 60,
        "1d": "daily",
        "1w": "weekly",
        "1mo": "monthly"
    }

    def __init__(self, data_provider=None, indicator_calculator=None, redis_url: Optional[str] = None):
        """
        初始化图表服务
        
        Args:
            data_provider: 数据提供者（如 AkShareProxyProvider）
            indicator_calculator: 指标计算器（如 TechnicalIndicators）
            redis_url: Redis连接URL（可选）
        """
        self.data_provider = data_provider
        self.indicator_calculator = indicator_calculator

        # Redis缓存配置
        self.redis_client = None
        self.redis_enabled = False
        if redis_url and HAS_REDIS:
            self._init_redis(redis_url)

        # 本地缓存配置（作为后备）
        self._cache = {}
        self._cache_ttl = {
            "1m": 5,  # 1分钟线缓存5秒
            "5m": 10,  # 5分钟线缓存10秒
            "15m": 30,  # 15分钟线缓存30秒
            "30m": 60,  # 30分钟线缓存60秒
            "60m": 120,  # 60分钟线缓存2分钟
            "1d": 300,  # 日线缓存5分钟
            "1w": 600,  # 周线缓存10分钟
            "1mo": 600  # 月线缓存10分钟
        }

        # 统计信息
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_errors": 0,
            "last_update": None
        }

        # 实时数据订阅管理
        self._subscriptions = {}
        self._subscription_tasks = {}

    def _clean_nan_values(self, data: Union[Dict, List, pd.DataFrame, Any]) -> Any:
        """
        递归清理数据中的NaN值
        
        Args:
            data: 需要清理的数据
            
        Returns:
            清理后的数据
        """
        if isinstance(data, dict):
            return {k: self._clean_nan_values(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_nan_values(item) for item in data]
        elif HAS_PANDAS and isinstance(data, pd.DataFrame):
            # DataFrame转换为dict时自动处理NaN
            return data.fillna(0).replace([np.inf, -np.inf], 0).to_dict(orient="records")
        elif HAS_PANDAS and isinstance(data, pd.Series):
            return data.fillna(0).replace([np.inf, -np.inf], 0).tolist()
        elif isinstance(data, (np.floating, np.integer)):
            # 转换numpy类型为Python原生类型
            if np.isnan(data) or np.isinf(data):
                return 0
            return float(data) if isinstance(data, np.floating) else int(data)
        elif isinstance(data, float):
            if np.isnan(data) or np.isinf(data):
                return 0
            return data
        else:
            return data

    def _init_redis(self, redis_url: str):
        """初始化Redis连接"""
        try:
            # 解析Redis URL
            if redis_url.startswith('redis://'):
                self.redis_client = aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # 使用二进制存储
                    socket_keepalive=True,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    max_connections=10
                )
                self.redis_enabled = True
                logger.info(f"Redis缓存已启用: {redis_url}")
            else:
                logger.warning(f"无效的Redis URL: {redis_url}")
        except Exception as e:
            logger.error(f"初始化Redis失败: {e}")
            self.redis_enabled = False

    def _get_cache_key(self, symbol: str, timeframe: str, **kwargs) -> str:
        """生成缓存键"""
        # 使用规范的Redis键格式
        params_str = json.dumps({"symbol": symbol, "timeframe": timeframe, **kwargs}, sort_keys=True)
        hash_suffix = hashlib.md5(params_str.encode()).hexdigest()[:8]

        # 格式: market:bars:{symbol}:{timeframe}:{adjust}:{hash}
        adjust = kwargs.get('adjust', 'none')
        return f"market:bars:{symbol}:{timeframe}:{adjust}:{hash_suffix}"

    async def _get_from_cache(self, symbol: str, timeframe: str, **kwargs) -> Optional[Any]:
        """从缓存获取数据（优先Redis，其次本地）"""
        key = self._get_cache_key(symbol, timeframe, **kwargs)
        ttl = self._cache_ttl.get(timeframe, 60)

        # 尝试从Redis获取
        if self.redis_enabled and self.redis_client:
            try:
                data = await self.redis_client.get(key)
                if data:
                    # 反序列化数据
                    cached_data = pickle.loads(data)
                    self.stats["cache_hits"] += 1
                    logger.debug(f"Redis缓存命中: {symbol} {timeframe}")
                    return cached_data
            except Exception as e:
                logger.warning(f"Redis读取失败: {e}")

        # 尝试从本地缓存获取
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] < ttl:
                self.stats["cache_hits"] += 1
                logger.debug(f"本地缓存命中: {symbol} {timeframe}")
                return entry["data"]

        self.stats["cache_misses"] += 1
        return None

    async def _set_cache(self, symbol: str, timeframe: str, data: Any, **kwargs) -> None:
        """设置缓存（同时写入Redis和本地）"""
        key = self._get_cache_key(symbol, timeframe, **kwargs)
        ttl = self._cache_ttl.get(timeframe, 60)

        # 写入Redis
        if self.redis_enabled and self.redis_client:
            try:
                # 序列化数据
                serialized = pickle.dumps(data)
                # 设置带TTL的缓存
                await self.redis_client.setex(key, ttl, serialized)
                logger.debug(f"写入Redis缓存: {key}, TTL: {ttl}s")
            except Exception as e:
                logger.warning(f"Redis写入失败: {e}")

        # 写入本地缓存
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
            # 使用最大TTL的2倍作为清理阈值
            if current_time - entry["timestamp"] > 1200:  # 20分钟
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 个过期缓存项")

    async def get_series(
            self,
            symbol: str,
            timeframe: str = "1d",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            limit: int = 500,
            adjust: str = "none",
            session_split: bool = True
    ) -> Dict:
        """
        获取K线数据序列
        
        Args:
            symbol: 股票代码
            timeframe: 时间周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1mo)
            start_date: 开始日期
            end_date: 结束日期
            limit: 数据条数限制
            adjust: 复权方式 (none, qfq, hfq)
            session_split: 是否分割交易时段（用于VWAP计算）
            
        Returns:
            包含meta信息和bars数据的字典
        """
        self.stats["total_requests"] += 1

        # 尝试从缓存获取
        cached = await self._get_from_cache(
            symbol, timeframe,
            start_date=start_date, end_date=end_date,
            limit=limit, adjust=adjust
        )
        if cached:
            return cached

        try:
            # 获取原始数据
            bars = await self._fetch_bars(symbol, timeframe, start_date, end_date, limit, adjust)

            # 处理会话信息
            if session_split and timeframe in ["1m", "3m", "5m", "15m", "30m", "60m"]:
                bars = self._add_session_info(bars)

            # 计算额外指标（如VWAP）
            bars = self._calculate_basic_metrics(bars)

            # 获取元数据
            meta = await self._get_meta_info(symbol, bars)

            # 清理NaN值
            if HAS_PANDAS and isinstance(bars, pd.DataFrame):
                bars_data = self._clean_nan_values(bars)
            else:
                bars_data = bars

            result = {
                "meta": self._clean_nan_values(meta),
                "bars": bars_data,
                "timestamp": datetime.now().isoformat()
            }

            # 缓存结果
            await self._set_cache(symbol, timeframe, result,
                                  start_date=start_date, end_date=end_date,
                                  limit=limit, adjust=adjust)

            self.stats["last_update"] = datetime.now()
            return result

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            self.stats["api_errors"] += 1

            # 尝试返回过期缓存
            cached = await self._get_from_cache(
                symbol, timeframe,
                start_date=start_date, end_date=end_date,
                limit=limit, adjust=adjust,
                ignore_ttl=True
            )
            if cached:
                cached["meta"]["stale"] = True
                return cached

            # 返回空数据
            return {
                "meta": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "stale": True,
                    "error": str(e)
                },
                "bars": [],
                "timestamp": datetime.now().isoformat()
            }

    async def _fetch_bars(
            self,
            symbol: str,
            timeframe: str,
            start_date: Optional[str],
            end_date: Optional[str],
            limit: int,
            adjust: str
    ) -> pd.DataFrame:
        """从数据源获取K线数据"""

        if not self.data_provider:
            # 返回空数据
            logger.error(f"No data provider available for {symbol} {timeframe}")
            return pd.DataFrame() if HAS_PANDAS else []

        # 根据时间周期选择不同的API
        if timeframe in ["1m", "3m", "5m", "15m", "30m", "60m"]:
            # 分钟级数据
            period_map = {
                "1m": "1",
                "3m": "3",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "60m": "60"
            }

            # 调用 stock_zh_a_hist_min_em
            try:
                response = await self.data_provider._fetch_with_fallback(
                    "stock_zh_a_hist_min_em",
                    {
                        "symbol": symbol,
                        "period": period_map[timeframe],
                        "start_date": start_date or "2020-01-01 09:30:00",
                        "end_date": end_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "adjust": adjust if adjust != "none" else ""
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to fetch minute data: {e}")
                return pd.DataFrame() if HAS_PANDAS else []

            if response:
                # Check if it's a mock response from the provider
                if "message" in response and "Mock data" in response.get("message", ""):
                    logger.info(f"Received mock response for {symbol} {timeframe}, returning empty data")
                    return pd.DataFrame() if HAS_PANDAS else []

                if "data" in response:
                    # 确保 response["data"] 是列表格式
                    data_list = response.get("data")
                    if isinstance(data_list, dict):
                        # 如果是字典，尝试转换为列表
                        data_list = [data_list]
                    elif not isinstance(data_list, list):
                        # 如果既不是字典也不是列表，返回模拟数据
                        logger.warning(f"Invalid data format for {symbol} {timeframe}: {type(data_list)}")
                        return pd.DataFrame() if HAS_PANDAS else []

                    if not data_list:
                        # 空数据，返回模拟数据
                        logger.warning(f"Empty data for {symbol} {timeframe}")
                        return pd.DataFrame() if HAS_PANDAS else []

                    try:
                        df = pd.DataFrame(data_list)
                    except Exception as e:
                        logger.error(f"Failed to create DataFrame from data_list: {e}")
                        logger.debug(
                            f"data_list type: {type(data_list)}, content: {data_list[:2] if isinstance(data_list, list) else data_list}")
                        return pd.DataFrame() if HAS_PANDAS else []

                    # 统一中英文列名
                    rename_map = {
                        "时间": "ts", "日期": "ts", "date": "ts", "datetime": "ts", "time": "ts",
                        "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
                        "成交量": "volume", "成交额": "amount"
                    }
                df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
                # 确保必需列存在
                if "ts" not in df.columns:
                    for cand in ["日期", "时间", "date", "datetime", "time"]:
                        if cand in df.columns:
                            df["ts"] = df[cand]
                            break
                # 转换类型
                if "ts" in df.columns:
                    try:
                        df["ts"] = pd.to_datetime(df["ts"])
                    except Exception:
                        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
                for col in ["open", "high", "low", "close", "volume", "amount"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                if "ts" in df.columns:
                    df = df.sort_values("ts").reset_index(drop=True)

                # 如果需要聚合到3分钟
                if timeframe == "3m":
                    df = self._aggregate_bars(df, 3)

                return df.tail(limit) if len(df) > limit else df

        elif timeframe in ["1d", "1w", "1mo"]:
            # 日线及以上级别数据
            period_map = {
                "1d": "daily",
                "1w": "weekly",
                "1mo": "monthly"
            }

            # 调用 stock_zh_a_hist
            try:
                response = await self.data_provider._fetch_with_fallback(
                    "stock_zh_a_hist",
                    {
                        "symbol": symbol,
                        "period": period_map[timeframe],
                        "start_date": start_date or "20200101",
                        "end_date": end_date or datetime.now().strftime("%Y%m%d"),
                        "adjust": adjust if adjust != "none" else ""
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to fetch daily data: {e}")
                return pd.DataFrame() if HAS_PANDAS else []

            if response:
                # Check if it's a mock response from the provider
                if "message" in response and "Mock data" in response.get("message", ""):
                    logger.info(f"Received mock response for {symbol} {timeframe}, returning empty data")
                    return pd.DataFrame() if HAS_PANDAS else []

                if "data" in response:
                    # 确保 response["data"] 是列表格式
                    data_list = response.get("data")

                    # 详细记录响应数据结构
                    logger.debug(f"Response data type for {symbol}: {type(data_list)}")
                    if isinstance(data_list, list):
                        logger.debug(f"Response data length for {symbol}: {len(data_list)}")
                        if data_list and len(data_list) > 0:
                            logger.debug(f"First item in data_list: {data_list[0]}")

                    if isinstance(data_list, dict):
                        # 如果是字典，可能是错误响应或单条数据，需要生成模拟数据
                        logger.warning(
                            f"Received single data point (dict) for {symbol}, fetching failed. Dict keys: {data_list.keys() if data_list else 'None'}")
                        return pd.DataFrame() if HAS_PANDAS else []
                    elif not isinstance(data_list, list):
                        # 如果既不是字典也不是列表，返回模拟数据
                        logger.warning(f"Invalid daily data format for {symbol}: {type(data_list)}")
                        return pd.DataFrame() if HAS_PANDAS else []

                    if not data_list or len(data_list) < 2:
                        # 空数据或数据太少，返回模拟数据
                        logger.warning(
                            f"Insufficient daily data for {symbol}: {len(data_list) if data_list else 0} bars")
                        return pd.DataFrame() if HAS_PANDAS else []

                df = pd.DataFrame(data_list)
                # 统一中英文列名
                rename_map = {
                    "日期": "ts", "时间": "ts", "date": "ts", "datetime": "ts", "time": "ts",
                    "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
                    "成交量": "volume", "成交额": "amount"
                }
                if not df.empty:
                    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
                    if "ts" not in df.columns:
                        for cand in ["日期", "时间", "date", "datetime", "time"]:
                            if cand in df.columns:
                                df["ts"] = df[cand]
                                break
                    if "ts" in df.columns:
                        try:
                            df["ts"] = pd.to_datetime(df["ts"])
                        except Exception:
                            df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
                    for col in ["open", "high", "low", "close", "volume", "amount"]:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    if "ts" in df.columns:
                        df = df.sort_values("ts").reset_index(drop=True)

                return df.tail(limit) if len(df) > limit else df
            else:
                # Response is None or doesn't have data
                logger.warning(f"No valid response for {symbol} {timeframe}")
                return pd.DataFrame() if HAS_PANDAS else []
        else:
            # No response at all, use mock data
            logger.warning(f"No response from API for {symbol} {timeframe}")
            return pd.DataFrame() if HAS_PANDAS else []

        # 如果没有数据，返回空数据
        logger.error(f"No data available for {symbol} {timeframe}")
        return pd.DataFrame() if HAS_PANDAS else []

    def _aggregate_bars(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """聚合K线数据到更大周期"""
        if not HAS_PANDAS or df.empty:
            return df

        # 检查 ts 列是否存在
        if 'ts' not in df.columns:
            logger.warning("DataFrame missing 'ts' column, cannot aggregate bars")
            return df

        # 设置时间索引
        df['ts'] = pd.to_datetime(df['ts'])
        df.set_index('ts', inplace=True)

        # 聚合规则
        agg_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'amount': 'sum'
        }

        # 按周期聚合
        resampled = df.resample(f'{period}T').agg(agg_rules)
        resampled.reset_index(inplace=True)

        # 过滤掉空值
        resampled = resampled.dropna()

        return resampled

    def _add_session_info(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加交易时段信息"""
        if not HAS_PANDAS or df.empty:
            return df

        # 检查 ts 列是否存在
        if 'ts' not in df.columns:
            logger.warning("DataFrame missing 'ts' column, skipping session info")
            return df

        df['ts'] = pd.to_datetime(df['ts'])

        # 判断上午还是下午
        df['session'] = df['ts'].apply(lambda x:
                                       'morning' if x.hour < 12 else 'afternoon'
                                       )

        # 标记会话开始
        df['session_start'] = False
        morning_start = df[(df['ts'].dt.hour == 9) & (df['ts'].dt.minute == 30)]
        afternoon_start = df[(df['ts'].dt.hour == 13) & (df['ts'].dt.minute == 0)]

        if not morning_start.empty:
            df.loc[morning_start.index, 'session_start'] = True
        if not afternoon_start.empty:
            df.loc[afternoon_start.index, 'session_start'] = True

        return df

    def _calculate_basic_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算基础指标（如VWAP）"""
        if not HAS_PANDAS or df.empty:
            return df

        # 检查必需列是否存在
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"DataFrame missing required columns: {missing_cols}")
            logger.debug(f"Available columns: {list(df.columns)}")
            # 返回原始DataFrame，避免计算失败
            return df

        # 确保数值列是数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 计算典型价格
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # 计算VWAP（成交量加权平均价）
        if 'session_start' in df.columns:
            # 按会话重置VWAP
            df['vwap'] = 0.0
            cumulative_pv = 0
            cumulative_volume = 0

            for i, row in df.iterrows():
                if row.get('session_start', False):
                    cumulative_pv = 0
                    cumulative_volume = 0

                cumulative_pv += row['typical_price'] * row['volume']
                cumulative_volume += row['volume']

                if cumulative_volume > 0:
                    df.at[i, 'vwap'] = cumulative_pv / cumulative_volume
                else:
                    df.at[i, 'vwap'] = row['typical_price']  # 使用典型价格作为默认值
        else:
            # 全局VWAP
            df['cumulative_pv'] = (df['typical_price'] * df['volume']).cumsum()
            df['cumulative_volume'] = df['volume'].cumsum()

            # 避免除零错误
            df['vwap'] = np.where(
                df['cumulative_volume'] > 0,
                df['cumulative_pv'] / df['cumulative_volume'],
                df['typical_price']  # 使用典型价格作为默认值
            )
            df.drop(['cumulative_pv', 'cumulative_volume'], axis=1, inplace=True)

        # 计算涨跌幅
        df['change'] = df['close'] - df['close'].shift(1)

        # 处理涨跌幅百分比，避免除零和第一行的NaN
        prev_close = df['close'].shift(1)
        df['change_pct'] = np.where(
            prev_close > 0,
            (df['change'] / prev_close) * 100,
            0
        )

        # 填充第一行的NaN值
        df['change'] = df['change'].fillna(0)
        df['change_pct'] = df['change_pct'].fillna(0)
        df['vwap'] = df['vwap'].fillna(df['typical_price'])

        # 替换所有inf值
        df = df.replace([np.inf, -np.inf], 0)

        return df

    async def _get_meta_info(self, symbol: str, bars: pd.DataFrame) -> Dict:
        """获取元数据信息"""
        meta = {
            "symbol": symbol,
            "tz": "Asia/Shanghai",
            "trading_sessions": self.TRADING_SESSIONS,
            "stale": False
        }

        if HAS_PANDAS and not bars.empty:
            # 检查必需列
            if 'close' in bars.columns and 'open' in bars.columns:
                # 前收盘价
                if len(bars) > 1:
                    meta["prev_close"] = float(bars.iloc[-2]['close'])
                else:
                    meta["prev_close"] = float(bars.iloc[0]['open'])

                # 涨跌停价（A股10%）
                meta["upper_limit"] = round(meta["prev_close"] * 1.1, 2)
                meta["lower_limit"] = round(meta["prev_close"] * 0.9, 2)

            # 统计信息
            meta["bar_count"] = len(bars)

            # 日期范围
            if 'ts' in bars.columns:
                meta["date_range"] = {
                    "start": str(bars.iloc[0]['ts']),
                    "end": str(bars.iloc[-1]['ts'])
                }

        return meta

    async def calculate_indicators(
            self,
            symbol: str,
            timeframe: str,
            indicators: List[Dict],
            bars_data: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        计算技术指标
        
        Args:
            symbol: 股票代码
            timeframe: 时间周期
            indicators: 指标配置列表
            bars_data: K线数据（如果为None则自动获取）
            
        Returns:
            指标计算结果
        """
        # 如果没有提供数据，先获取
        if bars_data is None:
            series_data = await self.get_series(symbol, timeframe)
            if not series_data.get("bars"):
                return {}

            bars_data = pd.DataFrame(series_data["bars"])

        results = {}

        # 没有指标计算器时，不返回模拟指标，直接返回空结果，确保数据必须真实
        if not self.indicator_calculator:
            logger.warning("Indicator calculator not configured; returning empty results (no mock indicators)")
            return {}

        # 使用指标计算器计算
        for indicator in indicators:
            name = indicator["name"]
            params = indicator.get("params", {})
            pane = indicator.get("pane", "main")

            try:
                # 调用对应的指标计算方法
                if hasattr(self.indicator_calculator, name.lower()):
                    method = getattr(self.indicator_calculator, name.lower())
                    result = method(bars_data, **params)

                    # 格式化输出
                    if isinstance(result, tuple):
                        # 多值输出（如MACD）
                        series_data = {}
                        for i, key in enumerate(["main", "signal", "histogram"]):
                            if i < len(result):
                                data = result[i]
                                if hasattr(data, 'fillna'):
                                    data = data.fillna(0).replace([np.inf, -np.inf], 0)
                                series_data[f"{name}_{key}"] = data.tolist() if hasattr(data, 'tolist') else data
                    elif isinstance(result, dict):
                        series_data = {}
                        for k, v in result.items():
                            if hasattr(v, 'fillna'):
                                v = v.fillna(0).replace([np.inf, -np.inf], 0)
                            series_data[k] = v.tolist() if hasattr(v, 'tolist') else v
                    else:
                        if hasattr(result, 'fillna'):
                            result = result.fillna(0).replace([np.inf, -np.inf], 0)
                        series_data = {name: result.tolist() if hasattr(result, 'tolist') else result}

                    # 清理NaN值
                    series_data = self._clean_nan_values(series_data)

                    results[name] = {
                        "pane": pane,
                        "series": series_data,
                        "style": self._get_indicator_style(name)
                    }
                else:
                    # 指标不存在，返回空数据
                    logger.warning(f"Indicator {name} not found, returning empty data")
                    results[name] = {
                        "pane": pane,
                        "series": {},
                        "style": {}
                    }

            except Exception as e:
                logger.error(f"计算指标 {name} 失败: {e}")
                results[name] = {
                    "pane": pane,
                    "series": {},
                    "error": str(e)
                }

        return results


    def _get_indicator_style(self, name: str) -> Dict:
        """获取指标默认样式"""
        styles = {
            "MA": {"type": "line", "smooth": True},
            "EMA": {"type": "line", "smooth": True},
            "BOLL": {"type": "line", "areas": True},
            "MACD": {"type": "bar", "colors": ["#ff0000", "#00ff00", "#0000ff"]},
            "RSI": {"type": "line", "bands": [30, 70]},
            "KDJ": {"type": "line", "colors": ["#ff0000", "#00ff00", "#0000ff"]},
            "ATR": {"type": "line"},
            "OBV": {"type": "line"},
            "VWAP": {"type": "line", "lineWidth": 2, "color": "#9c27b0"},
            "Volume": {"type": "bar", "colorKey": "change"}
        }

        return styles.get(name.upper(), {"type": "line"})

    def get_indicator_list(self) -> List[Dict]:
        """获取可用指标列表"""
        indicators = [
            {
                "name": "MA",
                "label": "移动平均线",
                "category": "trend",
                "pane": "main",
                "params": {
                    "periods": {"type": "array", "default": [5, 10, 20, 60], "min": 1, "max": 250}
                }
            },
            {
                "name": "EMA",
                "label": "指数移动平均",
                "category": "trend",
                "pane": "main",
                "params": {
                    "periods": {"type": "array", "default": [12, 26], "min": 1, "max": 250}
                }
            },
            {
                "name": "BOLL",
                "label": "布林带",
                "category": "volatility",
                "pane": "main",
                "params": {
                    "period": {"type": "number", "default": 20, "min": 5, "max": 100},
                    "std": {"type": "number", "default": 2, "min": 1, "max": 5}
                }
            },
            {
                "name": "VWAP",
                "label": "成交量加权平均价",
                "category": "volume",
                "pane": "main",
                "params": {
                    "sessionReset": {"type": "boolean", "default": True}
                }
            },
            {
                "name": "MACD",
                "label": "平滑异同移动平均",
                "category": "momentum",
                "pane": "sub",
                "params": {
                    "fast": {"type": "number", "default": 12, "min": 2, "max": 100},
                    "slow": {"type": "number", "default": 26, "min": 2, "max": 100},
                    "signal": {"type": "number", "default": 9, "min": 2, "max": 100}
                }
            },
            {
                "name": "RSI",
                "label": "相对强弱指标",
                "category": "momentum",
                "pane": "sub",
                "params": {
                    "period": {"type": "number", "default": 14, "min": 2, "max": 100}
                }
            },
            {
                "name": "KDJ",
                "label": "随机指标",
                "category": "momentum",
                "pane": "sub",
                "params": {
                    "n": {"type": "number", "default": 9, "min": 1, "max": 100},
                    "m1": {"type": "number", "default": 3, "min": 1, "max": 100},
                    "m2": {"type": "number", "default": 3, "min": 1, "max": 100}
                }
            },
            {
                "name": "ATR",
                "label": "真实波幅",
                "category": "volatility",
                "pane": "sub",
                "params": {
                    "period": {"type": "number", "default": 14, "min": 1, "max": 100}
                }
            },
            {
                "name": "OBV",
                "label": "能量潮",
                "category": "volume",
                "pane": "sub",
                "params": {}
            },
            {
                "name": "Volume",
                "label": "成交量",
                "category": "volume",
                "pane": "sub",
                "params": {}
            }
        ]

        return indicators

    async def get_snapshot(self, symbol: str) -> Dict:
        """
        获取实时快照数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情快照
        """
        # 这里应该调用实时行情接口
        # 暂时返回模拟数据
        import random

        price = round(10 + random.uniform(-1, 1), 2)
        prev_close = 10
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2)

        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "price": price,
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "open": round(10 + random.uniform(-0.5, 0.5), 2),
            "high": round(price + random.uniform(0, 0.5), 2),
            "low": round(price - random.uniform(0, 0.5), 2),
            "volume": random.randint(1000000, 10000000),
            "amount": random.randint(10000000, 100000000),
            "turnover_rate": round(random.uniform(0.5, 5), 2),
            "upper_limit": round(prev_close * 1.1, 2),
            "lower_limit": round(prev_close * 0.9, 2),
            "vwap": round(price + random.uniform(-0.1, 0.1), 2),
            "session": "trading",  # pre_market, trading, after_hours, closed
            "timestamp": datetime.now().isoformat()
        }

    def subscribe(self, symbol: str, timeframe: str, callback=None) -> str:
        """
        订阅实时数据
        
        Args:
            symbol: 股票代码
            timeframe: 时间周期
            callback: 数据回调函数
            
        Returns:
            订阅ID
        """
        subscription_id = f"{symbol}_{timeframe}_{int(time.time() * 1000)}"

        self._subscriptions[subscription_id] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "callback": callback,
            "created_at": datetime.now()
        }

        # 启动异步任务定期获取数据
        if subscription_id not in self._subscription_tasks:
            task = asyncio.create_task(self._subscription_loop(subscription_id))
            self._subscription_tasks[subscription_id] = task

        logger.info(f"订阅成功: {subscription_id}")
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]

            # 取消异步任务
            if subscription_id in self._subscription_tasks:
                task = self._subscription_tasks[subscription_id]
                task.cancel()
                del self._subscription_tasks[subscription_id]

            logger.info(f"取消订阅: {subscription_id}")
            return True

        return False

    async def _subscription_loop(self, subscription_id: str):
        """订阅数据循环"""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return

        symbol = subscription["symbol"]
        timeframe = subscription["timeframe"]
        callback = subscription["callback"]

        # 根据时间周期设置更新间隔
        interval = self._cache_ttl.get(timeframe, 60)

        while subscription_id in self._subscriptions:
            try:
                # 获取最新数据
                data = await self.get_series(symbol, timeframe, limit=2)

                if callback and data.get("bars"):
                    # 调用回调函数
                    await callback({
                        "type": "bar_update",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "data": data["bars"][-1] if data["bars"] else None
                    })

                # 等待下次更新
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"订阅循环错误 {subscription_id}: {e}")
                await asyncio.sleep(interval)

    async def get_statistics(self) -> Dict:
        """获取服务统计信息"""
        cache_hit_rate = 0
        if self.stats["total_requests"] > 0:
            cache_hit_rate = self.stats["cache_hits"] / self.stats["total_requests"] * 100

        redis_info = {}
        if self.redis_enabled and self.redis_client:
            try:
                # 获取Redis信息
                info = await self.redis_client.info()
                redis_info = {
                    "connected": True,
                    "used_memory": info.get('used_memory_human', 'N/A'),
                    "connected_clients": info.get('connected_clients', 0),
                    "total_commands": info.get('total_commands_processed', 0)
                }
            except:
                redis_info = {"connected": False}

        return {
            "total_requests": self.stats["total_requests"],
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "cache_hit_rate": round(cache_hit_rate, 2),
            "api_errors": self.stats["api_errors"],
            "local_cache_size": len(self._cache),
            "redis_cache": redis_info,
            "active_subscriptions": len(self._subscriptions),
            "last_update": self.stats["last_update"].isoformat() if self.stats["last_update"] else None
        }
