"""
进程间通信模块

提供主进程（Engine）和 WebUI 进程之间的通信机制。
利用现有的消息总线和缓存系统实现高效的进程间通信。
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Callable

from deepsearch.messaging.bus import MessageBus
from deepsearch.observability.logger import logger


class IPCMessage:
    """进程间通信消息"""

    def __init__(self, msg_type: str, data: Any, request_id: Optional[str] = None):
        self.id = request_id or str(uuid.uuid4())
        self.type = msg_type
        self.data = data
        self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IPCMessage':
        msg = cls(data["type"], data["data"], data["id"])
        msg.timestamp = datetime.fromisoformat(data["timestamp"])
        return msg


class EngineIPCServer:
    """
    引擎端的 IPC 服务器
    
    负责：
    - 监听来自 WebUI 的命令
    - 发布引擎状态更新
    - 处理控制请求
    """

    def __init__(self, engine, message_bus: MessageBus, cache):
        self.name = "engine_ipc_server"
        self.engine = engine
        self.message_bus = message_bus
        self.cache = cache
        self._handlers: Dict[str, Callable] = {}
        self._status_update_task: Optional[asyncio.Task] = None
        self._logger = logger

    async def initialize_async(self) -> None:
        """初始化 IPC 服务器"""
        # 注册默认处理器
        self._register_default_handlers()

        # 订阅 WebUI 命令
        await self.message_bus.subscribe_async(
            "webui.commands.*",
            self._handle_command
        )

        logger.info("Engine IPC Server initialized")

    def _register_default_handlers(self):
        """注册默认的命令处理器"""
        self._handlers.update({
            "get_status": self._handle_get_status,
            "get_component_status": self._handle_get_component_status,
            "start_component": self._handle_start_component,
            "stop_component": self._handle_stop_component,
            "restart_component": self._handle_restart_component,
            "get_config": self._handle_get_config,
            "get_metrics": self._handle_get_metrics
        })

    async def _handle_command(self, topic: str, data: dict):
        """处理来自 WebUI 的命令"""
        try:
            msg = IPCMessage.from_dict(data)
            logger.debug(f"Received IPC command: {msg.type}")

            handler = self._handlers.get(msg.type)
            if handler:
                result = await handler(msg.data)
                # 发送响应
                response = IPCMessage("response", {
                    "success": True,
                    "result": result
                }, request_id=msg.id)

                await self.message_bus.publish_async(
                    f"engine.responses.{msg.id}",
                    response.to_dict()
                )
            else:
                logger.warning(f"Unknown IPC command: {msg.type}")
                response = IPCMessage("response", {
                    "success": False,
                    "error": f"Unknown command: {msg.type}"
                }, request_id=msg.id)

                await self.message_bus.publish_async(
                    f"engine.responses.{msg.id}",
                    response.to_dict()
                )

        except Exception as e:
            logger.error(f"Error handling IPC command: {e}")
            response = IPCMessage("response", {
                "success": False,
                "error": str(e)
            }, request_id=data.get("id"))

            await self.message_bus.publish_async(
                f"engine.responses.{data.get('id')}",
                response.to_dict()
            )

    async def _handle_get_status(self, data: dict) -> dict:
        """获取引擎状态"""
        return {
            "running": self.engine.is_running(),
            "mode": self.engine._mode,
            "start_time": self.engine._start_time.isoformat() if self.engine._start_time else None,
            "components": {
                name: {
                    "status": comp.get_status().value,
                    "type": comp.__class__.__name__
                }
                for name, comp in self.engine._components.items()
            }
        }

    async def _handle_get_component_status(self, data: dict) -> dict:
        """获取特定组件状态"""
        component_name = data.get("component")
        component = self.engine.get_component_by_name(component_name)

        if component:
            return {
                "name": component_name,
                "status": component.get_status().value,
                "info": await component.get_info() if hasattr(component, 'get_info') else {}
            }
        else:
            raise ValueError(f"Component not found: {component_name}")

    async def _handle_start_component(self, data: dict) -> dict:
        """启动组件"""
        component_name = data.get("component")
        await self.engine.start_component(component_name)
        return {"message": f"Component {component_name} started"}

    async def _handle_stop_component(self, data: dict) -> dict:
        """停止组件"""
        component_name = data.get("component")
        await self.engine.stop_component(component_name)
        return {"message": f"Component {component_name} stopped"}

    async def _handle_restart_component(self, data: dict) -> dict:
        """重启组件"""
        component_name = data.get("component")
        await self.engine.restart_component(component_name)
        return {"message": f"Component {component_name} restarted"}

    async def _handle_get_config(self, data: dict) -> dict:
        """获取配置信息"""
        from deepsearch.config import get_config
        config = get_config()
        return config.dict()

    async def _handle_get_metrics(self, data: dict) -> dict:
        """获取系统指标"""
        # TODO: 实现指标收集
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "component_metrics": {}
        }

    async def start_async(self) -> None:
        """启动 IPC 服务器"""
        # 启动状态更新任务
        self._status_update_task = asyncio.create_task(self._update_status_loop())
        logger.info("Engine IPC Server started")

    async def stop_async(self) -> None:
        """停止 IPC 服务器"""
        if self._status_update_task:
            self._status_update_task.cancel()
            try:
                await self._status_update_task
            except asyncio.CancelledError:
                pass

        logger.info("Engine IPC Server stopped")

    async def _update_status_loop(self):
        """定期更新引擎状态到缓存"""
        while True:
            try:
                status = await self._handle_get_status({})
                await self.cache.set(
                    "engine:status",
                    json.dumps(status),
                    ttl=60  # 60秒过期
                )

                # 发布状态更新事件
                await self.message_bus.publish_async(
                    "engine.status.updated",
                    IPCMessage("status_update", status).to_dict()
                )

                await asyncio.sleep(5)  # 每5秒更新一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating engine status: {e}")
                await asyncio.sleep(5)

    def register_handler(self, command: str, handler: Callable):
        """注册自定义命令处理器"""
        self._handlers[command] = handler


class WebUIIPCClient:
    """
    WebUI 端的 IPC 客户端
    
    负责：
    - 发送命令到引擎
    - 订阅引擎状态更新
    - 处理异步响应
    """

    def __init__(self, message_bus: MessageBus, cache):
        self.message_bus = message_bus
        self.cache = cache
        self._response_futures: Dict[str, asyncio.Future] = {}
        self._initialized = False

    async def initialize(self):
        """初始化客户端"""
        if self._initialized:
            return

        # 订阅引擎响应
        await self.message_bus.subscribe_async(
            "engine.responses.*",
            self._handle_response
        )

        # 订阅状态更新
        await self.message_bus.subscribe_async(
            "engine.status.*",
            self._handle_status_update
        )

        self._initialized = True
        logger.info("WebUI IPC Client initialized")

    async def _handle_response(self, topic: str, data: dict):
        """处理引擎响应"""
        msg = IPCMessage.from_dict(data)
        future = self._response_futures.get(msg.id)

        if future and not future.done():
            future.set_result(msg.data)

    async def _handle_status_update(self, topic: str, data: dict):
        """处理状态更新"""
        # 可以在这里触发 WebSocket 广播等
        logger.debug(f"Received status update: {topic}")

    async def send_command(self, command: str, data: dict = None, timeout: float = 30.0) -> dict:
        """
        发送命令到引擎并等待响应
        
        Args:
            command: 命令类型
            data: 命令数据
            timeout: 超时时间（秒）
            
        Returns:
            响应数据
        """
        msg = IPCMessage(command, data or {})

        # 创建响应 Future
        future = asyncio.Future()
        self._response_futures[msg.id] = future

        try:
            # 发送命令
            await self.message_bus.publish_async(
                "webui.commands.control",
                msg.to_dict()
            )

            # 等待响应
            result = await asyncio.wait_for(future, timeout=timeout)

            if result.get("success"):
                return result.get("result", {})
            else:
                raise Exception(result.get("error", "Unknown error"))

        except asyncio.TimeoutError:
            raise TimeoutError(f"Command {command} timed out after {timeout}s")
        finally:
            # 清理 Future
            self._response_futures.pop(msg.id, None)

    async def get_cached_status(self) -> Optional[dict]:
        """从缓存获取引擎状态（快速）"""
        status_json = await self.cache.get("engine:status")
        if status_json:
            return json.loads(status_json)
        return None

    async def get_status(self) -> dict:
        """获取引擎状态"""
        # 先尝试从缓存获取
        cached = await self.get_cached_status()
        if cached:
            return cached

        # 缓存没有则发送命令
        return await self.send_command("get_status")

    async def get_component_status(self, component: str) -> dict:
        """获取组件状态"""
        return await self.send_command("get_component_status", {"component": component})

    async def start_component(self, component: str) -> dict:
        """启动组件"""
        return await self.send_command("start_component", {"component": component})

    async def stop_component(self, component: str) -> dict:
        """停止组件"""
        return await self.send_command("stop_component", {"component": component})

    async def restart_component(self, component: str) -> dict:
        """重启组件"""
        return await self.send_command("restart_component", {"component": component})

    async def get_config(self) -> dict:
        """获取配置"""
        return await self.send_command("get_config")

    async def get_metrics(self) -> dict:
        """获取指标"""
        return await self.send_command("get_metrics")
