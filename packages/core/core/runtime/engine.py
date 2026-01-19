"""
重构后的核心引擎模块

使用依赖注入容器管理组件，实现了松耦合的架构。
遵循SOLID原则，特别是依赖倒置原则。

重构说明：
- MainEngine 现在作为门面(Facade)协调各管理器
- BootstrapManager: 容器构建与组件装配
- LifecycleCoordinator: 生命周期协调
- SignalHandler: 信号处理
- WebUIRunner: WebUI 服务器管理
"""

import asyncio
from datetime import datetime
from typing import Any, Coroutine, Dict, List, Literal, Optional, Type, TypeVar, cast

from core.config import get_config
from core.observability import get_logger
from core.observability.logger import logger_manager

from ..interfaces import Component, ComponentType
from ..managers.component_manager import ComponentManager
from ..utils.container import AsyncContainer, ServiceProvider
from ..utils.exceptions import error_context
from .bootstrap import BootstrapManager
from .context import get_context
from .lifecycle import LifecycleCoordinator
from .signal_handler import SignalHandler
from .webui_runner import WebUIRunner

_T = TypeVar("_T")


RuntimeMode = Literal["all", "engine", "webui"]
RuntimeModeInput = Literal["all", "engine", "webui", "full"]

VALID_RUNTIME_MODES: tuple[RuntimeMode, ...] = ("all", "engine", "webui")


def normalize_runtime_mode(mode: RuntimeModeInput) -> RuntimeMode:
    """将外部传入的运行模式标准化为引擎内部可识别的取值。"""
    if mode == "full":
        return "all"
    if mode not in VALID_RUNTIME_MODES:
        raise ValueError(f"Unsupported runtime mode: {mode}")
    return cast(RuntimeMode, mode)


