"""
图表数据 API
提供K线数据、技术指标计算等接口
"""

from __future__ import annotations

import asyncio
import gc
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from core.indicators.technical import INDICATOR_REGISTRY, TechnicalIndicators
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.exception_handlers import (
    DataProviderError,
    InvalidParameterError,
    handle_api_exceptions,
)
from apps.api.api.providers import DataProviderFactory

# from core.application.services.market.chart_service import ChartService
# from core.application.services.market.signal_detector import SignalDetector


# 临时的服务类
class ChartService:
    """轻量占位的图表服务，实现基本接口以便 mypy 校验。"""

    def __init__(
        self,
        data_provider: Any | None = None,
        indicator_calculator: Any | None = None,
        *,
        redis_url: str | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._indicator_calculator = indicator_calculator
        self._redis_url = redis_url

    async def get_series(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 200,
        adjust: str = "none",
        start_date: str | None = None,
        end_date: str | None = None,
        session_split: bool | None = None,
        provider: str | None = None,
    ) -> Dict[str, Any]:
        return {
            "meta": {"symbol": symbol, "timeframe": timeframe, "adjust": adjust},
            "bars": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "limit": limit,
        }

    async def calculate_indicators(
        self,
        *,
        symbol: str,
        timeframe: str,
        indicators: List[Dict[str, Any]],
        bars_data: Any,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators,
            "data": [],
        }

    async def calculate_chip_distribution(
        self,
        symbol: str,
        timeframe: str,
        *,
        price_bins: int = 50,
        lookback_days: int | None = None,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "price_bins": price_bins,
            "distribution": [],
        }

    async def calculate_chip_distribution_by_date(
        self,
        *,
        symbol: str,
        target_date: str,
        price_bins: int = 50,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "target_date": target_date,
            "price_bins": price_bins,
            "distribution": [],
        }

    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "snapshot": {}}

    async def get_statistics(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "statistics": {}}

    async def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "info": {}}

    async def get_stock_meta(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "meta": {}}

    async def get_stock_list(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        return {"keyword": keyword, "items": [], "total": 0}

    async def validate_data_sources(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "valid": False,
            "providers": [],
        }

    def get_indicator_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "description": getattr(indicator, "__doc__", ""),
            }
            for name, indicator in INDICATOR_REGISTRY.items()
        ]

    def get_available_providers(self) -> List[str]:
        return ["unified", "amazingdata", "akshare", "fallback"]

    def subscribe(
        self,
        symbol: str,
        timeframe: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]] | None = None,
    ) -> str:
        return f"stub-{uuid.uuid4().hex}"

    def unsubscribe(self, subscription_id: str) -> bool:
        return True


class SignalDetector:
    """占位信号检测器，返回空结果以保持接口稳定。"""

    def detect_all_signals(self, bars: Any, indicator_data: Any) -> List[Dict[str, Any]]:
        return []

    def get_signal_summary(self, *, time_window: int = 24) -> Dict[str, Any]:
        return {"time_window": time_window, "signals": 0}


router = APIRouter(prefix="/api/chart", tags=["图表数据"])

# 全局服务实例
chart_service: ChartService | None = None
signal_detector: SignalDetector | None = None
websocket_manager: Any | None = None

# 添加异步初始化锁
_init_lock: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


async def get_chart_service() -> ChartService:
    """获取图表服务实例"""
    global chart_service
    if chart_service is None:
        async with _get_init_lock():
            # Double-check pattern
            if chart_service is None:
                # 使用单例数据提供者
                try:
                    # 优先使用统一数据管理器
                    data_provider = DataProviderFactory.get_provider("unified")
                    logger.info("使用单例统一数据源管理器")
                except Exception as e:
                    logger.warning(f"获取统一管理器失败: {e}, 使用akshare提供者")
                    # 降级使用akshare单例
                    data_provider = DataProviderFactory.get_provider("akshare")
                    logger.info("使用单例akshare提供者")

                indicator_calculator = TechnicalIndicators()

                # 尝试连接Redis（如果配置了）
                import os

                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

                # 初始化图表服务
                try:
                    chart_service = ChartService(
                        data_provider, indicator_calculator, redis_url=redis_url
                    )
                    logger.info(f"图表服务已初始化，Redis: {redis_url}")
                except Exception as e:
                    logger.warning(f"初始化图表服务失败，使用本地缓存: {e}")
                    chart_service = ChartService(data_provider, indicator_calculator)
    return chart_service


