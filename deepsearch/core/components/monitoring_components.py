"""
监控组件模块

负责系统监控和指标收集
从原unified_components.py拆分而来
"""

import asyncio
from typing import Any, Dict, Optional

from deepsearch.event.engine.engine import EventEngine

from ..async_component import AsyncComponent
from ..component_state import ComponentLifecycle
from ..interfaces import ComponentType
from ..utils.exceptions import ComponentLifecycleError, error_context
from ..utils.timeout_config import TimeoutCategory, TimeoutManager


class MonitorComponent(AsyncComponent):
    """监控组件 - 系统监控和指标收集"""

    def __init__(self):
        super().__init__("monitor", ComponentType.SUPPORTING, "监控器")
        self._event_engine = None
        self._timeout_manager = TimeoutManager()

    @property
    def _instance(self):
        """兼容旧版直接访问内部实例的属性"""
        return self.resource

    @_instance.setter
    def _instance(self, value):
        if value is None:
            self.state.clear_resource()
        else:
            self.state.set_resource(value)

    @_instance.deleter
    def _instance(self):
        self.state.clear_resource()

    async def stop(self) -> None:
        """覆写停止逻辑，兼容旧版直接赋值实例的场景"""
        if self.state.lifecycle == ComponentLifecycle.CREATED and self._instance:
            try:
                await self._stop()
            finally:
                del self._instance
            return
        await super().stop()

    def set_event_engine(self, event_engine: EventEngine):
        """设置事件引擎（用于依赖注入）"""
        self._event_engine = event_engine

    async def _initialize(self) -> None:
        """初始化监控器"""
        with error_context(self.name, "initialize"):
            if not self._event_engine:
                raise ComponentLifecycleError(self.name, "initialize", "Event engine not provided")

            # 延迟导入以避免循环导入
            from deepsearch.observability.monitoring.event_monitor import EventSystemMonitor

            # 使用超时控制进行初始化
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_INIT)
            try:

                async def _init():
                    instance = EventSystemMonitor(self._event_engine)
                    self._instance = instance

                await asyncio.wait_for(_init(), timeout=timeout)
            except asyncio.TimeoutError:
                raise ComponentLifecycleError(
                    self.name, "initialize", f"Initialization timeout after {timeout} seconds"
                )

    async def _start(self) -> None:
        """启动监控器"""
        with error_context(self.name, "start"):
            instance = self._instance
            if instance:
                # 使用超时控制进行启动
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_START)
                try:

                    async def _start_monitor():
                        instance.start()

                    await asyncio.wait_for(_start_monitor(), timeout=timeout)
                except asyncio.TimeoutError:
                    raise ComponentLifecycleError(
                        self.name, "start", f"Start timeout after {timeout} seconds"
                    )

    async def _stop(self) -> None:
        """停止监控器"""
        with error_context(self.name, "stop"):
            instance = self._instance
            if instance:
                # 使用超时控制进行停止
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_STOP)
                try:

                    async def _stop_monitor():
                        instance.stop()

                    await asyncio.wait_for(_stop_monitor(), timeout=timeout)
                except asyncio.TimeoutError:
                    self._logger.warning(f"Stop timeout after {timeout} seconds, forcing stop")
                    # 强制停止
                    if hasattr(instance, "_running"):
                        instance._running = False

    async def _do_initialize(self) -> Optional[Any]:
        """桥接 AsyncComponent 抽象接口，保持与旧版兼容"""
        await self._initialize()
        return self._instance

    async def _do_start(self) -> None:
        """桥接 AsyncComponent 抽象接口，保持与旧版兼容"""
        await self._start()

    async def _do_stop(self) -> None:
        """桥接 AsyncComponent 抽象接口，保持与旧版兼容"""
        await self._stop()

    def _health_check(self) -> bool:
        """检查监控器健康状态"""
        try:
            instance = self._instance
            if not instance:
                return False

            # 安全检查 is_running 方法是否存在
            if not hasattr(instance, "is_running"):
                # 如果没有 is_running 方法，检查 _running 属性
                if hasattr(instance, "_running"):
                    return bool(instance._running)
                # 如果实例存在但没有状态标记，认为是运行中
                return True

            # 调用 is_running 方法并确保返回布尔值
            return bool(instance.is_running())
        except Exception as e:
            self._logger.error(f"健康检查失败: {e}")
            return False

    async def health_check_async(self) -> bool:
        """异步健康检查（带超时）"""
        timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_HEALTH)
        try:

            async def _check():
                return self._health_check()

            return await asyncio.wait_for(_check(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning(f"Health check timeout after {timeout} seconds")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        instance = self._instance
        if instance and hasattr(instance, "get_metrics"):
            metrics = instance.get_metrics()
            if isinstance(metrics, dict):
                return metrics
        return {}

    def _get_component_statistics(self) -> Dict[str, Any]:
        """获取监控器的统计信息"""
        instance = self._instance
        if not instance:
            return {}

        # 获取监控器的核心指标
        summary = instance.get_summary() if hasattr(instance, "get_summary") else {}

        return {
            "monitoring_active": hasattr(instance, "_running") and instance._running,
            "events_monitored": len(summary.get("events", {})),
            "health_status": summary.get("health", {}).get("status", "unknown"),
            "total_events": (
                sum(metrics.get("total", 0) for metrics in summary.get("events", {}).values())
                if "events" in summary
                else 0
            ),
        }

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        info = {
            "monitoring_enabled": True,
            "event_engine_connected": self._event_engine is not None,
        }

        # 添加统计信息
        stats = self._get_component_statistics()
        if stats:
            info.update(stats)

        return info

    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """获取实时监控指标（带超时）"""
        timeout = self._timeout_manager.get_timeout(TimeoutCategory.NETWORK_REALTIME)
        try:

            async def _get_metrics():
                instance = self._instance
                if not instance:
                    return {}

                metrics = {}

                # 获取基础指标
                if hasattr(instance, "get_metrics"):
                    metrics["base"] = instance.get_metrics()

                # 获取详细摘要
                if hasattr(instance, "get_summary"):
                    metrics["summary"] = instance.get_summary()

                # 获取性能指标
                if hasattr(instance, "get_performance_metrics"):
                    metrics["performance"] = instance.get_performance_metrics()

                return metrics

            return await asyncio.wait_for(_get_metrics(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning(f"Get real-time metrics timeout after {timeout} seconds")
            return {"error": "Timeout getting metrics"}

    def get_instance(self) -> Optional[Any]:
        """获取内部监控实例"""
        return self._instance
