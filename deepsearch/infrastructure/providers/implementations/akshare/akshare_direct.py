"""
AKShare直连数据提供者
直接使用AKShare获取实时股票数据，作为备用数据源
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, cast

from loguru import logger

from deepsearch.core.utils.async_timeout import timeout_decorator

# 导入监控装饰器
from deepsearch.infrastructure.providers.unified_proxy import async_monitor_access
from deepsearch.ports.data_sources import DataAccessType, DataSourceType

from ._deps import AkshareModule, PandasModule, load_akshare, load_pandas

ak: Optional[AkshareModule] = load_akshare()
HAS_AKSHARE = ak is not None
if not HAS_AKSHARE:
    logger.warning("AKShare未安装，直连数据提供者不可用")

pd: Optional[PandasModule] = load_pandas()
HAS_PANDAS = pd is not None


CacheEntry = Tuple[float, Dict[str, Any]]


class AKShareDirectProvider:
    """AKShare直连数据提供者"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        akshare_module: Optional[AkshareModule] = None,
        pandas_module: Optional[PandasModule] = None,
    ):
        self.config = config if isinstance(config, dict) else {}
        self.timeout = timeout
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_ttl: Dict[str, int] = {
            "realtime": 10,  # 实时数据缓存10秒
            "hist": 300,  # 历史数据缓存5分钟
            "info": 3600,  # 股票信息缓存1小时
        }
        self._executor = ThreadPoolExecutor(max_workers=3)
        self.initialized = False
        self.access_mode = "auto"
        self.proxy_info = {"enabled": False, "worker_url": None, "mode": "direct"}
        self._akshare: Optional[AkshareModule] = akshare_module if akshare_module is not None else ak
        self._pandas: Optional[PandasModule] = pandas_module if pandas_module is not None else pd

    def _ensure_akshare(self) -> AkshareModule:
        """获取注入的 AkShare 模块"""

        if self._akshare is None:
            raise RuntimeError("AkShare 未安装或未注入，无法执行该操作")
        return self._akshare

    def _get_pandas(self) -> Optional[PandasModule]:
        """返回注入的 pandas 模块（允许为空）"""

        return self._pandas

    async def initialize(self):
        """初始化"""
        if self._akshare is None:
            logger.error("AKShare未安装或未注入，无法初始化直连数据提供者")
            return False

        proxy_config = {}
        if isinstance(self.config, dict):
            proxy_config = self.config.get("proxy", {}) or {}
        mode = "auto"
        if isinstance(self.config, dict) and "mode" in self.config:
            mode = str(self.config.get("mode", "auto")).lower()
        proxy_flag = proxy_config.get("enabled") if isinstance(proxy_config, dict) else None

        if mode == "worker":
            should_use_proxy = True
        elif mode == "direct":
            should_use_proxy = False
        else:
            should_use_proxy = bool(proxy_flag) if proxy_flag is not None else True

        worker_url = proxy_config.get("worker_url") if isinstance(proxy_config, dict) else None
        timeout_override = None
        if isinstance(proxy_config, dict):
            timeout_override = proxy_config.get("timeout")
        if timeout_override is None and isinstance(self.config, dict):
            timeout_override = self.config.get("timeout")
        if timeout_override is None:
            timeout_override = self.timeout

        self.access_mode = "worker" if should_use_proxy else "direct"
        self.proxy_info = {
            "enabled": False,
            "worker_url": None,
            "mode": self.access_mode,
            "timeout": timeout_override,
        }

        if should_use_proxy:
            try:
                from deepsearch.utils.network.proxy_client import get_proxy_client

                client = get_proxy_client(worker_url=worker_url, force_refresh=bool(worker_url))
                if timeout_override:
                    try:
                        client.default_timeout = timeout_override
                    except Exception as timeout_error:
                        logger.debug(f"设置代理默认超时失败: {timeout_error}")

                if client.use_proxy:
                    from deepsearch.utils.network.akshare_proxy import patch_akshare

                    patch_akshare()
                    self.access_mode = "worker"
                    self.proxy_info.update(
                        {
                            "enabled": True,
                            "worker_url": client.worker_url,
                            "mode": "worker",
                            "timeout": timeout_override or client.default_timeout,
                        }
                    )
                    logger.info("已应用 AkShare CloudFlare 代理补丁 (worker 模式)")
                else:
                    logger.warning("AkShare 代理启用但未配置有效的 Worker URL，将回退直连模式")
                    self.access_mode = "direct"
                    self.proxy_info.update({"enabled": False, "mode": "direct"})
            except Exception as e:
                logger.warning(f"应用 AkShare 代理补丁失败: {e}")
                self.access_mode = "direct"
                self.proxy_info.update({"enabled": False, "mode": "direct"})
        else:
            logger.info("AkShare 使用直连模式")

        logger.info("初始化AKShare直连数据提供者")
        self.initialized = True
        self.proxy_info["mode"] = self.access_mode
        return True

    def get_status_metadata(self) -> Dict[str, Any]:
        """返回当前代理模式与配置信息"""
        return {"access_mode": self.access_mode, "proxy": self.proxy_info}

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """
        安全地将值转换为浮点数

        Args:
            value: 要转换的值
            default: 转换失败时的默认值

        Returns:
            转换后的浮点数
        """
        if value is None:
            return default

        # 处理字符串
        if isinstance(value, str):
            # 处理空字符串或特殊字符
            if value in ["", "-", "--", "N/A", "null", "None"]:
                return default

            # 移除可能的千分位分隔符和百分号
            value = value.replace(",", "").replace("%", "")

            try:
                return float(value)
            except (ValueError, TypeError) as e:
                logger.debug(f"无法转换为浮点数: {value}, 错误: {e}")
                return default

        # 处理数字类型
        try:
            return float(value)
        except (ValueError, TypeError) as e:
            logger.debug(f"无法转换为浮点数: {value}, 错误: {e}")
            return default

    def _infer_exchange(self, symbol: str) -> str:
        """根据股票代码推断所属交易所"""
        if not symbol:
            return ""
        if symbol.startswith("6"):
            return "SSE"
        if symbol.startswith("0") or symbol.startswith("3"):
            return "SZSE"
        return ""

    def _fetch_stock_info_sync(self, symbol: str) -> Dict[str, Any]:
        """??????????"""
        module = self._akshare
        if module is None:
            logger.error("AkShare 未安装或未注入，无法获取股票基础信息")
            return {
                "symbol": symbol,
                "name": f"未知{symbol}",
                "exchange": self._infer_exchange(symbol),
                "industry": "",
                "market": "",
                "listed_date": "",
                "source": "akshare_direct",
                "error": "AkShare 未安装",
            }
        try:
            df = module.stock_individual_info_em(symbol=symbol)
            if df is None or df.empty:
                return {
                    "symbol": symbol,
                    "name": f"??{symbol}",
                    "exchange": self._infer_exchange(symbol),
                    "industry": "",
                    "market": "",
                    "listed_date": "",
                    "source": "akshare_direct",
                    "error": "????????",
                }

            info_dict = {}
            for _, row in df.iterrows():
                key = row.get("item")
                value = row.get("value")
                if key:
                    info_dict[str(key)] = value

            exchange = self._infer_exchange(symbol)
            market_flag = (
                "SH" if symbol.startswith("6") else "SZ" if symbol.startswith(("0", "3")) else ""
            )
            listed_date = info_dict.get("????") or info_dict.get("????") or ""
            industry = info_dict.get("????") or info_dict.get("??") or ""
            result = {
                "symbol": symbol,
                "code": symbol,
                "name": info_dict.get("????") or info_dict.get("????") or f"??{symbol}",
                "exchange": exchange,
                "industry": industry,
                "market": market_flag,
                "listed_date": str(listed_date),
                "total_shares": float(info_dict.get("???") or 0),
                "float_shares": float(info_dict.get("???") or 0),
                "market_cap": float(info_dict.get("???") or 0),
                "float_market_cap": float(info_dict.get("????") or 0),
                "source": "akshare_direct",
            }
            return result
        except Exception as exc:
            logger.error(f"AKShare ????????: {exc}")
            return {
                "symbol": symbol,
                "code": symbol,
                "name": f"??{symbol}",
                "exchange": self._infer_exchange(symbol),
                "industry": "",
                "market": "",
                "listed_date": "",
                "source": "akshare_direct",
                "error": str(exc),
            }

    def _default_rank_symbols(self) -> List[str]:
        """???????????"""
        symbols: List[str] = []
        if isinstance(self.config, dict):
            custom_symbols = self.config.get("rank_symbols")
            if isinstance(custom_symbols, list) and custom_symbols:
                symbols = [str(item) for item in custom_symbols if str(item)]
        if not symbols:
            symbols = [
                "000001",
                "000002",
                "000333",
                "000651",
                "002594",
                "300750",
                "600036",
                "600519",
                "601318",
                "601398",
                "601988",
                "603288",
            ]
        return symbols

    def _fetch_daily_summary(self, symbol: str) -> Optional[Dict[str, Any]]:
        """????????????"""
        module = self._akshare
        if module is None:
            logger.error("AkShare 未安装或未注入，无法获取日线摘要")
            return None
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")
            df = module.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            )
            if df is None or df.empty:
                return None
            latest = df.iloc[-1]
            columns = df.columns
            close = float(latest.get(columns[3], 0) or 0)
            change_pct = float(latest.get(columns[9], 0) or 0)
            change = float(latest.get(columns[10], 0) or 0)
            name = str(latest.get(columns[1], symbol))
            volume = float(latest.get(columns[6], 0) or 0)
            amount = float(latest.get(columns[7], 0) or 0)
            return {
                "symbol": symbol,
                "name": name,
                "close": close,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
                "amount": amount,
                "source": "akshare_direct",
            }
        except Exception as exc:
            logger.debug(f"?? {symbol} ??????: {exc}")
            return None

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_INFO,
        module="akshare_direct",
    )
    async def get_top_gainers(self, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """???????"""
        if self._akshare is None or not self.initialized:
            return []
        symbols = kwargs.get("symbols")
        if not symbols:
            symbols = self._default_rank_symbols()
        loop = asyncio.get_event_loop()
        summaries: List[Dict[str, Any]] = []
        for symbol in symbols:
            summary = await loop.run_in_executor(self._executor, self._fetch_daily_summary, symbol)
            if summary:
                summaries.append(summary)
        summaries.sort(key=lambda item: item.get("change_pct", 0.0), reverse=True)
        if limit and limit > 0:
            summaries = summaries[:limit]
        return summaries

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_INFO,
        module="akshare_direct",
    )
    async def get_top_losers(self, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """???????"""
        if self._akshare is None or not self.initialized:
            return []
        symbols = kwargs.get("symbols")
        if not symbols:
            symbols = self._default_rank_symbols()
        loop = asyncio.get_event_loop()
        summaries: List[Dict[str, Any]] = []
        for symbol in symbols:
            summary = await loop.run_in_executor(self._executor, self._fetch_daily_summary, symbol)
            if summary:
                summaries.append(summary)
        summaries.sort(key=lambda item: item.get("change_pct", 0.0))
        if limit and limit > 0:
            summaries = summaries[:limit]
        return summaries

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_INFO,
        module="akshare_direct",
    )
    @timeout_decorator(seconds=10.0, default={"error": "timeout"})
    async def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基础信息"""
        if self._akshare is None or not self.initialized:
            return {
                "symbol": symbol,
                "code": symbol,
                "name": f"股票{symbol}",
                "exchange": self._infer_exchange(symbol),
                "industry": "",
                "market": "",
                "listed_date": "",
                "source": "akshare_direct",
                "error": "AKShare未安装或未初始化",
            }

        cache_key = f"stock_info_{symbol}"
        cached_entry = self._cache.get(cache_key)
        if cached_entry:
            cached_time, cached_data = cached_entry
            if time.time() - cached_time < self._cache_ttl.get("info", 3600):
                return cast(Dict[str, Any], cached_data)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self._executor, self._fetch_stock_info_sync, symbol)

        if isinstance(result, dict) and not result.get("error"):
            self._cache[cache_key] = (time.time(), result)
        return result

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.REALTIME_QUOTE,
        module="akshare_direct",
    )
    @timeout_decorator(
        seconds=30.0, default={"error": "timeout"}  # 使用固定超时值或从TimeoutManager获取
    )
    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情

        Args:
            symbol: 股票代码

        Returns:
            实时行情数据
        """
        if self._akshare is None or not self.initialized:
            return {"error": "AKShare未安装或未初始化"}

        try:
            # 检查缓存
            cache_key = f"quote_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl["realtime"]:
                    return cast(Dict[str, Any], cached_data)

            # 在线程池中执行阻塞的AKShare调用
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, self._fetch_realtime_quote_sync, symbol
            )

            # 缓存结果
            if result is not None and not result.get("error"):
                self._cache[cache_key] = (time.time(), result)

            return result

        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return {"error": str(e)}

    def _fetch_realtime_quote_sync(self, symbol: str) -> Dict[str, Any]:
        """同步获取实时行情（在线程池中执行）"""
        module = self._akshare
        if module is None:
            return {"error": "AkShare 未安装或未注入"}
        try:
            logger.info(f"[AKShare] 开始获取 {symbol} 实时行情")

            # 方法1: 尝试使用个股信息接口（更快）
            try:
                # 获取个股信息
                df_info = module.stock_individual_info_em(symbol=symbol)
                if not df_info.empty:
                    info_dict = {}
                    for _, row in df_info.iterrows():
                        info_dict[row["item"]] = row["value"]

                    logger.info(f"[AKShare] 通过个股信息接口获取 {symbol} 成功")
                    return {
                        "symbol": symbol,
                        "name": info_dict.get("股票简称", ""),
                        "current": self._safe_float(info_dict.get("最新", 0)),
                        "prev_close": self._safe_float(info_dict.get("昨收", 0)),
                        "open": self._safe_float(info_dict.get("今开", 0)),
                        "high": self._safe_float(info_dict.get("最高", 0)),
                        "low": self._safe_float(info_dict.get("最低", 0)),
                        "volume": self._safe_float(info_dict.get("成交量", 0)),
                        "amount": self._safe_float(info_dict.get("成交额", 0)),
                        "change": self._safe_float(info_dict.get("涨跌", 0)),
                        "change_pct": self._safe_float(info_dict.get("涨跌幅", 0)),
                        "timestamp": datetime.now().isoformat(),
                        "source": "akshare_direct_individual",
                    }
            except Exception as e:
                logger.debug(f"个股信息接口失败: {e}")

            # 方法2: 降级到全市场查询（慢，约20秒）
            logger.warning("[AKShare] 降级到全市场查询（慢）")
            df = module.stock_zh_a_spot_em()

            # 查找指定股票
            stock_data = df[df["代码"] == symbol]

            if stock_data.empty:
                return {"error": f"未找到股票 {symbol}"}

            row = stock_data.iloc[0]

            return {
                "symbol": symbol,
                "name": row.get("名称", ""),
                "current": self._safe_float(row.get("最新价", 0)),
                "prev_close": self._safe_float(row.get("昨收", 0)),
                "open": self._safe_float(row.get("今开", 0)),
                "high": self._safe_float(row.get("最高", 0)),
                "low": self._safe_float(row.get("最低", 0)),
                "volume": self._safe_float(row.get("成交量", 0)),
                "amount": self._safe_float(row.get("成交额", 0)),
                "change": self._safe_float(row.get("涨跌额", 0)),
                "change_pct": self._safe_float(row.get("涨跌幅", 0)),
                "timestamp": datetime.now().isoformat(),
                "amplitude": self._safe_float(row.get("振幅", 0)),
                "turnover_rate": self._safe_float(row.get("换手率", 0)),
                "pe_ratio": self._safe_float(row.get("市盈率-动态", 0)),
                "pb_ratio": self._safe_float(row.get("市净率", 0)),
                "market_cap": self._safe_float(row.get("总市值", 0)),
                "float_market_cap": self._safe_float(row.get("流通市值", 0)),
                "source": "akshare_direct",
            }

        except Exception as e:
            logger.error(f"AKShare获取实时行情失败: {e}")
            return {"error": str(e)}

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.REALTIME_QUOTE,
        module="akshare_direct",
    )
    @timeout_decorator(
        seconds=45.0, default=[]  # 批量获取使用更长超时
    )
    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """
        批量获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            实时行情数据列表
        """
        if self._akshare is None or not self.initialized:
            return []

        try:
            # 在线程池中执行阻塞的AKShare调用
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, self._fetch_realtime_quotes_sync, symbols
            )
            return result
        except Exception as e:
            logger.error(f"批量获取实时行情失败: {e}")
            return []

    def _fetch_realtime_quotes_sync(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """同步批量获取实时行情"""
        module = self._akshare
        if module is None:
            return []
        
        try:
            logger.info(f"[AKShare] 开始批量获取 {len(symbols)} 只股票的实时行情")
            
            # 直接使用全市场查询
            df = module.stock_zh_a_spot_em()
            
            if df is None or df.empty:
                return []

            result = []
            # 创建代码索引以加速查找
            df_indexed = df.set_index("代码")
            
            for symbol in symbols:
                if symbol in df_indexed.index:
                    row = df_indexed.loc[symbol]
                    # 如果有重复代码，loc可能返回DataFrame，取第一行
                    if isinstance(row, pd.DataFrame):
                        row = row.iloc[0]
                        
                    result.append({
                        "symbol": symbol,
                        "name": row.get("名称", ""),
                        "current": self._safe_float(row.get("最新价", 0)),
                        "prev_close": self._safe_float(row.get("昨收", 0)),
                        "open": self._safe_float(row.get("今开", 0)),
                        "high": self._safe_float(row.get("最高", 0)),
                        "low": self._safe_float(row.get("最低", 0)),
                        "volume": self._safe_float(row.get("成交量", 0)),
                        "amount": self._safe_float(row.get("成交额", 0)),
                        "change": self._safe_float(row.get("涨跌额", 0)),
                        "change_pct": self._safe_float(row.get("涨跌幅", 0)),
                        "timestamp": datetime.now().isoformat(),
                        "amplitude": self._safe_float(row.get("振幅", 0)),
                        "turnover_rate": self._safe_float(row.get("换手率", 0)),
                        "pe_ratio": self._safe_float(row.get("市盈率-动态", 0)),
                        "pb_ratio": self._safe_float(row.get("市净率", 0)),
                        "market_cap": self._safe_float(row.get("总市值", 0)),
                        "float_market_cap": self._safe_float(row.get("流通市值", 0)),
                        "source": "akshare_direct_batch",
                    })
                else:
                    # 未找到的股票返回错误信息或空数据
                    result.append({
                        "symbol": symbol,
                        "error": "Not found",
                        "source": "akshare_direct_batch"
                    })
            
            return result

        except Exception as e:
            logger.error(f"AKShare批量获取实时行情失败: {e}")
            return []

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        module="akshare_direct",
    )
    @timeout_decorator(
        seconds=30.0, default={"data": [], "error": "timeout"}  # 历史数据使用更长的超时
    )
    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
    ) -> Dict[str, Any]:
        """
        获取股票历史数据

        Args:
            symbol: 股票代码
            period: 周期类型
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型

        Returns:
            历史K线数据
        """
        if self._akshare is None or not self.initialized:
            return {"data": [], "error": "AKShare未安装或未初始化"}

        try:
            # 检查缓存
            cache_key = f"hist_{symbol}_{period}_{start_date}_{end_date}_{adjust}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl["hist"]:
                    return cast(Dict[str, Any], cached_data)

            # 在线程池中执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, self._fetch_hist_sync, symbol, period, start_date, end_date, adjust
            )

            # 缓存结果
            if result is not None and not result.get("error"):
                self._cache[cache_key] = (time.time(), result)

            return result

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return {"data": [], "error": str(e)}

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取K线数据 - DataSourceManager接口方法

        Args:
            symbol: 股票代码
            period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量
            **kwargs: 其他参数

        Returns:
            K线数据列表
        """
        try:
            # 转换周期格式
            period_map = {
                "1d": "daily",
                "d": "daily",
                "daily": "daily",
                "1w": "weekly",
                "w": "weekly",
                "weekly": "weekly",
                "1M": "monthly",
                "M": "monthly",
                "monthly": "monthly",
            }

            period_str = period_map.get(period, "daily")
            adjust = kwargs.get("adjust", "")

            # 调用已有的get_stock_hist方法
            hist_data = await self.get_stock_hist(
                symbol=symbol,
                period=period_str,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )

            # 检查返回数据
            if not hist_data or "error" in hist_data:
                logger.error(f"获取K线数据失败: {hist_data.get('error', 'Unknown error')}")
                return None

            # 如果hist_data是DataFrame，转换为列表
            if hasattr(hist_data, "to_dict"):
                # 是DataFrame
                result = []
                for idx, row in hist_data.iterrows():
                    result.append(
                        {
                            "date": str(idx),
                            "open": float(row.get("开盘", 0)),
                            "high": float(row.get("最高", 0)),
                            "low": float(row.get("最低", 0)),
                            "close": float(row.get("收盘", 0)),
                            "volume": float(row.get("成交量", 0)),
                            "amount": float(row.get("成交额", 0)),
                            "source": "akshare",
                        }
                    )

                # 应用限制
                if limit and limit > 0:
                    result = result[-limit:]

                logger.info(f"AKShare返回{len(result)}条K线数据")
                return result

            # 如果是字典格式
            elif isinstance(hist_data, dict):
                data_list = cast(List[Dict[str, Any]], hist_data.get("data", []))
                if limit and limit > 0:
                    data_list = data_list[-limit:]
                return data_list

            return None

        except Exception as e:
            logger.error(f"AKShare get_kline_data失败: {e}")
            return None

    def _fetch_hist_sync(
        self,
        symbol: str,
        period: str,
        start_date: Optional[str],
        end_date: Optional[str],
        adjust: str,
    ) -> Dict[str, Any]:
        """同步获取历史数据"""
        module = self._akshare
        if module is None:
            return {
                "data": [],
                "error": "AkShare 未安装或未注入",
                "source": "akshare_direct",
            }
        try:
            # 转换复权类型
            adjust_map = {
                "": "",  # 不复权
                "none": "",  # 不复权
                "qfq": "qfq",  # 前复权
                "hfq": "hfq",  # 后复权
            }
            adjust_type = adjust_map.get(adjust, "")

            # 获取历史数据
            df = module.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date.replace("-", "") if start_date else "19900101",
                end_date=end_date.replace("-", "") if end_date else "20500101",
                adjust=adjust_type,
            )

            if df.empty:
                return {"data": [], "source": "akshare_direct"}

            # 转换为标准格式
            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "date": str(row.get("日期", "")),
                        "open": float(row.get("开盘", 0)),
                        "close": float(row.get("收盘", 0)),
                        "high": float(row.get("最高", 0)),
                        "low": float(row.get("最低", 0)),
                        "volume": float(row.get("成交量", 0)),
                        "amount": float(row.get("成交额", 0)),
                        "amplitude": float(row.get("振幅", 0)),
                        "pct_change": float(row.get("涨跌幅", 0)),
                        "change": float(row.get("涨跌额", 0)),
                        "turnover_rate": float(row.get("换手率", 0)),
                    }
                )

            logger.info(f"成功获取 {symbol} 的 {len(result)} 条历史数据")
            return {"data": result, "source": "akshare_direct"}

        except Exception as e:
            logger.error(f"AKShare获取历史数据失败: {e}")
            return {"data": [], "error": str(e)}

    async def fetch_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票基础信息

        Args:
            symbol: 股票代码

        Returns:
            股票基础信息
        """
        if self._akshare is None or not self.initialized:
            return {"symbol": symbol, "name": f"股票{symbol}", "error": "AKShare未安装或未初始化"}

        try:
            # 检查缓存
            cache_key = f"info_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl["info"]:
                    return cast(Dict[str, Any], cached_data)

            # 在线程池中执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._fetch_stock_info_sync, symbol)

            # 缓存结果
            if result is not None and not result.get("error"):
                self._cache[cache_key] = (time.time(), result)

            return result

        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            return {"symbol": symbol, "name": f"股票{symbol}", "error": str(e)}

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct",
    )
    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表"""
        if self._akshare is None or not self.initialized:
            return []

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._fetch_stock_list_sync)
            return result

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    async def get_stock_list(self, limit: Optional[int] = None, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票列表 - DataSourceManager接口方法

        Args:
            limit: 限制返回数量
            **kwargs: 其他参数

        Returns:
            股票列表
        """
        try:
            # 调用已有的fetch_stock_list方法
            stocks = await self.fetch_stock_list()

            if not stocks:
                return None

            # 转换格式以匹配DataSourceManager的期望格式
            result = []
            for stock in stocks:
                result.append(
                    {
                        "symbol": stock.get("代码", ""),
                        "name": stock.get("名称", ""),
                        "code": stock.get("代码", ""),
                        "source": "akshare",
                    }
                )

            # 应用限制
            if limit and limit > 0:
                result = result[:limit]

            logger.info(f"AKShare返回{len(result)}只股票")
            return result

        except Exception as e:
            logger.error(f"AKShare get_stock_list失败: {e}")
            return None

    def _fetch_stock_list_sync(self) -> List[Dict[str, str]]:
        """同步获取股票列表"""
        module = self._akshare
        if module is None:
            logger.error("AkShare 未安装或未注入，无法获取股票列表")
            return []
        try:
            # 尝试多种方式获取股票列表，提高容错性
            df = None

            # 方法1: 使用stock_zh_a_spot_em (东方财富实时行情)
            try:
                logger.debug("尝试使用东方财富接口获取股票列表...")
                df = module.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    stocks = []
                    for _, row in df.iterrows():
                        stocks.append(
                            {"代码": str(row.get("代码", "")), "名称": str(row.get("名称", ""))}
                        )
                    logger.info(f"通过东方财富接口获取到 {len(stocks)} 只股票")
                    return stocks
            except Exception as e1:
                logger.debug(f"东方财富接口失败: {e1}")

            # 方法2: 使用原来的stock_info_a_code_name
            try:
                logger.debug("尝试使用stock_info_a_code_name获取股票列表...")
                df = module.stock_info_a_code_name()
                if df is not None and not df.empty:
                    stocks = []
                    for _, row in df.iterrows():
                        stocks.append(
                            {"代码": str(row.get("code", "")), "名称": str(row.get("name", ""))}
                        )
                    logger.info(f"通过stock_info_a_code_name获取到 {len(stocks)} 只股票")
                    return stocks
            except Exception as e2:
                logger.debug(f"stock_info_a_code_name失败: {e2}")

            # 如果都失败了，返回一个基础的股票列表作为降级方案
            logger.warning("所有股票列表API都失败，使用默认股票列表")
            return [
                {"代码": "000001", "名称": "平安银行"},
                {"代码": "000002", "名称": "万科A"},
                {"代码": "600000", "名称": "浦发银行"},
                {"代码": "600036", "名称": "招商银行"},
            ]

        except Exception as e:
            logger.error(f"AKShare获取股票列表失败: {e}")
            # 返回基础股票列表
            return [
                {"代码": "000001", "名称": "平安银行"},
                {"代码": "000002", "名称": "万科A"},
            ]

    async def call_api(
        self, api_name: str, params: Dict[str, Any], max_retries: int = 3
    ) -> Dict[str, Any]:
        """通用 AkShare API 调用（直接模式）"""
        if not self.initialized:
            await self.initialize()

        safe_params = dict(params or {})
        return await self._fetch_with_fallback(api_name, safe_params, max_retries=max_retries)

    async def _fetch_with_fallback(
        self, api_name: str, params: Dict[str, Any], max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        带故障转移的数据获取（直连模式）

        Args:
            api_name: AkShare API函数名
            params: API参数
            max_retries: 最大重试次数

        Returns:
            API响应数据
        """
        if self._akshare is None or not self.initialized:
            return {"error": "AKShare未安装或未初始化"}

        # 检查缓存
        cache_key = f"api_{api_name}_{str(params)}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            cache_ttl = self._cache_ttl.get("api", 60)  # 默认60秒缓存
            if time.time() - cached_time < cache_ttl:
                logger.debug(f"从缓存返回 {api_name} 数据")
                return cast(Dict[str, Any], cached_data)

        retries = 0
        last_error = None

        while retries < max_retries:
            try:
                # 在线程池中执行AkShare API调用
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self._executor, self._call_akshare_api, api_name, params
                )

                # 缓存成功的结果
                if result is not None and not result.get("error"):
                    self._cache[cache_key] = (time.time(), result)

                return result

            except Exception as e:
                retries += 1
                last_error = e
                logger.warning(f"调用 {api_name} 失败 (尝试 {retries}/{max_retries}): {e}")

                if retries < max_retries:
                    # 指数退避
                    await asyncio.sleep(2**retries)

        # 所有重试都失败
        error_msg = f"调用 {api_name} 失败，已重试 {max_retries} 次: {last_error}"
        logger.error(error_msg)
        return {"error": error_msg}

    def _call_akshare_api(self, api_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步调用AkShare API（在线程池中执行）

        Args:
            api_name: AkShare API函数名
            params: API参数

        Returns:
            格式化的响应数据
        """
        module = self._akshare
        if module is None:
            return {"error": "AkShare 未安装或未注入"}
        pandas_module = self._get_pandas()
        try:
            logger.info(f"[AKShare Direct] 调用 {api_name} with params: {params}")

            # 获取AkShare函数
            if not hasattr(module, api_name):
                # 尝试处理一些已知的API变更
                alternate_names = {
                    "stock_zh_a_hist_adj_factor": "stock_zh_a_adjust",  # 复权因子新API
                    "stock_zh_a_daily": "stock_zh_a_hist",  # 日线数据新API
                }

                if api_name in alternate_names:
                    new_api_name = alternate_names[api_name]
                    logger.info(f"API {api_name} 不存在，尝试使用替代API: {new_api_name}")
                    api_name = new_api_name

                if not hasattr(module, api_name):
                    return {"error": f"AkShare不存在函数: {api_name}"}

            func = getattr(module, api_name)

            # 调用API
            result = func(**params) if params else func()

            # 处理返回结果
            if pandas_module and isinstance(result, pandas_module.DataFrame):
                # 转换DataFrame为字典
                return {
                    "success": True,
                    "data": result.to_dict("records"),
                    "columns": result.columns.tolist(),
                    "count": len(result),
                }
            elif pandas_module and isinstance(result, pandas_module.Series):
                # 转换Series为字典
                return {"success": True, "data": result.to_dict(), "count": len(result)}
            else:
                # 其他类型直接返回
                return {"success": True, "data": result}

        except Exception as e:
            logger.error(f"调用AkShare API {api_name} 失败: {e}")
            return {"error": str(e)}

    def is_connected(self) -> bool:
        """检查是否连接"""
        return self._akshare is not None and self.initialized

    async def close(self):
        """关闭连接"""
        if self._executor:
            self._executor.shutdown(wait=False)
        self._cache.clear()
        self.initialized = False
        logger.info("AKShare直连数据提供者已关闭")
