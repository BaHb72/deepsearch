"""
网关组件模块

负责外部交易接口和QMT数据网关
从原unified_components.py拆分而来
"""

import asyncio
from typing import Any, Callable, Dict, Optional, cast

from core.config import get_config
from core.core.runtime.context import get_context
from core.gateway.gateway import Gateway
from core.messaging.bus import CompositeMessageBus

from ..async_component import AsyncComponent
from ..component_state import ComponentLifecycle
from ..interfaces import ComponentType
from ..utils.exceptions import ComponentLifecycleError, error_context
from ..utils.timeout_config import TimeoutCategory, TimeoutManager


class GatewayComponent(AsyncComponent[Gateway]):
    """网关组件 - 外部交易接口"""

    def __init__(self):
        super().__init__("gateway", ComponentType.BUSINESS, "交易网关")
        self._gateway_type = "simulation"  # 默认使用模拟网关
        self._config = None
        self._message_bus: Optional[CompositeMessageBus] = None
        self._timeout_manager = TimeoutManager()

    @property
    def _instance(self) -> Optional[Gateway]:
        return self.resource

    @_instance.setter
    def _instance(self, value: Optional[Gateway]) -> None:
        if value is None:
            self._state_manager.state.clear_resource()
        else:
            self._state_manager.state.set_resource(value)

    @_instance.deleter
    def _instance(self) -> None:
        self._state_manager.state.clear_resource()

    async def stop(self) -> None:
        # 允许在未进入生命周期时释放测试注入的实例
        if self.state.lifecycle == ComponentLifecycle.CREATED and self._instance:
            try:
                await self._do_stop()
            finally:
                del self._instance
            return
        await super().stop()

    async def _do_initialize(self) -> Gateway:
        """初始化网关"""
        with error_context(self.name, "initialize"):
            # 从配置获取网关配置
            config = get_config()
            if config and hasattr(config, "gateway"):
                self._config = getattr(config.gateway, self._gateway_type, {})
            else:
                # 使用默认的模拟网关配置
                self._config = {"type": "simulation"}

            # 使用超时控制创建网关实例
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_INIT)
            message_bus = self._resolve_message_bus()
            gateway_name = "Gateway"
            if isinstance(self._config, dict):
                gateway_name = self._config.get("name", gateway_name)

            try:

                async def _create_gateway():
                    if message_bus is not None:
                        instance = Gateway(None, message_bus=message_bus, gateway_name=gateway_name)
                    else:
                        # 回退到 Gateway 内部的默认消息总线实现
                        instance = Gateway(None, gateway_name=gateway_name)

                    if hasattr(instance, "initialize"):
                        init_result = instance.initialize()
                        if asyncio.iscoroutine(init_result):
                            await init_result

                    self._instance = instance
                    return instance

                return await asyncio.wait_for(_create_gateway(), timeout=timeout)
            except asyncio.TimeoutError:
                raise ComponentLifecycleError(
                    self.name,
                    "initialize",
                    f"Gateway initialization timeout after {timeout} seconds",
                )

    def _resolve_message_bus(self) -> Optional[CompositeMessageBus]:
        """获取已初始化的消息总线组件，若缺失则回退到默认实现。"""
        try:
            context = get_context()
        except RuntimeError:
            self._logger.warning("未检测到全局应用上下文，网关将使用内存消息总线作为后备方案")
            return None

        try:
            message_bus_component = context.get_component("message_bus")
        except ValueError:
            self._logger.warning("应用上下文未注册消息总线组件，使用内存消息总线作为后备方案")
            return None

        message_bus_candidate = getattr(message_bus_component, "resource", None)
        if isinstance(message_bus_candidate, CompositeMessageBus):
            self._message_bus = message_bus_candidate
            return message_bus_candidate

        self._logger.warning("消息总线组件未初始化，将退回使用内存消息总线作为降级方案")
        return None

    async def _do_start(self) -> None:
        """启动网关"""
        with error_context(self.name, "start"):
            instance = self.resource
            if instance and hasattr(instance, "connect"):
                # 使用超时控制进行连接
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_CONNECT)
                try:

                    async def _connect():
                        # Gateway 的 connect 是同步方法
                        instance.connect()

                    await asyncio.wait_for(_connect(), timeout=timeout)
                except asyncio.TimeoutError:
                    raise ComponentLifecycleError(
                        self.name, "start", f"Gateway connection timeout after {timeout} seconds"
                    )

    async def _do_stop(self) -> None:
        """停止网关"""
        with error_context(self.name, "stop"):
            instance = self.resource
            if instance:
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_STOP)
                try:

                    async def _close():
                        if hasattr(instance, "close"):
                            # Gateway 使用 close 方法
                            instance.close()
                        elif hasattr(instance, "disconnect"):
                            instance.disconnect()

                    await asyncio.wait_for(_close(), timeout=timeout)
                    self._instance = None
                except asyncio.TimeoutError:
                    self._logger.warning(f"Gateway stop timeout after {timeout} seconds")

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        info = {
            "gateway_type": self._gateway_type,
            "connected": bool(
                self.resource and getattr(self.resource, "is_connected", lambda: False)()
            ),
        }

        if self._message_bus is not None:
            try:
                info["message_bus_running"] = bool(
                    getattr(self._message_bus, "is_running", lambda: False)()
                )
            except Exception:
                info["message_bus_running"] = False

        return info

    def _health_check(self) -> bool:
        """检查网关健康状态"""
        instance = self.resource
        if not instance:
            return False

        # 检查连接状态
        if hasattr(instance, "is_connected"):
            return bool(cast(Callable[[], Any], getattr(instance, "is_connected"))())

        return True

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


