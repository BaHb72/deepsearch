# encoding:utf-8
"""
AmazingData Provider - 子进程隔离实现。

通过 multiprocessing 子进程托管 AmazingData SDK，防止 SDK 异常影响主进程。
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from datetime import time as time_cls
from datetime import timedelta, timezone
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TypeVar, cast
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from deepsearch.infrastructure.providers.interfaces.base import DataProvider, DataProviderError
from deepsearch.ports.amazingdata_process import (
    AmazingDataLogoutRequest,
    ProcessCallResult,
    ProcessCommand,
)

from ..amazingdata_process_adapter import AmazingDataProcessAdapter
from ..amazingdata_process_pool import AmazingDataProcessPool, get_global_pool
from ..amazingdata_types import AmazingDataSecurityType
from ..common import DEFAULT_HIST_CODE_LIST_START, SubscriptionCallback
from ..config import (
    AmazingDataConfig,
    ProviderConfigLike,
    ensure_amazingdata_provider_config,
    resolve_local_cache_path,
)
from ..helpers import (
    _extract_symbol,
    _merge_board_metadata,
    _normalize_date_to_int,
    _records_need_board,
    normalize_stock_records,
)
from ..logging_utils import ProcessLoggerAdapter
from ..param_guards import (
    CacheParamMode,
    CachePolicy,
    normalize_security_type,
    validate_security_period,
)
from .alert_utils import collect_tgw_log_snippet, read_tgw_tail_lines, trigger_alert
from .login_flow import perform_login
from .subscription_tasks import ProcessSubscriptionCoordinator

# 安全导入SDK常量模块（仅包含枚举定义，不触发SDK初始化）
try:
    from AmazingData import constant as ad_constant

    _SDK_PERIOD_AVAILABLE = True
except ImportError:
    ad_constant = None  # type: ignore[assignment]
    _SDK_PERIOD_AVAILABLE = False


# 字符串到Period枚举的映射（用于IPC传递）
def _get_period_enum_map() -> Dict[str, Any]:
    """构建字符串到SDK Period枚举的映射表"""
    if not _SDK_PERIOD_AVAILABLE or ad_constant is None:
        return {}
    Period = ad_constant.Period
    return {
        # 日线
        "1d": Period.day,
        "day": Period.day,
        "daily": Period.day,
        # 周线
        "1w": Period.week,
        "week": Period.week,
        "weekly": Period.week,
        # 月线
        "1M": Period.month,
        "month": Period.month,
        "monthly": Period.month,
        # 分钟线
        "1m": Period.min1,
        "min1": Period.min1,
        "3m": Period.min3,
        "min3": Period.min3,
        "5m": Period.min5,
        "min5": Period.min5,
        "10m": Period.min10,
        "min10": Period.min10,
        "15m": Period.min15,
        "min15": Period.min15,
        "30m": Period.min30,
        "min30": Period.min30,
        "60m": Period.min60,
        "min60": Period.min60,
        "1h": Period.min60,
        "120m": Period.min120,
        "min120": Period.min120,
        "2h": Period.min120,
        # 季度/年
        "season": Period.season,
        "quarter": Period.season,
        "year": Period.year,
        "1y": Period.year,
    }


PERIOD_ENUM_MAP: Dict[str, Any] = _get_period_enum_map()

# 保留旧的别名映射用于兼容（当SDK不可用时回退）
PERIOD_ALIASES: Dict[str, str] = {
    "daily": "1d",
    "day": "1d",
    "1day": "1d",
    "weekly": "1w",
    "week": "1w",
    "1week": "1w",
    "monthly": "1M",
    "month": "1M",
    "1month": "1M",
}


def _resolve_period_to_enum(period_str: str) -> int | None:
    """将字符串period转换为SDK Period枚举值(int)，用于IPC传递

    根据SDK文档4.1.6，period参数类型为int，应传递Period.xxx.value
    """
    if not period_str:
        enum_obj = PERIOD_ENUM_MAP.get("1d") if PERIOD_ENUM_MAP else None
        return enum_obj.value if enum_obj is not None else None

    normalized = period_str.lower().strip()

    # 优先从枚举映射获取
    if PERIOD_ENUM_MAP:
        result = PERIOD_ENUM_MAP.get(normalized)
        if result is not None:
            return int(result.value)  # 返回int值

    # 回退：尝试别名转换后再查找
    alias = PERIOD_ALIASES.get(normalized, normalized)
    if PERIOD_ENUM_MAP:
        enum_obj = PERIOD_ENUM_MAP.get(alias)
        return enum_obj.value if enum_obj is not None else None

    return None


from ..query_manager import AmazingDataQueryManager
from ..subscription import SubscriptionInfo

TResult = TypeVar("TResult")


class SnapshotAlignPolicy(str, Enum):
    """历史快照对齐策略。"""

    NEAREST_PREV = "nearest_prev"
    STRICT = "strict"
    PASSTHROUGH = "passthrough"

    @classmethod
    def from_value(cls, value: "SnapshotAlignPolicy | str | None") -> "SnapshotAlignPolicy":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.NEAREST_PREV
        try:
            return cls(value)
        except ValueError:
            logger.warning("未知快照对齐策略 {}，回退为 nearest_prev", value)
            return cls.NEAREST_PREV


def _summarize_object(payload: object | None) -> str:
    """构造轻量级对象摘要，便于调试日志分析。"""

    if payload is None:
        return "None"
    if isinstance(payload, pd.DataFrame):
        try:
            return f"DataFrame{payload.shape}"
        except Exception:
            return "DataFrame"
    if isinstance(payload, Mapping):
        return f"Mapping(len={len(payload)})"
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return f"Sequence(len={len(payload)})"
    return type(payload).__name__


def _scalar_to_builtin(value: Any) -> Any:
    """Convert pandas/numpy scalars to JSON-serialisable builtin types."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).isoformat()
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        value = value.to_pytimedelta()  # type: ignore[attr-defined]
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, np.generic):  # type: ignore[attr-defined]
        return value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _dataframe_to_payload(frame: pd.DataFrame) -> Dict[str, Any]:
    """Serialise DataFrame to dict payload with safe scalar values."""
    if frame.empty:
        return {
            "columns": list(frame.columns),
            "records": [],
        }

    records: list[Dict[str, Any]] = []
    raw_records: list[Dict[str, Any]] = frame.to_dict(orient="records")  # type: ignore[assignment]
    for raw in raw_records:
        serialized = {key: _scalar_to_builtin(val) for key, val in raw.items()}
        records.append(serialized)
    return {
        "columns": list(frame.columns),
        "records": records,
    }


