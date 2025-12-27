"""市场行情指标计算器集合。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, getcontext
from typing import Callable, Dict, Sequence

from deepsearch.ports.market_data import (
    AuctionQualityEntry,
    CapitalPulseEntry,
    MarketSnapshot,
    OrderImbalanceEntry,
    WindowSpec,
)

from .buffers import SnapshotBuffer

getcontext().prec = 28

BoardResolver = Callable[[str], Sequence[str]]


def _decimal_zero() -> Decimal:
    return Decimal("0")


def _to_decimal(value: object, default: Decimal = Decimal("0")) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _select_baseline(
    series: Sequence[MarketSnapshot],
    prefix: MarketSnapshot | None,
    start_ts: datetime,
) -> MarketSnapshot:
    first = series[0]
    if prefix is not None and prefix.ts <= start_ts and first.ts > start_ts:
        return prefix
    return first


@dataclass(slots=True)
class CapitalPulseCalculator:
    """资金脉冲指标计算器。"""

    buffer: SnapshotBuffer
    resolve_board_codes: BoardResolver
    data_source: str
    _last_speed: Dict[tuple[str, str], Decimal] = field(default_factory=dict)

    def compute(
        self,
        board: str,
        window: WindowSpec,
        *,
        as_of: datetime | None = None,
        summary_mode: bool = False,
    ) -> CapitalPulseEntry | None:
        codes = tuple(self.resolve_board_codes(board))
        if not codes:
            return None

        end_ts = as_of or self.buffer.latest_timestamp(codes)
        if end_ts is None:
            return None

        start_ts = end_ts - window.duration
        series_map = self.buffer.sliced_series(
            codes,
            end=end_ts,
            duration=window.duration,
            include_prefetch=True,
        )

        if summary_mode:
            # 汇总模式：取当日累计成交额，速度设为 0
            from loguru import logger

            logger.debug(
                "汇总模式计算 board={} codes_count={} series_map_keys={}",
                board,
                len(codes),
                len(series_map),
            )
            total_amount = Decimal("0")
            valid_series_count = 0
            for code, payload in series_map.items():
                series, _ = payload
                if series:
                    valid_series_count += 1
                    amt = _to_decimal(series[-1].amount)
                    total_amount += amt
                    if amt > 0 and valid_series_count <= 3:
                        logger.debug("汇总模式示例 code={} amount={}", code, amt)
            logger.debug(
                "汇总模式结果 board={} valid_series={} total_amount={}",
                board,
                valid_series_count,
                total_amount,
            )
            return CapitalPulseEntry(
                board=board,
                window=window,
                amount_total=total_amount,
                speed_per_min=Decimal("0"),
                accel_per_min2=Decimal("0"),
                ts=end_ts,
                data_source=self.data_source,
            )

        # 实时模式：计算时间窗口内的增量
        total_delta = Decimal("0")
        for payload in series_map.values():
            series, prefix = payload
            if not series:
                continue
            baseline = _select_baseline(series, prefix, start_ts)
            last_snapshot = series[-1]
            delta = _to_decimal(last_snapshot.amount) - _to_decimal(baseline.amount)
            if delta < 0:
                delta = Decimal("0")
            total_delta += delta

        window_minutes = Decimal(str(window.duration.total_seconds())) / Decimal("60")
        if window_minutes <= 0:
            speed = Decimal("0")
        else:
            speed = total_delta / window_minutes

        key = (board, window.name)
        previous_speed = self._last_speed.get(key)
        accel = speed - previous_speed if previous_speed is not None else Decimal("0")
        self._last_speed[key] = speed

        return CapitalPulseEntry(
            board=board,
            window=window,
            amount_total=total_delta,
            speed_per_min=speed,
            accel_per_min2=accel,
            ts=end_ts,
            data_source=self.data_source,
        )


@dataclass(slots=True)
class AuctionQualityCalculator:
    """集合竞价质量指标计算器。"""

    buffer: SnapshotBuffer
    resolve_board_codes: BoardResolver
    data_source: str
    price_window: timedelta = field(default=timedelta(minutes=2))
    phase_codes: Sequence[str] = field(default=("C", "O"))

    def compute(
        self,
        board: str,
        window: WindowSpec,
        *,
        as_of: datetime | None = None,
    ) -> AuctionQualityEntry | None:
        codes = tuple(self.resolve_board_codes(board))
        if not codes:
            return None

        end_ts = as_of or self.buffer.latest_timestamp(codes)
        if end_ts is None:
            return None

        start_ts = end_ts - window.duration
        filtered_codes: list[str] = []
        series_map: Dict[str, tuple[list[MarketSnapshot], MarketSnapshot | None]] = {}

        for code in codes:
            series, prefix = self.buffer.window_series(
                code,
                end=end_ts,
                duration=window.duration,
                include_prefetch=True,
            )
            phase_series = [
                snap
                for snap in series
                if not self.phase_codes or (snap.trading_phase or "").upper() in self.phase_codes
            ]
            if not phase_series:
                continue
            series_map[code] = (phase_series, prefix)
            filtered_codes.append(code)

        if not filtered_codes:
            return None

        amount_delta = Decimal("0")
        volume_delta = Decimal("0")
        price_samples: list[Decimal] = []
        price_cutoff = max(start_ts, end_ts - self.price_window)

        for series, prefix in series_map.values():
            baseline = _select_baseline(series, prefix, start_ts)
            last_snapshot = series[-1]

            amount_delta += _to_decimal(last_snapshot.amount) - _to_decimal(baseline.amount)
            volume_delta += Decimal(str(last_snapshot.volume - baseline.volume))

            for snapshot in series:
                if snapshot.ts >= price_cutoff:
                    price_samples.append(_to_decimal(snapshot.last))

        window_minutes = Decimal(str(window.duration.total_seconds())) / Decimal("60")
        speed = amount_delta / window_minutes if window_minutes > 0 else Decimal("0")

        price_stability = self._variance(price_samples)

        return AuctionQualityEntry(
            board=board,
            amount_acc=amount_delta,
            volume_acc=volume_delta,
            speed_per_min=speed,
            price_stability=price_stability,
            ts=end_ts,
            data_source=self.data_source,
        )

    @staticmethod
    def _variance(samples: Sequence[Decimal]) -> Decimal:
        if len(samples) < 2:
            return Decimal("0")
        mean = sum(samples, Decimal("0")) / Decimal(len(samples))
        variance = sum((value - mean) ** 2 for value in samples) / Decimal(len(samples))
        return variance


@dataclass(slots=True)
class OrderImbalanceCalculator:
    """盘口失衡指标计算器。"""

    buffer: SnapshotBuffer
    data_source: str
    depth: int = 5

    def evaluate(
        self,
        code: str,
        window: WindowSpec,
        *,
        as_of: datetime | None = None,
    ) -> OrderImbalanceEntry | None:
        end_ts = as_of or self.buffer.latest_timestamp((code,))
        if end_ts is None:
            return None

        series, prefix = self.buffer.window_series(
            code,
            end=end_ts,
            duration=window.duration,
            include_prefetch=True,
        )
        if not series:
            return None

        last_snapshot = series[-1]
        start_ts = end_ts - window.duration
        baseline = _select_baseline(series, prefix, start_ts)

        obi = self._calc_obi(last_snapshot)
        speed = self._calc_speed(baseline, last_snapshot, window.duration)
        eis = self._calc_eis(last_snapshot, speed)
        ntm = self._calc_ntm(baseline, last_snapshot)

        return OrderImbalanceEntry(
            code=last_snapshot.code,
            name=last_snapshot.name,
            obi=obi,
            eis=eis,
            ntm=ntm,
            ts=end_ts,
            data_source=self.data_source,
        )

    def _calc_obi(self, snapshot: MarketSnapshot) -> Decimal:
        bid = sum(int(v) for v in snapshot.bid_volumes[: self.depth])
        ask = sum(int(v) for v in snapshot.ask_volumes[: self.depth])
        total = bid + ask
        if total == 0:
            return Decimal("0")
        return Decimal(bid - ask) / Decimal(total)

    def _calc_speed(
        self,
        baseline: MarketSnapshot,
        last_snapshot: MarketSnapshot,
        duration: timedelta,
    ) -> Decimal:
        delta = _to_decimal(last_snapshot.amount) - _to_decimal(baseline.amount)
        seconds = Decimal(str(duration.total_seconds()))
        if seconds <= 0:
            return Decimal("0")
        return delta * Decimal("60") / seconds

    def _calc_eis(self, snapshot: MarketSnapshot, speed: Decimal) -> Decimal:
        if not snapshot.ask_prices or not snapshot.bid_prices:
            return Decimal("0")
        ask1 = _to_decimal(snapshot.ask_prices[0])
        bid1 = _to_decimal(snapshot.bid_prices[0])
        mid = (ask1 + bid1) / Decimal("2") if ask1 and bid1 else Decimal("0")
        if mid == 0:
            return Decimal("0")
        spread = ask1 - bid1
        return (spread / mid) * speed

    def _calc_ntm(self, baseline: MarketSnapshot, last_snapshot: MarketSnapshot) -> Decimal:
        base = baseline.num_trades or 0
        latest = last_snapshot.num_trades or 0
        delta = max(latest - base, 0)
        return Decimal(delta)
