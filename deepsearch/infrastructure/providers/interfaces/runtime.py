# encoding:utf-8
"""
运行时类型定义

该模块收敛数据提供者管理器、SDK 封装与实时消息回调的公共类型，压缩对 ``Any`` 的依赖，
为 mypy 收敛提供统一约束。
"""

from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    TypeAlias,
    TypedDict,
)

from typing_extensions import NotRequired

from deepsearch.messaging.types import MessageEnvelope
from deepsearch.utils.patterns.request_batcher import MultiKeyBatchReport

# ---------------------------------------------------------------------------
# 统计信息
# ---------------------------------------------------------------------------

ProviderUsageMap: TypeAlias = Dict[str, int]


class ClientStats(TypedDict):
    """单个客户端的统计信息。"""

    messages: int
    bytes: int


class ProviderStats(TypedDict):
    """数据提供者统计信息快照。"""

    total_messages: int
    total_bytes: int
    message_types: Dict[str, int]
    client_stats: Dict[str, ClientStats]
    errors: int
    start_time: Optional[float]


class ProviderRuntimeStats(TypedDict):
    """数据提供者运行时统计。"""

    requests: int
    successes: int
    failures: int
    cache_hits: int
    provider_usage: ProviderUsageMap
    batch_stats: MultiKeyBatchReport


class ProviderCallStats(TypedDict):
    """单个 SDK 调用统计。"""

    total_calls: int
    successful_calls: int
    failed_calls: int
    retries: int
    crashes_handled: int
    last_health_status: NotRequired[Mapping[str, Any] | None]


class ProxyRuntimeStats(TypedDict, total=False):
    """进程代理统计。"""

    requests_sent: int
    requests_completed: int
    requests_failed: int
    process_restarts: int
    last_crash_time: NotRequired[float]
    last_crash_reason: NotRequired[str]


class ProviderStatsReport(ProviderCallStats, total=False):
    """安全封装的统计报表。"""

    proxy_stats: Optional[ProxyRuntimeStats]
    is_connected: bool


class CacheStats(TypedDict):
    """缓存统计结构。"""

    size: int
    hits: int
    misses: int
    evictions: int
    hit_rate: str
    hot_keys: List[tuple[str, int]]


def create_empty_batch_stats() -> MultiKeyBatchReport:
    """创建空的批处理统计，用于初始化。"""

    return {
        "total_requests": 0,
        "total_batches": 0,
        "successful_batches": 0,
        "failed_batches": 0,
        "by_key": {},
    }


def create_provider_runtime_stats() -> ProviderRuntimeStats:
    """初始化默认运行时统计。"""

    return {
        "requests": 0,
        "successes": 0,
        "failures": 0,
        "cache_hits": 0,
        "provider_usage": {},
        "batch_stats": create_empty_batch_stats(),
    }


# ---------------------------------------------------------------------------
# 状态跟踪
# ---------------------------------------------------------------------------


class ProviderHealthEntry(TypedDict, total=False):
    """单个数据源的健康状态。"""

    status: str
    mode: NotRequired[str]
    priority: NotRequired[int]
    note: NotRequired[str]
    error: NotRequired[str]
    test: NotRequired[str]
    last_transition: NotRequired[float]


class CircuitBreakerState(TypedDict, total=False):
    """熔断器状态。"""

    failures: int
    last_failure: Optional[float]
    is_open: bool
    next_attempt: Optional[float]


class ProviderManagerStatus(TypedDict):
    """数据提供者管理器整体状态。"""

    initialized: bool
    providers: List[str]
    health: Dict[str, ProviderHealthEntry]
    stats: ProviderRuntimeStats
    cache_stats: CacheStats


# ---------------------------------------------------------------------------
# 实时消息
# ---------------------------------------------------------------------------

ProviderMessageEnvelope: TypeAlias = MessageEnvelope
RealtimeCallback = Callable[[ProviderMessageEnvelope], Awaitable[None] | None]


# ---------------------------------------------------------------------------
# SDK 协议
# ---------------------------------------------------------------------------


class ProviderSDKProtocol(Protocol):
    """安全封装依赖的进程代理最小协议。"""

    is_running: bool

    def start(self) -> bool: ...

    def execute(self, method: str, *args: Any, **kwargs: Any) -> Any: ...

    def health_check(self) -> Any: ...

    def get_stats(self) -> Mapping[str, Any]: ...
