"""
Dask Scheduler 管理器

管理本地 Dask Scheduler 进程的生命周期。
支持检测外部 Scheduler（如 Docker 中运行的）并优先使用，
仅在外部不可用时启动本地 Scheduler。

架构设计:
- DaskSchedulerManager: 状态机管理 Scheduler 进程生命周期
- 健康检查: TCP 连接测试确保 Scheduler 可达
- 优雅关闭: 信号通知 + 超时强杀
"""

from __future__ import annotations

import asyncio
import signal
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from core.config.models.dask import SchedulerConfig


# ============================================================================
# 状态定义
# ============================================================================


class SchedulerState(Enum):
    """Dask Scheduler Manager 状态机状态"""

    IDLE = "idle"  # 初始状态，无 Scheduler
    CHECKING = "checking"  # 检查外部 Scheduler 可达性
    STARTING = "starting"  # 启动本地 Scheduler 进程
    READY = "ready"  # Scheduler 就绪（外部或本地）
    STOPPING = "stopping"  # 正在停止
    STOPPED = "stopped"  # 已停止
    FAILED = "failed"  # 失败状态


class SchedulerSource(Enum):
    """Scheduler 来源"""

    NONE = "none"  # 无 Scheduler
    EXTERNAL = "external"  # 外部 Scheduler（如 Docker）
    LOCAL = "local"  # 本地启动的 Scheduler


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class SchedulerProcessInfo:
    """Scheduler 进程元数据"""

    process: subprocess.Popen
    host: str
    port: int
    dashboard_port: int
    started_at: datetime
    pid: int


# ============================================================================
# 主管理器类
# ============================================================================