def get_signal_detector() -> SignalDetector:
    """获取信号检测器实例"""
    global signal_detector
    if signal_detector is None:
        signal_detector = SignalDetector()
    return signal_detector


class IndicatorConfig(BaseModel):
    """指标配置"""

    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    pane: Optional[str] = None  # main, sub1, sub2, sub3


class IndicatorsRequest(BaseModel):
    """指标计算请求"""

    symbol: str
    timeframe: str = "1d"
    adjust: str = "none"
    indicators: List[IndicatorConfig] = Field(default_factory=list)


class SeriesResponse(BaseModel):
    """K线序列响应"""

    meta: Dict[str, Any]
    bars: List[Dict[str, Any]]
    timestamp: str


@router.get("/series", response_model=SeriesResponse)
@handle_api_exceptions
async def get_series(
    symbol: str = Query(..., description="股票代码"),
    timeframe: str = Query("1d", description="时间周期: 1m, 3m, 5m, 15m, 30m, 60m, 1d, 1w, 1mo"),
    start: Optional[str] = Query(None, description="开始日期"),
    end: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(500, description="数据条数", ge=1, le=5000),
    adjust: str = Query("none", description="复权方式: none, qfq, hfq"),
    session_split: bool = Query(True, description="是否分割交易时段"),
    provider: Optional[str] = Query(None, description="数据提供者: default, miniqmt, akshare等"),
):
    """
    获取K线数据序列

    - **symbol**: 股票代码（如000001）
    - **timeframe**: 时间周期
    - **start**: 开始日期（YYYY-MM-DD）
    - **end**: 结束日期（YYYY-MM-DD）
    - **limit**: 返回数据条数
    - **adjust**: 复权方式（none=不复权, qfq=前复权, hfq=后复权）
    - **session_split**: 是否分割交易时段（用于VWAP计算）
    """
    # 参数验证
    if not symbol:
        raise InvalidParameterError("股票代码不能为空")

    if timeframe not in ["1m", "3m", "5m", "15m", "30m", "60m", "1d", "1w", "1mo"]:
        raise InvalidParameterError(f"不支持的时间周期: {timeframe}")

    if adjust not in ["none", "qfq", "hfq"]:
        raise InvalidParameterError(f"不支持的复权方式: {adjust}")

    service = await get_chart_service()
    if not service:
        raise DataProviderError("图表服务未初始化")

    data = await service.get_series(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start,
        end_date=end,
        limit=limit,
        adjust=adjust,
        session_split=session_split,
        provider=provider,
    )

    if not data:
        raise DataProviderError(f"无法获取股票 {symbol} 的K线数据")

    return data


@router.post("/indicators")
async def calculate_indicators(request: IndicatorsRequest):
    """
    计算技术指标

    请求体示例：
    ```json
    {
        "symbol": "000001",
        "timeframe": "1d",
        "indicators": [
            {"name": "MA", "params": {"periods": [5, 10, 20]}, "pane": "main"},
            {"name": "MACD", "params": {}, "pane": "sub1"},
            {"name": "RSI", "params": {"period": 14}, "pane": "sub2"}
        ]
    }
    ```
    """
    try:
        service = await get_chart_service()

        # 获取K线数据
        series_data = await service.get_series(
            symbol=request.symbol, timeframe=request.timeframe, adjust=request.adjust
        )

        if not series_data.get("bars"):
            raise HTTPException(status_code=404, detail="没有找到数据")

        # 准备指标配置
        indicators = []
        for config in request.indicators:
            # 如果没有指定pane，从注册表获取默认值
            if not config.pane and config.name.upper() in INDICATOR_REGISTRY:
                config.pane = INDICATOR_REGISTRY[config.name.upper()].get("pane", "sub")

            indicators.append(
                {"name": config.name, "params": config.params or {}, "pane": config.pane or "sub"}
            )

        # 计算指标
        import pandas as pd

        bars_df = pd.DataFrame(series_data["bars"])

        try:
            results = await service.calculate_indicators(
                symbol=request.symbol,
                timeframe=request.timeframe,
                indicators=indicators,
                bars_data=bars_df,
            )
            return results
        finally:
            # 显式释放 DataFrame 内存
            del bars_df
            gc.collect()

    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicator-list")
