"""
Windows Dask Worker 管理器

在后端 API 启动时自动启动 Windows Dask Worker 进程，
用于托管需要 Windows 环境的数据源 SDK（AmazingData、MiniQMT 等）。

架构设计:
- DaskWorkerManager: 状态机管理 Worker 进程生命周期
- Worker Plugin: 通过 Dask 原生 setup/teardown 管理 Actor
- 单一初始化路径: Plugin.setup() 是唯一的 Actor 创建入口
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import signal
import site
import socket
import subprocess
import sys
import sysconfig
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from core.utils.system.port_reservation import PortReservation


# ============================================================================
# 状态定义
# ============================================================================


class DaskWorkerState(Enum):
    """Dask Worker Manager 状态机状态"""

    IDLE = "idle"  # 初始状态，无 Worker
    CHECKING = "checking"  # 检查 Scheduler 可达性
    STARTING = "starting"  # 启动 Worker 进程
    REGISTERING = "registering"  # 注册 Plugins
    RUNNING = "running"  # Workers 运行中
    STOPPING = "stopping"  # 正在停止
    STOPPED = "stopped"  # 已停止
    FAILED = "failed"  # 失败状态


class PluginState(Enum):
    """插件注册状态"""

    UNREGISTERED = "unregistered"
    REGISTERING = "registering"
    REGISTERED = "registered"
    FAILED = "failed"


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class WorkerProcessInfo:
    """Worker 进程元数据"""

    process: subprocess.Popen
    name: str
    port: int
    started_at: datetime
    pid: int


@dataclass
class PluginRegistration:
    """插件注册跟踪"""

    name: str
    state: PluginState = PluginState.UNREGISTERED
    error: Optional[str] = None
    registered_at: Optional[datetime] = None


@dataclass
class MemoryThresholds:
    """内存管理阈值"""

    target: float = 0.60
    spill: float = 0.70
    pause: float = 0.80
    terminate: float = 0.95


@dataclass
class DaskConfig:
    """Dask 配置数据类"""

    scheduler_address: str = "localhost:8786"
    enabled: bool = False
    auto_start: bool = False
    num_workers: int = 2
    threads_per_worker: int = 2
    memory_limit: str = "4GB"
    name_prefix: str = "windows-worker"
    resources: dict[str, int] = field(default_factory=lambda: {"WIN": 1})
    contact_host: Optional[str] = None
    local_directory: Optional[str] = None  # spill to disk 目录
    use_nanny: bool = True  # 是否使用 Nanny 进程
    memory_thresholds: MemoryThresholds = field(default_factory=MemoryThresholds)


# ============================================================================
# 主管理器类
# ============================================================================


class DaskWorkerManager:
    """
    Dask Worker 进程管理器 - 状态机实现

    职责:
    - 启动/停止 Windows Dask Worker 进程
    - 注册数据源插件 (AmazingData, AkShare, MiniQMT)
    - 监控进程健康状态
    - 提供线程安全的状态转换

    线程安全:
    - 使用 asyncio.Lock 保护状态修改
    - 状态转换是原子的
    """

    # 状态转换表
    # 允许从启动中任意阶段转换到停止状态，以支持 Ctrl+C 中断启动流程
    VALID_TRANSITIONS: ClassVar[Dict[DaskWorkerState, List[DaskWorkerState]]] = {
        DaskWorkerState.IDLE: [DaskWorkerState.CHECKING, DaskWorkerState.FAILED],
        DaskWorkerState.CHECKING: [
            DaskWorkerState.STARTING,
            DaskWorkerState.STOPPING,  # 允许中断启动
            DaskWorkerState.FAILED,
        ],
        DaskWorkerState.STARTING: [
            DaskWorkerState.REGISTERING,
            DaskWorkerState.STOPPING,  # 允许中断启动
            DaskWorkerState.FAILED,
        ],
        DaskWorkerState.REGISTERING: [
            DaskWorkerState.RUNNING,
            DaskWorkerState.STOPPING,  # 允许中断启动
            DaskWorkerState.FAILED,
        ],
        DaskWorkerState.RUNNING: [DaskWorkerState.STOPPING, DaskWorkerState.FAILED],
        DaskWorkerState.STOPPING: [DaskWorkerState.STOPPED, DaskWorkerState.FAILED],
        DaskWorkerState.STOPPED: [DaskWorkerState.IDLE],
        DaskWorkerState.FAILED: [DaskWorkerState.IDLE],
    }

    def __init__(
        self,
        config: Optional[DaskConfig] = None,
    ) -> None:
        """
        初始化管理器

        Args:
            config: Dask 配置（依赖注入）
        """
        self._config = config
        self._logger = logger.bind(component="DaskWorkerManager")

        # 状态机
        self._state = DaskWorkerState.IDLE
        self._state_lock = asyncio.Lock()
        self._error: Optional[str] = None

        # 进程管理
        self._workers: Dict[int, WorkerProcessInfo] = {}  # pid -> info
        self._process_lock = asyncio.Lock()

        # 插件注册（带状态跟踪）
        self._plugins: Dict[str, PluginRegistration] = {
            "amazingdata": PluginRegistration(name="amazingdata"),
            "akshare": PluginRegistration(name="akshare"),
            "miniqmt": PluginRegistration(name="miniqmt"),
        }
        self._plugin_lock = asyncio.Lock()

        # 元数据
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

        # 解析后的地址缓存
        self._parsed_host: str = "localhost"
        self._parsed_port: int = 8786

        # Plugin 就绪事件（用于等待 Plugin 在 Worker 上完成 setup）
        self._amazingdata_plugin_ready = asyncio.Event()

        # Redis URL（用于 Plugin 就绪检查）
        self._redis_url: str = "redis://localhost:6379"

    # ========================================================================
    # 属性
    # ========================================================================

    @property
    def state(self) -> DaskWorkerState:
        """当前状态（只读）"""
        return self._state

    @property
    def is_running(self) -> bool:
        """检查 Workers 是否在运行"""
        return self._state == DaskWorkerState.RUNNING

    @property
    def worker_count(self) -> int:
        """活跃 Worker 数量"""
        return len([w for w in self._workers.values() if w.process.poll() is None])

    # ========================================================================
    # 状态转换
    # ========================================================================

    async def _transition_to(
        self,
        target: DaskWorkerState,
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
            DaskWorkerState.IDLE,
            DaskWorkerState.STOPPED,
            DaskWorkerState.FAILED,
        )

    # ========================================================================
    # 生命周期方法
    # ========================================================================

    async def start(self) -> bool:
        """
        启动 Dask Workers 和注册 Plugins

        Returns:
            True 如果启动成功
        """
        if not self._can_start():
            self._logger.warning(f"无法从状态 {self._state.value} 启动")
            return False

        # 非 Windows 平台跳过
        if sys.platform != "win32":
            self._logger.debug("非 Windows 环境，跳过 Windows Worker 自启动")
            return True

        # 加载配置
        if not await self._load_config():
            return True  # 配置禁用时返回 True

        try:
            # 启动前清理残留 Worker（避免 "name taken" 错误）
            cleaned_count = await self._cleanup_stale_workers()
            if cleaned_count > 0:
                self._logger.info(f"已清理 {cleaned_count} 个残留 Worker，继续启动")

            # 阶段 1: 检查 Scheduler
            if not await self._transition_to(DaskWorkerState.CHECKING):
                return False

            if not self._check_scheduler():
                await self._transition_to(
                    DaskWorkerState.FAILED,
                    f"Scheduler 不可达 ({self._parsed_host}:{self._parsed_port})",
                )
                return False

            # 阶段 2: 启动 Workers
            if not await self._transition_to(DaskWorkerState.STARTING):
                return False

            if not await self._start_workers():
                await self._transition_to(DaskWorkerState.FAILED, "Worker 启动失败")
                return False

            # 阶段 3: 注册 Plugins
            if not await self._transition_to(DaskWorkerState.REGISTERING):
                return False

            await self._register_all_plugins()

            # 阶段 4: 运行中
            if not await self._transition_to(DaskWorkerState.RUNNING):
                return False

            self._started_at = datetime.now()
            return True

        except Exception as e:
            self._logger.error(f"启动失败: {e}")
            await self._transition_to(DaskWorkerState.FAILED, str(e))
            await self._cleanup_workers()
            return False

    async def stop(self, timeout: float = 10.0) -> None:
        """
        停止所有 Workers（优雅关闭）

        Dask 会自动调用 Plugin.teardown() 清理 Actor

        Args:
            timeout: 等待优雅关闭的最大时间
        """
        if self._state == DaskWorkerState.STOPPED:
            return

        if self._state == DaskWorkerState.IDLE:
            return

        await self._transition_to(DaskWorkerState.STOPPING)

        try:
            await self._stop_workers(timeout)
            await self._transition_to(DaskWorkerState.STOPPED)
            self._stopped_at = datetime.now()
        except Exception as e:
            self._logger.error(f"停止失败: {e}")
            await self._transition_to(DaskWorkerState.FAILED, str(e))

    async def reset(self) -> None:
        """重置到 IDLE 状态（用于重试）"""
        if self._state in (DaskWorkerState.FAILED, DaskWorkerState.STOPPED):
            await self._cleanup_workers()
            self._reset_plugin_states()
            await self._transition_to(DaskWorkerState.IDLE)

    # ========================================================================
    # 内部实现
    # ========================================================================

    async def _load_config(self) -> bool:
        """
        加载配置

        Returns:
            True 如果应该继续启动，False 如果配置禁用
        """
        try:
            from core.config import get_config

            settings = get_config()
            self._logger.info(f"[配置加载] 获取配置对象: {type(settings)}")

            # 获取 Dask 配置
            dask_config = getattr(settings, "dask", None)
            self._logger.info(f"[配置加载] dask_config: {type(dask_config)}, 值: {dask_config}")
            if dask_config is None:
                self._logger.warning("未找到 Dask 配置，跳过Worker启动")
                return False

            # 检查是否启用
            windows_workers = getattr(dask_config, "windows_workers", None)
            self._logger.info(
                f"[配置加载] windows_workers: {type(windows_workers)}, enabled={getattr(windows_workers, 'enabled', '未设置')}, auto_start={getattr(windows_workers, 'auto_start', '未设置')}"
            )
            if windows_workers is None:
                self._logger.warning("未找到 Windows Workers 配置")
                return False

            if not getattr(windows_workers, "enabled", False):
                self._logger.warning("Windows Workers 未启用，跳过Worker启动")
                return False

            if not getattr(windows_workers, "auto_start", False):
                self._logger.warning("Windows Workers 自启动未开启，跳过Worker启动")
                return False

            # 解析配置
            scheduler_address = getattr(dask_config, "scheduler_address", "localhost:8786")
            self._parsed_host, self._parsed_port = self._parse_scheduler_address(scheduler_address)

            # 读取 resources 配置
            resources_config = getattr(windows_workers, "resources", None)
            resources_dict: dict[str, int] = {}

            self._logger.info(f"读取 resources 配置: {resources_config}")

            if resources_config is not None:
                # 将配置对象转换为字典
                if hasattr(resources_config, "model_dump"):
                    resources_dict = resources_config.model_dump()
                elif hasattr(resources_config, "__dict__"):
                    resources_dict = dict(resources_config.__dict__)
                elif isinstance(resources_config, dict):
                    resources_dict = resources_config
                self._logger.info(f"转换后的 resources: {resources_dict}")
            else:
                # 默认值
                resources_dict = {"WIN": 1}
                self._logger.info(f"使用默认 resources: {resources_dict}")

            # 读取内存阈值配置
            memory_thresholds = MemoryThresholds()
            mem_thresholds_config = getattr(dask_config, "memory_thresholds", None)
            if mem_thresholds_config is not None:
                memory_thresholds = MemoryThresholds(
                    target=getattr(mem_thresholds_config, "target", 0.60),
                    spill=getattr(mem_thresholds_config, "spill", 0.70),
                    pause=getattr(mem_thresholds_config, "pause", 0.80),
                    terminate=getattr(mem_thresholds_config, "terminate", 0.95),
                )
                self._logger.info(
                    f"内存阈值配置: target={memory_thresholds.target}, "
                    f"spill={memory_thresholds.spill}, "
                    f"pause={memory_thresholds.pause}, "
                    f"terminate={memory_thresholds.terminate}"
                )

            self._config = DaskConfig(
                scheduler_address=scheduler_address,
                enabled=True,
                auto_start=True,
                num_workers=getattr(windows_workers, "num_workers", 2),
                threads_per_worker=getattr(windows_workers, "threads_per_worker", 2),
                memory_limit=getattr(windows_workers, "memory_limit", "4GB"),
                name_prefix=getattr(windows_workers, "name_prefix", "windows-worker"),
                resources=resources_dict,
                contact_host=getattr(windows_workers, "contact_host", None),
                local_directory=getattr(windows_workers, "local_directory", None),
                use_nanny=getattr(windows_workers, "use_nanny", True),
                memory_thresholds=memory_thresholds,
            )

            # 读取 Redis URL（用于 Plugin 就绪检查）
            database_config = getattr(settings, "database", None)
            if database_config:
                cache_config = getattr(database_config, "cache", None)
                if cache_config:
                    host = getattr(cache_config, "host", "localhost")
                    port = getattr(cache_config, "port", 6379)
                    self._redis_url = f"redis://{host}:{port}"
                    self._logger.info(f"Redis URL: {self._redis_url}")

            self._logger.info(f"DaskConfig 创建完成，resources={self._config.resources}")

            return True

        except Exception as e:
            self._logger.error(f"加载配置失败: {e}")
            return False

    def _forward_worker_logs(
        self, stream, worker_name: str, stream_type: str  # 'stdout' or 'stderr'
    ) -> None:
        """转发 Worker 进程的日志输出到主进程日志系统

        Args:
            stream: Worker 进程的 stdout 或 stderr 流
            worker_name: Worker 名称（用于日志标识）
            stream_type: 流类型标识
        """
        try:
            for line in iter(stream.readline, b""):
                if line:
                    decoded_line = line.decode("utf-8", errors="replace").rstrip()
                    if decoded_line:
                        # 转发到主日志系统
                        self._logger.info(f"[{worker_name}] {decoded_line}")
        except Exception as e:
            self._logger.debug(f"Worker {worker_name} 日志转发异常: {e}")
        finally:
            stream.close()

    def _check_scheduler(self) -> bool:
        """检查 Scheduler 是否可达"""
        try:
            with socket.create_connection((self._parsed_host, self._parsed_port), timeout=3):
                return True
        except (OSError, socket.timeout):
            self._logger.warning(f"Dask Scheduler 不可达 ({self._parsed_host}:{self._parsed_port})")
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

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        """判断主机地址是否为 loopback。"""
        value = str(host or "").strip().strip("[]").lower()
        if not value:
            return False
        if value in {"localhost", "127.0.0.1", "::1"}:
            return True
        try:
            return ipaddress.ip_address(value).is_loopback
        except ValueError:
            return False

    @staticmethod
    def _extract_host_from_address(address: str) -> str:
        """从 tcp://host:port 形式中提取 host。"""
        value = str(address or "").strip()
        if value.startswith("tcp://"):
            value = value[6:]
        if ":" in value:
            host, _ = value.rsplit(":", 1)
            return host
        return value

    async def _detect_scheduler_runtime_host(self) -> str | None:
        """从 Scheduler 运行时信息中解析真实 host。"""
        scheduler_address = f"tcp://{self._parsed_host}:{self._parsed_port}"
        try:
            from distributed import Client

            async with Client(
                scheduler_address,
                asynchronous=True,
                timeout="5s",
                set_as_default=False,
            ) as client:
                scheduler_info = client.scheduler_info() or {}
                runtime_address = str(scheduler_info.get("address") or scheduler_address)
                return self._extract_host_from_address(runtime_address)
        except Exception as exc:
            self._logger.debug(f"获取 Scheduler 运行时地址失败，使用配置地址回退: {exc}")
            return None

    async def _resolve_worker_contact_host(self) -> str:
        """解析 Worker contact host（优先显式配置，其次自动判定）。"""
        if self._config and self._config.contact_host:
            explicit = str(self._config.contact_host).strip()
            if explicit:
                self._logger.info(f"使用显式配置的 Worker contact host: {explicit}")
                return explicit

        env_override = os.getenv("DEEPSEARCH_DASK_WORKER_CONTACT_HOST", "").strip()
        if env_override:
            self._logger.info(f"使用环境变量覆盖的 Worker contact host: {env_override}")
            return env_override

        runtime_host = await self._detect_scheduler_runtime_host()
        configured_host = self._parsed_host

        if runtime_host and self._is_loopback_host(runtime_host):
            return "localhost"

        if self._is_loopback_host(configured_host) and runtime_host and not self._is_loopback_host(
            runtime_host
        ):
            # 配置是 localhost，但实际 Scheduler 在容器/远端网络中，需避免回连到 127.0.0.1
            self._logger.info(
                f"检测到外部 Scheduler 运行地址 {runtime_host}，Worker contact host 切换为 host.docker.internal"
            )
            return "host.docker.internal"

        if runtime_host and not self._is_loopback_host(runtime_host):
            return runtime_host

        return "localhost"

    def _get_site_packages_paths(self) -> list[str]:
        """获取 site-packages 路径（多重 fallback）

        UV 虚拟环境下 site.getsitepackages() 可能返回不正确的路径，
        需要使用多种方法尝试获取正确的 site-packages 路径。

        Returns:
            site-packages 路径列表
        """
        paths: list[str] = []
        seen: set[str] = set()

        def add_path(p: str) -> None:
            """添加路径（去重）"""
            if p and p not in seen and os.path.isdir(p):
                seen.add(p)
                paths.append(p)

        # 方法 1: site.getsitepackages()（标准方法）
        try:
            site_packages = site.getsitepackages()
            if site_packages:
                for sp in site_packages:
                    add_path(sp)
                self._logger.debug(f"site.getsitepackages(): {site_packages}")
        except Exception as e:
            self._logger.debug(f"site.getsitepackages() 失败: {e}")

        # 方法 2: sysconfig.get_path('purelib')（UV 虚拟环境更可靠）
        try:
            purelib = sysconfig.get_path("purelib")
            if purelib:
                add_path(purelib)
                self._logger.debug(f"sysconfig purelib: {purelib}")
        except Exception as e:
            self._logger.debug(f"sysconfig.get_path('purelib') 失败: {e}")

        # 方法 3: 从 sys.prefix 推断（Windows 虚拟环境）
        try:
            if sys.platform == "win32":
                # Windows: venv/Lib/site-packages
                win_site_packages = os.path.join(sys.prefix, "Lib", "site-packages")
                add_path(win_site_packages)
            else:
                # Unix: venv/lib/pythonX.Y/site-packages
                py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
                unix_site_packages = os.path.join(sys.prefix, "lib", py_version, "site-packages")
                add_path(unix_site_packages)
        except Exception as e:
            self._logger.debug(f"从 sys.prefix 推断 site-packages 失败: {e}")

        # 方法 4: 从 sys.path 提取已知的 site-packages 路径
        try:
            for p in sys.path:
                if "site-packages" in p and os.path.isdir(p):
                    add_path(p)
        except Exception as e:
            self._logger.debug(f"从 sys.path 提取 site-packages 失败: {e}")

        return paths

    def _build_pythonpath(self, worker_name: str) -> str:
        """构建 Worker 进程的 PYTHONPATH

        确保包含：
        1. 项目根目录（deepsearch/）
        2. packages 目录（deepsearch/packages/）- 关键修复点
        3. site-packages 路径（多重 fallback）
        4. 已有的 PYTHONPATH

        Args:
            worker_name: Worker 名称（用于日志）

        Returns:
            完整的 PYTHONPATH 字符串
        """
        pythonpath_parts: list[str] = []
        seen: set[str] = set()

        def add_path(p: str) -> None:
            """添加路径（去重）"""
            if p and p not in seen:
                seen.add(p)
                pythonpath_parts.append(p)

        # 1. 项目根目录（deepsearch/）
        project_root = Path(
            __file__
        ).parent.parent.parent.parent  # compute -> core -> packages -> deepsearch
        add_path(str(project_root))

        # 2. packages 目录（关键修复：确保 import core.xxx 能正常工作）
        packages_dir = project_root / "packages"
        if packages_dir.is_dir():
            add_path(str(packages_dir))
            self._logger.debug(f"Worker {worker_name}: 添加 packages 目录到 PYTHONPATH")
        else:
            self._logger.warning(f"Worker {worker_name}: packages 目录不存在: {packages_dir}")

        # 3. site-packages 路径（多重 fallback）
        site_packages_paths = self._get_site_packages_paths()
        for sp in site_packages_paths:
            add_path(sp)

        # 4. 保留已有的 PYTHONPATH
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        if existing_pythonpath:
            for p in existing_pythonpath.split(os.pathsep):
                add_path(p)

        pythonpath = os.pathsep.join(pythonpath_parts)

        self._logger.info(
            f"Worker {worker_name}: PYTHONPATH 构建完成 | "
            f"paths_count={len(pythonpath_parts)} | "
            f"包含 packages={str(packages_dir) in pythonpath}"
        )
        self._logger.debug(f"Worker {worker_name}: PYTHONPATH={pythonpath}")

        return pythonpath

    def _reserve_ports(
        self, count: int, start_port: int = 58200, max_range: int = 100
    ) -> tuple[list[int], "PortReservation"]:
        """
        预留 N 个端口（原子性操作，解决 TOCTOU 竞态条件）

        使用 PortReservation 通过 socket bind 原子性预留端口，
        确保多个 Worker 不会抢占同一端口。

        Args:
            count: 需要的端口数量
            start_port: 起始端口
            max_range: 搜索范围

        Returns:
            (预留的端口列表, PortReservation 实例)
            调用者需要在 Worker 启动后调用 reservation.release_all() 释放预留

        Raises:
            RuntimeError: 无法找到足够的可用端口
        """
        from core.utils.system.port_reservation import PortReservation

        reservation = PortReservation()
        try:
            ports = reservation.reserve_ports(
                count=count,
                start_port=start_port,
                max_range=max_range,
                host="0.0.0.0",
            )
            self._logger.info(f"已预留端口: {ports}")
            return ports, reservation
        except RuntimeError:
            reservation.release_all()
            raise

    def _close_process_streams(self, process: subprocess.Popen) -> None:
        """
        安全关闭进程的管道流

        关闭管道流会使日志转发线程的 readline() 返回或抛出异常，
        从而让线程能够正常退出。

        Args:
            process: 要关闭管道流的进程
        """
        for stream_name in ("stdout", "stderr"):
            stream = getattr(process, stream_name, None)
            if stream:
                try:
                    stream.close()
                except Exception:
                    pass

    async def _wait_for_worker_ready(
        self, worker_name: str, timeout: float = 30.0, check_interval: float = 1.0
    ) -> bool:
        """等待 Worker 就绪（通过检查进程状态和日志）

        Args:
            worker_name: Worker 名称
            timeout: 最大等待时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            True 如果 Worker 就绪，False 如果超时或失败
        """
        elapsed = 0.0
        while elapsed < timeout:
            # 检查进程是否还在运行
            worker_info = next((w for w in self._workers.values() if w.name == worker_name), None)
            if worker_info:
                if worker_info.process.poll() is not None:
                    exit_code = worker_info.process.returncode
                    # 尝试读取 stderr（可能已被日志转发线程消费）
                    stderr_output = ""
                    try:
                        if worker_info.process.stderr and not worker_info.process.stderr.closed:
                            # 非阻塞读取剩余内容
                            remaining = worker_info.process.stderr.read()
                            if remaining:
                                stderr_output = remaining.decode("utf-8", errors="replace")
                    except Exception as e:
                        stderr_output = f"[读取失败: {e}]"

                    self._logger.error(
                        f"Worker {worker_name} 意外退出 | "
                        f"exit_code={exit_code} | "
                        f"stderr={stderr_output[:500] if stderr_output else '[已被日志转发线程消费，请查看上方日志]'}"
                    )
                    return False

            # 简单的时间等待（Dask Worker 通常在 5-10 秒内连接）
            # 更完善的实现可以检查 Scheduler 的 Worker 列表
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # 如果已经等待足够长时间，认为就绪
            if elapsed >= min(5.0, timeout / 2):
                return True

        return True  # 超时但不失败，继续执行

    async def _start_workers(self) -> bool:
        """启动 Worker 进程（支持重试）"""
        if not self._config:
            return False

        max_retries = 2  # 最多重试次数
        retry_delay = 2.0  # 重试延迟（秒）

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self._logger.info(f"重试启动 Workers (尝试 {attempt + 1}/{max_retries})...")
                    await asyncio.sleep(retry_delay * attempt)  # 指数退避

                if await self._do_start_workers():
                    return True

            except Exception as e:
                self._logger.warning(f"Worker 启动失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await self._cleanup_workers()
                else:
                    raise

        return False

    async def _do_start_workers(self) -> bool:
        """实际执行 Worker 启动（单次尝试）

        使用端口预留机制解决 TOCTOU 竞态条件：
        1. 原子性预留所有需要的端口
        2. 启动所有 Worker 进程
        3. 等待 Worker 绑定端口（0.5秒）
        4. 释放端口预留
        """
        if not self._config:
            return False

        # 用于跟踪端口预留，确保在所有路径上释放
        port_reservation = None

        async with self._process_lock:
            # 检查是否已有运行中的 Worker
            running = [w for w in self._workers.values() if w.process.poll() is None]
            if running:
                self._logger.debug(f"已有 {len(running)} 个 Worker 在运行")
                return True

            # 清空旧记录
            self._workers.clear()

            host_address = await self._resolve_worker_contact_host()

            # 原子性预留端口（解决 TOCTOU 竞态条件）
            try:
                worker_ports, port_reservation = self._reserve_ports(
                    count=self._config.num_workers,
                    start_port=getattr(self._config, "port_range_start", 58200),
                    max_range=100,
                )
            except RuntimeError as e:
                self._logger.error(f"端口预留失败: {e}")
                return False

            for i, worker_port in enumerate(worker_ports):
                worker_name = f"{self._config.name_prefix}-{i}"

                # 使用 sys.executable 直接调用 Python 模块，而不是 uv run
                # 原因: uv run dask worker 启动 Nanny 时，Nanny fork 的子进程
                # 无法继承 uv 的虚拟环境，导致 Worker 启动失败
                cmd = [
                    sys.executable,
                    "-m",
                    "distributed.cli.dask_worker",
                    f"tcp://{self._parsed_host}:{self._parsed_port}",
                    "--nthreads",
                    str(self._config.threads_per_worker),
                    "--memory-limit",
                    self._config.memory_limit,
                ]

                # Nanny 进程配置（启用 Nanny 后 terminate 阈值才生效）
                if not self._config.use_nanny:
                    cmd.append("--no-nanny")
                    self._logger.warning(
                        f"Worker {worker_name}: Nanny 进程已禁用，内存 terminate 阈值将失效"
                    )

                # 本地临时目录（用于 spill to disk）
                if self._config.local_directory:
                    # 确保目录存在
                    local_dir = os.path.abspath(self._config.local_directory)
                    os.makedirs(local_dir, exist_ok=True)
                    cmd.extend(["--local-directory", local_dir])
                    self._logger.info(f"Worker {worker_name}: spill 目录 = {local_dir}")

                # 添加资源标签
                self._logger.info(
                    f"Worker {worker_name}: self._config.resources = {self._config.resources}"
                )

                if self._config.resources:
                    # 规范化为 float 类型（Dask 内部要求）
                    resources_normalized = {k: float(v) for k, v in self._config.resources.items()}

                    # 使用多参数格式，每个资源独立传递（避免 Windows shell 解析问题）
                    for key, value in resources_normalized.items():
                        resource_arg = f"{key}={value}"
                        cmd.extend(["--resources", resource_arg])
                        self._logger.info(
                            f"Worker {worker_name}: 添加资源参数 --resources {resource_arg} (类型: float)"
                        )

                    self._logger.info(
                        f"Worker {worker_name}: 资源配置完成 | "
                        f"resources={resources_normalized} | "
                        f"预期 Worker 运行时应显示相同值"
                    )
                else:
                    self._logger.warning(
                        f"Worker {worker_name}: resources 为空或 None，跳过资源标签 | "
                        f"可能导致 Windows 特定 plugins 无法激活"
                    )

                cmd.extend(
                    [
                        "--name",
                        worker_name,
                        "--listen-address",
                        f"tcp://0.0.0.0:{worker_port}",
                        "--contact-address",
                        f"tcp://{host_address}:{worker_port}",
                    ]
                )

                # 打印完整的启动命令用于调试
                cmd_str = " ".join(cmd)
                self._logger.info(f"启动 Worker {i + 1}/{self._config.num_workers}: {worker_name}")
                self._logger.info(f"完整启动命令: {cmd_str}")
                self._logger.info(f"命令列表: {cmd}")
                self._logger.debug(f"Worker 启动命令: {cmd_str}")

                # 构建环境变量（包含资源标签和内存阈值）
                env = os.environ.copy()

                # 设置 PYTHONPATH（使用新的 _build_pythonpath 方法）
                # 关键修复：确保包含 packages 目录，使 import core.xxx 正常工作
                env["PYTHONPATH"] = self._build_pythonpath(worker_name)

                # 设置内存管理阈值（通过 Dask 环境变量）
                thresholds = self._config.memory_thresholds
                env["DASK_DISTRIBUTED__WORKER__MEMORY__TARGET"] = str(thresholds.target)
                env["DASK_DISTRIBUTED__WORKER__MEMORY__SPILL"] = str(thresholds.spill)
                env["DASK_DISTRIBUTED__WORKER__MEMORY__PAUSE"] = str(thresholds.pause)
                env["DASK_DISTRIBUTED__WORKER__MEMORY__TERMINATE"] = str(thresholds.terminate)
                self._logger.info(
                    f"Worker {worker_name}: 内存阈值环境变量已设置 | "
                    f"target={thresholds.target}, spill={thresholds.spill}, "
                    f"pause={thresholds.pause}, terminate={thresholds.terminate}"
                )

                # 设置资源标签
                if self._config.resources:
                    for key, value in self._config.resources.items():
                        env_key = f"DASK_DISTRIBUTED__WORKER__RESOURCES__{key.upper()}"
                        env[env_key] = str(float(value))
                        self._logger.info(
                            f"Worker {worker_name}: 设置环境变量 {env_key}={env[env_key]}"
                        )

                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,  # 传递包含资源配置的环境变量
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    )

                    self._workers[process.pid] = WorkerProcessInfo(
                        process=process,
                        name=worker_name,
                        port=worker_port,
                        started_at=datetime.now(),
                        pid=process.pid,
                    )

                    # 启动日志转发线程（daemon 线程，不阻塞主进程退出）
                    stdout_thread = threading.Thread(
                        target=self._forward_worker_logs,
                        args=(process.stdout, worker_name, "stdout"),
                        daemon=True,
                        name=f"{worker_name}-stdout-forwarder",
                    )
                    stdout_thread.start()

                    stderr_thread = threading.Thread(
                        target=self._forward_worker_logs,
                        args=(process.stderr, worker_name, "stderr"),
                        daemon=True,
                        name=f"{worker_name}-stderr-forwarder",
                    )
                    stderr_thread.start()

                    self._logger.debug(f"已启动 {worker_name} 日志转发线程 (PID={process.pid})")

                except Exception as e:
                    self._logger.error(f"启动 Worker {i} 失败: {e}")
                    if port_reservation:
                        port_reservation.release_all()
                    await self._cleanup_workers()
                    return False

            # 所有 Worker 进程已启动，等待它们绑定端口后释放预留
            # 延迟 0.5 秒让 Worker 有时间完成端口绑定
            self._logger.info("等待 Workers 绑定端口...")
            await asyncio.sleep(0.5)

            # 释放端口预留（Worker 已绑定端口）
            if port_reservation:
                port_reservation.release_all()
                self._logger.info("端口预留已释放")

            # 等待所有 Workers 就绪（健康检查）
            self._logger.info("等待 Workers 就绪...")
            ready_count = 0
            for pid, info in self._workers.items():
                # 从统一超时配置读取 worker_ready 超时
                _wr_timeout = 30.0
                try:
                    from core.config import get_config as _get_cfg2

                    _tc2 = getattr(_get_cfg2(), "timeouts", None)
                    if _tc2:
                        _wr_timeout = _tc2.dask.worker_ready
                except Exception:
                    pass
                is_ready = await self._wait_for_worker_ready(info.name, timeout=_wr_timeout)
                if is_ready:
                    ready_count += 1
                    self._logger.info(f"Worker {info.name} 已就绪 (PID={pid})")
                else:
                    self._logger.warning(f"Worker {info.name} 未就绪")

            # 最终检查进程状态
            failed = []
            for pid, info in self._workers.items():
                if info.process.poll() is not None:
                    exit_code = info.process.returncode
                    # 尝试读取 stderr（可能已被日志转发线程消费）
                    stderr_output = ""
                    try:
                        if info.process.stderr and not info.process.stderr.closed:
                            remaining = info.process.stderr.read()
                            if remaining:
                                stderr_output = remaining.decode("utf-8", errors="replace")
                    except Exception as e:
                        stderr_output = f"[读取失败: {e}]"

                    self._logger.error(
                        f"Worker {info.name} 启动后退出 | "
                        f"exit_code={exit_code} | "
                        f"stderr={stderr_output[:500] if stderr_output else '[已被日志转发线程消费，请查看上方日志]'}"
                    )
                    failed.append(pid)

            if failed:
                await self._cleanup_workers()
                return False

            pids = list(self._workers.keys())
            self._logger.info(
                f"Workers 已启动 ({len(pids)} 个, {ready_count} 个就绪, PIDs: {pids})"
            )
            return True

    async def _stop_workers(self, timeout: float) -> None:
        """停止所有 Worker 进程"""
        async with self._process_lock:
            running = [info for info in self._workers.values() if info.process.poll() is None]

            if not running:
                self._workers.clear()
                return

            self._logger.info(f"正在停止 {len(running)} 个 Workers...")

            # 先通过 Dask Client 发送 retire 命令，让 Scheduler 主动注销 Worker
            # 这样即使进程被强制杀死，Scheduler 上也不会残留 Worker 注册信息
            await self._retire_workers_from_scheduler(running)

            # 优雅关闭
            for info in running:
                try:
                    if sys.platform == "win32":
                        info.process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        info.process.terminate()
                except Exception as e:
                    self._logger.debug(f"发送终止信号失败: {e}")

            # 等待退出（使用 run_in_executor 避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            for info in running:
                try:
                    # 将同步的 process.wait() 放到线程池中执行，避免阻塞事件循环
                    await asyncio.wait_for(
                        loop.run_in_executor(None, lambda p=info.process: p.wait(timeout=timeout)),  # type: ignore[misc]
                        timeout=timeout + 1.0,
                    )
                except (subprocess.TimeoutExpired, asyncio.TimeoutError):
                    self._logger.warning(f"Worker {info.name} 未响应，强制终止")
                    info.process.kill()
                    # kill 后也用异步等待，避免阻塞
                    await loop.run_in_executor(None, lambda p=info.process: p.wait(timeout=5))  # type: ignore[misc]
                finally:
                    # 关闭管道流，释放日志转发线程的阻塞
                    self._close_process_streams(info.process)

            self._workers.clear()
            self._logger.info("Workers 已全部停止")

    async def _cleanup_stale_workers(self) -> int:
        """清理 Scheduler 上的残留 Worker 注册

        在启动新 Worker 前调用，避免 "name taken" 错误。
        查找所有以当前 name_prefix 开头的已注册 Worker 并移除。

        Returns:
            清理的 Worker 数量
        """
        from distributed import Client

        if not self._config:
            return 0

        scheduler_address = f"tcp://{self._parsed_host}:{self._parsed_port}"

        try:
            async with Client(
                scheduler_address,
                asynchronous=True,
                timeout="5s",
            ) as client:
                # scheduler_info() 返回同步结果，不需要 await
                scheduler_info = client.scheduler_info()
                registered_workers = scheduler_info.get("workers", {})

                # 查找所有以 name_prefix 开头的已注册 Worker
                stale_workers = [
                    addr
                    for addr, info in registered_workers.items()
                    if info.get("name", "").startswith(self._config.name_prefix)
                ]

                if stale_workers:
                    stale_names = [registered_workers[addr].get("name") for addr in stale_workers]
                    self._logger.warning(
                        f"发现 {len(stale_workers)} 个残留 Worker 注册，正在清理 | "
                        f"workers={stale_names}"
                    )
                    await client.retire_workers(stale_workers, close_workers=True)
                    self._logger.info("残留 Worker 清理完成")
                    return len(stale_workers)

                return 0

        except Exception as e:
            # 清理失败不阻塞启动，只记录警告
            self._logger.warning(f"清理残留 Worker 失败（继续启动）| error={e}")
            return 0

    async def _retire_workers_from_scheduler(self, workers: list) -> None:
        """
        通过 Dask Client 发送 retire 命令，让 Scheduler 主动注销 Worker

        这样即使进程被强制杀死，Scheduler 上也不会残留 Worker 注册信息，
        避免下次启动时出现 "name taken" 错误。

        Args:
            workers: 要注销的 Worker 信息列表
        """
        if not workers:
            return

        worker_names = [info.name for info in workers]
        scheduler_address = f"tcp://{self._parsed_host}:{self._parsed_port}"

        try:
            from distributed import Client

            # 使用短超时连接 Scheduler
            async with Client(scheduler_address, asynchronous=True, timeout="5s") as client:
                # 获取 Scheduler 上已注册的 Worker
                # scheduler_info() 返回同步结果，不需要 await
                scheduler_info = client.scheduler_info()
                registered_workers = scheduler_info.get("workers", {})

                # 找出需要 retire 的 Worker 地址
                workers_to_retire = []
                for addr, info in registered_workers.items():
                    worker_name = info.get("name", "")
                    if worker_name in worker_names:
                        workers_to_retire.append(addr)
                        self._logger.debug(f"准备从 Scheduler 注销 Worker: {worker_name} ({addr})")

                if workers_to_retire:
                    # 发送 retire 命令
                    await client.retire_workers(workers_to_retire, close_workers=False)
                    self._logger.info(
                        f"已从 Scheduler 注销 {len(workers_to_retire)} 个 Worker: {worker_names}"
                    )
                else:
                    self._logger.debug("Scheduler 上没有找到需要注销的 Worker")

        except Exception as e:
            # retire 失败不应阻止进程终止，只记录警告
            self._logger.warning(f"从 Scheduler 注销 Worker 失败（将继续终止进程）: {e}")

    async def _cleanup_workers(self) -> None:
        """清理所有 Worker 进程"""
        async with self._process_lock:
            for info in self._workers.values():
                if info.process.poll() is None:
                    try:
                        info.process.kill()
                        info.process.wait(timeout=5)
                    except Exception:
                        pass
                # 确保管道流被关闭
                self._close_process_streams(info.process)
            self._workers.clear()

    def _reset_plugin_states(self) -> None:
        """重置插件状态"""
        for plugin in self._plugins.values():
            plugin.state = PluginState.UNREGISTERED
            plugin.error = None
            plugin.registered_at = None

    async def _register_all_plugins(self) -> None:
        """注册所有 Plugins

        注册 Plugin 后，会等待 AmazingData Plugin 在 Worker 上完成 setup。
        这确保了在后续注册 Adapter 时，Actor 已经可用。
        """
        scheduler_address = f"tcp://{self._parsed_host}:{self._parsed_port}"

        # 并行注册，各自处理错误
        tasks = [
            self._register_plugin_safe("amazingdata", scheduler_address),
            self._register_plugin_safe("miniqmt", scheduler_address),
        ]

        await asyncio.gather(*tasks)

        # 统计结果
        registered = [
            name for name, p in self._plugins.items() if p.state == PluginState.REGISTERED
        ]
        failed = [name for name, p in self._plugins.items() if p.state == PluginState.FAILED]

        if registered:
            self._logger.info(f"Plugins 已注册: {registered}")
        if failed:
            self._logger.warning(f"Plugins 注册失败: {failed}")

        # 等待 AmazingData Plugin 在 Worker 上完成 setup
        # 这是关键步骤：确保 Actor 真正可用后再设置就绪事件
        if "amazingdata" in registered:
            # 关键修复：等待 Plugin 被 Scheduler 发送到 Worker
            # client.register_plugin() 返回后，Plugin 只是被发送给了 Scheduler
            # 还需要额外时间让 Scheduler 将 Plugin 调度到 Worker 并开始执行 setup
            self._logger.info("等待 Plugin 被调度到 Worker...")
            await asyncio.sleep(3.0)

            self._logger.info("等待 AmazingData Plugin 在 Worker 上完成 setup...")
            # 从统一超时配置读取
            _ad_timeout = 45.0
            try:
                from core.config import get_config as _get_cfg

                _tc = getattr(_get_cfg(), "timeouts", None)
                if _tc:
                    _ad_timeout = _tc.amazingdata.normal_call
            except Exception:
                pass
            plugin_ready = await self._wait_for_plugin_setup(
                actor_name="amazingdata",
                timeout=_ad_timeout,
            )
            if plugin_ready:
                self._amazingdata_plugin_ready.set()
                self._logger.info("AmazingData Plugin 已在 Worker 上就绪")
            else:
                # 关键修复：超时时也设置 Event，避免上层无限等待
                # Event 语义应该是"等待结束"而非"成功完成"
                self._amazingdata_plugin_ready.set()
                self._logger.warning(
                    "AmazingData Plugin setup 超时，但将继续执行 | "
                    "后续 Adapter 初始化会再次检查 Actor 可用性"
                )

    async def _register_plugin_safe(self, name: str, scheduler_address: str) -> None:
        """安全注册单个 Plugin"""
        try:
            await self._register_plugin(name, scheduler_address)
        except Exception as e:
            self._logger.error(f"Plugin {name} 注册失败: {e}")

    async def _register_plugin(self, name: str, scheduler_address: str) -> bool:
        """
        原子注册单个 Plugin

        使用锁确保同一 Plugin 不会被重复注册
        """
        async with self._plugin_lock:
            plugin = self._plugins.get(name)
            if not plugin:
                return False

            if plugin.state == PluginState.REGISTERED:
                return True

            if plugin.state == PluginState.REGISTERING:
                return False  # 已有注册在进行

            plugin.state = PluginState.REGISTERING

        try:
            success = await self._do_register_plugin(name, scheduler_address)

            async with self._plugin_lock:
                if success:
                    plugin.state = PluginState.REGISTERED
                    plugin.registered_at = datetime.now()
                else:
                    plugin.state = PluginState.FAILED

            return success

        except Exception as e:
            async with self._plugin_lock:
                plugin.state = PluginState.FAILED
                plugin.error = str(e)
            raise

    async def _do_register_plugin(self, name: str, scheduler_address: str) -> bool:
        """实际执行 Plugin 注册"""
        try:
            from core.config import get_config
            from distributed import Client

            settings = get_config()

            # 获取 Redis URL
            redis_url = "redis://localhost:6379"
            database_config = getattr(settings, "database", None)
            if database_config:
                cache_config = getattr(database_config, "cache", None)
                if cache_config:
                    host = getattr(cache_config, "host", "localhost")
                    port = getattr(cache_config, "port", 6379)
                    redis_url = f"redis://{host}:{port}"

            # 根据名称导入并注册对应的 Plugin
            async with Client(scheduler_address, asynchronous=True, timeout="60s") as client:
                if name == "amazingdata":
                    from core.compute.plugins.config import AmazingDataPluginConfig
                    from core.infrastructure.providers.implementations.amazingdata.dask_plugin import (
                        AmazingDataWorkerPlugin,
                    )

                    # 使用 Pydantic 配置模型
                    plugin_config = AmazingDataPluginConfig(
                        redis_url=redis_url,
                        only_on_windows=True,
                    )
                    plugin = AmazingDataWorkerPlugin(plugin_config)

                elif name == "miniqmt":
                    from core.compute.plugins.config import MiniQMTPluginConfig
                    from core.infrastructure.providers.implementations.qmt.dask_plugin import (
                        MiniQMTWorkerPlugin,
                    )

                    # 获取 MiniQMT 特定配置
                    cache_ttl = 300
                    failure_threshold = 5
                    # 从统一超时配置读取熔断器恢复超时
                    _tc_cb = getattr(settings, "timeouts", None)
                    recovery_timeout = _tc_cb.dask.circuit_breaker_recovery if _tc_cb else 60

                    data_sources = getattr(settings, "data_sources", None)
                    if data_sources:
                        providers = getattr(data_sources, "providers", None)
                        if providers:
                            miniqmt_provider = getattr(providers, "miniqmt", None)
                            if miniqmt_provider:
                                provider_config = getattr(miniqmt_provider, "config", None)
                                if provider_config:
                                    cache_cfg = getattr(provider_config, "cache", None)
                                    if cache_cfg:
                                        cache_ttl = getattr(cache_cfg, "ttl", 300)
                                    failure_threshold = getattr(
                                        provider_config, "failure_threshold", 5
                                    )

                    # 使用 Pydantic 配置模型（修复参数签名不匹配）
                    plugin_config = MiniQMTPluginConfig(  # type: ignore[assignment]
                        redis_url=redis_url,
                        only_on_windows=True,
                        cache_ttl=cache_ttl,
                        failure_threshold=failure_threshold,
                        recovery_timeout=recovery_timeout,
                    )
                    plugin = MiniQMTWorkerPlugin(plugin_config)  # type: ignore[arg-type]

                else:
                    self._logger.warning(f"未知的 Plugin: {name}")
                    return False

                await client.register_plugin(plugin)
                self._logger.info(f"{name} Plugin 已注册 | redis_url={redis_url}")
                return True

        except ImportError as e:
            self._logger.warning(f"无法导入 {name} Plugin: {e}")
            return False
        except Exception as e:
            self._logger.error(f"注册 {name} Plugin 失败: {e}")
            return False

    # ========================================================================
    # Plugin 就绪等待
    # ========================================================================

    async def wait_amazingdata_plugin_ready(self, timeout: float = 60.0) -> bool:
        """等待 AmazingData Plugin 在 Worker 上就绪

        当 Plugin 在 Worker 上完成 setup（包括 Actor 注册到 Redis）后，
        此方法返回 True。用于确保在注册 Adapter 前 Actor 已可用。

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            True 如果 Plugin 已就绪，False 如果超时
        """
        try:
            await asyncio.wait_for(
                self._amazingdata_plugin_ready.wait(),
                timeout=timeout,
            )
            self._logger.info("AmazingData Plugin 就绪事件已触发")
            return True
        except asyncio.TimeoutError:
            self._logger.warning(f"等待 AmazingData Plugin 就绪超时 ({timeout}s)")
            return False

    async def _wait_for_plugin_setup(
        self,
        actor_name: str,
        timeout: float = 45.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """等待 Plugin 在 Worker 上完成 setup

        通过 Redis 轮询检查 Actor 是否已在 Worker 上注册。
        Plugin 的 setup() 方法会在完成时设置 Redis 键。

        Args:
            actor_name: Actor 名称（如 "amazingdata"）
            timeout: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            True 如果 Actor 已就绪，False 如果超时或失败
        """
        import redis

        redis_key = f"dask_actor_ready:{actor_name}"
        max_polls = int(timeout / poll_interval)

        self._logger.info(
            f"等待 {actor_name} Plugin setup 完成 | "
            f"redis_key={redis_key} | redis_url={self._redis_url} | timeout={timeout}s"
        )

        try:
            # 创建 Redis 客户端（同步版本，用于简单轮询）
            redis_client = redis.from_url(self._redis_url)  # type: ignore[attr-defined]

            # 验证 Redis 连接
            try:
                redis_client.ping()
                self._logger.info(f"Redis 连接验证成功 | url={self._redis_url}")
            except Exception as e:
                self._logger.error(f"Redis 连接失败! | url={self._redis_url} | error={e}")
                # 连接失败时直接尝试 Actor 直接检查
                actor_available = await self._check_actor_directly(actor_name)
                if actor_available:
                    self._logger.info(f"{actor_name} Actor 直接检查可用（绕过 Redis）")
                    return True
                return False

            for i in range(max_polls):
                try:
                    # 检查 Redis 键是否存在
                    ready_value = redis_client.get(redis_key)
                    if ready_value:
                        self._logger.info(
                            f"{actor_name} Plugin setup 完成 | "
                            f"检测到 Redis 键 | value={ready_value} | poll_count={i + 1}"
                        )
                        redis_client.close()
                        return True
                except Exception as e:
                    self._logger.warning(f"Redis 轮询失败: {e}")

                # 等待下一轮轮询
                await asyncio.sleep(poll_interval)

                # 每 5 秒输出一次进度日志（便于诊断）
                if (i + 1) % 5 == 0:
                    elapsed = (i + 1) * poll_interval
                    self._logger.info(
                        f"仍在等待 {actor_name} Plugin setup | elapsed={elapsed:.0f}s/{timeout:.0f}s"
                    )

            redis_client.close()

            # Redis 轮询超时，尝试直接检查 Actor 可用性（fallback 机制）
            self._logger.warning(
                f"{actor_name} Plugin setup 超时（Redis 轮询）| " f"尝试直接检查 Actor 可用性..."
            )

            actor_available = await self._check_actor_directly(actor_name)
            if actor_available:
                self._logger.info(f"{actor_name} Actor 直接检查可用（绕过 Redis）")
                return True

            self._logger.warning(
                f"{actor_name} Plugin setup 超时 | timeout={timeout}s | "
                f"redis_key={redis_key} 未检测到，Actor 直接检查也失败"
            )
            return False

        except Exception as e:
            self._logger.error(f"等待 Plugin setup 失败: {e}")
            return False

    async def _check_actor_directly(self, actor_name: str) -> bool:
        """直接检查 Actor 是否可用（不依赖 Redis）

        当 Redis 轮询超时时，通过 Dask Client 直接在 Worker 上检查
        Actor 是否已注册。这是一个 fallback 机制，用于应对 Redis 键
        未正确设置但 Actor 实际已可用的情况。

        Args:
            actor_name: Actor 名称（如 "amazingdata"）

        Returns:
            True 如果 Actor 在 Worker 上可用，False 否则
        """
        from distributed import Client

        scheduler_address = f"tcp://{self._parsed_host}:{self._parsed_port}"

        try:
            async with Client(scheduler_address, asynchronous=True, timeout="10s") as client:
                # 获取 Worker 列表
                scheduler_info = client.scheduler_info()
                workers = scheduler_info.get("workers", {})

                if not workers:
                    self._logger.warning("直接检查 Actor: 没有可用的 Worker")
                    return False

                self._logger.info(
                    f"直接检查 Actor: 找到 {len(workers)} 个 Worker | "
                    f"workers={list(workers.keys())}"
                )

                # 定义在 Worker 上执行的检查函数
                def check_actor_on_worker(target_actor_name: str) -> bool:
                    """在 Worker 上检查 Actor 是否已注册"""
                    try:
                        from distributed import get_worker

                        worker = get_worker()
                        actors = getattr(worker, "actors", {})

                        # Actor 键名格式: "{actor_name}-actor"
                        actor_key = f"{target_actor_name}-actor"
                        actor_exists = actor_key in actors

                        # 记录所有已注册的 Actor（用于调试）
                        if actors:
                            print(f"[Worker] 已注册的 Actors: {list(actors.keys())}")
                        else:
                            print("[Worker] 没有已注册的 Actors")

                        return actor_exists
                    except Exception as e:
                        print(f"[Worker] 检查 Actor 失败: {e}")
                        return False

                # 提交任务到 Worker（要求 WIN 资源）
                future = client.submit(
                    check_actor_on_worker,
                    actor_name,
                    resources={"WIN": 1.0},
                )

                # 等待结果（最多 10 秒）
                result = await future.result(timeout=10)

                self._logger.info(f"直接检查 Actor 结果: {actor_name} | available={result}")
                return result

        except Exception as e:
            self._logger.warning(f"直接检查 Actor 失败: {e}")
            return False

    # ========================================================================
    # 状态查询
    # ========================================================================

    def get_status(self) -> Dict[str, Any]:
        """获取完整状态信息"""
        return {
            "state": self._state.value,
            "error": self._error,
            "workers": {
                "count": self.worker_count,
                "pids": list(self._workers.keys()),
            },
            "plugins": {
                name: {
                    "state": p.state.value,
                    "error": p.error,
                }
                for name, p in self._plugins.items()
            },
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime": (
                (datetime.now() - self._started_at).total_seconds()
                if self._started_at and self.is_running
                else None
            ),
        }


# ============================================================================
# 单例和向后兼容
# ============================================================================

_manager: Optional[DaskWorkerManager] = None
_manager_lock = asyncio.Lock()


async def get_dask_worker_manager() -> DaskWorkerManager:
    """获取或创建单例管理器实例"""
    global _manager
    async with _manager_lock:
        if _manager is None:
            _manager = DaskWorkerManager()
        return _manager


# 向后兼容函数


async def ensure_windows_workers() -> bool:
    """
    确保 Windows Dask Workers 已启动

    向后兼容函数，委托给 DaskWorkerManager.start()
    """
    manager = await get_dask_worker_manager()
    return await manager.start()


async def stop_windows_workers() -> None:
    """
    停止 Windows Dask Workers

    向后兼容函数，委托给 DaskWorkerManager.stop()
    """
    manager = await get_dask_worker_manager()
    await manager.stop()


def get_worker_status() -> dict:
    """
    获取 Worker 进程状态

    向后兼容函数，返回传统格式
    """
    global _manager
    if _manager is None:
        return {"running": False, "count": 0, "pids": []}

    status = _manager.get_status()
    return {
        "running": _manager.is_running,
        "count": status["workers"]["count"],
        "pids": status["workers"]["pids"],
    }
