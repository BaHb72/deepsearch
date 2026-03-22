"""
T-Trading API Endpoints

API endpoints for the T-Trading engine:
- Configuration
- Quick analysis
- Engine control (start/stop/status)
- Signal retrieval
- Data source status
"""

import inspect
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time
from typing import Any, Callable, Dict, Literal, Optional, Protocol, cast
from uuid import uuid4

import pandas as pd
from core.backtest.data.history_status_overlay import (
    BacktestHistoryStatusSnapshot,
    HistoryStatusOverlayError,
    apply_trade_day_status_snapshot,
    coerce_status_dataframe,
    extract_trade_day_status_snapshot,
)
from core.strategies.interfaces.models import (
    IntradayAnalysis,
    SignalDirection,
    TradingCostConfig,
    TTradingConfig,
    TTradingSignal,
    TTradingStats,
)
from core.strategies.ttrading import (
    MINIQMT_AVAILABLE,
    CompositeIntradayAnalyzer,
    GridSignalGenerator,
    MADeviationSignalGenerator,
    SupportResistanceSignalGenerator,
    VolumePriceSignalGenerator,
    get_miniqmt_provider,
    get_ttrading_engine,
    run_quick_analysis,
)
from core.strategies.ttrading.advanced_strategies import (
    MomentumReversalStrategy,
    OpeningBreakoutStrategy,
    TimeWindowStrategy,
    VWAPDeviationStrategy,
)
from core.strategies.ttrading.backtest_blocked_reasons import (
    build_blocked_summary_items,
    build_blocked_summary_zh,
    get_blocked_reason_label,
)
from core.strategies.ttrading.interfaces import IntradayDataProvider
from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.provider_deps import resolve_provider_from_request

router = APIRouter(prefix="/ttrading", tags=["ttrading"])

bt: Any
try:
    import backtrader as _backtrader

    bt = _backtrader
    HAS_BACKTRADER = True
except ImportError:
    bt = None
    HAS_BACKTRADER = False

TTradingBacktestMode = Literal["legacy", "shadow", "backtrader"]
DEFAULT_TTRADING_BACKTEST_MODE: TTradingBacktestMode = "shadow"
SHADOW_DIFF_THRESHOLDS: dict[str, float] = {
    "total_profit_pct": 0.5,
    "win_rate": 3.0,
    "trade_count": 2.0,
    "max_drawdown": 1.0,
    "blocked_total": 3.0,
}

# Global MiniQMT provider instance
_miniqmt_provider = None


@dataclass(frozen=True)
class TTradingBacktestContext:
    """做T回测执行上下文。"""

    symbol: str
    trade_day: date_type
    bars_df: pd.DataFrame
    strategy_keys: list[str]
    initial_capital: float
    base_position_ratio: float
    position_ratio: float
    min_confidence: float
    max_trades: int


def _normalize_probe_host(host: str) -> str:
    value = (host or "127.0.0.1").strip()
    if value in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return value


def _resolve_miniqmt_probe_targets() -> list[tuple[str, int]]:
    """解析 MiniQMT 探测目标列表（配置优先，兼容常见端口）。"""
    targets: list[tuple[str, int]] = []

    def _append_target(host_value: Any, port_value: Any) -> None:
        try:
            port = int(port_value)
        except Exception:
            return
        if port <= 0:
            return
        host = _normalize_probe_host(str(host_value))
        candidate = (host, port)
        if candidate not in targets:
            targets.append(candidate)

    try:
        from core.config import get_config

        config = get_config()
        miniqmt_config: Any = getattr(config, "miniqmt", None)

        host = "127.0.0.1"
        port = 7777
        connection: Any = None

        if isinstance(miniqmt_config, dict):
            connection = miniqmt_config.get("connection")
            host = str(miniqmt_config.get("host", host) or host)
            raw_port = miniqmt_config.get("port", port)
            try:
                port = int(raw_port)
            except Exception:
                port = 7777
        elif miniqmt_config is not None:
            connection = getattr(miniqmt_config, "connection", None)
            host = str(getattr(miniqmt_config, "host", host) or host)
            raw_port = getattr(miniqmt_config, "port", port)
            try:
                port = int(raw_port)
            except Exception:
                port = 7777

        if connection is not None:
            if isinstance(connection, dict):
                host = str(connection.get("host", host) or host)
                raw_port = connection.get("port", port)
                try:
                    port = int(raw_port)
                except Exception:
                    pass
            else:
                host = str(getattr(connection, "host", host) or host)
                raw_port = getattr(connection, "port", port)
                try:
                    port = int(raw_port)
                except Exception:
                    pass
        _append_target(host, port)
    except Exception as e:
        logger.debug(f"读取 MiniQMT 配置失败，使用默认探测端口: {e}")

    # 常见端口兜底：7777（旧默认）/58610（用户环境常见）
    for fallback_port in (7777, 58610):
        _append_target("127.0.0.1", fallback_port)

    if not targets:
        targets.append(("127.0.0.1", 7777))
    return targets


def _probe_miniqmt_tcp_connection() -> tuple[bool, str, int]:
    """检测 MiniQMT TCP 端口可达性，返回 (可达, host, port)。"""
    from core.utils.system.port_checker import PortChecker

    targets = _resolve_miniqmt_probe_targets()
    for host, port in targets:
        try:
            # PortChecker.is_port_available=True 表示端口空闲（无人监听）
            if not PortChecker.is_port_available(port=port, host=host):
                return True, host, port
        except Exception as e:
            logger.debug(f"MiniQMT TCP 探测失败({host}:{port})，继续尝试: {e}")
            continue
    first_host, first_port = targets[0]
    return False, first_host, first_port


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _extract_connected_from_provider(provider: Any) -> bool:
    status_getters = ("get_status", "get_connection_status")
    for getter_name in status_getters:
        getter = getattr(provider, getter_name, None)
        if not callable(getter):
            continue
        try:
            payload = await _await_if_needed(getter())
            if isinstance(payload, dict) and "connected" in payload:
                return bool(payload.get("connected"))
        except Exception:
            continue

    is_connected_attr = getattr(provider, "is_connected", None)
    try:
        if callable(is_connected_attr):
            return bool(is_connected_attr())
        if is_connected_attr is not None:
            return bool(is_connected_attr)
    except Exception:
        pass

    connected_attr = getattr(provider, "connected", None)
    if connected_attr is not None:
        try:
            return bool(connected_attr)
        except Exception:
            pass
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
        if param.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    )


