"""
AkShare 数据提供者适配器

为不同的AkShare实现（Direct和Proxy）提供统一的接口
"""

from collections.abc import Mapping
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

import pandas as pd
from core.infrastructure.providers.interfaces.base import DataProvider as IAkShareProvider
from core.infrastructure.providers.interfaces.base import DataProviderError, DataRequest
from core.utils.timeout import DataSourceState, get_timeout_manager
from loguru import logger

from .akshare_api_mapping import AkShareAPIMapping
from .akshare_direct import AKShareDirectProvider

# 数据源名称常量
_SOURCE_NAME = "akshare"

_STOCK_SYMBOL_FIELDS: tuple[str, ...] = (
    "symbol",
    "code",
    "CODE",
    "SECURITY_CODE",
    "SECURITY_ID",
    "MARKET_CODE",
    "股票代码",
    "证券代码",
    "代码",
    "����",
)
_STOCK_NAME_FIELDS: tuple[str, ...] = (
    "name",
    "NAME",
    "sec_name",
    "SEC_NAME_A",
    "SECURITY_NAME",
    "证券简称",
    "股票简称",
    "名称",
    "����",
)
_STOCK_BOARD_FIELDS: tuple[str, ...] = (
    "board",
    "board_name",
    "LISTPLATE_NAME",
    "所属板块",
    "板块",
    "所属概念",
    "����",
)
_STOCK_EXCHANGE_FIELDS: tuple[str, ...] = (
    "exchange",
    "market",
    "market_code",
    "MARKET",
    "MARKET_CAT",
    "交易所",
    "交易市场",
)


