"""
T-Trading API Endpoints

API endpoints for the T-Trading engine:
- Configuration
- Quick analysis
- Engine control (start/stop/status)
- Signal retrieval
- Data source status
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from core.strategies.interfaces.models import (
    IntradayAnalysis,
    TTradingConfig,
    TTradingSignal,
    TTradingStats,
)
from core.strategies.ttrading import (
    MINIQMT_AVAILABLE,
    get_best_data_provider,
    get_miniqmt_provider,
    get_ttrading_engine,
    run_quick_analysis,
)
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ttrading", tags=["ttrading"])

# Global MiniQMT provider instance
_miniqmt_provider = None


# ============================================
# Request/Response Models
# ============================================


class QuickAnalyzeRequest(BaseModel):
    """快速分析请求"""

    symbol: str
    config: Optional[TTradingConfig] = None


class QuickAnalyzeResponse(BaseModel):
    """快速分析响应"""

    symbol: str
    analysis: IntradayAnalysis
    signals: list[TTradingSignal]
    recommendation: str
    confidence: float


class EngineStartRequest(BaseModel):
    """引擎启动请求"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "T-Trading"
    # 可以传入完整配置，或者只传必要字段
    base_position_ratio: float = 50.0
    trading_position_ratio: float = 50.0
    grid_enabled: bool = True
    grid_step_ratio: float = 2.0
    grid_levels: int = 5
    # 数据源选择
    use_real_data: bool = False  # 是否使用真实 MiniQMT 数据


class EngineStatusResponse(BaseModel):
    """引擎状态响应"""

    symbol: str
    is_running: bool
    stats: Optional[TTradingStats] = None
    config: Optional[TTradingConfig] = None


# ============================================
# Endpoints
# ============================================


@router.get("/config")
async def get_default_config() -> Dict[str, Any]:
    """获取默认做T配置"""
    return TTradingConfig(
        id="default",
        name="Default T-Trading Config",
        symbol="",
    ).model_dump()


@router.post("/analyze", response_model=QuickAnalyzeResponse)
async def quick_analyze(request: QuickAnalyzeRequest):
    """
    执行快速分析 (无需启动引擎)

    优先使用实盘数据（MiniQMT），不可用时回退到Mock
    """
    try:
        # 使用数据源回退机制获取最佳数据提供者
        data_provider = get_best_data_provider()

        result = await run_quick_analysis(
            request.symbol,
            request.config,
            data_provider,
        )

        # 构建响应
        analysis_data = result.get("analysis")
        signals = result.get("signals", [])

        # 如果analysis为None，创建一个默认的分析结果
        if analysis_data is None:
            analysis = IntradayAnalysis(
                symbol=request.symbol,
                date=datetime.now().strftime("%Y-%m-%d"),
                time=datetime.now().strftime("%H:%M:%S"),
                current_price=0,
                open_price=0,
                high_price=0,
                low_price=0,
                vwap=0,
                intraday_ma=0,
                price_deviation=0,
                volume_ratio=1.0,
                support_levels=[],
                resistance_levels=[],
                trend="sideways",
                buy_signal_strength=0,
                sell_signal_strength=0,
            )
        elif isinstance(analysis_data, dict):
            analysis = IntradayAnalysis(**analysis_data)
        else:
            analysis = analysis_data

        # 确定推荐
        if signals:
            # 找置信度最高的信号
            best_signal = max(
                signals,
                key=lambda s: s.get("confidence", 0) if isinstance(s, dict) else s.confidence,
            )
            if isinstance(best_signal, dict):
                recommendation = best_signal.get("direction", "hold")
                confidence = best_signal.get("confidence", 0.5)
            else:
                recommendation = best_signal.direction.value
                confidence = best_signal.confidence
        else:
            recommendation = "hold"
            confidence = 0.5

        return QuickAnalyzeResponse(
            symbol=request.symbol,
            analysis=analysis,
            signals=signals,
            recommendation=recommendation,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"Quick analysis failed for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine/{symbol}/start")
