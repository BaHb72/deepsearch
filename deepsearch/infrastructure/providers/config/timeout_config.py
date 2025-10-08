"""
超时配置管理

提供统一的超时配置与动态调整能力
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, MutableMapping, TypeVar

from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import DataSourceType


EnumT = TypeVar("EnumT", bound=Enum)


class RequestType(Enum):
    """请求类型枚举"""

    REALTIME = "realtime"  # 实时数据
    HISTORICAL = "historical"  # 历史数据
    STOCK_LIST = "stock_list"  # 股票列表
    STOCK_INFO = "stock_info"  # 股票信息
    HEALTH_CHECK = "health_check"  # 健康检查


@dataclass(frozen=True)
class TimeoutRequest:
    """描述超时配置所处的数据源与请求类型"""

    source: DataSourceType
    request_type: RequestType

    @classmethod
    def from_raw(
        cls,
        source: DataSourceType | str | None = None,
        request_type: RequestType | str | None = None,
    ) -> "TimeoutRequest":
        """根据原始输入生成结构化的上下文"""
        resolved_source = _coerce_enum(DataSourceType, source, DataSourceType.DEFAULT)
        resolved_request_type = _coerce_enum(RequestType, request_type, RequestType.REALTIME)
        return cls(source=resolved_source, request_type=resolved_request_type)

    def history_key(self) -> str:
        """生成历史记录使用的字典键"""
        return f"{self.source.value}_{self.request_type.value}"


@dataclass(frozen=True)
class TimeoutObservation:
    """单次请求的执行统计"""

    success: bool
    elapsed: float


@dataclass(frozen=True)
class TimeoutStatistics:
    """聚合后的统计数据"""

    success_rate: float
    avg_time: float
    total_requests: int

    def as_dict(self) -> Dict[str, float | int]:
        """转换为便于序列化的字典"""
        return {
            "success_rate": self.success_rate,
            "avg_time": self.avg_time,
            "total_requests": self.total_requests,
        }


@dataclass
class TimeoutSettings:
    """超时配置矩阵"""

    default_timeouts: MutableMapping[RequestType, float] = field(default_factory=dict)
    source_overrides: MutableMapping[
        DataSourceType, MutableMapping[RequestType, float]
    ] = field(default_factory=dict)

    @classmethod
    def build_default(cls) -> "TimeoutSettings":
        """构造默认的超时配置矩阵"""
        settings = cls()
        settings.default_timeouts.update(
            {
                RequestType.REALTIME: 5.0,
                RequestType.HISTORICAL: 30.0,
                RequestType.STOCK_LIST: 60.0,
                RequestType.STOCK_INFO: 10.0,
                RequestType.HEALTH_CHECK: 3.0,
            }
        )
        settings.source_overrides.update(
            {
                DataSourceType.AMAZINGDATA: {
                    RequestType.REALTIME: 3.0,
                    RequestType.HISTORICAL: 20.0,
                    RequestType.STOCK_LIST: 30.0,
                },
                DataSourceType.CLOUDFLARE: {
                    RequestType.REALTIME: 10.0,
                    RequestType.HISTORICAL: 40.0,
                    RequestType.STOCK_LIST: 45.0,
                },
                DataSourceType.AKSHARE: {
                    RequestType.REALTIME: 15.0,
                    RequestType.HISTORICAL: 60.0,
                    RequestType.STOCK_LIST: 120.0,
                },
                DataSourceType.QMT: {
                    RequestType.REALTIME: 2.0,
                    RequestType.HISTORICAL: 15.0,
                    RequestType.STOCK_LIST: 20.0,
                },
            }
        )
        return settings

    def clone(self) -> "TimeoutSettings":
        """创建当前配置的深拷贝"""
        copied = TimeoutSettings()
        copied.default_timeouts.update(self.default_timeouts)
        copied.source_overrides.update(
            {source: dict(overrides) for source, overrides in self.source_overrides.items()}
        )
        return copied

    def get_default(self, request_type: RequestType) -> float:
        """获取指定请求类型的默认超时时间"""
        return self.default_timeouts.get(request_type, 30.0)

    def get(self, request: TimeoutRequest) -> float:
        """获取某个上下文的超时时间"""
        overrides = self.source_overrides.get(request.source)
        if overrides and request.request_type in overrides:
            return overrides[request.request_type]
        return self.get_default(request.request_type)

    def set_override(self, request: TimeoutRequest, timeout: float) -> None:
        """为指定上下文写入新的超时时间"""
        overrides = self.source_overrides.setdefault(request.source, {})
        overrides[request.request_type] = timeout


class TimeoutManager:
    """超时管理器，负责读取与动态调整配置"""

    HISTORY_LIMIT = 100
    RECENT_WINDOW = 10
    MAX_GROWTH_RATIO = 1.5
    MIN_SHRINK_RATIO = 0.5

    def __init__(self, settings: TimeoutSettings | None = None):
        base_settings = settings.clone() if settings else TimeoutSettings.build_default()
        self._settings = base_settings
        self._adjustment_history: Dict[TimeoutRequest, List[TimeoutObservation]] = {}

    def get_timeout(
        self,
        request: TimeoutRequest,
        custom_timeout: float | None = None,
    ) -> float:
        """读取上下文对应的超时时间"""
        if custom_timeout is not None and custom_timeout > 0:
            return custom_timeout
        return self._settings.get(request)

    def adjust_timeout(self, request: TimeoutRequest, success: bool, actual_time: float) -> None:
        """根据执行结果动态调整超时时间"""
        if actual_time <= 0:
            return

        history = self._adjustment_history.setdefault(request, [])
        history.append(TimeoutObservation(success=success, elapsed=actual_time))

        if len(history) > self.HISTORY_LIMIT:
            del history[:-self.HISTORY_LIMIT]

        if len(history) < self.RECENT_WINDOW:
            return

        recent = history[-self.RECENT_WINDOW:]
        success_times = [record.elapsed for record in recent if record.success]
        if not success_times:
            return

        success_times.sort()
        p95_index = int(len(success_times) * 0.95)
        if p95_index >= len(success_times):
            p95_index = len(success_times) - 1
        p95_time = success_times[p95_index]

        proposed_timeout = p95_time * 1.5
        current_timeout = self._settings.get(request)

        upper_bound = current_timeout * self.MAX_GROWTH_RATIO
        lower_bound = current_timeout * self.MIN_SHRINK_RATIO
        bounded_timeout = max(lower_bound, min(proposed_timeout, upper_bound))

        self._settings.set_override(request, bounded_timeout)

        logger.debug(
            f"调整超时: {request.source.value}.{request.request_type.value} 从 {current_timeout:.1f}s 到 {bounded_timeout:.1f}s"
        )

    def get_statistics(self) -> Dict[TimeoutRequest, TimeoutStatistics]:
        """汇总各上下文的执行统计"""
        stats: Dict[TimeoutRequest, TimeoutStatistics] = {}
        for request, history in self._adjustment_history.items():
            if not history:
                continue

            total_count = len(history)
            success_count = sum(1 for record in history if record.success)
            avg_time = sum(record.elapsed for record in history) / total_count
            stats[request] = TimeoutStatistics(
                success_rate=success_count / total_count,
                avg_time=avg_time,
                total_requests=total_count,
            )

        return stats

    @property
    def settings(self) -> TimeoutSettings:
        """返回内部配置引用"""
        return self._settings


_timeout_manager = TimeoutManager()


def _coerce_enum(enum_cls: type[EnumT], value: EnumT | str | None, default: EnumT) -> EnumT:
    """将字符串或枚举值归一化为目标枚举"""
    if isinstance(value, enum_cls):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        for member in enum_cls:
            if member.value == normalized or member.name.lower() == normalized:
                return member

    return default


def get_timeout(
    source: TimeoutRequest | DataSourceType | str | None = None,
    request_type: RequestType | str | None = None,
    custom_timeout: float | None = None,
) -> float:
    """读取超时时间（支持直接传入结构化请求或原始字符串）"""
    if isinstance(source, TimeoutRequest):
        request = source
    else:
        request = TimeoutRequest.from_raw(source, request_type)

    return _timeout_manager.get_timeout(request, custom_timeout)


def adjust_timeout(
    source: TimeoutRequest | DataSourceType | str,
    request_type: RequestType | str | None,
    success: bool,
    actual_time: float,
) -> None:
    """根据执行结果调整超时配置"""
    if isinstance(source, TimeoutRequest):
        request = source
    else:
        request = TimeoutRequest.from_raw(source, request_type)

    _timeout_manager.adjust_timeout(request, success, actual_time)


def get_timeout_stats() -> Dict[str, TimeoutStatistics]:
    """返回当前的超时统计数据"""
    stats = _timeout_manager.get_statistics()
    return {request.history_key(): summary for request, summary in stats.items()}
