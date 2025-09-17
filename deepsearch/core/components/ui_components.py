"""
UI组件模块

负责Web管理界面
从原unified_components.py拆分而来
"""
import asyncio
from typing import Optional, Dict, Any

from deepsearch.config import get_config
from ..async_component import AsyncComponent
from ..utils.exceptions import error_context
from ..interfaces import ComponentType
from ..utils.timeout_config import TimeoutManager, TimeoutCategory


class WebUIComponent(AsyncComponent):
    """WebUI组件 - Web管理界面"""

    def __init__(self):
        super().__init__("webui", ComponentType.INTERFACE, "Web界面")
        self._server = None
        self._frontend_process = None
        self._timeout_manager = TimeoutManager()

        # 获取配置
        config = get_config()
        self._backend_port = config.webui.backend_port if config and config.webui else 8000
        self._frontend_port = config.webui.frontend_port if config and config.webui else 3000
        self._enabled = config.webui.enabled if config and config.webui else True

    async def _initialize(self) -> None:
        """初始化WebUI"""
        with error_context(self.name, "initialize"):
            if not self._enabled:
                self._logger.info("WebUI组件已禁用")
                self._instance = self
                return

            # 使用超时控制进行初始化
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_INIT)
            try:
                async def _init_webui():
                    # WebUI的初始化在启动时进行
                    # 这里只做基本准备工作
                    self._instance = self
                    self._logger.info(f"WebUI组件已初始化，后端端口: {self._backend_port}, 前端端口: {self._frontend_port}")

                await asyncio.wait_for(_init_webui(), timeout=timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"WebUI initialization timeout after {timeout} seconds")

    async def _start(self) -> None:
        """启动WebUI服务"""
        with error_context(self.name, "start"):
            if not self._enabled:
                return

            # 使用超时控制进行启动
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_START)
            try:
                async def _start_webui():
                    # WebUI 服务器现在由 MainEngine 的异步任务管理
                    # 这里只记录启动信息
                    self._logger.info(f"WebUI组件已准备就绪")
                    self._logger.info(f"后端访问地址: http://localhost:{self._backend_port}")
                    self._logger.info(f"前端访问地址: http://localhost:{self._frontend_port}")

                await asyncio.wait_for(_start_webui(), timeout=timeout)
            except asyncio.TimeoutError:
                self._logger.warning(f"WebUI start timeout after {timeout} seconds")

    async def _stop(self) -> None:
        """停止WebUI服务"""
        with error_context(self.name, "stop"):
            if not self._enabled:
                return

            # 使用超时控制进行停止
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_STOP)
            try:
                async def _stop_webui():
                    # 停止前端进程（如果有）
                    if self._frontend_process:
                        self._frontend_process.terminate()
                        await asyncio.sleep(0.5)
                        if self._frontend_process.returncode is None:
                            self._frontend_process.kill()
                        self._frontend_process = None

                    # 停止服务器（如果有）
                    if self._server:
                        # 具体的停止逻辑
                        pass

                    self._logger.info("WebUI服务已停止")

                await asyncio.wait_for(_stop_webui(), timeout=timeout)
            except asyncio.TimeoutError:
                self._logger.warning(f"WebUI stop timeout after {timeout} seconds, forcing stop")
                # 强制停止
                if self._frontend_process:
                    self._frontend_process.kill()
                    self._frontend_process = None

    def _health_check(self) -> bool:
        """检查WebUI健康状态"""
        if not self._enabled:
            return True  # 禁用状态下认为是健康的

        # 基本健康检查
        return self._instance is not None

    async def health_check_async(self) -> bool:
        """异步健康检查（带超时）"""
        if not self._enabled:
            return True

        timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_HEALTH)
        try:
            async def _check():
                # 可以尝试访问健康检查端点
                import aiohttp
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"http://localhost:{self._backend_port}/api/health"
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            return response.status == 200
                except:
                    return False

            return await asyncio.wait_for(_check(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning(f"Health check timeout after {timeout} seconds")
            return False
        except Exception as e:
            self._logger.debug(f"Health check failed: {e}")
            return False

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        info = {
            "enabled": self._enabled,
            "backend_port": self._backend_port,
            "frontend_port": self._frontend_port,
            "backend_url": f"http://localhost:{self._backend_port}",
            "frontend_url": f"http://localhost:{self._frontend_port}"
        }

        # 添加服务状态
        if self._server:
            info["server_running"] = True
        else:
            info["server_running"] = False

        if self._frontend_process:
            info["frontend_running"] = self._frontend_process.returncode is None
        else:
            info["frontend_running"] = False

        return info

    def get_backend_port(self) -> int:
        """获取后端端口"""
        return self._backend_port

    def get_frontend_port(self) -> int:
        """获取前端端口"""
        return self._frontend_port

    def is_enabled(self) -> bool:
        """检查WebUI是否启用"""
        return self._enabled

    async def get_api_status(self) -> Dict[str, Any]:
        """获取API状态信息（带超时）"""
        if not self._enabled:
            return {"enabled": False}

        timeout = self._timeout_manager.get_timeout(TimeoutCategory.NETWORK_HEALTH)
        try:
            async def _get_status():
                import aiohttp
                status = {
                    "backend": {"port": self._backend_port, "status": "unknown"},
                    "frontend": {"port": self._frontend_port, "status": "unknown"}
                }

                # 检查后端状态
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"http://localhost:{self._backend_port}/api/health"
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            if response.status == 200:
                                data = await response.json()
                                status["backend"]["status"] = "healthy"
                                status["backend"]["details"] = data
                            else:
                                status["backend"]["status"] = "unhealthy"
                except Exception as e:
                    status["backend"]["status"] = "error"
                    status["backend"]["error"] = str(e)

                # 检查前端状态
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"http://localhost:{self._frontend_port}/"
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            if response.status == 200:
                                status["frontend"]["status"] = "healthy"
                            else:
                                status["frontend"]["status"] = "unhealthy"
                except Exception as e:
                    status["frontend"]["status"] = "error"
                    status["frontend"]["error"] = str(e)

                return status

            return await asyncio.wait_for(_get_status(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"Status check timeout after {timeout} seconds"}
        except Exception as e:
            self._logger.error(f"Failed to get API status: {e}")
            return {"error": str(e)}

    def set_server_instance(self, server):
        """设置服务器实例（由MainEngine调用）"""
        self._server = server

    def set_frontend_process(self, process):
        """设置前端进程（由启动脚本调用）"""
        self._frontend_process = process