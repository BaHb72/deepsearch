# encoding:utf-8
"""
AmazingData 参数守卫与归一化工具。

提供以下能力：
- 本地缓存 / 远端日期区间参数互斥校验
- security_type / period 枚举归一化与白名单校验
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Mapping, Tuple

from deepsearch.infrastructure.providers.interfaces.base import DataProviderError
from .amazingdata_types import AmazingDataPeriod, AmazingDataSecurityType, convert_period
from .logging_utils import log_info, log_warning


class CacheParamMode(str, Enum):
    """本地缓存参数组的选择结果。"""

    LOCAL_CACHE = "local_cache"
    REMOTE_RANGE = "remote_range"
    NONE = "none"


_LOCAL_GROUP_KEYS: Tuple[str, ...] = ("local_path", "is_local")
_REMOTE_GROUP_KEYS: Tuple[str, ...] = ("begin_date", "end_date")


def _has_effective_value(value: object | None) -> bool:
    """判断值是否可视为有效（用于检测参数是否显式给出）。"""

    if isinstance(value, bool):
        return True
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _normalize_local_path(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(slots=True)
class CachePolicy:
    """Sanitized cache configuration derived from user input."""

    mode: CacheParamMode
    values: Dict[str, object | None]

    @property
    def is_local(self) -> bool:
        return self.mode is CacheParamMode.LOCAL_CACHE

    @property
    def is_remote(self) -> bool:
        return self.mode is CacheParamMode.REMOTE_RANGE

    @classmethod
    def from_params(
            cls,
            *,
            context: str,
            local_path: object | None,
            is_local: object | None,
            begin_date: object | None,
            end_date: object | None,
    ) -> "CachePolicy":
        mode, data = sanitize_cache_params(
            local_path=local_path,
            is_local=is_local,
            begin_date=begin_date,
            end_date=end_date,
            context=context,
        )
        return cls(mode=mode, values=data)

    @classmethod
    def from_kwargs(cls, *, context: str, kwargs: Mapping[str, object]) -> "CachePolicy":
        mode, data = sanitize_cache_kwargs(kwargs, context=context)
        return cls(mode=mode, values=data)

    def apply(self, original: Mapping[str, object]) -> Dict[str, object]:
        merged = dict(original)
        for key in _LOCAL_GROUP_KEYS + _REMOTE_GROUP_KEYS:
            value = self.values.get(key)
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        return merged

    def get(self, key: str) -> object | None:
        return self.values.get(key)


def sanitize_cache_params(
        *,
        local_path: object | None,
        is_local: object | None,
        begin_date: object | None,
        end_date: object | None,
        context: str,
) -> tuple[CacheParamMode, Dict[str, object | None]]:
    """
    校验并整理本地缓存与远端日期区间参数组合。

    返回值中的字典始终包含 local_path / is_local / begin_date / end_date 四个键，
    其中无效的键会被置为 None。
    """

    has_local_group = _has_effective_value(local_path) or is_local is not None
    has_remote_group = _has_effective_value(begin_date) or _has_effective_value(end_date)

    normalized_path = _normalize_local_path(local_path)
    normalized_is_local = None if is_local is None else bool(is_local)

    result: Dict[str, object | None] = {
        "local_path": normalized_path,
        "is_local": normalized_is_local,
        "begin_date": begin_date,
        "end_date": end_date,
    }

    if has_local_group and has_remote_group:
        log_warning("检测到本地缓存与远程区间参数同时存在，自动切换为远程模式", action="cache_params",
                    metadata={"context": context})
        result["local_path"] = None
        result["is_local"] = None
        return CacheParamMode.REMOTE_RANGE, result

    if has_local_group:
        if result["is_local"] is None:
            result["is_local"] = True
        result["begin_date"] = None
        result["end_date"] = None
        return CacheParamMode.LOCAL_CACHE, result

    if has_remote_group:
        result["local_path"] = None
        result["is_local"] = None
        return CacheParamMode.REMOTE_RANGE, result

    # 未显式指定任一组
    result["local_path"] = None
    result["is_local"] = None if is_local is None else bool(is_local)
    result["begin_date"] = None
    result["end_date"] = None
    return CacheParamMode.NONE, result


def sanitize_cache_kwargs(
        kwargs: Mapping[str, object],
        *,
        context: str,
) -> tuple[CacheParamMode, Dict[str, object]]:
    """针对 kwargs 版本的参数整理工具。"""

    mode, sanitized = sanitize_cache_params(
        local_path=kwargs.get("local_path"),
        is_local=kwargs.get("is_local"),
        begin_date=kwargs.get("begin_date"),
        end_date=kwargs.get("end_date"),
        context=context,
    )
    merged: Dict[str, object] = dict(kwargs)
    for key in _LOCAL_GROUP_KEYS + _REMOTE_GROUP_KEYS:
        value = sanitized.get(key)
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return mode, merged


_SECURITY_VALUE_LOOKUP: Dict[str, str] = {
    item.value.lower(): item.value for item in AmazingDataSecurityType
}
_SECURITY_NAME_LOOKUP: Dict[str, str] = {
    item.name.lower(): item.value for item in AmazingDataSecurityType
}

_SECURITY_ALIASES: Dict[str, str] = {
    "EXTRA__FUTURE": AmazingDataSecurityType.FUTURE.value,
    "EXTRA__STOCK_A": AmazingDataSecurityType.STOCK_A.value,
    "STOCK_A_SHSZ": AmazingDataSecurityType.STOCK_A_SH_SZ.value,
    "STOCK_A_SH_SZ": AmazingDataSecurityType.STOCK_A_SH_SZ.value,
    "A_SH_SZ": AmazingDataSecurityType.STOCK_A_SH_SZ.value,
}

_KNOWN_PERIOD_VALUES: Dict[str, AmazingDataPeriod] = {
    item.value: item for item in AmazingDataPeriod
}


def normalize_security_type(value: object | None, *, allow_empty: bool = True) -> str | None:
    """将 security_type 归一化为 AmazingData 枚举值。"""

    if value is None:
        return None if allow_empty else ""
    text = str(value).strip()
    if not text:
        if allow_empty:
            return None
        raise DataProviderError("AmazingData security_type 不能为空字符串")

    normalized = text.upper().replace("-", "_").replace(" ", "")
    alias = _SECURITY_ALIASES.get(normalized)
    if alias:
        return alias

    lowered = normalized.lower()
    if lowered in _SECURITY_VALUE_LOOKUP:
        return _SECURITY_VALUE_LOOKUP[lowered]
    if lowered in _SECURITY_NAME_LOOKUP:
        return _SECURITY_NAME_LOOKUP[lowered]
    if text in _SECURITY_VALUE_LOOKUP.values():
        return text

    raise DataProviderError(f"AmazingData 不支持 security_type={value!r}")


def normalize_period(value: object | None) -> str | None:
    """统一 period 表示。"""

    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    converted = convert_period(text)
    if converted in _KNOWN_PERIOD_VALUES:
        return converted

    lowered = converted.lower()
    if lowered in _KNOWN_PERIOD_VALUES:
        return lowered

    raise DataProviderError(f"AmazingData 不支持周期 period={value!r}")


_SECURITY_DISPLAY_NAMES: Dict[str, str] = {
    AmazingDataSecurityType.STOCK_A.value: "沪深A股",
    AmazingDataSecurityType.STOCK_A_SH_SZ.value: "沪深A股(全量)",
    AmazingDataSecurityType.INDEX_A.value: "指数",
    AmazingDataSecurityType.INDEX_A_SH_SZ.value: "沪深指数",
    AmazingDataSecurityType.SH_INDEX.value: "上证指数",
    AmazingDataSecurityType.SZ_INDEX.value: "深证指数",
    AmazingDataSecurityType.BJ_INDEX.value: "北证指数",
    AmazingDataSecurityType.ETF.value: "ETF",
    AmazingDataSecurityType.SH_ETF.value: "上证ETF",
    AmazingDataSecurityType.SZ_ETF.value: "深证ETF",
    AmazingDataSecurityType.KZZ.value: "可转债",
    AmazingDataSecurityType.SH_KZZ.value: "上证可转债",
    AmazingDataSecurityType.SZ_KZZ.value: "深证可转债",
    AmazingDataSecurityType.HKT.value: "沪深港通",
    AmazingDataSecurityType.SH_HKT.value: "沪股通",
    AmazingDataSecurityType.SZ_HKT.value: "深股通",
    AmazingDataSecurityType.FUTURE.value: "期货",
    AmazingDataSecurityType.FUTURE_CFFEX.value: "中金所期货",
    AmazingDataSecurityType.FUTURE_SHFE.value: "上期所期货",
    AmazingDataSecurityType.FUTURE_DCE.value: "大商所期货",
    AmazingDataSecurityType.FUTURE_CZCE.value: "郑商所期货",
    AmazingDataSecurityType.FUTURE_INE.value: "能源中心期货",
    AmazingDataSecurityType.OPTION.value: "期权",
}

_PERIOD_DISPLAY_NAMES: Dict[str, str] = {
    AmazingDataPeriod.TICK.value: "逐笔",
    AmazingDataPeriod.SNAPSHOT.value: "快照",
    AmazingDataPeriod.SNAPSHOT_FUTURE.value: "期货快照",
    AmazingDataPeriod.SNAPSHOT_HKT.value: "港股通快照",
    AmazingDataPeriod.M1.value: "1分钟",
    AmazingDataPeriod.M3.value: "3分钟",
    AmazingDataPeriod.M5.value: "5分钟",
    AmazingDataPeriod.M10.value: "10分钟",
    AmazingDataPeriod.M15.value: "15分钟",
    AmazingDataPeriod.M30.value: "30分钟",
    AmazingDataPeriod.M60.value: "60分钟",
    AmazingDataPeriod.M120.value: "120分钟",
    AmazingDataPeriod.DAY.value: "日线",
    AmazingDataPeriod.WEEK.value: "周线",
    AmazingDataPeriod.MONTH.value: "月线",
    AmazingDataPeriod.QUARTER.value: "季线",
    AmazingDataPeriod.YEAR.value: "年线",
}


def _describe_security(security_type: str | None) -> str:
    if not security_type:
        return "<未指定>"
    return _SECURITY_DISPLAY_NAMES.get(security_type, security_type)


def _describe_period(period: str | None) -> str:
    if not period:
        return "<未指定>"
    return _PERIOD_DISPLAY_NAMES.get(period, period)


_EQUITY_TYPES: frozenset[str] = frozenset(
    (
        AmazingDataSecurityType.STOCK_A.value,
        AmazingDataSecurityType.STOCK_A_SH_SZ.value,
        AmazingDataSecurityType.INDEX_A.value,
        AmazingDataSecurityType.INDEX_A_SH_SZ.value,
        AmazingDataSecurityType.SH_INDEX.value,
        AmazingDataSecurityType.SZ_INDEX.value,
        AmazingDataSecurityType.BJ_INDEX.value,
        AmazingDataSecurityType.ETF.value,
        AmazingDataSecurityType.SH_ETF.value,
        AmazingDataSecurityType.SZ_ETF.value,
        AmazingDataSecurityType.KZZ.value,
        AmazingDataSecurityType.SH_KZZ.value,
        AmazingDataSecurityType.SZ_KZZ.value,
        AmazingDataSecurityType.OPTION.value,
    )
)
_HKT_TYPES: frozenset[str] = frozenset(
    (
        AmazingDataSecurityType.HKT.value,
        AmazingDataSecurityType.SH_HKT.value,
        AmazingDataSecurityType.SZ_HKT.value,
    )
)
_FUTURE_TYPES: frozenset[str] = frozenset(
    (
        AmazingDataSecurityType.FUTURE.value,
        AmazingDataSecurityType.FUTURE_CFFEX.value,
        AmazingDataSecurityType.FUTURE_SHFE.value,
        AmazingDataSecurityType.FUTURE_DCE.value,
        AmazingDataSecurityType.FUTURE_CZCE.value,
        AmazingDataSecurityType.FUTURE_INE.value,
    )
)

_DEFAULT_PERIODS: frozenset[str] = frozenset(
    {
        AmazingDataPeriod.TICK.value,
        AmazingDataPeriod.SNAPSHOT.value,
        AmazingDataPeriod.M1.value,
        AmazingDataPeriod.M3.value,
        AmazingDataPeriod.M5.value,
        AmazingDataPeriod.M10.value,
        AmazingDataPeriod.M15.value,
        AmazingDataPeriod.M30.value,
        AmazingDataPeriod.M60.value,
        AmazingDataPeriod.M120.value,
        AmazingDataPeriod.DAY.value,
        AmazingDataPeriod.WEEK.value,
        AmazingDataPeriod.MONTH.value,
        AmazingDataPeriod.QUARTER.value,
        AmazingDataPeriod.YEAR.value,
    }
)

_FUTURE_ALLOWED_PERIODS: frozenset[str] = frozenset(
    (_DEFAULT_PERIODS - {AmazingDataPeriod.SNAPSHOT.value}) | {AmazingDataPeriod.SNAPSHOT_FUTURE.value}
)
_HKT_ALLOWED_PERIODS: frozenset[str] = frozenset(
    (_DEFAULT_PERIODS - {AmazingDataPeriod.SNAPSHOT.value}) | {AmazingDataPeriod.SNAPSHOT_HKT.value}
)


def _resolve_allowed_periods(security_type: str | None) -> Iterable[str]:
    if not security_type:
        return _DEFAULT_PERIODS
    if security_type in _FUTURE_TYPES:
        return _FUTURE_ALLOWED_PERIODS
    if security_type in _HKT_TYPES:
        return _HKT_ALLOWED_PERIODS
    return _DEFAULT_PERIODS


def validate_security_period(
        security_type: object | None,
        period: object | None,
        *,
        context: str,
) -> tuple[str | None, str | None]:
    """
    校验 security_type 与 period 组合是否合法。

    若检测到需要的自动转换（例如 HKT + snapshot → snapshot_hkt），
    将返回转换后的值并写日志说明。
    """

    canonical_security = normalize_security_type(security_type)
    canonical_period = normalize_period(period)

    if canonical_security in _HKT_TYPES and canonical_period == AmazingDataPeriod.SNAPSHOT.value:
        canonical_period = AmazingDataPeriod.SNAPSHOT_HKT.value
        log_info("自动调整 period=snapshot -> snapshot_hkt 以匹配港股通标的", action="period_validation",
                 metadata={"context": context, "security": _describe_security(canonical_security)})
    if canonical_security in _FUTURE_TYPES and canonical_period == AmazingDataPeriod.SNAPSHOT.value:
        canonical_period = AmazingDataPeriod.SNAPSHOT_FUTURE.value
        log_info("自动调整 period=snapshot -> snapshot_future 以匹配期货标的", action="period_validation",
                 metadata={"context": context, "security": _describe_security(canonical_security)})

    allowed_periods = set(_resolve_allowed_periods(canonical_security))

    if canonical_period and canonical_period not in allowed_periods:
        raise DataProviderError(
            f"AmazingData {context} 收到不兼容的 security_type/period 组合："
            f"{_describe_security(canonical_security)} 与 {_describe_period(canonical_period)}"
        )

    if canonical_period == AmazingDataPeriod.SNAPSHOT_FUTURE.value and canonical_security not in _FUTURE_TYPES:
        raise DataProviderError(
            f"AmazingData {context} 仅允许期货品种使用 period=snapshot_future，当前 security_type="
            f"{_describe_security(canonical_security)}"
        )

    if canonical_period == AmazingDataPeriod.SNAPSHOT_HKT.value and canonical_security not in _HKT_TYPES:
        raise DataProviderError(
            f"AmazingData {context} 仅允许港股通品种使用 period=snapshot_hkt，当前 security_type="
            f"{_describe_security(canonical_security)}"
        )

    return canonical_security, canonical_period


__all__ = [
    "CacheParamMode",
    "CachePolicy",
    "sanitize_cache_params",
    "sanitize_cache_kwargs",
    "normalize_security_type",
    "normalize_period",
    "validate_security_period",
]