async def get_indicator_list():
    """
    获取可用指标列表

    返回所有支持的技术指标及其配置参数
    """
    try:
        service = await get_chart_service()
        indicators = service.get_indicator_list()

        # 补充从注册表获取的信息
        for name, config in INDICATOR_REGISTRY.items():
            # 查找是否已在列表中
            found = False
            for indicator in indicators:
                if indicator["name"] == name:
                    found = True
                    # 更新信息
                    indicator.update({"func": config.get("func"), "doc": config.get("doc", "")})
                    break

            # 如果不在列表中，添加
            if not found:
                indicators.append(
                    {
                        "name": name,
                        "label": config.get("label", name),
                        "category": config.get("category", "other"),
                        "pane": config.get("pane", "sub"),
                        "params": config.get("params", {}),
                        "func": config.get("func"),
                        "doc": config.get("doc", ""),
                    }
                )

        return indicators

    except Exception as e:
        logger.error(f"获取指标列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snap")
async def get_snapshot(symbol: str = Query(..., description="股票代码")):
    """
    获取实时快照数据

    返回股票的实时行情快照，包括价格、涨跌幅、成交量等
    """
    try:
        service = await get_chart_service()
        data = await service.get_snapshot(symbol)
        return data
    except Exception as e:
        logger.error(f"获取快照数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/{symbol}")
async def validate_data_sources(symbol: str, timeframe: str = Query("1d", description="时间周期")):
    """
    验证多个数据源的数据一致性

    返回各数据源的数据和差异分析
    """
    try:
        service = await get_chart_service()
        result = await service.validate_data_sources(symbol, timeframe)
        return result
    except Exception as e:
        logger.error(f"数据验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def get_available_providers():
    """
    获取可用的数据提供者列表

    返回所有配置的数据源及其状态
    """
    try:
        service = await get_chart_service()
        providers = service.get_available_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"获取数据提供者列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta/{symbol}")
async def get_stock_meta(symbol: str):
    """
    获取股票元数据

    返回股票的上市日期、数据范围、缓存状态等元信息
    """
    try:
        service = await get_chart_service()
        meta = await service.get_stock_meta(symbol)
        return meta
    except Exception as e:
        logger.error(f"获取股票元数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-info")
async def get_stock_info(symbol: str = Query(..., description="股票代码")):
    """
    获取股票基础信息

    返回股票的基本信息，包括名称、所属板块、市值、市盈率等
    """
    try:
        service = await get_chart_service()
        data = await service.get_stock_info(symbol)
        return data
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        # 如果服务失败，返回基础信息
        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "sector": "未知",
            "market_cap": "未知",
            "pe_ratio": 0,
            "error": str(e),
        }