class QMTGatewayComponent(AsyncComponent):
    """QMT网关组件 - 处理QMT数据接收和转发"""

    def __init__(self):
        super().__init__("qmt_gateway", ComponentType.BUSINESS, "QMT网关")
        self._gateway = None
        self._event_engine = None
        self._message_bus = None
        self._config = None
        self._timeout_manager = TimeoutManager()

    async def _do_initialize(self) -> None:
        """初始化QMT网关"""
        with error_context(self.name, "initialize"):
            # 从配置获取QMT设置
            config = get_config()
            qmt_settings = getattr(config, "qmt", None) if config else None
            if qmt_settings is not None:
                if hasattr(qmt_settings, "model_dump"):
                    self._config = cast(Dict[str, Any], qmt_settings.model_dump())
                elif hasattr(qmt_settings, "dict"):
                    self._config = cast(Dict[str, Any], qmt_settings.dict())
                else:
                    self._config = self._build_qmt_config(qmt_settings)
            else:
                self._config = {"enabled": False, "receiver": {"host": "0.0.0.0", "tcp_port": 9999}}
            if not self._config.get("enabled", False):
                self._logger.info("QMT网关已禁用")
                return None

            self._logger.info("QMT网关配置已加载，等待依赖注入...")
            return None

    def _build_qmt_config(self, qmt_settings: Optional[Any]) -> Dict[str, Any]:
        """构建QMT配置字典"""
        receiver = getattr(qmt_settings, "receiver", None) if qmt_settings is not None else None
        security = getattr(qmt_settings, "security", None) if qmt_settings is not None else None
        data_settings = getattr(qmt_settings, "data", None) if qmt_settings is not None else None

        def _as_int(value: Any, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def _as_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        return {
            "enabled": (
                bool(getattr(qmt_settings, "enabled", True)) if qmt_settings is not None else True
            ),
            "receiver": {
                "host": getattr(receiver, "host", "0.0.0.0") or "0.0.0.0",
                "tcp_port": _as_int(getattr(receiver, "tcp_port", 9999), 9999),
                "websocket_port": _as_int(getattr(receiver, "websocket_port", 9998), 9998),
            },
            "security": {
                "enable_auth": (
                    bool(getattr(security, "enable_auth", False)) if security is not None else False
                ),
                "token": getattr(security, "token", "") or "",
            },
            "data": {
                "batch_size": _as_int(getattr(data_settings, "batch_size", 100), 100),
                "flush_interval": _as_float(getattr(data_settings, "flush_interval", 0.1), 0.1),
                "cache_ttl": _as_int(getattr(data_settings, "cache_ttl", 60), 60),
            },
        }

    def set_dependencies(self, event_engine, message_bus):
        """设置依赖（由容器在初始化后调用）"""
        self._event_engine = event_engine
        self._message_bus = message_bus
        self._logger.info("QMT网关依赖已设置")

        # 现在创建网关实例
        if self._config and self._config.get("enabled", False):
            # 使用优化版的 QMTGatewayComponent
            from core.core.components.qmt_gateway_component import (
                QMTGatewayComponent as OptimizedQMTGateway,
            )

            # 创建优化版网关实例
            self._gateway = OptimizedQMTGateway(event_engine, message_bus, self._config)
            self._logger.info("QMT网关实例已创建")

    async def _do_start(self) -> None:
        """启动QMT网关"""
        with error_context(self.name, "start"):
            if not self._config or not self._config.get("enabled", False):
                self._logger.info("QMT网关未启用，跳过启动")
                return

            # 如果依赖还没设置，等待一下
            if not self._gateway and (self._event_engine or self._message_bus):
                self._logger.warning("QMT网关尚未创建，可能依赖未设置")
                # 尝试手动创建
                if self._event_engine and self._message_bus:
                    self.set_dependencies(self._event_engine, self._message_bus)

            if self._gateway:
                # 使用超时控制进行初始化和启动
                init_timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_INIT)
                start_timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_START)

                try:
                    # 先初始化网关
                    if hasattr(self._gateway, "initialize"):
                        await asyncio.wait_for(self._gateway.initialize(), timeout=init_timeout)

                    # 然后启动网关
                    await asyncio.wait_for(self._gateway.start(), timeout=start_timeout)
                    self._logger.info(
                        f"QMT网关已启动，监听端口: {self._config.get('receiver', {}).get('tcp_port', 9999)}"
                    )
                except asyncio.TimeoutError as e:
                    raise ComponentLifecycleError(
                        self.name, "start", f"QMT Gateway start timeout: {e}"
                    )
            else:
                self._logger.error("QMT网关实例未创建，无法启动")

    async def _do_stop(self) -> None:
        """停止QMT网关"""
        with error_context(self.name, "stop"):
            if self._gateway:
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_STOP)
                try:
                    await asyncio.wait_for(self._gateway.stop(), timeout=timeout)
                    self._logger.info("QMT网关已停止")
                except asyncio.TimeoutError:
                    self._logger.warning(f"QMT Gateway stop timeout after {timeout} seconds")

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        if self._gateway and hasattr(self._gateway, "get_status"):
            status_info = self._gateway.get_status()
            if isinstance(status_info, dict):
                return cast(Dict[str, Any], status_info)
            return {}

        return {
            "enabled": self._config.get("enabled", False) if self._config else False,
            "tcp_port": (
                self._config.get("receiver", {}).get("tcp_port", 9999) if self._config else 9999
            ),
            "connected": False,
        }

    def _health_check(self) -> bool:
        """检查QMT网关健康状态"""
        if not self._config or not self._config.get("enabled", False):
            return True  # 禁用状态下认为是健康的

        if not self._gateway:
            return False

        # 检查网关运行状态
        if hasattr(self._gateway, "is_running"):
            return bool(self._gateway.is_running())

        return True

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

    def get_instance(self):
        """获取网关实例（供API使用）"""
        return self._gateway

    def get_statistics(self) -> Dict[str, Any]:
        """获取QMT网关统计信息。"""
        if not self._gateway or not hasattr(self._gateway, "get_statistics"):
            return {}

        gateway = cast(Any, self._gateway)
        try:
            result = gateway.get_statistics()
        except Exception as exc:
            self._logger.warning(f"Failed to fetch QMT statistics: {exc}")
            return {"error": str(exc)}

        if isinstance(result, dict):
            return result
        if result is None:
            return {}
        return {"data": result}
