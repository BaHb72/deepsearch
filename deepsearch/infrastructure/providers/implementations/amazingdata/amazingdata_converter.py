# encoding:utf-8
"""
AmazingData 数据转换器
将 AmazingData 的数据格式转换为系统统一格式
"""

from datetime import datetime
from typing import Callable, Mapping, Optional, Sequence, Union, cast

import pandas as pd
from loguru import logger

from .amazingdata_types import (
    FIELD_MAPPING,
    DragonTigerRecord,
    DragonTigerSeat,
    KlineBarMessage,
    OrderBookSnapshot,
    RawDataMapping,
    RawDataSequence,
    ShareholderSeat,
    ShareholderSnapshot,
    SnapshotFuture,
    SnapshotHKT,
    SnapshotIndex,
    SnapshotOption,
    SnapshotPayload,
    SnapshotQuote,
    SubscriptionMessage,
    TickMessage,
)


def _coalesce(*values: object | None) -> object | None:
    """按顺序返回首个有效值，支持保留零值与布尔假值"""

    if not values:
        return None

    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            # 空字符串视为无效，继续尝试后续值
            continue
        return value

    return None


def _ensure_float(value: object | None, default: float = 0.0) -> float:
    """将任意类型转换为 float，无法转换时返回默认值"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return float(stripped)
        except ValueError:
            return default
    return default


def _normalize_trade_time(value: object | None) -> str:
    """����ʱ��ֵ����תΪ�ɶ��õ����ַ���"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    value_str = str(value).strip()
    if not value_str:
        return ""
    if value_str.isdigit():
        if len(value_str) == 14:
            return (
                f"{value_str[:4]}-{value_str[4:6]}-{value_str[6:8]} "
                f"{value_str[8:10]}:{value_str[10:12]}:{value_str[12:14]}"
            )
        if len(value_str) == 12:
            return (
                f"{value_str[:4]}-{value_str[4:6]}-{value_str[6:8]} "
                f"{value_str[8:10]}:{value_str[10:12]}:00"
            )
        if len(value_str) == 8:
            return f"{value_str[:4]}-{value_str[4:6]}-{value_str[6:8]}"
    return value_str


def _fill_order_book(snapshot: Mapping[str, object], result: dict[str, object]) -> None:
    """�����ݲ�ѯ���Ľ��, ��������������"""
    for i in range(1, 6):
        bid_price = _coalesce(snapshot.get(f"bid_price{i}"), snapshot.get(f"bid{i}"))
        bid_volume = _coalesce(
            snapshot.get(f"bid_volume{i}"),
            snapshot.get(f"bid{i}_volume"),
            snapshot.get(f"bid{i}_vol"),
        )
        ask_price = _coalesce(snapshot.get(f"ask_price{i}"), snapshot.get(f"ask{i}"))
        ask_volume = _coalesce(
            snapshot.get(f"ask_volume{i}"),
            snapshot.get(f"ask{i}_volume"),
            snapshot.get(f"ask{i}_vol"),
        )

        result[f"bid_price{i}"] = _ensure_float(bid_price)
        result[f"bid_volume{i}"] = _ensure_int(bid_volume)
        result[f"ask_price{i}"] = _ensure_float(ask_price)
        result[f"ask_volume{i}"] = _ensure_int(ask_volume)


def _ensure_mapping(data: object) -> Mapping[str, object]:
    """�����κβ������ص� Mapping ��ʽ"""
    if isinstance(data, Mapping):
        return cast(Mapping[str, object], data)
    if hasattr(data, "__dict__"):
        return cast(Mapping[str, object], getattr(data, "__dict__", {}))
    return cast(Mapping[str, object], {})


def _ensure_int(value: object | None, default: int = 0) -> int:
    """将任意类型转换为 int，无法转换时返回默认值"""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(float(stripped))
        except ValueError:
            return default
    return default


RawFrameInput = Union[
    RawDataSequence,
    RawDataMapping,
    Mapping[str, Union[RawDataSequence, RawDataMapping, pd.DataFrame]],
    pd.DataFrame,
]

SnapshotInput = Union[Mapping[str, RawDataMapping], Sequence[RawDataMapping]]
DragonTigerInput = Union[
    Mapping[str, Union[Sequence[RawDataMapping], RawDataMapping]],
    Sequence[RawDataMapping],
]


