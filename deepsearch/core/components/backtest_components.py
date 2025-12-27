"""
回测组件模块

负责策略回测引擎
从原unified_components.py拆分而来
"""

import asyncio
import inspect
from typing import Any, Dict, Optional, cast

from deepsearch.config import get_config

from ..async_component import AsyncComponent
from ..interfaces import ComponentType
from ..utils.exceptions import ComponentLifecycleError, error_context
from ..utils.timeout_config import TimeoutCategory, TimeoutManager


class BacktestComponent(AsyncComponent):
    """回测组件 - 策略回测引擎"""

    def __init__(self):
        super().__init__("backtest", ComponentType.BUSINESS, "回测引擎")
        self._backtest_instance: Optional[Any] = None
        self._event_engine: Optional[Any] = None
        self._message_bus: Optional[Any] = None
        self._data_provider: Optional[Any] = None
        self._timeout_manager = TimeoutManager()

        # 获取配置
        config = get_config()
        raw_enabled = config.backtest.enabled if config and hasattr(config, "backtest") else True
        self._enabled: bool = bool(raw_enabled)

    def set_dependencies(self, event_engine=None, message_bus=None, data_provider=None):
        """设置组件依赖"""
        self._event_engine = event_engine
        self._message_bus = message_bus
        self._data_provider = data_provider

    async def _do_initialize(self) -> Optional[Any]:
        """初始化回测组件"""
        with error_context(self.name, "initialize"):
            if not self._enabled:
                self._logger.info("回测组件已禁用")
                return None  # 返回None表示没有资源

            # 使用超时控制进行初始化
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_INIT)
            try:

                async def _init_backtest():
                    # 延迟导入，避免循环依赖
                    from deepsearch.backtest.components.component import (
                        BacktestComponent as BacktestCore,
                    )

                    # 创建回测组件实例
                    self._backtest_instance = BacktestCore()

                    # 设置依赖
                    if self._event_engine or self._message_bus or self._data_provider:
                        # 获取实际的实例
                        event_engine_instance = (
                            self._event_engine._instance
                            if self._event_engine and hasattr(self._event_engine, "_instance")
                            else None
                        )
                        message_bus_instance = (
                            self._message_bus._instance
                            if self._message_bus and hasattr(self._message_bus, "_instance")
                            else None
                        )

                        self._backtest_instance.set_dependencies(
                            event_engine_instance, message_bus_instance, self._data_provider
                        )

                    # 初始化回测组件
                    await self._backtest_instance._initialize()
                    self._logger.info("回测组件初始化完成")
                    return self._backtest_instance  # 返回回测实例作为资源

                await asyncio.wait_for(_init_backtest(), timeout=timeout)
                return self._backtest_instance
            except asyncio.TimeoutError:
                raise ComponentLifecycleError(
                    self.name,
                    "initialize",
                    f"Backtest initialization timeout after {timeout} seconds",
                )

    async def _do_start(self) -> None:
        """启动回测组件"""
        with error_context(self.name, "start"):
            if not self._enabled:
                return

            if self._backtest_instance:
                # 使用超时控制进行启动
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_START)
                try:
                    await asyncio.wait_for(self._backtest_instance._start(), timeout=timeout)
                    self._logger.info("回测组件已启动")
                except asyncio.TimeoutError:
                    raise ComponentLifecycleError(
                        self.name, "start", f"Backtest start timeout after {timeout} seconds"
                    )

    async def _do_stop(self) -> None:
        """停止回测组件"""
        with error_context(self.name, "stop"):
            if not self._enabled:
                return

            if self._backtest_instance:
                # 使用超时控制进行停止
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_STOP)
                try:
                    await asyncio.wait_for(self._backtest_instance._stop(), timeout=timeout)
                    self._logger.info("回测组件已停止")
                except asyncio.TimeoutError:
                    self._logger.warning(f"Backtest stop timeout after {timeout} seconds")

    def _health_check(self) -> bool:
        """健康检查"""
        if not self._enabled:
            return True  # 禁用状态下认为是健康的

        if not self._backtest_instance:
            return False
        health_result = self._backtest_instance._health_check()
        if inspect.isawaitable(health_result):
            return False
        return bool(health_result)

    async def health_check_async(self) -> bool:
        """异步健康检查（带超时）"""
        if not self._enabled:
            return True

        timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_HEALTH)
        try:

            async def _check():
                if not self._backtest_instance:
                    return False

                # 检查回测实例的健康状态
                if hasattr(self._backtest_instance, "health_check_async"):
                    return await self._backtest_instance.health_check_async()
                else:
                    return self._health_check()

            return await asyncio.wait_for(_check(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning(f"Health check timeout after {timeout} seconds")
            return False
        except Exception as e:
            self._logger.error(f"Health check failed: {e}")
            return False

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """获取额外状态信息"""
        info: Dict[str, Any] = {"enabled": self._enabled}

        if self._backtest_instance:
            # 获取回测实例的状态信息
            instance_info = self._backtest_instance._get_extra_status_info()
            info.update(instance_info)

            # 添加依赖状态
            info["dependencies"] = {
                "event_engine": self._event_engine is not None,
                "message_bus": self._message_bus is not None,
                "data_provider": self._data_provider is not None,
            }

        return info

    async def run_backtest(self, strategy, data, params: Optional[Dict] = None) -> Dict[str, Any]:
        """运行回测（带超时）"""
        if not self._enabled:
            return {"error": "Backtest component is disabled"}

        if not self._backtest_instance:
            return {"error": "Backtest instance not initialized"}

        # 根据参数判断是否是复杂回测
        is_complex = params and params.get("complex", False)
        timeout = self._timeout_manager.get_timeout(
            TimeoutCategory.NETWORK_BATCH if is_complex else TimeoutCategory.NETWORK_HISTORICAL
        )

        try:

            async def _run():
                if hasattr(self._backtest_instance, "run_backtest"):
                    return await self._backtest_instance.run_backtest(strategy, data, params)
                else:
                    return {"error": "Backtest instance does not support run_backtest"}

            result = await asyncio.wait_for(_run(), timeout=timeout)
            if isinstance(result, dict):
                return cast(Dict[str, Any], result)
            if result is None:
                return {"error": "Empty result from backtest run"}
            return {"result": result}
        except asyncio.TimeoutError:
            return {"error": f"Backtest execution timeout after {timeout} seconds"}
        except Exception as e:
            self._logger.error(f"Backtest execution failed: {e}")
            return {"error": str(e)}

    def get_statistics(self) -> Dict[str, Any]:
        """获取回测统计信息（同步接口，内部适配异步实现）"""
        if not self._backtest_instance or not hasattr(self._backtest_instance, "get_statistics"):
            return {}

        stats_callable = getattr(self._backtest_instance, "get_statistics")
        timeout = self._timeout_manager.get_timeout(TimeoutCategory.NETWORK_REALTIME)

        try:
            if inspect.iscoroutinefunction(stats_callable):

                async def _invoke_async() -> Dict[str, Any]:
                    result = await asyncio.wait_for(stats_callable(), timeout=timeout)
                    if isinstance(result, dict):
                        return cast(Dict[str, Any], result)
                    if result is None:
                        return {}
                    return {"value": result}

                return self._execute_async_callable(_invoke_async)

            result = stats_callable()
            if inspect.isawaitable(result):

                async def _await_result() -> Dict[str, Any]:
                    awaited = await asyncio.wait_for(result, timeout=timeout)
                    if isinstance(awaited, dict):
                        return cast(Dict[str, Any], awaited)
                    if awaited is None:
                        return {}
                    return {"value": awaited}

                return self._execute_async_callable(_await_result)

            if isinstance(result, dict):
                return cast(Dict[str, Any], result)
            if result is None:
                return {}
            return {"value": result}
        except asyncio.TimeoutError:
            self._logger.warning(f"Get statistics timeout after {timeout} seconds")
            return {"error": "Timeout getting statistics"}
        except Exception as e:
            self._logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}

    def get_instance(self) -> Optional[Any]:
        """获取回测实例（供其他组件使用）"""
        return self._backtest_instance

    async def cancel_backtest(self, task_id: str) -> bool:
        """取消指定任务中的回测任务"""
        if not self._backtest_instance or not hasattr(self._backtest_instance, "cancel_task"):
            return False

        try:
            result = await self._backtest_instance.cancel_task(task_id)
            return bool(result)
        except Exception as e:
            self._logger.error(f"Failed to cancel backtest task {task_id}: {e}")
            return False

    async def get_backtest_status(self, task_id: str) -> Dict[str, Any]:
        """获取回测任务状态"""
        if not self._backtest_instance or not hasattr(self._backtest_instance, "get_task_status"):
            return {"error": "Backtest instance not available"}

        try:
            result = await self._backtest_instance.get_task_status(task_id)
            if isinstance(result, dict):
                return cast(Dict[str, Any], result)
            if result is None:
                return {"error": "No status returned"}
            return {"error": "Unexpected backtest status format", "raw": result}
        except Exception as e:
            self._logger.error(f"Failed to get backtest status for task {task_id}: {e}")
            return {"error": str(e)}

    def is_enabled(self) -> bool:
        """检查回测组件是否启用"""
        return bool(self._enabled)
