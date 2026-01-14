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
import os
import signal
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    pass


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
    VALID_TRANSITIONS: ClassVar[Dict[DaskWorkerState, List[DaskWorkerState]]] = {
        DaskWorkerState.IDLE: [DaskWorkerState.CHECKING, DaskWorkerState.FAILED],
        DaskWorkerState.CHECKING: [DaskWorkerState.STARTING, DaskWorkerState.FAILED],
        DaskWorkerState.STARTING: [DaskWorkerState.REGISTERING, DaskWorkerState.FAILED],
        DaskWorkerState.REGISTERING: [DaskWorkerState.RUNNING, DaskWorkerState.FAILED],
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

            self._config = DaskConfig(
                scheduler_address=scheduler_address,
                enabled=True,
                auto_start=True,
                num_workers=getattr(windows_workers, "num_workers", 2),
                threads_per_worker=getattr(windows_workers, "threads_per_worker", 2),
                memory_limit=getattr(windows_workers, "memory_limit", "4GB"),
                name_prefix=getattr(windows_workers, "name_prefix", "windows-worker"),
                resources=resources_dict,
            )

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
    def _get_host_address_for_docker() -> str:
        """获取 Docker 容器可访问的主机地址"""
        return "host.docker.internal"

    def _find_available_ports(
        self, count: int, start_port: int = 58200, max_range: int = 100
    ) -> list[int]:
        """
        查找 N 个可用端口

        Args:
            count: 需要的端口数量
            start_port: 起始端口
            max_range: 搜索范围

        Returns:
            可用端口列表

        Raises:
            RuntimeError: 无法找到足够的可用端口
        """
        from core.utils.system.port_checker import PortChecker

        available_ports: list[int] = []
        occupied_ports: list[int] = []

        for port in range(start_port, start_port + max_range):
            if len(available_ports) >= count:
                break

            if PortChecker.is_port_available(port, host="0.0.0.0"):
                available_ports.append(port)
            else:
                occupied_ports.append(port)
                self._logger.debug(f"端口 {port} 已被占用，跳过")

        if len(available_ports) < count:
            raise RuntimeError(
                f"无法在范围 {start_port}-{start_port + max_range} 内找到 {count} 个可用端口。"
                f"已占用端口: {occupied_ports}"
            )

        self._logger.info(f"找到可用端口: {available_ports}")
        return available_ports

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

    async def _start_workers(self) -> bool:
        """启动 Worker 进程"""
        if not self._config:
            return False

        async with self._process_lock:
            # 检查是否已有运行中的 Worker
            running = [w for w in self._workers.values() if w.process.poll() is None]
            if running:
                self._logger.debug(f"已有 {len(running)} 个 Worker 在运行")
                return True

            # 清空旧记录
            self._workers.clear()

            host_address = self._get_host_address_for_docker()

            # 动态查找可用端口
            try:
                worker_ports = self._find_available_ports(
                    count=self._config.num_workers,
                    start_port=getattr(self._config, "port_range_start", 58200),
                    max_range=100,
                )
            except RuntimeError as e:
                self._logger.error(f"端口发现失败: {e}")
                return False

            for i, worker_port in enumerate(worker_ports):
                worker_name = f"{self._config.name_prefix}-{i}"

                cmd = [
                    "uv",
                    "run",
                    "dask",
                    "worker",
                    f"tcp://{self._parsed_host}:{self._parsed_port}",
                    "--nthreads",
                    str(self._config.threads_per_worker),
                    "--memory-limit",
                    self._config.memory_limit,
                    "--no-nanny",  # 直接启动 Worker，不使用 Nanny 进程
                ]

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

                # 构建环境变量（包含资源标签）
                env = os.environ.copy()
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
                    await self._cleanup_workers()
                    return False

            # 等待连接
            await asyncio.sleep(10)

            # 检查进程状态
            failed = []
            for pid, info in self._workers.items():
                if info.process.poll() is not None:
                    self._logger.error(f"Worker {info.name} 启动后退出")
                    failed.append(pid)

            if failed:
                await self._cleanup_workers()
                return False

            pids = list(self._workers.keys())
            self._logger.info(f"Workers 已启动 ({len(pids)} 个, PIDs: {pids})")
            return True

    async def _stop_workers(self, timeout: float) -> None:
        """停止所有 Worker 进程"""
        async with self._process_lock:
            running = [info for info in self._workers.values() if info.process.poll() is None]

            if not running:
                self._workers.clear()
                return

            self._logger.info(f"正在停止 {len(running)} 个 Workers...")

            # 优雅关闭
            for info in running:
                try:
                    if sys.platform == "win32":
                        info.process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        info.process.terminate()
                except Exception as e:
                    self._logger.debug(f"发送终止信号失败: {e}")

            # 等待退出
            for info in running:
                try:
                    info.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self._logger.warning(f"Worker {info.name} 未响应，强制终止")
                    info.process.kill()
                    info.process.wait(timeout=5)
                finally:
                    # 关闭管道流，释放日志转发线程的阻塞
                    self._close_process_streams(info.process)

            self._workers.clear()
            self._logger.info("Workers 已全部停止")

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
        """注册所有 Plugins"""
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
                    recovery_timeout = 60

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
                                    recovery_timeout = getattr(
                                        provider_config, "recovery_timeout", 60
                                    )

                    # 使用 Pydantic 配置模型（修复参数签名不匹配）
                    plugin_config = MiniQMTPluginConfig(
                        redis_url=redis_url,
                        only_on_windows=True,
                        cache_ttl=cache_ttl,
                        failure_threshold=failure_threshold,
                        recovery_timeout=recovery_timeout,
                    )
                    plugin = MiniQMTWorkerPlugin(plugin_config)

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
