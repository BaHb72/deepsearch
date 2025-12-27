"""
QMT数据接收服务

负责接收来自QMT终端的实时行情数据
"""

import asyncio
import json
import struct
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypedDict,
    cast,
)

from loguru import logger

from deepsearch.infrastructure.providers.interfaces.payloads import ReceiverStats
from deepsearch.infrastructure.providers.interfaces.runtime import ClientStats, ProviderStats


def _client_stats_factory() -> ClientStats:
    """创建客户端统计基础结构。"""

    return ClientStats(messages=0, bytes=0)


@dataclass
class ProviderStatistics:
    """封装 QMT 接收器内部统计，避免裸 `dict`。"""

    total_messages: int = 0
    total_bytes: int = 0
    message_types: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))
    client_stats: defaultdict[str, ClientStats] = field(
        default_factory=lambda: defaultdict(_client_stats_factory)
    )
    errors: int = 0
    start_time: float | None = None

    def snapshot(self) -> ProviderStats:
        """生成 ProviderStats 快照。"""

        return {
            "total_messages": self.total_messages,
            "total_bytes": self.total_bytes,
            "message_types": dict(self.message_types),
            "client_stats": {
                client_id: ClientStats(messages=stats["messages"], bytes=stats["bytes"])
                for client_id, stats in self.client_stats.items()
            },
            "errors": self.errors,
            "start_time": self.start_time,
        }

    def record_payload(self, *, client_id: Optional[str], byte_count: int) -> None:
        """累计消息计数与字节数。"""

        self.total_messages += 1
        self.total_bytes += byte_count

        if client_id is not None:
            stats = self.client_stats[client_id]
            stats["messages"] += 1
            stats["bytes"] += byte_count

    def increment_message_type(self, msg_type: str) -> None:
        """记录消息类型出现次数。"""

        self.message_types[msg_type] += 1

    def increment_error(self) -> None:
        """累计错误次数。"""

        self.errors += 1


class ClientInfo(TypedDict, total=False):
    """维护客户端连接的运行时状态。"""

    writer: asyncio.StreamWriter
    address: Tuple[str, int]
    connected_time: float
    authenticated: bool
    last_heartbeat: Optional[float]
    supports_dynamic: bool
    client_type: str


class ClientOverview(TypedDict, total=False):
    """用于管理端展示的客户端概览。"""

    address: Tuple[str, int]
    connected_time: float
    authenticated: bool
    last_heartbeat: Optional[float]
    stats: ClientStats
    supports_dynamic: bool
    client_type: str


MessagePayload = Dict[str, object]


