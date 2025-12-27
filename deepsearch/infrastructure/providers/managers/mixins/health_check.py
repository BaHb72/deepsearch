"""
健康检查混入模块

提供数据源健康检查能力。
从 enhanced_manager.py 提取并优化。

功能：
- 定期检查各数据源的健康状态
- 记录健康检查历史
- 支持自定义健康检查逻辑
- 与熔断器集成

使用方法:
    class MyManager(BaseDataSourceManager, HealthCheckMixin):
        async def initialize(self):
            await super().initialize()
            self._init_health_check()

        async def start_monitoring(self):
            await self.start_health_check_loop(interval=60)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Protocol

from loguru import logger


class _ProviderProtocol(Protocol):
    """提供者协议（用于健康检查）"""

    async def initialize(self) -> None: ...

    def is_healthy(self) -> bool: ...


@dataclass
class HealthCheckResult:
    """健康检查结果

    Attributes:
        source: 数据源标识
        healthy: 是否健康
        latency_ms: 检查延迟（毫秒）
        timestamp: 检查时间戳
        message: 附加信息
        error: 错误信息（如果有）
    """

    source: str
    healthy: bool
    latency_ms: float
    timestamp: float = field(default_factory=time.time)
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class HealthCheckConfig:
    """健康检查配置

    Attributes:
        check_interval: 检查间隔（秒）
        timeout: 单次检查超时（秒）
        failure_threshold: 连续失败多少次认为不健康
        history_size: 保留多少条历史记录
    """

    check_interval: float = 60.0
    timeout: float = 10.0
    failure_threshold: int = 3
    history_size: int = 100


class HealthCheckMixin:
    """健康检查混入

    为数据源管理器提供健康检查能力。

    Attributes:
        _health_status: 各数据源的健康状态
        _health_history: 健康检查历史记录
        _health_config: 健康检查配置
        _health_check_task: 后台检查任务
        _custom_health_checks: 自定义健康检查函数

    Example:
        >>> class Manager(HealthCheckMixin):
        ...     pass
        >>> mgr = Manager()
        >>> mgr._init_health_check(check_interval=30)
        >>> await mgr.check_health_all()
    """

    # 类属性声明
    _health_status: Dict[str, Dict[str, Any]]
    _health_history: Dict[str, List[HealthCheckResult]]
    _health_config: HealthCheckConfig
    _health_check_task: Optional[asyncio.Task]
    _custom_health_checks: Dict[str, Callable[..., Coroutine[Any, Any, bool]]]

    def _init_health_check(
        self,
        check_interval: float = 60.0,
        timeout: float = 10.0,
        failure_threshold: int = 3,
        history_size: int = 100,
    ) -> None:
        """初始化健康检查配置

        Args:
            check_interval: 检查间隔（秒）
            timeout: 单次检查超时（秒）
            failure_threshold: 连续失败多少次认为不健康
            history_size: 保留多少条历史记录
        """
        self._health_status = {}
        self._health_history = {}
        self._health_config = HealthCheckConfig(
            check_interval=check_interval,
            timeout=timeout,
            failure_threshold=failure_threshold,
            history_size=history_size,
        )
        self._health_check_task = None
        self._custom_health_checks = {}

        logger.info(
            f"✅ 健康检查初始化成功: 检查间隔={check_interval}s, "
            f"超时={timeout}s, 失败阈值={failure_threshold}"
        )

    def register_health_check(
        self,
        source_name: str,
        check_func: Callable[..., Coroutine[Any, Any, bool]],
    ) -> None:
        """注册自定义健康检查函数

        Args:
            source_name: 数据源名称
            check_func: 异步健康检查函数，返回布尔值

        Example:
            >>> async def check_my_source():
            ...     return await ping_server()
            >>> mgr.register_health_check("my_source", check_my_source)
        """
        if not hasattr(self, "_custom_health_checks"):
            self._custom_health_checks = {}
        self._custom_health_checks[source_name] = check_func

    async def check_health(self, source_name: str, provider: Any) -> HealthCheckResult:
        """检查单个数据源的健康状态

        Args:
            source_name: 数据源名称
            provider: 数据提供者实例

        Returns:
            健康检查结果
        """
        if not hasattr(self, "_health_config"):
            self._health_config = HealthCheckConfig()

        start_time = time.time()
        healthy = False
        error_msg: Optional[str] = None
        message: Optional[str] = None

        try:
            # 1. 尝试使用自定义健康检查
            if hasattr(self, "_custom_health_checks") and source_name in self._custom_health_checks:
                check_func = self._custom_health_checks[source_name]
                healthy = await asyncio.wait_for(
                    check_func(),
                    timeout=self._health_config.timeout,
                )
                message = "自定义健康检查"

            # 2. 尝试调用提供者的 is_healthy 方法
            elif hasattr(provider, "is_healthy"):
                if asyncio.iscoroutinefunction(provider.is_healthy):
                    healthy = await asyncio.wait_for(
                        provider.is_healthy(),
                        timeout=self._health_config.timeout,
                    )
                else:
                    healthy = provider.is_healthy()
                message = "is_healthy 检查"

            # 3. 尝试调用提供者的 ping 方法
            elif hasattr(provider, "ping"):
                if asyncio.iscoroutinefunction(provider.ping):
                    await asyncio.wait_for(
                        provider.ping(),
                        timeout=self._health_config.timeout,
                    )
                else:
                    provider.ping()
                healthy = True
                message = "ping 检查"

            # 4. 检查提供者是否有 status 属性
            elif hasattr(provider, "status"):
                status = provider.status
                healthy = status in ("running", "connected", "healthy", "active")
                message = f"status={status}"

            else:
                # 没有健康检查方法，假设健康
                healthy = True
                message = "无健康检查方法，默认健康"

        except asyncio.TimeoutError:
            healthy = False
            error_msg = f"健康检查超时 ({self._health_config.timeout}s)"
            logger.warning(f"数据源 {source_name} {error_msg}")

        except Exception as e:
            healthy = False
            error_msg = str(e)
            logger.warning(f"数据源 {source_name} 健康检查失败: {e}")

        latency_ms = (time.time() - start_time) * 1000

        result = HealthCheckResult(
            source=source_name,
            healthy=healthy,
            latency_ms=latency_ms,
            message=message,
            error=error_msg,
        )

        # 更新状态和历史
        self._update_health_status(source_name, result)
        self._add_to_history(source_name, result)

        return result

    async def check_health_all(self) -> Dict[str, HealthCheckResult]:
        """检查所有数据源的健康状态

        Returns:
            各数据源的健康检查结果

        Note:
            此方法需要管理器有 providers 属性。
        """
        results: Dict[str, HealthCheckResult] = {}

        # 获取 providers（假设管理器有此属性）
        providers = getattr(self, "providers", {})

        for source_type, provider in providers.items():
            source_name = source_type.value if hasattr(source_type, "value") else str(source_type)

            try:
                result = await self.check_health(source_name, provider)
                results[source_name] = result
            except Exception as e:
                logger.error(f"检查数据源 {source_name} 健康状态时发生错误: {e}")
                results[source_name] = HealthCheckResult(
                    source=source_name,
                    healthy=False,
                    latency_ms=0,
                    error=str(e),
                )

        # 打印检查摘要
        healthy_count = sum(1 for r in results.values() if r.healthy)
        total_count = len(results)
        logger.info(f"🏥 健康检查完成: {healthy_count}/{total_count} 个数据源健康")

        return results

    def _update_health_status(self, source_name: str, result: HealthCheckResult) -> None:
        """更新健康状态"""
        if not hasattr(self, "_health_status"):
            self._health_status = {}

        if source_name not in self._health_status:
            self._health_status[source_name] = {
                "healthy": result.healthy,
                "consecutive_failures": 0,
                "last_check": result.timestamp,
                "last_latency_ms": result.latency_ms,
            }

        status = self._health_status[source_name]
        status["healthy"] = result.healthy
        status["last_check"] = result.timestamp
        status["last_latency_ms"] = result.latency_ms

        if result.healthy:
            status["consecutive_failures"] = 0
        else:
            status["consecutive_failures"] = status.get("consecutive_failures", 0) + 1

    def _add_to_history(self, source_name: str, result: HealthCheckResult) -> None:
        """添加到历史记录"""
        if not hasattr(self, "_health_history"):
            self._health_history = {}
        if not hasattr(self, "_health_config"):
            self._health_config = HealthCheckConfig()

        if source_name not in self._health_history:
            self._health_history[source_name] = []

        history = self._health_history[source_name]
        history.append(result)

        # 保持历史记录大小
        if len(history) > self._health_config.history_size:
            self._health_history[source_name] = history[-self._health_config.history_size :]

    async def start_health_check_loop(self) -> None:
        """启动后台健康检查循环

        Note:
            此方法会创建一个后台任务，定期执行健康检查。
            使用 stop_health_check_loop() 停止。
        """
        if not hasattr(self, "_health_config"):
            self._health_config = HealthCheckConfig()

        if hasattr(self, "_health_check_task") and self._health_check_task:
            logger.warning("健康检查循环已在运行")
            return

        async def _loop():
            while True:
                try:
                    await self.check_health_all()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"健康检查循环发生错误: {e}")

                await asyncio.sleep(self._health_config.check_interval)

        self._health_check_task = asyncio.create_task(_loop())
        logger.info(f"🔄 健康检查循环已启动，间隔: {self._health_config.check_interval}s")

    def stop_health_check_loop(self) -> None:
        """停止后台健康检查循环"""
        if hasattr(self, "_health_check_task") and self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
            logger.info("健康检查循环已停止")

    def is_healthy(self, source_name: str) -> bool:
        """检查数据源是否健康

        Args:
            source_name: 数据源名称

        Returns:
            是否健康
        """
        if not hasattr(self, "_health_status"):
            return True  # 未初始化时假设健康

        status = self._health_status.get(source_name)
        if not status:
            return True  # 未检查过假设健康

        return bool(status.get("healthy", True))

    def get_health_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源的健康状态

        Returns:
            各数据源的健康状态信息
        """
        if not hasattr(self, "_health_status"):
            return {}
        return dict(self._health_status)

    def get_health_history(
        self,
        source_name: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """获取健康检查历史

        Args:
            source_name: 指定数据源，None 表示所有
            limit: 每个数据源返回的最大记录数

        Returns:
            健康检查历史记录
        """
        if not hasattr(self, "_health_history"):
            return {}

        result: Dict[str, List[Dict[str, Any]]] = {}

        sources = [source_name] if source_name else list(self._health_history.keys())

        for src in sources:
            if src in self._health_history:
                history = self._health_history[src][-limit:]
                result[src] = [
                    {
                        "healthy": r.healthy,
                        "latency_ms": r.latency_ms,
                        "timestamp": r.timestamp,
                        "message": r.message,
                        "error": r.error,
                    }
                    for r in history
                ]

        return result


__all__ = [
    "HealthCheckMixin",
    "HealthCheckResult",
    "HealthCheckConfig",
]