class DaskSchedulerManager:
    """
    Dask Scheduler 进程管理器 - 状态机实现

    职责:
    - 检测外部 Scheduler 是否可用
    - 启动/停止本地 Scheduler 进程
    - 提供健康检查
    - 提供线程安全的状态转换

    线程安全:
    - 使用 asyncio.Lock 保护状态修改
    - 状态转换是原子的
    """

    # 状态转换表
    VALID_TRANSITIONS: ClassVar[Dict[SchedulerState, List[SchedulerState]]] = {
        SchedulerState.IDLE: [SchedulerState.CHECKING, SchedulerState.FAILED],
        SchedulerState.CHECKING: [
            SchedulerState.READY,
            SchedulerState.STARTING,
            SchedulerState.FAILED,
        ],
        SchedulerState.STARTING: [SchedulerState.READY, SchedulerState.FAILED],
        SchedulerState.READY: [SchedulerState.STOPPING, SchedulerState.FAILED],
        SchedulerState.STOPPING: [SchedulerState.STOPPED, SchedulerState.FAILED],
        SchedulerState.STOPPED: [SchedulerState.IDLE],
        SchedulerState.FAILED: [SchedulerState.IDLE],
    }

    def __init__(self, config: Optional["SchedulerConfig"] = None) -> None:
        """
        初始化管理器

        Args:
            config: Scheduler 配置（依赖注入）
        """
        self._config = config
        self._logger = logger.bind(component="DaskSchedulerManager")

        # 状态机
        self._state = SchedulerState.IDLE
        self._state_lock = asyncio.Lock()
        self._error: Optional[str] = None

        # 进程管理
        self._process_info: Optional[SchedulerProcessInfo] = None
        self._process_lock = asyncio.Lock()

        # Scheduler 来源
        self._source = SchedulerSource.NONE

        # 元数据
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

        # 解析后的地址缓存
        self._host: str = "localhost"
        self._port: int = 8786
        self._dashboard_port: int = 8787

    # ========================================================================
    # 属性
    # ========================================================================

    @property
    def state(self) -> SchedulerState:
        """当前状态（只读）"""
        return self._state

    @property
    def is_ready(self) -> bool:
        """检查 Scheduler 是否就绪"""
        return self._state == SchedulerState.READY

    @property
    def source(self) -> SchedulerSource:
        """Scheduler 来源"""
        return self._source

    @property
    def address(self) -> str:
        """Scheduler 地址（tcp://host:port 格式）"""
        return f"tcp://{self._host}:{self._port}"

    @property
    def dashboard_address(self) -> str:
        """Dashboard 地址"""
        return f"http://{self._host}:{self._dashboard_port}"

    # ========================================================================
    # 状态转换
    # ========================================================================

    async def _transition_to(
        self,
        target: SchedulerState,
        error: Optional[str] = None,
    ) -> bool:
        """
        原子状态转换

        Args:
            target: 目标状态
            error: 错误信息（如果转换到 FAILED）

        Returns:
            True 如果转换成功，False 否则
        """
        async with self._state_lock:
            if target not in self.VALID_TRANSITIONS.get(self._state, []):
                self._logger.warning(f"无效的状态转换: {self._state.value} -> {target.value}")
                return False

            old_state = self._state
            self._state = target
            self._error = error

            self._logger.info(f"状态转换: {old_state.value} -> {target.value}")
            return True

    def _can_start(self) -> bool:
        """检查是否可以启动"""
        return self._state in (
            SchedulerState.IDLE,
            SchedulerState.STOPPED,
            SchedulerState.FAILED,
        )

    # ========================================================================
    # 生命周期方法
    # ========================================================================

    async def start(self) -> bool:
        """
        启动或连接 Scheduler

        流程:
        1. 如果 prefer_external=True，先检查外部 Scheduler
        2. 如果外部可用，直接使用
        3. 如果外部不可用且 auto_start=True，启动本地 Scheduler

        Returns:
            True 如果成功连接到 Scheduler
        """
        if not self._can_start():
            self._logger.warning(f"无法从状态 {self._state.value} 启动")
            return False

        # 加载配置
        if not self._load_config():
            return False

        try:
            # 阶段 1: 检查外部 Scheduler
            if not await self._transition_to(SchedulerState.CHECKING):
                return False

            if self._config and self._config.prefer_external:
                if self._check_scheduler_health():
                    self._source = SchedulerSource.EXTERNAL
                    self._logger.info(
                        f"使用外部 Scheduler | address={self.address} | source=external"
                    )
                    await self._transition_to(SchedulerState.READY)
                    self._started_at = datetime.now()
                    return True
                else:
                    self._logger.info(f"外部 Scheduler 不可用 ({self._host}:{self._port})")

            # 阶段 2: 启动本地 Scheduler
            if self._config and self._config.auto_start:
                if not await self._transition_to(SchedulerState.STARTING):
                    return False

                if not await self._start_local_scheduler():
                    await self._transition_to(SchedulerState.FAILED, "本地 Scheduler 启动失败")
                    return False

                self._source = SchedulerSource.LOCAL
                self._logger.info(f"本地 Scheduler 已启动 | address={self.address} | source=local")
                await self._transition_to(SchedulerState.READY)
                self._started_at = datetime.now()
                return True

            # 没有可用的 Scheduler
            await self._transition_to(
                SchedulerState.FAILED,
                "无可用 Scheduler（外部不可达且本地自启动未开启）",
            )
            return False

        except Exception as e:
            self._logger.error(f"启动失败: {e}")
            await self._transition_to(SchedulerState.FAILED, str(e))
            await self._cleanup()
            return False

    async def stop(self, timeout: float = 10.0) -> None:
        """
        停止本地 Scheduler（如果是我们启动的）

        Args:
            timeout: 等待优雅关闭的最大时间
        """
        if self._state == SchedulerState.STOPPED:
            return

        if self._state == SchedulerState.IDLE:
            return

        # 如果是外部 Scheduler，只需要更新状态
        if self._source == SchedulerSource.EXTERNAL:
            self._logger.info("外部 Scheduler，无需停止")
            self._source = SchedulerSource.NONE
            await self._transition_to(SchedulerState.STOPPED)
            self._stopped_at = datetime.now()
            return

        await self._transition_to(SchedulerState.STOPPING)

        try:
            await self._stop_local_scheduler(timeout)
            await self._transition_to(SchedulerState.STOPPED)
            self._stopped_at = datetime.now()
        except Exception as e:
            self._logger.error(f"停止失败: {e}")
            await self._transition_to(SchedulerState.FAILED, str(e))

    async def reset(self) -> None:
        """重置到 IDLE 状态（用于重试）"""
        if self._state in (SchedulerState.FAILED, SchedulerState.STOPPED):
            await self._cleanup()
            self._source = SchedulerSource.NONE
            await self._transition_to(SchedulerState.IDLE)

    def check_health(self) -> bool:
        """检查 Scheduler 健康状态"""
        return self._check_scheduler_health()

    # ========================================================================
    # 内部实现
    # ========================================================================

    def _load_config(self) -> bool:
        """
        加载配置

        Returns:
            True 如果配置有效
        """
        try:
            from core.config import get_config

            settings = get_config()

            # 获取 Dask 配置
            dask_config = getattr(settings, "dask", None)
            if dask_config is None:
                self._logger.warning("未找到 Dask 配置")
                return False

            # 获取 Scheduler 配置
            scheduler_config = getattr(dask_config, "scheduler", None)
            if scheduler_config is None:
                # 没有 scheduler 配置时，使用默认值并从 scheduler_address 解析地址
                from core.config.models.dask import SchedulerConfig

                self._config = SchedulerConfig()
                self._logger.info("使用默认 Scheduler 配置")
            else:
                self._config = scheduler_config

            # 检查是否启用
            if not self._config.enabled:  # type: ignore[union-attr]
                self._logger.info("Scheduler 管理已禁用")
                return False

            # 解析地址
            self._host = self._config.host  # type: ignore[union-attr]
            self._port = self._config.port  # type: ignore[union-attr]
            self._dashboard_port = self._config.dashboard_port  # type: ignore[union-attr]

            # 如果存在 scheduler_address，优先使用它（向后兼容）
            scheduler_address = getattr(dask_config, "scheduler_address", None)
            if scheduler_address:
                host, port = self._parse_scheduler_address(scheduler_address)
                self._host = host
                self._port = port

            self._logger.info(
                f"Scheduler 配置加载完成 | host={self._host} | port={self._port} | "
                f"auto_start={self._config.auto_start} | prefer_external={self._config.prefer_external}"  # type: ignore[union-attr]
            )
            return True

        except Exception as e:
            self._logger.error(f"加载配置失败: {e}")
            return False

    @staticmethod
    def _parse_scheduler_address(address: str) -> tuple[str, int]:
        """解析 Scheduler 地址"""
        if address.startswith("tcp://"):
            address = address[6:]
        elif address.startswith("://"):
            address = address[3:]

        if ":" in address:
            host, port_str = address.rsplit(":", 1)
            return host, int(port_str)
        return address, 8786

    def _check_scheduler_health(self, timeout: float = 3.0) -> bool:
        """检查 Scheduler 是否可达"""
        try:
            with socket.create_connection((self._host, self._port), timeout=timeout):
                return True
        except (OSError, socket.timeout):
            return False

    async def _start_local_scheduler(self) -> bool:
        """启动本地 Scheduler 进程"""
        if not self._config:
            return False

        async with self._process_lock:
            # 检查是否已有进程
            if self._process_info and self._process_info.process.poll() is None:
                self._logger.debug("Scheduler 进程已在运行")
                return True

            # 构建启动命令
            cmd = [
                sys.executable,
                "-m",
                "distributed.cli.dask_scheduler",
                "--host",
                self._host,
                "--port",
                str(self._port),
            ]

            # Dashboard 配置
            if self._config.dashboard_enabled:
                cmd.extend(["--dashboard-address", f":{self._dashboard_port}"])
            else:
                cmd.append("--no-dashboard")

            cmd_str = " ".join(cmd)
            self._logger.info(f"启动本地 Scheduler: {cmd_str}")

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=(
                        subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                    ),
                )

                self._process_info = SchedulerProcessInfo(
                    process=process,
                    host=self._host,
                    port=self._port,
                    dashboard_port=self._dashboard_port,
                    started_at=datetime.now(),
                    pid=process.pid,
                )

                self._logger.info(f"Scheduler 进程已启动 (PID={process.pid})")

                # 等待 Scheduler 就绪
                if not await self._wait_for_scheduler_ready():
                    self._logger.error("Scheduler 启动超时")
                    await self._cleanup()
                    return False

                return True

            except Exception as e:
                self._logger.error(f"启动 Scheduler 失败: {e}")
                return False

    async def _wait_for_scheduler_ready(self) -> bool:
        """等待 Scheduler 就绪"""
        if not self._config:
            return False

        timeout = self._config.startup_timeout
        check_interval = 0.5
        elapsed = 0.0

        while elapsed < timeout:
            # 检查进程是否还在运行
            if self._process_info and self._process_info.process.poll() is not None:
                exit_code = self._process_info.process.returncode
                stderr = ""
                try:
                    if self._process_info.process.stderr:
                        stderr = self._process_info.process.stderr.read().decode(
                            "utf-8", errors="replace"
                        )
                except Exception:
                    pass
                self._logger.error(
                    f"Scheduler 进程意外退出 | exit_code={exit_code} | stderr={stderr[:500]}"
                )
                return False

            # 检查健康状态
            if self._check_scheduler_health(timeout=1.0):
                self._logger.info(f"Scheduler 已就绪 (等待 {elapsed:.1f}s)")
                return True

            await asyncio.sleep(check_interval)
            elapsed += check_interval

        return False

    async def _stop_local_scheduler(self, timeout: float) -> None:
        """停止本地 Scheduler 进程"""
        async with self._process_lock:
            if not self._process_info:
                return

            process = self._process_info.process
            if process.poll() is not None:
                self._logger.debug("Scheduler 进程已停止")
                self._process_info = None
                return

            self._logger.info(f"正在停止 Scheduler (PID={self._process_info.pid})...")

            # 发送终止信号
            try:
                if sys.platform == "win32":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
            except Exception as e:
                self._logger.debug(f"发送终止信号失败: {e}")

            # 等待退出
            try:
                process.wait(timeout=timeout)
                self._logger.info("Scheduler 已优雅停止")
            except subprocess.TimeoutExpired:
                self._logger.warning("Scheduler 未响应，强制终止")
                process.kill()
                process.wait(timeout=5)
            finally:
                # 关闭管道流
                for stream in (process.stdout, process.stderr):
                    if stream:
                        try:
                            stream.close()
                        except Exception:
                            pass

            self._process_info = None
            self._logger.info("Scheduler 已停止")

    async def _cleanup(self) -> None:
        """清理资源"""
        async with self._process_lock:
            if self._process_info:
                process = self._process_info.process
                if process.poll() is None:
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except Exception:
                        pass
                # 关闭管道流
                for stream in (process.stdout, process.stderr):
                    if stream:
                        try:
                            stream.close()
                        except Exception:
                            pass
                self._process_info = None

    # ========================================================================
    # 状态查询
    # ========================================================================

    def get_status(self) -> Dict[str, Any]:
        """获取完整状态信息"""
        return {
            "state": self._state.value,
            "source": self._source.value,
            "error": self._error,
            "address": self.address,
            "dashboard_address": (
                self.dashboard_address if self._config and self._config.dashboard_enabled else None
            ),
            "process": {
                "pid": self._process_info.pid if self._process_info else None,
                "running": (
                    self._process_info.process.poll() is None if self._process_info else False
                ),
            },
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime": (
                (datetime.now() - self._started_at).total_seconds()
                if self._started_at and self.is_ready
                else None
            ),
        }


# ============================================================================
# 单例和便捷函数
# ============================================================================

_scheduler_manager: Optional[DaskSchedulerManager] = None
_scheduler_manager_lock = asyncio.Lock()


async def get_scheduler_manager() -> DaskSchedulerManager:
    """获取或创建单例管理器实例"""
    global _scheduler_manager
    async with _scheduler_manager_lock:
        if _scheduler_manager is None:
            _scheduler_manager = DaskSchedulerManager()
        return _scheduler_manager


async def ensure_scheduler() -> bool:
    """
    确保 Scheduler 可用

    Returns:
        True 如果 Scheduler 可用
    """
    manager = await get_scheduler_manager()
    return await manager.start()


async def stop_scheduler() -> None:
    """停止 Scheduler（如果是本地启动的）"""
    manager = await get_scheduler_manager()
    await manager.stop()


def get_scheduler_status() -> dict:
    """获取 Scheduler 状态"""
    global _scheduler_manager
    if _scheduler_manager is None:
        return {"state": "idle", "source": "none"}
    return _scheduler_manager.get_status()
