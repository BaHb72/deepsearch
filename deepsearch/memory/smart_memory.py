"""
智能内存管理模块

提供自动内存监控、清理和优化
"""
from __future__ import annotations

import ctypes
import gc
import os
import sys
import threading
import time
import weakref
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional, TypedDict, cast

import psutil

# resource 模块只在类 Unix 系统可用
try:
    import resource as _resource_module
except ImportError:
    HAS_RESOURCE = False  # Windows 不支持 resource 模块
else:
    HAS_RESOURCE = True

from loguru import logger

IS_WINDOWS = sys.platform.startswith("win")


class MemoryMeasurement(TypedDict):
    timestamp: datetime
    usage: int
    allocated: int
    freed: int


class MemorySummary(TypedDict):
    current: int
    peak: int
    average: float
    total_allocated: int
    total_freed: int
    net_allocated: int


class GCRecord(TypedDict):
    timestamp: datetime
    collected: int
    stats: list[dict[str, int]]


class CleanupStats(TypedDict):
    gc_collected: int
    objects_cleared: int
    cache_cleared: int
    memory_freed: int


class LargeObjectInfo(TypedDict):
    name: str
    size: int
    size_mb: float
    type: str


class MemoryTrend(TypedDict, total=False):
    slope: float
    growing: bool
    time_to_limit_minutes: float


class MemoryRecommendation(TypedDict):
    level: str
    message: str
    action: str


class MemoryAnalysis(TypedDict):
    timestamp: str
    current_usage: dict[str, float]
    trends: MemoryTrend
    recommendations: list[MemoryRecommendation]



class _UnixResourceLimiter:
    """使用 resource 模块在类 Unix 系统上设置内存限制。"""

    def __init__(self, limit_bytes: int):
        import resource as _resource

        self._resource: Any = _resource
        self.limit_bytes = max(0, limit_bytes)
        self._original_limits: Optional[tuple[int, int]] = None

    def apply(self) -> None:
        if self.limit_bytes <= 0:
            return

        self._original_limits = self._resource.getrlimit(self._resource.RLIMIT_AS)
        soft, hard = self._original_limits
        new_soft = self.limit_bytes
        if hard != self._resource.RLIM_INFINITY:
            new_soft = min(new_soft, hard)

        self._resource.setrlimit(self._resource.RLIMIT_AS, (new_soft, hard))

    def restore(self) -> None:
        if not self._original_limits:
            return

        self._resource.setrlimit(self._resource.RLIMIT_AS, self._original_limits)
        self._original_limits = None


