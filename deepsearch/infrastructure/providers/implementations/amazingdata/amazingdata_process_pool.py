"""
AmazingData进程池管理器

为每个数据源维护独立的工作进程，实现完全隔离。

Author: DeepSearch Team
Version: 2.1.0
Date: 2025-10-11
"""

from __future__ import annotations

import multiprocessing as mp
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple, TypedDict, cast

from typing_extensions import NotRequired

from loguru import logger

from .amazingdata_process_proxy import AmazingDataProcessProxy

# ---------------------------------------------------------------------------
# 类型定义
# ---------------------------------------------------------------------------

WorkerProcess = mp.Process | subprocess.Popen[bytes] | None


class ProcessStatusEntry(TypedDict, total=False):
    """单个进程的运行状态快照。"""

    pid: int | None
    is_running: bool
    created_at: float
    last_used: float
    uptime_seconds: float
    restart_count: int
    requests_completed: int
    requests_failed: int
    auto_cleanup: bool
    reuse_count: NotRequired[int]
    is_test: NotRequired[bool]


class ProcessPoolStatus(TypedDict):
    """进程池总体状态。"""

    total_processes: int
    max_processes: int
    processes: Dict[str, ProcessStatusEntry]


@dataclass
class ProcessHandle:
    """保存进程代理及其元数据。"""

    datasource_id: str
    proxy: AmazingDataProcessProxy
    created_at: float
    last_used: float
    auto_cleanup: bool = False
    cleanup_delay: float = 60.0
    config: dict[str, Any] = field(default_factory=dict)
    restart_count: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    reuse_count: int = 0
    reuse_window: float | None = None
    is_test: bool = False

    def mark_used(self) -> None:
        """更新最后使用时间。"""
        self.last_used = time.time()

    def should_reuse(self, now: float) -> bool:
        """测试进程是否仍在复用窗口内。"""
        if not self.is_test:
            return True
        if self.reuse_window is None:
            return True
        return now - self.created_at <= self.reuse_window

    def uptime(self, now: float) -> float:
        """返回进程存活时长（秒）。"""
        return max(0.0, now - self.created_at)

    def clone_config(self) -> dict[str, Any]:
        """创建配置副本，防止引用共享。"""
        return dict(self.config)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_worker_process(proxy: AmazingDataProcessProxy) -> WorkerProcess:
    return cast(WorkerProcess, proxy.worker_process)


def _get_worker_pid(proxy: AmazingDataProcessProxy) -> int | None:
    process = _get_worker_process(proxy)
    if process is None:
        return None
    pid = getattr(process, "pid", None)
    try:
        return int(pid) if pid is not None else None
    except (TypeError, ValueError):
        return None


def _is_worker_alive(process: WorkerProcess) -> bool:
    if process is None:
        return False
    if isinstance(process, mp.Process):
        return process.is_alive()
    if isinstance(process, subprocess.Popen):
        return process.poll() is None
    return False


def _terminate_worker(process: WorkerProcess, *, force: bool) -> None:
    if process is None:
        return
    try:
        if force:
            if hasattr(process, "kill"):
                process.kill()
            else:
                process.terminate()
        else:
            process.terminate()
    except Exception as exc:
        logger.debug(f"[ProcessPool] 终止进程异常: {exc}")


def _safe_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# 进程池实现
# ---------------------------------------------------------------------------


