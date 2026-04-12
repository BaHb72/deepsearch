# encoding:utf-8
"""
Unified Backtrader Adapter
统一的Backtrader数据适配器 - 整合QMT/MiniQMT/AkShare数据源
Author: DeepSearch Team
Version: 1.0.0
"""

import asyncio
import concurrent.futures
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import pandas as pd
from core.backtest.rules import is_a_share_symbol
from core.infrastructure.providers.managers.data_source_manager import get_data_manager
from core.ports.data_sources import DataSourceType
from loguru import logger

from ..data.data_bridge import DataBridge
from ..data.history_status_overlay import HistoryStatusOverlayError, coerce_status_dataframe

bt: Any

try:
    import backtrader as _backtrader

    HAS_BACKTRADER = True
    bt = _backtrader
except ImportError:
    HAS_BACKTRADER = False
    bt = None

if TYPE_CHECKING:
    from backtrader.feeds import PandasData as BacktraderPandasData
else:
    BacktraderPandasData = Any


class UnifiedBacktraderAdapter:
    """
    统一的Backtrader数据适配器

    特性：
    1. 自动选择最佳数据源（QMT/MiniQMT/AkShare）
    2. 智能格式转换
    3. 数据验证和清洗
    4. 缓存优化
    """

    def __init__(self, source: str = "auto"):
        """
        初始化适配器

        Args:
            source: 数据源选择 ('auto', 'qmt', 'akshare')
        """
        if not HAS_BACKTRADER:
            raise ImportError("请先安装 backtrader: pip install backtrader")

        self.source = source
        self.data_manager: Any | None = None
        self.data_bridge = DataBridge()
        self._cache: Dict[str, pd.DataFrame] = {}
        self._initialized = False

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return symbol.strip().upper().replace("-", "").replace("_", "")

    @classmethod
    def _is_a_share_symbol(cls, symbol: str) -> bool:
        return is_a_share_symbol(symbol)

    @staticmethod
    async def _await_if_needed(value: Any) -> Any:
        if asyncio.iscoroutine(value):
            return await value
        return value

    async def _fetch_daily_data(
        self,
        manager: Any,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> Any:
        if hasattr(manager, "get_stock_daily"):
            getter = getattr(manager, "get_stock_daily")
            if callable(getter):
                try:
                    return await getter(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        source=self.source,
                        adjust=adjust,
                        use_cache=True,
                    )
                except TypeError:
                    return await getter(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        source=self.source,
                        adjust=adjust,
                    )

        hist_getter = getattr(manager, "get_stock_hist", None)
        if callable(hist_getter):
            raw_payload = await hist_getter(
                symbol=symbol,
                period="1d",
                start_date=start_date,
                end_date=end_date,
                preferred_source=self.source,
                limit=5000,
            )
            if isinstance(raw_payload, dict) and "data" in raw_payload:
                return raw_payload.get("data")
            return raw_payload

        raise ValueError("数据管理器不支持日线历史数据接口")

    async def _fetch_history_status_payload(self, manager: Any, symbol: str) -> Any:
        provider: Any | None = None
        get_provider = getattr(manager, "get_provider", None)
        if callable(get_provider):
            try:
                provider = get_provider(DataSourceType.AMAZINGDATA)
            except Exception:
                provider = None
            if provider is None:
                try:
                    provider = get_provider()
                except Exception:
                    provider = None

        if provider is None:
            raise HistoryStatusOverlayError(
                "回测要求强制接入 history_stock_status，但当前数据管理器未提供可用 Provider"
            )

        fetcher = getattr(provider, "get_history_stock_status", None)
        if not callable(fetcher):
            raise HistoryStatusOverlayError(
                "回测要求强制接入 history_stock_status，但当前 Provider 不支持该接口"
            )

        last_error: Optional[Exception] = None
        call_patterns = (
            lambda: fetcher(code_list=[symbol], is_local=True),
            lambda: fetcher([symbol], is_local=True),
            lambda: fetcher(code_list=[symbol]),
            lambda: fetcher([symbol]),
        )

        for invoke in call_patterns:
            try:
                payload = await self._await_if_needed(invoke())
            except TypeError:
                continue
            except Exception as exc:
                last_error = exc
                continue

            if not coerce_status_dataframe(payload).empty:
                return payload

        if last_error is not None:
            raise HistoryStatusOverlayError(
                f"拉取 history_stock_status 失败: {last_error}"
            ) from last_error

        raise HistoryStatusOverlayError(
            f"{symbol} 未返回有效 history_stock_status 数据", not_found=True
        )

    async def _apply_status_overlay_if_needed(
        self,
        manager: Any,
        bars_df: pd.DataFrame,
        *,
        symbol: str,
    ) -> pd.DataFrame:
        if bars_df.empty:
            return bars_df

        if not self._is_a_share_symbol(symbol):
            logger.debug(f"{symbol} 非A股标的，跳过 history_status_overlay")
            return bars_df

        payload = await self._fetch_history_status_payload(manager, symbol)
        return self.data_bridge.apply_history_status_overlay(
            bars_df,
            status_payload=payload,
            symbol=symbol,
            strict=True,
        )

    def _require_data_manager(self) -> Any:
        """Retrieve the data manager instance or raise if not initialized."""
        if self.data_manager is None:
            raise RuntimeError("Data manager is not initialized")
        return self.data_manager

    async def initialize(self):
        """异步初始化"""
        if not self._initialized:
            logger.info("初始化Unified Backtrader Adapter...")
            self.data_manager = await get_data_manager()
            self._initialized = True
            logger.info("适配器初始化完成")

    def _run_sync(self, coro):
        """安全地在同步上下文中运行异步协程

        基于Python asyncio最佳实践：
        - 如果已有运行中的事件循环，使用线程池避免嵌套循环
        - 如果没有运行中的循环，使用asyncio.run()
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # 已有事件循环运行中，使用线程池执行
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            # 没有运行中的循环，安全使用 asyncio.run
            return asyncio.run(coro)

    def initialize_sync(self):
        """同步初始化（用于Backtrader）"""
        self._run_sync(self.initialize())

    def _ensure_dataframe(self, data: Any) -> pd.DataFrame:
        """Ensure the returned payload is a DataFrame.

        基于pandas最佳实践，增加异常处理避免意外类型导致崩溃。
        """
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if data is None:
            return pd.DataFrame()
        try:
            return pd.DataFrame(data)
        except (ValueError, TypeError) as e:
            logger.warning(f"无法转换数据为DataFrame: {e}")
            return pd.DataFrame()

    async def get_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        timeframe: str = "1d",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取历史数据并转换为 Backtrader 兼容格式"""
        if not self._initialized:
            await self.initialize()

        manager = self._require_data_manager()

        start_str = (
            start_date.strftime("%Y%m%d")
            if isinstance(start_date, datetime)
            else start_date.replace("-", "")
        )
        end_str = (
            end_date.strftime("%Y%m%d")
            if isinstance(end_date, datetime)
            else end_date.replace("-", "")
        )

        cache_key = f"{symbol}_{start_str}_{end_str}_{timeframe}_{adjust}"
        if cache_key in self._cache:
            logger.debug(f"使用缓存数据: {symbol}")
            return self._cache[cache_key].copy()

        logger.info(f"获取数据: {symbol} [{start_str} - {end_str}] {timeframe}")

        if timeframe == "1d":
            raw_df = await self._fetch_daily_data(
                manager,
                symbol=symbol,
                start_date=start_str,
                end_date=end_str,
                adjust=adjust,
            )
        elif timeframe in ["1m", "5m", "15m", "30m", "60m"]:
            raw_df = await self._get_minute_data(symbol, start_str, end_str, timeframe, adjust)
        elif timeframe == "1w":
            raw_df = await self._get_weekly_data(symbol, start_str, end_str, adjust)
        else:
            raise ValueError(f"不支持的时间周期: {timeframe}")

        standardized_df = self._ensure_dataframe(raw_df)
        df = self.data_bridge.convert_to_backtrader(standardized_df, symbol)
        df = await self._apply_status_overlay_if_needed(manager, df, symbol=symbol)

        if not df.empty:
            self._cache[cache_key] = df.copy()
            logger.info(f"获取到 {len(df)} 条记录")
        else:
            logger.warning(f"未获取到数据: {symbol}")

        return df

    async def _get_minute_data(
        self, symbol: str, start_date: str, end_date: str, timeframe: str, adjust: str
    ) -> pd.DataFrame:
        """获取分钟级别数据"""
        manager = self._require_data_manager()

        period_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "60m": "60m"}
        period = period_map.get(timeframe, "5m")

        if self.source in ["auto", "qmt"]:
            try:
                provider = getattr(manager, "_qmt_provider", None)
                if provider:
                    df = await provider.get_kline(
                        symbol=symbol,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        adjust=adjust,
                    )
                    standardized = self._ensure_dataframe(df)
                    if not standardized.empty:
                        return standardized
            except Exception as exc:
                logger.warning(f"QMT 获取分钟数据失败: {exc}")

        logger.warning("未命中分钟级专用数据源，使用日线数据降采样")
        fallback = await self._fetch_daily_data(
            manager,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        return self._ensure_dataframe(fallback)

    async def _get_weekly_data(
        self, symbol: str, start_date: str, end_date: str, adjust: str
    ) -> pd.DataFrame:
        """获取周线数据"""
        manager = self._require_data_manager()

        daily_df = await self._fetch_daily_data(
            manager,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )

        standardized = self._ensure_dataframe(daily_df)

        if standardized.empty:
            return standardized

        return self._resample_to_weekly(standardized)

    def _resample_to_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        """将日线数据转换为周线

        基于pandas最佳实践，避免使用inplace=True，先复制再修改。
        """
        if df.empty:
            return df.copy()  # 返回副本而非原对象

        # 先复制，避免修改原始数据
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            if "date" in df.columns:
                df = df.set_index("date")  # 不使用inplace

        resampler = df.resample("W")
        weekly_data: Dict[str, pd.Series] = {}

        if "open" in df.columns:
            weekly_data["open"] = resampler["open"].first()
        if "high" in df.columns:
            weekly_data["high"] = resampler["high"].max()
        if "low" in df.columns:
            weekly_data["low"] = resampler["low"].min()
        if "close" in df.columns:
            weekly_data["close"] = resampler["close"].last()
        if "volume" in df.columns:
            weekly_data["volume"] = resampler["volume"].sum()

        weekly = pd.DataFrame(weekly_data)
        return weekly

    def create_backtrader_feed(
        self, dataframe: pd.DataFrame, name: Optional[str] = None, **kwargs
    ) -> Optional["BacktraderPandasData"]:
        """创建 Backtrader 数据源"""
        feed = self.data_bridge.create_backtrader_feed(dataframe, **kwargs)
        if feed is not None and name:
            feed._name = name
        return feed

    def get_data_sync(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        timeframe: str = "1d",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """同步获取数据，兼容 Backtrader 引擎调用"""
        return self._run_sync(self.get_data(symbol, start_date, end_date, timeframe, adjust))  # type: ignore[no-any-return]

    async def get_multi_data(
        self,
        symbols: List[str],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        timeframe: str = "1d",
        adjust: str = "qfq",
    ) -> Dict[str, pd.DataFrame]:
        """批量获取多支股票数据"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"批量获取 {len(symbols)} 支股票数据")

        tasks = [
            self.get_data(symbol, start_date, end_date, timeframe, adjust) for symbol in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        data_dict: Dict[str, pd.DataFrame] = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"获取 {symbol} 失败: {result}")
                data_dict[symbol] = pd.DataFrame()
            else:
                data_dict[symbol] = self._ensure_dataframe(result)

        success_count = sum(1 for df in data_dict.values() if not df.empty)
        logger.info(f"成功获取 {success_count}/{len(symbols)} 支股票数据")

        return data_dict

    def validate_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """验证数据完整性"""
        validation_result: Dict[str, Any] = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        if df.empty:
            validation_result["is_valid"] = False
            validation_result["errors"].append("数据为空")
            return validation_result

        required_fields = ["open", "high", "low", "close"]
        missing_fields = [f for f in required_fields if f not in df.columns]
        if missing_fields:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"缺少必要字段: {missing_fields}")

        if all(f in df.columns for f in required_fields):
            invalid_high = df["high"] < df[["open", "close"]].max(axis=1)
            if invalid_high.any():
                validation_result["warnings"].append(
                    f"存在 {invalid_high.sum()} 条 high 值异常记录"
                )

            invalid_low = df["low"] > df[["open", "close"]].min(axis=1)
            if invalid_low.any():
                validation_result["warnings"].append(f"存在 {invalid_low.sum()} 条 low 值异常记录")

        # 安全获取日期范围，处理边界情况
        try:
            date_range = f"{df.index[0]} to {df.index[-1]}" if len(df) > 0 else "N/A"
        except IndexError, KeyError:
            date_range = "N/A"

        validation_result["stats"] = {
            "rows": len(df),
            "columns": list(df.columns),
            "date_range": date_range,
            "null_values": df.isnull().sum().to_dict(),
        }

        return validation_result

    def clear_cache(self) -> None:
        """清理缓存"""
        self._cache.clear()
        if self.data_manager and hasattr(self.data_manager, "clear_cache"):
            self.data_manager.clear_cache()
        logger.info("缓存已清理")

    def get_diagnostics(self) -> Dict[str, Any]:
        """获取适配器诊断信息"""
        return {
            "initialized": self._initialized,
            "source": self.source,
            "cache_size": len(self._cache),
            "cached_symbols": list({key.split("_")[0] for key in self._cache.keys()}),
            "bridge_diagnostics": self.data_bridge.get_diagnostics(),
            "manager_status": (
                self.data_manager.get_status()
                if self.data_manager and hasattr(self.data_manager, "get_status")
                else None
            ),
        }


async def create_adapter(source: str = "auto") -> UnifiedBacktraderAdapter:
    """
    创建并初始化适配器

    Args:
        source: 数据源选择

    Returns:
        初始化后的适配器
    """
    adapter = UnifiedBacktraderAdapter(source)
    await adapter.initialize()
    return adapter