class _WindowsWorkingSetLimiter:
    """使用 Windows API 设置进程工作集限制。"""

    QUOTA_LIMITS_HARDWS_MIN_DISABLE = 0x00000002
    QUOTA_LIMITS_HARDWS_MAX_ENABLE = 0x00000004
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100

    def __init__(self, limit_bytes: int):
        from ctypes import wintypes

        self.limit_bytes = max(0, limit_bytes)
        self._ctypes: Any = ctypes
        self._wintypes = wintypes
        kernel32 = ctypes.windll.kernel32
        self._kernel32: Any = kernel32
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.restype = wintypes.BOOL

        extended_set = getattr(kernel32, "SetProcessWorkingSetSizeEx", None)
        extended_get = getattr(kernel32, "GetProcessWorkingSetSizeEx", None)

        self._set_ws: Callable[..., bool]
        self._get_ws: Callable[..., bool]

        if callable(extended_set) and callable(extended_get):
            extended_set.restype = wintypes.BOOL
            extended_get.restype = wintypes.BOOL
            self._set_ws = cast(Callable[..., bool], extended_set)
            self._get_ws = cast(Callable[..., bool], extended_get)
            self._use_extended = True
        else:
            fallback_set = getattr(kernel32, "SetProcessWorkingSetSize", None)
            fallback_get = getattr(kernel32, "GetProcessWorkingSetSize", None)
            if not callable(fallback_set) or not callable(fallback_get):
                raise RuntimeError("SetProcessWorkingSetSize API 不可用")
            fallback_set.restype = wintypes.BOOL
            fallback_get.restype = wintypes.BOOL
            self._set_ws = cast(Callable[..., bool], fallback_set)
            self._get_ws = cast(Callable[..., bool], fallback_get)
            self._use_extended = False

        access = self.PROCESS_QUERY_INFORMATION | self.PROCESS_SET_QUOTA
        handle = self._kernel32.OpenProcess(access, False, os.getpid())
        if handle:
            self._handle = handle
            self._owns_handle = True
        else:
            self._handle = self._kernel32.GetCurrentProcess()
            self._owns_handle = False

        self._original_state: Optional[tuple[int, int, Optional[int]]] = None
        self._active = False

    def apply(self) -> None:
        if self.limit_bytes <= 0:
            return

        try:
            original_min = self._ctypes.c_size_t()
            original_max = self._ctypes.c_size_t()
            if self._use_extended:
                original_flags = self._wintypes.DWORD()
                if not self._get_ws(
                    self._handle,
                    self._ctypes.byref(original_min),
                    self._ctypes.byref(original_max),
                    self._ctypes.byref(original_flags),
                ):
                    raise self._ctypes.WinError()
                flags_value: Optional[int] = original_flags.value
            else:
                if not self._get_ws(
                    self._handle,
                    self._ctypes.byref(original_min),
                    self._ctypes.byref(original_max),
                ):
                    raise self._ctypes.WinError()
                flags_value = None

            self._original_state = (
                original_min.value,
                original_max.value,
                flags_value,
            )

            limit = max(self.limit_bytes, self._page_size())
            min_size = min(self._original_state[0], limit)
            flags = self.QUOTA_LIMITS_HARDWS_MIN_DISABLE | self.QUOTA_LIMITS_HARDWS_MAX_ENABLE

            if self._use_extended:
                if not self._set_ws(
                    self._handle,
                    self._ctypes.c_size_t(min_size),
                    self._ctypes.c_size_t(limit),
                    self._wintypes.DWORD(flags),
                ):
                    raise self._ctypes.WinError()
            else:
                if not self._set_ws(
                    self._handle,
                    self._ctypes.c_size_t(min_size),
                    self._ctypes.c_size_t(limit),
                ):
                    raise self._ctypes.WinError()

            self._active = True
            self.limit_bytes = limit
        except Exception:
            self._release_handle()
            raise

    def restore(self) -> None:
        if not self._active or not self._original_state:
            self._release_handle()
            return

        min_size, max_size, flags = self._original_state
        if self._use_extended:
            if flags is None:
                flags = 0
            self._set_ws(
                self._handle,
                self._ctypes.c_size_t(min_size),
                self._ctypes.c_size_t(max_size),
                self._wintypes.DWORD(flags),
            )
        else:
            self._set_ws(
                self._handle,
                self._ctypes.c_size_t(min_size),
                self._ctypes.c_size_t(max_size),
            )

        self._active = False
        self._original_state = None
        self._release_handle()

    def _page_size(self) -> int:
        wintypes = self._wintypes

        class SYSTEM_INFO(ctypes.Structure):
            _fields_ = [
                ("wProcessorArchitecture", wintypes.WORD),
                ("wReserved", wintypes.WORD),
                ("dwPageSize", wintypes.DWORD),
                ("lpMinimumApplicationAddress", ctypes.c_void_p),
                ("lpMaximumApplicationAddress", ctypes.c_void_p),
                ("dwActiveProcessorMask", ctypes.c_void_p),
                ("dwNumberOfProcessors", wintypes.DWORD),
                ("dwProcessorType", wintypes.DWORD),
                ("dwAllocationGranularity", wintypes.DWORD),
                ("wProcessorLevel", wintypes.WORD),
                ("wProcessorRevision", wintypes.WORD),
            ]

        sys_info = SYSTEM_INFO()
        self._kernel32.GetSystemInfo(ctypes.byref(sys_info))
        return sys_info.dwPageSize or 4096

    def _release_handle(self) -> None:
        if getattr(self, "_owns_handle", False) and getattr(self, "_handle", None):
            self._kernel32.CloseHandle(self._handle)
        self._handle = None
        self._owns_handle = False


class MemoryStats:
    """内存统计信息"""

    def __init__(self) -> None:
        self.measurements: deque[MemoryMeasurement] = deque(maxlen=1000)
        self.peak_usage: int = 0
        self.total_allocated: int = 0
        self.total_freed: int = 0

    def record(self, usage: int, allocated: int = 0, freed: int = 0) -> None:
        """记录内存使用"""
        entry: MemoryMeasurement = {
            "timestamp": datetime.now(),
            "usage": usage,
            "allocated": allocated,
            "freed": freed,
        }
        self.measurements.append(entry)

        if usage > self.peak_usage:
            self.peak_usage = usage

        self.total_allocated += allocated
        self.total_freed += freed

    def get_summary(self) -> MemorySummary:
        """获取统计摘要"""
        recent = list(self.measurements)[-100:] if self.measurements else []
        usages = [m["usage"] for m in recent]
        average = sum(usages) / len(usages) if usages else 0.0

        summary: MemorySummary = {
            "current": usages[-1] if usages else 0,
            "peak": self.peak_usage,
            "average": average,
            "total_allocated": self.total_allocated,
            "total_freed": self.total_freed,
            "net_allocated": self.total_allocated - self.total_freed,
        }
        return summary