class AmazingDataConverter:
    """
    AmazingData 数据格式转换器

    负责将 AmazingData SDK 返回的数据转换为系统标准格式
    """

    @staticmethod
    def convert_kline(data: RawFrameInput, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        转换K线数据

        Args:
            data: AmazingData K线原始数据
            symbol: 股票代码

        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            payload: object = data
            if isinstance(data, Mapping) and symbol and symbol in data:
                payload = data[symbol]

            if isinstance(payload, pd.DataFrame):
                df = payload.copy()
            elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
                df = pd.DataFrame(list(payload))
            elif isinstance(payload, Mapping):
                df = pd.DataFrame([payload])
            else:
                df = pd.DataFrame([payload])

            # 字段映射
            field_map = FIELD_MAPPING.get("kline", {})
            df.rename(columns=field_map, inplace=True)

            # 标准化关键字段
            required_fields = ["datetime", "open", "high", "low", "close", "volume"]
            for field in required_fields:
                if field not in df.columns:
                    if field == "datetime" and "time" in df.columns:
                        df["datetime"] = df["time"]
                    else:
                        logger.warning(f"K线数据缺失字段: {field}")

            # 时间处理
            if "datetime" in df.columns:
                if df["datetime"].dtype == "object":
                    df["datetime"] = pd.to_datetime(df["datetime"])
                elif df["datetime"].dtype in ["int64", "int32"]:
                    if df["datetime"].iloc[0] > 10000000000:
                        df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
                    else:
                        df["datetime"] = pd.to_datetime(df["datetime"], unit="s")

                df.set_index("datetime", inplace=True)

            numeric_columns = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "turnover_rate",
                "change",
                "change_percent",
            ]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"K线数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_snapshot(
        data: SnapshotInput,
        symbols: Optional[Sequence[str]] = None,
        snapshot_type: str = "level1",
    ) -> dict[str, SnapshotPayload]:
        """转换快照行情数据"""

        try:
            result: dict[str, SnapshotPayload] = {}
            normalized_type = snapshot_type.lower()
            converter_map: dict[str, Callable[[Mapping[str, object], str], SnapshotPayload]] = {
                "level1": AmazingDataConverter._convert_single_snapshot,
                "snapshot": AmazingDataConverter._convert_single_snapshot,
                "stock": AmazingDataConverter._convert_single_snapshot,
                "option": AmazingDataConverter._convert_option_snapshot,
                "snapshot_option": AmazingDataConverter._convert_option_snapshot,
                "future": AmazingDataConverter._convert_future_snapshot,
                "snapshot_future": AmazingDataConverter._convert_future_snapshot,
                "index": AmazingDataConverter._convert_index_snapshot,
                "snapshot_index": AmazingDataConverter._convert_index_snapshot,
                "hkt": AmazingDataConverter._convert_hkt_snapshot,
                "snapshot_hkt": AmazingDataConverter._convert_hkt_snapshot,
            }
            converter = converter_map.get(
                normalized_type, AmazingDataConverter._convert_single_snapshot
            )

            if isinstance(data, Mapping):
                for raw_symbol, snapshot in data.items():
                    symbol_key = str(raw_symbol)
                    snapshot_mapping = _ensure_mapping(snapshot)
                    result[symbol_key] = converter(snapshot_mapping, symbol_key)
            else:
                for index, item in enumerate(data):
                    snapshot_mapping = _ensure_mapping(item)
                    raw_symbol_value = snapshot_mapping.get("code") or snapshot_mapping.get(
                        "symbol"
                    )
                    if isinstance(raw_symbol_value, str) and raw_symbol_value:
                        symbol_key = raw_symbol_value
                    elif raw_symbol_value is not None:
                        symbol_key = str(raw_symbol_value)
                    elif symbols and index < len(symbols):
                        symbol_key = str(symbols[index])
                    else:
                        continue
                    result[symbol_key] = converter(snapshot_mapping, symbol_key)

            return result

        except Exception as e:
            logger.error(f"快照数据转换失败: {e}")
            return {}

    @staticmethod
    def _convert_single_snapshot(snapshot: Mapping[str, object], symbol: str) -> SnapshotQuote:
        """转换快照原始数据"""
        try:
            name_value = _coalesce(snapshot.get("name"), snapshot.get("security_name"), "")
            time_value = _coalesce(snapshot.get("trade_time"), snapshot.get("time"), "")
            last_raw = _coalesce(
                snapshot.get("last"), snapshot.get("last_price"), snapshot.get("latest_price"), 0
            )
            open_raw = _coalesce(snapshot.get("open"), snapshot.get("open_price"))
            high_raw = _coalesce(snapshot.get("high"), snapshot.get("high_price"))
            low_raw = _coalesce(snapshot.get("low"), snapshot.get("low_price"))
            close_raw = _coalesce(snapshot.get("close"), snapshot.get("close_price"))
            prev_close_raw = _coalesce(snapshot.get("pre_close"), snapshot.get("prev_close"))
            volume_raw = _coalesce(
                snapshot.get("volume"), snapshot.get("vol"), snapshot.get("trade_volume")
            )
            amount_raw = _coalesce(snapshot.get("amount"), snapshot.get("trade_amount"))
            turnover_raw = _coalesce(snapshot.get("turnover"), snapshot.get("turnover_value"))
            change_raw = snapshot.get("change")
            change_percent_raw = _coalesce(
                snapshot.get("change_rate"), snapshot.get("change_percent")
            )
            turnover_rate_raw = _coalesce(
                snapshot.get("turnover_rate"), snapshot.get("turnoverratio")
            )
            amplitude_raw = snapshot.get("amplitude")
            limit_up_raw = _coalesce(snapshot.get("high_limited"), snapshot.get("limit_up"))
            limit_down_raw = _coalesce(snapshot.get("low_limited"), snapshot.get("limit_down"))
            status_raw = _coalesce(snapshot.get("status"), snapshot.get("trade_status"), "normal")
            num_trades_raw = _coalesce(
                snapshot.get("num_trades"),
                snapshot.get("trade_count"),
                snapshot.get("trade_num"),
                snapshot.get("num_of_trades"),
            )

            result: dict[str, object] = {
                "code": str(
                    _coalesce(snapshot.get("code"), snapshot.get("symbol"), symbol) or symbol
                ),
                "name": str(name_value or ""),
                "trade_time": _normalize_trade_time(time_value),
                "last": _ensure_float(last_raw),
                "open": _ensure_float(open_raw),
                "high": _ensure_float(high_raw),
                "low": _ensure_float(low_raw),
                "close": _ensure_float(close_raw),
                "pre_close": _ensure_float(prev_close_raw),
                "volume": _ensure_float(volume_raw),
                "amount": _ensure_float(amount_raw),
                "num_trades": _ensure_float(num_trades_raw),
                "high_limited": _ensure_float(limit_up_raw),
                "low_limited": _ensure_float(limit_down_raw),
                "change": _ensure_float(change_raw),
                "change_percent": _ensure_float(change_percent_raw),
                "turnover_rate": _ensure_float(turnover_rate_raw),
                "amplitude": _ensure_float(amplitude_raw),
                "status": str(status_raw),
            }

            if turnover_raw is not None:
                result["turnover"] = _ensure_float(turnover_raw)
            avg_price_raw = _coalesce(snapshot.get("avg_price"), snapshot.get("average_price"))
            if avg_price_raw is not None:
                result["avg_price"] = _ensure_float(avg_price_raw)
            if snapshot.get("iopv") is not None:
                result["iopv"] = _ensure_float(snapshot.get("iopv"))
            if snapshot.get("nav") is not None:
                result["nav"] = _ensure_float(snapshot.get("nav"))
            if snapshot.get("premium_rate") is not None:
                result["premium_rate"] = _ensure_float(snapshot.get("premium_rate"))
            if snapshot.get("pre_settle") is not None:
                result["pre_settle"] = _ensure_float(snapshot.get("pre_settle"))
            if snapshot.get("settle_price") is not None:
                result["settle_price"] = _ensure_float(snapshot.get("settle_price"))
            if snapshot.get("pre_open_interest") is not None:
                result["pre_open_interest"] = _ensure_float(snapshot.get("pre_open_interest"))
            if snapshot.get("open_interest") is not None:
                result["open_interest"] = _ensure_float(snapshot.get("open_interest"))
            if snapshot.get("open_interest_delta") is not None:
                result["open_interest_delta"] = _ensure_float(snapshot.get("open_interest_delta"))
            trading_phase = _coalesce(snapshot.get("trading_phase_code"), "")
            if trading_phase:
                result["trading_phase_code"] = str(trading_phase)
            if snapshot.get("up_count") is not None:
                result["up_count"] = _ensure_int(snapshot.get("up_count"))
            if snapshot.get("down_count") is not None:
                result["down_count"] = _ensure_int(snapshot.get("down_count"))
            if snapshot.get("flat_count") is not None:
                result["flat_count"] = _ensure_int(snapshot.get("flat_count"))

            _fill_order_book(snapshot, result)

            return cast(SnapshotQuote, result)

        except Exception as e:
            logger.error(f"快照转换失败: {e}")
            return cast(SnapshotQuote, {"symbol": symbol, "error": str(e)})

    @staticmethod
    def _convert_option_snapshot(snapshot: Mapping[str, object], symbol: str) -> SnapshotOption:
        """转化 ETF 期权行情"""
        try:
            trade_time = _normalize_trade_time(
                _coalesce(snapshot.get("trade_time"), snapshot.get("time"), "")
            )
            result: dict[str, object] = {
                "code": str(
                    _coalesce(snapshot.get("code"), snapshot.get("symbol"), symbol) or symbol
                ),
                "trade_time": trade_time,
                "trading_phase_code": str(_coalesce(snapshot.get("trading_phase_code"), "") or ""),
                "total_long_position": _ensure_int(
                    _coalesce(snapshot.get("total_long_position"), snapshot.get("open_interest"))
                ),
                "volume": _ensure_float(_coalesce(snapshot.get("volume"), snapshot.get("vol"))),
                "amount": _ensure_float(
                    _coalesce(snapshot.get("amount"), snapshot.get("trade_amount"))
                ),
                "pre_close": _ensure_float(
                    _coalesce(snapshot.get("pre_close"), snapshot.get("prev_close"))
                ),
                "pre_settle": _ensure_float(snapshot.get("pre_settle")),
                "auction_price": _ensure_float(
                    _coalesce(snapshot.get("auction_price"), snapshot.get("callauction_price"))
                ),
                "auction_volume": _ensure_int(
                    _coalesce(snapshot.get("auction_volume"), snapshot.get("callauction_volume"))
                ),
                "last": _ensure_float(_coalesce(snapshot.get("last"), snapshot.get("last_price"))),
                "open": _ensure_float(_coalesce(snapshot.get("open"), snapshot.get("open_price"))),
                "high": _ensure_float(_coalesce(snapshot.get("high"), snapshot.get("high_price"))),
                "low": _ensure_float(_coalesce(snapshot.get("low"), snapshot.get("low_price"))),
                "close": _ensure_float(
                    _coalesce(snapshot.get("close"), snapshot.get("close_price"))
                ),
                "settle": _ensure_float(
                    _coalesce(snapshot.get("settle"), snapshot.get("settle_price"))
                ),
                "high_limited": _ensure_float(
                    _coalesce(snapshot.get("high_limited"), snapshot.get("limit_up"))
                ),
                "low_limited": _ensure_float(
                    _coalesce(snapshot.get("low_limited"), snapshot.get("limit_down"))
                ),
                "contract_type": str(
                    _coalesce(
                        snapshot.get("contract_type"),
                        snapshot.get("option_type"),
                        snapshot.get("call_put"),
                        "",
                    )
                ),
                "expire_date": _ensure_int(
                    _coalesce(
                        snapshot.get("expire_date"),
                        snapshot.get("expiry_date"),
                        snapshot.get("expiredate"),
                    )
                ),
                "underlying_security_code": str(
                    _coalesce(
                        snapshot.get("underlying_security_code"),
                        snapshot.get("underlying_security_cod"),
                        "",
                    )
                    or ""
                ),
                "exercise_price": _ensure_float(
                    _coalesce(snapshot.get("exercise_price"), snapshot.get("strike_price"))
                ),
            }
            _fill_order_book(snapshot, result)
            return cast(SnapshotOption, result)
        except Exception as e:
            logger.error(f"ETF 期权行情转换失败: {e}")
            return cast(
                SnapshotOption,
                {
                    "code": symbol,
                    "trade_time": "",
                    "trading_phase_code": "",
                    "total_long_position": 0,
                    "volume": 0.0,
                    "amount": 0.0,
                    "pre_close": 0.0,
                    "pre_settle": 0.0,
                    "auction_price": 0.0,
                    "auction_volume": 0,
                    "last": 0.0,
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.0,
                    "settle": 0.0,
                    "high_limited": 0.0,
                    "low_limited": 0.0,
                    "contract_type": "",
                    "expire_date": 0,
                    "underlying_security_code": "",
                    "exercise_price": 0.0,
                },
            )

    @staticmethod
    def _convert_future_snapshot(snapshot: Mapping[str, object], symbol: str) -> SnapshotFuture:
        """转化期货行情"""
        try:
            trade_time = _normalize_trade_time(
                _coalesce(snapshot.get("trade_time"), snapshot.get("time"), "")
            )
            result: dict[str, object] = {
                "code": str(
                    _coalesce(snapshot.get("code"), snapshot.get("symbol"), symbol) or symbol
                ),
                "trade_time": trade_time,
                "action_day": str(
                    _coalesce(snapshot.get("action_day"), snapshot.get("actionday"), "")
                ),
                "trading_day": str(
                    _coalesce(snapshot.get("trading_day"), snapshot.get("tradingday"), "")
                ),
                "pre_close": _ensure_float(
                    _coalesce(snapshot.get("pre_close"), snapshot.get("prev_close"))
                ),
                "pre_settle": _ensure_float(snapshot.get("pre_settle")),
                "pre_open_interest": _ensure_int(snapshot.get("pre_open_interest")),
                "open_interest": _ensure_int(snapshot.get("open_interest")),
                "last": _ensure_float(_coalesce(snapshot.get("last"), snapshot.get("last_price"))),
                "open": _ensure_float(_coalesce(snapshot.get("open"), snapshot.get("open_price"))),
                "high": _ensure_float(_coalesce(snapshot.get("high"), snapshot.get("high_price"))),
                "low": _ensure_float(_coalesce(snapshot.get("low"), snapshot.get("low_price"))),
                "close": _ensure_float(
                    _coalesce(snapshot.get("close"), snapshot.get("close_price"))
                ),
                "volume": _ensure_float(_coalesce(snapshot.get("volume"), snapshot.get("vol"))),
                "amount": _ensure_float(
                    _coalesce(snapshot.get("amount"), snapshot.get("trade_amount"))
                ),
                "high_limited": _ensure_float(
                    _coalesce(snapshot.get("high_limited"), snapshot.get("limit_up"))
                ),
                "low_limited": _ensure_float(
                    _coalesce(snapshot.get("low_limited"), snapshot.get("limit_down"))
                ),
                "average_price": _ensure_float(
                    _coalesce(snapshot.get("average_price"), snapshot.get("avg_price"))
                ),
                "settle": _ensure_float(
                    _coalesce(snapshot.get("settle"), snapshot.get("settle_price"))
                ),
            }
            _fill_order_book(snapshot, result)
            return cast(SnapshotFuture, result)
        except Exception as e:
            logger.error(f"期货行情转换失败: {e}")
            return cast(
                SnapshotFuture,
                {
                    "code": symbol,
                    "trade_time": "",
                    "action_day": "",
                    "trading_day": "",
                    "pre_close": 0.0,
                    "pre_settle": 0.0,
                    "pre_open_interest": 0,
                    "open_interest": 0,
                    "last": 0.0,
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.0,
                    "volume": 0.0,
                    "amount": 0.0,
                    "high_limited": 0.0,
                    "low_limited": 0.0,
                    "average_price": 0.0,
                    "settle": 0.0,
                },
            )

    @staticmethod
    def _convert_index_snapshot(snapshot: Mapping[str, object], symbol: str) -> SnapshotIndex:
        """转化指数行情"""
        try:
            return cast(
                SnapshotIndex,
                {
                    "code": str(
                        _coalesce(snapshot.get("code"), snapshot.get("symbol"), symbol) or symbol
                    ),
                    "trade_time": _normalize_trade_time(
                        _coalesce(snapshot.get("trade_time"), snapshot.get("time"), "")
                    ),
                    "last": _ensure_float(
                        _coalesce(snapshot.get("last"), snapshot.get("last_price"))
                    ),
                    "pre_close": _ensure_float(
                        _coalesce(snapshot.get("pre_close"), snapshot.get("prev_close"))
                    ),
                    "open": _ensure_float(
                        _coalesce(snapshot.get("open"), snapshot.get("open_price"))
                    ),
                    "high": _ensure_float(
                        _coalesce(snapshot.get("high"), snapshot.get("high_price"))
                    ),
                    "low": _ensure_float(_coalesce(snapshot.get("low"), snapshot.get("low_price"))),
                    "close": _ensure_float(
                        _coalesce(snapshot.get("close"), snapshot.get("close_price"))
                    ),
                    "volume": _ensure_float(_coalesce(snapshot.get("volume"), snapshot.get("vol"))),
                    "amount": _ensure_float(
                        _coalesce(snapshot.get("amount"), snapshot.get("trade_amount"))
                    ),
                },
            )
        except Exception as e:
            logger.error(f"指数行情转换失败: {e}")
            return cast(
                SnapshotIndex,
                {
                    "code": symbol,
                    "trade_time": "",
                    "last": 0.0,
                    "pre_close": 0.0,
                    "open": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "close": 0.0,
                    "volume": 0.0,
                    "amount": 0.0,
                },
            )

    @staticmethod
    def _convert_hkt_snapshot(snapshot: Mapping[str, object], symbol: str) -> SnapshotHKT:
        """转化港股通行情"""
        try:
            result: dict[str, object] = {
                "code": str(
                    _coalesce(snapshot.get("code"), snapshot.get("symbol"), symbol) or symbol
                ),
                "trade_time": _normalize_trade_time(
                    _coalesce(snapshot.get("trade_time"), snapshot.get("time"), "")
                ),
                "pre_close": _ensure_float(
                    _coalesce(snapshot.get("pre_close"), snapshot.get("prev_close"))
                ),
                "last": _ensure_float(_coalesce(snapshot.get("last"), snapshot.get("last_price"))),
                "high": _ensure_float(_coalesce(snapshot.get("high"), snapshot.get("high_price"))),
                "low": _ensure_float(_coalesce(snapshot.get("low"), snapshot.get("low_price"))),
                "volume": _ensure_float(_coalesce(snapshot.get("volume"), snapshot.get("vol"))),
                "amount": _ensure_float(
                    _coalesce(snapshot.get("amount"), snapshot.get("trade_amount"))
                ),
                "nominal_price": _ensure_float(snapshot.get("nominal_price")),
                "ref_price": _ensure_float(
                    _coalesce(snapshot.get("ref_price"), snapshot.get("reference_price"))
                ),
                "bid_price_limit_up": _ensure_float(
                    _coalesce(snapshot.get("bid_price_limit_up"), snapshot.get("bidlimit_up"))
                ),
                "bid_price_limit_down": _ensure_float(
                    _coalesce(snapshot.get("bid_price_limit_down"), snapshot.get("bidlimit_down"))
                ),
                "offer_price_limit_up": _ensure_float(
                    _coalesce(snapshot.get("offer_price_limit_up"), snapshot.get("asklimit_up"))
                ),
                "offer_price_limit_down": _ensure_float(
                    _coalesce(snapshot.get("offer_price_limit_down"), snapshot.get("asklimit_down"))
                ),
                "high_limited": _ensure_float(
                    _coalesce(snapshot.get("high_limited"), snapshot.get("limit_up"))
                ),
                "low_limited": _ensure_float(
                    _coalesce(snapshot.get("low_limited"), snapshot.get("limit_down"))
                ),
                "trading_phase_code": str(_coalesce(snapshot.get("trading_phase_code"), "") or ""),
            }
            _fill_order_book(snapshot, result)
            return cast(SnapshotHKT, result)
        except Exception as e:
            logger.error(f"港股通行情转换失败: {e}")
            return cast(
                SnapshotHKT,
                {
                    "code": symbol,
                    "trade_time": "",
                    "pre_close": 0.0,
                    "last": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "volume": 0.0,
                    "amount": 0.0,
                    "nominal_price": 0.0,
                    "ref_price": 0.0,
                    "bid_price_limit_up": 0.0,
                    "bid_price_limit_down": 0.0,
                    "offer_price_limit_up": 0.0,
                    "offer_price_limit_down": 0.0,
                    "high_limited": 0.0,
                    "low_limited": 0.0,
                    "trading_phase_code": "",
                },
            )

    @staticmethod
    def convert_financial(data: RawFrameInput, symbol: str, report_type: str) -> pd.DataFrame:
        """
        转换财务数据

        Args:
            data: AmazingData 财务原始数据
            symbol: 股票代码
            report_type: 报表类型

        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            # 提取股票数据
            if isinstance(data, dict) and symbol in data:
                stock_data = data[symbol]
            else:
                stock_data = data

            # 转换为 DataFrame
            if isinstance(stock_data, list):
                df = pd.DataFrame(stock_data)
            elif isinstance(stock_data, pd.DataFrame):
                df = stock_data.copy()
            elif isinstance(stock_data, dict):
                # 如果是单条记录
                df = pd.DataFrame([stock_data])
            else:
                return pd.DataFrame()

            # 添加元信息
            df["symbol"] = symbol
            df["report_type"] = report_type

            # 时间字段处理
            date_fields = ["report_date", "announce_date", "end_date"]
            for field in date_fields:
                if field in df.columns:
                    df[field] = pd.to_datetime(df[field])

            # 设置索引
            if "report_date" in df.columns:
                df.set_index("report_date", inplace=True)
                df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"财务数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_tick(data: RawFrameInput, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        转换逐笔数据

        Args:
            data: AmazingData 逐笔原始数据
            symbol: 股票代码

        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            # 处理不同格式
            if isinstance(data, dict) and symbol and symbol in data:
                tick_data = data[symbol]
            else:
                tick_data = data

            # 转换为 DataFrame
            if isinstance(tick_data, list):
                df = pd.DataFrame(tick_data)
            elif isinstance(tick_data, pd.DataFrame):
                df = tick_data.copy()
            else:
                return pd.DataFrame()

            # 字段标准化
            column_map = {
                "deal_time": "time",
                "deal_price": "price",
                "deal_volume": "volume",
                "deal_amount": "amount",
                "bs_flag": "direction",
            }
            df.rename(columns=column_map, inplace=True)

            # 时间处理
            if "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"])
                df.set_index("time", inplace=True)

            # 方向映射
            if "direction" in df.columns:
                direction_map = {1: "B", 2: "S", 0: "N"}
                df["direction"] = df["direction"].map(direction_map).fillna("N")

            # 添加股票代码
            if symbol:
                df["symbol"] = symbol

            return df

        except Exception as e:
            logger.error(f"逐笔数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_order_book(
        data: Mapping[str, object], symbol: Optional[str] = None
    ) -> OrderBookSnapshot:
        """转换盘口数据（Level2）"""
        try:
            if not data:
                return cast(OrderBookSnapshot, {})

            bid_queue: list[int] = []
            ask_queue: list[int] = []
            bid_prices: list[float] = []
            ask_prices: list[float] = []
            bid_volumes: list[int] = []
            ask_volumes: list[int] = []

            result: OrderBookSnapshot = {
                "symbol": str(symbol or data.get("symbol", "")),
                "time": str(data.get("time", "")),
                "bid_queue": bid_queue,
                "ask_queue": ask_queue,
                "bid_prices": bid_prices,
                "ask_prices": ask_prices,
                "bid_volumes": bid_volumes,
                "ask_volumes": ask_volumes,
            }

            for i in range(1, 11):
                bid_price = data.get(f"bid{i}_price") or data.get(f"bid{i}")
                bid_volume = data.get(f"bid{i}_volume") or data.get(f"bid{i}_vol")
                ask_price = data.get(f"ask{i}_price") or data.get(f"ask{i}")
                ask_volume = data.get(f"ask{i}_volume") or data.get(f"ask{i}_vol")

                if bid_price:
                    bid_prices.append(_ensure_float(bid_price))
                    bid_volumes.append(_ensure_int(bid_volume))

                if ask_price:
                    ask_prices.append(_ensure_float(ask_price))
                    ask_volumes.append(_ensure_int(ask_volume))

            if (
                "bid_queue" in data
                and isinstance(data["bid_queue"], Sequence)
                and not isinstance(data["bid_queue"], (str, bytes))
            ):
                bid_queue.extend(
                    _ensure_int(item) for item in cast(Sequence[object], data["bid_queue"])
                )

            if (
                "ask_queue" in data
                and isinstance(data["ask_queue"], Sequence)
                and not isinstance(data["ask_queue"], (str, bytes))
            ):
                ask_queue.extend(
                    _ensure_int(item) for item in cast(Sequence[object], data["ask_queue"])
                )

            return result

        except Exception as e:
            logger.error(f"盘口数据转换失败: {e}")
            return cast(OrderBookSnapshot, {})

    @staticmethod
    def convert_shareholder(data: Mapping[str, object], symbol: str) -> ShareholderSnapshot:
        """转换股东数据"""
        try:
            if not data:
                return cast(ShareholderSnapshot, {})

            if isinstance(data, Mapping) and symbol in data:
                holder_data = cast(Mapping[str, object], data[symbol])
            else:
                holder_data = data

            top10_holders: list[ShareholderSeat] = []
            top10_tradable: list[ShareholderSeat] = []

            result_dict: dict[str, object] = {
                "symbol": symbol,
                "report_date": str(holder_data.get("report_date", "")),
                "shareholder_count": _ensure_int(holder_data.get("holder_num")),
                "avg_holding": _ensure_float(holder_data.get("avg_hold")),
                "institution_ratio": _ensure_float(holder_data.get("institution_ratio")),
                "concentration": _ensure_float(holder_data.get("concentration")),
                "top10_holders": top10_holders,
                "top10_tradable": top10_tradable,
            }

            if "top10_holders" in holder_data:
                for holder in cast(Sequence[Mapping[str, object]], holder_data["top10_holders"]):
                    holder_entry: ShareholderSeat = {
                        "name": str(holder.get("holder_name", "")),
                        "holding": _ensure_float(holder.get("hold_num")),
                        "ratio": _ensure_float(holder.get("hold_ratio")),
                        "change": _ensure_float(holder.get("change")),
                    }
                    top10_holders.append(holder_entry)

            if "top10_tradable" in holder_data:
                for holder in cast(Sequence[Mapping[str, object]], holder_data["top10_tradable"]):
                    tradable_entry: ShareholderSeat = {
                        "name": str(holder.get("holder_name", "")),
                        "holding": _ensure_float(holder.get("hold_num")),
                        "ratio": _ensure_float(holder.get("hold_ratio")),
                        "change": _ensure_float(holder.get("change")),
                    }
                    top10_tradable.append(tradable_entry)

            return cast(ShareholderSnapshot, result_dict)

        except Exception as e:
            logger.error(f"股东数据转换失败: {e}")
            return cast(ShareholderSnapshot, {})

    @staticmethod
    def convert_dragon_tiger(
        data: DragonTigerInput, symbol: Optional[str] = None
    ) -> list[DragonTigerRecord]:
        """转换龙虎榜数据"""
        try:
            if not data:
                return []

            if isinstance(data, Mapping):
                if symbol and symbol in data:
                    raw_items = cast(Sequence[Mapping[str, object]], data[symbol])
                else:
                    raw_items = [cast(Mapping[str, object], data)]
            elif isinstance(data, Sequence):
                raw_items = [
                    cast(Mapping[str, object], item) for item in data if isinstance(item, Mapping)
                ]
            else:
                return []

            result: list[DragonTigerRecord] = []
            for item in raw_items:
                buy_list: list[DragonTigerSeat] = []
                sell_list: list[DragonTigerSeat] = []

                record_dict: dict[str, object] = {
                    "symbol": str(symbol or item.get("symbol", "")),
                    "trade_date": str(item.get("trade_date", "")),
                    "reason": str(item.get("reason", "")),
                    "buy_amount": _ensure_float(item.get("buy_amount")),
                    "sell_amount": _ensure_float(item.get("sell_amount")),
                    "net_amount": _ensure_float(item.get("net_amount")),
                    "turnover_rate": _ensure_float(item.get("turnover_rate")),
                    "buy_list": buy_list,
                    "sell_list": sell_list,
                }

                if "buy_list" in item:
                    for seat in cast(Sequence[Mapping[str, object]], item["buy_list"]):
                        buy_seat_entry: DragonTigerSeat = {
                            "name": str(seat.get("seat_name", "")),
                            "amount": _ensure_float(seat.get("buy_amount")),
                            "ratio": _ensure_float(seat.get("buy_ratio")),
                        }
                        buy_list.append(buy_seat_entry)

                if "sell_list" in item:
                    for seat in cast(Sequence[Mapping[str, object]], item["sell_list"]):
                        sell_seat_entry: DragonTigerSeat = {
                            "name": str(seat.get("seat_name", "")),
                            "amount": _ensure_float(seat.get("sell_amount")),
                            "ratio": _ensure_float(seat.get("sell_ratio")),
                        }
                        sell_list.append(sell_seat_entry)

                result.append(cast(DragonTigerRecord, record_dict))

            return result

        except Exception as e:
            logger.error(f"龙虎榜数据转换失败: {e}")
            return []

    @staticmethod
    def convert_margin_trading(data: RawFrameInput, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        转换融资融券数据

        Args:
            data: AmazingData 融资融券原始数据
            symbol: 股票代码

        Returns:
            标准化的 DataFrame
        """
        try:
            if not data:
                return pd.DataFrame()

            # 提取数据
            if isinstance(data, dict) and symbol and symbol in data:
                margin_data = data[symbol]
            else:
                margin_data = data

            # 转换为 DataFrame
            if isinstance(margin_data, list):
                df = pd.DataFrame(margin_data)
            elif isinstance(margin_data, pd.DataFrame):
                df = margin_data.copy()
            else:
                df = pd.DataFrame([margin_data])

            # 字段映射
            column_map = {
                "fin_balance": "margin_balance",
                "MARGIN_TRADE_BALANCE": "margin_balance",
                "fin_buy": "margin_buy",
                "MARGIN_BUY_VALUE": "margin_buy",
                "fin_repay": "margin_repay",
                "MARGIN_REPAY_VALUE": "margin_repay",
                "sec_balance": "short_balance",
                "STOCK_BALANCE": "short_balance",
                "sec_sell": "short_sell",
                "STOCK_SELL_VALUE": "short_sell",
                "sec_repay": "short_repay",
                "STOCK_REPAY_VALUE": "short_repay",
                "fin_sec_ratio": "margin_ratio",
                "MARGIN_RATIO": "margin_ratio",
            }
            df.rename(columns=column_map, inplace=True)

            # ���ӹ�Ʊ����
            if symbol:
                df["symbol"] = symbol

            # ʱ�䴦��
            if "TRADE_DATE" in df.columns and "trade_date" not in df.columns:
                df.rename(columns={"TRADE_DATE": "trade_date"}, inplace=True)
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df.set_index("trade_date", inplace=True)
                df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"融资融券数据转换失败: {e}")
            return pd.DataFrame()

    @staticmethod
    def convert_subscription_data(data: object, data_type: str) -> SubscriptionMessage:
        """转换订阅推送的数据格式"""
        try:
            result_dict: dict[str, object] = {
                "type": data_type,
                "timestamp": datetime.now().isoformat(),
                "data": None,
            }

            if data_type in {"snapshot", "snapshot_stock", "snapshot_etf"}:
                payload_map = _ensure_mapping(data)
                symbol_value = str(
                    _coalesce(
                        payload_map.get("code"),
                        payload_map.get("symbol"),
                        getattr(data, "code", None),
                        getattr(data, "symbol", ""),
                    )
                    or ""
                )
                result_dict["data"] = AmazingDataConverter._convert_single_snapshot(
                    payload_map, symbol_value
                )

            elif data_type in {"snapshot_option"}:
                payload_map = _ensure_mapping(data)
                symbol_value = str(
                    _coalesce(
                        payload_map.get("code"),
                        payload_map.get("symbol"),
                        getattr(data, "code", None),
                        getattr(data, "symbol", ""),
                    )
                    or ""
                )
                result_dict["data"] = AmazingDataConverter._convert_option_snapshot(
                    payload_map, symbol_value
                )

            elif data_type in {"snapshot_future"}:
                payload_map = _ensure_mapping(data)
                symbol_value = str(
                    _coalesce(
                        payload_map.get("code"),
                        payload_map.get("symbol"),
                        getattr(data, "code", None),
                        getattr(data, "symbol", ""),
                    )
                    or ""
                )
                result_dict["data"] = AmazingDataConverter._convert_future_snapshot(
                    payload_map, symbol_value
                )

            elif data_type in {"snapshot_index"}:
                payload_map = _ensure_mapping(data)
                symbol_value = str(
                    _coalesce(
                        payload_map.get("code"),
                        payload_map.get("symbol"),
                        getattr(data, "code", None),
                        getattr(data, "symbol", ""),
                    )
                    or ""
                )
                result_dict["data"] = AmazingDataConverter._convert_index_snapshot(
                    payload_map, symbol_value
                )

            elif data_type in {"snapshot_hkt"}:
                payload_map = _ensure_mapping(data)
                symbol_value = str(
                    _coalesce(
                        payload_map.get("code"),
                        payload_map.get("symbol"),
                        getattr(data, "code", None),
                        getattr(data, "symbol", ""),
                    )
                    or ""
                )
                result_dict["data"] = AmazingDataConverter._convert_hkt_snapshot(
                    payload_map, symbol_value
                )

            elif data_type == "kline":
                bar_dict: dict[str, object] = {
                    "symbol": str(getattr(data, "symbol", "")),
                    "period": str(getattr(data, "period", "")),
                    "datetime": str(getattr(data, "time", "")),
                    "open": _ensure_float(getattr(data, "open", None)),
                    "high": _ensure_float(getattr(data, "high", None)),
                    "low": _ensure_float(getattr(data, "low", None)),
                    "close": _ensure_float(getattr(data, "close", None)),
                    "volume": _ensure_float(getattr(data, "volume", None)),
                    "amount": _ensure_float(getattr(data, "amount", None)),
                }
                result_dict["data"] = cast(KlineBarMessage, bar_dict)

            elif data_type == "tick":
                tick_dict: dict[str, object] = {
                    "symbol": str(getattr(data, "symbol", "")),
                    "time": str(getattr(data, "time", "")),
                    "price": _ensure_float(getattr(data, "price", None)),
                    "volume": _ensure_int(getattr(data, "volume", None)),
                    "direction": str(getattr(data, "direction", "N")),
                }
                result_dict["data"] = cast(TickMessage, tick_dict)

            else:
                if isinstance(data, Mapping):
                    result_dict["data"] = cast(Mapping[str, object], data)
                elif hasattr(data, "__dict__"):
                    result_dict["data"] = cast(Mapping[str, object], getattr(data, "__dict__", {}))
                else:
                    result_dict["data"] = data

            return cast(SubscriptionMessage, result_dict)

        except Exception as e:
            logger.error(f"订阅消息转换失败: {e}")
            return cast(SubscriptionMessage, {"type": data_type, "error": str(e)})