class MainEngine:
    """
    重构后的主引擎

    作为门面(Facade)协调各管理器，实现了：
    1. 松耦合的组件管理
    2. 清晰的依赖关系
    3. 优雅的生命周期管理
    4. 更好的可测试性

    职责委托：
    - BootstrapManager: 容器构建与组件装配
    - LifecycleCoordinator: 生命周期协调（初始化、启停、健康检查）
    - SignalHandler: 系统信号处理
    - WebUIRunner: WebUI 服务器管理
    """

    def __init__(
        self,
        container: Optional[AsyncContainer] = None,
        mode: Optional[RuntimeModeInput] = None,
    ) -> None:
        """
        初始化主引擎

        Args:
            container: 依赖注入容器，如果不提供则创建默认容器
            mode: 运行模式
        """
        # 基本属性
        self._logger = get_logger(f"deepsearch.{self.__class__.__name__}")
        self._running = False
        self._stop_event = asyncio.Event()
        self._components: Dict[str, Component] = {}
        self._component_manager: Optional[ComponentManager] = None
        self._provider: Optional[ServiceProvider] = None

        # 解析运行模式
        runtime_mode_input = self._resolve_runtime_mode(mode)
        self._mode: RuntimeMode = normalize_runtime_mode(runtime_mode_input)

        # 初始化管理器
        self._bootstrap = BootstrapManager(self._mode)
        self._lifecycle = LifecycleCoordinator(self._mode)
        self._signal_handler = SignalHandler()
        self._webui_runner = WebUIRunner()

        # 异步任务管理
        self._tasks: List[asyncio.Task] = []

        # 创建容器
        self._container = container or self._bootstrap.create_container()

    def _resolve_runtime_mode(self, explicit_mode: Optional[RuntimeModeInput]) -> RuntimeModeInput:
        """根据显式参数或配置解析运行模式。"""
        if explicit_mode is not None:
            return explicit_mode

        fallback: RuntimeModeInput = "full"
        try:
            config = get_config()
        except Exception as exc:
            self._logger.debug(f"加载配置以确定运行模式失败: {exc}")
            return fallback

        runtime_config = getattr(config, "runtime", None)
        config_mode = getattr(runtime_config, "mode", None) if runtime_config else None

        if isinstance(config_mode, str):
            if config_mode == "full":
                return "full"
            if config_mode in VALID_RUNTIME_MODES:
                return cast(RuntimeModeInput, config_mode)
            self._logger.warning(
                f"配置中的运行模式 '{config_mode}' 不受支持，将回退到 '{fallback}'"
            )

        return fallback

    @property
    def mode(self) -> RuntimeMode:
        """返回标准化后的运行模式。"""
        return self._mode

    def _require_provider(self) -> ServiceProvider:
        """Return the ServiceProvider or raise if it is missing."""
        if self._provider is None:
            raise RuntimeError("Service provider is not initialized")
        return self._provider

    # ==================== 生命周期管理 ====================

    async def initialize_async(self) -> None:
        """异步初始化引擎"""
        with error_context("MainEngine", "initialize"):
            # 构建服务提供者
            provider = self._container.build()
            self._provider = provider

            # 加载组件
            self._components = self._bootstrap.load_components(provider, self)
            self._component_manager = get_context().get_component_manager()

            # 设置组件依赖
            await self._bootstrap.setup_dependencies(self._components)

            # 初始化所有组件
            await self._lifecycle.initialize_all(self, self._container, provider, self._components)

    async def start(self) -> None:
        """启动引擎和所有组件"""
        with error_context("MainEngine", "start"):
            if self._running:
                self._logger.warning("Engine is already running")
                return

            self._logger.info("Starting DeepSearch System...")

            # 设置信号处理
            self._signal_handler.setup(self._signal_callback, self._stop_event)

            # 分阶段启动
            await self._lifecycle.start_phased(
                self._container, self._require_provider(), self._components
            )

            # 启动 WebUI（如果需要）
            if self._mode in ["all", "webui"]:
                await self._start_webui()

            self._running = True
            self._logger.info(f"[OK] DeepSearch System started in {self._mode} mode")

    async def _start_webui(self) -> None:
        """启动 WebUI 服务器"""
        try:
            config = get_config()
            task = await self._webui_runner.start(self, config.webui)
            task.add_done_callback(self._handle_task_exception)
            self._tasks.append(task)
        except Exception as e:
            self._logger.error(f"Failed to start WebUI: {e}")

    async def _start_phased_async(
        self,
        include_business: bool = True,
        include_webui: bool = True,
        include_frontend: bool = True,
    ) -> None:
        """
        分阶段异步启动引擎

        提供细粒度控制，允许选择性启动不同组件组合。

        Args:
            include_business: 是否启动业务组件
            include_webui: 是否启动 WebUI 后端服务
            include_frontend: 是否启动前端（预留参数，当前未使用）
        """
        with error_context("MainEngine", "_start_phased_async"):
            if self._running:
                self._logger.warning("Engine is already running")
                return

            self._logger.info("Starting DeepSearch System (phased)...")

            # 设置信号处理
            self._signal_handler.setup(self._signal_callback, self._stop_event)

            # 启动基础设施（始终需要）
            await self._lifecycle.start_phased(
                self._container, self._require_provider(), self._components
            )

            # 根据参数启动业务组件
            if include_business:
                await self.start_business_components_async()

            # 根据参数启动 WebUI
            if include_webui:
                await self._start_webui()

            self._running = True
            self._logger.info("[OK] DeepSearch System started (phased mode)")

    async def run(self) -> None:
        """运行引擎直到收到停止信号"""
        if not self._running:
            await self.start()

        try:
            await self._stop_event.wait()
        except KeyboardInterrupt:
            self._logger.info("Received keyboard interrupt")
        finally:
            await self.stop_async()

    async def stop_async(self) -> None:
        """异步停止引擎和所有组件"""
        with error_context("MainEngine", "stop"):
            if not self._running:
                self._logger.warning("Engine is not running")
                return

            # 停止 WebUI
            await self._webui_runner.stop()

            # 分阶段停止
            await self._lifecycle.stop_phased(
                self._container, self._provider, self._components, self._tasks
            )

            # 恢复信号处理
            self._signal_handler.restore()

            self._running = False
            self._tasks.clear()

    async def _signal_callback(self) -> None:
        """信号回调"""
        self._logger.info("Received shutdown signal")
        self._stop_event.set()

    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """处理任务异常"""
        try:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                self._logger.error(f"Task {task.get_name()} failed with exception: {exc}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error handling task exception: {e}")

    # ==================== 组件管理 ====================

    def _ensure_component_manager(self) -> ComponentManager:
        """确保组件管理器已经初始化."""
        if self._component_manager is None:
            raise RuntimeError("Component manager is not initialized")
        return self._component_manager

    def get_component_manager(self) -> ComponentManager:
        """获取组件管理器."""
        return self._ensure_component_manager()

    async def start_component_async(self, name: str) -> None:
        """异步启动指定组件."""
        manager = self._ensure_component_manager()
        await manager.start_component(name)

    async def stop_component_async(self, name: str) -> None:
        """异步停止指定组件."""
        manager = self._ensure_component_manager()
        await manager.stop_component(name)

    async def restart_component_async(self, name: str) -> None:
        """异步重启指定组件."""
        await self.stop_component_async(name)
        await self.start_component_async(name)

    async def start_business_components_async(self) -> None:
        """异步启动所有业务组件."""
        manager = self._ensure_component_manager()
        await manager.start_all(ComponentType.BUSINESS)

    async def stop_business_components_async(self) -> None:
        """异步停止所有业务组件."""
        manager = self._ensure_component_manager()
        await manager.stop_all(ComponentType.BUSINESS)

    # ==================== 组件访问 ====================

    def get_component(self, component_type: type[Any]) -> Optional[Component]:
        """通过类型获取组件"""
        # 优先从 _components 字典查找（支持新 DI 容器）
        for component in self._components.values():
            if isinstance(component, component_type):
                return component

        # Fallback：使用旧的 provider API（向后兼容）
        provider = self._provider
        if provider is None:
            return None
        try:
            result: Optional[Component] = provider.get_service(cast(Type[Any], component_type))
            return result
        except Exception:
            return None

    def get_component_by_name(self, name: str) -> Optional[Component]:
        """通过名称获取组件"""
        return self._components.get(name)

    def get_all_components(self) -> Dict[str, Component]:
        """获取所有组件"""
        return self._components.copy()

    # ==================== 状态和监控 ====================

    def is_running(self) -> bool:
        """检查引擎是否正在运行"""
        return self._running

    def is_infrastructure_running(self) -> bool:
        """基础设施是否处于运行状态."""
        return self._running

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        start_time = self._lifecycle.start_time
        components_info: Dict[str, Any] = {}
        status: Dict[str, Any] = {
            "running": self._running,
            "mode": self._mode,
            "start_time": start_time.isoformat() if start_time else None,
            "uptime": (datetime.now() - start_time).total_seconds() if start_time else 0,
            "webui_port": self._webui_runner.actual_port,
            "components": components_info,
        }

        for name, component in self._components.items():
            components_info[name] = {
                "status": component.status.value,
                "type": component.component_type.value,
                "info": component.get_status_info(),
            }

        return status

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        components_health: Dict[str, Any] = {}
        health: Dict[str, Any] = {
            "healthy": True,
            "timestamp": datetime.now().isoformat(),
            "components": components_health,
        }

        health_manager = self._lifecycle.health_check_manager
        if health_manager:
            last_results = health_manager.get_last_results()
            overall_status = health_manager.get_overall_status()

            health["healthy"] = overall_status.value == "healthy"
            health["overall_status"] = overall_status.value

            for name, result in last_results.items():
                components_health[name] = {
                    "healthy": result.status.value == "healthy",
                    "status": result.status.value,
                    "message": result.message,
                    "last_check": result.timestamp.isoformat(),
                }
        else:
            for name, component in self._components.items():
                component_health = component.health_check()
                components_health[name] = {
                    "healthy": component_health,
                    "status": component.status.value,
                }
                if not component_health:
                    health["healthy"] = False

        return health

    async def health_check_async(self) -> Dict[str, Any]:
        """异步健康检查"""
        health_manager = self._lifecycle.health_check_manager
        if health_manager:
            report = await health_manager.get_health_report()
            return cast(Dict[str, Any], report)
        else:
            return self.health_check()

    # ==================== 兼容性方法 ====================

    def _run_coroutine_from_sync(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """在同步环境中执行协程；异步环境请直接 await."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError(
            "Operation requires awaiting in asynchronous context; use the '*_async' variant."
        )

    def initialize(self) -> None:
        """同步初始化方法（向后兼容）"""
        self._run_coroutine_from_sync(self.initialize_async())

    def start_component(self, name: str) -> None:
        """同步启动指定组件（异步环境请使用 async 版本）。"""
        self._run_coroutine_from_sync(self.start_component_async(name))

    def stop_component(self, name: str) -> None:
        """同步停止指定组件（异步环境请使用 async 版本）。"""
        self._run_coroutine_from_sync(self.stop_component_async(name))

    def restart_component(self, name: str) -> None:
        """同步重启指定组件（异步环境请使用 async 版本）。"""
        self._run_coroutine_from_sync(self.restart_component_async(name))

    def start_business_components(self) -> None:
        """同步启动所有业务组件（异步环境请使用 async 版本）。"""
        self._run_coroutine_from_sync(self.start_business_components_async())

    def stop_business_components(self) -> None:
        """同步停止所有业务组件（异步环境请使用 async 版本）。"""
        self._run_coroutine_from_sync(self.stop_business_components_async())

    def stop(self) -> None:
        """同步停止方法（向后兼容）"""
        from concurrent.futures import TimeoutError

        try:
            loop = asyncio.get_running_loop()
            future = asyncio.run_coroutine_threadsafe(self.stop_async(), loop)
            try:
                future.result(timeout=30)
            except TimeoutError:
                self._logger.error("Stop operation timed out after 30 seconds")
        except RuntimeError:
            asyncio.run(self.stop_async())

    async def start_infrastructure_async(self) -> None:
        """异步启动基础设施组件。"""
        await self._lifecycle.start_phased(
            self._container, self._require_provider(), self._components
        )

    def start_infrastructure(self) -> None:
        """同步启动基础设施组件。"""
        self._run_coroutine_from_sync(self.start_infrastructure_async())

    def start_phased(
        self,
        include_business: bool = True,
        include_webui: bool = True,
        include_frontend: bool = True,
    ) -> None:
        """分阶段启动引擎（同步包装器，向后兼容）"""
        self._run_coroutine_from_sync(
            self._start_phased_async(include_business, include_webui, include_frontend)
        )


# ==================== 工厂函数 ====================


def create_engine(
    mode: Optional[str] = None, container: Optional[AsyncContainer] = None
) -> MainEngine:
    """
    创建引擎实例

    Args:
        mode: 运行模式 (all, engine, webui)，默认为配置文件中的值
        container: 自定义依赖注入容器

    Returns:
        MainEngine: 引擎实例
    """
    runtime_mode_input = cast(Optional[RuntimeModeInput], mode)
    return MainEngine(container=container, mode=runtime_mode_input)


async def run_engine(
    mode: Optional[RuntimeModeInput] = None,
    container: Optional[AsyncContainer] = None,
) -> None:
    """
    运行引擎

    Args:
        mode: 运行模式
        container: 自定义依赖注入容器
    """
    engine = create_engine(mode, container)

    try:
        await engine.initialize_async()
        await engine.run()
    except Exception as e:
        logger_manager.get_logger(__name__).error(f"Engine failed: {e}")
        raise
    finally:
        if engine.is_running():
            await engine.stop_async()