class SmartMemoryManager:
    """智能内存管理器"""

    _instance: ClassVar[Optional["SmartMemoryManager"]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            # 内存限制设置
            total_memory = psutil.virtual_memory().total
            self.memory_limit = int(total_memory * 0.8)  # 使用80%内存
            self.warning_threshold = int(self.memory_limit * 0.9)  # 90%时告警
            self.gc_threshold = 100 * 1024 * 1024  # 100MB触发GC

            # 对象追踪
            self.large_objects: weakref.WeakValueDictionary[str, Any] = (
                weakref.WeakValueDictionary()
            )
            self.object_sizes: dict[str, int] = {}
            self.cache_objects: weakref.WeakSet[Any] = weakref.WeakSet()

            # 统计信息
            self.stats = MemoryStats()
            self.gc_stats: deque[GCRecord] = deque(maxlen=100)

            # 监控设置
            self.monitoring_enabled: bool = True
            self.monitor_thread: Optional[threading.Thread] = None
            self.monitor_interval: int = 10  # 秒

            # 自动清理设置
            try:
                from deepsearch.config import settings

                self.auto_cleanup: bool = settings.app.env == "production"
            except ImportError:
                self.auto_cleanup = False
            self.last_cleanup: datetime = datetime.now()
            self.cleanup_interval: int = 300  # 5分钟

            self._lock = threading.Lock()
            self._initialized = True

            # 启动监控
            self.start_monitoring()

    def start_monitoring(self) -> None:
        """启动内存监控"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return

        def monitor() -> None:
            while self.monitoring_enabled:
                try:
                    self._monitor_memory()
                    time.sleep(self.monitor_interval)
                except Exception as exc:  # pragma: no cover - 防御性日志
                    logger.error(f"内存监控错误: {exc}")

        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        logger.debug("内存监控已启动")

    def stop_monitoring(self) -> None:
        """停止内存监控"""
        self.monitoring_enabled = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.debug("内存监控已停止")

    def _monitor_memory(self):
        """监控内存使用"""
        process = psutil.Process()
        memory_usage = process.memory_info().rss

        # 记录统计
        self.stats.record(memory_usage)

        # 检查内存使用
        if memory_usage > self.memory_limit:
            logger.error(
                f"内存使用超限: {memory_usage / 1024 / 1024:.2f}MB / {self.memory_limit / 1024 / 1024:.2f}MB"
            )
            if self.auto_cleanup:
                self.cleanup()

        elif memory_usage > self.warning_threshold:
            logger.warning(
                f"内存使用接近限制: {memory_usage / 1024 / 1024:.2f}MB / {self.memory_limit / 1024 / 1024:.2f}MB"
            )

        # 定期清理
        if self.auto_cleanup:
            now = datetime.now()
            if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
                self.cleanup()
                self.last_cleanup = now

    def register_large_object(self, obj: Any, name: str) -> bool:
        """注册大对象"""
        try:
            size = sys.getsizeof(obj)

            # 只注册大于1MB的对象
            if size > 1024 * 1024:
                with self._lock:
                    self.large_objects[name] = obj
                    self.object_sizes[name] = size

                logger.debug(f"注册大对象: {name} ({size / 1024 / 1024:.2f}MB)")
                return True

        except Exception as e:
            logger.debug(f"注册对象失败: {e}")

        return False

    def unregister_object(self, name: str) -> None:
        """注销对象"""
        with self._lock:
            if name in self.large_objects:
                del self.large_objects[name]

            if name in self.object_sizes:
                size = self.object_sizes.pop(name)
                logger.debug(f"注销对象: {name} ({size / 1024 / 1024:.2f}MB)")

    def add_cache_object(self, obj: Any) -> None:
        """添加缓存对象（可被清理）"""
        self.cache_objects.add(obj)

    def cleanup(self, force: bool = False) -> CleanupStats:
        """清理内存"""
        logger.info("开始内存清理...")

        cleanup_stats: CleanupStats = {
            "gc_collected": 0,
            "objects_cleared": 0,
            "cache_cleared": 0,
            "memory_freed": 0,
        }

        initial_memory = psutil.Process().memory_info().rss

        # 1. 强制垃圾回收
        gc.get_stats()
        collected = gc.collect()
        cleanup_stats["gc_collected"] = collected

        # 记录GC统计
        gc_stats_after = cast(list[dict[str, int]], gc.get_stats())
        record: GCRecord = {
            "timestamp": datetime.now(),
            "collected": collected,
            "stats": gc_stats_after,
        }
        self.gc_stats.append(record)

        # 2. 清理大对象（如果强制清理）
        if force:
            with self._lock:
                cleared = 0
                for name in list(self.large_objects.keys()):
                    if name in self.large_objects:
                        del self.large_objects[name]
                        cleared += 1

                cleanup_stats["objects_cleared"] = cleared

        # 3. 清理缓存对象
        cache_cleared = len(self.cache_objects)
        self.cache_objects.clear()
        cleanup_stats["cache_cleared"] = cache_cleared

        # 4. 清理模块缓存
        if force:
            self._clear_module_caches()

        # 计算释放的内存
        gc.collect()  # 再次回收
        final_memory = psutil.Process().memory_info().rss
        memory_freed = initial_memory - final_memory
        cleanup_stats["memory_freed"] = memory_freed

        # 记录统计
        self.stats.record(final_memory, freed=max(0, memory_freed))

        logger.info(
            f"内存清理完成: 回收对象={collected}, "
            f"清理大对象={cleanup_stats['objects_cleared']}, "
            f"清理缓存={cache_cleared}, "
            f"释放内存={memory_freed / 1024 / 1024:.2f}MB"
        )

        return cleanup_stats

    def _clear_module_caches(self):
        """清理模块级缓存"""
        try:
            # 清理functools缓存
            import functools

            functools._lru_cache_clear_all()
        except Exception:
            pass

        try:
            # 清理re模块缓存
            import re

            re.purge()
        except Exception:
            pass

    @contextmanager
    def memory_limit_context(self, limit_mb: int) -> Iterator[None]:
        """内存限制上下文"""
        limit_bytes = int(limit_mb * 1024 * 1024)
        old_limit = self.memory_limit
        old_warning = self.warning_threshold
        limiter: _WindowsWorkingSetLimiter | _UnixResourceLimiter | None = None

        if limit_bytes > 0:
            self.memory_limit = limit_bytes
            self.warning_threshold = int(limit_bytes * 0.9)

            if IS_WINDOWS:
                try:
                    limiter = _WindowsWorkingSetLimiter(limit_bytes)
                    limiter.apply()
                except Exception as exc:
                    limiter = None
                    logger.warning(
                        "Windows 内存限制设置失败，启用软限制: {}",
                        exc,
                    )
            elif HAS_RESOURCE:
                try:
                    limiter = _UnixResourceLimiter(limit_bytes)
                    limiter.apply()
                except Exception as exc:
                    limiter = None
                    logger.warning(
                        "resource 内存限制设置失败，启用软限制: {}",
                        exc,
                    )

        try:
            yield
        finally:
            self.memory_limit = old_limit
            self.warning_threshold = old_warning
            if limiter is not None:
                try:
                    limiter.restore()
                except Exception as exc:
                    logger.warning("恢复内存限制失败: {}", exc)

    def get_memory_info(self) -> dict[str, Any]:
        """获取内存信息"""
        process = psutil.Process()
        virtual_memory = psutil.virtual_memory()

        return {
            "system": {
                "total": virtual_memory.total,
                "available": virtual_memory.available,
                "percent": virtual_memory.percent,
                "used": virtual_memory.used,
                "free": virtual_memory.free,
            },
            "process": {
                "rss": process.memory_info().rss,
                "vms": process.memory_info().vms,
                "percent": process.memory_percent(),
                "num_threads": process.num_threads(),
            },
            "limits": {
                "configured_limit": self.memory_limit,
                "warning_threshold": self.warning_threshold,
                "gc_threshold": self.gc_threshold,
            },
            "objects": {
                "large_objects": len(self.large_objects),
                "cache_objects": len(self.cache_objects),
                "total_size": sum(self.object_sizes.values()),
            },
            "stats": self.stats.get_summary(),
        }

    def get_large_objects(self, top_n: int = 10) -> list[LargeObjectInfo]:
        """获取最大的对象"""
        objects: list[LargeObjectInfo] = []

        with self._lock:
            for name, size in self.object_sizes.items():
                if name in self.large_objects:
                    obj_type = type(self.large_objects[name]).__name__
                    info: LargeObjectInfo = {
                        "name": name,
                        "size": size,
                        "size_mb": size / 1024 / 1024,
                        "type": obj_type,
                    }
                    objects.append(info)

        # 按大小排序
        objects.sort(key=lambda x: x["size"], reverse=True)

        return objects[:top_n]

    def analyze_memory_usage(self) -> MemoryAnalysis:
        """分析内存使用"""
        analysis: MemoryAnalysis = {
            "timestamp": datetime.now().isoformat(),
            "current_usage": {},
            "trends": {},
            "recommendations": [],
        }

        # 当前使用情况
        memory_info = self.get_memory_info()
        analysis["current_usage"] = {
            "process_mb": memory_info["process"]["rss"] / 1024 / 1024,
            "system_percent": memory_info["system"]["percent"],
            "large_objects_mb": memory_info["objects"]["total_size"] / 1024 / 1024,
        }

        # 趋势分析
        trends: MemoryTrend = {}
        if self.stats.measurements:
            recent = list(self.stats.measurements)[-100:]
            usages = [m["usage"] for m in recent]

            # 计算趋势
            if len(usages) > 10:
                # 简单线性回归
                x = list(range(len(usages)))
                y = usages
                n = len(x)

                x_mean = sum(x) / n
                y_mean = sum(y) / n

                numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

                if denominator != 0:
                    slope = numerator / denominator
                    trends["slope"] = slope
                    trends["growing"] = slope > 0

                    # 预测
                    if slope > 0:
                        current = usages[-1]
                        time_to_limit = (self.memory_limit - current) / slope / 6  # 转换为分钟
                        trends["time_to_limit_minutes"] = max(0.0, time_to_limit)

        # 生成建议
        recommendations: list[MemoryRecommendation] = []
        if memory_info["process"]["percent"] > 50:
            recommendations.append(
                {
                    "level": "WARNING",
                    "message": "进程内存使用超过50%",
                    "action": "考虑优化内存使用或增加系统内存",
                }
            )

        if len(self.large_objects) > 50:
            recommendations.append(
                {
                    "level": "INFO",
                    "message": f"追踪了{len(self.large_objects)}个大对象",
                    "action": "检查是否有不必要的对象引用",
                }
            )

        if trends.get("growing"):
            recommendations.append(
                {
                    "level": "WARNING",
                    "message": "内存使用呈增长趋势",
                    "action": "可能存在内存泄漏，建议检查代码",
                }
            )

        analysis["trends"] = trends
        analysis["recommendations"] = recommendations
        return analysis

    def find_memory_leaks(self) -> list[dict[str, Any]]:
        """查找可能的内存泄漏"""
        leaks = []

        # 检查循环引用
        gc.collect()
        for obj in gc.garbage:
            leaks.append(
                {
                    "type": "circular_reference",
                    "object": str(obj)[:100],
                    "size": sys.getsizeof(obj) if hasattr(obj, "__sizeof__") else 0,
                }
            )

        # 检查持续增长的对象
        growing_objects = []
        for name, size in self.object_sizes.items():
            if name in self.large_objects:
                # 这里可以添加更复杂的增长检测逻辑
                growing_objects.append({"name": name, "size": size})

        if growing_objects:
            leaks.append({"type": "growing_objects", "objects": growing_objects})

        return leaks

    def optimize_memory(self) -> None:
        """优化内存使用"""
        logger.info("开始内存优化...")

        # 1. 调整GC阈值
        gc.set_threshold(700, 10, 10)

        # 2. 清理不必要的模块
        self._clear_module_caches()

        # 3. 压缩大对象（如果可能）
        compressed = 0
        for name in list(self.large_objects.keys()):
            if name in self.large_objects:
                self.large_objects[name]
                # 这里可以添加对象压缩逻辑
                compressed += 1

        # 4. 执行清理
        self.cleanup()

        logger.info(f"内存优化完成，处理了{compressed}个对象")

    def reset(self) -> None:
        """重置内存管理器"""
        with self._lock:
            self.large_objects.clear()
            self.object_sizes.clear()
            self.cache_objects.clear()
            self.stats = MemoryStats()
            self.gc_stats.clear()

        logger.info("内存管理器已重置")


# 创建全局实例
memory_manager = SmartMemoryManager()


# 便捷函数
def track_large_object(obj: Any, name: str) -> bool:
    """追踪大对象"""
    return memory_manager.register_large_object(obj, name)


def clear_cache() -> CleanupStats:
    """清理缓存"""
    return memory_manager.cleanup()


@contextmanager
def memory_limit(limit_mb: int) -> Iterator[None]:
    """内存限制上下文"""
    with memory_manager.memory_limit_context(limit_mb):
        yield
