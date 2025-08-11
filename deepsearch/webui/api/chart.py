"""
图表数据 API
提供K线数据、技术指标计算等接口
"""
import json
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel

from deepsearch.data_providers.proxy_provider import ProxyDataProvider
from deepsearch.indicators.technical import TechnicalIndicators, INDICATOR_REGISTRY
from deepsearch.services.chart_service import ChartService
from deepsearch.services.signal_detector import SignalDetector

router = APIRouter(prefix="/api/chart", tags=["图表数据"])

# 全局服务实例
chart_service = None
signal_detector = None
websocket_manager = None


def get_chart_service() -> ChartService:
    """获取图表服务实例"""
    global chart_service
    if chart_service is None:
        # 初始化数据提供者和指标计算器
        data_provider = ProxyDataProvider()
        indicator_calculator = TechnicalIndicators()

        # 尝试连接Redis（如果配置了）
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # 初始化图表服务
        try:
            chart_service = ChartService(
                data_provider,
                indicator_calculator,
                redis_url=redis_url
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
    params: Optional[Dict[str, Any]] = {}
    pane: Optional[str] = None  # main, sub1, sub2, sub3


class IndicatorsRequest(BaseModel):
    """指标计算请求"""
    symbol: str
    timeframe: str = "1d"
    adjust: str = "none"
    indicators: List[IndicatorConfig]


class SeriesResponse(BaseModel):
    """K线序列响应"""
    meta: Dict[str, Any]
    bars: List[Dict[str, Any]]
    timestamp: str


@router.get("/series", response_model=SeriesResponse)
async def get_series(
        symbol: str = Query(..., description="股票代码"),
        timeframe: str = Query("1d", description="时间周期: 1m, 3m, 5m, 15m, 30m, 60m, 1d, 1w, 1mo"),
        start: Optional[str] = Query(None, description="开始日期"),
        end: Optional[str] = Query(None, description="结束日期"),
        limit: int = Query(500, description="数据条数", ge=1, le=5000),
        adjust: str = Query("none", description="复权方式: none, qfq, hfq"),
        session_split: bool = Query(True, description="是否分割交易时段")
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
    try:
        service = get_chart_service()
        data = await service.get_series(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start,
            end_date=end,
            limit=limit,
            adjust=adjust,
            session_split=session_split
        )
        return data
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        service = get_chart_service()

        # 获取K线数据
        series_data = await service.get_series(
            symbol=request.symbol,
            timeframe=request.timeframe,
            adjust=request.adjust
        )

        if not series_data.get("bars"):
            raise HTTPException(status_code=404, detail="没有找到数据")

        # 准备指标配置
        indicators = []
        for config in request.indicators:
            # 如果没有指定pane，从注册表获取默认值
            if not config.pane and config.name.upper() in INDICATOR_REGISTRY:
                config.pane = INDICATOR_REGISTRY[config.name.upper()].get("pane", "sub")

            indicators.append({
                "name": config.name,
                "params": config.params or {},
                "pane": config.pane or "sub"
            })

        # 计算指标
        import pandas as pd
        bars_df = pd.DataFrame(series_data["bars"])

        results = await service.calculate_indicators(
            symbol=request.symbol,
            timeframe=request.timeframe,
            indicators=indicators,
            bars_data=bars_df
        )

        return results

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
        service = get_chart_service()
        indicators = service.get_indicator_list()

        # 补充从注册表获取的信息
        for name, config in INDICATOR_REGISTRY.items():
            # 查找是否已在列表中
            found = False
            for indicator in indicators:
                if indicator["name"] == name:
                    found = True
                    # 更新信息
                    indicator.update({
                        "func": config.get("func"),
                        "doc": config.get("doc", "")
                    })
                    break

            # 如果不在列表中，添加
            if not found:
                indicators.append({
                    "name": name,
                    "label": config.get("label", name),
                    "category": config.get("category", "other"),
                    "pane": config.get("pane", "sub"),
                    "params": config.get("params", {}),
                    "func": config.get("func"),
                    "doc": config.get("doc", "")
                })

        return indicators

    except Exception as e:
        logger.error(f"获取指标列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snap")
async def get_snapshot(
        symbol: str = Query(..., description="股票代码")
):
    """
    获取实时快照数据
    
    返回股票的实时行情快照，包括价格、涨跌幅、成交量等
    """
    try:
        service = get_chart_service()
        data = await service.get_snapshot(symbol)
        return data
    except Exception as e:
        logger.error(f"获取快照数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_signals(
        symbol: str = Query(..., description="股票代码"),
        timeframe: str = Query("1d", description="时间周期")
):
    """
    获取智能信号检测结果
    
    包括金叉死叉、背离、K线形态等信号
    """
    try:
        service = get_chart_service()
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
            {"name": "RSI", "params": {}}
        ]

        indicator_results = await service.calculate_indicators(
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators_config,
            bars_data=df
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

        return {
            "signals": signals,
            "summary": summary,
            "timestamp": series_data.get("timestamp")
        }

    except Exception as e:
        logger.error(f"获取信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_chart_stats():
    """
    获取图表服务统计信息
    
    包括请求数、缓存命中率、活跃订阅数等
    """
    try:
        service = get_chart_service()
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
    service = get_chart_service()
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
                    await websocket.send_json({
                        "type": "error",
                        "message": "Symbol is required"
                    })
                    continue

                # 定义回调函数
                async def send_update(data):
                    await websocket.send_json(data)

                # 订阅数据
                subscription_id = service.subscribe(
                    symbol=symbol,
                    timeframe=timeframe,
                    callback=send_update
                )

                subscriptions[subscription_id] = {
                    "symbol": symbol,
                    "timeframe": timeframe
                }

                await websocket.send_json({
                    "type": "subscribed",
                    "subscription_id": subscription_id,
                    "symbol": symbol,
                    "timeframe": timeframe
                })

                logger.info(f"WebSocket订阅: {symbol} {timeframe}")

            elif action == "unsubscribe":
                subscription_id = message.get("subscription_id")

                if subscription_id and subscription_id in subscriptions:
                    service.unsubscribe(subscription_id)
                    del subscriptions[subscription_id]

                    await websocket.send_json({
                        "type": "unsubscribed",
                        "subscription_id": subscription_id
                    })

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
                                bars_data=bars_df
                            )

                            await websocket.send_json({
                                "type": "indicators",
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "data": results
                            })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"计算指标失败: {str(e)}"
                        })

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
            except:
                pass


@router.post("/subscribe")
async def subscribe_data(
        symbol: str = Query(..., description="股票代码"),
        timeframe: str = Query("1m", description="时间周期")
):
    """
    订阅实时数据（用于测试）
    
    返回订阅ID，可用于后续取消订阅
    """
    try:
        service = get_chart_service()
        subscription_id = service.subscribe(symbol, timeframe)

        return {
            "success": True,
            "subscription_id": subscription_id,
            "symbol": symbol,
            "timeframe": timeframe
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
        service = get_chart_service()
        success = service.unsubscribe(subscription_id)

        if success:
            return {"success": True, "message": "取消订阅成功"}
        else:
            raise HTTPException(status_code=404, detail="订阅不存在")

    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
