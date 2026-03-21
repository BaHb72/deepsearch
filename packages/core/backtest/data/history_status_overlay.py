"""交易状态覆盖工具。

将 `history_stock_status` 数据解析为交易日状态快照，并覆盖到分钟/日线数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime
from typing import Any, Optional

import pandas as pd


class HistoryStatusOverlayError(ValueError):
    """交易状态覆盖错误。"""

    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


@dataclass(frozen=True)
class BacktestHistoryStatusSnapshot:
    """回测交易日状态快照（来自 history_stock_status）。"""

    high_limited: float
    low_limited: float
    is_suspended: bool


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


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except Exception:
        return default


def _resolve_column_name(columns: pd.Index, aliases: list[str]) -> Optional[str]:
    alias_map = {str(column).strip().lower(): str(column) for column in columns}
    for alias in aliases:
        column_name = alias_map.get(alias.strip().lower())
        if column_name:
            return column_name
    return None


def _parse_trade_day_value(raw_value: Any) -> Optional[date_type]:
    dt = _to_datetime_safe(raw_value)
    if dt is not None:
        return dt.date()

    if raw_value is None:
        return None

    if isinstance(raw_value, (int, float)):
        raw_text = str(int(raw_value))
    else:
        raw_text = str(raw_value).strip()
    if not raw_text:
        return None

    digits = "".join(ch for ch in raw_text if ch.isdigit())
    if len(digits) < 8:
        return None
    try:
        return datetime.strptime(digits[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _build_symbol_aliases(symbol: str) -> set[str]:
    value = symbol.strip().upper().replace("-", "").replace("_", "")
    if not value:
        return set()

    aliases: set[str] = {value.replace(".", "")}

    if "." in value:
        code_part, market_part = value.split(".", 1)
        code_part = code_part.strip()
        market_part = market_part.strip()
        if code_part and market_part:
            aliases.add(code_part)
            aliases.add(f"{market_part}{code_part}")
            aliases.add(f"{code_part}{market_part}")
    else:
        for market_part in ("SH", "SZ", "BJ"):
            if value.startswith(market_part) and len(value) > len(market_part):
                code_part = value[len(market_part) :]
                aliases.add(code_part)
                aliases.add(f"{code_part}.{market_part}".replace(".", ""))
            if value.endswith(market_part) and len(value) > len(market_part):
                code_part = value[: -len(market_part)]
                aliases.add(code_part)
                aliases.add(f"{code_part}.{market_part}".replace(".", ""))

    return {item for item in aliases if item}


def _coerce_bool_flag(raw_value: Any) -> Optional[bool]:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return None

    if isinstance(raw_value, (int, float)):
        return bool(int(raw_value))

    text = str(raw_value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "停牌", "suspended"}:
        return True
    if text in {"0", "false", "f", "no", "n", "正常", "active", "trading"}:
        return False
    return None


def coerce_status_dataframe(raw_payload: Any) -> pd.DataFrame:
    """将 history_stock_status 返回体统一为 DataFrame。"""

    if isinstance(raw_payload, pd.DataFrame):
        return raw_payload.copy()
    if isinstance(raw_payload, list):
        return pd.DataFrame(raw_payload)
    if isinstance(raw_payload, dict):
        data = raw_payload.get("data")
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if isinstance(data, list):
            return pd.DataFrame(data)
    return pd.DataFrame()


def extract_trade_day_status_snapshot(
    status_df: pd.DataFrame,
    *,
    symbol: str,
    trade_day: date_type,
) -> BacktestHistoryStatusSnapshot:
    """从 history_stock_status 中提取某交易日状态快照。"""

    if status_df.empty:
        raise HistoryStatusOverlayError(
            f"{symbol} history_stock_status 数据为空",
            not_found=True,
        )

    date_col = _resolve_column_name(status_df.columns, ["trade_date", "TRADE_DATE", "date", "DATE"])
    if date_col is None:
        raise HistoryStatusOverlayError(
            "history_stock_status 缺少 TRADE_DATE 字段，无法用于强制回测约束"
        )

    symbol_col = _resolve_column_name(
        status_df.columns,
        ["market_code", "MARKET_CODE", "symbol", "SYMBOL", "code", "CODE"],
    )
    symbol_aliases = _build_symbol_aliases(symbol)

    matched_rows: list[pd.Series] = []
    for _, row in status_df.iterrows():
        row_trade_day = _parse_trade_day_value(row.get(date_col))
        if row_trade_day != trade_day:
            continue

        if symbol_col is not None and symbol_aliases:
            row_symbol_aliases = _build_symbol_aliases(str(row.get(symbol_col, "")))
            if row_symbol_aliases and not (row_symbol_aliases & symbol_aliases):
                continue
        matched_rows.append(row)

    if not matched_rows:
        raise HistoryStatusOverlayError(
            f"{symbol} 在 {trade_day} 无 history_stock_status 记录，回测已阻断",
            not_found=True,
        )

    selected_row = matched_rows[-1]
    high_col = _resolve_column_name(
        status_df.columns,
        ["high_limited", "HIGH_LIMITED", "limit_up", "LIMIT_UP"],
    )
    low_col = _resolve_column_name(
        status_df.columns,
        ["low_limited", "LOW_LIMITED", "limit_down", "LIMIT_DOWN"],
    )
    suspended_col = _resolve_column_name(
        status_df.columns,
        ["is_susp_sec", "IS_SUSP_SEC", "is_suspended", "IS_SUSPENDED", "suspended", "SUSPENDED"],
    )

    if high_col is None or low_col is None or suspended_col is None:
        raise HistoryStatusOverlayError(
            "history_stock_status 缺少关键字段（HIGH_LIMITED/LOW_LIMITED/IS_SUSP_SEC），无法执行强制约束回测"
        )

    high_limited = _to_float(selected_row.get(high_col), default=0.0)
    low_limited = _to_float(selected_row.get(low_col), default=0.0)
    suspended_flag = _coerce_bool_flag(selected_row.get(suspended_col))

    if high_limited <= 0 or low_limited <= 0:
        raise HistoryStatusOverlayError("history_stock_status 涨跌停价格无效，回测已阻断")
    if suspended_flag is None:
        raise HistoryStatusOverlayError("history_stock_status 停牌标记无效，回测已阻断")

    return BacktestHistoryStatusSnapshot(
        high_limited=high_limited,
        low_limited=low_limited,
        is_suspended=suspended_flag,
    )


def apply_trade_day_status_snapshot(
    bars_df: pd.DataFrame,
    snapshot: BacktestHistoryStatusSnapshot,
) -> pd.DataFrame:
    """将交易日状态快照覆盖到行情数据。"""

    merged_df = bars_df.copy()
    merged_df["high_limited"] = float(snapshot.high_limited)
    merged_df["low_limited"] = float(snapshot.low_limited)
    merged_df["is_suspended"] = bool(snapshot.is_suspended)
    return merged_df


def _resolve_trade_day_series(bars_df: pd.DataFrame) -> pd.Series:
    """从行情数据中解析交易日序列。"""

    if isinstance(bars_df.index, pd.DatetimeIndex):
        index_series = pd.Series(bars_df.index, index=bars_df.index)
        return pd.to_datetime(index_series, errors="coerce").dt.date

    for column_name in ("datetime", "date", "time", "trade_date", "TRADE_DATE"):
        if column_name not in bars_df.columns:
            continue
        parsed_series = pd.to_datetime(pd.Series(bars_df[column_name]), errors="coerce")
        has_valid_trade_day = any(not bool(pd.isna(value)) for value in parsed_series.tolist())
        if has_valid_trade_day:
            return parsed_series.dt.date

    raise HistoryStatusOverlayError("行情数据缺少可解析的交易日字段，无法应用状态约束")


def apply_history_status_overlay(
    bars_df: pd.DataFrame,
    status_df: pd.DataFrame,
    *,
    symbol: str,
    strict: bool = True,
) -> pd.DataFrame:
    """按交易日批量覆盖交易状态。

    Args:
        bars_df: 分钟或日线行情。
        status_df: history_stock_status 明细。
        symbol: 标的代码。
        strict: True 时任一交易日缺失状态即抛错阻断。
    """

    if bars_df.empty:
        return bars_df.copy()

    trade_days = _resolve_trade_day_series(bars_df)
    unique_days = [day for day in sorted(set(trade_days.dropna().tolist())) if day is not None]

    if not unique_days:
        raise HistoryStatusOverlayError("行情数据未包含有效交易日，无法应用状态约束")

    snapshots: dict[date_type, BacktestHistoryStatusSnapshot] = {}
    missing_days: list[date_type] = []

    for trade_day in unique_days:
        try:
            snapshots[trade_day] = extract_trade_day_status_snapshot(
                status_df,
                symbol=symbol,
                trade_day=trade_day,
            )
        except HistoryStatusOverlayError:
            missing_days.append(trade_day)

    if strict and missing_days:
        day_text = ",".join(day.isoformat() for day in missing_days[:5])
        if len(missing_days) > 5:
            day_text = f"{day_text}..."
        raise HistoryStatusOverlayError(
            f"{symbol} 缺少交易状态快照({day_text})，回测已阻断",
            not_found=True,
        )

    if not snapshots:
        if strict:
            raise HistoryStatusOverlayError(
                f"{symbol} 未匹配到任何交易状态快照，回测已阻断",
                not_found=True,
            )
        return bars_df.copy()

    merged_df = bars_df.copy()
    day_to_snapshot = trade_days.map(snapshots.get)
    matched_mask_values = [not bool(pd.isna(value)) for value in day_to_snapshot.tolist()]
    matched_mask = pd.Series(matched_mask_values, index=merged_df.index, dtype=bool)

    if strict and not all(matched_mask_values):
        raise HistoryStatusOverlayError(
            f"{symbol} 存在交易日未匹配状态快照，回测已阻断", not_found=True
        )

    if "high_limited" not in merged_df.columns:
        merged_df["high_limited"] = pd.NA
    if "low_limited" not in merged_df.columns:
        merged_df["low_limited"] = pd.NA
    if "is_suspended" not in merged_df.columns:
        merged_df["is_suspended"] = False

    if any(matched_mask_values):
        matched_snapshots = day_to_snapshot[matched_mask]
        merged_df.loc[matched_mask, "high_limited"] = matched_snapshots.map(
            lambda item: float(item.high_limited)
        )
        merged_df.loc[matched_mask, "low_limited"] = matched_snapshots.map(
            lambda item: float(item.low_limited)
        )
        merged_df.loc[matched_mask, "is_suspended"] = matched_snapshots.map(
            lambda item: bool(item.is_suspended)
        )

    return merged_df
