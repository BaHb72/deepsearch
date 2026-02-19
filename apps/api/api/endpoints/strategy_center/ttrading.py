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
import inspect
from typing import Any, Dict, Optional, cast
from uuid import uuid4

from core.strategies.interfaces.models import (
    IntradayAnalysis,
    TTradingConfig,
    TTradingSignal,
    TTradingStats,
)
from core.strategies.ttrading import (
    MINIQMT_AVAILABLE,
    get_miniqmt_provider,
    get_ttrading_engine,
    run_quick_analysis,
)
from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
import pandas as pd
from pydantic import BaseModel, Field

from apps.api.api.provider_deps import resolve_provider_from_request

router = APIRouter(prefix="/ttrading", tags=["ttrading"])

# Global MiniQMT provider instance
_miniqmt_provider = None


def _probe_miniqmt_tcp_connection() -> bool:
    """检测 MiniQMT 配置端口是否可达（进程级可用性）。"""
    try:
        from core.config import get_config
        from core.utils.system.port_checker import PortChecker

        config = get_config()
        miniqmt_config: Any = getattr(config, "miniqmt", None)

        host = "127.0.0.1"
        port = 7777
        connection: Any = None

        if isinstance(miniqmt_config, dict):
            connection = miniqmt_config.get("connection")
            host = str(miniqmt_config.get("host", host))
            port = int(miniqmt_config.get("port", port))
        elif miniqmt_config is not None:
            connection = getattr(miniqmt_config, "connection", None)
            host = str(getattr(miniqmt_config, "host", host))
            port = int(getattr(miniqmt_config, "port", port))

        if connection is not None:
            if isinstance(connection, dict):
                host = str(connection.get("host", host))
                port = int(connection.get("port", port))
            else:
                host = str(getattr(connection, "host", host))
                port = int(getattr(connection, "port", port))

        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"

        # PortChecker.is_port_available=True 表示端口空闲（无人监听）
        return not PortChecker.is_port_available(port=port, host=host)

    except Exception as e:
        logger.debug(f"MiniQMT TCP 探测失败，按未连接处理: {e}")
        return False


def _get_positional_arity(func: Any) -> int:
    """返回可调用对象的位置参数个数（仅统计 POSITIONAL_*）。"""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return 0
    return sum(
        1
        for param in signature.parameters.values()
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    )


async def _probe_miniqmt_actor_connection(request: Optional[Request] = None) -> bool:
    """通过 MiniQMT Actor 主动探活，返回真实连接状态。"""
    try:
        if request is None:
            return False
        provider = await resolve_provider_from_request(request, "miniqmt", strict=False)
        if provider is None:
            return False

        heartbeat = getattr(provider, "heartbeat", None)
        if not callable(heartbeat):
            return False

        connected = bool(await heartbeat())
        if not connected:
            return False

        get_status = getattr(provider, "get_status", None)
        if callable(get_status):
            status = await get_status()
            if isinstance(status, dict):
                connected = bool(status.get("connected", connected))

        return connected

    except Exception as e:
        logger.debug(f"MiniQMT Actor 探活失败，按未连接处理: {e}")
        return False


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except Exception:
        return default