async def _probe_miniqmt_actor_connection(
    request: Optional[Request] = None,
    *,
    probe_host: str | None = None,
    probe_port: int | None = None,
) -> bool:
    """通过 MiniQMT Actor 主动探活，返回真实连接状态。"""
    try:
        if request is None:
            return False
        provider = await resolve_provider_from_request(request, "miniqmt", strict=False)
        if provider is None:
            return False

        # 兼容直连 Provider：按 TCP 探测结果覆盖 host/port 后再探活
        if probe_host and hasattr(provider, "host"):
            try:
                setattr(provider, "host", probe_host)
            except Exception:
                pass
        if probe_port and hasattr(provider, "port"):
            try:
                setattr(provider, "port", int(probe_port))
            except Exception:
                pass

        heartbeat = getattr(provider, "heartbeat", None)
        if callable(heartbeat):
            try:
                connected = bool(await _await_if_needed(heartbeat()))
                if connected:
                    return bool(await _extract_connected_from_provider(provider))
            except Exception:
                pass

        connected = await _extract_connected_from_provider(provider)
        if connected:
            return True

        initializer = getattr(provider, "initialize", None)
        if callable(initializer):
            try:
                init_result = await _await_if_needed(initializer())
                if init_result is False:
                    return False
                connected = await _extract_connected_from_provider(provider)
                if connected:
                    return True
            except Exception as init_exc:
                logger.debug(f"MiniQMT 初始化探活失败: {init_exc}")

        return False

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


async def _probe_miniqmt_actor_connection_compat(
    request: Optional[Request],
    *,
    probe_host: str | None = None,
    probe_port: int | None = None,
) -> bool:
    probe = _probe_miniqmt_actor_connection
    arity = _get_positional_arity(probe)
    if arity == 0:
        for invoke in (
            lambda: probe(probe_host=probe_host, probe_port=probe_port),
            lambda: probe(),
        ):
            try:
                return bool(await invoke())
            except TypeError:
                continue
        return False

    for invoke in (
        lambda: probe(request, probe_host=probe_host, probe_port=probe_port),
        lambda: probe(request),
    ):
        try:
            return bool(await invoke())
        except TypeError:
            continue
    return False


async def _get_provider_with_soft_fail_compat(
    request: Optional[Request], provider_name: str
) -> Any:
    getter: Any = _get_provider_with_soft_fail
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


async def _get_current_quote_compat(
    data_provider: Any, request: Optional[Request], symbol: str
) -> Any:
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
        lambda: fetcher(
            symbol, period=period, start_date=start_date, end_date=end_date, limit=limit
        ),
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


async def _fetch_history_stock_status_dataframe(provider: Any, symbol: str) -> pd.DataFrame:
    fetcher = getattr(provider, "get_history_stock_status", None)
    if not callable(fetcher):
        raise HTTPException(
            status_code=503,
            detail="回测要求强制接入 history_stock_status，但当前数据源不支持该接口",
        )

    last_error: Optional[Exception] = None
    for invoke in (
        lambda: fetcher(code_list=[symbol], is_local=True),
        lambda: fetcher([symbol], is_local=True),
        lambda: fetcher(code_list=[symbol]),
        lambda: fetcher([symbol]),
    ):
        try:
            raw_payload = await _await_if_needed(invoke())
        except TypeError:
            continue
        except Exception as exc:
            last_error = exc
            continue

        status_df = coerce_status_dataframe(raw_payload)
        if not status_df.empty:
            return status_df

    if last_error is not None:
        raise HTTPException(
            status_code=502,
            detail=f"拉取 history_stock_status 失败: {last_error}",
        ) from last_error

    raise HTTPException(
        status_code=404,
        detail=f"{symbol} 未返回有效 history_stock_status 数据",
    )


async def _fetch_trade_day_status_snapshot(
    request: Optional[Request],
    symbol: str,
    trade_day: date_type,
) -> BacktestHistoryStatusSnapshot:
    provider = await _get_provider_with_soft_fail_compat(request, "amazingdata")
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="回测要求强制接入 history_stock_status，但 AmazingData Provider 不可用",
        )

    status_df = await _fetch_history_stock_status_dataframe(provider, symbol)
    try:
        snapshot = extract_trade_day_status_snapshot(
            status_df,
            symbol=symbol,
            trade_day=trade_day,
        )
    except HistoryStatusOverlayError as exc:
        status_code = 404 if exc.not_found else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    logger.info(
        f"回测历史状态已接入: symbol={symbol}, trade_day={trade_day}, "
        f"high_limited={snapshot.high_limited}, low_limited={snapshot.low_limited}, "
        f"is_suspended={snapshot.is_suspended}"
    )
    return snapshot


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


class TTradingBacktestRequest(BaseModel):
    """做T真实回测请求"""

    symbol: str = Field(..., min_length=1, description="股票代码")
    strategies: list[str] = Field(..., min_length=1, description="策略列表")
    trade_date: Optional[str] = Field(default=None, description="交易日期 YYYY-MM-DD")
    initial_capital: float = Field(default=100000.0, gt=0, description="初始资金")
    base_position_ratio: float = Field(
        default=50.0,
        ge=0.0,
        le=100.0,
        description="底仓占比（视为昨日持仓，可用于当日卖出）",
    )
    position_ratio: float = Field(default=50.0, ge=5.0, le=100.0, description="单次开仓资金占比")
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0, description="最小置信度")
    max_trades: int = Field(default=12, ge=1, le=200, description="最大交易次数")


class TTradingBacktestTrade(BaseModel):
    """做T回测交易记录"""

    id: str
    time: str
    direction: Literal["buy", "sell"]
    price: float
    quantity: int
    strategy: str
    reason: str
    profit_pct: Optional[float] = None


class TTradingBacktestBlockedEvent(BaseModel):
    """做T回测未成交约束记录。"""

    time: str
    direction: Literal["buy", "sell"]
    strategy: str
    reason_code: str
    reason: str


class TTradingBacktestBlockedSummaryItem(BaseModel):
    """做T回测阻断统计项。"""

    code: str
    label: str
    count: int


class TTradingBacktestEquityPoint(BaseModel):
    """做T回测权益曲线点"""

    time: str
    equity: float


