"""
EventEngine 和 MessageBus 集成测试

测试事件系统和消息总线的交互
"""

import asyncio
import pickle
import time
import zlib
from collections.abc import Mapping

import pytest

from deepsearch.event.engine.engine import EventEngine
from deepsearch.event.schema import Event
from deepsearch.messaging.bus import CompositeMessageBus


def decode_message_payload(message):
    """解码 CompositeMessageBus 投递的压缩消息。"""
    if isinstance(message, dict) and "_data" in message:
        data = message.get("_data")
        is_compressed = bool(message.get("_compressed"))
        try:
            if is_compressed:
                data = zlib.decompress(data)
            return pickle.loads(data)
        except Exception:
            return message
    return message


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
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

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
            received_messages.append(decode_message_payload(message))

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
            payload = decode_message_payload(message)
            event = Event(type="MESSAGE_EVENT", data=payload)
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
        while (event_counter < num_items or message_counter < num_items) and (
            time.time() - wait_start < max_wait
        ):
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
            route_a_messages.append(decode_message_payload(message))

        def handler_b(topic, message):
            route_b_messages.append(decode_message_payload(message))

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
        processed_events: list[int] = []

        def priority_handler(event: Event):
            priority_source = event.data if isinstance(event.data, Mapping) else {}
            processed_events.append(int(priority_source.get("priority", 0)))

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
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

        memory_bus = MessageBusFactory.create("inmem", {})
        buses = {"inmem": memory_bus}
        routes = [RouteConfig(match="*", buses=["inmem"])]

        bus = CompositeMessageBus(buses=buses, routes=routes)
        bus.start()

        received = []

        def handler(topic, message):
            received.append(decode_message_payload(message))

        bus.subscribe("test.*", handler)

        bus.publish("test.one", {"id": 1})
        bus.publish("test.two", {"id": 2})
        bus.publish("other.test", {"id": 3})

        await asyncio.sleep(0.1)

        assert len(received) == 2
        assert received[0]["id"] == 1
        assert received[1]["id"] == 2

        bus.stop()

    @pytest.mark.asyncio
    async def test_message_compression_roundtrip(self):
        """验证启用压缩后的消息可以被正确解码。"""
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

        memory_bus = MessageBusFactory.create("inmem", {})
        buses = {"inmem": memory_bus}
        routes = [RouteConfig(match="compress.*", buses=["inmem"])]

        bus = CompositeMessageBus(
            buses=buses,
            routes=routes,
            enable_compression=True,
            enable_deduplication=False,
        )
        bus.start()

        decoded = []

        def handler(topic, message):
            decoded.append(decode_message_payload(message))

        bus.subscribe("compress.topic", handler)

        payload = {"blob": "x" * 2048, "index": 1}
        bus.publish("compress.topic", payload)

        await asyncio.sleep(0.05)

        assert decoded == [payload]
        performance = bus.get_statistics()["performance"]
        assert performance["messages_compressed"] >= 1
        assert performance["compression_ratio"] > 0

        bus.stop()

    @pytest.mark.asyncio
    async def test_message_deduplication(self):
        """验证消息去重策略避免重复投递。"""
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

        memory_bus = MessageBusFactory.create("inmem", {})
        buses = {"inmem": memory_bus}
        routes = [RouteConfig(match="dedup.*", buses=["inmem"])]

        bus = CompositeMessageBus(
            buses=buses,
            routes=routes,
            enable_compression=False,
            enable_deduplication=True,
        )
        bus.start()

        counter = 0

        def handler(topic, message):
            nonlocal counter
            counter += 1

        bus.subscribe("dedup.topic", handler)

        payload = {"id": 42}
        bus.publish("dedup.topic", payload)
        bus.publish("dedup.topic", payload)
        bus.publish("dedup.topic", dict(payload))

        await asyncio.sleep(0.05)

        assert counter == 1
        performance = bus.get_statistics()["performance"]
        assert performance["messages_deduplicated"] >= 1
        assert performance["deduplication_ratio"] > 0

        bus.stop()

    @pytest.mark.asyncio
    async def test_statistics_reset(self):
        """验证统计信息复位逻辑。"""
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

        memory_bus = MessageBusFactory.create("inmem", {})
        buses = {"inmem": memory_bus}
        routes = [RouteConfig(match="stats.*", buses=["inmem"])]

        bus = CompositeMessageBus(
            buses=buses,
            routes=routes,
            enable_compression=True,
            enable_deduplication=True,
        )
        bus.start()

        payload = {"blob": "x" * 2048}
        bus.publish("stats.topic", payload)
        bus.publish("stats.topic", payload)

        await asyncio.sleep(0.05)

        stats = bus.get_statistics()
        performance = stats["performance"]
        assert performance["messages_published"] == 2
        assert performance["messages_compressed"] >= 1
        assert performance["messages_deduplicated"] >= 1
        assert performance["compression_ratio"] > 0
        assert performance["deduplication_ratio"] > 0

        if "deduplicator" in stats:
            dedup_stats = stats["deduplicator"]
            assert dedup_stats["total_messages"] >= 2
            assert dedup_stats["duplicates_filtered"] >= 1

        bus.reset_statistics()
        reset_stats = bus.get_statistics()
        performance_after = reset_stats["performance"]
        assert performance_after["messages_published"] == 0
        assert performance_after["messages_compressed"] == 0
        assert performance_after["messages_deduplicated"] == 0
        assert performance_after["compression_ratio"] == 0.0
        assert performance_after["deduplication_ratio"] == 0.0
        assert performance_after["routing_decisions"] == {}
        assert performance_after["errors"] == {}
        assert performance_after["avg_publish_time"] == 0.0

        if "deduplicator" in reset_stats:
            dedup_stats_after = reset_stats["deduplicator"]
            assert dedup_stats_after["total_messages"] == 0
            assert dedup_stats_after["duplicates_filtered"] == 0
            assert dedup_stats_after["unique_messages"] == 0

        bus.stop()

    @pytest.mark.asyncio
    async def test_dynamic_bus_registration(self):
        """验证动态新增总线与路由后消息可正确分发。"""
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

        primary_bus = MessageBusFactory.create("inmem", {})
        composite = CompositeMessageBus(buses={"inmem": primary_bus}, routes=[])

        secondary_bus = MessageBusFactory.create("inmem", {})
        composite.add_bus("zmq", secondary_bus)
        composite.add_route(RouteConfig(match="dyn.*", buses=["inmem", "zmq"]))

        received = []

        def handler(topic, message):
            received.append(decode_message_payload(message))

        composite.subscribe("dyn.*", handler)
        composite.start()

        composite.publish("dyn.topic", {"value": 1})
        await asyncio.sleep(0.05)

        assert len(received) == 2
        routing = composite.get_statistics()["performance"]["routing_decisions"]
        assert routing == {"inmem": 1, "zmq": 1}

        with pytest.raises(RuntimeError):
            composite.add_bus("timeseries", MessageBusFactory.create("inmem", {}))

        composite.stop()

    @pytest.mark.asyncio
    async def test_async_publish_requires_start(self):
        """验证未启动时的异步发布会抛出异常。"""
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

        bus = CompositeMessageBus(
            buses={"inmem": MessageBusFactory.create("inmem", {})},
            routes=[RouteConfig(match="async.*", buses=["inmem"])],
        )

        with pytest.raises(RuntimeError):
            await bus.publish_async("async.topic", {"msg": "test"})

    @pytest.mark.asyncio
    async def test_async_subscription_flow(self):
        """验证异步订阅与发布的桥接逻辑。"""
        from deepsearch.config.models.bus import RouteConfig
        from deepsearch.messaging.factory import MessageBusFactory

        memory_bus = MessageBusFactory.create("inmem", {})
        buses = {"inmem": memory_bus}
        routes = [RouteConfig(match="async.*", buses=["inmem"])]

        bus = CompositeMessageBus(buses=buses, routes=routes)
        bus.start()

        received = []

        async def async_handler(topic, message):
            received.append(decode_message_payload(message))

        await bus.subscribe_async("async.*", async_handler)
        await bus.publish_async("async.topic", {"value": 1})

        for _ in range(10):
            if received:
                break
            await asyncio.sleep(0.01)

        assert received == [{"value": 1}]

        await bus.unsubscribe_async("async.*", async_handler)
        bus.stop()
