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
from deepsearch.services.data.data_service_adapter import DataServiceAdapter

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    from deepsearch.indicators.chip_distribution import ChipDistribution

    HAS_CHIP = True
except ImportError:
    HAS_CHIP = False
    ChipDistribution = None

try:
    from deepsearch.services.cache.kline_cache import KlineCache

    HAS_KLINE_CACHE = True
except ImportError:
    HAS_KLINE_CACHE = False
    KlineCache = None

try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None

try:
    from deepsearch.services.market.adjust_service import get_adjust_service

    HAS_ADJUST = True
except ImportError:
    HAS_ADJUST = False
    get_adjust_service = None


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

    def __init__(self, data_provider=None, indicator_calculator=None, redis_url: Optional[str] = None,
                 provider_manager=None, use_unified_manager: bool = True, stock_info_service=None):
        """
        初始化图表服务
        
        Args:
            data_provider: 默认数据提供者（如 AkShareProxyProvider）
            indicator_calculator: 指标计算器（如 TechnicalIndicators）
            redis_url: Redis连接URL（可选）
            provider_manager: 数据提供者管理器（可选）
            use_unified_manager: 是否使用统一数据管理器
            stock_info_service: 股票信息服务（可选）
        """
        # 包装为适配器
        if data_provider is not None:
            self.data_adapter = DataServiceAdapter(data_provider)
        else:
            self.data_adapter = DataServiceAdapter()
        self.data_provider = data_provider
        self.default_provider = data_provider
        self.indicator_calculator = indicator_calculator
        self.provider_manager = provider_manager
        self._current_provider = None
        self.use_unified_manager = use_unified_manager
        self._unified_manager = None

        # 股票信息服务
        if stock_info_service is None:
            try:
                from deepsearch.services.interfaces.stock_info_service import get_stock_info_service
                self.stock_info_service = get_stock_info_service()
            except ImportError:
                logger.warning("无法导入StockInfoService，上市日期功能将使用默认值")
                self.stock_info_service = None
        else:
            self.stock_info_service = stock_info_service

        # Redis缓存配置
        self.redis_client = None
        self.redis_enabled = False
        if redis_url and HAS_REDIS:
            self._init_redis(redis_url)

        # 分层缓存管理器
        self.kline_cache = None
        if HAS_KLINE_CACHE:
            try:
                self.kline_cache = KlineCache(
                    redis_client=self.redis_client,
                    db_path="./data/kline_cache.db"
                )
                logger.info("分层缓存管理器初始化成功")
            except Exception as e:
                logger.warning(f"分层缓存管理器初始化失败: {e}")

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
            "last_update": None,
            "current_provider": None
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
            df_clean = data.fillna(0).replace([np.inf, -np.inf], 0)

            # 处理时间字段 - 将ts重命名为time供前端使用
            if 'ts' in df_clean.columns:
                df_clean = df_clean.copy()
                # 格式化时间字段
                if pd.api.types.is_datetime64_any_dtype(df_clean['ts']):
                    # 根据数据频率决定时间格式
                    if len(df_clean) > 0:
                        # 检查是否为日线数据（时间间隔大于1天）
                        time_diff = df_clean['ts'].iloc[-1] - df_clean['ts'].iloc[0] if len(
                            df_clean) > 1 else pd.Timedelta(days=0)
                        if time_diff.days > 0 and len(df_clean) < 500:  # 日线数据
                            df_clean['time'] = df_clean['ts'].dt.strftime('%Y-%m-%d')
                        else:  # 分钟线数据
                            df_clean['time'] = df_clean['ts'].dt.strftime('%Y-%m-%d %H:%M')
                    else:
                        df_clean['time'] = df_clean['ts'].dt.strftime('%Y-%m-%d %H:%M')
                else:
                    # 如果不是datetime类型，尝试转换
                    try:
                        df_clean['time'] = pd.to_datetime(df_clean['ts']).dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        df_clean['time'] = df_clean['ts'].astype(str)

                # 删除原始ts列，避免混淆
                df_clean = df_clean.drop(columns=['ts'])

            return df_clean.to_dict(orient="records")
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
            session_split: bool = True,
            provider: Optional[str] = None
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

        # 如果启用了分层缓存，优先使用
        if self.kline_cache:
            try:
                bars, source = await self.kline_cache.get_data(
                    symbol, timeframe, start_date, end_date, limit
                )
                if bars is not None and not bars.empty:
                    logger.info(f"从分层缓存获取数据成功，来源: {source}")
                    # 处理数据格式
                    bars = self._standardize_columns(bars)
                    if session_split and timeframe in ["1m", "3m", "5m", "15m", "30m", "60m"]:
                        bars = self._add_session_info(bars)
                    bars = self._calculate_basic_metrics(bars)

                    meta = await self._get_meta_info(symbol, bars)
                    meta["data_source"] = source
                    meta["cached"] = True

                    result = {
                        "meta": self._clean_nan_values(meta),
                        "bars": self._clean_nan_values(bars),
                        "timestamp": datetime.now().isoformat(),
                        "source": source
                    }
                    return result
            except Exception as e:
                logger.warning(f"分层缓存获取失败: {e}，回退到普通缓存")

        # 尝试从普通缓存获取
        cached = await self._get_from_cache(
            symbol, timeframe,
            start_date=start_date, end_date=end_date,
            limit=limit, adjust=adjust
        )
        if cached:
            return cached

        try:
            # 获取原始数据
            bars = await self._fetch_bars(symbol, timeframe, start_date, end_date, limit, adjust, provider)

            # 标准化列名（中文转英文）
            if HAS_PANDAS and isinstance(bars, pd.DataFrame):
                bars = self._standardize_columns(bars)

            # 应用复权处理
            if HAS_ADJUST and adjust != "none" and HAS_PANDAS and isinstance(bars, pd.DataFrame):
                try:
                    adjust_service = get_adjust_service()
                    bars = await adjust_service.get_adjusted_kline(symbol, bars, adjust)
                    logger.debug(f"已应用{adjust}复权处理")
                except Exception as e:
                    logger.warning(f"应用复权处理失败: {e}")

            # 处理会话信息
            if session_split and timeframe in ["1m", "3m", "5m", "15m", "30m", "60m"]:
                bars = self._add_session_info(bars)

            # 计算额外指标（如VWAP）
            bars = self._calculate_basic_metrics(bars)

            # 获取元数据
            meta = await self._get_meta_info(symbol, bars)

            # 添加数据源信息到元数据
            meta["data_source"] = self.stats.get("current_provider", "unknown")
            meta["data_validated"] = False  # 标记是否经过多源验证

            # 清理NaN值
            if HAS_PANDAS and isinstance(bars, pd.DataFrame):
                bars_data = self._clean_nan_values(bars)
            else:
                bars_data = bars

            result = {
                "meta": self._clean_nan_values(meta),
                "bars": bars_data,
                "timestamp": datetime.now().isoformat(),
                "source": self.stats.get("current_provider", "unknown")
            }

            # 缓存结果
            await self._set_cache(symbol, timeframe, result,
                                  start_date=start_date, end_date=end_date,
                                  limit=limit, adjust=adjust)

            # 保存到分层缓存
            if self.kline_cache and bars_data:
                try:
                    if isinstance(bars_data, list):
                        bars_df = pd.DataFrame(bars_data)
                    else:
                        bars_df = bars_data
                    await self.kline_cache.save_data(symbol, timeframe, bars_df)
                except Exception as e:
                    logger.warning(f"保存到分层缓存失败: {e}")

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

    async def _get_unified_manager(self):
        """获取统一数据管理器实例"""
        if self._unified_manager is None and self.use_unified_manager:
            try:
                from deepsearch.services.data.unified_data_manager import get_unified_data_manager
                self._unified_manager = await get_unified_data_manager()
                logger.info("已启用统一数据管理器")
            except Exception as e:
                logger.error(f"初始化统一数据管理器失败: {e}")
                self.use_unified_manager = False
        return self._unified_manager

    def _timeframe_to_period(self, timeframe: str) -> str:
        """将 timeframe 转换为 period 格式"""
        # 映射关系
        period_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
            "1d": "daily",
            "1w": "weekly",
            "1mo": "monthly"
        }
        return period_map.get(timeframe, "daily")

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化DataFrame列名（中文转英文）"""
        if not HAS_PANDAS or df is None or df.empty:
            return df

        # 列名映射表
        column_mapping = {
            '日期': 'date',
            '时间': 'time',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'pct_change',
            '涨跌额': 'change',
            '振幅': 'amplitude',
            '换手率': 'turnover_rate'
        }

        # 重命名列
        df = df.rename(columns=column_mapping)

        # 确保必要的列存在
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in df.columns:
                logger.warning(f"Missing required column: {col}")

        return df

    def get_current_provider(self, provider_name: Optional[str] = None):
        """获取当前使用的数据提供者"""
        if provider_name and self.provider_manager:
            # 尝试获取指定的提供者
            provider = self.provider_manager.get_provider(provider_name)
            if provider:
                self._current_provider = provider
                self.stats["current_provider"] = provider_name
                return provider
            else:
                logger.warning(f"Provider {provider_name} not found, using default")

        # 使用默认提供者
        if self.default_provider:
            self.stats["current_provider"] = "default"
            return self.default_provider

        return None

    async def _fetch_bars(
            self,
            symbol: str,
            timeframe: str,
            start_date: Optional[str],
            end_date: Optional[str],
            limit: int,
            adjust: str,
            provider_name: Optional[str] = None
    ) -> pd.DataFrame:
        """从数据源获取K线数据"""

        # 优先使用统一数据管理器
        unified_manager = await self._get_unified_manager()
        if unified_manager and self.use_unified_manager:
            try:
                # 将 provider_name 转换为 DataSourceType
                from deepsearch.services.data.unified_data_manager import DataSourceType
                preferred_source = None
                if provider_name:
                    source_map = {
                        "qmt": DataSourceType.QMT,
                        "cloudflare": DataSourceType.CLOUDFLARE,
                        "akshare": DataSourceType.AKSHARE,
                        "direct": DataSourceType.DIRECT_API
                    }
                    preferred_source = source_map.get(provider_name.lower())

                # 调用统一管理器获取数据
                result = await unified_manager.get_stock_hist(
                    symbol=symbol,
                    period=self._timeframe_to_period(timeframe),
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                    preferred_source=preferred_source
                )

                if result and "data" in result:
                    # 转换为 DataFrame
                    if HAS_PANDAS:
                        df = pd.DataFrame(result["data"])
                        if not df.empty:
                            # 记录数据源
                            self.stats["current_provider"] = result.get("source", "unified")
                            logger.info(f"从 {result.get('source', 'unified')} 获取到 {len(df)} 条数据")
                            return df
                    else:
                        return result["data"]

            except Exception as e:
                logger.warning(f"统一数据管理器获取数据失败: {e}，回退到直接提供者")

        # 回退到原有逻辑
        provider = self.get_current_provider(provider_name)

        if not provider:
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
                # 默认获取最近两个月的数据
                from datetime import timedelta
                default_start = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d 09:30:00")

                response = await self.data_adapter.fetch_api(
                    "stock_zh_a_hist_min_em",
                    {
                        "symbol": symbol,
                        "period": period_map[timeframe],
                        "start_date": start_date or default_start,
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
                # 默认获取最近两年的数据（约730天）
                from datetime import timedelta
                default_start = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

                response = await self.data_adapter.fetch_api(
                    "stock_zh_a_hist",
                    {
                        "symbol": symbol,
                        "period": period_map[timeframe],
                        "start_date": start_date or default_start,
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
                            # 使用json.dumps()避免中文键导致的格式化错误
                            import json
                            logger.debug(f"First item in data_list: {json.dumps(data_list[0], ensure_ascii=False)}")

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
                    # Response has no "data" key
                    logger.warning(f"Response has no 'data' key for {symbol} {timeframe}")
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

        # 导入指标注册表
        try:
            from deepsearch.indicators.technical import INDICATOR_REGISTRY
        except ImportError:
            INDICATOR_REGISTRY = {}

        # 使用指标计算器计算
        for indicator in indicators:
            name = indicator["name"]
            params = indicator.get("params", {})
            pane = indicator.get("pane", "main")

            try:
                # 首先从注册表查找真实的函数名
                method_name = name.lower()
                if name.upper() in INDICATOR_REGISTRY:
                    registry_info = INDICATOR_REGISTRY[name.upper()]
                    method_name = registry_info.get("func", name.lower())
                    logger.debug(f"Using registered method '{method_name}' for indicator '{name}'")
                
                # 参数映射处理 - 解决前后端参数名不一致问题
                # BOLL指标: 前端使用std_dev，后端TA-Lib使用nbdev
                if name.upper() == 'BOLL' and 'std_dev' in params:
                    params['nbdev'] = params.pop('std_dev')
                    logger.debug(f"BOLL参数映射: std_dev -> nbdev = {params['nbdev']}")
                
                # 调用对应的指标计算方法
                if hasattr(self.indicator_calculator, method_name):
                    method = getattr(self.indicator_calculator, method_name)
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
                    logger.warning(f"Indicator method '{method_name}' not found for '{name}', returning empty data")
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

    async def validate_data_sources(self, symbol: str, timeframe: str = "1d") -> Dict:
        """
        验证多个数据源的数据一致性
        
        Args:
            symbol: 股票代码
            timeframe: 时间周期
            
        Returns:
            包含各数据源数据和差异分析的字典
        """
        unified_manager = await self._get_unified_manager()
        if not unified_manager:
            return {"error": "统一数据管理器未启用"}

        from deepsearch.services.data.unified_data_manager import DataSourceType

        results = {}
        data_points = []

        # 从所有可用数据源获取数据
        for source_type in DataSourceType:
            try:
                result = await unified_manager.get_stock_hist(
                    symbol=symbol,
                    period=self._timeframe_to_period(timeframe),
                    limit=1,  # 只获取最新的一条数据用于比较
                    preferred_source=source_type
                )

                if result and "data" in result and result["data"]:
                    latest = result["data"][-1] if isinstance(result["data"], list) else result["data"]
                    results[source_type.value] = {
                        "data": latest,
                        "source": result.get("source"),
                        "latency": result.get("latency")
                    }

                    # 收集关键数据点用于比较
                    if isinstance(latest, dict):
                        data_points.append({
                            "source": source_type.value,
                            "close": latest.get("收盘", latest.get("close", 0)),
                            "volume": latest.get("成交量", latest.get("volume", 0)),
                            "high": latest.get("最高", latest.get("high", 0)),
                            "low": latest.get("最低", latest.get("low", 0))
                        })

            except Exception as e:
                results[source_type.value] = {"error": str(e)}

        # 分析数据差异
        if len(data_points) > 1:
            # 计算价格差异
            closes = [p["close"] for p in data_points if p["close"] > 0]
            if closes:
                max_close = max(closes)
                min_close = min(closes)
                avg_close = sum(closes) / len(closes)
                price_variance = (max_close - min_close) / avg_close * 100 if avg_close > 0 else 0

                results["analysis"] = {
                    "price_variance_pct": round(price_variance, 2),
                    "sources_count": len(data_points),
                    "consensus_price": round(avg_close, 2),
                    "max_price": max_close,
                    "min_price": min_close,
                    "reliable": price_variance < 0.5  # 价格差异小于0.5%认为可靠
                }
            else:
                results["analysis"] = {"error": "无有效价格数据"}
        else:
            results["analysis"] = {"error": "数据源不足，无法比较"}

        return results

    def _get_trading_session(self) -> str:
        """
        获取当前交易时段
        
        Returns:
            交易时段: pre_market, trading, after_hours, closed
        """
        from datetime import datetime, time
        import pytz

        # 使用上海时区
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        current_time = now.time()
        weekday = now.weekday()  # 0=周一, 6=周日

        # 周末休市
        if weekday >= 5:  # 周六或周日
            return "closed"

        # 交易时段定义
        pre_market_start = time(9, 15)
        pre_market_end = time(9, 30)
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)

        # 判断时段
        if pre_market_start <= current_time < pre_market_end:
            return "pre_market"
        elif (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end):
            return "trading"
        elif time(15, 0) < current_time <= time(15, 30):
            return "after_hours"
        else:
            return "closed"
    
    async def get_snapshot(self, symbol: str) -> Dict:
        """
        获取实时快照数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情快照
        """
        try:
            # 优先从数据提供者获取实时行情
            if self.data_provider and hasattr(self.data_provider, 'get_realtime_quote'):
                quote_data = await self.data_provider.get_realtime_quote(symbol)

                if quote_data and not quote_data.get("error"):
                    # 计算涨跌幅相关数据
                    price = quote_data.get("current", 0)
                    prev_close = quote_data.get("prev_close", price)
                    change = price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    # 计算涨跌停价格
                    # 创业板(300开头)涨跌幅限制为20%，其他为10%
                    limit_ratio = 0.2 if symbol.startswith("300") or symbol.startswith("688") else 0.1
                    upper_limit = round(prev_close * (1 + limit_ratio), 2)
                    lower_limit = round(prev_close * (1 - limit_ratio), 2)

                    return {
                        "symbol": symbol,
                        "name": quote_data.get("name", f"股票{symbol}"),
                        "price": price,
                        "prev_close": prev_close,
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2),
                        "open": quote_data.get("open", 0),
                        "high": quote_data.get("high", 0),
                        "low": quote_data.get("low", 0),
                        "volume": quote_data.get("volume", 0),
                        "amount": quote_data.get("amount", 0),
                        "turnover_rate": quote_data.get("turnover_rate", 0),
                        "upper_limit": upper_limit,
                        "lower_limit": lower_limit,
                        "vwap": quote_data.get("vwap", price),
                        "session": self._get_trading_session(),
                        "timestamp": datetime.now().isoformat()
                    }

            # 如果没有数据提供者或获取失败，尝试从统一数据管理器获取
            unified_manager = await self._get_unified_manager()
            if unified_manager:
                quote_result = await unified_manager.get_realtime_quote(symbol)
                if quote_result and quote_result.get("data"):
                    quote_data = quote_result["data"]
                    price = quote_data.get("current", 0)
                    prev_close = quote_data.get("prev_close", price)
                    change = price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0

                    limit_ratio = 0.2 if symbol.startswith("300") or symbol.startswith("688") else 0.1
                    upper_limit = round(prev_close * (1 + limit_ratio), 2)
                    lower_limit = round(prev_close * (1 - limit_ratio), 2)

                    return {
                        "symbol": symbol,
                        "name": quote_data.get("name", f"股票{symbol}"),
                        "price": price,
                        "prev_close": prev_close,
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2),
                        "open": quote_data.get("open", 0),
                        "high": quote_data.get("high", 0),
                        "low": quote_data.get("low", 0),
                        "volume": quote_data.get("volume", 0),
                        "amount": quote_data.get("amount", 0),
                        "turnover_rate": quote_data.get("turnover_rate", 0),
                        "upper_limit": upper_limit,
                        "lower_limit": lower_limit,
                        "vwap": quote_data.get("vwap", price),
                        "session": self._get_trading_session(),
                        "timestamp": datetime.now().isoformat()
                    }

        except Exception as e:
            logger.error(f"获取股票 {symbol} 快照失败: {e}")

        # 如果都失败了，返回空数据
        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "price": 0,
            "prev_close": 0,
            "change": 0,
            "change_pct": 0,
            "open": 0,
            "high": 0,
            "low": 0,
            "volume": 0,
            "amount": 0,
            "turnover_rate": 0,
            "upper_limit": 0,
            "lower_limit": 0,
            "vwap": 0,
            "session": "closed",
            "timestamp": datetime.now().isoformat(),
            "error": "无法获取实时数据"
        }

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """获取所有可用的数据提供者列表"""
        providers = []

        # 添加默认提供者
        if self.default_provider:
            providers.append({
                "name": "default",
                "label": "Cloudflare代理",
                "type": "proxy",
                "enabled": True,
                "status": "running"
            })

        # 添加管理器中的提供者
        if self.provider_manager:
            for name in self.provider_manager.get_available_providers():
                provider = self.provider_manager.get_provider(name)
                if provider:
                    label_map = {
                        "miniqmt": "MiniQMT本地",
                        "qmt": "QMT实时",
                        "akshare": "AkShare",
                        "cloudflare_proxy": "Cloudflare代理"
                    }
                    providers.append({
                        "name": name,
                        "label": label_map.get(name, name),
                        "type": getattr(provider, "provider_type", "unknown"),
                        "enabled": True,
                        "status": "running"
                    })

        return providers

    async def get_stock_list(self, keyword: str = None) -> List[Dict]:
        """
        获取股票列表，支持关键字搜索
        
        Args:
            keyword: 搜索关键字（可选）
            
        Returns:
            股票列表
        """
        try:
            # 尝试从data_provider获取股票列表
            stock_list = []
            if self.data_provider and hasattr(self.data_provider, 'fetch_stock_list'):
                try:
                    stock_list = await self.data_provider.fetch_stock_list()
                except Exception as e:
                    logger.warning(f"从数据提供者获取股票列表失败: {e}")
                    stock_list = []

            # 如果获取成功且有数据
            if stock_list:
                # 如果有关键字，进行过滤
                if keyword:
                    keyword_lower = keyword.lower()
                    filtered = []
                    for stock in stock_list:
                        code = str(stock.get('代码', stock.get('code', '')))
                        name = stock.get('名称', stock.get('name', ''))
                        # 匹配代码或名称
                        if keyword_lower in code.lower() or keyword_lower in name.lower():
                            filtered.append({
                                'code': code,
                                'name': name,
                                'label': f"{name} ({code})",
                                'value': code
                            })
                    return filtered[:20]  # 限制返回20条
                else:
                    # 返回全部，格式化
                    return [{
                        'code': str(stock.get('代码', stock.get('code', ''))),
                        'name': stock.get('名称', stock.get('name', '')),
                        'label': f"{stock.get('名称', stock.get('name', ''))} ({stock.get('代码', stock.get('code', ''))})",
                        'value': str(stock.get('代码', stock.get('code', '')))
                    } for stock in stock_list[:100]]  # 限制100条

            # 返回模拟数据
            mock_stocks = [
                {'code': '000001', 'name': '平安银行', 'label': '平安银行 (000001)', 'value': '000001'},
                {'code': '000002', 'name': '万科A', 'label': '万科A (000002)', 'value': '000002'},
                {'code': '600000', 'name': '浦发银行', 'label': '浦发银行 (600000)', 'value': '600000'},
                {'code': '600036', 'name': '招商银行', 'label': '招商银行 (600036)', 'value': '600036'},
                {'code': '601606', 'name': '长城军工', 'label': '长城军工 (601606)', 'value': '601606'},
            ]

            if keyword:
                keyword_lower = keyword.lower()
                return [s for s in mock_stocks if
                        keyword_lower in s['code'].lower() or keyword_lower in s['name'].lower()]
            return mock_stocks

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    async def get_stock_info(self, symbol: str) -> Dict:
        """
        获取股票基础信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票基础信息
        """
        try:
            # 如果data_provider支持获取股票信息，则调用
            if self.data_provider and hasattr(self.data_provider, 'fetch_stock_info'):
                info = await self.data_provider.fetch_stock_info(symbol)
                if info:
                    # 处理返回的数据格式
                    result = {
                        "symbol": symbol,
                        "name": info.get('股票简称', info.get('name', f'股票{symbol}')),
                        "full_name": info.get('公司名称', info.get('full_name', '')),
                        "market": info.get('市场', info.get('market', '主板')),
                        "industry": info.get('行业', info.get('industry', '')),
                        "sector": info.get('细分行业', info.get('sector', '')),
                        "listed_date": info.get('上市日期', info.get('listed_date', '')),
                        "total_shares": info.get('总股本', info.get('total_shares', 0)),
                        "float_shares": info.get('流通股本', info.get('float_shares', 0)),
                        "market_cap": info.get('总市值', info.get('market_cap', 0)),
                        "float_market_cap": info.get('流通市值', info.get('float_market_cap', 0)),
                        "pe_ratio": info.get('市盈率', info.get('pe_ratio', 0)),
                        "pb_ratio": info.get('市净率', info.get('pb_ratio', 0)),
                        "ps_ratio": info.get('市销率', info.get('ps_ratio', 0)),
                        "roe": info.get('ROE', info.get('roe', 0)),
                        "eps": info.get('每股收益', info.get('eps', 0)),
                        "bvps": info.get('每股净资产', info.get('bvps', 0)),
                        "main_business": info.get('主营业务', info.get('main_business', '')),
                        "business_scope": info.get('经营范围', info.get('business_scope', '')),
                        "website": info.get('公司网站', info.get('website', '')),
                        "area": info.get('所在地区', info.get('area', '')),
                        "employees": info.get('员工人数', info.get('employees', 0)),
                        "update_time": datetime.now().isoformat()
                    }
                    return self._clean_nan_values(result)

            # 否则返回模拟数据
            import random

            return {
                "symbol": symbol,
                "name": f"股票{symbol}",
                "full_name": f"某某科技股份有限公司",
                "market": "主板",
                "industry": "信息技术",
                "sector": "软件服务",
                "listed_date": "2010-01-01",
                "total_shares": random.randint(1000000000, 5000000000),  # 总股本
                "float_shares": random.randint(500000000, 2000000000),  # 流通股本
                "market_cap": random.randint(10000000000, 100000000000),  # 总市值
                "float_market_cap": random.randint(5000000000, 50000000000),  # 流通市值
                "pe_ratio": round(random.uniform(10, 50), 2),  # 市盈率
                "pb_ratio": round(random.uniform(1, 5), 2),  # 市净率
                "ps_ratio": round(random.uniform(1, 10), 2),  # 市销率
                "roe": round(random.uniform(5, 25), 2),  # 净资产收益率
                "eps": round(random.uniform(0.1, 2), 2),  # 每股收益
                "bvps": round(random.uniform(1, 10), 2),  # 每股净资产
                "main_business": "计算机软件开发、技术服务、系统集成",
                "business_scope": "从事计算机软件、硬件的技术开发、技术转让、技术咨询、技术服务；计算机系统集成；数据处理；基础软件服务；应用软件服务",
                "website": f"http://www.{symbol}.com",
                "area": "北京市",
                "employees": random.randint(1000, 10000),
                "update_time": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            # 返回基础信息
            return {
                "symbol": symbol,
                "name": f"股票{symbol}",
                "error": str(e)
            }

    async def calculate_chip_distribution_by_date(
            self,
            symbol: str,
            target_date: str,
            price_bins: int = 100
    ) -> Dict:
        """
        计算指定日期的筹码分布（用于随鼠标移动的筹码峰）
        
        Args:
            symbol: 股票代码
            target_date: 目标日期 (YYYY-MM-DD)
            price_bins: 价格分档数量
            
        Returns:
            指定日期的筹码分布数据
        """
        try:
            # 尝试使用AkShare的筹码分布API (stock_cyq_em)
            try:
                import akshare as ak
                # AkShare的筹码分布数据
                cyq_df = await asyncio.get_event_loop().run_in_executor(
                    None,
                    ak.stock_cyq_em,
                    symbol
                )

                if cyq_df is not None and not cyq_df.empty:
                    # 筛选目标日期的数据
                    if 'date' in cyq_df.columns:
                        target_data = cyq_df[cyq_df['date'] == target_date]
                        if not target_data.empty:
                            # 转换为标准格式
                            price_levels = []
                            distribution = []
                            for _, row in target_data.iterrows():
                                if 'price' in row and 'ratio' in row:
                                    price_levels.append(float(row['price']))
                                    distribution.append(float(row['ratio']))

                            return {
                                "date": target_date,
                                "price_levels": price_levels,
                                "distribution": distribution,
                                "source": "akshare_cyq"
                            }
            except Exception as e:
                logger.debug(f"AkShare筹码分布获取失败，使用备用方法: {e}")

            # 备用方法：基于历史成交计算
            return await self._calculate_chip_distribution_fallback(
                symbol, target_date, price_bins
            )

        except Exception as e:
            logger.error(f"计算指定日期筹码分布失败: {e}")
            return {
                "error": str(e),
                "date": target_date,
                "price_levels": [],
                "distribution": []
            }

    async def _calculate_chip_distribution_fallback(
            self,
            symbol: str,
            target_date: str,
            price_bins: int = 100
    ) -> Dict:
        """备用筹码分布计算方法"""
        # 获取目标日期之前的历史数据
        series_data = await self.get_series(
            symbol=symbol,
            timeframe="1d",
            end_date=target_date,
            limit=120
        )

        if not series_data.get("bars"):
            return {
                "date": target_date,
                "price_levels": [],
                "distribution": [],
                "source": "fallback"
            }

        bars_df = pd.DataFrame(series_data["bars"])

        # 简单的筹码分布计算：基于成交量加权
        price_min = bars_df['low'].min()
        price_max = bars_df['high'].max()
        price_levels = np.linspace(price_min, price_max, price_bins)

        distribution = []
        for price in price_levels:
            # 计算该价位的筹码量（简化算法）
            volume_at_price = 0
            for _, bar in bars_df.iterrows():
                if bar['low'] <= price <= bar['high']:
                    # 该K线包含此价位，按比例分配成交量
                    price_range = bar['high'] - bar['low']
                    if price_range > 0:
                        volume_at_price += bar['volume'] / price_range
                    else:
                        volume_at_price += bar['volume']
            distribution.append(volume_at_price)

        # 归一化
        total = sum(distribution)
        if total > 0:
            distribution = [d / total * 100 for d in distribution]

        return {
            "date": target_date,
            "price_levels": price_levels.tolist(),
            "distribution": distribution,
            "source": "fallback"
        }

    async def calculate_chip_distribution(
            self,
            symbol: str,
            timeframe: str = "1d",
            lookback_days: int = 120,
            price_bins: int = 100
    ) -> Dict:
        """
        计算筹码分布
        
        Args:
            symbol: 股票代码
            timeframe: 时间周期（建议使用日线）
            lookback_days: 回看天数
            price_bins: 价格分档数量
            
        Returns:
            筹码分布数据
        """
        try:
            if not HAS_CHIP:
                return {
                    "error": "ChipDistribution module not available",
                    "price_levels": [],
                    "distribution": []
                }

            # 获取K线数据
            series_data = await self.get_series(
                symbol=symbol,
                timeframe=timeframe,
                limit=lookback_days + 50  # 多获取一些数据以确保足够
            )

            if not series_data.get("bars"):
                return {
                    "error": "No data available",
                    "price_levels": [],
                    "distribution": []
                }

            # 转换为DataFrame
            bars_df = pd.DataFrame(series_data["bars"])

            # 确保有必要的字段
            required_fields = ['open', 'high', 'low', 'close', 'volume']
            if not all(field in bars_df.columns for field in required_fields):
                return {
                    "error": "Missing required fields",
                    "price_levels": [],
                    "distribution": []
                }

            # 计算换手率（如果没有的话，使用成交量估算）
            if 'turnover_rate' not in bars_df.columns:
                # 简单估算：使用成交量的相对值
                avg_volume = bars_df['volume'].rolling(20, min_periods=1).mean()
                bars_df['turnover_rate'] = (bars_df['volume'] / avg_volume) * 2  # 粗略估算

            # 初始化筹码分布计算器
            chip_calculator = ChipDistribution(decay_days=120)

            # 计算筹码分布
            chip_data = chip_calculator.calculate_distribution(
                bars=bars_df,
                price_bins=price_bins,
                lookback_days=lookback_days
            )

            # 计算支撑阻力位
            if chip_data.get('price_levels') and chip_data.get('distribution'):
                support_resistance = chip_calculator.calculate_support_resistance(
                    price_levels=np.array(chip_data['price_levels']),
                    distribution=np.array(chip_data['distribution']),
                    current_price=chip_data.get('current_price', bars_df.iloc[-1]['close'])
                )
                chip_data['support_resistance'] = support_resistance

            # 清理NaN值
            chip_data = self._clean_nan_values(chip_data)

            return chip_data

        except Exception as e:
            logger.error(f"计算筹码分布失败: {e}")
            return {
                "error": str(e),
                "price_levels": [],
                "distribution": []
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

    async def get_stock_meta(self, symbol: str) -> Dict:
        """
        获取股票元数据
        
        Returns:
            包含上市日期、数据范围等信息
        """
        if self.kline_cache:
            meta = await self.kline_cache.get_stock_meta(symbol)

            # 如果没有缓存，尝试获取基本信息
            if not meta.get("has_cache"):
                try:
                    # 获取最新的一条数据来确定最新日期
                    recent_data = await self.get_series(symbol, "1d", limit=1)
                    if recent_data and recent_data.get("bars"):
                        bars = recent_data["bars"]
                        if bars:
                            latest_bar = bars[-1] if isinstance(bars, list) else bars.iloc[-1]
                            meta["latest_date"] = latest_bar.get("date", latest_bar.get("time"))

                    # 从StockInfoService获取上市日期
                    if self.stock_info_service:
                        try:
                            # 先尝试从缓存获取
                            stock_info = self.stock_info_service.get(symbol)
                            if stock_info and stock_info.get('listed_date'):
                                meta["listing_date"] = stock_info['listed_date']
                            else:
                                # 如果缓存中没有，尝试从API更新
                                logger.debug(f"尝试从API获取股票 {symbol} 的上市日期")
                                updated_info = await self.stock_info_service.update_from_api(symbol)
                                if updated_info and updated_info.get('listed_date'):
                                    meta["listing_date"] = updated_info['listed_date']
                                else:
                                    meta["listing_date"] = "2010-01-01"  # 获取失败时的默认值
                        except Exception as e:
                            logger.warning(f"从StockInfoService获取上市日期失败: {e}")
                            meta["listing_date"] = "2010-01-01"  # 异常时的默认值
                    else:
                        meta["listing_date"] = "2010-01-01"  # 服务不可用时的默认值

                except Exception as e:
                    logger.warning(f"获取股票元数据失败: {e}")

            return meta

        # 返回默认元数据
        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "listing_date": "2010-01-01",
            "total_bars": 0,
            "has_cache": False
        }
    
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

        result = {
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

        # 添加分层缓存统计
        if self.kline_cache:
            result["kline_cache_stats"] = self.kline_cache.get_cache_stats()

        return result