class TTradingBacktestResponse(BaseModel):
    """做T回测响应"""

    symbol: str
    trade_date: str
    strategies: list[str]
    total_profit_pct: float
    win_rate: float
    trade_count: int
    win_count: int
    lose_count: int
    avg_profit_loss_ratio: float
    max_drawdown: float
    trades: list[TTradingBacktestTrade]
    blocked_events: list[TTradingBacktestBlockedEvent]
    blocked_summary: dict[str, int]
    blocked_summary_zh: dict[str, int]
    blocked_summary_items: list[TTradingBacktestBlockedSummaryItem]
    equity_curve: list[TTradingBacktestEquityPoint]


BacktestStrategyFactory = Callable[[], Any]

BACKTEST_STRATEGY_GENERATORS: dict[str, BacktestStrategyFactory] = {
    "vwap_deviation": VWAPDeviationStrategy,
    "opening_breakout": OpeningBreakoutStrategy,
    "time_window": TimeWindowStrategy,
    "momentum_reversal": MomentumReversalStrategy,
    "ma_deviation": MADeviationSignalGenerator,
    "support_resistance": SupportResistanceSignalGenerator,
    "grid": GridSignalGenerator,
    "volume_price": VolumePriceSignalGenerator,
}


def _resolve_backtest_trade_date(raw_date: Optional[str]) -> date_type:
    """解析回测交易日。"""

    if not raw_date:
        return datetime.now().date()
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"trade_date 格式错误: {exc}") from exc


def _calculate_max_drawdown_pct(equity_curve: list[TTradingBacktestEquityPoint]) -> float:
    """根据权益曲线计算最大回撤百分比。"""

    if not equity_curve:
        return 0.0

    peak = equity_curve[0].equity
    max_drawdown = 0.0
    for point in equity_curve:
        if point.equity > peak:
            peak = point.equity
            continue
        if peak <= 0:
            continue
        drawdown = (peak - point.equity) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def _format_intraday_time(dt: datetime) -> str:
    """格式化分时时间。"""

    return dt.strftime("%H:%M")