class AmazingDataLoginManager:
    # Helper to manage AmazingData login lifecycle and reconnection.

    def __init__(self, provider: "ProcessIsolatedAmazingDataProvider") -> None:
        self._provider = provider
        self._lock = asyncio.Lock()
        self._backoff_step = 0
        self._initial_delay = 1.0
        self._max_delay = 30.0
        self._backoff_base = 2.0

    def _next_delay(self) -> float:
        delay = min(self._initial_delay * (self._backoff_base**self._backoff_step), self._max_delay)
        self._backoff_step = min(self._backoff_step + 1, 10)
        return delay

    def record_success(self) -> None:
        self._backoff_step = 0

    async def ensure_ready(self) -> "AmazingDataProcessAdapter":
        async with self._lock:
            adapter = await self._provider._ensure_adapter()
            if not self._provider._initialized:
                started = await adapter.ensure_started()
                if not started:
                    raise DataProviderError("AmazingData worker start failed")
                await self._provider._perform_login(adapter)
                self._provider._initialized = True
            elif not self._provider.is_connected():
                await self._provider._perform_login(adapter)
                self._provider._initialized = True
            self.record_success()
            return adapter

    async def handle_authentication_failure(self, reason: str) -> None:
        async with self._lock:
            delay = self._next_delay()
            logger.warning(
                "AmazingData authentication issue detected; retry login in %.1fs: %s",
                delay,
                reason,
            )
            await asyncio.sleep(delay)
            self._provider._reset_connection_state(drop_adapter=False, reason=reason)
            adapter = await self._provider._ensure_adapter()
            started = await adapter.ensure_started()
            if not started:
                raise DataProviderError("AmazingData worker start failed")
            await self._provider._perform_login(adapter)
            self._provider._initialized = True
            self.record_success()


