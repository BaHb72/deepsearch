"""
AmazingData进程池管理器

为每个数据源维护独立的工作进程，实现完全隔离。

Author: DeepSearch Team
Version: 2.0.0
Date: 2025-01-21
"""

import threading
import time
from typing import Dict, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

from .amazingdata_process_proxy import AmazingDataProcessProxy


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
        self.processes: Dict[str, AmazingDataProcessProxy] = {}
        self.process_info: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=3)

        # 启动健康检查
        self._start_health_monitor()

    def get_test_process(
        self,
        datasource_type: str = "amazingdata",
        reuse_window: float = 30.0
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
            # 检查是否存在可复用的测试进程
            if test_process_id in self.processes:
                proxy = self.processes[test_process_id]
                info = self.process_info[test_process_id]

                # 检查进程是否健康且在复用时间窗口内
                time_since_created = current_time - info.get("created_at", 0)

                if proxy.is_running and time_since_created <= reuse_window:
                    # 复用现有进程
                    info["last_used"] = current_time
                    info["reuse_count"] = info.get("reuse_count", 0) + 1
                    logger.info(f"[ProcessPool] Reusing test process {test_process_id} "
                              f"(age: {time_since_created:.1f}s, reuse_count: {info['reuse_count']})")
                    return proxy, test_process_id
                else:
                    # 进程过期或已死，清理并创建新的
                    if time_since_created > reuse_window:
                        logger.info(f"[ProcessPool] Test process expired "
                                  f"(age: {time_since_created:.1f}s > {reuse_window}s)")
                    else:
                        logger.warning(f"[ProcessPool] Test process dead, creating new one")

                    # 停止旧进程（带logout）
                    self.stop(test_process_id, with_logout=True)

            # 创建新的测试进程
            logger.info(f"[ProcessPool] Creating new test process {test_process_id}")
            proxy = AmazingDataProcessProxy(restart_on_crash=False)

            if not proxy.start():
                raise Exception(f"Failed to start test process")

            # 注册进程
            self.processes[test_process_id] = proxy
            self.process_info[test_process_id] = {
                "created_at": current_time,
                "last_used": current_time,
                "is_test": True,
                "reuse_count": 0,
                "reuse_window": reuse_window
            }

            logger.info(f"[ProcessPool] Test process created (PID: {proxy.worker_process.pid})")
            return proxy, test_process_id

    def get_or_create(
        self,
        datasource_id: str,
        auto_cleanup: bool = False,
        cleanup_delay: float = 60.0,
        config: Optional[Dict[str, Any]] = None
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
            Exception: 进程创建失败
        """
        with self.lock:
            # 检查进程数量限制
            if len(self.processes) >= self.max_processes:
                self._cleanup_idle_processes()

            # 检查现有进程
            if datasource_id in self.processes:
                proxy = self.processes[datasource_id]
                if proxy.is_running:
                    # 更新最后使用时间
                    self.process_info[datasource_id]["last_used"] = time.time()
                    logger.info(f"[ProcessPool] Reusing process for {datasource_id}")
                    return proxy
                else:
                    # 进程已死，清理并重建
                    logger.warning(f"[ProcessPool] Dead process detected for {datasource_id}")
                    self._remove_process(datasource_id)

            # 创建新进程
            logger.info(f"[ProcessPool] Creating new process for {datasource_id}")
            proxy = AmazingDataProcessProxy(
                restart_on_crash=not auto_cleanup
            )

            if not proxy.start():
                raise Exception(f"Failed to start process for {datasource_id}")

            # 注册进程
            self.processes[datasource_id] = proxy
            self.process_info[datasource_id] = {
                "created_at": time.time(),
                "last_used": time.time(),
                "auto_cleanup": auto_cleanup,
                "cleanup_delay": cleanup_delay,
                "config": config or {},
                "restart_count": 0,
                "total_requests": 0,
                "failed_requests": 0
            }

            # 设置自动清理
            if auto_cleanup:
                self.executor.submit(self._schedule_cleanup, datasource_id, cleanup_delay)

            logger.info(f"[ProcessPool] Process created for {datasource_id} (PID: {proxy.worker_process.pid})")
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
            if datasource_id not in self.processes:
                return True

            logger.info(f"[ProcessPool] Stopping process for {datasource_id} (with_logout={with_logout})")
            proxy = self.processes[datasource_id]

            # 尝试优雅停止（包含logout）
            success = proxy.stop(
                timeout=5.0 if not force else 1.0,
                with_logout=with_logout
            )

            if not success and force:
                # 强制终止
                logger.warning(f"[ProcessPool] Force killing process for {datasource_id}")
                if proxy.worker_process and proxy.worker_process.is_alive():
                    proxy.worker_process.kill()

            # 清理记录
            self._remove_process(datasource_id)
            return success

    def stop_all(self, force: bool = False):
        """停止所有进程"""
        logger.info("[ProcessPool] Stopping all processes")
        datasource_ids = list(self.processes.keys())

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

        # 保存配置
        config = None
        if datasource_id in self.process_info:
            config = self.process_info[datasource_id].get("config")

        # 停止旧进程
        self.stop(datasource_id)

        # 创建新进程
        try:
            proxy = self.get_or_create(datasource_id, auto_cleanup=False, config=config)
            if datasource_id in self.process_info:
                self.process_info[datasource_id]["restart_count"] += 1
            return proxy is not None
        except Exception as e:
            logger.error(f"[ProcessPool] Failed to restart process: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        获取进程池状态

        Returns:
            状态信息字典
        """
        with self.lock:
            status = {
                "total_processes": len(self.processes),
                "max_processes": self.max_processes,
                "processes": {}
            }

            for datasource_id, proxy in self.processes.items():
                info = self.process_info.get(datasource_id, {})
                proxy_stats = proxy.get_stats()

                status["processes"][datasource_id] = {
                    "pid": proxy.worker_process.pid if proxy.worker_process else None,
                    "is_running": proxy.is_running,
                    "created_at": info.get("created_at"),
                    "last_used": info.get("last_used"),
                    "uptime_seconds": time.time() - info.get("created_at", time.time()),
                    "restart_count": info.get("restart_count", 0),
                    "requests_completed": proxy_stats.get("requests_completed", 0),
                    "requests_failed": proxy_stats.get("requests_failed", 0),
                    "auto_cleanup": info.get("auto_cleanup", False)
                }

            return status

    def _remove_process(self, datasource_id: str):
        """内部方法：移除进程记录"""
        if datasource_id in self.processes:
            del self.processes[datasource_id]
        if datasource_id in self.process_info:
            del self.process_info[datasource_id]

    def _cleanup_idle_processes(self):
        """清理空闲进程"""
        current_time = time.time()
        idle_threshold = 300  # 5分钟

        for datasource_id, info in list(self.process_info.items()):
            if info.get("auto_cleanup"):
                continue

            last_used = info.get("last_used", current_time)
            if current_time - last_used > idle_threshold:
                logger.info(f"[ProcessPool] Cleaning idle process: {datasource_id}")
                self.stop(datasource_id)

    def _schedule_cleanup(self, datasource_id: str, delay: float):
        """调度自动清理任务"""
        time.sleep(delay)

        with self.lock:
            if datasource_id in self.process_info:
                info = self.process_info[datasource_id]
                if info.get("auto_cleanup"):
                    logger.info(f"[ProcessPool] Auto-cleanup triggered for {datasource_id}")
                    self.stop(datasource_id)

    def _start_health_monitor(self):
        """启动健康监控线程"""
        def monitor():
            while True:
                time.sleep(30)  # 每30秒检查一次
                self._check_process_health()

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _check_process_health(self):
        """检查所有进程健康状态"""
        with self.lock:
            for datasource_id, proxy in list(self.processes.items()):
                if not proxy.health_check():
                    logger.warning(f"[ProcessPool] Unhealthy process detected: {datasource_id}")
                    # 尝试重启
                    self.restart(datasource_id)


# 全局进程池实例
_global_pool = None


def get_global_pool() -> AmazingDataProcessPool:
    """获取全局进程池实例"""
    global _global_pool
    if _global_pool is None:
        _global_pool = AmazingDataProcessPool()
    return _global_pool


def shutdown_pool():
    """关闭进程池"""
    global _global_pool
    if _global_pool:
        _global_pool.stop_all(force=True)
        _global_pool = None