class QMTReceiver:
    """QMT数据接收器"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9999,
        auth_enabled: bool = False,
        auth_token: str = "",
    ):
        """
        初始化接收器

        Args:
            host: 监听地址
            port: 监听端口
            auth_enabled: 是否启用认证
            auth_token: 认证令牌
        """
        self.host = host
        self.port = port
        self.auth_enabled = auth_enabled
        self.auth_token = auth_token

        # 服务器状态
        self.server: asyncio.AbstractServer | None = None
        self.running = False

        # 客户端管理
        self.clients: Dict[str, ClientInfo] = {}
        self.authenticated_clients: Set[str] = set()
        self.client_writers: Dict[str, asyncio.StreamWriter] = {}

        # 数据处理回调
        self.data_handlers: Dict[
            str, Callable[[str, MessagePayload], Coroutine[Any, Any, None]]
        ] = {}

        # 订阅管理器（延迟导入）
        self._subscription_manager: Any | None = None

        # 统计信息
        self.stats = ProviderStatistics()

        # 线程池
        self.executor = None

    def register_handler(
        self, msg_type: str, handler: Callable[[str, MessagePayload], Coroutine[Any, Any, None]]
    ) -> None:
        """
        注册消息处理器

        Args:
            msg_type: 消息类型
            handler: 处理函数
        """
        self.data_handlers[msg_type] = handler
        logger.debug(f"注册消息处理器: {msg_type}")

    async def start(self):
        """启动接收服务"""
        if self.running:
            logger.warning("接收服务已在运行")
            return

        try:
            # 创建服务器
            self.server = await asyncio.start_server(self._handle_client, self.host, self.port)

            self.running = True
            self.stats.start_time = time.time()

            logger.info(f"QMT接收服务已启动 {self.host}:{self.port}")

            # 启动订阅更新推送任务
            update_task = asyncio.create_task(self.push_subscription_updates())

            # 运行服务器
            async with self.server:
                try:
                    await self.server.serve_forever()
                finally:
                    update_task.cancel()
                    try:
                        await update_task
                    except asyncio.CancelledError:
                        pass

        except Exception as e:
            logger.error(f"启动接收服务失败: {e}")
            raise

    async def stop(self):
        """停止接收服务"""
        if not self.running:
            return

        self.running = False

        # 断开所有客户端
        for client_id in list(self.clients.keys()):
            await self._disconnect_client(client_id)

        # 关闭服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logger.info("QMT接收服务已停止")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接"""
        addr = writer.get_extra_info("peername")
        client_id = f"{addr[0]}:{addr[1]}"

        logger.info(f"新客户端连接: {client_id}")

        # 记录客户端信息
        self.clients[client_id] = {
            "writer": writer,
            "address": addr,
            "connected_time": time.time(),
            "authenticated": False,
        }

        try:
            while self.running:
                # 接收消息
                msg = await self._receive_message(client_id, reader)
                if not msg:
                    break

                # 处理消息
                await self._process_message(client_id, msg)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"处理客户端 {client_id} 异常: {e}")
            self.stats.increment_error()
        finally:
            await self._disconnect_client(client_id)

    async def _receive_message(
        self, client_id: str, reader: asyncio.StreamReader
    ) -> Optional[MessagePayload]:
        """接收客户端消息（支持两种格式）"""
        try:
            # 先尝试读取一些数据来判断格式
            peek_data = await reader.read(4)
            if not peek_data:
                return None

            # 检查是否是二进制长度前缀格式（前4字节是长度）
            # 如果第一个字节是ASCII字符（如 '{' 或字母），则认为是文本格式
            if peek_data[0] < 128 and chr(peek_data[0]) in '{"ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                # 文本格式（换行符分隔的JSON）
                # 读取直到换行符
                line = bytearray(peek_data)
                while b"\n" not in line:
                    chunk = await reader.read(1024)
                    if not chunk:
                        break
                    line.extend(chunk)

                # 解析JSON
                if line:
                    newline_index = line.find(b"\n")
                    payload_bytes = bytes(
                        line[: newline_index + 1] if newline_index != -1 else line
                    )
                    json_str = payload_bytes.rstrip(b"\n").decode("utf-8")
                    raw_msg = json.loads(json_str)
                    if not isinstance(raw_msg, dict):
                        logger.warning(f"忽略非字典格式的文本消息: {raw_msg!r}")
                        return None
                    msg = cast(MessagePayload, raw_msg)

                    # 更新统计
                    self.stats.record_payload(client_id=client_id, byte_count=len(payload_bytes))

                    return msg
            else:
                # 二进制格式（长度前缀）
                length = struct.unpack("!I", peek_data)[0]

                # 读取消息内容
                data = await reader.readexactly(length)

                # 解析JSON
                raw_msg = json.loads(data.decode("utf-8"))
                if not isinstance(raw_msg, dict):
                    logger.warning(f"忽略非字典格式的二进制消息: {raw_msg!r}")
                    return None
                msg = cast(MessagePayload, raw_msg)

                # 更新统计
                self.stats.record_payload(client_id=client_id, byte_count=length + 4)

                return msg

        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            logger.error(f"接收消息失败: {e}")
            return None
        return None

    async def _send_message(self, writer: asyncio.StreamWriter, msg: Mapping[str, object]) -> None:
        """发送消息到客户端（使用文本格式，换行符分隔）"""
        try:
            # 序列化消息为JSON，添加换行符
            data = json.dumps(msg, ensure_ascii=False) + "\n"

            # 发送文本消息（不使用长度前缀）
            writer.write(data.encode("utf-8"))
            await writer.drain()

            logger.debug(f"发送消息: {msg.get('type', 'UNKNOWN')}")

        except Exception as e:
            logger.error(f"发送消息失败: {e}")

    async def _process_message(self, client_id: str, msg: MessagePayload) -> None:
        """处理接收到的消息"""
        raw_type = msg.get("type")
        msg_type = raw_type if isinstance(raw_type, str) else "UNKNOWN"

        # 对于LEVEL2数据，记录更详细的信息
        if msg_type == "LEVEL2":
            maybe_mapping = msg.get("data")
            level2_data: Mapping[str, object] = (
                maybe_mapping if isinstance(maybe_mapping, Mapping) else {}
            )
            symbol_obj = level2_data.get("symbol", "UNKNOWN")
            symbol = symbol_obj if isinstance(symbol_obj, str) else str(symbol_obj)
            bid_prices = level2_data.get("bid_price")
            ask_prices = level2_data.get("ask_price")
            bid_count = (
                len(bid_prices)
                if isinstance(bid_prices, Sequence) and not isinstance(bid_prices, (str, bytes))
                else 0
            )
            ask_count = (
                len(ask_prices)
                if isinstance(ask_prices, Sequence) and not isinstance(ask_prices, (str, bytes))
                else 0
            )
            logger.info(
                f"[RECEIVER] 收到LEVEL2消息: symbol={symbol}, bid_levels={bid_count}, ask_levels={ask_count}, from {client_id}"
            )
        else:
            logger.info(f"[RECEIVER] 收到消息: {msg_type} from {client_id}")

        # 更新统计
        self.stats.increment_message_type(msg_type)

        # 认证检查
        if self.auth_enabled and client_id not in self.authenticated_clients:
            if msg_type != "AUTH":
                await self._send_auth_required(client_id)
                return

            # 处理认证
            if await self._handle_auth(client_id, msg):
                self.authenticated_clients.add(client_id)
                self.clients[client_id]["authenticated"] = True
            else:
                await self._disconnect_client(client_id)
                return
        elif not self.auth_enabled and msg_type == "AUTH":
            # 即使认证关闭，也要处理AUTH消息，以便注册客户端
            logger.info(f"处理AUTH消息（认证已关闭）: {client_id}")

            # 保存writer以便后续推送
            writer = self.clients[client_id]["writer"]
            self.client_writers[client_id] = writer

            # 检查是否支持动态订阅
            capabilities_value = msg.get("capabilities", [])
            supports_dynamic = (
                isinstance(capabilities_value, Sequence)
                and not isinstance(capabilities_value, (str, bytes))
                and "dynamic_subscription" in capabilities_value
            )

            # 记录客户端信息
            self.clients[client_id]["supports_dynamic"] = supports_dynamic
            client_type = msg.get("client", "Unknown")
            if not isinstance(client_type, str):
                client_type = "Unknown"
            self.clients[client_id]["client_type"] = client_type
            self.clients[client_id]["authenticated"] = True

            # 发送认证成功响应
            await self._send_message(
                writer,
                {
                    "type": "AUTH_RESPONSE",
                    "status": "OK",
                    "message": "Authentication successful (auth disabled)",
                    "client_id": client_id,
                },
            )

            # 如果支持动态订阅，注册到订阅管理器
            if supports_dynamic:
                await self._register_dynamic_client(client_id, msg)

            return  # AUTH消息处理完毕，不需要继续

        # 分发消息到处理器
        if msg_type in self.data_handlers:
            try:
                # 异步执行处理器
                handler = self.data_handlers[msg_type]
                asyncio.create_task(handler(client_id, msg))
                logger.info(f"[RECEIVER] 已分发 {msg_type} 消息到处理器")
            except Exception as e:
                logger.error(f"[RECEIVER] 处理消息失败 {msg_type}: {e}")

        # 处理特殊消息类型
        if msg_type == "HEARTBEAT":
            await self._handle_heartbeat(client_id, msg)
        elif msg_type == "DISCONNECT":
            await self._disconnect_client(client_id)
        elif msg_type == "BATCH":
            await self._handle_batch(client_id, msg)
        elif msg_type == "GET_SUBSCRIPTION":
            await self._handle_get_subscription(client_id, msg)

    async def _handle_auth(self, client_id: str, msg: MessagePayload) -> bool:
        """处理认证消息"""
        token_value = msg.get("token")
        token = token_value if isinstance(token_value, str) else ""

        if token == self.auth_token:
            # 认证成功
            logger.info(f"客户端 {client_id} 认证成功")

            # 保存writer以便后续推送
            writer = self.clients[client_id]["writer"]
            self.client_writers[client_id] = writer

            # 检查是否支持动态订阅
            capabilities_value = msg.get("capabilities", [])
            supports_dynamic = (
                isinstance(capabilities_value, Sequence)
                and not isinstance(capabilities_value, (str, bytes))
                and "dynamic_subscription" in capabilities_value
            )

            # 记录客户端信息
            self.clients[client_id]["supports_dynamic"] = supports_dynamic
            client_type = msg.get("client", "Unknown")
            if not isinstance(client_type, str):
                client_type = "Unknown"
            self.clients[client_id]["client_type"] = client_type

            # 发送认证成功响应，包含客户端ID
            await self._send_message(
                writer,
                {
                    "type": "AUTH_RESPONSE",
                    "status": "OK",
                    "message": "Authentication successful",
                    "client_id": client_id,
                },
            )

            # 如果支持动态订阅，注册到订阅管理器
            if supports_dynamic:
                await self._register_dynamic_client(client_id, msg)

            return True
        else:
            # 认证失败
            logger.warning(f"客户端 {client_id} 认证失败")

            writer = self.clients[client_id]["writer"]
            await self._send_message(
                writer,
                {"type": "AUTH_RESPONSE", "status": "FAILED", "message": "Authentication failed"},
            )
            return False

    async def _send_auth_required(self, client_id: str):
        """发送需要认证的响应"""
        writer = self.clients[client_id]["writer"]
        await self._send_message(
            writer, {"type": "AUTH_REQUIRED", "message": "Please authenticate first"}
        )

    async def _handle_heartbeat(self, client_id: str, msg: MessagePayload) -> None:
        """处理心跳消息"""
        writer = self.clients[client_id]["writer"]

        # 回复心跳
        await self._send_message(
            writer,
            {
                "type": "HEARTBEAT_RESPONSE",
                "timestamp": time.time(),
                "server_stats": self.get_stats(),
            },
        )

        # 更新客户端最后活动时间
        self.clients[client_id]["last_heartbeat"] = time.time()

    async def _handle_batch(self, client_id: str, msg: MessagePayload) -> None:
        """处理批量消息"""
        data_value = msg.get("data", [])
        batch_items = (
            data_value
            if isinstance(data_value, Sequence) and not isinstance(data_value, (str, bytes))
            else []
        )

        for item in batch_items:
            if isinstance(item, Mapping):
                await self._process_message(client_id, cast(MessagePayload, dict(item)))

    async def _disconnect_client(self, client_id: str):
        """断开客户端连接"""
        if client_id not in self.clients:
            return

        client = self.clients[client_id]

        # 关闭连接
        try:
            client["writer"].close()
            await client["writer"].wait_closed()
        except Exception:
            pass

        # 清理记录
        del self.clients[client_id]
        self.authenticated_clients.discard(client_id)

        # 从订阅管理器中移除
        if client_id in self.client_writers:
            del self.client_writers[client_id]
            try:
                from deepsearch.webui.api.endpoints.qmt.qmt_subscription import subscription_manager

                subscription_manager.remove_client(client_id)
            except Exception:
                pass

        logger.info(f"客户端断开连接: {client_id}")

    def get_stats(self) -> ReceiverStats:
        """获取统计信息"""
        start_time = self.stats.start_time
        now = time.time()
        uptime = float(now - start_time) if start_time else 0.0
        total_messages = self.stats.total_messages
        rate = float(total_messages) / uptime if uptime > 0 else 0.0

        return ReceiverStats(
            running=self.running,
            uptime=uptime,
            clients={
                "connected": len(self.clients),
                "authenticated": len(self.authenticated_clients),
            },
            messages={"total": total_messages, "types": dict(self.stats.message_types)},
            data={"total_bytes": self.stats.total_bytes, "rate": rate},
            errors=self.stats.errors,
        )

    def get_client_info(self) -> Dict[str, ClientOverview]:
        """获取客户端信息"""
        info: Dict[str, ClientOverview] = {}
        for client_id, client in self.clients.items():
            client_stats = self.stats.client_stats[client_id]
            info[client_id] = ClientOverview(
                address=client["address"],
                connected_time=client["connected_time"],
                authenticated=client["authenticated"],
                last_heartbeat=client.get("last_heartbeat"),
                stats=ClientStats(messages=client_stats["messages"], bytes=client_stats["bytes"]),
                supports_dynamic=bool(client.get("supports_dynamic", False)),
                client_type=(
                    client_type_value
                    if isinstance(client_type_value := client.get("client_type"), str)
                    else "Unknown"
                ),
            )
        return info

    async def _register_dynamic_client(self, client_id: str, msg: MessagePayload) -> None:
        """注册支持动态订阅的客户端"""
        try:
            # 延迟导入避免循环依赖
            from deepsearch.webui.api.endpoints.qmt.qmt_subscription import subscription_manager

            # 添加客户端到订阅管理器
            client_type = msg.get("client", "QMT")
            if not isinstance(client_type, str):
                client_type = "QMT"
            version = msg.get("version", "Unknown")
            if not isinstance(version, str):
                version = "Unknown"
            client_info = {
                "client_type": client_type,
                "version": version,
                "connected_time": time.time(),
            }
            subscription_manager.add_client(client_id, client_info)

            # 立即获取并发送初始订阅列表
            symbols = subscription_manager.get_client_symbols(client_id)
            writer = self.client_writers.get(client_id)

            if writer:
                if symbols:
                    # 发送订阅列表
                    await self._send_message(
                        writer,
                        {"type": "SUBSCRIPTION_LIST", "symbols": symbols, "timestamp": time.time()},
                    )
                    logger.info(
                        f"注册动态订阅客户端 {client_id}，发送初始订阅 {len(symbols)} 只股票: {symbols}"
                    )
                else:
                    # 即使没有股票也发送空列表，让客户端知道状态
                    await self._send_message(
                        writer,
                        {"type": "SUBSCRIPTION_LIST", "symbols": [], "timestamp": time.time()},
                    )
                    logger.info(f"注册动态订阅客户端 {client_id}，当前无订阅")
            else:
                logger.warning(f"客户端 {client_id} 注册成功但无法发送订阅列表 - writer不存在")

        except Exception as e:
            logger.error(f"注册动态客户端失败: {e}", exc_info=True)

    async def _handle_get_subscription(self, client_id: str, msg: MessagePayload) -> None:
        """处理获取订阅列表请求"""
        try:
            from deepsearch.webui.api.endpoints.qmt.qmt_subscription import subscription_manager

            # 获取客户端订阅列表
            symbols = subscription_manager.get_client_symbols(client_id)

            # 发送订阅列表
            writer = self.client_writers.get(client_id)
            if writer:
                await self._send_message(
                    writer,
                    {"type": "SUBSCRIPTION_LIST", "symbols": symbols, "timestamp": time.time()},
                )

            logger.debug(f"向客户端 {client_id} 发送订阅列表: {len(symbols)} 只股票")

        except Exception as e:
            logger.error(f"处理订阅请求失败: {e}")

    async def push_subscription_updates(self):
        """推送订阅更新到客户端（定期任务）"""
        while self.running:
            try:
                # 延迟导入
                from deepsearch.webui.api.endpoints.qmt.qmt_subscription import subscription_manager

                # 检查每个客户端的待推送更新
                for client_id in list(self.client_writers.keys()):
                    if client_id not in self.clients:
                        continue

                    # 只推送给支持动态订阅的客户端
                    if not self.clients[client_id].get("supports_dynamic", False):
                        continue

                    # 获取待推送更新
                    updates = subscription_manager.get_pending_updates(client_id)

                    if updates:
                        writer = self.client_writers.get(client_id)
                        if writer:
                            for update in updates:
                                await self._send_message(writer, update)
                            logger.info(f"向客户端 {client_id} 推送了 {len(updates)} 个订阅更新")

                # 每秒检查一次
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"推送订阅更新失败: {e}")
                await asyncio.sleep(5)


class QMTReceiverComponent:
    """QMT接收器组件（用于集成到ComponentManager）"""

    def __init__(self, config: Dict):
        """初始化组件"""
        self.config = config
        self.receiver = None
        self.task = None

    async def initialize(self):
        """初始化组件"""
        # 创建接收器
        self.receiver = QMTReceiver(
            host=self.config.get("host", "0.0.0.0"),
            port=self.config.get("tcp_port", 9999),
            auth_enabled=self.config.get("enable_auth", False),
            auth_token=self.config.get("token", ""),
        )

        logger.info("QMT接收器组件初始化完成")

    async def start(self):
        """启动组件"""
        if not self.receiver:
            await self.initialize()

        # 在后台任务中运行接收器
        self.task = asyncio.create_task(self.receiver.start())
        logger.info("QMT接收器组件已启动")

    async def stop(self):
        """停止组件"""
        if self.receiver:
            await self.receiver.stop()

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("QMT接收器组件已停止")

    def get_status(self) -> Dict:
        """获取组件状态"""
        if self.receiver:
            return {
                "running": self.receiver.running,
                "stats": self.receiver.get_stats(),
                "clients": self.receiver.get_client_info(),
            }
        return {"running": False}