class AmazingDataProcessPool:
    """
    数据源进程池管理器

    特性：
    - 每个数据源独立进程
    - 自动健康检查
    - 崩溃自动恢复
    - 资源使用监控
    """

    def __init__(self, max_processes: int = 10):
        """
        初始化进程池

        Args:
            max_processes: 最大进程数限制
        """
        self.max_processes = max_processes
        self._handles: Dict[str, ProcessHandle] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=3)

        # 启动健康检查
        self._start_health_monitor()

    # ------------------------------------------------------------------ #
    # 对外接口
    # ------------------------------------------------------------------ #

    def get_test_process(
        self,
        datasource_type: str = "amazingdata",
        reuse_window: float = 30.0,
    ) -> Tuple[AmazingDataProcessProxy, str]:
        """
        获取测试专用进程（支持时间窗口内复用）

        Args:
            datasource_type: 数据源类型
            reuse_window: 复用时间窗口（秒）

        Returns:
            (进程代理实例, 进程ID)
        """
        current_time = time.time()
        test_process_id = f"{datasource_type}_test"

        with self.lock:
            handle = self._handles.get(test_process_id)
            if handle:
                proxy = handle.proxy
                handle.reuse_window = reuse_window
                time_since_created = current_time - handle.created_at

                if proxy.is_running and handle.should_reuse(current_time):
                    handle.reuse_count += 1
                    handle.mark_used()
                    pid = _get_worker_pid(proxy)
                    pid_info = pid if pid is not None else "unknown"
                    logger.info(
                        f"[ProcessPool] Reusing test process {test_process_id} "
                        f"(age: {time_since_created:.1f}s, reuse_count: {handle.reuse_count}, pid={pid_info})"
                    )
                    return proxy, test_process_id

                if time_since_created > reuse_window:
                    logger.info(
                        f"[ProcessPool] Test process expired "
                        f"(age: {time_since_created:.1f}s > {reuse_window}s)"
                    )
                else:
                    logger.warning(f"[ProcessPool] Test process dead, creating new one")

        # 复用失败或不存在，先清理再创建
        self.stop(test_process_id, with_logout=True)

        logger.info(f"[ProcessPool] Creating new test process {test_process_id}")
        proxy = AmazingDataProcessProxy(restart_on_crash=False)

        if not proxy.start():
            raise RuntimeError("Failed to start test process")

        handle = ProcessHandle(
            datasource_id=test_process_id,
            proxy=proxy,
            created_at=current_time,
            last_used=current_time,
            auto_cleanup=False,
            cleanup_delay=0.0,
            config={},
            is_test=True,
            reuse_window=reuse_window,
        )

        with self.lock:
            self._handles[test_process_id] = handle

        pid = _get_worker_pid(proxy)
        pid_info = pid if pid is not None else "unknown"
        logger.info(f"[ProcessPool] Test process created (PID: {pid_info})")
        return proxy, test_process_id

    def get_or_create(
        self,
        datasource_id: str,
        auto_cleanup: bool = False,
        cleanup_delay: float = 60.0,
        config: Optional[Mapping[str, Any]] = None,
    ) -> AmazingDataProcessProxy:
        """
        获取或创建数据源专属进程

        Args:
            datasource_id: 数据源唯一标识
            auto_cleanup: 是否自动清理（测试场景）
            cleanup_delay: 自动清理延迟时间
            config: 进程配置参数

        Returns:
            进程代理实例

        Raises:
            RuntimeError: 进程创建失败
        """

        # 为避免锁重入，空闲清理在锁外执行
        self._cleanup_idle_processes()

        with self.lock:
            handle = self._handles.get(datasource_id)
            if handle:
                proxy = handle.proxy
                if proxy.is_running:
                    handle.mark_used()
                    logger.info(f"[ProcessPool] Reusing process for {datasource_id}")
                    return proxy

                logger.warning(f"[ProcessPool] Dead process detected for {datasource_id}")

            if len(self._handles) >= self.max_processes:
                logger.debug("[ProcessPool] Max processes reached, attempting idle cleanup")

        if handle:
            # 在锁外执行停机，避免重入
            self.stop(datasource_id)

        with self.lock:
            if len(self._handles) >= self.max_processes:
                # 再次检查，若仍超限直接拒绝
                raise RuntimeError(
                    f"Reached max process limit ({self.max_processes}), cannot create {datasource_id}"
                )

            logger.info(f"[ProcessPool] Creating new process for {datasource_id}")
            proxy = AmazingDataProcessProxy(restart_on_crash=not auto_cleanup)

            if not proxy.start():
                raise RuntimeError(f"Failed to start process for {datasource_id}")

            now = time.time()
            handle = ProcessHandle(
                datasource_id=datasource_id,
                proxy=proxy,
                created_at=now,
                last_used=now,
                auto_cleanup=auto_cleanup,
                cleanup_delay=cleanup_delay,
                config=dict(config or {}),
            )
            self._handles[datasource_id] = handle

        if auto_cleanup:
            self.executor.submit(self._schedule_cleanup, datasource_id, cleanup_delay)

        pid = _get_worker_pid(proxy)
        pid_info = pid if pid is not None else "unknown"
        logger.info(f"[ProcessPool] Process created for {datasource_id} (PID: {pid_info})")
        return proxy

    def stop(self, datasource_id: str, force: bool = False, with_logout: bool = True) -> bool:
        """
        停止指定数据源的进程

        Args:
            datasource_id: 数据源标识
            force: 是否强制停止
            with_logout: 是否先尝试执行logout（测试成功后应设置为True）

        Returns:
            是否成功停止
        """
        with self.lock:
            handle = self._handles.get(datasource_id)
            if not handle:
                return True

        proxy = handle.proxy
        logger.info(f"[ProcessPool] Stopping process for {datasource_id} (with_logout={with_logout})")

        success = bool(
            proxy.stop(
                timeout=5.0 if not force else 1.0,
                with_logout=with_logout,
            )
        )

        if not success and force:
            logger.warning(f"[ProcessPool] Force killing process for {datasource_id}")
            _terminate_worker(_get_worker_process(proxy), force=True)

        with self.lock:
            self._handles.pop(datasource_id, None)

        return success

    def stop_all(self, force: bool = False) -> None:
        """停止所有进程。"""
        logger.info("[ProcessPool] Stopping all processes")
        datasource_ids = self._snapshot_ids()
        for datasource_id in datasource_ids:
            self.stop(datasource_id, force=force)

    def restart(self, datasource_id: str) -> bool:
        """
        重启指定数据源的进程

        Args:
            datasource_id: 数据源标识

        Returns:
            是否成功重启
        """
        logger.info(f"[ProcessPool] Restarting process for {datasource_id}")

        with self.lock:
            handle = self._handles.get(datasource_id)
            stored_config = handle.clone_config() if handle else {}
            auto_cleanup = handle.auto_cleanup if handle else False

        self.stop(datasource_id)

        try:
            proxy = self.get_or_create(
                datasource_id,
                auto_cleanup=auto_cleanup,
                config=stored_config,
            )
            with self.lock:
                new_handle = self._handles.get(datasource_id)
                if new_handle:
                    new_handle.restart_count += 1
            return proxy is not None
        except Exception as exc:
            logger.error(f"[ProcessPool] Failed to restart process: {exc}")
            return False

    def get_status(self) -> ProcessPoolStatus:
        """
        获取进程池状态

        Returns:
            状态信息字典
        """
        with self.lock:
            handles_snapshot = list(self._handles.items())

        process_entries: Dict[str, ProcessStatusEntry] = {}
        now = time.time()

        for datasource_id, handle in handles_snapshot:
            proxy = handle.proxy
            stats = proxy.get_stats()
            pid = _get_worker_pid(proxy)

            entry: ProcessStatusEntry = {
                "pid": pid,
                "is_running": proxy.is_running and _is_worker_alive(_get_worker_process(proxy)),
                "created_at": handle.created_at,
                "last_used": handle.last_used,
                "uptime_seconds": handle.uptime(now),
                "restart_count": handle.restart_count,
                "requests_completed": _safe_int(stats, "requests_completed"),
                "requests_failed": _safe_int(stats, "requests_failed"),
                "auto_cleanup": handle.auto_cleanup,
            }

            if handle.is_test:
                entry["is_test"] = True
            if handle.reuse_count:
                entry["reuse_count"] = handle.reuse_count

            process_entries[datasource_id] = entry

        return {
            "total_processes": len(process_entries),
            "max_processes": self.max_processes,
            "processes": process_entries,
        }

    # ------------------------------------------------------------------ #
    # 内部工具
    # ------------------------------------------------------------------ #

    def _snapshot_ids(self) -> list[str]:
        with self.lock:
            return list(self._handles.keys())

    def _cleanup_idle_processes(self) -> None:
        """清理长时间未使用的进程。"""
        idle_threshold = 300  # 5分钟
        current_time = time.time()
        candidates: list[Tuple[str, float]] = []

        with self.lock:
            for datasource_id, handle in list(self._handles.items()):
                if handle.auto_cleanup:
                    continue
                elapsed = current_time - handle.last_used
                if elapsed > idle_threshold:
                    candidates.append((datasource_id, elapsed))

        for datasource_id, elapsed in candidates:
            logger.info(
                f"[ProcessPool] Cleaning idle process: {datasource_id} (idle {elapsed:.0f}s)"
            )
            self.stop(datasource_id)

    def _schedule_cleanup(self, datasource_id: str, delay: float) -> None:
        """调度自动清理任务"""
        time.sleep(delay)
        should_cleanup = False
        with self.lock:
            handle = self._handles.get(datasource_id)
            if handle and handle.auto_cleanup:
                should_cleanup = True

        if should_cleanup:
            logger.info(f"[ProcessPool] Auto-cleanup triggered for {datasource_id}")
            self.stop(datasource_id)

    def _start_health_monitor(self) -> None:
        """启动健康监控线程"""

        def monitor() -> None:
            while True:
                time.sleep(30)  # 每30秒检查一次
                self._check_process_health()

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _check_process_health(self) -> None:
        """检查所有进程健康状态"""
        unhealthy: list[str] = []
        with self.lock:
            for datasource_id, handle in list(self._handles.items()):
                proxy = handle.proxy
                try:
                    healthy = proxy.health_check()
                except Exception as exc:  # pragma: no cover - 容错
                    logger.warning(f"[ProcessPool] Health check raised for {datasource_id}: {exc}")
                    healthy = False

                if not healthy:
                    unhealthy.append(datasource_id)

        for datasource_id in unhealthy:
            logger.warning(f"[ProcessPool] Unhealthy process detected: {datasource_id}")
            self.restart(datasource_id)


# 全局进程池实例
_global_pool: Optional[AmazingDataProcessPool] = None


def get_global_pool() -> AmazingDataProcessPool:
    """获取全局进程池实例"""
    global _global_pool
    if _global_pool is None:
        _global_pool = AmazingDataProcessPool()
    return _global_pool


def shutdown_pool() -> None:
    """关闭进程池"""
    global _global_pool
    if _global_pool:
        _global_pool.stop_all(force=True)
        _global_pool = None