def _to_datetime_safe(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return None
        if hasattr(dt, "to_pydatetime"):
            return dt.to_pydatetime()
    except Exception:
        return None
    return None


def _extract_row_value(row: Dict[str, Any], candidates: list[str], default: Any = None) -> Any:
    for key in candidates:
        if key in row and row[key] is not None:
            return row[key]
    return default


def _normalize_kline_rows(
    rows: list[Dict[str, Any]],
    *,
    symbol: str,
    limit: int,
) -> pd.DataFrame:
    normalized: list[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt_raw = _extract_row_value(
            row,
            ["datetime", "date", "time", "trade_time", "timestamp", "ts"],
        )
        dt = _to_datetime_safe(dt_raw)
        if dt is None:
            continue
        close = _to_float(_extract_row_value(row, ["close", "收盘", "last", "latest"]))
        open_ = _to_float(_extract_row_value(row, ["open", "开盘"], close))
        high = _to_float(_extract_row_value(row, ["high", "最高"], close))
        low = _to_float(_extract_row_value(row, ["low", "最低"], close))
        volume = _to_float(_extract_row_value(row, ["volume", "vol", "成交量"], 0.0))
        amount = _to_float(_extract_row_value(row, ["amount", "成交额"], 0.0))
        normalized.append(
            {
                "symbol": symbol,
                "datetime": dt,
                "time": dt.strftime("%H:%M"),
                "date": dt.strftime("%Y-%m-%d"),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": amount,
            }
        )
    if not normalized:
        return pd.DataFrame()
    normalized.sort(key=lambda x: x["datetime"])
    if limit > 0:
        normalized = normalized[-limit:]
    return pd.DataFrame(normalized)


async def _get_provider_with_soft_fail(request: Optional[Request], provider_name: str) -> Any:
    try:
        if request is None:
            return None
        return await resolve_provider_from_request(request, provider_name, strict=False)
    except Exception as e:
        logger.debug(f"Provider 获取失败({provider_name})，软失败降级: {e}")
        return None


async def _probe_miniqmt_actor_connection_compat(request: Optional[Request]) -> bool:
    probe = _probe_miniqmt_actor_connection
    arity = _get_positional_arity(probe)
    if arity == 0:
        return bool(await probe())
    return bool(await probe(request))


async def _get_provider_with_soft_fail_compat(request: Optional[Request], provider_name: str) -> Any:
    getter = _get_provider_with_soft_fail
    arity = _get_positional_arity(getter)
    if arity <= 1:
        return await getter(provider_name)
    return await getter(request, provider_name)


async def _get_intraday_bars_compat(
    data_provider: Any, request: Optional[Request], symbol: str, minutes: int
) -> pd.DataFrame:
    getter = data_provider.get_intraday_bars
    arity = _get_positional_arity(getter)
    if arity >= 3:
        return await getter(request, symbol, minutes=minutes)
    return await getter(symbol, minutes=minutes)


async def _get_current_quote_compat(data_provider: Any, request: Optional[Request], symbol: str) -> Any:
    getter = data_provider.get_current_quote
    arity = _get_positional_arity(getter)
    if arity >= 2:
        return await getter(request, symbol)
    return await getter(symbol)


async def _fetch_kline_rows_from_provider(
    provider: Any,
    *,
    symbol: str,
    period: str,
    start_date: str,
    end_date: str,
    limit: int,
) -> list[Dict[str, Any]]:
    if provider is None:
        return []

    fetcher = getattr(provider, "get_kline_data", None)
    if not callable(fetcher):
        return []

    for invoke in (
        lambda: fetcher(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        ),
        lambda: fetcher(symbol, period=period, start_date=start_date, end_date=end_date, limit=limit),
        lambda: fetcher(symbol=symbol, period=period, start_date=start_date, end_date=end_date),
    ):
        try:
            result = await invoke()
            if result is None:
                continue
            if isinstance(result, pd.DataFrame):
                return cast(list[Dict[str, Any]], result.to_dict("records"))
            if isinstance(result, list):
                return cast(list[Dict[str, Any]], result)
            if isinstance(result, dict):
                payload = result.get("data")
                if isinstance(payload, list):
                    return cast(list[Dict[str, Any]], payload)
        except TypeError:
            continue
        except Exception:
            return []
    return []


async def _fetch_quote_from_provider(provider: Any, symbol: str) -> Optional[Dict[str, Any]]:
    if provider is None:
        return None

    quote_fetcher = getattr(provider, "get_realtime_quote", None)
    if callable(quote_fetcher):
        for invoke in (
            lambda: quote_fetcher(symbol=symbol),
            lambda: quote_fetcher(symbol),
            lambda: quote_fetcher([symbol]),
        ):
            try:
                data = await invoke()
                if isinstance(data, dict):
                    if symbol in data and isinstance(data[symbol], dict):
                        return cast(Dict[str, Any], data[symbol])
                    return cast(Dict[str, Any], data)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    return cast(Dict[str, Any], data[0])
            except TypeError:
                continue
            except Exception:
                break

    quotes_fetcher = getattr(provider, "get_realtime_quotes", None)
    if callable(quotes_fetcher):
        try:
            data = await quotes_fetcher([symbol])
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return cast(Dict[str, Any], data[0])
        except Exception:
            return None
    return None


class _FailoverIntradayDataProvider:
    """端点级止血适配器：MiniQMT 失败后回退 AmazingData/AkShare。"""

    def __init__(self) -> None:
        self._miniqmt_provider = get_miniqmt_provider()
        self.active_source: str = "none"
        self.attempts: list[str] = []

    async def _fetch_miniqmt_bars(self, symbol: str, minutes: int) -> pd.DataFrame:
        provider = self._miniqmt_provider
        if provider is None:
            self.attempts.append("miniqmt:provider_none")
            return pd.DataFrame()
        try:
            bars = await provider.get_intraday_bars(symbol, minutes=minutes)
            if bars is not None and not bars.empty:
                self.active_source = "miniqmt"
                return bars
            self.attempts.append("miniqmt:empty")
        except Exception as e:
            self.attempts.append(f"miniqmt:error:{e.__class__.__name__}")
        return pd.DataFrame()

    async def _fetch_fallback_bars(
        self, request: Optional[Request], source: str, symbol: str, minutes: int
    ) -> pd.DataFrame:
        provider = await _get_provider_with_soft_fail_compat(request, source)
        if provider is None:
            self.attempts.append(f"{source}:provider_none")
            return pd.DataFrame()

        now_dt = datetime.now()
        start_dt = now_dt.replace(hour=9, minute=30, second=0, microsecond=0)
        if now_dt < start_dt:
            start_dt = now_dt
        rows = await _fetch_kline_rows_from_provider(
            provider,
            symbol=symbol,
            period="1m",
            start_date=start_dt.strftime("%Y%m%d"),
            end_date=now_dt.strftime("%Y%m%d"),
            limit=max(30, minutes),
        )
        bars = _normalize_kline_rows(rows, symbol=symbol, limit=minutes)
        if bars.empty:
            self.attempts.append(f"{source}:empty")
            return pd.DataFrame()
        self.active_source = source
        return bars

    async def get_intraday_bars(
        self, request: Optional[Request], symbol: str, minutes: int = 240
    ) -> pd.DataFrame:
        self.attempts = []
        self.active_source = "none"

        bars = await self._fetch_miniqmt_bars(symbol, minutes)
        if not bars.empty:
            return bars

        for source in ("amazingdata", "akshare"):
            bars = await self._fetch_fallback_bars(request, source, symbol, minutes)
            if not bars.empty:
                return bars
        return pd.DataFrame()

    async def get_current_quote(self, request: Optional[Request], symbol: str):
        from core.strategies.ttrading.interfaces import QuoteSnapshot

        provider = self._miniqmt_provider
        if provider is not None:
            try:
                quote = await provider.get_current_quote(symbol)
                if quote is not None:
                    self.active_source = "miniqmt"
                    return quote
            except Exception:
                pass

        for source in ("amazingdata", "akshare"):
            provider_obj = await _get_provider_with_soft_fail_compat(request, source)
            payload = await _fetch_quote_from_provider(provider_obj, symbol)
            if not payload:
                continue

            price = _to_float(
                _extract_row_value(
                    payload,
                    ["price", "last", "last_price", "最新价", "close", "收盘"],
                ),
                0.0,
            )
            if price <= 0:
                continue
            open_ = _to_float(_extract_row_value(payload, ["open", "开盘"], price), price)
            high = _to_float(_extract_row_value(payload, ["high", "最高"], price), price)
            low = _to_float(_extract_row_value(payload, ["low", "最低"], price), price)
            prev_close = _to_float(
                _extract_row_value(payload, ["prev_close", "昨收", "pre_close"], open_),
                open_,
            )
            volume = _to_float(_extract_row_value(payload, ["volume", "成交量"], 0.0), 0.0)
            amount = _to_float(_extract_row_value(payload, ["amount", "成交额"], 0.0), 0.0)

            self.active_source = source
            return QuoteSnapshot(
                symbol=symbol,
                datetime=datetime.now(),
                price=price,
                open=open_,
                high=high,
                low=low,
                prev_close=prev_close,
                volume=volume,
                amount=amount,
            )
        return None

    async def subscribe(self, symbols, callback: Any) -> None:
        provider = self._miniqmt_provider
        if provider is None:
            return
        try:
            await provider.subscribe(symbols, callback)
        except Exception:
            return

    async def unsubscribe(self, symbols) -> None:
        provider = self._miniqmt_provider
        if provider is None:
            return
        try:
            await provider.unsubscribe(symbols)
        except Exception:
            return


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
        data_provider = _FailoverIntradayDataProvider()

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
async def start_engine(
    symbol: str,
    payload: EngineStartRequest,
    request: Request = None,
):
    """启动做T引擎"""
    global _miniqmt_provider

    try:
        # 确定数据提供者
        data_provider = None
        data_source = "mock"

        if payload.use_real_data:
            data_provider = _FailoverIntradayDataProvider()
            probe_quote = await _get_current_quote_compat(data_provider, request, symbol)
            probe_bars = await _get_intraday_bars_compat(data_provider, request, symbol, minutes=30)
            if probe_quote is None and (probe_bars is None or probe_bars.empty):
                raise HTTPException(
                    status_code=503,
                    detail={
                        "message": "所有实时数据源均不可用",
                        "attempts": data_provider.attempts,
                        "fallback_order": ["miniqmt", "amazingdata", "akshare"],
                    },
                )
            data_source = data_provider.active_source or "fallback"

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
            id=payload.id,
            name=payload.name,
            symbol=symbol,
            base_position_ratio=payload.base_position_ratio,
            trading_position_ratio=payload.trading_position_ratio,
            grid_enabled=payload.grid_enabled,
            grid_step_ratio=payload.grid_step_ratio,
            grid_levels=payload.grid_levels,
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
async def get_datasource_status(request: Request = None):
    """获取数据源状态"""
    status = {
        "miniqmt_available": MINIQMT_AVAILABLE,
        "miniqmt_connected": False,
        "active_provider": "mock",
    }

    if not MINIQMT_AVAILABLE:
        return status

    # 先做进程级可达性检测，避免“客户端未启动”时误报已连接。
    if not _probe_miniqmt_tcp_connection():
        return status

    # 状态接口只依据真实探活结果，不再依赖“可导入即连接”的本地标志位。
    connected = await _probe_miniqmt_actor_connection_compat(request)
    if connected:
        status["miniqmt_connected"] = True
        status["active_provider"] = "miniqmt"
        return status

    amazingdata = await _get_provider_with_soft_fail_compat(request, "amazingdata")
    if amazingdata is not None:
        status["active_provider"] = "amazingdata"
        status["amazingdata_available"] = True
    else:
        status["amazingdata_available"] = False

    akshare = await _get_provider_with_soft_fail_compat(request, "akshare")
    if akshare is not None:
        status["akshare_available"] = True
        if status["active_provider"] == "mock":
            status["active_provider"] = "akshare"
    else:
        status["akshare_available"] = False

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
    symbol: str,
    request: Request = None,
    minutes: int = Query(60, ge=15, le=240, description="分钟数"),
):
    """
    获取分时K线数据

    用于分时图展示，返回最近N分钟的分时数据
    """
    try:
        data_provider = _FailoverIntradayDataProvider()

        # 获取分时数据
        bars_df = await _get_intraday_bars_compat(data_provider, request, symbol, minutes=minutes)
        quote = await _get_current_quote_compat(data_provider, request, symbol)

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

        if quote is None and bars:
            current_price = bars[-1].close
        else:
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
    request: Request = None,
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
        from datetime import timedelta

        from core.adapters.market_data.miniqmt_polling_adapter import get_shared_miniqmt_collector

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

        rows: list[Dict[str, Any]] = []
        source = "none"

        try:
            collector = await get_shared_miniqmt_collector()
            if collector.connected:
                result = await asyncio.to_thread(
                    collector.download_history_data,
                    stock_code=symbol,
                    period=period,
                    start_time=start_str,
                    end_time=end_str,
                )
                if result.get("success") and result.get("data"):
                    raw_rows = result["data"]
                    if isinstance(raw_rows, list):
                        rows = cast(list[Dict[str, Any]], raw_rows)
                        source = "miniqmt"
        except Exception as e:
            logger.warning(f"MiniQMT kline 获取失败，尝试回退: {e}")

        if not rows:
            for fallback_source in ("amazingdata", "akshare"):
                provider = await _get_provider_with_soft_fail_compat(request, fallback_source)
                fallback_rows = await _fetch_kline_rows_from_provider(
                    provider,
                    symbol=symbol,
                    period=period,
                    start_date=start_str,
                    end_date=end_str,
                    limit=count,
                )
                if fallback_rows:
                    rows = fallback_rows
                    source = fallback_source
                    break

        bars = []
        if rows:
            import pytz

            shanghai_tz = pytz.timezone("Asia/Shanghai")

            for bar in rows:
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
                        if "T" in time_val:
                            dt = datetime.fromisoformat(time_val.replace("Z", "+00:00"))
                        elif len(time_val) == 8 and time_val.isdigit():
                            dt = datetime.strptime(time_val, "%Y%m%d")
                        else:
                            dt = datetime.strptime(time_val, "%Y-%m-%d %H:%M:%S")
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
                    else:
                        dt_fallback = _to_datetime_safe(
                            bar.get("datetime") or bar.get("date") or bar.get("timestamp")
                        )
                        if dt_fallback is not None:
                            ts = int(dt_fallback.timestamp() * 1000)
                            if dt_fallback.tzinfo is None:
                                dt_fallback = dt_fallback.replace(tzinfo=pytz.UTC)
                            beijing_dt = dt_fallback.astimezone(shanghai_tz)
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

        logger.info(f"Got {len(bars)} kline bars for {symbol} from {source}")

        return KLineDataResponse(
            symbol=symbol,
            period=period,
            bars=bars,
        )

    except Exception as e:
        logger.error(f"Failed to get kline data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
