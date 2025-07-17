import json
import logging
import pickle
import threading
from abc import abstractmethod, ABC
from fnmatch import fnmatch
from typing import Any, Callable, TypeVar, Protocol, Optional

import zmq

from config.setting import RouteConfig
from .type import BusName

logger = logging.getLogger(__name__)
T = TypeVar("T")  # Data / Event / Command payload
R = TypeVar("R")  # Response payload


class Serializer(Protocol):
    """
    定义一个序列化器协议类。

    该类表明序列化器需要实现的最小行为，包括对象的序列化和反序列化。实现此协议的类可用于将对象
    转换为字节流或从字节流还原为对象。本类主要作为接口定义使用。

    """

    def serialize(self, obj: Any) -> bytes:
        """序列化对象到字节流"""
        ...

    def deserialize(self, data: bytes) -> Any:
        """从字节流反序列化对象"""
        ...


class PickleSerializer:
    """
    PickleSerializer 类实现了对象的序列化与反序列化功能。

    该类使用 Python 的 pickle 模块，将对象序列化为字节流，或将字节流反序列化为对象。

    """

    def serialize(self, obj: Any) -> bytes:
        return pickle.dumps(obj)

    def deserialize(self, data: bytes) -> Any:
        return pickle.loads(data)


class JsonSerializer:
    """
    JsonSerializer类的功能概述。

    该类用于将Python对象序列化为字节形式，或将字节形式反序列化为Python对象。
    适用于需要数据序列化与反序列化的场景。

    Methods:
        serialize(obj: Any) -> bytes: 将任意Python对象序列化为字节形式。
        deserialize(data: bytes) -> Any: 将字节形式的数据反序列化为Python对象。
    """

    def serialize(self, obj: Any) -> bytes:
        return json.dumps(obj, ensure_ascii=False).encode('utf-8')

    def deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode('utf-8'))


class AbstractMessageBus(ABC):
    """
    AbstractMessageBus 类的摘要说明。

    此抽象类定义了一个消息总线的接口。消息总线是一种用于在不同模块或组件之间传递消息的机制。
    通过此类可以发布主题相关的消息，订阅指定的主题，并管理消息的生命周期。

    方法：
    - 提供发布消息至指定主题的方法。
    - 提供订阅/取消订阅指定主题的方法。
    - 提供启动与优雅关闭消息循环的方法。

    """

    @abstractmethod
    def publish(self, topic: str, payload: T) -> None:
        """发布任意对象到指定主题"""

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[T], None]) -> None:
        """订阅主题；handler 为同步回调"""

    @abstractmethod
    def unsubscribe(self, topic: str, handler: Callable[[T], None]) -> None:
        """取消订阅"""

    @abstractmethod
    def start(self) -> None:
        """启动事件循环 / 后台线程"""

    @abstractmethod
    def stop(self) -> None:
        """优雅关闭，确保缓冲区刷写完毕"""


