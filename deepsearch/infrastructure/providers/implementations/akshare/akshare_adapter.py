"""
AkShare 数据提供者适配器

为不同的AkShare实现（Direct和Proxy）提供统一的接口
"""

from collections.abc import Mapping
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

import pandas as pd
from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider as IAkShareProvider,
    DataProviderError,
    DataRequest,
)
from .akshare import AkShareProxyProvider
from .akshare_api_mapping import AkShareAPIMapping
from .akshare_direct import AKShareDirectProvider

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
    AkShare适配器 - 统一Direct和Proxy两种实现

    可以根据配置或运行时条件选择使用直连还是代理模式
    """

    def __init__(self, use_proxy: bool = False):
        """
        初始化适配器

        Args:
            use_proxy: 是否使用代理模式
        """
        self.use_proxy = use_proxy
        self.provider = None
        self.fallback_provider = None

    async def initialize(self):
        """初始化提供者"""
        if self.use_proxy:
            # 主用代理，备用直连
            self.provider = AkShareProxyProvider()
            self.fallback_provider = AKShareDirectProvider()
            logger.info("使用AkShare代理模式，备用直连模式")
        else:
            # 主用直连，备用代理
            self.provider = AKShareDirectProvider()
            self.fallback_provider = AkShareProxyProvider()
            logger.info("使用AkShare直连模式，备用代理模式")

        # 初始化主提供者
        if hasattr(self.provider, "initialize"):
            await self.provider.initialize()

        # 初始化备用提供者
        if hasattr(self.fallback_provider, "initialize"):
            try:
                await self.fallback_provider.initialize()
            except Exception as e:
                logger.warning(f"备用提供者初始化失败: {e}")

    def _require_provider(self) -> IAkShareProvider:
        if self.provider is None:
            raise DataProviderError("AkShare provider not initialized. Call initialize() first.")
        return self.provider

    def _require_fallback(self) -> IAkShareProvider:
        if self.fallback_provider is None:
            raise DataProviderError("AkShare fallback provider not available. Call initialize() first.")
        return self.fallback_provider
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
        """对外暴露兼容 DataProvider 的股票列表接口."""
        async def _call_provider(provider_obj: IAkShareProvider | None) -> Optional[List[Dict[str, Any]]]:
            if provider_obj is None:
                return None
            fetcher = getattr(provider_obj, "get_stock_list", None)
            if not callable(fetcher):
                return None
            return await fetcher(limit=limit, **kwargs)

        try:
            result = await _call_provider(self.provider)
            if result:
                return result if not limit else result[:limit]
        except Exception as exc:
            logger.warning(f"AkShare primary get_stock_list failed: {exc}")

        try:
            result = await _call_provider(self.fallback_provider)
            if result:
                return result if not limit else result[:limit]
        except Exception as exc:
            logger.warning(f"AkShare fallback get_stock_list failed: {exc}")

        api_result = await self.fetch_with_api("stock_info_a_code_name", {})
        stocks = self._extract_data_list(api_result)
        if not stocks:
            return None
        return stocks if not limit else stocks[:limit]

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
        async def _call_provider(provider_obj: IAkShareProvider | None) -> Optional[List[Dict[str, Any]]]:
            if provider_obj is None:
                return None
            fetcher = getattr(provider_obj, "get_kline_data", None)
            if not callable(fetcher):
                return None
            return await fetcher(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                **kwargs,
            )

        try:
            result = await _call_provider(self.provider)
            if result:
                return result
        except Exception as exc:
            logger.warning(f"AkShare primary get_kline_data failed: {exc}")

        try:
            result = await _call_provider(self.fallback_provider)
            if result:
                return result
        except Exception as exc:
            logger.warning(f"AkShare fallback get_kline_data failed: {exc}")

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
    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        provider = cast(Any, self._require_provider())
        try:
            result = await provider.get_realtime_quote(symbol)
            if isinstance(result, dict) and not result.get("error"):
                return cast(Dict[str, Any], result)
        except Exception as e:
            logger.warning(f"主数据源获取失败: {e}")

        if self.fallback_provider:
            try:
                logger.info(f"切换到备用数据源获取 {symbol} 实时行情")
                fallback = cast(Any, self._require_fallback())
                result = await fallback.get_realtime_quote(symbol)
                if isinstance(result, dict) and not result.get("error"):
                    result["fallback"] = True
                    return cast(Dict[str, Any], result)
            except Exception as e:
                logger.error(f"备用数据源也失败: {e}")

        return {"error": "所有数据源均失败"}

    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """批量获取实时行情"""
        provider = cast(Any, self._require_provider())
        try:
            # 优先尝试批量接口
            if hasattr(provider, "get_realtime_quotes"):
                result = await provider.get_realtime_quotes(symbols)
                if result:
                    return result
        except Exception as e:
            logger.warning(f"主数据源批量获取实时行情失败: {e}")

        if self.fallback_provider:
            try:
                fallback = cast(Any, self._require_fallback())
                if hasattr(fallback, "get_realtime_quotes"):
                    logger.info(f"切换到备用数据源批量获取 {len(symbols)} 只股票行情")
                    result = await fallback.get_realtime_quotes(symbols)
                    if result:
                        # 标记为fallback
                        for item in result:
                            item["fallback"] = True
                        return result
            except Exception as e:
                logger.error(f"备用数据源批量获取失败: {e}")

        # 如果批量接口不可用，回退到逐个获取
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
            logger.warning(f"主数据源获取历史数据失败: {e}")

        if self.fallback_provider:
            try:
                logger.info(f"切换到备用数据源获取 {symbol} 历史数据")
                fallback = cast(Any, self._require_fallback())
                result = await fallback.get_stock_hist(symbol, period, start_date, end_date, adjust)
                if isinstance(result, dict) and not result.get("error"):
                    result["fallback"] = True
                    return cast(Dict[str, Any], result)
            except Exception as e:
                logger.error(f"备用数据源也失败: {e}")

        return {"data": [], "error": "所有数据源均失败"}

    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表"""
        provider = cast(Any, self._require_provider())
        try:
            result = await provider.fetch_stock_list()
            normalized = self._normalize_stock_list(result)
            if normalized:
                return normalized
        except Exception as e:
            logger.warning(f"主数据源获取股票列表失败: {e}")

        if self.fallback_provider:
            try:
                logger.info("切换到备用数据源获取股票列表")
                fallback = cast(Any, self._require_fallback())
                result = await fallback.fetch_stock_list()
                normalized = self._normalize_stock_list(result)
                if normalized:
                    return normalized
            except Exception as e:
                logger.error(f"备用数据源也失败: {e}")

        # 返回默认列表
        return [
            {"symbol": "000001", "\u4ee3\u7801": "000001", "name": "\u5e73\u5b89\u94f6\u884c"},
            {"symbol": "000002", "\u4ee3\u7801": "000002", "name": "\u4e07\u79d1A"},
            {"symbol": "600000", "\u4ee3\u7801": "600000", "name": "\u6d66\u53d1\u94f6\u884c"},
            {"symbol": "600036", "\u4ee3\u7801": "600036", "name": "\u62db\u5546\u94f6\u884c"},
        ]

    async def get_realtime_data(self, symbols: List[str]) -> Dict[str, Any]:
        """兼容管理器调用：批量获取实时行情，返回 {symbol: payload} 结构"""
        # 尝试使用批量接口
        try:
            quotes_list = await self.get_realtime_quotes(symbols)
            if quotes_list:
                result = {}
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

        result: Dict[str, Any] = {}
        for sym in symbols:
            try:
                payload = await self.get_realtime_quote(sym)
                result[str(sym)] = payload
            except Exception as e:
                logger.error(f"获取 {sym} 实时行情失败: {e}")
                result[str(sym)] = {"error": str(e)}
        return result

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

    def is_connected(self) -> bool:
        """检查连接状态"""
        if self.provider and hasattr(self.provider, "is_connected"):
            return self.provider.is_connected()
        return False

    async def fetch_with_api(
        self, api_name: str, params: Dict[str, Any], max_retries: int = 3
    ) -> Dict[str, Any]:
        """Unified AkShare API entry point"""
        safe_params = dict(params or {})

        api_info = AkShareAPIMapping.get_api_info(api_name)
        if api_info:
            safe_params = AkShareAPIMapping.transform_params(api_name, safe_params)

        primary_result = await self._call_provider_api(
            self.provider, api_name, dict(safe_params), max_retries=max_retries
        )
        if primary_result.get("success"):
            return primary_result

        if self.fallback_provider:
            fallback_result = await self._call_provider_api(
                self.fallback_provider,
                api_name,
                dict(safe_params),
                max_retries=max_retries,
                mark_fallback=True,
            )
            if fallback_result.get("success"):
                return fallback_result
            return fallback_result

        return primary_result

    async def _call_provider_api(
        self,
        provider,
        api_name: str,
        params: Dict[str, Any],
        *,
        max_retries: int = 3,
        mark_fallback: bool = False,
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

        normalized = self._normalize_api_result(raw_result)
        if mark_fallback and normalized.get("success"):
            normalized["fallback"] = True
        return normalized

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