class ProcessIsolatedAmazingDataProvider(DataProvider):
    """基于子进程代理的 AmazingData 数据提供者。"""

    _LOGIN_LOCKS: Dict[str, asyncio.Lock] = {}
    _LOGIN_LOCKS_GUARD = threading.Lock()
    _LOGIN_STATE: Dict[str, Dict[str, float]] = {}
    _LOGIN_STATE_GUARD = threading.Lock()
    _LOGIN_DEDUP_WINDOW_SECONDS = 60.0
    _TRADING_CALENDAR_TTL_SECONDS = 600.0
    _LOCAL_TZ = ZoneInfo("Asia/Shanghai")
    _TRADING_WINDOWS: tuple[tuple[time_cls, time_cls], ...] = (
        (time_cls(9, 15), time_cls(9, 25)),
        (time_cls(9, 30), time_cls(11, 30)),
        (time_cls(13, 0), time_cls(15, 0)),
    )
    _AUTH_ERROR_KEYWORDS: Tuple[str, ...] = (
        "not login",
        "not logged",
        "login first",
        "authentication",
        "auth",
        "session expired",
        "session invalid",
        "token",
        "\u672a\u767b\u5f55",
        "\u767b\u5f55\u5931\u6548",
        "\u8ba4\u8bc1",
    )
    _API_MODE_ALIASES: ClassVar[dict[str, str]] = {
        "api": "kInternetMode",
        "internet": "kInternetMode",
        "internetmode": "kInternetMode",
        "kinternetmode": "kInternetMode",
        "apimodekinternetmode": "kInternetMode",
        "tgwapimodekinternetmode": "kInternetMode",
        "push": "kColocationMode",
        "colocation": "kColocationMode",
        "colocationmode": "kColocationMode",
        "kcolocationmode": "kColocationMode",
        "apimodekcolocationmode": "kColocationMode",
        "tgwapimodekcolocationmode": "kColocationMode",
    }

    @classmethod
    def _normalize_api_mode(cls, value: object | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            alias_key = "".join(ch for ch in text.lower() if ch.isalnum())
            alias = cls._API_MODE_ALIASES.get(alias_key)
            return alias or text
        try:
            numeric = int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return str(value)
        return str(numeric)

    def _set_login_api_mode(self, value: object | None) -> None:
        normalized = self._normalize_api_mode(value)
        if normalized is None and value not in (None, ""):
            logger.warning(
                "AmazingData api_mode %r normalized to None; falling back to default", value
            )
        elif normalized != value:
            logger.debug("AmazingData api_mode adjusted from %r to %r", value, normalized)
        self._login_api_mode = normalized

    def __init__(self, config: ProviderConfigLike) -> None:
        provider_config = ensure_amazingdata_provider_config(config)
        super().__init__(provider_config)
        self.config: AmazingDataConfig = provider_config
        self._initialized = False
        self._pool: AmazingDataProcessPool | None = None
        self._adapter: AmazingDataProcessAdapter | None = None
        self._datasource_id = self._build_datasource_id()
        self._proxy_config = self._build_proxy_config()
        self._login_api_mode: str | None = None  # type: ignore[no-redef]
        self._set_login_api_mode(self._resolve_initial_api_mode())
        self._connected: bool = False
        # 对于进程隔离Provider，SDK可用性由子进程管理，这里默认True表示会尝试加载
        self._sdk_available: bool = True
        self._degraded_mode: bool = False
        self._connected_since: datetime | None = None
        self._last_disconnect_at: datetime | None = None
        self._last_error: str | None = None
        self._last_health_status: Dict[str, Any] | None = None
        self._last_code_list_branch: str | None = None
        self._last_code_list_security_type: str | None = None
        poll_interval = self._resolve_subscription_poll_interval()
        batch_size = self._resolve_subscription_batch_size()
        self._subscription = ProcessSubscriptionCoordinator(
            self,
            poll_interval=poll_interval,
            batch_size=batch_size,
        )
        self._calendar_cache: dict[str, tuple[set[int], float]] = {}
        self._calendar_cache_lock = asyncio.Lock()
        self._login_manager = AmazingDataLoginManager(self)
        self._alerts: dict[str, list[dict[str, str]]] = {}
        safe_wrapper_module: ModuleType | None
        try:
            from .. import amazingdata_safe_wrapper as safe_wrapper_module
        except Exception:  # noqa: BLE001
            safe_wrapper_module = None
        if safe_wrapper_module is not None:
            wrapper_instance = getattr(safe_wrapper_module, "_global_wrapper", None)
            if wrapper_instance is not None:
                try:
                    wrapper_instance.register_subscription_bridge(self)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("AmazingData safe wrapper bridge registration failed: {}", exc)

    @property
    def _subscription_poll_interval(self) -> float:
        return self._subscription.poll_interval

    @_subscription_poll_interval.setter
    def _subscription_poll_interval(self, value: float) -> None:
        self._subscription.poll_interval = value

    @property
    def _subscription_batch_size(self) -> int:
        return self._subscription.batch_size

    @_subscription_batch_size.setter
    def _subscription_batch_size(self, value: int) -> None:
        self._subscription.batch_size = value

    @classmethod
    async def _acquire_global_login_lock(cls, key: str) -> asyncio.Lock:
        """跨实例串行化登录请求，避免并发触发底层 SDK 异常。"""

        loop = asyncio.get_running_loop()
        with cls._LOGIN_LOCKS_GUARD:
            lock = cls._LOGIN_LOCKS.get(key)
            if lock is None or getattr(lock, "_loop", None) is not loop:
                lock = asyncio.Lock()
                cls._LOGIN_LOCKS[key] = lock
        await lock.acquire()
        return lock

    @classmethod
    def _record_login_state(cls, key: str, *, success: bool) -> None:
        """记录最近一次登录结果，供幂等/防抖判断使用。"""

        now = time.monotonic()
        with cls._LOGIN_STATE_GUARD:
            state = cls._LOGIN_STATE.setdefault(key, {})
            if success:
                state["last_success"] = now
            else:
                state["last_failure"] = now

    def _is_worker_login_fresh(self, window_seconds: float) -> bool:
        """检查进程池中对应 worker 的登录是否仍在有效期内。"""

        pool = self._pool
        if not pool:
            return False
        try:
            status = pool.get_status()
        except Exception:
            return False
        entry = status.get("processes", {}).get(self._datasource_id)
        if not entry:
            return False
        if not entry.get("is_running"):
            return False
        iso_ts = entry.get("last_login_success_at")
        if not iso_ts:
            return False
        try:
            timestamp = datetime.fromisoformat(iso_ts)
        except Exception:
            return False
        now = datetime.now(timezone.utc)
        return now - timestamp <= timedelta(seconds=window_seconds)

    def _should_reuse_recent_login(self) -> bool:
        """若短时间内已有成功登录，则跳过重复登录并直接复用。"""

        window = self._LOGIN_DEDUP_WINDOW_SECONDS
        key = self._datasource_id
        now_mono = time.monotonic()
        with self.__class__._LOGIN_STATE_GUARD:
            state = dict(self.__class__._LOGIN_STATE.get(key, {}))
        last_success = float(state.get("last_success", 0.0))
        if last_success and now_mono - last_success <= window:
            return self._is_worker_login_fresh(window)
        return False

    def _build_datasource_id(self) -> str:
        username = getattr(self.config, "username", "") or "anonymous"
        host = getattr(self.config, "host", "") or "unknown"
        port = getattr(self.config, "port", 0)
        return f"amazingdata::{username}@{host}:{port}"

    def _build_proxy_config(self) -> Dict[str, Any]:
        proxy_config: Dict[str, Any] = {}
        # 检查多个可能的配置位置
        python_candidate = getattr(
            self.config, "python_interpreter_path", ""
        ) or self.config.config.get("python_interpreter_path")
        # 也检查嵌套的 connection 块
        if not python_candidate:
            connection_cfg = self.config.config.get("connection", {})
            if isinstance(connection_cfg, dict):
                python_candidate = connection_cfg.get("python_interpreter_path")
        python_path = str(python_candidate or "").strip()
        if python_path:
            proxy_config["python_executable"] = python_path
        worker_env = getattr(self.config, "worker_env", None)
        if worker_env:
            proxy_config["worker_env"] = dict(worker_env)
        try:
            timeout_value = float(getattr(self.config, "timeout", 30.0))
        except (TypeError, ValueError):
            timeout_value = 10.0
        proxy_config["startup_timeout"] = max(timeout_value, 5.0)
        return proxy_config

    def _resolve_initial_api_mode(self) -> str | None:
        config_section: Mapping[str, Any] | None = None
        raw_config = getattr(self.config, "config", None)
        if isinstance(raw_config, Mapping):
            config_section = raw_config
        candidate: object | None = None
        if config_section is not None:
            candidate = config_section.get("api_mode")
            if candidate is None:
                connection_section = config_section.get("connection")
                if isinstance(connection_section, Mapping):
                    candidate = connection_section.get("api_mode")
        if candidate is None:
            return None
        candidate_str = str(candidate).strip()
        return candidate_str or None

    def _resolve_subscription_poll_interval(self) -> float:
        config_section = self.config.config if isinstance(self.config.config, Mapping) else {}
        candidate: object | None = None
        if isinstance(config_section, Mapping):
            candidate = config_section.get("subscription_poll_interval")
            if candidate is None:
                subscription_section = config_section.get("subscription")
                if isinstance(subscription_section, Mapping):
                    candidate = subscription_section.get("poll_interval")
        try:
            interval = float(candidate)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            interval = 1.0
        if interval <= 0:
            interval = 1.0
        return interval

    def _resolve_subscription_batch_size(self) -> int:
        try:
            batch_size = int(getattr(self.config, "subscription_batch_size", 100))
        except (TypeError, ValueError):
            batch_size = 100
        if batch_size <= 0:
            batch_size = 100
        max_symbols = getattr(self.config, "max_subscriptions", None)
        if isinstance(max_symbols, int) and max_symbols > 0:
            batch_size = min(batch_size, max_symbols)
        return batch_size

    def _resolve_market_code(self) -> str:
        """���ݳ����趨���ҷ���Ĭ�Ͻ����г���"""

        candidate: object | None = getattr(self.config, "market", None)
        if candidate is None and isinstance(getattr(self.config, "config", None), Mapping):
            config_mapping = getattr(self.config, "config")
            market_candidate = None
            if isinstance(config_mapping, Mapping):
                market_candidate = config_mapping.get("market")
                connection_section = config_mapping.get("connection")
                if market_candidate is None and isinstance(connection_section, Mapping):
                    market_candidate = connection_section.get("market")
            candidate = market_candidate
        text = str(candidate or "SH").strip().upper()
        if text not in {"SH", "SZ", "BJ"}:
            return "SH"
        return text

    def _current_date_int(self) -> int:
        """������ĵ�ǰ����ֵ��YYYYMMDD��"""

        return int(datetime.now().strftime("%Y%m%d"))

    async def _get_trading_days(self, market: str) -> set[int]:
        """���ع����г���ǰ���ã���������������ˢ��"""

        raw_key = market.upper() if market else "SH"
        # 安全映射：仅允许 SH/SZ 直传；其他（BJ/BSE/INDEX/ETF/别名）统一映射到 SH，避免 SDK 崩溃
        if raw_key in {"SH", "SZ"}:
            market_key = raw_key
        elif "SZ" in raw_key:
            market_key = "SZ"
        else:
            if raw_key not in {"SH"}:
                logger.debug("AmazingData get_calendar 市场别名映射 {} -> SH", raw_key)
            market_key = "SH"
        now = time.monotonic()
        async with self._calendar_cache_lock:
            cached = self._calendar_cache.get(market_key)
            if cached and now - cached[1] <= self._TRADING_CALENDAR_TTL_SECONDS:
                return set(cached[0])

        command = ProcessCommand[Any](
            method="BaseData.get_calendar",
            args=(),
            kwargs={"data_type": "int", "market": market_key},
        )
        try:
            raw = await self._execute(command)
        except DataProviderError as exc:
            logger.warning("AmazingData get_calendar failed market={} error={}", market_key, exc)
            if cached:
                logger.info(
                    "AmazingData get_calendar 使用缓存数据 market={} cached_days={}",
                    market_key,
                    len(cached[0]),
                )
                return set(cached[0])
            return set()

        iterable: Sequence[Any]
        if isinstance(raw, Mapping):
            iterable = list(raw.values())
        elif isinstance(raw, Sequence):
            iterable = list(raw)
        else:
            iterable = []

        candidates: set[int] = set()
        for item in iterable:
            text = str(item).strip()
            if not text:
                continue
            try:
                digits = int(text)
            except ValueError:
                continue
            candidates.add(digits)

        if not candidates:
            if cached:
                logger.info(
                    "AmazingData get_calendar 返回空结果，回退缓存 market={} cached_days={}",
                    market_key,
                    len(cached[0]),
                )
                return set(cached[0])
            return set()

        async with self._calendar_cache_lock:
            self._calendar_cache[market_key] = (set(candidates), now)
        return candidates

    async def get_calendar(
        self, market: str = "SH", data_type: str = "int"
    ) -> list[int] | list[str] | list[datetime] | None:
        """Return trading calendar for the given market."""
        trading_days = await self._get_trading_days(market)
        if not trading_days:
            return None
        days_sorted = sorted(trading_days)
        normalized_type = (data_type or "int").lower()
        if normalized_type == "int":
            return days_sorted
        if normalized_type == "datetime":
            return [datetime.strptime(str(day), "%Y%m%d") for day in days_sorted]
        if normalized_type == "str":
            return [str(day) for day in days_sorted]
        return days_sorted

    async def _adjust_snapshot_dates(
        self,
        begin_date: int | None,
        end_date: int | None,
        market: str,
        *,
        trading_days: set[int] | None = None,
    ) -> tuple[int, int] | None:
        """���ݽ����г���ѹ�Ʋ�ѯ�����ڣ��򷵻ؿգ�"""

        trading_day_set = trading_days or await self._get_trading_days(market)
        if not trading_day_set:
            return None
        sorted_days = sorted(trading_day_set)
        adjusted_begin: int | None = None
        adjusted_end: int | None = None

        if begin_date is None:
            adjusted_begin = sorted_days[0]
        else:
            for candidate in sorted_days:
                if candidate >= begin_date:
                    adjusted_begin = candidate
                    break
            if adjusted_begin is None:
                for candidate in reversed(sorted_days):
                    if candidate < begin_date:
                        adjusted_begin = candidate
                        break

        if end_date is None:
            adjusted_end = sorted_days[-1]
        else:
            for candidate in reversed(sorted_days):
                if candidate <= end_date:
                    adjusted_end = candidate
                    break
            if adjusted_end is None:
                for candidate in sorted_days:
                    if candidate > end_date:
                        adjusted_end = candidate
                        break

        if adjusted_begin is None or adjusted_end is None:
            return None
        if adjusted_begin > adjusted_end:
            return None
        return adjusted_begin, adjusted_end

    @classmethod
    def _resolve_previous_trading_day(cls, trading_days: set[int], current_day: int) -> int | None:
        candidates = [day for day in trading_days if day < current_day]
        if not candidates:
            return None
        return max(candidates)

    @classmethod
    def _is_within_trading_window(cls, now: datetime) -> bool:
        current_time = now.time()
        for start, end in cls._TRADING_WINDOWS:
            if start <= current_time <= end:
                return True
        return False

    def _mark_connected(self, value: bool, *, error: str | None = None) -> None:
        previous_state = self._connected
        self._connected = value
        now = datetime.now(timezone.utc)
        if value:
            if not previous_state:
                self._connected_since = now
                self._subscription.schedule_resume()
            if error:
                self._last_error = error
            else:
                self._last_error = None
        else:
            if previous_state:
                self._last_disconnect_at = now
                self._subscription.schedule_pause()
            if error:
                self._last_error = error

    def update_health_status(self, payload: Dict[str, Any] | None) -> None:
        self._last_health_status = dict(payload) if payload else None

    def connection_status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected(),
            "connected_since": self._format_dt(self._connected_since),
            "last_disconnect_at": self._format_dt(self._last_disconnect_at),
            "last_error": self._last_error,
            "health": self._last_health_status or {},
        }

    @staticmethod
    def _format_dt(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _extract_response_metadata(response: ProcessCallResult[Any]) -> Mapping[str, Any] | None:
        if response.metadata:
            return response.metadata
        if isinstance(response.result, Mapping):
            return response.result
        return None

    def _should_switch_to_api_mode(self, response: ProcessCallResult[int]) -> bool:
        if self._login_api_mode:
            return False
        metadata = self._extract_response_metadata(response)
        combined_tokens = [
            str(response.error or ""),
            str(response.error_type or ""),
        ]
        if metadata:
            combined_tokens.extend(str(value) for value in metadata.values())
        combined = " ".join(token for token in combined_tokens if token).lower()
        if "tgw_push_init_failed" in combined:
            return True
        if "sdk_system_exit" in combined:
            return True
        if (response.error_type or "").lower() == "systemexit":
            return True
        if metadata:
            exit_code = metadata.get("exit_code")
            if exit_code is not None and str(exit_code).strip() == "0":
                return True
        return False

    async def _ensure_adapter(self) -> AmazingDataProcessAdapter:
        if self._adapter is not None:
            return self._adapter

        pool = get_global_pool()
        try:
            proxy = await asyncio.to_thread(
                pool.get_or_create,
                self._datasource_id,
                False,
                300.0,
                dict(self._proxy_config),
            )
        except Exception as exc:  # pragma: no cover - 极端异常用于日志观测
            logger.error(f"AmazingData 子进程获取失败: {exc}")
            raise DataProviderError(f"AmazingData 子进程获取失败: {exc}") from exc

        self._pool = pool
        self._adapter = AmazingDataProcessAdapter(proxy)
        return self._adapter

    async def _perform_login(self, adapter: AmazingDataProcessAdapter) -> None:
        await perform_login(self, adapter)

    def _reset_connection_state(
        self, *, drop_adapter: bool = False, reason: str | None = None
    ) -> None:
        if reason:
            logger.warning(f"AmazingData process provider will reset connection due to: {reason}")
        self._initialized = False
        self._mark_connected(False, error=reason)
        if drop_adapter:
            self._adapter = None

    @staticmethod
    def _classify_recoverable_error(message: str) -> tuple[bool, bool]:
        lowered = message.lower()
        drop_adapter_tokens = (
            "worker process crashed",
            "worker process exited",
            "process died",
            "broken pipe",
            "connection reset",
            "eoferror",
        )
        retry_tokens = drop_adapter_tokens + (
            "nonetype object is not subscriptable",
            "session expired",
            "channel closed",
            "worker lock busy",
        )

        for token in drop_adapter_tokens:
            if token in lowered:
                return True, True
        for token in retry_tokens:
            if token in lowered:
                return True, False
        return False, False

    async def _trigger_alert(self, alert_type: str, message: str) -> None:
        await trigger_alert(self, alert_type, message)

    def _collect_tgw_log_snippet(self, max_lines: int = 10) -> Optional[str]:
        return collect_tgw_log_snippet(self, max_lines=max_lines)

    @staticmethod
    def _read_tgw_tail_lines(
        file_path: Path, max_bytes: int = 4096, max_lines: int = 10
    ) -> list[str]:
        return read_tgw_tail_lines(file_path, max_bytes=max_bytes, max_lines=max_lines)

    def _is_authentication_error(
        self,
        message: str,
        error_type: str | None,
        metadata: Mapping[str, object] | None,
    ) -> bool:
        lowered = message.lower()
        if error_type and "auth" in error_type.lower():
            return True
        for token in self._AUTH_ERROR_KEYWORDS:
            if token in lowered:
                return True
        if metadata:
            for value in metadata.values():
                if isinstance(value, str) and any(
                    token in value.lower() for token in self._AUTH_ERROR_KEYWORDS
                ):
                    return True
        return False

    async def _ensure_ready(self) -> AmazingDataProcessAdapter:
        return await self._login_manager.ensure_ready()

    async def _execute(self, command: ProcessCommand[TResult]) -> Optional[TResult]:
        last_error: DataProviderError | None = None
        context = self._extract_command_context(command)

        try:
            validate_security_period(
                command.kwargs.get("security_type"),
                command.kwargs.get("period"),
                context=command.method,
            )
        except DataProviderError:
            raise

        for attempt in range(3):
            adapter = await self._login_manager.ensure_ready()
            logger.debug(
                "AmazingData execute attempt={} method={} timeout={} context={}",
                attempt + 1,
                command.method,
                command.timeout,
                context or {},
            )
            result = await adapter.execute(command)
            if result.success:
                self._login_manager.record_success()
                logger.debug(
                    "AmazingData execute success method={} context={}",
                    command.method,
                    context or {},
                )
                return result.result

            message = result.error or result.error_type or "子进程执行失败"
            if self._is_authentication_error(message, result.error_type, result.metadata):
                last_error = DataProviderError(message)
                await self._login_manager.handle_authentication_failure(message)
                continue

            error = DataProviderError(message)
            recoverable, drop_adapter = self._classify_recoverable_error(message)
            if recoverable and attempt < 2:
                self._reset_connection_state(drop_adapter=drop_adapter, reason=message)
                logger.warning(
                    "AmazingData execute recoverable error method={} attempt={} context={} error={}",
                    command.method,
                    attempt + 1,
                    context or {},
                    message,
                )
                last_error = error
                continue
            missing_method = "method" in message.lower() and "not found" in message.lower()
            if missing_method:
                logger.warning(
                    "AmazingData execute missing method={} context={} error={}",
                    command.method,
                    context or {},
                    message,
                )
                raise error
            self._mark_connected(False, error=message)
            logger.error(
                "AmazingData execute failed method={} context={} error={}",
                command.method,
                context or {},
                message,
            )
            raise error

        assert last_error is not None
        self._mark_connected(False, error=str(last_error))
        logger.error(
            "AmazingData execute exhausted retries method={} context={} last_error={}",
            command.method,
            context or {},
            last_error,
        )
        raise last_error

    async def initialize(self) -> bool:
        await self._ensure_ready()
        return True

    def is_connected(self) -> bool:
        return self._connected and self._initialized

    @property
    def last_code_list_branch(self) -> str | None:
        return self._last_code_list_branch

    @property
    def last_code_list_security_type(self) -> str | None:
        return self._last_code_list_security_type

    async def get_stock_list(
        self,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[list[Dict[str, Any]]]:
        config_section = self.config.config if isinstance(self.config.config, Mapping) else {}
        requested_security_type = (
            kwargs.get("security_type")
            or getattr(self.config, "security_type", None)
            or config_section.get("security_type")
        )
        normalized_security_type = (
            normalize_security_type(requested_security_type)
            or AmazingDataSecurityType.STOCK_A_SH_SZ.value
        )
        self._last_code_list_security_type = normalized_security_type

        security_type_candidates: list[str] = []
        for candidate in (
            normalized_security_type,
            AmazingDataSecurityType.STOCK_A_SH_SZ.value,
            AmazingDataSecurityType.STOCK_A.value,
        ):
            if candidate and candidate not in security_type_candidates:
                security_type_candidates.append(candidate)

        raw_result: Any | None = None
        last_error: DataProviderError | None = None
        branch_used: str | None = None
        for candidate in security_type_candidates:
            command = ProcessCommand[Any](
                method="BaseData.get_code_list",
                kwargs={"security_type": candidate},
                alt_methods=("BaseData.get_code_info",),
                kwargs_patches=(),
            )
            try:
                raw_result = await self._execute(command)
                branch_used = f"BaseData.get_code_list[{candidate}]"
                break
            except DataProviderError as exc:
                last_error = exc
                logger.warning(f"BaseData.get_code_list({candidate}) 调用失败: {exc}")
        else:
            raw_result = None

        if raw_result is None:
            cache_policy = CachePolicy.from_kwargs(
                context="BaseData.get_hist_code_list", kwargs=kwargs
            )
            effective_mode = (
                cache_policy.mode
                if cache_policy.mode is not CacheParamMode.NONE
                else CacheParamMode.REMOTE_RANGE
            )
            begin_candidate = cache_policy.values.get("begin_date")
            end_candidate = cache_policy.values.get("end_date")

            fallback_start = _normalize_date_to_int(begin_candidate) or DEFAULT_HIST_CODE_LIST_START
            fallback_end = _normalize_date_to_int(end_candidate)
            if fallback_end is None:
                fallback_end = int(datetime.now().strftime("%Y%m%d"))
            if fallback_end < fallback_start:
                fallback_start, fallback_end = fallback_end, fallback_start

            local_path_value: str | None = None
            is_local_flag: bool | None = None
            if effective_mode is CacheParamMode.LOCAL_CACHE:
                local_path_value = resolve_local_cache_path(
                    self.config, cache_policy.values.get("local_path")
                )
                is_local_flag = bool(cache_policy.values.get("is_local", True))
                try:
                    Path(local_path_value).mkdir(parents=True, exist_ok=True)
                except Exception as path_exc:  # pragma: no cover - 路径异常
                    logger.debug(f"创建本地缓存目录 {local_path_value} 失败: {path_exc}")

            fallback_candidates = security_type_candidates or [normalized_security_type]
            fallback_errors: list[str] = []

            for hist_security_type in fallback_candidates:
                if not hist_security_type:
                    continue

                base_params: Dict[str, object] = {"security_type": hist_security_type}

                if effective_mode is CacheParamMode.LOCAL_CACHE and local_path_value:
                    base_params["local_path"] = local_path_value
                    base_params["is_local"] = True if is_local_flag is None else is_local_flag
                    logger.info(
                        "准备调用 BaseData.get_hist_code_list security_type=%s local_path=%s is_local=%s",
                        hist_security_type,
                        local_path_value,
                        base_params["is_local"],
                    )
                else:
                    base_params["start_date"] = fallback_start
                    base_params["end_date"] = fallback_end
                    logger.info(
                        "准备调用 BaseData.get_hist_code_list security_type=%s start=%s end=%s",
                        hist_security_type,
                        fallback_start,
                        fallback_end,
                    )
                try:
                    raw_result = await self._execute(
                        ProcessCommand[Any](
                            method="BaseData.get_hist_code_list",
                            kwargs=base_params,
                        )
                    )
                    if effective_mode is CacheParamMode.LOCAL_CACHE:
                        branch_used = f"BaseData.get_hist_code_list[{hist_security_type}](local)"
                    else:
                        branch_used = (
                            f"BaseData.get_hist_code_list[{hist_security_type}]"
                            f"(start={fallback_start},end={fallback_end})"
                        )
                    break
                except DataProviderError as fallback_exc:
                    message = str(fallback_exc)
                    fallback_errors.append(f"{hist_security_type}: {message}")
                    if (
                        "unexpected keyword argument 'is_local'" in message
                        and "is_local" in base_params
                    ):
                        logger.info(
                            "BaseData.get_hist_code_list 不支持 is_local 参数，自动切换远端模式"
                        )
                        compat_params = {k: v for k, v in base_params.items() if k != "is_local"}
                        try:
                            raw_result = await self._execute(
                                ProcessCommand[Any](
                                    method="BaseData.get_hist_code_list",
                                    kwargs=compat_params,
                                )
                            )
                            branch_used = (
                                f"BaseData.get_hist_code_list[{hist_security_type}]"
                                f"(start={fallback_start},end={fallback_end},compat)"
                            )
                            break
                        except DataProviderError as compat_exc:
                            compat_message = f"[{hist_security_type}] BaseData.get_hist_code_list compat: {compat_exc}"
                            fallback_errors.append(compat_message)
                            continue
                    continue
            else:
                error_message = "; ".join(fallback_errors) if fallback_errors else "no candidates"
                if last_error is not None:
                    combined = f"{last_error}; BaseData.get_hist_code_list fallback failed: {error_message}"
                    raise DataProviderError(combined) from None
                raise DataProviderError(
                    f"BaseData.get_hist_code_list fallback failed: {error_message}"
                )
        records = normalize_stock_records(raw_result)
        self._last_code_list_branch = branch_used
        logger.debug(
            "AmazingData 股票列表获取完成 branch={} security_type={} count={}",
            branch_used or "unknown",
            normalized_security_type,
            len(records),
        )
        if not records:
            if branch_used:
                logger.warning(
                    "AmazingData 股票代码表为空 (branch={}, security_type={})",
                    branch_used,
                    normalized_security_type,
                )
            else:
                logger.warning(
                    "AmazingData 股票代码表为空 (branch=unknown, security_type={})",
                    normalized_security_type,
                )
            return None

        logger.info(
            "Using AmazingData.fetch_code_list (branch={}, security_type={}, count={})",
            branch_used or "unknown",
            normalized_security_type,
            len(records),
        )

        # 仅对 A 股品种尝试补全部块信息，避免 ETF/指数等产生无效告警
        if (
            records
            and _records_need_board(records)
            and ("STOCK_A" in (normalized_security_type or "").upper())
        ):
            try:
                board_metadata = await self._fetch_board_metadata(
                    [_extract_symbol(item) for item in records]
                )
            except DataProviderError as meta_exc:
                logger.warning("Board metadata fetch failed: {}", meta_exc)
            else:
                if board_metadata:
                    _merge_board_metadata(records, board_metadata)
                    logger.info(
                        "AmazingData get_stock_list 补全板块信息 success={}",
                        len(board_metadata),
                    )
                else:
                    sample_symbols = [
                        _extract_symbol(item)
                        for item in (records[:10] if isinstance(records, list) else [])
                    ]
                    logger.warning(
                        "Board metadata payload为空，无法补全部块信息 symbols={} security_type={}",
                        sample_symbols,
                        normalized_security_type,
                    )

        if limit and limit > 0:
            records = records[:limit]
        return records

    @staticmethod
    def _extract_command_context(command: ProcessCommand[Any]) -> dict[str, object]:
        """挑选与调试相关的参数用于日志输出。"""

        interesting_keys = (
            "security_type",
            "start_date",
            "end_date",
            "local_path",
            "is_local",
            "host",
            "port",
            "timeout",
            "period",
            "adjust",
        )
        context: dict[str, object] = {}
        for key in interesting_keys:
            if key in command.kwargs:
                context[key] = command.kwargs[key]

        if command.args:
            arg0 = command.args[0]
            if isinstance(arg0, (str, int)):
                context["arg0"] = arg0 if not isinstance(arg0, str) else arg0[:32]
            elif isinstance(arg0, Sequence) and not isinstance(arg0, (str, bytes, bytearray)):
                try:
                    context["arg0_len"] = len(arg0)
                except TypeError:
                    pass

        return context

    async def _fetch_board_metadata(self, symbols: Sequence[str]) -> list[dict[str, Any]]:
        """通过 InfoData/BaseData 查询板块信息。"""

        normalized_symbols = sorted(
            {symbol.upper() for symbol in symbols if isinstance(symbol, str) and symbol.strip()}
        )
        if not normalized_symbols:
            return []

        try:
            info_result = await self._execute(
                ProcessCommand[Any](
                    method="InfoData.get_stock_basic",
                    kwargs={"code_list": normalized_symbols},
                )
            )
            info_records = normalize_stock_records(info_result)
            if info_records:
                return info_records
        except DataProviderError as exc:
            logger.debug("InfoData.get_stock_basic 调用失败: {}", exc)

        security_type = (
            self._last_code_list_security_type or AmazingDataSecurityType.STOCK_A_SH_SZ.value
        )
        try:
            code_info_result = await self._execute(
                ProcessCommand[Any](
                    method="BaseData.get_code_info",
                    kwargs={"security_type": security_type},
                )
            )
            code_info_records = normalize_stock_records(code_info_result)
            if not code_info_records:
                return []

            lookup: dict[str, dict[str, Any]] = {}
            for item in code_info_records:
                symbol = _extract_symbol(item)
                if symbol and symbol not in lookup:
                    lookup[symbol] = item
            return [lookup[symbol] for symbol in normalized_symbols if symbol in lookup]
        except DataProviderError as exc:
            logger.debug("BaseData.get_code_info 调用失败: {}", exc)
        return []

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> Optional[list[Dict[str, Any]]]:
        # 将字符串period转换为SDK Period枚举
        period_enum = _resolve_period_to_enum(period or "1d")
        if period_enum is None:
            logger.warning("无法解析period '{}', 使用默认日线", period)
            period_enum = _resolve_period_to_enum("1d")

        begin_date_value = _normalize_date_to_int(start_date)
        end_date_value = _normalize_date_to_int(end_date)
        adjust_value = kwargs.get("adjust", "none")

        base_kwargs: Dict[str, object] = {}
        if begin_date_value is not None:
            base_kwargs["begin_date"] = begin_date_value
        if end_date_value is not None:
            base_kwargs["end_date"] = end_date_value
        if period_enum is not None:
            base_kwargs["period"] = period_enum  # 传递枚举对象而非字符串
        if adjust_value is not None:
            base_kwargs["adjust"] = adjust_value

        command = ProcessCommand[Any](
            method="MarketData.query_kline",
            args=([symbol],),
            kwargs=base_kwargs,
        )

        raw_result = await self._execute(command)
        if not raw_result:
            return None

        df = AmazingDataQueryManager.normalize_kline_payload(raw_result, symbol)
        if df.empty:
            return None

        if limit and limit > 0:
            df = df.head(limit)

        records = cast(list[dict[str, Any]], df.reset_index().to_dict("records"))
        return records

    async def get_realtime_quote(
        self,
        symbols: Sequence[str] | str,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        today = self._current_date_int()
        market_code = str(kwargs.get("market") or self._resolve_market_code())

        if isinstance(symbols, str):
            symbol_list = [symbols]
            single_query = True
        else:
            symbol_list = [str(item).strip() for item in symbols if str(item).strip()]
            single_query = False

        if not symbol_list:
            return {} if not single_query else None

        normalized_targets = [code.upper() for code in symbol_list]

        trading_days = await self._get_trading_days(market_code)
        if trading_days and today not in trading_days:
            logger.info(
                "AmazingData 实时行情在非交易日跳过 datasource={} market={} date={}",
                self._datasource_id,
                market_code,
                today,
            )
            return {} if not single_query else None
        if not trading_days:
            logger.warning(
                "AmazingData 未能获取交易日历，仍将尝试实时行情请求 datasource={} market={}",
                self._datasource_id,
                market_code,
            )

        command = ProcessCommand[Any](
            method="MarketData.query_snapshot",
            args=(normalized_targets,),
            kwargs={"begin_date": today, "end_date": today},
        )
        raw_result = await self._execute(command)
        result_summary = _summarize_object(raw_result)
        logger.debug(
            "AmazingData query_snapshot 原始结果摘要 targets={} summary={}",
            len(normalized_targets),
            result_summary,
        )
        if not raw_result:
            logger.warning(
                "AmazingData query_snapshot 返回空 payload targets={} summary={}",
                len(normalized_targets),
                result_summary,
            )
            return {} if not single_query else None

        rows = AmazingDataQueryManager._collect_snapshot_rows(raw_result)
        if not rows:
            logger.debug(
                "AmazingData query_snapshot 未解析到行情记录 targets={} summary={}",
                len(normalized_targets),
                result_summary,
            )
            return {} if not single_query else None

        formatted = AmazingDataQueryManager._format_snapshot_map(normalized_targets, rows)
        if single_query:
            target_code = normalized_targets[0]
            return formatted.get(target_code)

        return formatted

    async def query_snapshot(
        self,
        code_list: Sequence[str],
        begin_date: int,
        end_date: int,
        *,
        market: str | None = None,
        align_policy: SnapshotAlignPolicy | str | None = SnapshotAlignPolicy.NEAREST_PREV,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        normalized_codes = [
            code.strip().upper() for code in code_list if isinstance(code, str) and code.strip()
        ]
        if not normalized_codes:
            return {}

        market_code = str(market or self._resolve_market_code())
        requested_begin = begin_date
        requested_end = end_date

        policy = SnapshotAlignPolicy.from_value(align_policy)

        trading_days = await self._get_trading_days(market_code)
        if not trading_days:
            logger.info(
                "AmazingData 历史快照请求缺少交易日信息 datasource={} market={} begin={} end={}",
                self._datasource_id,
                market_code,
                requested_begin,
                requested_end,
            )
            return {}

        now_local = datetime.now(self._LOCAL_TZ)
        today_int = int(now_local.strftime("%Y%m%d"))
        manual_adjusted = False
        adjusted_begin = begin_date
        adjusted_end = end_date

        if policy is SnapshotAlignPolicy.NEAREST_PREV:
            if adjusted_begin == adjusted_end:
                target_day = adjusted_begin
                needs_previous = False
                if target_day == today_int:
                    if target_day not in trading_days or not self._is_within_trading_window(
                        now_local
                    ):
                        needs_previous = True
                elif target_day not in trading_days:
                    needs_previous = True

                if needs_previous:
                    previous_day = self._resolve_previous_trading_day(trading_days, target_day)
                    if previous_day is None:
                        logger.info(
                            "AmazingData 历史快照在窗口内无上一交易日 datasource={} market={} target={}",
                            self._datasource_id,
                            market_code,
                            target_day,
                        )
                        return {}
                    adjusted_begin = previous_day
                    adjusted_end = previous_day
                    manual_adjusted = True
                    logger.info(
                        "AmazingData 历史快照自动回退日期 datasource={} market={} requested={} adjusted={}",
                        self._datasource_id,
                        market_code,
                        target_day,
                        previous_day,
                    )

            adjusted_range = await self._adjust_snapshot_dates(
                adjusted_begin,
                adjusted_end,
                market_code,
                trading_days=trading_days,
            )
            if adjusted_range is None:
                logger.info(
                    "AmazingData 历史快照无有效交易区间 datasource={} market={} begin={} end={} policy={}",
                    self._datasource_id,
                    market_code,
                    requested_begin,
                    requested_end,
                    policy.value,
                )
                return {}
            adjusted_begin, adjusted_end = adjusted_range
        elif policy is SnapshotAlignPolicy.STRICT:
            missing_days = [
                day for day in (adjusted_begin, adjusted_end) if day not in trading_days
            ]
            if missing_days:
                missing_display = ",".join(str(day) for day in missing_days)
                logger.info(
                    "AmazingData 历史快照严格策略拒绝非交易日 datasource={} market={} begin={} end={} missing={}",
                    self._datasource_id,
                    market_code,
                    requested_begin,
                    requested_end,
                    missing_display,
                )
                return {}
        else:
            # passthrough: 保持调用方日期范围
            pass

        if adjusted_begin > adjusted_end:
            logger.info(
                "AmazingData 历史快照起止日期无效 datasource={} market={} begin={} end={} policy={}",
                self._datasource_id,
                market_code,
                adjusted_begin,
                adjusted_end,
                policy.value,
            )
            return {}

        if manual_adjusted or adjusted_begin != requested_begin or adjusted_end != requested_end:
            logger.info(
                "AmazingData 历史快照调整区间 datasource={} market={} begin={} end={} adjusted_begin={} adjusted_end={} policy={}",
                self._datasource_id,
                market_code,
                requested_begin,
                requested_end,
                adjusted_begin,
                adjusted_end,
                policy.value,
            )

        command = ProcessCommand[Any](
            method="MarketData.query_snapshot",
            args=(normalized_codes,),
            kwargs={"begin_date": adjusted_begin, "end_date": adjusted_end},
        )
        raw_result = await self._execute(command)
        result_summary = _summarize_object(raw_result)
        logger.debug(
            "AmazingData query_snapshot(历史) 摘要 codes={} begin={} end={} summary={}",
            len(normalized_codes),
            adjusted_begin,
            adjusted_end,
            result_summary,
        )
        if not raw_result:
            return {}

        symbol_frames: defaultdict[str, list[pd.DataFrame]] = defaultdict(list)
        symbol_suffixes = {"SH", "SZ", "BJ", "HK", "US"}

        def _is_symbol_key(text: str) -> bool:
            normalized = text.strip().upper()
            if not normalized:
                return False
            if "." in normalized:
                prefix, _, suffix = normalized.partition(".")
                return bool(prefix) and suffix in symbol_suffixes
            if normalized.isdigit():
                return 3 <= len(normalized) <= 6
            if normalized[:2].isalpha() and normalized[2:].isdigit():
                return True
            return False

        def _resolve_symbol_candidate(candidate: Any, fallback: str | None = None) -> str | None:
            if candidate is None:
                return fallback
            if isinstance(candidate, str):
                normalized = candidate.strip().upper()
                return normalized if _is_symbol_key(normalized) else fallback
            if isinstance(candidate, (int, float)):
                return fallback
            return fallback

        def _resolve_symbol_from_row(
            row: Mapping[str, Any], fallback: str | None = None
        ) -> str | None:
            for key in ("code", "symbol", "SECURITY_CODE", "SECURITYID", "SYMBOL_CODE", "ticker"):
                value = row.get(key)
                if value is None:
                    continue
                resolved = _resolve_symbol_candidate(str(value), fallback)
                if resolved:
                    return resolved
            return fallback

        def _resolve_symbol_from_frame(
            frame: pd.DataFrame, fallback: str | None = None
        ) -> str | None:
            for column in (
                "symbol",
                "code",
                "SECURITY_CODE",
                "SECURITYID",
                "SYMBOL_CODE",
                "ticker",
            ):
                if column not in frame.columns:
                    continue
                series = frame[column].dropna()
                if series.empty:
                    continue
                resolved = _resolve_symbol_candidate(str(series.iloc[0]), fallback)
                if resolved:
                    return resolved
            return fallback

        def _visit(node: Any, context_symbol: str | None = None) -> None:
            if node is None:
                return
            if isinstance(node, pd.DataFrame):
                frame = node.copy()
                if frame.index.name and frame.index.name not in frame.columns:
                    frame = frame.reset_index()
                else:
                    frame = frame.reset_index(drop=True)
                symbol = _resolve_symbol_from_frame(frame, context_symbol)
                if symbol is None and len(normalized_codes) == 1:
                    symbol = normalized_codes[0]
                if symbol is None:
                    logger.debug(
                        "AmazingData query_snapshot DataFrame 缺少 symbol 信息 summary={} columns={}",
                        result_summary,
                        list(frame.columns),
                    )
                    return
                symbol = symbol.upper()
                if "symbol" not in frame.columns:
                    frame = frame.assign(symbol=symbol)
                symbol_frames[symbol].append(frame)
                return
            if isinstance(node, Mapping):
                lowered_keys = {str(key).lower() for key in node.keys()}
                if {"code", "symbol"} & lowered_keys:
                    symbol = _resolve_symbol_from_row(node, context_symbol)
                    if symbol is None and len(normalized_codes) == 1:
                        symbol = normalized_codes[0]
                    if symbol is None:
                        logger.debug(
                            "AmazingData query_snapshot 行记录缺少 symbol summary={} keys={}",
                            result_summary,
                            list(node.keys()),
                        )
                        return
                    symbol = symbol.upper()
                    frame = pd.DataFrame([dict(node)]).reset_index(drop=True)
                    if "symbol" not in frame.columns:
                        frame = frame.assign(symbol=symbol)
                    symbol_frames[symbol].append(frame)
                    return
                for key, value in node.items():
                    next_symbol = _resolve_symbol_candidate(str(key), context_symbol)
                    _visit(value, next_symbol or context_symbol)
                return
            if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
                for item in node:
                    _visit(item, context_symbol)
                return

        if isinstance(raw_result, pd.DataFrame):
            _visit(raw_result)
        elif isinstance(raw_result, Mapping):
            _visit(raw_result)
        elif isinstance(raw_result, Sequence) and not isinstance(
            raw_result, (str, bytes, bytearray)
        ):
            for item in raw_result:
                _visit(item)
        else:
            logger.warning(
                "AmazingData query_snapshot 结果类型不受支持 summary={} type={}",
                result_summary,
                type(raw_result).__name__,
            )
            return {}

        if not symbol_frames:
            logger.debug(
                "AmazingData query_snapshot 未获取到可序列化的行情数据 summary={}",
                result_summary,
            )
            return {}
        ordered_symbols = [code for code in normalized_codes if code in symbol_frames]
        for symbol in list(symbol_frames.keys()):
            if symbol not in ordered_symbols:
                ordered_symbols.append(symbol)

        serialized: Dict[str, Dict[str, Any]] = {}
        for symbol in ordered_symbols:
            frames = symbol_frames.get(symbol)
            if not frames:
                continue
            if len(frames) == 1:
                combined = frames[0].reset_index(drop=True)
            else:
                combined = pd.concat(frames, ignore_index=True, sort=False)  # type: ignore[call-arg]
            serialized[symbol] = _dataframe_to_payload(combined)
        return serialized

    async def subscribe_stock_snapshot(
        self,
        symbols: list[str],
        callback: SubscriptionCallback,
        data_type: str = "snapshot",
        **kwargs: Any,
    ) -> bool:
        return await self._subscription.subscribe_snapshot(
            symbols,
            callback,
            data_type or "snapshot",
            **kwargs,
        )

    async def unsubscribe_quote(
        self,
        symbols: Sequence[str],
        **_: Any,
    ) -> bool:
        return await self._subscription.unsubscribe(symbols)

    async def snapshot_subscriptions(self) -> Mapping[str, SubscriptionInfo]:
        return await self._subscription.snapshot()

    async def drain_subscriptions(self) -> Mapping[str, SubscriptionInfo]:
        return await self._subscription.drain()

    async def restore_subscriptions(self, snapshot: Mapping[str, SubscriptionInfo]) -> None:
        await self._subscription.restore(snapshot)

    async def _stop_subscription_loop(self) -> None:
        await self._subscription.stop_loop()

    async def _dispatch_subscription_payloads(
        self,
        codes: Sequence[str],
        callbacks_map: Mapping[str, tuple[SubscriptionCallback, ...]],
    ) -> None:
        await self._subscription.dispatch_payloads(codes, callbacks_map)

    async def subscribe(
        self,
        symbols: list[str],
        callback: Any,
        data_type: str = "realtime",
        **kwargs: Any,
    ) -> bool:
        return await self.subscribe_stock_snapshot(
            symbols,
            callback,
            data_type=data_type or "snapshot",
            **kwargs,
        )

    async def unsubscribe(
        self,
        symbols: list[str],
        data_type: str = "realtime",
        **kwargs: Any,
    ) -> bool:
        return await self.unsubscribe_quote(symbols, **kwargs)

    async def get_block_trading(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        获取大宗交易数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 交易日期开始筛选(格式: YYYYMMDD)
            end_date: 交易日期结束筛选(格式: YYYYMMDD)

        Returns:
            DataFrame: 大宗交易数据
        """
        # 解析本地缓存路径
        resolved_path = resolve_local_cache_path(self.config, local_path)

        # 构建关键字参数（不包含symbols，因为它是位置参数）
        call_kwargs: Dict[str, Any] = {}
        if resolved_path:
            call_kwargs["local_path"] = resolved_path
            call_kwargs["is_local"] = is_local
        if begin_date is not None:
            call_kwargs["begin_date"] = begin_date
        if end_date is not None:
            call_kwargs["end_date"] = end_date

        logger.warning(
            f"[get_block_trading] Calling InfoData.get_block_trading with args={code_list}, kwargs={call_kwargs}"
        )

        try:
            result = await self._execute(
                ProcessCommand[Any](
                    method="InfoData.get_block_trading",
                    args=(code_list,),  # symbols作为第一个位置参数
                    kwargs=call_kwargs,
                )
            )

            logger.warning(
                f"[get_block_trading] Result type: {type(result).__name__}, is None: {result is None}"
            )

            if result is None:
                return pd.DataFrame()

            if isinstance(result, pd.DataFrame):
                return result
            elif isinstance(result, dict):
                # 如果返回的是字典，尝试转换为DataFrame
                frames: list[pd.DataFrame] = []
                for symbol, payload in result.items():
                    if isinstance(payload, pd.DataFrame):
                        item_df = payload.copy()
                    else:
                        item_df = pd.DataFrame(payload) if payload else pd.DataFrame()
                    if not item_df.empty and "symbol" not in item_df.columns:
                        item_df["symbol"] = symbol
                    frames.append(item_df)
                return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            elif isinstance(result, (list, tuple)):
                return pd.DataFrame(result)
            else:
                return pd.DataFrame([result])

        except DataProviderError as exc:
            logger.error(f"[get_block_trading] SDK调用失败: {exc}")
            return pd.DataFrame()
        except Exception as exc:
            logger.error(f"[get_block_trading] 未知错误: {exc}")
            return pd.DataFrame()

    async def close(self) -> None:
        await self._subscription.shutdown()

        adapter = self._adapter
        if adapter:
            try:
                await adapter.logout(
                    AmazingDataLogoutRequest(username=getattr(self.config, "username", None))
                )
            except Exception as exc:  # pragma: no cover - 仅记录日志
                logger.warning(f"AmazingData 子进程注销异常: {exc}")

        if self._pool:
            try:
                await asyncio.to_thread(
                    self._pool.stop,
                    self._datasource_id,
                    False,
                    False,
                )
            except Exception as exc:  # pragma: no cover - 仅记录日志
                logger.warning(f"AmazingData 子进程停止异常: {exc}")

        self._adapter = None
        self._pool = None
        self._initialized = False
        safe_wrapper_module: ModuleType | None
        try:
            from .. import amazingdata_safe_wrapper as safe_wrapper_module
        except Exception:  # noqa: BLE001
            safe_wrapper_module = None
        if safe_wrapper_module is not None:
            wrapper_instance = getattr(safe_wrapper_module, "_global_wrapper", None)
            if wrapper_instance is not None:
                try:
                    wrapper_instance.unregister_subscription_bridge(self)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("AmazingData safe wrapper bridge unregister failed: {}", exc)
        self._mark_connected(False)


logger = ProcessLoggerAdapter(action="process")