class InMemoryMessageBus(AbstractMessageBus):
    """
    一个基于内存的消息总线实现。

    此类提供发布/订阅模型的功能，允许不同的组件之间以松耦合的方式进行通信。通过内存中的数据结构
    管理主题和处理器的注册、调用等操作。适用于单机进程中轻量级的消息交互场景。

    :ivar handlers: 存储主题及其对应处理器列表的字典，支持不同消息类型和多个订阅者。
    :type handlers: dict[str, list[Callable]]
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False

    def publish(self, topic: str, payload: Any) -> None:
        """发布消息到指定主题"""
        if topic in self._handlers:
            for handler in self._handlers[topic]:
                try:
                    handler(payload)
                except Exception as e:
                    logger.error(f"Handler error for topic '{topic}': {e}")

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """订阅指定主题"""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """取消订阅"""
        if topic in self._handlers:
            try:
                self._handlers[topic].remove(handler)
                if not self._handlers[topic]:
                    del self._handlers[topic]
            except ValueError:
                logger.warning(f"Handler not found for topic: {topic}")

    def start(self) -> None:
        """启动消息总线"""
        self._running = True
        logger.info("InMemory MessageBus started")

    def stop(self) -> None:
        """停止消息总线"""
        self._running = False
        logger.info("InMemory MessageBus stopped")


class ZeroMQMessageBus(AbstractMessageBus):
    """
    基于 ZeroMQ 的消息总线实现。

    该类提供发布/订阅模式的消息总线功能，通过 ZeroMQ 底层框架实现消息的高效传输。
    支持多主题消息的发布订阅，同时允许动态添加和移除主题订阅处理器。

    :ivar config: 消息总线配置，用于定义 ZeroMQ 地址和其他参数。
    :type config: ZeroMQConfig
    :ivar serializer: 用于序列化和反序列化消息负载的对象。
    :type serializer: Serializer
    """

    def __init__(self, config=None, serializer: Serializer = None):
        # 延迟导入避免循环依赖
        from config.setting import ZeroMQConfig

        self._config = config or ZeroMQConfig()
        self._serializer = serializer or PickleSerializer()
        self._context = zmq.Context()
        self._publisher = self._context.socket(zmq.PUB)
        self._subscriber = self._context.socket(zmq.SUB)
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False
        self._thread: threading.Thread | None = None

        self._build_addresses()
        self._configure_sockets()

    def _build_addresses(self) -> None:
        """构建发布者和订阅者地址"""
        self._pub_addr = f"tcp://{self._config.host}:{self._config.pub_port}"
        self._sub_addr = f"tcp://{self._config.host}:{self._config.sub_port}"

    def _configure_sockets(self) -> None:
        """配置套接字选项"""
        self._publisher.setsockopt(zmq.SNDHWM, self._config.send_hwm)
        self._subscriber.setsockopt(zmq.RCVHWM, self._config.recv_hwm)
        if self._config.verbose:
            self._publisher.setsockopt(zmq.XPUB_VERBOSE, 1)

    def publish(self, topic: str, payload: Any) -> None:
        """发布消息到指定主题
        
        使用多帧消息格式：
        - 帧 0: UTF-8 编码的主题
        - 帧 1: 序列化后的负载
        """
        if not isinstance(topic, str):
            raise ValueError("Topic must be a string")

        try:
            # 序列化负载
            payload_bytes = self._serializer.serialize(payload)

            # 发送多帧消息
            self._publisher.send_multipart([
                topic.encode('utf-8'),  # 帧 0: 主题
                payload_bytes  # 帧 1: 负载
            ], flags=zmq.NOBLOCK)

        except Exception as e:
            logger.error(f"Failed to publish message to topic '{topic}': {e}")
            raise

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """订阅指定主题"""
        if topic not in self._handlers:
            self._handlers[topic] = []
            # 注意：对于多帧消息，订阅时仍然使用主题字符串
            self._subscriber.setsockopt_string(zmq.SUBSCRIBE, topic)
        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """取消订阅"""
        if topic in self._handlers:
            try:
                self._handlers[topic].remove(handler)
                if not self._handlers[topic]:
                    self._subscriber.setsockopt_string(zmq.UNSUBSCRIBE, topic)
                    del self._handlers[topic]
            except ValueError:
                logger.warning(f"Handler not found for topic: {topic}")

    def _parse_multipart_message(self, frames: list[bytes]) -> tuple[str, Any]:
        """解析多帧消息
        
        Args:
            frames: ZeroMQ 多帧消息列表
            
        Returns:
            (topic, payload) 元组
            
        Raises:
            ValueError: 如果消息格式不正确
            Exception: 如果反序列化失败
        """
        if len(frames) != 2:
            raise ValueError(f"Expected 2 frames, got {len(frames)}")

        # 帧 0: 解码主题
        topic = frames[0].decode('utf-8')

        # 帧 1: 反序列化负载
        payload = self._serializer.deserialize(frames[1])

        return topic, payload

    def _message_loop(self):
        """消息处理循环"""
        while self._running:
            try:
                # 接收多帧消息
                frames = self._subscriber.recv_multipart(flags=zmq.NOBLOCK)

                # 解析消息
                topic, payload = self._parse_multipart_message(frames)

                # 分发到处理器
                if topic in self._handlers:
                    for handler in self._handlers[topic]:
                        try:
                            handler(payload)
                        except Exception as e:
                            logger.error(f"Handler error for topic '{topic}': {e}")

            except zmq.ZMQError as e:
                if e.errno != zmq.EAGAIN:
                    logger.error(f"ZMQ error: {e}")
            except Exception as e:
                logger.error(f"Message loop error: {e}")

    def start(self) -> None:
        """
        启动消息总线的方法。

        该方法用于启动 ZeroMQ 消息总线。在运行状态下绑定发布地址，
        并连接订阅地址，然后启动一个新的线程来处理消息循环。

        :raises zmq.ZMQError: 如果绑定或连接过程中发生错误，抛出 ZeroMQ 异常。
        :return: None
        """
        if self._running:
            return
        try:
            self._publisher.bind(self._pub_addr)
            self._subscriber.connect(self._sub_addr)
            self._running = True
            self._thread = threading.Thread(target=self._message_loop)
            self._thread.daemon = True
            self._thread.start()
            logger.info(f"ZeroMQ MessageBus started on {self._pub_addr}")
        except zmq.ZMQError as e:
            logger.error(f"Failed to start message bus: {e}")
            raise

    def stop(self) -> None:
        """停止消息总线"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self._publisher.close()
        self._subscriber.close()
        self._context.term()
        logger.info("ZeroMQ MessageBus stopped")