@router.get("/stock-list")
async def get_stock_list(keyword: Optional[str] = Query(None, description="搜索关键字")):
    """
    获取股票列表

    支持通过代码或名称搜索股票
    """
    try:
        service = await get_chart_service()
        data = await service.get_stock_list(keyword)
        return data
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        # 如果服务失败，返回模拟数据
        mock_stocks = [
            {"code": "000001", "name": "平安银行", "label": "平安银行 (000001)", "value": "000001"},
            {"code": "000002", "name": "万科A", "label": "万科A (000002)", "value": "000002"},
            {"code": "000858", "name": "五粮液", "label": "五粮液 (000858)", "value": "000858"},
            {"code": "002415", "name": "海康威视", "label": "海康威视 (002415)", "value": "002415"},
            {"code": "300750", "name": "宁德时代", "label": "宁德时代 (300750)", "value": "300750"},
            {"code": "600000", "name": "浦发银行", "label": "浦发银行 (600000)", "value": "600000"},
            {"code": "600036", "name": "招商银行", "label": "招商银行 (600036)", "value": "600036"},
            {"code": "600519", "name": "贵州茅台", "label": "贵州茅台 (600519)", "value": "600519"},
            {"code": "601318", "name": "中国平安", "label": "中国平安 (601318)", "value": "601318"},
            {"code": "601606", "name": "长城军工", "label": "长城军工 (601606)", "value": "601606"},
        ]

        if keyword:
            keyword_lower = keyword.lower()
            filtered = [
                s
                for s in mock_stocks
                if keyword_lower in s["code"].lower() or keyword_lower in s["name"].lower()
            ]
            return filtered

        return mock_stocks


