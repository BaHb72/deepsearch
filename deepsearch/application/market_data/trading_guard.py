"""交易时段守护逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time as time_type, timedelta
from enum import Enum
from typing import Awaitable, Callable, Iterable, Sequence
from zoneinfo import ZoneInfo

from loguru import logger

from deepsearch.ports.market_data import MarketSnapshot

CalendarLoader = Callable[[str], Awaitable[Sequence[int] | None]]
SnapshotSupplier = Callable[[], MarketSnapshot | None]


class PhaseState(str, Enum):
    """交易阶段枚举。"""

    OFF_DAY = "off_day"
    NO_TRADE = "no_trade"
    AUCTION = "auction"
    CONTINUOUS = "continuous"


@dataclass(slots=True)
class PhaseDetector:
    """根据时间与交易所返回的 phase token 判断当前交易阶段。"""

    timezone: ZoneInfo
    auction_windows: tuple[tuple[time_type, time_type], ...]
    continuous_windows: tuple[tuple[time_type, time_type], ...]
    trading_phase_continuous: frozenset[str] = frozenset({"C", "T", "O", "M", "U"})
    trading_phase_auction: frozenset[str] = frozenset({"A", "P"})
    trading_phase_no_trade: frozenset[str] = frozenset({"S", "E", "B", "H", "V"})

    def detect(
            self,
            *,
            now: datetime,
            trading_days: set[int],
            phase_token: str | None,
    ) -> PhaseState:
        today_int = int(now.strftime("%Y%m%d"))
        if not trading_days or today_int not in trading_days:
            return PhaseState.OFF_DAY

        if phase_token:
            head = phase_token[:1]
            if head in self.trading_phase_continuous:
                return PhaseState.CONTINUOUS
            if head in self.trading_phase_auction:
                return PhaseState.AUCTION
            if head in self.trading_phase_no_trade:
                return PhaseState.NO_TRADE

        current_time = now.time()
        for start, end in self.auction_windows:
            if start <= current_time <= end:
                return PhaseState.AUCTION
        for start, end in self.continuous_windows:
            if start <= current_time <= end:
                return PhaseState.CONTINUOUS
        return PhaseState.NO_TRADE


@dataclass(slots=True, frozen=True)
class TradingSessionDecision:
    """交易会话的判定结果。"""

    now: datetime
    is_trading_day: bool
    is_trading_session: bool
    reason: str | None
    phase_token: str | None
    phase_state: PhaseState
    previous_trading_day: int | None
    interval_seconds: float
    timeout_seconds: float
    timeout_log_level: str  # "warning" 或 "info"

    @property
    def should_skip_step(self) -> bool:
        return not (self.is_trading_day and self.is_trading_session)

    @property
    def status_label(self) -> str:
        if not self.is_trading_day:
            return "off-day"
        if not self.is_trading_session:
            return "off-session"
        return "trading"


@dataclass(slots=True)
class TradingSessionGuard:
    """结合交易日历与实时快照识别交易阶段，并给出调度建议。"""

    calendar_loader: CalendarLoader
    snapshot_supplier: SnapshotSupplier | None = None
    markets: Sequence[str] = field(default_factory=lambda: ("SH", "SZ"))
    timezone: ZoneInfo = ZoneInfo("Asia/Shanghai")
    calendar_ttl: timedelta = timedelta(minutes=10)
    phase_intervals: dict[PhaseState, float] = field(default_factory=dict)
    phase_timeouts: dict[PhaseState, float] = field(default_factory=dict)
    _calendar_cache: dict[str, tuple[set[int], datetime]] = field(default_factory=dict, init=False)
    _phase_detector: PhaseDetector = field(init=False)
    _calendar_fallback_active: bool = field(default=False, init=False)

    _DEFAULT_INTERVALS = {
        PhaseState.OFF_DAY: 120.0,
        PhaseState.NO_TRADE: 45.0,
        PhaseState.AUCTION: 5.0,
        PhaseState.CONTINUOUS: 1.0,
    }
    _DEFAULT_TIMEOUTS = {
        PhaseState.OFF_DAY: 5.0,
        PhaseState.NO_TRADE: 5.0,
        PhaseState.AUCTION: 3.0,
        PhaseState.CONTINUOUS: 3.0,
    }
    _AUCTION_WINDOWS: tuple[tuple[time_type, time_type], ...] = ((time_type(9, 15), time_type(9, 25)),)
    _CONTINUOUS_WINDOWS: tuple[tuple[time_type, time_type], ...] = (
        (time_type(9, 30), time_type(11, 30)),
        (time_type(13, 0), time_type(15, 0)),
    )

    def __post_init__(self) -> None:
        self.phase_intervals = {**self._DEFAULT_INTERVALS, **self.phase_intervals}
        self.phase_timeouts = {**self._DEFAULT_TIMEOUTS, **self.phase_timeouts}
        self._phase_detector = PhaseDetector(
            timezone=self.timezone,
            auction_windows=self._AUCTION_WINDOWS,
            continuous_windows=self._CONTINUOUS_WINDOWS,
        )

    async def evaluate(
            self,
            *,
            default_interval: float,
            default_timeout: float,
            now: datetime | None = None,
    ) -> TradingSessionDecision:
        now = (now.astimezone(self.timezone) if now else datetime.now(self.timezone))
        today_int = self._as_date_int(now.date())
        trading_days = await self._collect_trading_days()
        if not trading_days:
            trading_days = {today_int}
            if not self._calendar_fallback_active:
                logger.warning(
                    "交易日历为空，临时视 {} 为交易日，允许实时行情继续运行",
                    today_int,
                )
            self._calendar_fallback_active = True
        elif self._calendar_fallback_active:
            logger.info("交易日历恢复，关闭临时交易日回退")
            self._calendar_fallback_active = False

        phase_token = self._resolve_trading_phase()
        phase_state = self._phase_detector.detect(
            now=now,
            trading_days=trading_days,
            phase_token=phase_token,
        )

        is_trading_day = phase_state is not PhaseState.OFF_DAY
        previous_day = self._resolve_previous_day(today_int, trading_days)
        is_trading_session = phase_state in (PhaseState.AUCTION, PhaseState.CONTINUOUS)

        reason: str | None = None
        if phase_state is PhaseState.OFF_DAY:
            reason = "non-trading-day"
        elif phase_state is PhaseState.NO_TRADE:
            reason = "outside-trading-window"
        elif phase_state is PhaseState.AUCTION:
            reason = "auction"

        interval = self.phase_intervals.get(phase_state, default_interval)
        if interval <= 0:
            interval = default_interval
        timeout = self.phase_timeouts.get(phase_state, default_timeout)
        if timeout <= 0:
            timeout = default_timeout

        timeout_log_level = "warning" if phase_state is PhaseState.CONTINUOUS else "info"

        return TradingSessionDecision(
            now=now,
            is_trading_day=is_trading_day,
            is_trading_session=is_trading_session,
            reason=reason,
            phase_token=phase_token,
            phase_state=phase_state,
            previous_trading_day=previous_day,
            interval_seconds=interval,
            timeout_seconds=timeout,
            timeout_log_level=timeout_log_level,
        )

    async def _collect_trading_days(self) -> set[int]:
        merged: set[int] = set()
        for market in self.markets:
            days = await self._load_calendar(market)
            merged.update(days)
        return merged

    async def _load_calendar(self, market: str) -> set[int]:
        market_key = market.upper()
        cache_entry = self._calendar_cache.get(market_key)
        now = datetime.now(self.timezone)
        if cache_entry:
            cached_days, cached_at = cache_entry
            if cached_days and now - cached_at <= self.calendar_ttl:
                return set(cached_days)

        try:
            result = await self.calendar_loader(market_key)
        except Exception as exc:  # pragma: no cover - 仅记录日志
            logger.warning("获取交易日历失败 market={} error={}", market_key, exc)
            return cache_entry[0] if cache_entry else set()

        normalized = self._normalize_calendar(result)
        if normalized:
            self._calendar_cache[market_key] = (normalized, now)
            return normalized

        if cache_entry and cache_entry[0]:
            return set(cache_entry[0])
        return set()

    def _normalize_calendar(self, raw: Sequence[int] | None) -> set[int]:
        normalized: set[int] = set()
        if raw is None:
            return normalized
        for item in raw:
            digits: str | None = None
            if isinstance(item, datetime):
                digits = item.strftime("%Y%m%d")
            elif hasattr(item, "strftime"):
                try:
                    digits = item.strftime("%Y%m%d")
                except Exception:  # pragma: no cover - 容错
                    digits = None
            else:
                text = "".join(ch for ch in str(item) if ch.isdigit())
                if len(text) >= 8:
                    digits = text[-8:]
            if not digits or len(digits) != 8:
                continue
            try:
                normalized.add(int(digits))
            except (TypeError, ValueError):
                continue
        return normalized

    def _resolve_previous_day(self, today: int, trading_days: Iterable[int]) -> int | None:
        candidates = [day for day in trading_days if day < today]
        if not candidates:
            return None
        return max(candidates)

    def _resolve_trading_phase(self) -> str | None:
        if not self.snapshot_supplier:
            return None
        snapshot = self.snapshot_supplier()
        if not snapshot:
            return None
        phase = (snapshot.trading_phase or "").strip().upper()
        return phase or None

    @staticmethod
    def _as_date_int(value: date) -> int:
        return int(value.strftime("%Y%m%d"))