class AkShareAdapter(IAkShareProvider):
    """
    AkShare 适配器

    注意：AkShareProxyProvider 已废弃（与 AKShareDirectProvider 是同一个类），
    因此不再使用 primary/fallback 切换机制。内部 fallback 由 AKShareDirectProvider
    自行处理（stock_zh_a_spot_em -> stock_info_a_code_name）。
    """

    def __init__(self, use_proxy: bool = False):
        """
        初始化适配器

        Args:
            use_proxy: 已废弃参数，保留仅为向后兼容
        """
        if use_proxy:
            logger.warning(
                "use_proxy=True 已废弃: AkShareProxyProvider 现在与 AKShareDirectProvider 相同"
            )
        self.use_proxy = use_proxy
        self.provider: AKShareDirectProvider | None = None

    async def initialize(self):
        """初始化提供者"""
        # 统一使用 AKShareDirectProvider，它内部有 API fallback 机制
        self.provider = AKShareDirectProvider()
        if self.use_proxy:
            logger.info("使用 AkShare 代理模式（已废弃，建议切换为直连）")
        else:
            logger.info("使用 AkShare 直连模式（内置 API fallback）")

        if hasattr(self.provider, "initialize"):
            await self.provider.initialize()

    def _require_provider(self) -> IAkShareProvider:
        if self.provider is None:
            raise DataProviderError("AkShare provider not initialized. Call initialize() first.")
        return self.provider  # type: ignore[return-value]

    @staticmethod
    def _extract_data_list(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        data = result.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    @staticmethod
    def _normalize_row(row: Mapping[Any, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {str(key): value for key, value in row.items()}

        def _pick(fields: tuple[str, ...]) -> Any:
            for field in fields:
                value = normalized.get(field)
                if value not in (None, ""):
                    return value
            return None

        symbol = _pick(_STOCK_SYMBOL_FIELDS)
        if symbol:
            normalized_symbol = str(symbol).strip().upper()
            if "." in normalized_symbol:
                normalized_symbol = normalized_symbol.split(".", 1)[0]
            if normalized_symbol.isdigit():
                normalized_symbol = normalized_symbol.zfill(6)
            normalized["symbol"] = normalized_symbol
            normalized.setdefault("code", normalized_symbol)

        name = _pick(_STOCK_NAME_FIELDS)
        if name:
            normalized["name"] = str(name).strip()
        elif symbol:
            normalized["name"] = normalized.get("symbol", "")

        board_value = _pick(_STOCK_BOARD_FIELDS)
        if board_value is not None and "board" not in normalized:
            normalized["board"] = board_value

        exchange_value = _pick(_STOCK_EXCHANGE_FIELDS)
        if exchange_value is not None and "exchange" not in normalized:
            normalized["exchange"] = str(exchange_value).strip().upper()

        return normalized

    async def get_stock_list(
        self,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票列表

        内部 fallback 机制由 AKShareDirectProvider 处理：
        1. 先尝试 stock_zh_a_spot_em（东方财富实时行情）
        2. 失败后尝试 stock_info_a_code_name（代码名称映射）
        """
        timeout_manager = get_timeout_manager()

        # 设置批量获取状态（股票列表通常有 500+ 条数据）
        with timeout_manager.operation(
            _SOURCE_NAME,
            DataSourceState.BATCH_FETCHING,
            "get_stock_list",
        ):
            try:
                if self.provider is None:
                    logger.error("AkShare provider 未初始化")
                    return None

                fetcher = getattr(self.provider, "get_stock_list", None)
                if not callable(fetcher):
                    logger.error("AkShare provider 没有 get_stock_list 方法")
                    return None

                result = await fetcher(limit=limit, **kwargs)
                if result:
                    return list(result) if not limit else list(result)[:limit]

                logger.warning("AkShare get_stock_list 返回空结果")
                return None

            except Exception as exc:
                logger.error(f"AkShare get_stock_list 失败: {exc}")
                return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """封装 DataProvider 兼容的 K 线数据接口."""

        async def _call_provider(
            provider_obj: IAkShareProvider | None,
        ) -> Optional[List[Dict[str, Any]]]:
            if provider_obj is None:
                return None
            fetcher = getattr(provider_obj, "get_kline_data", None)
            if not callable(fetcher):
                return None
            result = await fetcher(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                **kwargs,
            )
            if result is None:
                return None
            return list(result)

        try:
            result = await _call_provider(self.provider)  # type: ignore[arg-type]
            if result:
                return result
        except Exception as exc:
            logger.warning(f"AkShare get_kline_data failed: {exc}")

        hist = await self.get_stock_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=kwargs.get("adjust", ""),
        )
        rows = self._extract_hist_rows(hist)
        if not rows:
            return None
        if limit and limit > 0:
            rows = rows[-limit:]
        return rows

    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        provider = cast(Any, self._require_provider())
        try:
            result = await provider.get_realtime_quote(symbol)
            if isinstance(result, dict) and not result.get("error"):
                return cast(Dict[str, Any], result)
        except Exception as e:
            logger.warning(f"获取 {symbol} 实时行情失败: {e}")

        return {"error": "数据源获取失败"}

    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """批量获取实时行情"""
        provider = cast(Any, self._require_provider())
        try:
            if hasattr(provider, "get_realtime_quotes"):
                result = await provider.get_realtime_quotes(symbols)
                if result:
                    return list(result)
        except Exception as e:
            logger.warning(f"批量获取实时行情失败: {e}")

        # 批量接口不可用，回退到逐个获取
        results = []
        for symbol in symbols:
            quote = await self.get_realtime_quote(symbol)
            if quote and not quote.get("error"):
                results.append(quote)

        return results

    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
    ) -> Dict[str, Any]:
        """获取历史K线数据"""
        provider = cast(Any, self._require_provider())
        try:
            result = await provider.get_stock_hist(symbol, period, start_date, end_date, adjust)
            if isinstance(result, dict) and not result.get("error"):
                return cast(Dict[str, Any], result)
        except Exception as e:
            logger.warning(f"获取 {symbol} 历史数据失败: {e}")

        return {"data": [], "error": "数据源获取失败"}

    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表"""
        timeout_manager = get_timeout_manager()

        # 设置批量获取状态
        with timeout_manager.operation(
            _SOURCE_NAME,
            DataSourceState.BATCH_FETCHING,
            "fetch_stock_list",
        ):
            provider = cast(Any, self._require_provider())
            try:
                result = await provider.fetch_stock_list()
                normalized = self._normalize_stock_list(result)
                if normalized:
                    return normalized
            except Exception as e:
                logger.warning(f"获取股票列表失败: {e}")

        # 数据源获取失败，返回空列表（禁止返回 mock 数据）
        logger.error("AkShare 获取股票列表失败，返回空列表")
        return []

    async def get_trading_calendar(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[List[str]]:
        """获取交易日历

        Args:
            start_date: 开始日期 (格式: YYYYMMDD)
            end_date: 结束日期 (格式: YYYYMMDD)

        Returns:
            交易日期列表 (格式: YYYYMMDD)，失败返回 None
        """
        timeout_manager = get_timeout_manager()

        with timeout_manager.operation(
            _SOURCE_NAME,
            DataSourceState.FETCHING,
            "get_trading_calendar",
        ):
            provider = cast(Any, self._require_provider())
            try:
                result = await provider.get_trading_calendar(
                    start_date=start_date, end_date=end_date
                )
                if result:
                    return result
            except Exception as e:
                logger.error(f"AkShare 获取交易日历失败: {e}")

        return None

    async def get_calendar(self, market: str = "A") -> Optional[List[int]]:
        """获取交易日历（标准协议方法）

        与 get_trading_calendar 相同，但返回 YYYYMMDD 整数列表，
        兼容 CapabilityRouter 的 TRADING_CALENDAR 能力接口。

        Returns:
            交易日期整数列表，失败返回 None
        """
        dates = await self.get_trading_calendar()
        if dates is None:
            return None
        result = []
        for d in dates:
            try:
                result.append(int(d))
            except (ValueError, TypeError):
                continue
        return result if result else None

    async def get_realtime_data(self, symbols: List[str]) -> Dict[str, Any]:
        """兼容管理器调用：批量获取实时行情，返回 {symbol: payload} 结构"""
        # 尝试使用批量接口
        try:
            quotes_list = await self.get_realtime_quotes(symbols)
            if quotes_list:
                result: Dict[str, Any] = {}
                for quote in quotes_list:
                    symbol = quote.get("symbol") or quote.get("code")
                    if symbol:
                        result[str(symbol)] = quote

                # 确保所有请求的symbol都有返回
                for sym in symbols:
                    if str(sym) not in result:
                        result[str(sym)] = {"error": "Not found", "symbol": sym}

                return result
        except Exception as e:
            logger.warning(f"批量获取失败，降级到循环获取: {e}")

        fallback_result: Dict[str, Any] = {}
        for sym in symbols:
            try:
                payload = await self.get_realtime_quote(sym)
                fallback_result[str(sym)] = payload
            except Exception as e:
                logger.error(f"获取 {sym} 实时行情失败: {e}")
                fallback_result[str(sym)] = {"error": str(e)}
        return fallback_result

    async def get_history_data(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
    ) -> pd.DataFrame:
        """兼容管理器调用：获取历史K线，返回 DataFrame"""
        try:
            data = await self.get_stock_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            if isinstance(data, dict):
                rows = data.get("data") if isinstance(data.get("data"), list) else None
                if rows:
                    return pd.DataFrame(rows)
            elif isinstance(data, pd.DataFrame):
                return data
        except Exception as e:
            logger.error(f"get_history_data 失败: {e}")
        return pd.DataFrame()

    async def start(self) -> None:
        """启动数据源"""
        await self._start_source()

    async def stop(self) -> None:
        """停止数据源"""
        await self._stop_source()

    async def health_check(self):
        """健康检查，委托给底层 provider"""
        if self.provider and hasattr(self.provider, "health_check"):
            return await self.provider.health_check()

        from core.infrastructure.providers.protocols.lifecycle import (
            HealthCheckResult,
            HealthStatus,
        )

        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            message="AkShare provider 未初始化",
        )

    def is_connected(self) -> bool:
        """检查连接状态"""
        if self.provider and hasattr(self.provider, "is_connected"):
            return self.provider.is_connected()
        return False

    async def fetch_with_api(
        self, api_name: str, params: Dict[str, Any], max_retries: int = 3
    ) -> Dict[str, Any]:
        """统一的 AkShare API 调用入口"""
        safe_params = dict(params or {})

        api_info = AkShareAPIMapping.get_api_info(api_name)
        if api_info:
            safe_params = AkShareAPIMapping.transform_params(api_name, safe_params)

        # 直接调用主 provider
        return await self._call_provider_api(
            self.provider, api_name, dict(safe_params), max_retries=max_retries
        )

    async def _call_provider_api(
        self,
        provider,
        api_name: str,
        params: Dict[str, Any],
        *,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Execute one AkShare API call against a provider"""
        if not provider:
            return {"success": False, "error": "provider unavailable", "data": []}

        try:
            if hasattr(provider, "call_api"):
                raw_result = await provider.call_api(api_name, params)
            elif hasattr(provider, "_fetch_with_fallback"):
                fallback_fn = cast(
                    Callable[[str, Dict[str, Any], int], Awaitable[Any]],
                    getattr(provider, "_fetch_with_fallback"),
                )
                raw_result = await fallback_fn(api_name, params, max_retries)
            else:
                return {"success": False, "error": "provider missing call_api", "data": []}
        except Exception as exc:
            logger.error(f"AkShare provider call failed for {api_name}: {exc}")
            return {"success": False, "error": str(exc), "data": []}

        return self._normalize_api_result(raw_result)

    @staticmethod
    def _normalize_api_result(result: Any) -> Dict[str, Any]:
        """Normalize provider responses into a consistent structure"""
        if result is None:
            return {"success": False, "error": "empty response", "data": []}

        if isinstance(result, dict):
            if result.get("success") is False:
                return {
                    "success": False,
                    "error": result.get("error", "unknown error"),
                    "data": result.get("data", []),
                }

            error_message = result.get("error")
            if error_message and result.get("success") is not True:
                return {"success": False, "error": error_message, "data": result.get("data", [])}

            if "success" in result or "data" in result or "error" in result:
                normalized = dict(result)
                normalized.setdefault("success", True)
                normalized.setdefault("data", [])
                return normalized

            return {"success": True, "data": result}

        if isinstance(result, list):
            return {"success": True, "data": result}

        return {"success": True, "data": result}

    @staticmethod
    def _normalize_stock_list(result: Any) -> List[Dict[str, str]]:
        """将不同来源的股票列表统一转换为字典列表"""

        def _normalize_rows(rows: list[Any]) -> List[Dict[str, str]]:
            normalized_rows: List[Dict[str, str]] = []
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                normalized = AkShareAdapter._normalize_row(cast(Mapping[str, Any], row))
                # StockListRecord.from_payload 依赖 symbol/code 字段，缺失时应直接丢弃。
                if not normalized.get("symbol"):
                    continue
                normalized_rows.append(cast(Dict[str, str], normalized))
            return normalized_rows

        if result is None:
            return []
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return []
            return _normalize_rows(cast(list[Any], result.to_dict(orient="records")))
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, pd.DataFrame):
                if data.empty:
                    return []
                return _normalize_rows(cast(list[Any], data.to_dict(orient="records")))
            if isinstance(data, list):
                return _normalize_rows(data)
        if isinstance(result, list):
            return _normalize_rows(result)
        return []

    @staticmethod
    def _extract_hist_rows(result: Any) -> List[Dict[str, Any]]:
        """提取历史数据记录并转换为统一结构"""
        if result is None:
            return []
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return []
            return [
                AkShareAdapter._normalize_row(cast(Mapping[str, Any], row))
                for row in result.to_dict(orient="records")
                if isinstance(row, dict)
            ]
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, pd.DataFrame):
                if data.empty:
                    return []
                return [
                    AkShareAdapter._normalize_row(cast(Mapping[str, Any], row))
                    for row in data.to_dict(orient="records")
                    if isinstance(row, dict)
                ]
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        return []

    async def fetch_market_overview(self) -> Dict[str, Any]:
        """获取市场概览"""
        # 使用通用API接口
        return await self.fetch_with_api("stock_zh_index_spot_em", {"symbol": "上证系列指数"})

    async def fetch_sector_data(self) -> List[Dict[str, Any]]:
        """获取板块数据"""
        # 使用通用API接口
        result = await self.fetch_with_api("stock_board_industry_name_em", {})
        if result.get("success"):
            return self._extract_data_list(result)
        return []

    # 实现抽象基类的必需方法
    async def _initialize_source(self) -> None:
        """初始化数据源特定配置"""
        await self.initialize()

    async def _start_source(self) -> None:
        """启动数据源特定服务"""
        if self.provider:
            if hasattr(self.provider, "start"):
                await self.provider.start()
            logger.info("AkShare数据源已启动")

    async def _stop_source(self) -> None:
        """停止数据源特定服务"""
        if self.provider:
            if hasattr(self.provider, "stop"):
                await self.provider.stop()
            logger.info("AkShare数据源已停止")

    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的具体实现

        Args:
            request: 数据请求参数

        Returns:
            处理后的数据 DataFrame
        """
        try:
            if request.symbol:
                result = await self.get_stock_hist(
                    symbol=request.symbol,
                    period=request.period or "daily",
                    start_date=str(request.start_date) if request.start_date else None,
                    end_date=str(request.end_date) if request.end_date else None,
                    adjust=request.adjust or "",
                )

                rows = self._extract_hist_rows(result)
                if rows:
                    df = pd.DataFrame(rows)
                    if not df.empty and "日期" in df.columns:
                        df["date"] = pd.to_datetime(df["日期"])
                        df = df.set_index("date")
                    return df

            elif request.symbols:
                frames = []
                for symbol in request.symbols:
                    result = await self.get_stock_hist(
                        symbol=symbol,
                        period=request.period or "daily",
                        start_date=str(request.start_date) if request.start_date else None,
                        end_date=str(request.end_date) if request.end_date else None,
                        adjust=request.adjust or "",
                    )

                    rows = self._extract_hist_rows(result)
                    if rows:
                        df = pd.DataFrame(rows)
                        df["symbol"] = symbol
                        frames.append(df)

                if frames:
                    combined = pd.concat(frames, ignore_index=True)
                    if "日期" in combined.columns:
                        combined["date"] = pd.to_datetime(combined["日期"])
                    return combined

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return pd.DataFrame()