@router.get("/chip-distribution")
async def get_chip_distribution(
    symbol: str = Query(..., description="股票代码"),
    lookback_days: int = Query(120, description="回看天数"),
    price_bins: int = Query(100, description="价格分档数"),
    target_date: Optional[str] = Query(None, description="指定日期 (YYYY-MM-DD)"),
):
    """
    获取筹码分布数据

    返回股票的筹码分布、成本分布和支撑阻力位等信息
    支持指定日期的筹码分布计算
    """
    try:
        service = await get_chart_service()

        # 如果指定了日期，获取该日期的筹码分布
        if target_date:
            data = await service.calculate_chip_distribution_by_date(
                symbol=symbol, target_date=target_date, price_bins=price_bins
            )
        else:
            data = await service.calculate_chip_distribution(
                symbol=symbol,
                timeframe="1d",  # 筹码分布使用日线数据
                lookback_days=lookback_days,
                price_bins=price_bins,
            )
        return data
    except Exception as e:
        logger.error(f"获取筹码分布失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_signals(
    symbol: str = Query(..., description="股票代码"),
    timeframe: str = Query("1d", description="时间周期"),
):
    """
    获取智能信号检测结果

    包括金叉死叉、背离、K线形态等信号
    """
    df = None
    indicator_data = None
    try:
        service = await get_chart_service()
        detector = get_signal_detector()

        # 获取K线数据
        series_data = await service.get_series(symbol, timeframe, limit=100)

        if not series_data.get("bars"):
            return {"signals": {}, "summary": {}}

        import pandas as pd

        df = pd.DataFrame(series_data["bars"])

        # 计算常用指标
        indicators_config = [
            {"name": "MA", "params": {"periods": [5, 10, 20]}},
            {"name": "MACD", "params": {}},
            {"name": "RSI", "params": {}},
        ]

        indicator_results = await service.calculate_indicators(
            symbol=symbol, timeframe=timeframe, indicators=indicators_config, bars_data=df
        )

        # 提取指标数据
        indicator_data = {}
        for name, result in indicator_results.items():
            if "series" in result:
                for key, values in result["series"].items():
                    indicator_data[key] = pd.Series(values)

        # 检测所有信号
        signals = detector.detect_all_signals(df, indicator_data)

        # 获取信号摘要
        summary = detector.get_signal_summary(time_window=24)

        return {"signals": signals, "summary": summary, "timestamp": series_data.get("timestamp")}

    except Exception as e:
        logger.error(f"获取信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 显式释放 DataFrame 和 Series 内存
        if df is not None:
            del df
        if indicator_data is not None:
            indicator_data.clear()
            del indicator_data
        gc.collect()


@router.get("/stats")
async def get_chart_stats():
    """
    获取图表服务统计信息

    包括请求数、缓存命中率、活跃订阅数等
    """
    try:
        service = await get_chart_service()
        stats = await service.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def websocket_chart(websocket: WebSocket):
    """
    图表数据 WebSocket 端点

    支持实时K线数据推送和指标更新

    消息格式：
    订阅：{"action": "subscribe", "symbol": "000001", "timeframe": "1m"}
    取消订阅：{"action": "unsubscribe", "subscription_id": "xxx"}
    ping：{"action": "ping"}
    """
    await websocket.accept()
    service = await get_chart_service()
    subscriptions = {}

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")

            if action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif action == "subscribe":
                symbol = message.get("symbol")
                timeframe = message.get("timeframe", "1m")

                if not symbol:
                    await websocket.send_json({"type": "error", "message": "Symbol is required"})
                    continue

                # 定义回调函数
                async def send_update(data):
                    await websocket.send_json(data)

                # 订阅数据
                subscription_id = service.subscribe(
                    symbol=symbol, timeframe=timeframe, callback=send_update
                )

                subscriptions[subscription_id] = {"symbol": symbol, "timeframe": timeframe}

                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "subscription_id": subscription_id,
                        "symbol": symbol,
                        "timeframe": timeframe,
                    }
                )

                logger.info(f"WebSocket订阅: {symbol} {timeframe}")

            elif action == "unsubscribe":
                subscription_id = message.get("subscription_id")

                if subscription_id and subscription_id in subscriptions:
                    service.unsubscribe(subscription_id)
                    del subscriptions[subscription_id]

                    await websocket.send_json(
                        {"type": "unsubscribed", "subscription_id": subscription_id}
                    )

                    logger.info(f"WebSocket取消订阅: {subscription_id}")

            elif action == "get_indicators":
                # 实时计算指标
                symbol = message.get("symbol")
                timeframe = message.get("timeframe", "1d")
                indicators = message.get("indicators", [])

                if symbol and indicators:
                    try:
                        # 获取数据并计算指标
                        series_data = await service.get_series(symbol, timeframe, limit=100)

                        if series_data.get("bars"):
                            import pandas as pd

                            bars_df = pd.DataFrame(series_data["bars"])

                            results = await service.calculate_indicators(
                                symbol=symbol,
                                timeframe=timeframe,
                                indicators=indicators,
                                bars_data=bars_df,
                            )

                            await websocket.send_json(
                                {
                                    "type": "indicators",
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "data": results,
                                }
                            )
                    except Exception as e:
                        await websocket.send_json(
                            {"type": "error", "message": f"计算指标失败: {str(e)}"}
                        )

    except WebSocketDisconnect:
        # 清理订阅
        for subscription_id in subscriptions:
            service.unsubscribe(subscription_id)
        logger.info(f"WebSocket断开连接，清理了 {len(subscriptions)} 个订阅")

    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        # 清理订阅
        for subscription_id in subscriptions:
            try:
                service.unsubscribe(subscription_id)
            except Exception as exc:
                logger.opt(exception=exc).debug("取消行情订阅时忽略异常")


@router.post("/subscribe")
async def subscribe_data(
    symbol: str = Query(..., description="股票代码"),
    timeframe: str = Query("1m", description="时间周期"),
):
    """
    订阅实时数据（用于测试）

    返回订阅ID，可用于后续取消订阅
    """
    try:
        service = await get_chart_service()
        subscription_id = service.subscribe(symbol, timeframe)

        return {
            "success": True,
            "subscription_id": subscription_id,
            "symbol": symbol,
            "timeframe": timeframe,
        }
    except Exception as e:
        logger.error(f"订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscribe/{subscription_id}")
async def unsubscribe_data(subscription_id: str):
    """
    取消订阅
    """
    try:
        service = await get_chart_service()
        success = service.unsubscribe(subscription_id)

        if success:
            return {"success": True, "message": "取消订阅成功"}
        else:
            raise HTTPException(status_code=404, detail="订阅不存在")

    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
