"""
AKShare 数据提供者

统一的 AkShare Provider，支持两种访问模式：
- worker 模式：通过 Cloudflare Worker 代理访问（使用 proxy_client.py）
- direct 模式：直接调用 akshare 库

配置示例：
    config:
        mode: worker  # 或 direct
        proxy:
            enabled: true
            worker_url: https://your-worker.workers.dev
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, cast

from core.core.utils.async_timeout import timeout_decorator
from core.infrastructure.providers.exceptions import ProviderDataError
from core.infrastructure.providers.interfaces.capabilities import DataCapability
from core.infrastructure.providers.protocols.lifecycle import (
    HealthCheckResult,
    HealthStatus,
    ILifecycleProvider,
)

# 导入监控装饰器
from core.infrastructure.providers.unified_proxy import async_monitor_access
from core.ports.data_sources import DataAccessType, DataSourceType
from loguru import logger

from ._deps import AkshareModule, PandasModule, load_akshare, load_pandas

ak: Optional[AkshareModule] = load_akshare()
HAS_AKSHARE = ak is not None
if not HAS_AKSHARE:
    logger.warning("AKShare未安装，直连数据提供者不可用")

pd: Optional[PandasModule] = load_pandas()
HAS_PANDAS = pd is not None


CacheEntry = Tuple[float, Dict[str, Any]]


class AkShareProvider(ILifecycleProvider):
    """AKShare 数据提供者（统一实现，支持 worker/direct 模式）

    实现 ILifecycleProvider 协议，支持统一的生命周期管理。
    """

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
        self._executor = ThreadPoolExecutor(max_workers=10)
        self.initialized = False
        self._started = False  # 跟踪 Provider 启动状态
        self.access_mode = "auto"
        self.proxy_info = {"enabled": False, "worker_url": None, "mode": "direct"}
        self._akshare: Optional[AkshareModule] = (
            akshare_module if akshare_module is not None else ak
        )
        self._pandas: Optional[PandasModule] = pandas_module if pandas_module is not None else pd

    def get_capabilities(self) -> set[DataCapability]:
        """返回 AKShare Direct 支持的数据能力集合。

        AKShare 提供丰富的免费股票数据接口：
        - 基础数据：股票列表、实时行情、K线数据、股票信息
        - 市场数据：资金流向、板块数据、行业数据
        - 特色数据：融资融券、大宗交易、北向资金、龙虎榜
        - 财务数据：财务报表
        - 基础信息：交易日历
        """
        return {
            # 基础数据能力
            DataCapability.STOCK_LIST,
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.STOCK_INFO,
            # 市场数据能力
            DataCapability.CAPITAL_FLOW,
            DataCapability.SECTOR_DATA,
            DataCapability.INDUSTRY_DATA,
            # 特色数据能力
            DataCapability.MARGIN_TRADING,
            DataCapability.BLOCK_TRADE,
            DataCapability.NORTH_FLOW,
            DataCapability.DRAGON_TIGER,
            # 财务数据能力
            DataCapability.FINANCIAL_DATA,
            # 基础信息能力
            DataCapability.TRADING_CALENDAR,
        }

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
            # auto 模式：仅当显式配置 proxy.enabled=true 时才使用代理
            # 默认直连，避免 Cloudflare Worker 被速率限制（520 错误）
            should_use_proxy = bool(proxy_flag) if proxy_flag is not None else False

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
                from core.utils.network.proxy_client import get_proxy_client

                client = get_proxy_client(worker_url=worker_url, force_refresh=bool(worker_url))
                if timeout_override:
                    try:
                        client.default_timeout = timeout_override
                    except Exception as timeout_error:
                        logger.debug(f"设置代理默认超时失败: {timeout_error}")

                if client.use_proxy:
                    from core.utils.network.akshare_proxy import patch_akshare

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

    async def start(self) -> None:
        """启动 AkShare Provider

        注意: AkShare 是无状态的 HTTP 调用库,不需要特殊启动逻辑。
        此方法主要用于:
        1. 满足 ILifecycleProvider 协议
        2. 为未来扩展预留接口(如连接池、限流器)
        3. 统一所有 Provider 的生命周期管理
        """
        if self._started:
            logger.warning("AkShareProvider 已经启动")
            return

        self._started = True
        logger.info("AkShareProvider 已启动(无状态模式)")

    async def stop(self) -> None:
        """停止 AkShare Provider

        清理资源(如果有)。当前 AkShare 无需特殊清理,
        但为未来扩展预留接口(如关闭 HTTP 会话)。

        Note:
            此方法是幂等的,可以多次调用
        """
        if not self._started:
            return

        # 未来可以在这里添加清理逻辑,例如:
        # - 关闭 HTTP 会话池
        # - 停止限流器
        # - 保存统计数据
        # - 关闭线程池
        if hasattr(self, "_executor") and self._executor:
            try:
                self._executor.shutdown(wait=False)
                logger.debug("AkShareProvider 线程池已关闭")
            except Exception as e:
                logger.warning(f"关闭线程池时出错: {e}")

        self._started = False
        logger.info("AkShareProvider 已停止")

    async def health_check(self) -> HealthCheckResult:
        """健康检查

        测试 AkShare 服务是否可用。使用轻量级接口测试连通性。

        Returns:
            HealthCheckResult: 健康状态
        """
        if not self.initialized:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message="Provider 未初始化",
                details={"initialized": False, "started": self._started},
            )

        if not self._started:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                message="Provider 未启动",
                details={"initialized": True, "started": False},
            )

        # AkShare 是无状态的 HTTP 库,只需检查模块是否可用
        # 不进行实际 API 调用以保持健康检查的轻量级
        if self._akshare is None:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message="AkShare 模块不可用",
                details={"initialized": True, "started": True, "akshare_available": False},
            )

        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="AkShare Provider 运行正常",
            details={
                "initialized": True,
                "started": True,
                "access_mode": self.access_mode,
                "proxy_enabled": self.proxy_info.get("enabled", False),
                "akshare_available": True,
            },
        )

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
    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """
        批量获取实时行情

        对于少量股票（<=10），使用并发单股票查询（快速）
        对于大量股票，使用全市场查询（较慢但高效）

        Args:
            symbols: 股票代码列表

        Returns:
            实时行情数据列表
        """
        if self._akshare is None or not self.initialized:
            return []

        if not symbols:
            return []

        try:
            # 对于少量股票，使用并发单股票查询（更快）
            if len(symbols) <= 10:
                logger.info(f"[AKShare] 使用并发单股票查询获取 {len(symbols)} 只股票行情")
                tasks = [self.get_realtime_quote(symbol) for symbol in symbols]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                quotes = []
                for symbol, result in zip(symbols, results):
                    if isinstance(result, Exception):
                        logger.debug(f"获取 {symbol} 行情失败: {result}")
                        quotes.append(
                            {"symbol": symbol, "error": str(result), "source": "akshare_direct"}
                        )
                    elif isinstance(result, dict) and not result.get("error"):
                        result["symbol"] = symbol
                        quotes.append(result)
                    elif isinstance(result, dict):
                        quotes.append(result)

                logger.info(f"[AKShare] 并发查询完成，获取 {len(quotes)} 条行情")
                return quotes

            # 对于大量股票，使用全市场查询（慢但高效）
            logger.info(f"[AKShare] 使用全市场查询获取 {len(symbols)} 只股票行情")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, self._fetch_realtime_quotes_sync, symbols
            )
            return result  # type: ignore[return-value]
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
                    if isinstance(row, pd.DataFrame):  # type: ignore[union-attr]
                        row = row.iloc[0]

                    result.append(
                        {
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
                        }
                    )
                else:
                    # 未找到的股票返回错误信息或空数据
                    result.append(
                        {"symbol": symbol, "error": "Not found", "source": "akshare_direct_batch"}
                    )

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
        """获取股票列表

        Raises:
            ProviderDataError: 当获取失败时抛出，让上层调用者尝试其他数据源
        """
        if self._akshare is None or not self.initialized:
            raise ProviderDataError(
                provider="akshare",
                message="AKShare 未安装或未初始化",
            )

        loop = asyncio.get_event_loop()
        # 不捕获异常，让 ProviderDataError 传播到上层
        return await loop.run_in_executor(self._executor, self._fetch_stock_list_sync)

    async def get_stock_list(
        self, limit: Optional[int] = None, **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
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
                logger.warning(f"东方财富接口失败: {e1}")

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
                logger.warning(f"stock_info_a_code_name失败: {e2}")

            # 所有 API 都失败，抛出异常让上层调用者处理（尝试其他数据源）
            raise ProviderDataError(
                provider="akshare",
                message="所有股票列表 API 都失败（stock_zh_a_spot_em, stock_info_a_code_name）",
            )

        except ProviderDataError:
            # 重新抛出 ProviderDataError，让上层处理
            raise
        except Exception as e:
            logger.error(f"AKShare 获取股票列表失败: {e}")
            raise ProviderDataError(
                provider="akshare",
                message=f"获取股票列表失败: {e}",
            ) from e

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

    # ==================== 板块接口 ====================

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct",
    )
    async def get_concept_sectors(self, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        获取概念板块列表

        使用东方财富接口 stock_board_concept_name_em

        Returns:
            概念板块列表，包含板块名称、代码、涨跌幅等
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            # 检查缓存
            cache_key = "concept_sectors"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("info", 3600):
                    return cast(List[Dict[str, Any]], cached_data.get("data", []))

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._fetch_concept_sectors_sync)

            if result:
                self._cache[cache_key] = (time.time(), {"data": result})

            return result

        except Exception as e:
            logger.error(f"获取概念板块列表失败: {e}")
            return None

    def _fetch_concept_sectors_sync(self) -> List[Dict[str, Any]]:
        """同步获取概念板块列表"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_board_concept_name_em()
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "rank": int(row.get("排名", 0)),
                        "name": str(row.get("板块名称", "")),
                        "code": str(row.get("板块代码", "")),
                        "price": float(row.get("最新价", 0) or 0),
                        "change": float(row.get("涨跌额", 0) or 0),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                        "market_cap": int(row.get("总市值", 0) or 0),
                        "turnover_rate": float(row.get("换手率", 0) or 0),
                        "up_count": int(row.get("上涨家数", 0) or 0),
                        "down_count": int(row.get("下跌家数", 0) or 0),
                        "leading_stock": str(row.get("领涨股票", "")),
                        "leading_stock_change_pct": float(row.get("领涨股票-涨跌幅", 0) or 0),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 个概念板块")
            return result

        except Exception as e:
            logger.error(f"获取概念板块列表失败: {e}")
            return []

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct",
    )
    async def get_industry_sectors(self, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        获取行业板块列表

        使用东方财富接口 stock_board_industry_name_em

        Returns:
            行业板块列表，包含板块名称、代码、涨跌幅等
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            # 检查缓存
            cache_key = "industry_sectors"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("info", 3600):
                    return cast(List[Dict[str, Any]], cached_data.get("data", []))

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, self._fetch_industry_sectors_sync)

            if result:
                self._cache[cache_key] = (time.time(), {"data": result})

            return result

        except Exception as e:
            logger.error(f"获取行业板块列表失败: {e}")
            return None

    def _fetch_industry_sectors_sync(self) -> List[Dict[str, Any]]:
        """同步获取行业板块列表"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_board_industry_name_em()
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "rank": int(row.get("排名", 0)),
                        "name": str(row.get("板块名称", "")),
                        "code": str(row.get("板块代码", "")),
                        "price": float(row.get("最新价", 0) or 0),
                        "change": float(row.get("涨跌额", 0) or 0),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                        "market_cap": int(row.get("总市值", 0) or 0),
                        "turnover_rate": float(row.get("换手率", 0) or 0),
                        "up_count": int(row.get("上涨家数", 0) or 0),
                        "down_count": int(row.get("下跌家数", 0) or 0),
                        "leading_stock": str(row.get("领涨股票", "")),
                        "leading_stock_change_pct": float(row.get("领涨股票-涨跌幅", 0) or 0),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 个行业板块")
            return result

        except Exception as e:
            logger.error(f"获取行业板块列表失败: {e}")
            return []

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct",
    )
    async def get_sector_stocks(
        self,
        sector_name: str,
        sector_type: str = "concept",
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取板块成份股

        Args:
            sector_name: 板块名称或代码（如 "融资融券" 或 "BK0655"）
            sector_type: 板块类型，"concept" 或 "industry"

        Returns:
            成份股列表
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            # 检查缓存
            cache_key = f"sector_stocks_{sector_type}_{sector_name}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("info", 3600):
                    return cast(List[Dict[str, Any]], cached_data.get("data", []))

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_sector_stocks_sync,
                sector_name,
                sector_type,
            )

            if result:
                self._cache[cache_key] = (time.time(), {"data": result})

            return result

        except Exception as e:
            logger.error(f"获取板块成份股失败: {e}")
            return None

    def _fetch_sector_stocks_sync(
        self,
        sector_name: str,
        sector_type: str,
    ) -> List[Dict[str, Any]]:
        """同步获取板块成份股"""
        module = self._akshare
        if module is None:
            return []

        try:
            if sector_type == "concept":
                df = module.stock_board_concept_cons_em(symbol=sector_name)
            else:
                df = module.stock_board_industry_cons_em(symbol=sector_name)

            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "rank": int(row.get("序号", 0)),
                        "symbol": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "price": float(row.get("最新价", 0) or 0),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                        "change": float(row.get("涨跌额", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                        "amount": float(row.get("成交额", 0) or 0),
                        "amplitude": float(row.get("振幅", 0) or 0),
                        "high": float(row.get("最高", 0) or 0),
                        "low": float(row.get("最低", 0) or 0),
                        "open": float(row.get("今开", 0) or 0),
                        "prev_close": float(row.get("昨收", 0) or 0),
                        "turnover_rate": float(row.get("换手率", 0) or 0),
                        "pe_ratio": float(row.get("市盈率-动态", 0) or 0),
                        "pb_ratio": float(row.get("市净率", 0) or 0),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {sector_name} 板块 {len(result)} 只成份股")
            return result

        except Exception as e:
            logger.error(f"获取板块成份股失败: {e}")
            return []

    # ==================== 资金流向接口 ====================

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        module="akshare_direct",
    )
    async def get_individual_capital_flow(
        self,
        symbol: str,
        market: str = "sh",
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取个股资金流向

        使用东方财富接口 stock_individual_fund_flow

        Args:
            symbol: 股票代码（如 "600094"）
            market: 市场，"sh" 上海 / "sz" 深圳 / "bj" 北京

        Returns:
            近 100 个交易日的资金流向数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_individual_capital_flow_sync,
                symbol,
                market,
            )
            return result

        except Exception as e:
            logger.error(f"获取个股资金流向失败: {e}")
            return None

    def _fetch_individual_capital_flow_sync(
        self,
        symbol: str,
        market: str,
    ) -> List[Dict[str, Any]]:
        """同步获取个股资金流向"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_individual_fund_flow(stock=symbol, market=market)
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "date": str(row.get("日期", "")),
                        "close": float(row.get("收盘价", 0) or 0),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                        "main_net_inflow": float(row.get("主力净流入-净额", 0) or 0),
                        "main_net_inflow_pct": float(row.get("主力净流入-净占比", 0) or 0),
                        "super_large_net_inflow": float(row.get("超大单净流入-净额", 0) or 0),
                        "super_large_net_inflow_pct": float(row.get("超大单净流入-净占比", 0) or 0),
                        "large_net_inflow": float(row.get("大单净流入-净额", 0) or 0),
                        "large_net_inflow_pct": float(row.get("大单净流入-净占比", 0) or 0),
                        "medium_net_inflow": float(row.get("中单净流入-净额", 0) or 0),
                        "medium_net_inflow_pct": float(row.get("中单净流入-净占比", 0) or 0),
                        "small_net_inflow": float(row.get("小单净流入-净额", 0) or 0),
                        "small_net_inflow_pct": float(row.get("小单净流入-净占比", 0) or 0),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {symbol} 共 {len(result)} 条资金流向数据")
            return result

        except Exception as e:
            logger.error(f"获取个股资金流向失败: {e}")
            return []

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct",
    )
    async def get_sector_capital_flow_rank(
        self,
        indicator: str = "今日",
        sector_type: str = "行业资金流",
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取板块资金流向排名

        使用东方财富接口 stock_sector_fund_flow_rank

        Args:
            indicator: 时间周期，"今日" / "5日" / "10日"
            sector_type: 板块类型，"行业资金流" / "概念资金流" / "地域资金流"

        Returns:
            板块资金流向排名数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            # 检查缓存
            cache_key = f"sector_capital_flow_{indicator}_{sector_type}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("realtime", 60):
                    return cast(List[Dict[str, Any]], cached_data.get("data", []))

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_sector_capital_flow_rank_sync,
                indicator,
                sector_type,
            )

            if result:
                self._cache[cache_key] = (time.time(), {"data": result})

            return result

        except Exception as e:
            logger.error(f"获取板块资金流向排名失败: {e}")
            return None

    def _fetch_sector_capital_flow_rank_sync(
        self,
        indicator: str,
        sector_type: str,
    ) -> List[Dict[str, Any]]:
        """同步获取板块资金流向排名"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)
            if df is None or df.empty:
                return []

            result = []
            # 动态获取列名前缀
            prefix = indicator if indicator != "今日" else "今日"

            for _, row in df.iterrows():
                result.append(
                    {
                        "rank": int(self._safe_float(row.get("序号", 0), 0.0)),
                        "name": str(row.get("名称", "")),
                        "change_pct": self._safe_float(
                            row.get(f"{prefix}涨跌幅", row.get("今日涨跌幅", 0)),
                            0.0,
                        ),
                        "main_net_inflow": self._safe_float(
                            row.get(
                                f"{prefix}主力净流入-净额",
                                row.get("主力净流入-净额", 0),
                            ),
                            0.0,
                        ),
                        "main_net_inflow_pct": self._safe_float(
                            row.get(
                                f"{prefix}主力净流入-净占比",
                                row.get("主力净流入-净占比", 0),
                            ),
                            0.0,
                        ),
                        "super_large_net_inflow": self._safe_float(
                            row.get(
                                f"{prefix}超大单净流入-净额",
                                row.get("超大单净流入-净额", 0),
                            ),
                            0.0,
                        ),
                        "super_large_net_inflow_pct": self._safe_float(
                            row.get(
                                f"{prefix}超大单净流入-净占比",
                                row.get("超大单净流入-净占比", 0),
                            ),
                            0.0,
                        ),
                        "large_net_inflow": self._safe_float(
                            row.get(
                                f"{prefix}大单净流入-净额",
                                row.get("大单净流入-净额", 0),
                            ),
                            0.0,
                        ),
                        "large_net_inflow_pct": self._safe_float(
                            row.get(
                                f"{prefix}大单净流入-净占比",
                                row.get("大单净流入-净占比", 0),
                            ),
                            0.0,
                        ),
                        "leading_stock": str(
                            row.get(
                                f"{prefix}主力净流入最大股", row.get("今日主力净流入最大股", "")
                            )
                        ),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 条板块资金流向数据")
            return result

        except Exception as e:
            logger.error(f"获取板块资金流向排名失败: {e}")
            # AkShare 在 5日/10日口径偶发返回字符串值，内部排序会触发类型比较异常。
            # 这里回退到直接请求东财接口，并在本地做数值清洗与排序。
            return self._fetch_sector_capital_flow_rank_raw_sync(indicator, sector_type)

    def _fetch_sector_capital_flow_rank_raw_sync(
        self,
        indicator: str,
        sector_type: str,
    ) -> List[Dict[str, Any]]:
        """绕过 akshare 排序逻辑，直接请求东财接口并做稳健解析。"""
        try:
            import math
            import requests
        except Exception as import_error:
            logger.error(f"加载 fallback 依赖失败: {import_error}")
            return []

        sector_type_map = {"行业资金流": "2", "概念资金流": "3", "地域资金流": "1"}
        indicator_fields: Dict[str, Dict[str, str]] = {
            "今日": {
                "fid0": "f62",
                "stat": "1",
                "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124",
                "change": "f3",
                "main_net": "f62",
                "main_pct": "f184",
                "super_net": "f66",
                "super_pct": "f69",
                "large_net": "f72",
                "large_pct": "f75",
                "leading_stock": "f204",
            },
            "5日": {
                "fid0": "f164",
                "stat": "5",
                "fields": "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124",
                "change": "f109",
                "main_net": "f164",
                "main_pct": "f165",
                "super_net": "f166",
                "super_pct": "f167",
                "large_net": "f168",
                "large_pct": "f169",
                "leading_stock": "f257",
            },
            "10日": {
                "fid0": "f174",
                "stat": "10",
                "fields": "f12,f14,f2,f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f260,f261,f124",
                "change": "f160",
                "main_net": "f174",
                "main_pct": "f175",
                "super_net": "f176",
                "super_pct": "f177",
                "large_net": "f178",
                "large_pct": "f179",
                "leading_stock": "f260",
            },
        }

        mapping = indicator_fields.get(indicator)
        sector_tag = sector_type_map.get(sector_type)
        if mapping is None or sector_tag is None:
            logger.error(f"不支持的板块资金流参数: indicator={indicator}, sector_type={sector_type}")
            return []

        url = "https://push2.eastmoney.com/api/qt/clist/get"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
        }
        params: Dict[str, Any] = {
            "pn": 1,
            "pz": 100,
            "po": 1,
            "np": 1,
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fltt": 2,
            "invt": 2,
            "fid0": mapping["fid0"],
            "fs": f"m:90 t:{sector_tag}",
            "stat": mapping["stat"],
            "fields": mapping["fields"],
            "_": int(time.time() * 1000),
        }

        try:
            first_resp = requests.get(url, params=params, headers=headers, timeout=15)
            first_resp.raise_for_status()
            first_json = first_resp.json()
        except Exception as request_error:
            logger.error(f"fallback 请求板块资金流首页失败: {request_error}")
            return []

        data_node = first_json.get("data") if isinstance(first_json, dict) else None
        if not isinstance(data_node, dict):
            return []

        total = int(data_node.get("total") or 0)
        total_pages = max(1, math.ceil(total / 100)) if total > 0 else 1
        rows: List[Dict[str, Any]] = []

        for page in range(1, total_pages + 1):
            params["pn"] = page
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                payload = resp.json()
                data = payload.get("data") if isinstance(payload, dict) else None
                diff = data.get("diff") if isinstance(data, dict) else None
                if not isinstance(diff, list):
                    continue
            except Exception as page_error:
                logger.warning(f"fallback 获取板块资金流分页失败(page={page}): {page_error}")
                continue

            for item in diff:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "name": str(item.get("f14", "")),
                        "change_pct": self._safe_float(item.get(mapping["change"]), 0.0),
                        "main_net_inflow": self._safe_float(item.get(mapping["main_net"]), 0.0),
                        "main_net_inflow_pct": self._safe_float(item.get(mapping["main_pct"]), 0.0),
                        "super_large_net_inflow": self._safe_float(
                            item.get(mapping["super_net"]),
                            0.0,
                        ),
                        "super_large_net_inflow_pct": self._safe_float(
                            item.get(mapping["super_pct"]),
                            0.0,
                        ),
                        "large_net_inflow": self._safe_float(item.get(mapping["large_net"]), 0.0),
                        "large_net_inflow_pct": self._safe_float(
                            item.get(mapping["large_pct"]),
                            0.0,
                        ),
                        "leading_stock": str(item.get(mapping["leading_stock"], "")),
                        "source": "akshare_direct_raw",
                    }
                )

        rows.sort(key=lambda x: self._safe_float(x.get("main_net_inflow"), 0.0), reverse=True)
        for idx, row in enumerate(rows, start=1):
            row["rank"] = idx

        logger.info(
            f"fallback 直连东财获取到 {len(rows)} 条板块资金流向数据(indicator={indicator}, sector_type={sector_type})"
        )
        return rows

    # ==================== 融资融券接口 ====================

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        module="akshare_direct",
    )
    async def get_margin_trading(
        self,
        start_date: str,
        end_date: str,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取融资融券汇总数据（上交所）

        使用接口 stock_margin_sse

        Args:
            start_date: 开始日期 (如 "20240101")
            end_date: 结束日期 (如 "20240131")

        Returns:
            融资融券汇总数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_margin_trading_sync,
                start_date,
                end_date,
            )
            return result

        except Exception as e:
            logger.error(f"获取融资融券数据失败: {e}")
            return None

    def _fetch_margin_trading_sync(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """同步获取融资融券汇总数据"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_margin_sse(start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "date": str(row.get("信用交易日期", "")),
                        "margin_balance": float(row.get("融资余额", 0) or 0),
                        "margin_buy": float(row.get("融资买入额", 0) or 0),
                        "short_volume": float(row.get("融券余量", 0) or 0),
                        "short_volume_value": float(row.get("融券余量金额", 0) or 0),
                        "short_sell_volume": float(row.get("融券卖出量", 0) or 0),
                        "total_balance": float(row.get("融资融券余额", 0) or 0),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 条融资融券数据")
            return result

        except Exception as e:
            logger.error(f"获取融资融券数据失败: {e}")
            return []

    # ==================== 大宗交易接口 ====================

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        module="akshare_direct",
    )
    async def get_block_trades(
        self,
        start_date: str,
        end_date: str,
        symbol: str = "A股",
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取大宗交易每日明细

        使用接口 stock_dzjy_mrmx

        Args:
            start_date: 开始日期 (如 "20240101")
            end_date: 结束日期 (如 "20240101")
            symbol: 证券类型 ("A股", "B股", "基金", "债券")

        Returns:
            大宗交易明细数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_block_trades_sync,
                start_date,
                end_date,
                symbol,
            )
            return result

        except Exception as e:
            logger.error(f"获取大宗交易数据失败: {e}")
            return None

    def _fetch_block_trades_sync(
        self,
        start_date: str,
        end_date: str,
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """同步获取大宗交易明细"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_dzjy_mrmx(symbol=symbol, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "rank": int(row.get("序号", 0)),
                        "date": str(row.get("交易日期", "")),
                        "symbol": str(row.get("证券代码", "")),
                        "name": str(row.get("证券简称", "")),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                        "close": float(row.get("收盘价", 0) or 0),
                        "trade_price": float(row.get("成交价", 0) or 0),
                        "premium_rate": float(row.get("折溢率", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                        "amount": float(row.get("成交额", 0) or 0),
                        "buyer": str(row.get("买方营业部", "")),
                        "seller": str(row.get("卖方营业部", "")),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 条大宗交易数据")
            return result

        except Exception as e:
            logger.error(f"获取大宗交易数据失败: {e}")
            return []

    # ==================== 北向资金接口 ====================

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        module="akshare_direct",
    )
    async def get_northbound_flow_hist(
        self,
        symbol: str = "北向资金",
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取北向资金历史数据

        使用接口 stock_hsgt_hist_em

        Args:
            symbol: 资金类型 ("北向资金", "沪股通", "深股通", "南向资金", "港股通沪", "港股通深")

        Returns:
            北向资金历史数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            # 检查缓存
            cache_key = f"northbound_hist_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("historical", 300):
                    return cast(List[Dict[str, Any]], cached_data.get("data", []))

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_northbound_flow_hist_sync,
                symbol,
            )

            if result:
                self._cache[cache_key] = (time.time(), {"data": result})

            return result

        except Exception as e:
            logger.error(f"获取北向资金历史数据失败: {e}")
            return None

    def _fetch_northbound_flow_hist_sync(self, symbol: str) -> List[Dict[str, Any]]:
        """同步获取北向资金历史数据"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_hsgt_hist_em(symbol=symbol)
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "date": str(row.get("日期", "")),
                        "net_buy": float(row.get("当日成交净买额", 0) or 0),
                        "buy_amount": float(row.get("买入成交额", 0) or 0),
                        "sell_amount": float(row.get("卖出成交额", 0) or 0),
                        "cumulative_net_buy": float(row.get("历史累计净买额", 0) or 0),
                        "fund_inflow": float(row.get("当日资金流入", 0) or 0),
                        "balance": float(row.get("当日余额", 0) or 0),
                        "market_value": float(row.get("持股市值", 0) or 0),
                        "leading_stock": str(row.get("领涨股", "")),
                        "leading_stock_change_pct": float(row.get("领涨股-涨跌幅", 0) or 0),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 条北向资金历史数据")
            return result

        except Exception as e:
            logger.error(f"获取北向资金历史数据失败: {e}")
            return []

    # ==================== 涨停板接口 ====================

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct",
    )
    async def get_limit_up_pool(
        self,
        date: str,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取涨停股池

        使用接口 stock_zt_pool_em

        Args:
            date: 交易日期 (如 "20241008")

        Returns:
            涨停股池数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            # 检查缓存
            cache_key = f"limit_up_pool_{date}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("historical", 300):
                    return cast(List[Dict[str, Any]], cached_data.get("data", []))

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_limit_up_pool_sync,
                date,
            )

            if result:
                self._cache[cache_key] = (time.time(), {"data": result})

            return result

        except Exception as e:
            logger.error(f"获取涨停股池数据失败: {e}")
            return None

    def _fetch_limit_up_pool_sync(self, date: str) -> List[Dict[str, Any]]:
        """同步获取涨停股池"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_zt_pool_em(date=date)
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "rank": int(row.get("序号", 0)),
                        "symbol": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                        "price": float(row.get("最新价", 0) or 0),
                        "amount": float(row.get("成交额", 0) or 0),
                        "circulating_market_cap": float(row.get("流通市值", 0) or 0),
                        "total_market_cap": float(row.get("总市值", 0) or 0),
                        "turnover_rate": float(row.get("换手率", 0) or 0),
                        "seal_amount": float(row.get("封板资金", 0) or 0),
                        "first_seal_time": str(row.get("首次封板时间", "")),
                        "last_seal_time": str(row.get("最后封板时间", "")),
                        "break_count": int(row.get("炸板次数", 0) or 0),
                        "limit_up_stats": str(row.get("涨停统计", "")),
                        "continuous_count": int(row.get("连板数", 0) or 0),
                        "industry": str(row.get("所属行业", "")),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 只涨停股")
            return result

        except Exception as e:
            logger.error(f"获取涨停股池数据失败: {e}")
            return []

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct",
    )
    async def get_limit_down_pool(
        self,
        date: str,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取跌停股池

        使用接口 stock_zt_pool_dtgc_em

        Args:
            date: 交易日期 (如 "20241011")

        Returns:
            跌停股池数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_limit_down_pool_sync,
                date,
            )
            return result

        except Exception as e:
            logger.error(f"获取跌停股池数据失败: {e}")
            return None

    def _fetch_limit_down_pool_sync(self, date: str) -> List[Dict[str, Any]]:
        """同步获取跌停股池"""
        module = self._akshare
        if module is None:
            return []

        try:
            df = module.stock_zt_pool_dtgc_em(date=date)
            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append(
                    {
                        "rank": int(row.get("序号", 0)),
                        "symbol": str(row.get("代码", "")),
                        "name": str(row.get("名称", "")),
                        "change_pct": float(row.get("涨跌幅", 0) or 0),
                        "price": float(row.get("最新价", 0) or 0),
                        "amount": float(row.get("成交额", 0) or 0),
                        "circulating_market_cap": float(row.get("流通市值", 0) or 0),
                        "total_market_cap": float(row.get("总市值", 0) or 0),
                        "turnover_rate": float(row.get("换手率", 0) or 0),
                        "seal_amount": float(row.get("封单资金", 0) or 0),
                        "last_seal_time": str(row.get("最后封板时间", "")),
                        "on_board_amount": float(row.get("板上成交额", 0) or 0),
                        "continuous_count": int(row.get("连续跌停", 0) or 0),
                        "break_count": int(row.get("开板次数", 0) or 0),
                        "industry": str(row.get("所属行业", "")),
                        "source": "akshare_direct",
                    }
                )

            logger.info(f"获取到 {len(result)} 只跌停股")
            return result

        except Exception as e:
            logger.error(f"获取跌停股池数据失败: {e}")
            return []

    # ==================== 财务报表接口 ====================

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        module="akshare_direct",
    )
    async def get_financial_report(
        self,
        date: str,
        report_type: str = "业绩报表",
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取财务报表数据

        Args:
            date: 报告期 (如 "20240331"、"20240630"、"20240930"、"20241231")
            report_type: 报表类型 ("业绩报表", "业绩快报", "业绩预告")

        Returns:
            财务报表数据
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_financial_report_sync,
                date,
                report_type,
            )
            return result

        except Exception as e:
            logger.error(f"获取财务报表数据失败: {e}")
            return None

    def _fetch_financial_report_sync(
        self,
        date: str,
        report_type: str,
    ) -> List[Dict[str, Any]]:
        """同步获取财务报表"""
        module = self._akshare
        if module is None:
            return []

        try:
            if report_type == "业绩报表":
                df = module.stock_yjbb_em(date=date)
            elif report_type == "业绩快报":
                df = module.stock_yjkb_em(date=date)
            elif report_type == "业绩预告":
                df = module.stock_yjyg_em(date=date)
            else:
                logger.warning(f"未知的报表类型: {report_type}")
                return []

            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                item = {
                    "rank": int(row.get("序号", 0)),
                    "symbol": str(row.get("股票代码", "")),
                    "name": str(row.get("股票简称", "")),
                    "report_type": report_type,
                    "source": "akshare_direct",
                }

                # 根据不同报表类型添加不同字段
                if report_type == "业绩报表":
                    item.update(
                        {
                            "eps": float(row.get("每股收益", 0) or 0),
                            "revenue": float(row.get("营业总收入-营业总收入", 0) or 0),
                            "revenue_yoy": float(row.get("营业总收入-同比增长", 0) or 0),
                            "net_profit": float(row.get("净利润-净利润", 0) or 0),
                            "net_profit_yoy": float(row.get("净利润-同比增长", 0) or 0),
                            "bps": float(row.get("每股净资产", 0) or 0),
                            "roe": float(row.get("净资产收益率", 0) or 0),
                            "gross_margin": float(row.get("销售毛利率", 0) or 0),
                            "industry": str(row.get("所处行业", "")),
                        }
                    )
                elif report_type == "业绩快报":
                    item.update(
                        {
                            "eps": float(row.get("每股收益", 0) or 0) if row.get("每股收益") else 0,
                            "revenue": (
                                float(row.get("营业收入-营业收入", 0) or 0)
                                if row.get("营业收入-营业收入")
                                else 0
                            ),
                            "net_profit": (
                                float(row.get("净利润-净利润", 0) or 0)
                                if row.get("净利润-净利润")
                                else 0
                            ),
                            "bps": (
                                float(row.get("每股净资产", 0) or 0) if row.get("每股净资产") else 0
                            ),
                            "roe": (
                                float(row.get("净资产收益率", 0) or 0)
                                if row.get("净资产收益率")
                                else 0
                            ),
                            "industry": str(row.get("所处行业", "")),
                        }
                    )
                elif report_type == "业绩预告":
                    item.update(
                        {
                            "forecast_indicator": str(row.get("预测指标", "")),
                            "performance_change": str(row.get("业绩变动", "")),
                            "forecast_value": str(row.get("预测数值", "")),
                            "change_range": str(row.get("业绩变动幅度", "")),
                            "change_reason": str(row.get("业绩变动原因", "")),
                            "forecast_type": str(row.get("预告类型", "")),
                            "last_year_value": str(row.get("上年同期值", "")),
                        }
                    )

                result.append(item)

            logger.info(f"获取到 {len(result)} 条{report_type}数据")
            return result

        except Exception as e:
            logger.error(f"获取财务报表数据失败: {e}")
            return []

    # ==================== 扩展接口 ====================

    async def get_trading_calendar(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> Optional[List[str]]:
        """
        获取交易日历

        使用 AkShare 的 tool_trade_date_hist_sina 接口

        Args:
            start_date: 开始日期 (格式: YYYYMMDD)
            end_date: 结束日期 (格式: YYYYMMDD)
            **kwargs: 其他参数

        Returns:
            交易日期列表 (格式: YYYYMMDD)，失败返回 None
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_trading_calendar_sync,
                start_date,
                end_date,
            )
            return result
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return None

    def _fetch_trading_calendar_sync(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Optional[List[str]]:
        """同步获取交易日历"""
        module = self._akshare
        if module is None:
            return None

        try:
            # 使用 tool_trade_date_hist_sina 获取历史交易日
            df = module.tool_trade_date_hist_sina()

            if df is None or df.empty:
                return None

            # 提取交易日期
            if "trade_date" in df.columns:
                dates = df["trade_date"].tolist()
            else:
                # 尝试第一列
                dates = df.iloc[:, 0].tolist()

            # 转换为字符串格式 YYYYMMDD
            result = []
            for d in dates:
                try:
                    if hasattr(d, "strftime"):
                        result.append(d.strftime("%Y%m%d"))
                    else:
                        # 清洗字符串
                        cleaned = "".join(c for c in str(d) if c.isdigit())
                        if len(cleaned) == 8:
                            result.append(cleaned)
                except Exception:
                    continue

            # 过滤日期范围
            if start_date:
                result = [d for d in result if d >= start_date]
            if end_date:
                result = [d for d in result if d <= end_date]

            logger.info(f"获取到 {len(result)} 个交易日")
            return result

        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return None

    async def get_dragon_tiger(
        self,
        date: Optional[str] = None,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取龙虎榜数据

        使用 AkShare 的 stock_lhb_detail_em 接口

        Args:
            date: 交易日期 (格式: YYYYMMDD)，默认为最近交易日
            **kwargs: 其他参数

        Returns:
            龙虎榜数据列表，失败返回 None
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            # 默认使用最近的交易日
            if not date:
                date = datetime.now().strftime("%Y%m%d")

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_dragon_tiger_sync,
                date,
            )
            return result
        except Exception as e:
            logger.error(f"获取龙虎榜失败: {e}")
            return None

    def _fetch_dragon_tiger_sync(self, date: str) -> Optional[List[Dict[str, Any]]]:
        """同步获取龙虎榜数据"""
        module = self._akshare
        if module is None:
            return None

        try:
            # 使用 stock_lhb_detail_em 获取龙虎榜详情
            df = module.stock_lhb_detail_em(
                start_date=date,
                end_date=date,
            )

            if df is None or df.empty:
                logger.warning(f"龙虎榜 {date} 无数据")
                return []

            result = []
            for _, row in df.iterrows():
                item = {
                    "date": date,
                    "symbol": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "close": self._safe_float(row.get("收盘价", 0)),
                    "change_pct": self._safe_float(row.get("涨跌幅", 0)),
                    "turnover_rate": self._safe_float(row.get("换手率", 0)),
                    "net_buy": self._safe_float(row.get("龙虎榜净买额", 0)),
                    "buy_amount": self._safe_float(row.get("龙虎榜买入额", 0)),
                    "sell_amount": self._safe_float(row.get("龙虎榜卖出额", 0)),
                    "reason": str(row.get("上榜原因", "")),
                    "source": "akshare_direct",
                }
                result.append(item)

            logger.info(f"获取到 {len(result)} 条龙虎榜数据")
            return result

        except Exception as e:
            logger.error(f"获取龙虎榜数据失败: {e}")
            return None

    async def get_minute_kline(
        self,
        symbol: str,
        period: str = "1",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取分钟K线数据

        使用 AkShare 的 stock_zh_a_hist_min_em 接口

        Args:
            symbol: 股票代码 (如 "000001")
            period: 分钟周期 ("1", "5", "15", "30", "60")
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 其他参数

        Returns:
            分钟K线数据列表，失败返回 None
        """
        if self._akshare is None or not self.initialized:
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_minute_kline_sync,
                symbol,
                period,
            )
            return result
        except Exception as e:
            logger.error(f"获取分钟K线失败: {e}")
            return None

    def _fetch_minute_kline_sync(
        self,
        symbol: str,
        period: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """同步获取分钟K线"""
        module = self._akshare
        if module is None:
            return None

        try:
            # 使用 stock_zh_a_hist_min_em 获取分钟K线
            df = module.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=period,
            )

            if df is None or df.empty:
                return None

            result = []
            for _, row in df.iterrows():
                item = {
                    "datetime": str(row.get("时间", "")),
                    "open": self._safe_float(row.get("开盘", 0)),
                    "high": self._safe_float(row.get("最高", 0)),
                    "low": self._safe_float(row.get("最低", 0)),
                    "close": self._safe_float(row.get("收盘", 0)),
                    "volume": self._safe_float(row.get("成交量", 0)),
                    "amount": self._safe_float(row.get("成交额", 0)),
                    "source": "akshare_direct",
                }
                result.append(item)

            logger.info(f"获取到 {len(result)} 条分钟K线数据")
            return result

        except Exception as e:
            logger.error(f"获取分钟K线失败: {e}")
            return None


# 向后兼容别名（重命名前的旧名称）
AKShareDirectProvider = AkShareProvider