def _build_intraday_dataframe(kline_result: "KLineDataResponse") -> pd.DataFrame:
    """将 K 线响应转换为回测使用的 DataFrame。"""

    rows: list[dict[str, Any]] = []
    for bar in kline_result.bars:
        if bar.timestamp <= 0:
            continue
        dt = datetime.fromtimestamp(bar.timestamp / 1000)
        rows.append(
            {
                "datetime": dt,
                "time": bar.time_str or _format_intraday_time(dt),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
                "amount": float(bar.amount or 0),
                "symbol": kline_result.symbol,
                "high_limited": float(bar.high_limited) if bar.high_limited is not None else None,
                "low_limited": float(bar.low_limited) if bar.low_limited is not None else None,
                "is_suspended": bool(bar.is_suspended) if bar.is_suspended is not None else False,
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)
    return df


def _create_backtest_config(
    symbol: str,
    min_confidence: float,
    position_ratio: float,
    max_trades: int,
) -> TTradingConfig:
    """构造做T回测运行配置。"""

    return TTradingConfig(
        id=f"backtest-{uuid4().hex[:8]}",
        name="TTrading Backtest",
        symbol=symbol,
        trading_position_ratio=position_ratio,
        min_success_rate=max(min_confidence, 0.3),
        max_daily_trades=max_trades,
    )


def _blocked_reason_text(reason_code: str) -> str:
    return get_blocked_reason_label(reason_code)


def _compose_backtest_result(
    *,
    initial_capital: float,
    cash: float,
    sellable_qty: int,
    intraday_bought_qty: int,
    last_close: float,
    trades: list[TTradingBacktestTrade],
    blocked_events: list[TTradingBacktestBlockedEvent],
    blocked_summary: dict[str, int],
    equity_curve: list[TTradingBacktestEquityPoint],
    realized_profit_pct: list[float],
) -> dict[str, Any]:
    final_sellable_qty = sellable_qty + intraday_bought_qty
    final_equity = cash + final_sellable_qty * last_close
    total_profit_pct = (final_equity - initial_capital) / initial_capital * 100

    win_values = [value for value in realized_profit_pct if value > 0]
    lose_values = [abs(value) for value in realized_profit_pct if value < 0]
    win_count = len(win_values)
    lose_count = len(lose_values)
    closed_count = len(realized_profit_pct)
    win_rate = (win_count / closed_count * 100) if closed_count > 0 else 0.0

    if win_values and lose_values:
        avg_profit_loss_ratio = (sum(win_values) / len(win_values)) / (
            sum(lose_values) / len(lose_values)
        )
    elif win_values:
        avg_profit_loss_ratio = 999.0
    else:
        avg_profit_loss_ratio = 0.0

    normalized_summary = {code: int(count) for code, count in blocked_summary.items()}
    blocked_summary_items = [
        TTradingBacktestBlockedSummaryItem(**item)
        for item in build_blocked_summary_items(normalized_summary)
    ]

    return {
        "total_profit_pct": round(total_profit_pct, 4),
        "win_rate": round(win_rate, 4),
        "trade_count": len(trades),
        "win_count": win_count,
        "lose_count": lose_count,
        "avg_profit_loss_ratio": round(avg_profit_loss_ratio, 4),
        "max_drawdown": round(_calculate_max_drawdown_pct(equity_curve), 4),
        "trades": trades,
        "blocked_events": blocked_events,
        "blocked_summary": normalized_summary,
        "blocked_summary_zh": build_blocked_summary_zh(normalized_summary),
        "blocked_summary_items": blocked_summary_items,
        "equity_curve": equity_curve,
    }


def _in_trading_session(time_label: str) -> bool:
    try:
        minute = datetime.strptime(time_label, "%H:%M").time()
    except ValueError:
        return False

    morning_open = time(9, 30)
    morning_close = time(11, 30)
    afternoon_open = time(13, 0)
    afternoon_close = time(15, 0)
    return (morning_open <= minute <= morning_close) or (
        afternoon_open <= minute <= afternoon_close
    )


def _as_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _is_a_share_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper().replace("-", "").replace("_", "")
    if not normalized:
        return False

    def _is_stock_code(code_part: str, market: Optional[str] = None) -> bool:
        if not (code_part.isdigit() and len(code_part) == 6):
            return False

        prefix = code_part[:3]
        if market == "SH":
            return prefix in {"600", "601", "603", "605", "688", "689"}
        if market == "SZ":
            return prefix in {"000", "001", "002", "003", "300", "301"}
        if market == "BJ":
            return code_part.startswith(("4", "8"))
        return prefix in {
            "000",
            "001",
            "002",
            "003",
            "300",
            "301",
            "600",
            "601",
            "603",
            "605",
            "688",
            "689",
        } or code_part.startswith(("4", "8"))

    if "." in normalized:
        code_part, market = normalized.split(".", 1)
        return market in {"SH", "SZ", "BJ"} and _is_stock_code(code_part, market)

    if normalized.endswith(("SH", "SZ", "BJ")) and len(normalized) > 2:
        return _is_stock_code(normalized[:-2], normalized[-2:])

    if normalized.startswith(("SH", "SZ", "BJ")) and len(normalized) > 2:
        return _is_stock_code(normalized[2:], normalized[:2])

    return _is_stock_code(normalized)


def _resolve_ttrading_backtest_mode() -> TTradingBacktestMode:
    try:
        from core.config import get_config

        config = get_config()
        return cast(TTradingBacktestMode, config.strategy_center.ttrading_backtest_mode)
    except Exception as exc:
        logger.debug(f"读取做T回测模式配置失败，使用默认模式: {exc}")

    return DEFAULT_TTRADING_BACKTEST_MODE


def _simulate_ttrading_backtest(
    bars_df: pd.DataFrame,
    symbol: str,
    strategy_keys: list[str],
    initial_capital: float,
    base_position_ratio: float,
    position_ratio: float,
    min_confidence: float,
    max_trades: int,
) -> dict[str, Any]:
    """使用真实分钟行情执行做T回测（含 T+1 / 涨跌停 / 停牌约束）。"""
    max_blocked_events = 200

    analyzer = CompositeIntradayAnalyzer()
    generators = [BACKTEST_STRATEGY_GENERATORS[key]() for key in strategy_keys]
    config = _create_backtest_config(symbol, min_confidence, position_ratio, max_trades)
    cost_config = TradingCostConfig()

    cash = float(initial_capital)
    closed_trades = 0

    # 底仓（视作昨日持仓，可当日卖出）
    first_price = float(bars_df.iloc[0]["open"] or bars_df.iloc[0]["close"])
    base_position_qty = 0
    base_cost_price = first_price

    if first_price > 0 and base_position_ratio > 0:
        base_budget = initial_capital * (base_position_ratio / 100.0)
        base_quantity = int(base_budget / first_price / 100) * 100
        if base_quantity >= 100:
            amount = base_quantity * first_price
            buy_cost = amount + cost_config.calc_buy_cost(amount)
            if buy_cost <= cash:
                cash -= buy_cost
                base_position_qty = base_quantity

    sellable_qty = base_position_qty  # 可卖：仅昨日持仓
    intraday_bought_qty = 0  # 当日买入，T+1 不可卖

    trades: list[TTradingBacktestTrade] = []
    blocked_events: list[TTradingBacktestBlockedEvent] = []
    blocked_summary: dict[str, int] = {}
    equity_curve: list[TTradingBacktestEquityPoint] = []
    realized_profit_pct: list[float] = []

    for idx in range(len(bars_df)):
        bar_row = bars_df.iloc[idx]
        current_price = float(bar_row["close"])
        bar_time = str(bar_row["time"])
        total_position_qty = sellable_qty + intraday_bought_qty

        equity_curve.append(
            TTradingBacktestEquityPoint(
                time=bar_time,
                equity=round(cash + total_position_qty * current_price, 2),
            )
        )

        # 指标预热：至少使用 20 根 K 线计算
        if idx < 20 or closed_trades >= max_trades:
            continue

        if not _in_trading_session(bar_time):
            continue

        bar_volume = float(bar_row.get("volume", 0))
        is_suspended = bool(bar_row.get("is_suspended", False))
        if is_suspended or bar_volume <= 0 or current_price <= 0:
            blocked_summary["market_untradable"] = blocked_summary.get("market_untradable", 0) + 1
            continue

        high_limited = _as_optional_float(bar_row.get("high_limited"))
        low_limited = _as_optional_float(bar_row.get("low_limited"))
        at_high_limit = high_limited is not None and current_price >= high_limited * 0.9999
        at_low_limit = low_limited is not None and current_price <= low_limited * 1.0001

        analysis_df = bars_df.iloc[: idx + 1]
        analysis_map = analyzer.analyze_all(analysis_df, current_price)
        analysis_results = list(analysis_map.values())

        signals: list[TTradingSignal] = []
        for generator in generators:
            try:
                signals.extend(generator.generate(analysis_results, config, current_price))
            except Exception as exc:
                logger.debug(f"信号生成器执行失败: {exc}")

        if not signals:
            continue

        candidate_signals = sorted(
            (signal for signal in signals if signal.confidence >= min_confidence),
            key=lambda signal: signal.confidence,
            reverse=True,
        )
        if not candidate_signals:
            continue

        for signal in candidate_signals:
            signal_strategy = signal.signal_type or "unknown"
            signal_reason = signal.reason or "策略触发"

            def _record_blocked(reason_code: str, reason_text: str) -> None:
                blocked_summary[reason_code] = blocked_summary.get(reason_code, 0) + 1
                if len(blocked_events) >= max_blocked_events:
                    return
                blocked_events.append(
                    TTradingBacktestBlockedEvent(
                        time=bar_time,
                        direction="sell" if signal.direction == SignalDirection.SELL else "buy",
                        strategy=signal_strategy,
                        reason_code=reason_code,
                        reason=reason_text,
                    )
                )

            if signal.direction == SignalDirection.SELL:
                # T+1 约束：仅可卖昨日底仓（sellable_qty）
                if sellable_qty < 100:
                    _record_blocked("t1_no_sellable", _blocked_reason_text("t1_no_sellable"))
                    continue
                # 跌停限制：跌停价附近视为无法卖出
                if at_low_limit:
                    _record_blocked("low_limit_block", _blocked_reason_text("low_limit_block"))
                    continue

                sell_qty = int((sellable_qty * (position_ratio / 100.0)) / 100) * 100
                if sell_qty < 100:
                    sell_qty = (sellable_qty // 100) * 100
                if sell_qty < 100:
                    _record_blocked(
                        "sell_qty_too_small", _blocked_reason_text("sell_qty_too_small")
                    )
                    continue

                amount = sell_qty * current_price
                sell_income = amount - cost_config.calc_sell_cost(amount)
                cash += sell_income
                sellable_qty -= sell_qty

                profit_pct = (
                    (current_price - base_cost_price) / base_cost_price * 100
                    if base_cost_price > 0
                    else 0.0
                )
                realized_profit_pct.append(profit_pct)
                closed_trades += 1

                trades.append(
                    TTradingBacktestTrade(
                        id=f"sell-{uuid4().hex[:8]}",
                        time=bar_time,
                        direction="sell",
                        price=round(current_price, 3),
                        quantity=sell_qty,
                        strategy=signal_strategy,
                        reason=signal_reason,
                        profit_pct=round(profit_pct, 3),
                    )
                )
                break

            if signal.direction == SignalDirection.BUY:
                # 涨停限制：涨停价附近视为无法买入
                if at_high_limit:
                    _record_blocked("high_limit_block", _blocked_reason_text("high_limit_block"))
                    continue

                budget = cash * (position_ratio / 100.0)
                buy_qty = int(budget / current_price / 100) * 100
                if buy_qty < 100:
                    _record_blocked("buy_qty_too_small", _blocked_reason_text("buy_qty_too_small"))
                    continue

                amount = buy_qty * current_price
                buy_cost = amount + cost_config.calc_buy_cost(amount)
                if buy_cost > cash:
                    _record_blocked("insufficient_cash", _blocked_reason_text("insufficient_cash"))
                    continue

                cash -= buy_cost
                intraday_bought_qty += buy_qty  # 当日买入份额不可当日卖出

                trades.append(
                    TTradingBacktestTrade(
                        id=f"buy-{uuid4().hex[:8]}",
                        time=bar_time,
                        direction="buy",
                        price=round(current_price, 3),
                        quantity=buy_qty,
                        strategy=signal_strategy,
                        reason=signal_reason,
                    )
                )
                break

    return _compose_backtest_result(
        initial_capital=initial_capital,
        cash=cash,
        sellable_qty=sellable_qty,
        intraday_bought_qty=intraday_bought_qty,
        last_close=float(bars_df.iloc[-1]["close"]),
        trades=trades,
        blocked_events=blocked_events,
        blocked_summary=blocked_summary,
        equity_curve=equity_curve,
        realized_profit_pct=realized_profit_pct,
    )


class TTradingBacktestExecutor(Protocol):
    """做T回测执行器协议。"""

    name: TTradingBacktestMode

    def execute(self, context: TTradingBacktestContext) -> dict[str, Any]:
        """执行回测并返回统一结果字典。"""


class LegacySimExecutor:
    """历史模拟执行器（现网主结果口径）。"""

    name: TTradingBacktestMode = "legacy"

    def execute(self, context: TTradingBacktestContext) -> dict[str, Any]:
        return _simulate_ttrading_backtest(
            bars_df=context.bars_df,
            symbol=context.symbol,
            strategy_keys=context.strategy_keys,
            initial_capital=context.initial_capital,
            base_position_ratio=context.base_position_ratio,
            position_ratio=context.position_ratio,
            min_confidence=context.min_confidence,
            max_trades=context.max_trades,
        )


if HAS_BACKTRADER and bt is not None:

    class _TTradingStatusFeed(bt.feeds.PandasData):  # type: ignore[misc]
        """携带状态约束字段的 Backtrader 数据源。"""

        lines = ("high_limited", "low_limited", "is_suspended")
        params = (
            ("datetime", None),
            ("open", "open"),
            ("high", "high"),
            ("low", "low"),
            ("close", "close"),
            ("volume", "volume"),
            ("openinterest", -1),
            ("high_limited", "high_limited"),
            ("low_limited", "low_limited"),
            ("is_suspended", "is_suspended"),
        )

    class _BacktraderTTradingStrategy(bt.Strategy):  # type: ignore[misc]
        """Backtrader 做T执行策略（保持与 legacy 口径一致）。"""

        params = (
            ("symbol", ""),
            ("strategy_keys", ()),
            ("initial_capital", 100000.0),
            ("base_position_ratio", 50.0),
            ("position_ratio", 50.0),
            ("min_confidence", 0.6),
            ("max_trades", 12),
            ("max_blocked_events", 200),
            ("result_holder", None),
        )

        def __init__(self) -> None:
            self._analyzer = CompositeIntradayAnalyzer()
            self._generators = [BACKTEST_STRATEGY_GENERATORS[key]() for key in self.p.strategy_keys]
            self._config = _create_backtest_config(
                symbol=str(self.p.symbol),
                min_confidence=float(self.p.min_confidence),
                position_ratio=float(self.p.position_ratio),
                max_trades=int(self.p.max_trades),
            )
            self._cost_config = TradingCostConfig()
            self._cash = float(self.p.initial_capital)
            self._closed_trades = 0
            self._base_cost_price = 0.0
            self._sellable_qty = 0
            self._intraday_bought_qty = 0
            self._base_initialized = False

            self._history_rows: list[dict[str, Any]] = []
            self._trades: list[TTradingBacktestTrade] = []
            self._blocked_events: list[TTradingBacktestBlockedEvent] = []
            self._blocked_summary: dict[str, int] = {}
            self._equity_curve: list[TTradingBacktestEquityPoint] = []
            self._realized_profit_pct: list[float] = []

        def _record_blocked(
            self,
            *,
            bar_time: str,
            direction: Literal["buy", "sell"],
            strategy: str,
            reason_code: str,
        ) -> None:
            self._blocked_summary[reason_code] = self._blocked_summary.get(reason_code, 0) + 1
            if len(self._blocked_events) >= int(self.p.max_blocked_events):
                return
            self._blocked_events.append(
                TTradingBacktestBlockedEvent(
                    time=bar_time,
                    direction=direction,
                    strategy=strategy,
                    reason_code=reason_code,
                    reason=_blocked_reason_text(reason_code),
                )
            )

        def next(self) -> None:
            bar_dt = self.data.datetime.datetime(0)
            bar_time = _format_intraday_time(bar_dt)
            current_price = float(self.data.close[0])
            open_price = float(self.data.open[0])
            high_price = float(self.data.high[0])
            low_price = float(self.data.low[0])
            bar_volume = float(self.data.volume[0])

            high_limited = _as_optional_float(getattr(self.data, "high_limited")[0])
            low_limited = _as_optional_float(getattr(self.data, "low_limited")[0])
            suspended_value = _as_optional_float(getattr(self.data, "is_suspended")[0])
            is_suspended = bool(int(suspended_value)) if suspended_value is not None else False

            if not self._base_initialized:
                first_price = open_price if open_price > 0 else current_price
                self._base_cost_price = first_price
                if first_price > 0 and float(self.p.base_position_ratio) > 0:
                    base_budget = float(self.p.initial_capital) * (
                        float(self.p.base_position_ratio) / 100.0
                    )
                    base_quantity = int(base_budget / first_price / 100) * 100
                    if base_quantity >= 100:
                        amount = base_quantity * first_price
                        buy_cost = amount + self._cost_config.calc_buy_cost(amount)
                        if buy_cost <= self._cash:
                            self._cash -= buy_cost
                            self._sellable_qty = base_quantity
                self._base_initialized = True

            self._history_rows.append(
                {
                    "datetime": bar_dt,
                    "time": bar_time,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": current_price,
                    "volume": bar_volume,
                    "high_limited": high_limited,
                    "low_limited": low_limited,
                    "is_suspended": is_suspended,
                }
            )

            total_position_qty = self._sellable_qty + self._intraday_bought_qty
            self._equity_curve.append(
                TTradingBacktestEquityPoint(
                    time=bar_time,
                    equity=round(self._cash + total_position_qty * current_price, 2),
                )
            )

            if len(self._history_rows) <= 20 or self._closed_trades >= int(self.p.max_trades):
                return
            if not _in_trading_session(bar_time):
                return

            if is_suspended or bar_volume <= 0 or current_price <= 0:
                self._blocked_summary["market_untradable"] = (
                    self._blocked_summary.get("market_untradable", 0) + 1
                )
                return

            at_high_limit = high_limited is not None and current_price >= high_limited * 0.9999
            at_low_limit = low_limited is not None and current_price <= low_limited * 1.0001

            analysis_df = pd.DataFrame(self._history_rows)
            analysis_map = self._analyzer.analyze_all(analysis_df, current_price)
            analysis_results = list(analysis_map.values())

            signals: list[TTradingSignal] = []
            for generator in self._generators:
                try:
                    signals.extend(
                        generator.generate(analysis_results, self._config, current_price)
                    )
                except Exception as exc:
                    logger.debug(f"Backtrader 信号生成器执行失败: {exc}")

            if not signals:
                return

            candidate_signals = sorted(
                (signal for signal in signals if signal.confidence >= float(self.p.min_confidence)),
                key=lambda signal: signal.confidence,
                reverse=True,
            )
            if not candidate_signals:
                return

            for signal in candidate_signals:
                signal_strategy = signal.signal_type or "unknown"
                signal_reason = signal.reason or "策略触发"

                if signal.direction == SignalDirection.SELL:
                    if self._sellable_qty < 100:
                        self._record_blocked(
                            bar_time=bar_time,
                            direction="sell",
                            strategy=signal_strategy,
                            reason_code="t1_no_sellable",
                        )
                        continue
                    if at_low_limit:
                        self._record_blocked(
                            bar_time=bar_time,
                            direction="sell",
                            strategy=signal_strategy,
                            reason_code="low_limit_block",
                        )
                        continue

                    sell_qty = (
                        int((self._sellable_qty * (float(self.p.position_ratio) / 100.0)) / 100)
                        * 100
                    )
                    if sell_qty < 100:
                        sell_qty = (self._sellable_qty // 100) * 100
                    if sell_qty < 100:
                        self._record_blocked(
                            bar_time=bar_time,
                            direction="sell",
                            strategy=signal_strategy,
                            reason_code="sell_qty_too_small",
                        )
                        continue

                    amount = sell_qty * current_price
                    sell_income = amount - self._cost_config.calc_sell_cost(amount)
                    self._cash += sell_income
                    self._sellable_qty -= sell_qty

                    profit_pct = (
                        (current_price - self._base_cost_price) / self._base_cost_price * 100
                        if self._base_cost_price > 0
                        else 0.0
                    )
                    self._realized_profit_pct.append(profit_pct)
                    self._closed_trades += 1
                    self._trades.append(
                        TTradingBacktestTrade(
                            id=f"sell-{uuid4().hex[:8]}",
                            time=bar_time,
                            direction="sell",
                            price=round(current_price, 3),
                            quantity=sell_qty,
                            strategy=signal_strategy,
                            reason=signal_reason,
                            profit_pct=round(profit_pct, 3),
                        )
                    )
                    break

                if signal.direction == SignalDirection.BUY:
                    if at_high_limit:
                        self._record_blocked(
                            bar_time=bar_time,
                            direction="buy",
                            strategy=signal_strategy,
                            reason_code="high_limit_block",
                        )
                        continue

                    budget = self._cash * (float(self.p.position_ratio) / 100.0)
                    buy_qty = int(budget / current_price / 100) * 100
                    if buy_qty < 100:
                        self._record_blocked(
                            bar_time=bar_time,
                            direction="buy",
                            strategy=signal_strategy,
                            reason_code="buy_qty_too_small",
                        )
                        continue

                    amount = buy_qty * current_price
                    buy_cost = amount + self._cost_config.calc_buy_cost(amount)
                    if buy_cost > self._cash:
                        self._record_blocked(
                            bar_time=bar_time,
                            direction="buy",
                            strategy=signal_strategy,
                            reason_code="insufficient_cash",
                        )
                        continue

                    self._cash -= buy_cost
                    self._intraday_bought_qty += buy_qty
                    self._trades.append(
                        TTradingBacktestTrade(
                            id=f"buy-{uuid4().hex[:8]}",
                            time=bar_time,
                            direction="buy",
                            price=round(current_price, 3),
                            quantity=buy_qty,
                            strategy=signal_strategy,
                            reason=signal_reason,
                        )
                    )
                    break

        def stop(self) -> None:
            result_holder = self.p.result_holder if isinstance(self.p.result_holder, dict) else None
            if result_holder is None:
                return
            last_close = float(self._history_rows[-1]["close"]) if self._history_rows else 0.0
            result_holder["result"] = _compose_backtest_result(
                initial_capital=float(self.p.initial_capital),
                cash=self._cash,
                sellable_qty=self._sellable_qty,
                intraday_bought_qty=self._intraday_bought_qty,
                last_close=last_close,
                trades=self._trades,
                blocked_events=self._blocked_events,
                blocked_summary=self._blocked_summary,
                equity_curve=self._equity_curve,
                realized_profit_pct=self._realized_profit_pct,
            )


class BacktraderTTradingExecutor:
    """Backtrader 执行器。"""

    name: TTradingBacktestMode = "backtrader"

    def execute(self, context: TTradingBacktestContext) -> dict[str, Any]:
        if not HAS_BACKTRADER or bt is None:
            raise HTTPException(
                status_code=503, detail="backtrader 不可用，无法执行 backtrader 模式"
            )
        if context.bars_df.empty:
            raise HTTPException(status_code=404, detail="无可用分钟数据")

        bars_df = context.bars_df.copy()
        if "datetime" in bars_df.columns:
            bars_df["datetime"] = pd.to_datetime(bars_df["datetime"], errors="coerce")
            bars_df = bars_df.dropna(subset=["datetime"]).set_index("datetime")
        elif not isinstance(bars_df.index, pd.DatetimeIndex):
            raise HTTPException(
                status_code=502, detail="回测分钟数据缺少 datetime 字段，无法执行 backtrader"
            )

        bars_df = bars_df.sort_index()
        if bars_df.empty:
            raise HTTPException(status_code=404, detail="分钟数据为空，无法执行 backtrader 回测")

        for field in ("open", "high", "low", "close", "volume", "high_limited", "low_limited"):
            if field not in bars_df.columns:
                bars_df[field] = 0.0
        if "is_suspended" not in bars_df.columns:
            bars_df["is_suspended"] = 0
        bars_df["is_suspended"] = bars_df["is_suspended"].astype(int)

        result_holder: dict[str, Any] = {}
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(context.initial_capital)
        cerebro.adddata(_TTradingStatusFeed(dataname=bars_df), name=context.symbol)
        cerebro.addstrategy(
            _BacktraderTTradingStrategy,
            symbol=context.symbol,
            strategy_keys=tuple(context.strategy_keys),
            initial_capital=context.initial_capital,
            base_position_ratio=context.base_position_ratio,
            position_ratio=context.position_ratio,
            min_confidence=context.min_confidence,
            max_trades=context.max_trades,
            result_holder=result_holder,
        )
        cerebro.run()

        result = result_holder.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("backtrader 执行完成但未返回有效结果")
        return result


def _build_shadow_diff(
    legacy_result: dict[str, Any],
    backtrader_result: dict[str, Any],
) -> dict[str, Any]:
    metric_diff = {
        "total_profit_pct": abs(
            float(legacy_result.get("total_profit_pct", 0.0))
            - float(backtrader_result.get("total_profit_pct", 0.0))
        ),
        "win_rate": abs(
            float(legacy_result.get("win_rate", 0.0))
            - float(backtrader_result.get("win_rate", 0.0))
        ),
        "trade_count": abs(
            float(legacy_result.get("trade_count", 0.0))
            - float(backtrader_result.get("trade_count", 0.0))
        ),
        "max_drawdown": abs(
            float(legacy_result.get("max_drawdown", 0.0))
            - float(backtrader_result.get("max_drawdown", 0.0))
        ),
    }

    legacy_blocked = cast(dict[str, int], legacy_result.get("blocked_summary", {}))
    backtrader_blocked = cast(dict[str, int], backtrader_result.get("blocked_summary", {}))
    all_codes = sorted(set(legacy_blocked.keys()) | set(backtrader_blocked.keys()))
    blocked_code_diff = {
        code: abs(int(legacy_blocked.get(code, 0)) - int(backtrader_blocked.get(code, 0)))
        for code in all_codes
    }
    metric_diff["blocked_total"] = float(sum(blocked_code_diff.values()))

    exceeded = {
        key: value
        for key, value in metric_diff.items()
        if value > float(SHADOW_DIFF_THRESHOLDS.get(key, float("inf")))
    }
    return {
        "metric_diff": metric_diff,
        "blocked_code_diff": blocked_code_diff,
        "thresholds": SHADOW_DIFF_THRESHOLDS,
        "exceeded": exceeded,
        "within_threshold": not bool(exceeded),
    }


def _to_ttrading_backtest_response(
    *,
    context: TTradingBacktestContext,
    result: dict[str, Any],
) -> TTradingBacktestResponse:
    blocked_summary = cast(dict[str, int], result.get("blocked_summary", {}))
    blocked_summary_zh = cast(dict[str, int], result.get("blocked_summary_zh", {}))
    blocked_summary_items = result.get("blocked_summary_items") or [
        TTradingBacktestBlockedSummaryItem(**item)
        for item in build_blocked_summary_items(blocked_summary)
    ]

    return TTradingBacktestResponse(
        symbol=context.symbol,
        trade_date=context.trade_day.strftime("%Y-%m-%d"),
        strategies=context.strategy_keys,
        total_profit_pct=float(result.get("total_profit_pct", 0.0)),
        win_rate=float(result.get("win_rate", 0.0)),
        trade_count=int(result.get("trade_count", 0)),
        win_count=int(result.get("win_count", 0)),
        lose_count=int(result.get("lose_count", 0)),
        avg_profit_loss_ratio=float(result.get("avg_profit_loss_ratio", 0.0)),
        max_drawdown=float(result.get("max_drawdown", 0.0)),
        trades=cast(list[TTradingBacktestTrade], result.get("trades", [])),
        blocked_events=cast(list[TTradingBacktestBlockedEvent], result.get("blocked_events", [])),
        blocked_summary=blocked_summary,
        blocked_summary_zh=blocked_summary_zh,
        blocked_summary_items=cast(list[TTradingBacktestBlockedSummaryItem], blocked_summary_items),
        equity_curve=cast(list[TTradingBacktestEquityPoint], result.get("equity_curve", [])),
    )


def _select_ttrading_executor(
    mode: TTradingBacktestMode,
) -> tuple[TTradingBacktestExecutor, Optional[TTradingBacktestExecutor]]:
    legacy_executor = LegacySimExecutor()
    backtrader_executor = BacktraderTTradingExecutor()
    if mode == "legacy":
        return legacy_executor, None
    if mode == "backtrader":
        return backtrader_executor, None
    return legacy_executor, backtrader_executor


async def _prepare_ttrading_backtest_context(
    payload: TTradingBacktestRequest,
    request: Optional[Request],
) -> TTradingBacktestContext:
    symbol = payload.symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol 不能为空")

    if not payload.strategies:
        raise HTTPException(status_code=400, detail="至少选择一个策略")

    unknown_strategies = sorted(
        set(
            strategy
            for strategy in payload.strategies
            if strategy not in BACKTEST_STRATEGY_GENERATORS
        )
    )
    if unknown_strategies:
        raise HTTPException(
            status_code=400, detail=f"不支持的策略: {', '.join(unknown_strategies)}"
        )

    trade_day = _resolve_backtest_trade_date(payload.trade_date)
    start_dt = datetime.combine(trade_day, time(9, 30))
    end_dt = datetime.combine(trade_day, time(15, 0))

    kline_response = await get_kline_data(
        symbol=symbol,
        request=request,
        period="1m",
        from_ts=int(start_dt.timestamp() * 1000),
        to_ts=int(end_dt.timestamp() * 1000),
        count=480,
    )
    bars_df = _build_intraday_dataframe(kline_response)
    if bars_df.empty:
        raise HTTPException(status_code=404, detail=f"{trade_day} 无可用分钟数据")
    if len(bars_df) < 30:
        raise HTTPException(status_code=400, detail="分钟数据不足（<30），无法执行回测")

    if _is_a_share_symbol(symbol):
        status_snapshot = await _fetch_trade_day_status_snapshot(
            request=request,
            symbol=symbol,
            trade_day=trade_day,
        )
        bars_df = apply_trade_day_status_snapshot(bars_df, status_snapshot)
    else:
        logger.info(f"{symbol} 非A股标的，做T回测跳过强制 history_stock_status 约束")

    return TTradingBacktestContext(
        symbol=symbol,
        trade_day=trade_day,
        bars_df=bars_df,
        strategy_keys=payload.strategies,
        initial_capital=payload.initial_capital,
        base_position_ratio=payload.base_position_ratio,
        position_ratio=payload.position_ratio,
        min_confidence=payload.min_confidence,
        max_trades=payload.max_trades,
    )


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
            cast(IntradayDataProvider, data_provider),
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
    request: Request = cast(Request, None),
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

        engine = get_ttrading_engine(symbol, cast(Optional[IntradayDataProvider], data_provider))

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

        await engine.start(config, cast(Optional[IntradayDataProvider], data_provider))

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
async def get_datasource_status(request: Request = cast(Request, None)):
    """获取数据源状态"""
    status = {
        "miniqmt_available": MINIQMT_AVAILABLE,
        "miniqmt_connected": False,
        "active_provider": "mock",
    }

    if not MINIQMT_AVAILABLE:
        return status

    # 先做进程级可达性检测，避免“客户端未启动”时误报已连接。
    tcp_probe_result = _probe_miniqmt_tcp_connection()
    if isinstance(tcp_probe_result, tuple) and len(tcp_probe_result) == 3:
        reachable, probe_host, probe_port = tcp_probe_result
    else:
        # 兼容旧测试/旧调用方：允许只返回 bool。
        reachable = bool(tcp_probe_result)
        probe_host, probe_port = "127.0.0.1", 7777
    status["miniqmt_probe"] = {"host": probe_host, "port": probe_port, "reachable": reachable}
    if not reachable:
        return status

    # 状态接口只依据真实探活结果，不再依赖“可导入即连接”的本地标志位。
    connected = await _probe_miniqmt_actor_connection_compat(
        request,
        probe_host=probe_host,
        probe_port=probe_port,
    )
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
    request: Request,
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
    high_limited: Optional[float] = None  # 涨停价
    low_limited: Optional[float] = None  # 跌停价
    is_suspended: Optional[bool] = None  # 是否停牌


class KLineDataResponse(BaseModel):
    """K线数据响应"""

    symbol: str
    period: str
    bars: list[KLineBar]


@router.get("/kline/{symbol}", response_model=KLineDataResponse)
async def get_kline_data(
    symbol: str,
    request: Request = cast(Request, None),
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
                    if time_val is not None and hasattr(time_val, "timestamp"):
                        # pandas Timestamp 或 datetime 对象
                        ts_callable = getattr(time_val, "timestamp", None)
                        if not callable(ts_callable):
                            raise TypeError("timestamp is not callable")
                        ts = int(ts_callable() * 1000)
                        # 转换为 datetime
                        to_py = getattr(time_val, "to_pydatetime", None)
                        if callable(to_py):
                            dt = to_py()
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
                        high_limited=(
                            float(bar.get("high_limited"))
                            if bar.get("high_limited") is not None
                            else (
                                float(bar.get("HIGH_LIMITED"))
                                if bar.get("HIGH_LIMITED") is not None
                                else None
                            )
                        ),
                        low_limited=(
                            float(bar.get("low_limited"))
                            if bar.get("low_limited") is not None
                            else (
                                float(bar.get("LOW_LIMITED"))
                                if bar.get("LOW_LIMITED") is not None
                                else None
                            )
                        ),
                        is_suspended=bool(
                            bar.get("is_suspended")
                            if bar.get("is_suspended") is not None
                            else bar.get("IS_SUSP_SEC", False)
                        ),
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


@router.post("/backtest", response_model=TTradingBacktestResponse)
async def run_ttrading_backtest(
    payload: TTradingBacktestRequest,
    request: Request = cast(Request, None),
):
    """执行做T真实回测（分钟级）。"""
    context = await _prepare_ttrading_backtest_context(payload, request)
    mode = _resolve_ttrading_backtest_mode()
    primary_executor, shadow_executor = _select_ttrading_executor(mode)

    logger.info(
        f"做T回测执行模式={mode}, symbol={context.symbol}, trade_day={context.trade_day}, "
        f"strategies={context.strategy_keys}"
    )

    result = primary_executor.execute(context)

    if mode == "shadow" and shadow_executor is not None:
        try:
            shadow_result = shadow_executor.execute(context)
            shadow_diff = _build_shadow_diff(result, shadow_result)
            if shadow_diff["within_threshold"]:
                logger.info(
                    f"做T回测 shadow 对齐通过: symbol={context.symbol}, trade_day={context.trade_day}, "
                    f"diff={shadow_diff['metric_diff']}"
                )
            else:
                logger.warning(
                    f"做T回测 shadow 偏差超阈值: symbol={context.symbol}, trade_day={context.trade_day}, "
                    f"diff={shadow_diff['metric_diff']}, exceeded={shadow_diff['exceeded']}, "
                    f"blocked_diff={shadow_diff['blocked_code_diff']}"
                )
        except Exception as exc:
            logger.warning(
                f"做T回测 shadow 执行失败，已回退 legacy 结果: symbol={context.symbol}, "
                f"trade_day={context.trade_day}, error={exc}"
            )

    return _to_ttrading_backtest_response(context=context, result=result)