async def start_engine(symbol: str, request: EngineStartRequest):
    """启动做T引擎"""
    global _miniqmt_provider

    try:
        # 确定数据提供者
        data_provider = None
        data_source = "mock"

        if request.use_real_data:
            if not MINIQMT_AVAILABLE:
                raise HTTPException(
                    status_code=400,
                    detail="MiniQMT not available. Please use mock data.",
                )
            # 获取或创建 MiniQMT 提供者
            if _miniqmt_provider is None:
                _miniqmt_provider = get_miniqmt_provider()
            data_provider = _miniqmt_provider
            data_source = "miniqmt"

            if data_provider is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create MiniQMT provider.",
                )

        engine = get_ttrading_engine(symbol, data_provider)

        if engine.is_running:
            return {
                "status": "already_running",
                "symbol": symbol,
                "data_source": data_source,
                "message": "Engine is already running",
            }

        # 构建配置
        config = TTradingConfig(
            id=request.id,
            name=request.name,
            symbol=symbol,
            base_position_ratio=request.base_position_ratio,
            trading_position_ratio=request.trading_position_ratio,
            grid_enabled=request.grid_enabled,
            grid_step_ratio=request.grid_step_ratio,
            grid_levels=request.grid_levels,
        )

        await engine.start(config, data_provider)

        logger.info(f"T-Trading engine started for {symbol} with {data_source} data")

        return {
            "status": "started",
            "symbol": symbol,
            "data_source": data_source,
            "config": config.model_dump(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start engine for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine/{symbol}/stop")
async def stop_engine(symbol: str):
    """停止做T引擎"""
    try:
        engine = get_ttrading_engine(symbol)

        if not engine.is_running:
            return {
                "status": "not_running",
                "symbol": symbol,
                "message": "Engine is not running",
            }

        await engine.stop()

        logger.info(f"T-Trading engine stopped for {symbol}")

        return {
            "status": "stopped",
            "symbol": symbol,
        }

    except Exception as e:
        logger.error(f"Failed to stop engine for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine/{symbol}/status", response_model=EngineStatusResponse)
async def get_engine_status(symbol: str):
    """获取引擎状态"""
    try:
        engine = get_ttrading_engine(symbol)

        stats = None
        config = None

        if engine.is_running:
            stats = engine.get_stats()
            config = engine.config

        return EngineStatusResponse(
            symbol=symbol,
            is_running=engine.is_running,
            stats=stats,
            config=config,
        )

    except Exception as e:
        logger.error(f"Failed to get engine status for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine/{symbol}/signals")
async def get_engine_signals(symbol: str):
    """获取当前信号"""
    try:
        engine = get_ttrading_engine(symbol)

        if not engine.is_running:
            return {
                "symbol": symbol,
                "is_running": False,
                "signals": [],
                "message": "Engine is not running. Start the engine first.",
            }

        # 执行一次tick获取最新信号
        signals = await engine.tick()

        return {
            "symbol": symbol,
            "is_running": True,
            "signals": [s.model_dump() for s in signals],
            "total": len(signals),
        }

    except Exception as e:
        logger.error(f"Failed to get signals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine/{symbol}/snapshot")
async def get_engine_snapshot(symbol: str):
    """获取分析快照"""
    try:
        engine = get_ttrading_engine(symbol)

        if not engine.is_running:
            return {
                "symbol": symbol,
                "is_running": False,
                "snapshot": None,
                "message": "Engine is not running. Start the engine first.",
            }

        snapshot = engine.get_analysis_snapshot()

        return {
            "symbol": symbol,
            "is_running": True,
            "snapshot": snapshot.model_dump() if snapshot else None,
        }

    except Exception as e:
        logger.error(f"Failed to get snapshot for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasource/status")
async def get_datasource_status():
    """获取数据源状态"""
    global _miniqmt_provider

    status = {
        "miniqmt_available": MINIQMT_AVAILABLE,
        "miniqmt_connected": False,
        "active_provider": "mock",
    }

    # 首先检查全局引擎提供者
    if _miniqmt_provider is not None:
        status["miniqmt_connected"] = _miniqmt_provider.is_connected
        status["active_provider"] = "miniqmt"
    elif MINIQMT_AVAILABLE:
        # 如果 MiniQMT 可用但未手动启动引擎，也尝试检测实际连接状态
        try:
            provider = get_best_data_provider()
            if provider is not None:
                status["miniqmt_connected"] = provider.is_connected
                status["active_provider"] = "miniqmt"
        except Exception:
            pass

    return status


# ============================================
# Intraday Data API
# ============================================


class IntradayBar(BaseModel):
    """分时K线数据"""

    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None
    date: Optional[str] = None  # YYYY-MM-DD 格式，用于日期分隔


class IntradayDataResponse(BaseModel):
    """分时数据响应"""

    symbol: str
    bars: list[IntradayBar]
    current_price: float
    vwap: float
    signals: list[Dict[str, Any]] = []


@router.get("/intraday/{symbol}", response_model=IntradayDataResponse)
async def get_intraday_data(
    symbol: str, minutes: int = Query(60, ge=15, le=240, description="分钟数")
):
    """
    获取分时K线数据

    用于分时图展示，返回最近N分钟的分时数据
    """
    try:
        data_provider = get_best_data_provider()

        if data_provider is None:
            # 无数据源，返回空数据（不返回模拟数据）
            logger.warning(f"No data provider available for {symbol}")
            return IntradayDataResponse(
                symbol=symbol,
                bars=[],
                current_price=0,
                vwap=0,
                signals=[],
            )

        # 获取分时数据
        bars_df = await data_provider.get_intraday_bars(symbol, minutes=minutes)
        quote = await data_provider.get_current_quote(symbol)

        bars = []
        if bars_df is not None and not bars_df.empty:
            for _, row in bars_df.iterrows():
                bars.append(
                    IntradayBar(
                        time=row.get("time", ""),
                        open=float(row.get("open", 0)),
                        high=float(row.get("high", 0)),
                        low=float(row.get("low", 0)),
                        close=float(row.get("close", 0)),
                        volume=float(row.get("volume", 0)),
                        vwap=float(row.get("vwap", 0)) if "vwap" in row else None,
                        date=row.get("date", None),  # 从 DataFrame 中获取日期
                    )
                )

        current_price = quote.price if quote else 0
        vwap = quote.avg_price if quote and hasattr(quote, "avg_price") else current_price

        return IntradayDataResponse(
            symbol=symbol,
            bars=bars,
            current_price=current_price,
            vwap=vwap,
            signals=[],
        )

    except Exception as e:
        logger.error(f"Failed to get intraday data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# K-Line Data API (for KLineChart Pro)
# ============================================


class KLineBar(BaseModel):
    """K线数据"""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None
    # 新增字段：用于前端显示
    date: Optional[str] = None  # YYYY-MM-DD 格式
    time_str: Optional[str] = None  # HH:MM 格式


class KLineDataResponse(BaseModel):
    """K线数据响应"""

    symbol: str
    period: str
    bars: list[KLineBar]


@router.get("/kline/{symbol}", response_model=KLineDataResponse)
async def get_kline_data(
    symbol: str,
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M"),
    from_ts: Optional[int] = Query(None, description="开始时间戳(毫秒), 参数名: from"),
    to_ts: Optional[int] = Query(None, description="结束时间戳(毫秒), 参数名: to"),
    count: int = Query(300, ge=10, le=1000, description="数据条数"),
):
    """
    获取K线历史数据

    用于 KLineChart Pro 图表展示
    """
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        from datetime import timedelta

        from core.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        # 获取MiniQMTCollector实例
        collector = MiniQMTCollector()

        if not collector.connected:
            logger.warning("MiniQMT not connected for kline data")
            return KLineDataResponse(symbol=symbol, period=period, bars=[])

        # 计算时间范围
        now = datetime.now()
        if to_ts:
            end_date = datetime.fromtimestamp(to_ts / 1000)
        else:
            end_date = now

        if from_ts:
            start_date = datetime.fromtimestamp(from_ts / 1000)
        else:
            # 根据周期计算默认开始时间
            if period.endswith("m"):
                # 分钟级别，默认查询当天
                start_date = now.replace(hour=9, minute=30, second=0, microsecond=0)
            elif period.endswith("d"):
                # 日级别，默认查询近一年
                start_date = now - timedelta(days=365)
            elif period.endswith("w"):
                # 周级别，默认查询近两年
                start_date = now - timedelta(weeks=104)
            else:
                # 月级别，默认查询近五年
                start_date = now - timedelta(days=365 * 5)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        logger.info(
            f"Fetching kline data for {symbol}, period={period}, start={start_str}, end={end_str}"
        )

        # 在线程池中执行同步操作
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                lambda: collector.download_history_data(
                    stock_code=symbol,
                    period=period,
                    start_time=start_str,
                    end_time=end_str,
                ),
            )

        bars = []
        if result.get("success") and result.get("data"):
            import pytz

            shanghai_tz = pytz.timezone("Asia/Shanghai")

            for bar in result["data"]:
                # 解析时间戳
                time_val = bar.get("time")
                ts = 0
                date_str = None
                time_str = None

                try:
                    # 处理不同类型的时间值
                    if hasattr(time_val, "timestamp"):
                        # pandas Timestamp 或 datetime 对象
                        ts = int(time_val.timestamp() * 1000)
                        # 转换为 datetime
                        if hasattr(time_val, "to_pydatetime"):
                            dt = time_val.to_pydatetime()
                        else:
                            dt = time_val
                        # 转换为北京时间
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=pytz.UTC)
                        beijing_dt = dt.astimezone(shanghai_tz)
                        date_str = beijing_dt.strftime("%Y-%m-%d")
                        time_str = beijing_dt.strftime("%H:%M")
                    elif isinstance(time_val, str):
                        # 解析时间字符串
                        dt = (
                            datetime.fromisoformat(time_val.replace("Z", "+00:00"))
                            if "T" in time_val
                            else datetime.strptime(time_val, "%Y-%m-%d %H:%M:%S")
                        )
                        ts = int(dt.timestamp() * 1000)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=pytz.UTC)
                        beijing_dt = dt.astimezone(shanghai_tz)
                        date_str = beijing_dt.strftime("%Y-%m-%d")
                        time_str = beijing_dt.strftime("%H:%M")
                    elif isinstance(time_val, (int, float)):
                        ts = int(time_val)
                        # 将毫秒时间戳转换为北京时间
                        dt = datetime.fromtimestamp(ts / 1000, tz=pytz.UTC)
                        beijing_dt = dt.astimezone(shanghai_tz)
                        date_str = beijing_dt.strftime("%Y-%m-%d")
                        time_str = beijing_dt.strftime("%H:%M")
                except Exception as e:
                    logger.debug(f"Failed to parse time value {time_val}: {e}")

                bars.append(
                    KLineBar(
                        timestamp=ts,
                        open=float(bar.get("open", 0)),
                        high=float(bar.get("high", 0)),
                        low=float(bar.get("low", 0)),
                        close=float(bar.get("close", 0)),
                        volume=float(bar.get("volume", 0)),
                        amount=float(bar.get("amount", 0)) if bar.get("amount") else None,
                        date=date_str,
                        time_str=time_str,
                    )
                )

        logger.info(f"Got {len(bars)} kline bars for {symbol}")

        return KLineDataResponse(
            symbol=symbol,
            period=period,
            bars=bars,
        )

    except Exception as e:
        logger.error(f"Failed to get kline data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
