"""
内存管理器

提供:
1. 内存使用监控
2. 定时垃圾回收任务
3. 手动触发 GC
4. GC 历史记录持久化
"""

from __future__ import annotations

import asyncio
import gc
import os
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from core.infrastructure.memory.gc_persistence import GCPersistence


class MemoryManager:
    """内存管理器 - 单例"""

    _instance: Optional["MemoryManager"] = None
    _lock = threading.Lock()
    _initialized: bool

    def __new__(cls) -> "MemoryManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._gc_task: Optional[asyncio.Task[None]] = None
        self._gc_interval = 300  # 默认 5 分钟
        self._gc_enabled = True
        self._gc_log_enabled = True
        self._last_gc_time: Optional[datetime] = None
        self._gc_history: List[Dict[str, Any]] = []  # 内存中的历史记录（兼容）
        self._gc_persistence: Optional["GCPersistence"] = None  # GC 持久化服务

        # 初始化 GC 持久化服务
        try:
            from core.infrastructure.memory.gc_persistence import get_gc_persistence

            self._gc_persistence = get_gc_persistence()
            logger.debug("GC 持久化服务已初始化")
        except Exception as e:
            logger.warning(f"GC 持久化服务初始化失败: {e}")
            self._gc_persistence = None

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取当前进程内存统计"""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            threads = process.num_threads()

            try:
                open_files = len(process.open_files())  # type: ignore[attr-defined]
            except psutil.AccessDenied, psutil.NoSuchProcess:
                open_files = -1

            return {
                "process_id": os.getpid(),
                "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
                "threads": threads,
                "open_files": open_files,
                "gc_counts": list(gc.get_count()),
                "gc_thresholds": list(gc.get_threshold()),
                "python_objects": len(gc.get_objects()),
            }
        except ImportError:
            # psutil 不可用时的降级方案
            return {
                "process_id": os.getpid(),
                "rss_mb": 0,
                "vms_mb": 0,
                "threads": threading.active_count(),
                "open_files": -1,
                "gc_counts": list(gc.get_count()),
                "gc_thresholds": list(gc.get_threshold()),
                "python_objects": len(gc.get_objects()),
            }

    def get_all_python_processes(self) -> List[Dict[str, Any]]:
        """获取所有 DeepSearch 相关的 Python 进程的内存信息"""
        try:
            import psutil

            processes = []
            current_pid = os.getpid()

            for proc in psutil.process_iter(
                ["pid", "name", "memory_info", "num_threads", "cmdline"]
            ):
                try:
                    pinfo: Dict[str, Any] = proc.info  # type: ignore[attr-defined]
                    if "python" not in str(pinfo.get("name", "")).lower():
                        continue

                    # 只包含 DeepSearch 相关进程
                    cmdline = pinfo.get("cmdline") or []
                    cmdline_str = " ".join(cmdline).lower() if cmdline else ""

                    is_deepsearch = pinfo["pid"] == current_pid or "deepsearch" in cmdline_str

                    if not is_deepsearch:
                        continue

                    mem = pinfo.get("memory_info")
                    name = pinfo["name"]
                    if "webui" in cmdline_str:
                        name = "deepsearch-webui"
                    elif "worker" in cmdline_str:
                        name = "deepsearch-worker"
                    elif "deepsearch" in cmdline_str:
                        name = "deepsearch"

                    processes.append(
                        {
                            "pid": pinfo["pid"],
                            "name": name,
                            "rss_mb": round(mem.rss / 1024 / 1024, 2) if mem else 0,
                            "threads": pinfo.get("num_threads", 0),
                        }
                    )
                except psutil.NoSuchProcess, psutil.AccessDenied:
                    continue

            return sorted(processes, key=lambda x: x["rss_mb"], reverse=True)
        except ImportError:
            return [self.get_memory_stats()]

    def run_gc(
        self,
        full: bool = True,
        trigger_type: str = "manual",
    ) -> Dict[str, Any]:
        """
        手动执行垃圾回收

        Args:
            full: 是否执行完整 GC (收集所有代)，默认 True
            trigger_type: 触发类型 (manual/periodic/threshold/shutdown)
        """
        # 获取 GC 前内存
        before_stats = self.get_memory_stats()
        before_mb = before_stats["rss_mb"]

        start_time = time.time()

        if full:
            collected = [gc.collect(i) for i in range(3)]
        else:
            collected = [gc.collect(0), 0, 0]

        duration_ms = (time.time() - start_time) * 1000

        # 获取 GC 后内存
        after_stats = self.get_memory_stats()
        after_mb = after_stats["rss_mb"]

        result = {
            "collected": collected,
            "uncollectable": len(gc.garbage),
            "duration_ms": round(duration_ms, 2),
            "memory_before_mb": before_mb,
            "memory_after_mb": after_mb,
            "memory_freed_mb": round(before_mb - after_mb, 2),
            "timestamp": datetime.now().isoformat(),
        }

        # 记录历史（内存）
        self._gc_history.append(result)
        if len(self._gc_history) > 100:
            self._gc_history = self._gc_history[-100:]

        # 持久化到数据库
        if self._gc_persistence:
            try:
                self._gc_persistence.record(result, trigger_type=trigger_type)
            except Exception as e:
                logger.warning(f"GC 历史持久化失败: {e}")

        self._last_gc_time = datetime.now()

        if self._gc_log_enabled:
            logger.info(
                f"GC 完成: 回收 {sum(collected)} 对象, "
                f"释放 {result['memory_freed_mb']:.1f}MB, "
                f"耗时 {duration_ms:.1f}ms"
            )

        return result

    async def start_periodic_gc(self) -> None:
        """启动定时 GC 任务"""
        if self._gc_task and not self._gc_task.done():
            logger.warning("定时 GC 任务已在运行")
            return

        self._gc_task = asyncio.create_task(self._periodic_gc_loop())
        logger.info(f"定时 GC 已启动，间隔 {self._gc_interval} 秒")

    async def stop_periodic_gc(self) -> None:
        """停止定时 GC 任务"""
        if self._gc_task and not self._gc_task.done():
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass
            self._gc_task = None
            logger.info("定时 GC 已停止")

    async def _periodic_gc_loop(self) -> None:
        """定时 GC 循环"""
        while True:
            try:
                await asyncio.sleep(self._gc_interval)

                if not self._gc_enabled:
                    continue

                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, lambda: self.run_gc(full=True, trigger_type="periodic")
                )

            except asyncio.CancelledError:
                logger.debug("定时 GC 循环已取消")
                break
            except Exception as e:
                logger.error(f"定时 GC 执行错误: {e}")
                await asyncio.sleep(60)

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "gc_enabled": self._gc_enabled,
            "gc_interval_seconds": self._gc_interval,
            "gc_log_enabled": self._gc_log_enabled,
            "gc_task_running": self._gc_task is not None and not self._gc_task.done(),
            "last_gc_time": self._last_gc_time.isoformat() if self._last_gc_time else None,
        }

    def update_config(
        self,
        gc_enabled: Optional[bool] = None,
        gc_interval_seconds: Optional[int] = None,
        gc_log_enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """更新配置"""
        if gc_enabled is not None:
            self._gc_enabled = gc_enabled
        if gc_interval_seconds is not None:
            self._gc_interval = max(60, gc_interval_seconds)
        if gc_log_enabled is not None:
            self._gc_log_enabled = gc_log_enabled

        return self.get_config()

    def get_gc_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取 GC 历史记录

        优先从持久化存储读取，降级使用内存历史记录

        Args:
            limit: 返回记录数，默认 20
        """
        if self._gc_persistence:
            try:
                return self._gc_persistence.get_recent(limit=limit)
            except Exception as e:
                logger.warning(f"从持久化读取 GC 历史失败: {e}")

        return self._gc_history[-limit:]


# 全局实例
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取内存管理器实例"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