class CompositeMessageBus(AbstractMessageBus):
    """
    复合消息总线的实现类。

    该类用于管理多个消息总线实例，并根据路由配置确定消息的目标总线。可以通过配置文件
    初始化多个子总线的实例，并根据特定的主题路由消息至适合的总线。支持订阅和取消订阅
    操作，并提供统一的启动和停止所有总线的接口。

    :ivar buses: 包含所有子总线的字典，键为总线名称，值为各自的总线实例。
    :type buses: dict[BusName, AbstractMessageBus]
    :ivar routes: 路由规则的列表，其中每条规则包含主题匹配模式和目标总线名称列表。
    :type routes: list[tuple[str, list[str]]]
    """

    def __init__(
            self,
            buses: Optional[dict[BusName, AbstractMessageBus]] = None,
            routes: Optional[list[RouteConfig]] = None
    ):
        if buses is None or routes is None:
            from config.setting import settings

            if buses is None:
                buses = self._create_buses_from_config(settings)
            if routes is None:
                routes = settings.message_bus.routes

        self._buses = buses
        normalized_routes: list[tuple[str, list[str]]] = []

        for route in routes:
            names = [name.value for name in route.buses]
            normalized_routes.append((route.match, names))

        self._routes = normalized_routes
        self._validate_routes()

        # 显示总线名称时使用枚举的字符串表示
        bus_names = [bus_name.value for bus_name in self._buses.keys()]
        logger.info(f"CompositeMessageBus initialized with buses: {bus_names}")

    def _validate_routes(self) -> None:
        """验证路由配置的有效性"""
        # 获取可用总线的字符串名称集合
        available_buses = {bus_name.value for bus_name in self._buses.keys()}

        print(f"Debug: available_buses = {available_buses}")  # 调试信息

        for pattern, bus_names in self._routes:
            print(
                f"Debug: pattern = {pattern}, bus_names = {bus_names}, types = {[type(name) for name in bus_names]}")  # 调试信息
            for bus_name in bus_names:
                if bus_name not in available_buses:
                    raise ValueError(f"路由 '{pattern}' 引用了不存在的总线 '{bus_name}'。可用总线：{available_buses}")

    def _create_buses_from_config(self, settings) -> dict[BusName, AbstractMessageBus]:
        """从配置创建消息总线字典"""
        buses = {}

        for bus_name_str in settings.message_bus.enabled_buses:
            try:
                # 将字符串转换为枚举
                bus_name = BusName(bus_name_str)

                if bus_name == BusName.ZMQ:
                    # 使用统一的配置获取方式
                    bus_config = settings.message_bus.get_bus_config(bus_name_str)
                    # 创建 ZeroMQConfig 实例 
                    from config.setting import ZeroMQConfig
                    zeromq_config = ZeroMQConfig.model_validate(bus_config)
                    buses[bus_name] = ZeroMQMessageBus(config=zeromq_config)
                elif bus_name == BusName.INMEM:
                    buses[bus_name] = InMemoryMessageBus()
                else:
                    logger.warning(f"Unknown bus type: {bus_name_str}")
            except ValueError:
                logger.warning(f"Invalid bus name: {bus_name_str}")
            except Exception as e:
                logger.error(f"Failed to create bus '{bus_name_str}': {e}")

        return buses

    def _find_target_buses(self, topic: str) -> set[str]:
        """找到匹配主题的目标总线"""
        targets: set[str] = set()
        for pattern, names in self._routes:
            if fnmatch(topic, pattern):
                targets.update(names)
        return targets

    def publish(self, topic: str, payload: Any) -> None:
        """发布消息到匹配的总线"""
        targets = self._find_target_buses(topic)
        for name in targets:
            # 需要将字符串名称转换为枚举来查找总线
            try:
                bus_name = BusName(name)
                if bus_name in self._buses:
                    self._buses[bus_name].publish(topic, payload)
                else:
                    logger.warning(f"Target bus '{name}' not found for topic '{topic}'")
            except ValueError:
                logger.warning(f"Invalid bus name in route: {name}")

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """在所有子总线上注册订阅"""
        for bus in self._buses.values():
            bus.subscribe(topic, handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """在所有子总线上取消订阅"""
        for bus in self._buses.values():
            bus.unsubscribe(topic, handler)

    def start(self) -> None:
        """启动所有子总线"""
        for bus_name, bus in self._buses.items():
            try:
                bus.start()
                logger.info(f"Started bus: {bus_name.value}")
            except Exception as e:
                logger.error(f"Failed to start bus '{bus_name.value}': {e}")
            # 可选择是否继续启动其他总线

    def stop(self) -> None:
        """停止所有子总线"""
        for bus_name, bus in self._buses.items():
            try:
                bus.stop()
                logger.info(f"Stopped bus: {bus_name.value}")
            except Exception as e:
                logger.error(f"Failed to stop bus '{bus_name.value}': {e}")


# 工厂函数，提供便利的创建接口
def create_message_bus(
        buses: Optional[dict[BusName, AbstractMessageBus]] = None,
        routes: Optional[list] = None
) -> CompositeMessageBus:
    """
    创建一个组合消息总线。

    该方法通过提供可选的消息总线字典和路由列表，用于初始化并返回一个组合消息总线实例。
    它允许将多个消息总线组合在一起，同时配置其路由规则。

    :param buses: 可选的消息总线字典，其中键为消息总线名称，值为具体的消息总线实例。
    :type buses: Optional[dict[BusName, AbstractMessageBus]]
    :param routes: 可选的路由列表，用于描述消息在总线间的流转规则。
    :type routes: Optional[list]
    :return: 返回组合消息总线实例。
    :rtype: CompositeMessageBus
    """
    return CompositeMessageBus(buses=buses, routes=routes)
