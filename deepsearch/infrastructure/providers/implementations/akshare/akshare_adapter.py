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
        return {str(key): value for key, value in row.items()}



    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """��ȡʵʱ����"""
        provider = cast(Any, self._require_provider())
        try:
            result = await provider.get_realtime_quote(symbol)
            if isinstance(result, dict) and not result.get("error"):
                return cast(Dict[str, Any], result)
        except Exception as e:
            logger.warning(f"������Դ��ȡʧ��: {e}")

        if self.fallback_provider:
            try:
                logger.info(f"�л�����������Դ��ȡ {symbol} ʵʱ����")
                fallback = cast(Any, self._require_fallback())
                result = await fallback.get_realtime_quote(symbol)
                if isinstance(result, dict) and not result.get("error"):
                    result["fallback"] = True
                    return cast(Dict[str, Any], result)
            except Exception as e:
                logger.error(f"��������ԴҲʧ��: {e}")

        return {"error": "��������Դ��ʧ��"}

    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
    ) -> Dict[str, Any]:
        """��ȡ��ʷK������"""
        provider = cast(Any, self._require_provider())
        try:
            result = await provider.get_stock_hist(symbol, period, start_date, end_date, adjust)
            if isinstance(result, dict) and not result.get("error"):
                return cast(Dict[str, Any], result)
        except Exception as e:
            logger.warning(f"������Դ��ȡ��ʷ����ʧ��: {e}")

        if self.fallback_provider:
            try:
                logger.info(f"�л�����������Դ��ȡ {symbol} ��ʷ����")
                fallback = cast(Any, self._require_fallback())
                result = await fallback.get_stock_hist(symbol, period, start_date, end_date, adjust)
                if isinstance(result, dict) and not result.get("error"):
                    result["fallback"] = True
                    return cast(Dict[str, Any], result)
            except Exception as e:
                logger.error(f"��������ԴҲʧ��: {e}")

        return {"data": [], "error": "��������Դ��ʧ��"}

    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """��ȡ��Ʊ�б�"""
        provider = cast(Any, self._require_provider())
        try:
            result = await provider.fetch_stock_list()
            normalized = self._normalize_stock_list(result)
            if normalized:
                return normalized
        except Exception as e:
            logger.warning(f"������Դ��ȡ��Ʊ�б�ʧ��: {e}")

        if self.fallback_provider:
            try:
                logger.info("�л�����������Դ��ȡ��Ʊ�б�")
                fallback = cast(Any, self._require_fallback())
                result = await fallback.fetch_stock_list()
                normalized = self._normalize_stock_list(result)
                if normalized:
                    return normalized
            except Exception as e:
                logger.error(f"��������ԴҲʧ��: {e}")

        # ����Ĭ���б�
        return [
            {"����": "000001", "����": "ƽ������"},
            {"����": "000002", "����": "���A"},
            {"����": "600000", "����": "�ַ�����"},
            {"����": "600036", "����": "��������"},
        ]


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
                AkShareAdapter._normalize_row(row)
                for row in result.to_dict(orient="records")
                if isinstance(row, dict)
            ]
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, pd.DataFrame):
                if data.empty:
                    return []
                return [
                    AkShareAdapter._normalize_row(row)
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
                AkShareAdapter._normalize_row(row)
                for row in result.to_dict(orient="records")
                if isinstance(row, dict)
            ]
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, pd.DataFrame):
                if data.empty:
                    return []
                return [
                    AkShareAdapter._normalize_row(row)
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

