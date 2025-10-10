"""
MiniQMT 数据提供者

提供 MiniQMT 量化终端的数据接入功能
"""

import asyncio
import inspect
import json
import socket
import struct
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

import pandas as pd
from loguru import logger
from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataProviderError,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability



class MiniQMTProvider(DataProvider):
    """
    MiniQMT 数据提供者

    功能：
    - 连接 MiniQMT 终端获取实时和历史数据
    - 支持股票、期货、期权等多品种
    - 自动重连和错误恢复
    - 数据缓存和性能优化
    """

    def __init__(self, config: Optional[DataProviderConfig] = None):
        """初始化 MiniQMT 提供者"""
        if config is None:
            # 创建默认配置
            config = DataProviderConfig(
                name="miniqmt",
                source_type=DataSourceType.QMT,
                enabled=True,
                timeout=10,
                config={
                    "max_concurrent": 10,
                    "rate_limit": 100,  # MiniQMT 每秒最多 100 个请求
                    "retry_times": 3,
                    "retry_delay": 1.0,
                    "cache_enabled": True,
                    "cache_ttl": 60,  # 1分钟缓存
                },
            )

        super().__init__(config)

        # MiniQMT 特定配置
        self.host = "127.0.0.1"
        self.port = 7777  # MiniQMT 默认端口
        self.username = ""
        self.password = ""

        # 连接状态
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # 订阅管理
        self.subscribed_symbols: set[str] = set()
        self.symbol_callbacks: dict[str, list[Callable[[Dict[str, Any]], Awaitable[None] | None]]] = {}

        # 心跳管理
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 30  # 30秒心跳
        self.heartbeat_task: Optional[asyncio.Task[None]] = None

        # 数据接收
        self.receive_task: Optional[asyncio.Task[None]] = None
        self.data_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=10000)

    def get_capabilities(self) -> set[DataCapability]:
        """返回 MiniQMT 支持的数据能力集合。"""

        return {
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.TICK_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.KLINE_DATA,
        }

    async def _initialize_source(self) -> None:
        """初始化 MiniQMT 数据源"""
        # 从配置加载连接参数
        from deepsearch.config import get_config

        config = get_config()

        miniqmt_config: Any = getattr(config, "miniqmt", None)
        connection: Any = None

        if isinstance(miniqmt_config, dict):
            connection = miniqmt_config.get("connection")
            self.host = str(miniqmt_config.get("host", self.host))
            self.port = int(miniqmt_config.get("port", self.port))
        elif miniqmt_config is not None:
            connection = getattr(miniqmt_config, "connection", None)

        if connection is not None:
            self.host = str(getattr(connection, "host", self.host))
            self.port = int(getattr(connection, "port", self.port))
            self.username = str(getattr(connection, "username", self.username))
            self.password = str(getattr(connection, "password", self.password))

        logger.info(f"MiniQMT 配置: {self.host}:{self.port}")

    async def _start_source(self) -> None:
        """启动 MiniQMT 连接"""
        # 连接到 MiniQMT
        await self._connect()

        # 启动心跳任务
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # 启动数据接收任务
        self.receive_task = asyncio.create_task(self._receive_loop())

        logger.info("MiniQMT 数据源已启动")

    async def _stop_source(self) -> None:
        """停止 MiniQMT 连接"""
        # 取消任务
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass

        # 断开连接
        await self._disconnect()

        logger.info("MiniQMT 数据源已停止")

    async def _connect(self) -> bool:
        """连接到 MiniQMT 服务器"""
        try:
            if self.socket:
                self.socket.close()

            # 创建 socket 连接
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)

            # 连接到服务器
            await asyncio.get_event_loop().run_in_executor(
                None, self.socket.connect, (self.host, self.port)
            )

            # 发送认证信息
            if self.username:
                auth_msg = {
                    "type": "AUTH",
                    "username": self.username,
                    "password": self.password,
                    "client": "DeepSearch",
                    "version": "1.0.0",
                }

                if await self._send_message(auth_msg):
                    # 等待认证响应
                    response = await self._receive_message()
                    if response and response.get("status") == "OK":
                        self.connected = True
                        self.reconnect_attempts = 0
                        logger.info(f"成功连接到 MiniQMT 服务器 {self.host}:{self.port}")
                        return True
                    else:
                        logger.error(f"MiniQMT 认证失败: {response}")
                        return False
            else:
                # 无需认证
                self.connected = True
                self.reconnect_attempts = 0
                logger.info(f"成功连接到 MiniQMT 服务器 {self.host}:{self.port}")
                return True

        except Exception as e:
            logger.error(f"连接 MiniQMT 失败: {e}")
            self.connected = False
            return False

        return False

    async def _disconnect(self) -> None:
        """断开 MiniQMT 连接"""
        if self.socket:
            try:
                # 发送断开消息
                disconnect_msg = {"type": "DISCONNECT"}
                await self._send_message(disconnect_msg)
            except Exception:
                pass

            self.socket.close()
            self.socket = None

        self.connected = False
        logger.info("已断开 MiniQMT 连接")

    async def _reconnect(self) -> bool:
        """重新连接 MiniQMT"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("达到最大重连次数，停止重连")
            return False

        self.reconnect_attempts += 1
        logger.info(f"尝试重新连接 MiniQMT (第{self.reconnect_attempts}次)")

        # 断开现有连接
        await self._disconnect()

        # 等待一段时间
        await asyncio.sleep(self.config.retry_delay * self.reconnect_attempts)

        # 尝试重新连接
        if await self._connect():
            # 重新订阅
            if self.subscribed_symbols:
                await self._subscribe_symbols(list(self.subscribed_symbols))
            return True

        return False

    async def _send_message(self, msg: Dict) -> bool:
        """发送消息到 MiniQMT"""
        if not self.socket:
            return False

        try:
            data = json.dumps(msg).encode("utf-8")
            length = struct.pack("!I", len(data))

            await asyncio.get_event_loop().run_in_executor(None, self.socket.sendall, length + data)

            return True

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.connected = False
            return False

    async def _receive_message(self) -> Optional[Dict]:
        """接收 MiniQMT 消息"""
        if not self.socket:
            return None

        try:
            # 读取消息长度
            length_data = await asyncio.get_event_loop().run_in_executor(None, self.socket.recv, 4)
            if not length_data:
                return None

            length = struct.unpack("!I", length_data)[0]

            # 读取消息内容
            data = await asyncio.get_event_loop().run_in_executor(None, self.socket.recv, length)

            return cast(Dict[str, Any], json.loads(data.decode("utf-8")))

        except Exception as e:
            logger.error(f"接收消息失败: {e}")
            return None

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if self.connected:
                    # 发送心跳
                    heartbeat_msg = {"type": "HEARTBEAT", "timestamp": time.time()}

                    if not await self._send_message(heartbeat_msg):
                        # 心跳失败，尝试重连
                        await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳异常: {e}")

    async def _receive_loop(self) -> None:
        """数据接收循环"""
        while True:
            try:
                if not self.connected:
                    await asyncio.sleep(1)
                    continue

                # 接收消息
                msg = await self._receive_message()
                if msg:
                    await self._process_message(msg)
                else:
                    # 连接可能断开
                    if self.connected:
                        logger.warning("接收到空消息，尝试重连")
                        await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"接收数据异常: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, msg: Dict[str, Any]) -> None:
        """处理接收到的消息"""
        msg_type = msg.get("type")

        if msg_type == "TICK":
            # 处理 tick 数据
            data = msg.get("data")
            if isinstance(data, dict):
                await self._process_tick_data(data)
        elif msg_type == "KLINE":
            # 处理 K线数据
            data = msg.get("data")
            if isinstance(data, dict):
                await self._process_kline_data(data)
        elif msg_type == "ORDERBOOK":
            # 处理盘口数据
            data = msg.get("data")
            if isinstance(data, dict):
                await self._process_orderbook_data(data)
        elif msg_type == "HEARTBEAT":
            # 心跳响应
            self.last_heartbeat = time.time()
        elif msg_type == "ERROR":
            # 错误消息
            logger.error(f"MiniQMT 错误: {msg.get('message')}")

    async def _process_tick_data(self, data: Dict[str, Any]) -> None:
        """处理 tick 数据"""
        if not data:
            return

        # 将数据放入队列
        await self.data_queue.put({"type": "tick", "data": data, "timestamp": time.time()})

        # 触发回调
        symbol = data.get("symbol")
        if symbol in self.symbol_callbacks:
            for callback in self.symbol_callbacks[symbol]:
                result = callback(data)
                if inspect.isawaitable(result):
                    await result

    async def _process_kline_data(self, data: Dict[str, Any]) -> None:
        """处理 K线数据"""
        if not data:
            return

        # 将数据放入队列
        await self.data_queue.put({"type": "kline", "data": data, "timestamp": time.time()})

    async def _process_orderbook_data(self, data: Dict[str, Any]) -> None:
        """处理盘口数据"""
        if not data:
            return

        # 将数据放入队列
        await self.data_queue.put({"type": "orderbook", "data": data, "timestamp": time.time()})

    async def _subscribe_symbols(self, symbols: List[str]) -> bool:
        """订阅股票行情"""
        if not self.connected:
            return False

        # 发送订阅请求
        subscribe_msg = {
            "type": "SUBSCRIBE",
            "symbols": symbols,
            "data_types": ["tick", "orderbook"],  # 订阅 tick 和盘口数据
        }

        if await self._send_message(subscribe_msg):
            # 更新订阅列表
            self.subscribed_symbols.update(symbols)
            logger.info(f"订阅 MiniQMT 行情: {symbols}")
            return True

        return False

    async def _unsubscribe_symbols(self, symbols: List[str]) -> bool:
        """取消订阅股票行情"""
        if not self.connected:
            return False

        # 发送取消订阅请求
        unsubscribe_msg = {"type": "UNSUBSCRIBE", "symbols": symbols}

        if await self._send_message(unsubscribe_msg):
            # 更新订阅列表
            for symbol in symbols:
                self.subscribed_symbols.discard(symbol)
            logger.info(f"取消订阅 MiniQMT 行情: {symbols}")
            return True

        return False

    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的具体实现

        Args:
            request: 数据请求

        Returns:
            数据 DataFrame
        """
        if not self.connected:
            # 尝试连接
            if not await self._connect():
                raise DataProviderError("无法连接到 MiniQMT")

        # 根据请求类型获取数据
        if request.period == "tick":
            # 获取实时数据
            return await self._fetch_realtime_data(request)
        elif request.period in ["1m", "5m", "15m", "30m", "60m"]:
            # 获取分钟数据
            return await self._fetch_minute_data(request)
        else:
            # 获取日线数据
            return await self._fetch_daily_data(request)

    async def _fetch_realtime_data(self, request: DataRequest) -> pd.DataFrame:
        """获取实时数据"""
        symbols = request.symbols or [request.symbol] if request.symbol else []
        if not symbols:
            return pd.DataFrame()

        # 发送实时数据请求
        query_msg = {"type": "QUERY_REALTIME", "symbols": symbols}

        if not await self._send_message(query_msg):
            raise DataProviderError("发送请求失败")

        # 等待响应（超时处理）
        try:
            response = await asyncio.wait_for(
                self._wait_for_response("REALTIME_DATA"), timeout=self.config.timeout
            )

            if response and "data" in response:
                # 转换为 DataFrame
                df = pd.DataFrame(response["data"])
                return df

        except asyncio.TimeoutError:
            raise DataProviderError("获取实时数据超时")

        return pd.DataFrame()

    async def _fetch_minute_data(self, request: DataRequest) -> pd.DataFrame:
        """获取分钟数据"""
        if not request.symbol:
            return pd.DataFrame()

        # 发送分钟数据请求
        query_msg = {
            "type": "QUERY_MINUTE",
            "symbol": request.symbol,
            "period": request.period,
            "start_date": str(request.start_date) if request.start_date else None,
            "end_date": str(request.end_date) if request.end_date else None,
        }

        if not await self._send_message(query_msg):
            raise DataProviderError("发送请求失败")

        # 等待响应
        try:
            response = await asyncio.wait_for(
                self._wait_for_response("MINUTE_DATA"), timeout=self.config.timeout
            )

            if response and "data" in response:
                # 转换为 DataFrame
                df = pd.DataFrame(response["data"])
                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    df.set_index("datetime", inplace=True)
                return df

        except asyncio.TimeoutError:
            raise DataProviderError("获取分钟数据超时")

        return pd.DataFrame()

    async def _fetch_daily_data(self, request: DataRequest) -> pd.DataFrame:
        """获取日线数据"""
        if not request.symbol:
            return pd.DataFrame()

        # 发送日线数据请求
        query_msg = {
            "type": "QUERY_DAILY",
            "symbol": request.symbol,
            "start_date": str(request.start_date) if request.start_date else None,
            "end_date": str(request.end_date) if request.end_date else None,
            "adjust": request.adjust,
        }

        if not await self._send_message(query_msg):
            raise DataProviderError("发送请求失败")

        # 等待响应
        try:
            response = await asyncio.wait_for(
                self._wait_for_response("DAILY_DATA"), timeout=self.config.timeout
            )

            if response and "data" in response:
                # 转换为 DataFrame
                df = pd.DataFrame(response["data"])
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                return df

        except asyncio.TimeoutError:
            raise DataProviderError("获取日线数据超时")

        return pd.DataFrame()

    async def _wait_for_response(self, response_type: str) -> Optional[Dict]:
        """等待特定类型的响应"""
        start_time = time.time()

        while time.time() - start_time < self.config.timeout:
            if not self.connected:
                return None

            # 接收消息
            msg = await self._receive_message()
            if msg and msg.get("type") == response_type:
                return msg

            await asyncio.sleep(0.1)

        return None

    # 公共 API 方法

    async def subscribe(self, symbols: List[str]) -> bool:
        """
        订阅股票行情

        Args:
            symbols: 股票代码列表

        Returns:
            是否成功
        """
        return await self._subscribe_symbols(symbols)

    async def unsubscribe(self, symbols: List[str]) -> bool:
        """
        取消订阅股票行情

        Args:
            symbols: 股票代码列表

        Returns:
            是否成功
        """
        return await self._unsubscribe_symbols(symbols)

    async def get_data(self, request: DataRequest) -> DataResponse:
        """按照 `DataRequest` 获取数据并封装响应。"""

        metadata = {
            "source": self.config.name or "miniqmt",
            "request_type": request.request_type,
        }

        try:
            dataframe = await self._fetch_data(request)
        except DataProviderError as exc:
            return DataResponse(success=False, error=str(exc), metadata=metadata)
        except Exception as exc:  # pragma: no cover - 防御日志
            logger.exception("MiniQMT 获取数据异常: %s", exc)
            return DataResponse(success=False, error=str(exc), metadata=metadata)

        return DataResponse(success=True, data=dataframe, metadata=metadata)

    def add_symbol_callback(self, symbol: str, callback) -> None:
        """
        添加股票数据回调

        Args:
            symbol: 股票代码
            callback: 回调函数
        """
        if symbol not in self.symbol_callbacks:
            self.symbol_callbacks[symbol] = []
        self.symbol_callbacks[symbol].append(callback)

    def remove_symbol_callback(self, symbol: str, callback) -> None:
        """
        移除股票数据回调

        Args:
            symbol: 股票代码
            callback: 回调函数
        """
        if symbol in self.symbol_callbacks:
            try:
                self.symbol_callbacks[symbol].remove(callback)
            except ValueError:
                pass

    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "subscribed_symbols": list(self.subscribed_symbols),
            "last_heartbeat": self.last_heartbeat,
            "reconnect_attempts": self.reconnect_attempts,
            "queue_size": self.data_queue.qsize(),
        }
