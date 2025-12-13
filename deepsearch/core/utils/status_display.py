"""
Rich 终端状态显示组件

提供实时的终端状态显示，替代频繁刷屏的日志输出
"""

import asyncio
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional

from loguru import logger

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # 创建占位类型，避免类型注解导致NameError
    Console = None  # type: ignore
    Live = None  # type: ignore
    Panel = None  # type: ignore
    Table = None  # type: ignore
    Text = None  # type: ignore
    logger.warning("rich 库未安装，状态显示功能将被禁用")


@dataclass
class DataSourceMetrics:
    """单个数据源的指标"""

    name: str
    status: str = "offline"
    requests: int = 0
    success: int = 0
    errors: int = 0
    last_request_time: Optional[float] = None
    avg_latency_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def success_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return (self.success / self.requests) * 100

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100


@dataclass
class StatusMetrics:
    """全局状态指标"""

    start_time: float = field(default_factory=time.time)
    sources: Dict[str, DataSourceMetrics] = field(default_factory=dict)
    total_requests: int = 0
    active_source: str = ""
    last_update: Optional[float] = None

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def uptime_display(self) -> str:
        seconds = int(self.uptime_seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


class RichStatusDisplay:
    """
    Rich 终端状态显示器

    提供不刷屏的实时状态更新，包括：
    - 数据源状态（在线/离线）
    - 请求统计（速率、成功率）
    - 缓存命中率
    - 运行时长
    """

    _instance: Optional["RichStatusDisplay"] = None
    _lock = Lock()

    def __new__(cls) -> "RichStatusDisplay":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._enabled = RICH_AVAILABLE
        self._console = Console() if RICH_AVAILABLE else None
        self._live: Optional[Live] = None
        self._metrics = StatusMetrics()
        self._running = False
        self._update_interval = 1.0  # 每秒更新一次显示
        self._update_task: Optional[asyncio.Task] = None
        self._suppress_logs = False  # 是否抑制普通日志

    @classmethod
    def get_instance(cls) -> "RichStatusDisplay":
        """获取单例实例"""
        return cls()

    def enable(self, suppress_logs: bool = True) -> None:
        """启用状态显示"""
        if not self._enabled:
            return
        self._suppress_logs = suppress_logs

    def disable(self) -> None:
        """禁用状态显示"""
        self._suppress_logs = False

    @property
    def should_suppress_log(self) -> bool:
        """是否应该抑制当前日志（由外部检查）"""
        return self._suppress_logs and self._running

    def start(self) -> None:
        """启动状态显示"""
        if not self._enabled or self._running:
            return

        self._running = True
        self._metrics.start_time = time.time()
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=2,
            transient=False,
        )
        self._live.start()
        logger.info("Rich 状态显示已启动")

    def stop(self) -> None:
        """停止状态显示"""
        if not self._running:
            return

        self._running = False
        if self._live:
            self._live.stop()
            self._live = None

    def update_source(
            self,
            source: str,
            *,
            status: Optional[str] = None,
            request: bool = False,
            success: bool = False,
            error: bool = False,
            latency_ms: Optional[float] = None,
            cache_hit: Optional[bool] = None,
    ) -> None:
        """更新数据源指标"""
        if source not in self._metrics.sources:
            self._metrics.sources[source] = DataSourceMetrics(name=source)

        metrics = self._metrics.sources[source]

        if status is not None:
            metrics.status = status

        if request:
            metrics.requests += 1
            self._metrics.total_requests += 1
            metrics.last_request_time = time.time()

        if success:
            metrics.success += 1

        if error:
            metrics.errors += 1

        if latency_ms is not None:
            # 滑动平均
            if metrics.avg_latency_ms == 0:
                metrics.avg_latency_ms = latency_ms
            else:
                metrics.avg_latency_ms = (metrics.avg_latency_ms * 0.9) + (latency_ms * 0.1)

        if cache_hit is True:
            metrics.cache_hits += 1
        elif cache_hit is False:
            metrics.cache_misses += 1

        self._metrics.last_update = time.time()
        self._refresh()

    def set_active_source(self, source: str) -> None:
        """设置当前活跃数据源"""
        self._metrics.active_source = source
        self._refresh()

    def _refresh(self) -> None:
        """刷新显示"""
        if self._live and self._running:
            self._live.update(self._render())

    def _render(self) -> Any:
        """渲染状态面板"""
        if not RICH_AVAILABLE:
            return None  # type: ignore

        # 创建表格
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="cyan", width=12)
        table.add_column("Value", style="white")
        table.add_column("Key2", style="cyan", width=12)
        table.add_column("Value2", style="white")

        # 第一行：数据源和请求数
        active = self._metrics.active_source or "N/A"
        status_style = "green" if self._get_active_status() == "online" else "yellow"
        source_text = Text()
        source_text.append(active, style=status_style)

        table.add_row(
            "数据源",
            source_text,
            "请求总数",
            str(self._metrics.total_requests),
        )

        # 第二行：成功率和延迟
        active_metrics = self._metrics.sources.get(self._metrics.active_source)
        if active_metrics:
            success_rate = f"{active_metrics.success_rate:.1f}%"
            latency = f"{active_metrics.avg_latency_ms:.0f}ms"
            cache_rate = f"{active_metrics.cache_hit_rate:.1f}%"
        else:
            success_rate = "N/A"
            latency = "N/A"
            cache_rate = "N/A"

        table.add_row("成功率", success_rate, "平均延迟", latency)

        # 第三行：缓存和运行时间
        last_update = ""
        if self._metrics.last_update:
            last_update = datetime.fromtimestamp(self._metrics.last_update).strftime(
                "%H:%M:%S"
            )

        table.add_row(
            "缓存命中",
            cache_rate,
            "运行时间",
            self._metrics.uptime_display,
        )

        # 第四行：最后更新时间
        table.add_row("最后更新", last_update or "N/A", "", "")

        return Panel(
            table,
            title="[bold blue]DeepSearch 状态监控[/bold blue]",
            border_style="blue",
            padding=(0, 1),
        )

    def _get_active_status(self) -> str:
        """获取活跃数据源状态"""
        if not self._metrics.active_source:
            return "offline"
        metrics = self._metrics.sources.get(self._metrics.active_source)
        return metrics.status if metrics else "offline"

    @contextmanager
    def live_context(self):
        """上下文管理器，用于自动启动和停止"""
        try:
            self.start()
            yield self
        finally:
            self.stop()


# 全局实例
_status_display: Optional[RichStatusDisplay] = None


def get_status_display() -> RichStatusDisplay:
    """获取全局状态显示实例"""
    global _status_display
    if _status_display is None:
        _status_display = RichStatusDisplay.get_instance()
    return _status_display
