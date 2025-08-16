"""
图表数据 API
提供K线数据、技术指标计算等接口
"""
import json
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel

from deepsearch.data_providers.cloudflare import ProxyDataProvider
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
        data_provider = None

        # 优先尝试使用AKShare直连提供者
        try:
            from deepsearch.data_providers.akshare_direct import AKShareDirectProvider
            import asyncio

            akshare_provider = AKShareDirectProvider()
            # 检查是否有运行中的事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果在异步上下文中，创建任务
                init_task = loop.create_task(akshare_provider.initialize())
                # 这里无法等待，所以假设成功
                data_provider = akshare_provider
                logger.info("使用AKShare直连数据提供者（异步初始化）")
            except RuntimeError:
                # 没有运行的事件循环，创建新的
                loop = asyncio.new_event_loop()
                init_result = loop.run_until_complete(akshare_provider.initialize())
                loop.close()

                if init_result:
                    data_provider = akshare_provider
                    logger.info("使用AKShare直连数据提供者")
        except Exception as e:
            logger.warning(f"初始化AKShare直连提供者失败: {e}")

        # 如果AKShare不可用，使用CloudFlare代理
        if data_provider is None:
            data_provider = ProxyDataProvider()
            logger.info("使用CloudFlare代理数据提供者")
        
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
        session_split: bool = Query(True, description="是否分割交易时段"),
        provider: Optional[str] = Query(None, description="数据提供者: default, miniqmt, akshare等")
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
            session_split=session_split,
            provider=provider
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


@router.get("/validate/{symbol}")
async def validate_data_sources(
        symbol: str,
        timeframe: str = Query("1d", description="时间周期")
):
    """
    验证多个数据源的数据一致性
    
    返回各数据源的数据和差异分析
    """
    try:
        service = get_chart_service()
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
        service = get_chart_service()
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
        service = get_chart_service()
        meta = await service.get_stock_meta(symbol)
        return meta
    except Exception as e:
        logger.error(f"获取股票元数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-info")
async def get_stock_info(
        symbol: str = Query(..., description="股票代码")
):
    """
    获取股票基础信息
    
    返回股票的基本信息，包括名称、所属板块、市值、市盈率等
    """
    try:
        service = get_chart_service()
        data = await service.get_stock_info(symbol)
        return data
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        # 如果服务失败，返回基础信息
        return {
            'symbol': symbol,
            'name': f'股票{symbol}',
            'sector': '未知',
            'market_cap': '未知',
            'pe_ratio': 0,
            'error': str(e)
        }


@router.get("/stock-list")
async def get_stock_list(
        keyword: Optional[str] = Query(None, description="搜索关键字")
):
    """
    获取股票列表
    
    支持通过代码或名称搜索股票
    """
    try:
        service = get_chart_service()
        data = await service.get_stock_list(keyword)
        return data
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        # 如果服务失败，返回模拟数据
        mock_stocks = [
            {'code': '000001', 'name': '平安银行', 'label': '平安银行 (000001)', 'value': '000001'},
            {'code': '000002', 'name': '万科A', 'label': '万科A (000002)', 'value': '000002'},
            {'code': '000858', 'name': '五粮液', 'label': '五粮液 (000858)', 'value': '000858'},
            {'code': '002415', 'name': '海康威视', 'label': '海康威视 (002415)', 'value': '002415'},
            {'code': '300750', 'name': '宁德时代', 'label': '宁德时代 (300750)', 'value': '300750'},
            {'code': '600000', 'name': '浦发银行', 'label': '浦发银行 (600000)', 'value': '600000'},
            {'code': '600036', 'name': '招商银行', 'label': '招商银行 (600036)', 'value': '600036'},
            {'code': '600519', 'name': '贵州茅台', 'label': '贵州茅台 (600519)', 'value': '600519'},
            {'code': '601318', 'name': '中国平安', 'label': '中国平安 (601318)', 'value': '601318'},
            {'code': '601606', 'name': '长城军工', 'label': '长城军工 (601606)', 'value': '601606'},
        ]

        if keyword:
            keyword_lower = keyword.lower()
            filtered = [s for s in mock_stocks
                        if keyword_lower in s['code'].lower() or keyword_lower in s['name'].lower()]
            return filtered

        return mock_stocks


@router.get("/chip-distribution")
async def get_chip_distribution(
        symbol: str = Query(..., description="股票代码"),
        lookback_days: int = Query(120, description="回看天数"),
        price_bins: int = Query(100, description="价格分档数")
):
    """
    获取筹码分布数据
    
    返回股票的筹码分布、成本分布和支撑阻力位等信息
    """
    try:
        service = get_chart_service()
        data = await service.calculate_chip_distribution(
            symbol=symbol,
            timeframe="1d",  # 筹码分布使用日线数据
            lookback_days=lookback_days,
            price_bins=price_bins
        )
        return data
    except Exception as e:
        logger.error(f"获取筹码分布失败: {e}")
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
