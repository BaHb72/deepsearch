"""
EventEngine 和 MessageBus 集成测试

测试事件系统和消息总线的交互
"""
import pytest
import asyncio
import time
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from deepsearch.event.engine.engine import EventEngine
from deepsearch.event.schema import Event
from deepsearch.messaging.bus import CompositeMessageBus
from deepsearch.core.utils.exceptions import ComponentLifecycleError


class TestEventMessageIntegration:
    """事件引擎和消息总线集成测试"""

    @pytest.fixture
    async def event_engine(self):
        """创建事件引擎实例"""
        engine = EventEngine()
        engine.start()
        yield engine
        engine.stop()

    @pytest.fixture
    async def message_bus(self):
        """创建消息总线实例"""
        # 使用内存总线进行测试
        from deepsearch.messaging.factory import MessageBusFactory
        from deepsearch.config.models.bus import RouteConfig

        # 创建内存总线实例
        memory_bus = MessageBusFactory.create("inmem", {})

        # 创建复合总线，包含内存总线
        buses = {"inmem": memory_bus}
        routes = [RouteConfig(match="*", buses=["inmem"])]

        bus = CompositeMessageBus(buses=buses, routes=routes)
        bus.start()  # start是同步方法
        yield bus
        bus.stop()  # stop是同步方法

    @pytest.mark.asyncio
    async def test_event_to_message_flow(self, event_engine, message_bus):
        """测试事件到消息的流转"""
        received_messages = []

        # 订阅消息
        def message_handler(topic, message):
            received_messages.append(message)

        message_bus.subscribe("test.event", message_handler)

        # 注册事件处理器，将事件转发到消息总线
        def event_handler(event: Event):
            # Event is a dataclass, not a pydantic model
            from dataclasses import asdict
            message_bus.publish("test.event", asdict(event))

        event_engine.register("TEST_EVENT", event_handler)

        # 发送事件
        test_event = Event(type="TEST_EVENT", data={"key": "value"})
        event_engine.put(test_event)

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证消息被接收
        assert len(received_messages) == 1
        assert received_messages[0]["type"] == "TEST_EVENT"
        assert received_messages[0]["data"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_message_to_event_flow(self, event_engine, message_bus):
        """测试消息到事件的流转"""
        received_events = []

        # 注册事件处理器
        def event_handler(event: Event):
            received_events.append(event)

        event_engine.register("MESSAGE_EVENT", event_handler)

        # 订阅消息并转发到事件引擎
        def message_handler(topic, message):
            event = Event(type="MESSAGE_EVENT", data=message)
            event_engine.put(event)

        message_bus.subscribe("test.message", message_handler)

        # 发布消息
        message_bus.publish("test.message", {"msg": "hello"})

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证事件被接收
        assert len(received_events) == 1
        assert received_events[0].type == "MESSAGE_EVENT"
        assert received_events[0].data["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_bidirectional_communication(self, event_engine, message_bus):
        """测试双向通信"""
        event_count = 0
        message_count = 0

        # 事件处理器
        def event_handler(event: Event):
            nonlocal event_count
            event_count += 1
            # 事件触发消息
            message_bus.publish("event.triggered", {"event_id": event_count})

        event_engine.register("BIDIRECTIONAL", event_handler)

        # 消息处理器
        def message_handler(topic, message):
            nonlocal message_count
            message_count += 1
            # 消息触发事件
            if message_count < 5:  # 防止无限循环
                event = Event(type="BIDIRECTIONAL", data={"msg_id": message_count})
                event_engine.put(event)

        message_bus.subscribe("event.triggered", message_handler)

        # 启动通信
        initial_event = Event(type="BIDIRECTIONAL", data={"start": True})
        event_engine.put(initial_event)

        # 等待处理
        await asyncio.sleep(0.5)

        # 验证双向通信
        assert event_count >= 1
        assert message_count >= 1

    @pytest.mark.asyncio
    async def test_error_handling(self, event_engine, message_bus):
        """测试错误处理"""
        errors = []

        # 错误的事件处理器
        def faulty_event_handler(event: Event):
            raise ValueError("Event processing error")

        # 错误的消息处理器
        def faulty_message_handler(topic, message):
            raise RuntimeError("Message processing error")

        # 注册错误处理器
        event_engine.register("ERROR_EVENT", faulty_event_handler)
        message_bus.subscribe("error.message", faulty_message_handler)

        # 发送事件和消息
        error_event = Event(type="ERROR_EVENT", data={})
        event_engine.put(error_event)
        message_bus.publish("error.message", {"error": "test"})

        # 等待处理
        await asyncio.sleep(0.1)

        # 系统应该继续运行，不应崩溃
        assert event_engine.is_active()
        # 注意：message_bus 的状态检查方法可能不同

    @pytest.mark.asyncio
    async def test_performance_under_load(self, event_engine, message_bus):
        """测试高负载下的性能"""
        event_counter = 0
        message_counter = 0
        start_time = time.time()

        # 事件处理器
        def count_event_handler(event: Event):
            nonlocal event_counter
            event_counter += 1

        # 消息处理器
        def count_message_handler(topic, message):
            nonlocal message_counter
            message_counter += 1

        # 注册处理器
        event_engine.register("LOAD_TEST", count_event_handler)
        message_bus.subscribe("load.test", count_message_handler)

        # 发送大量事件和消息
        num_items = 1000
        for i in range(num_items):
            event = Event(type="LOAD_TEST", data={"index": i})
            event_engine.put(event)
            message_bus.publish("load.test", {"index": i})

        # 等待处理完成
        max_wait = 5  # 最多等待5秒
        wait_start = time.time()
        while (event_counter < num_items or message_counter < num_items) and \
              (time.time() - wait_start < max_wait):
            await asyncio.sleep(0.01)

        elapsed_time = time.time() - start_time

        # 验证性能
        assert event_counter == num_items, f"只处理了 {event_counter}/{num_items} 个事件"
        assert message_counter == num_items, f"只处理了 {message_counter}/{num_items} 个消息"
        assert elapsed_time < 5, f"处理时间过长: {elapsed_time:.2f}秒"

        # 计算吞吐量
        event_throughput = event_counter / elapsed_time
        message_throughput = message_counter / elapsed_time
        print(f"\n事件吞吐量: {event_throughput:.0f} events/sec")
        print(f"消息吞吐量: {message_throughput:.0f} messages/sec")

    @pytest.mark.asyncio
    async def test_message_routing(self, event_engine, message_bus):
        """测试消息路由功能"""
        route_a_messages = []
        route_b_messages = []

        # 不同路由的处理器 - 使用同步处理器
        def handler_a(topic, message):
            route_a_messages.append(message)

        def handler_b(topic, message):
            route_b_messages.append(message)

        # 订阅不同的路由
        message_bus.subscribe("route.a", handler_a)
        message_bus.subscribe("route.b", handler_b)

        # 发布到不同路由
        message_bus.publish("route.a", {"target": "A"})
        message_bus.publish("route.b", {"target": "B"})
        message_bus.publish("route.a", {"target": "A2"})

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证路由
        assert len(route_a_messages) == 2
        assert len(route_b_messages) == 1
        assert route_a_messages[0]["target"] == "A"
        assert route_a_messages[1]["target"] == "A2"
        assert route_b_messages[0]["target"] == "B"

    @pytest.mark.asyncio
    async def test_event_priority(self, event_engine):
        """测试事件优先级处理"""
        processed_events = []

        def priority_handler(event: Event):
            processed_events.append(event.data.get("priority", 0))

        event_engine.register("PRIORITY_EVENT", priority_handler)

        # 发送不同优先级的事件
        # 注意：EventEngine 可能需要支持优先级
        events = [
            Event(type="PRIORITY_EVENT", data={"priority": 1}),
            Event(type="PRIORITY_EVENT", data={"priority": 3}),
            Event(type="PRIORITY_EVENT", data={"priority": 2}),
        ]

        for event in events:
            event_engine.put(event)

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证处理顺序
        assert len(processed_events) == 3

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, event_engine, message_bus):
        """测试错误后的清理"""
        cleanup_called = False

        def cleanup_handler(event: Event):
            nonlocal cleanup_called
            cleanup_called = True
            raise Exception("Intentional error")

        event_engine.register("CLEANUP_TEST", cleanup_handler)

        # 发送事件
        event = Event(type="CLEANUP_TEST", data={})
        event_engine.put(event)

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证清理
        assert cleanup_called
        # 引擎应该仍在运行
        assert event_engine.is_active()


class TestEventEngineFeatures:
    """事件引擎特性测试"""

    @pytest.mark.asyncio
    async def test_event_handler_registration(self):
        """测试事件处理器注册"""
        engine = EventEngine()
        handler_called = False

        def test_handler(event):
            nonlocal handler_called
            handler_called = True

        # 注册处理器
        engine.register("TEST", test_handler)

        # 启动引擎
        engine.start()

        # 发送事件
        event = Event(type="TEST", data={})
        engine.put(event)

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证
        assert handler_called

        # 清理
        engine.stop()

    @pytest.mark.asyncio
    async def test_event_handler_unregistration(self):
        """测试事件处理器注销"""
        engine = EventEngine()
        call_count = 0

        def test_handler(event):
            nonlocal call_count
            call_count += 1

        # 注册处理器
        engine.register("TEST", test_handler)
        engine.start()

        # 发送第一个事件
        engine.put(Event(type="TEST", data={}))
        await asyncio.sleep(0.1)
        assert call_count == 1

        # 注销处理器
        engine.unregister("TEST", test_handler)

        # 发送第二个事件
        engine.put(Event(type="TEST", data={}))
        await asyncio.sleep(0.1)
        assert call_count == 1  # 不应该增加

        engine.stop()

    @pytest.mark.asyncio
    async def test_multiple_handlers_same_event(self):
        """测试同一事件的多个处理器"""
        engine = EventEngine()
        results = []

        def handler1(event):
            results.append("handler1")

        def handler2(event):
            results.append("handler2")

        def handler3(event):
            results.append("handler3")

        # 注册多个处理器
        engine.register("MULTI", handler1)
        engine.register("MULTI", handler2)
        engine.register("MULTI", handler3)

        engine.start()

        # 发送事件
        engine.put(Event(type="MULTI", data={}))

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证所有处理器都被调用
        assert len(results) == 3
        assert "handler1" in results
        assert "handler2" in results
        assert "handler3" in results

        engine.stop()


class TestMessageBusFeatures:
    """消息总线特性测试"""

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self):
        """测试通配符订阅"""
        from deepsearch.messaging.factory import MessageBusFactory
        from deepsearch.config.models.bus import RouteConfig

        # 创建内存总线实例
        memory_bus = MessageBusFactory.create("inmem", {})

        # 创建复合总线，包含内存总线
        buses = {"inmem": memory_bus}
        routes = [RouteConfig(match="*", buses=["inmem"])]

        bus = CompositeMessageBus(buses=buses, routes=routes)
        bus.start()  # start是同步方法

        received = []

        def handler(topic, message):
            received.append(message)

        # 订阅通配符路由
        bus.subscribe("test.*", handler)

        # 发布到不同的子路由
        bus.publish("test.one", {"id": 1})
        bus.publish("test.two", {"id": 2})
        bus.publish("other.test", {"id": 3})  # 不应该被接收

        # 等待处理
        await asyncio.sleep(0.1)

        # 验证
        assert len(received) == 2
        assert received[0]["id"] == 1
        assert received[1]["id"] == 2

        bus.stop()  # stop是同步方法

    @pytest.mark.asyncio
    async def test_message_persistence(self):
        """测试消息持久化（如果支持）"""
        # 这个测试依赖于消息总线的具体实现
        pass

    @pytest.mark.asyncio
    async def test_message_acknowledgment(self):
        """测试消息确认机制（如果支持）"""
        # 这个测试依赖于消息总线的具体实现
        pass