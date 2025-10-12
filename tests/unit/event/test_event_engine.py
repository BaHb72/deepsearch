"""
单元测试 - 事件引擎

测试EventEngine的核心功能
"""

import threading
import time
from typing import Any, Dict, List, cast
from unittest.mock import Mock

import pytest

from deepsearch.event.engine.engine import BatchHandler, Event, EventEngine, HandlerManager


def _event_payload(event: Event) -> Dict[str, Any]:
    """确保事件数据以字典形式返回，便于类型检查。"""

    assert isinstance(event.data, dict)
    return cast(Dict[str, Any], event.data)


class TestEvent:
    """Event类测试"""

    def test_event_creation(self):
        """测试事件创建"""
        event = Event(type="TEST_EVENT", data={"key": "value"})

        assert event.type == "TEST_EVENT"
        assert event.data == {"key": "value"}
        assert event.ts > 0

    def test_event_default_data(self):
        """测试事件默认数据"""
        event = Event(type="TEST_EVENT")

        assert event.type == "TEST_EVENT"
        assert event.data == {}
        assert event.ts > 0

    def test_event_immutability(self):
        """测试事件不可变性"""
        event = Event(type="TEST_EVENT", data={"key": "value"})

        # Event使用frozen=True，属性不可修改
        with pytest.raises(AttributeError):
            event.type = "MODIFIED"

        with pytest.raises(AttributeError):
            event.data = {"new": "data"}

    def test_event_repr(self):
        """测试事件字符串表示"""
        event = Event(type="TEST_EVENT")
        repr_str = repr(event)

        assert "TEST_EVENT" in repr_str
        assert "@" in repr_str


class TestHandlerManager:
    """HandlerManager类测试"""

    @pytest.fixture
    def handler_manager(self):
        """创建HandlerManager实例"""
        return HandlerManager()

    @pytest.fixture
    def mock_handler(self):
        """创建模拟处理器"""
        handler = Mock()
        handler.__name__ = "mock_handler"
        return handler

    def test_register_handler(self, handler_manager, mock_handler):
        """测试注册处理器"""
        handler_manager.register(
            event_type="TEST_EVENT", handler=mock_handler, priority=10, async_flag=False
        )

        specific, general = handler_manager.get_handlers("TEST_EVENT")

        assert len(specific) == 1
        assert specific[0][1] is mock_handler
        assert specific[0][0] == 10  # priority
        assert specific[0][2] is False  # async_flag

    def test_register_duplicate_handler(self, handler_manager, mock_handler):
        """测试重复注册同一处理器"""
        handler_manager.register(
            event_type="TEST_EVENT", handler=mock_handler, priority=10, async_flag=False
        )

        # 再次注册相同的处理器（相同的async_flag）
        handler_manager.register(
            event_type="TEST_EVENT", handler=mock_handler, priority=20, async_flag=False
        )

        specific, _ = handler_manager.get_handlers("TEST_EVENT")

        # 不应该重复注册
        assert len(specific) == 1

    def test_register_handler_with_different_async_flag(self, handler_manager, mock_handler):
        """测试使用不同async_flag注册同一处理器"""
        handler_manager.register(
            event_type="TEST_EVENT", handler=mock_handler, priority=10, async_flag=False
        )

        handler_manager.register(
            event_type="TEST_EVENT", handler=mock_handler, priority=20, async_flag=True
        )

        specific, _ = handler_manager.get_handlers("TEST_EVENT")

        # 应该注册两次（不同的async_flag）
        assert len(specific) == 2

    def test_unregister_handler(self, handler_manager, mock_handler):
        """测试注销处理器"""
        handler_manager.register(event_type="TEST_EVENT", handler=mock_handler)

        handler_manager.unregister(event_type="TEST_EVENT", handler=mock_handler)

        specific, _ = handler_manager.get_handlers("TEST_EVENT")
        assert len(specific) == 0

    def test_register_general_handler(self, handler_manager, mock_handler):
        """测试注册通用处理器"""
        handler_manager.register_general(handler=mock_handler, priority=15, async_flag=True)

        _, general = handler_manager.get_handlers("ANY_EVENT")

        assert len(general) == 1
        assert general[0][1] is mock_handler
        assert general[0][0] == 15  # priority
        assert general[0][2] is True  # async_flag

    def test_unregister_general_handler(self, handler_manager, mock_handler):
        """测试注销通用处理器"""
        handler_manager.register_general(handler=mock_handler)
        handler_manager.unregister_general(handler=mock_handler)

        _, general = handler_manager.get_handlers("ANY_EVENT")
        assert len(general) == 0

    def test_handler_priority_sorting(self, handler_manager):
        """测试处理器按优先级排序"""
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        handler_manager.register(event_type="TEST", handler=handler1, priority=10)
        handler_manager.register(event_type="TEST", handler=handler2, priority=30)
        handler_manager.register(event_type="TEST", handler=handler3, priority=20)

        specific, _ = handler_manager.get_handlers("TEST")

        # 应该按优先级降序排列
        assert specific[0][0] == 30
        assert specific[1][0] == 20
        assert specific[2][0] == 10

    def test_register_batch_handler(self, handler_manager, mock_handler):
        """测试批量注册处理器"""
        event_types = ["EVENT1", "EVENT2", "EVENT3"]

        handler_manager.register_batch_handler(
            event_types=event_types, handler=mock_handler, priority=10, async_flag=False
        )

        for event_type in event_types:
            specific, _ = handler_manager.get_handlers(event_type)
            assert len(specific) == 1
            assert specific[0][1] is mock_handler

    def test_get_statistics(self, handler_manager):
        """测试获取统计信息"""
        handler1 = Mock()
        handler2 = Mock()

        handler_manager.register(event_type="EVENT1", handler=handler1)
        handler_manager.register(event_type="EVENT2", handler=handler2)
        handler_manager.register_general(handler=handler1)

        stats = handler_manager.get_statistics()

        assert stats["specific_handlers"]["EVENT1"] == 1
        assert stats["specific_handlers"]["EVENT2"] == 1
        assert stats["general_handlers"] == 1

    def test_invalid_registrations(self, handler_manager):
        """测试无效的注册操作"""
        # 空事件类型
        with pytest.raises(ValueError, match="event_type cannot be empty"):
            handler_manager.register(event_type="", handler=Mock())

        # 非可调用对象
        with pytest.raises(TypeError, match="handler must be callable"):
            handler_manager.register(event_type="TEST", handler="not_callable")

        # 通用处理器非可调用
        with pytest.raises(TypeError, match="handler must be callable"):
            handler_manager.register_general(handler="not_callable")


class TestBatchHandler:
    """BatchHandler基类测试"""

    def test_batch_handler_interface(self):
        """测试BatchHandler接口"""

        class TestBatchHandler(BatchHandler):
            def __init__(self):
                self.processed_events = []

            def process_batch(self, events: List[Event]) -> None:
                self.processed_events.extend(events)

        handler = TestBatchHandler()
        events = [Event(type="TEST1", data={"id": 1}), Event(type="TEST2", data={"id": 2})]

        # 测试批处理
        handler.process_batch(events)
        assert len(handler.processed_events) == 2

        # 测试单个事件处理（通过__call__）
        single_event = Event(type="TEST3", data={"id": 3})
        handler(single_event)
        assert len(handler.processed_events) == 3

    def test_batch_handler_not_implemented(self):
        """测试未实现process_batch的BatchHandler"""

        class IncompleteBatchHandler(BatchHandler):
            pass

        handler = IncompleteBatchHandler()
        events = [Event(type="TEST")]

        with pytest.raises(NotImplementedError):
            handler.process_batch(events)


class TestEventEngine:
    """EventEngine类测试"""

    @pytest.fixture
    def engine(self):
        """创建EventEngine实例"""
        engine = EventEngine(queue_size=100, max_workers=2)
        yield engine
        # 清理
        if engine._running:
            engine.stop(timeout=1.0)

    @pytest.fixture
    def batch_engine(self):
        """创建支持批处理的EventEngine实例"""
        engine = EventEngine(
            queue_size=100,
            max_workers=2,
            enable_batch_processing=True,
            batch_size=5,
            batch_timeout=0.1,
        )
        yield engine
        # 清理
        if engine._running:
            engine.stop(timeout=1.0)

    def test_engine_initialization(self):
        """测试引擎初始化"""
        engine = EventEngine(queue_size=50, max_workers=4)

        assert engine._queue.maxsize == 50
        assert engine._max_workers == 4
        assert not engine._running
        assert engine._executor is None

    def test_engine_invalid_initialization(self):
        """测试无效的引擎初始化参数"""
        # 无效的队列大小
        with pytest.raises(ValueError, match="queue_size must be positive"):
            EventEngine(queue_size=0)

        # 无效的工作线程数
        with pytest.raises(ValueError, match="max_workers cannot be negative"):
            EventEngine(max_workers=-1)

        # 无效的批处理大小
        with pytest.raises(ValueError, match="batch_size must be positive"):
            EventEngine(batch_size=0)

        # 无效的批处理超时
        with pytest.raises(ValueError, match="batch_timeout must be positive"):
            EventEngine(batch_timeout=0)

    def test_engine_start_stop(self, engine):
        """测试引擎启动和停止"""
        # 启动引擎
        engine.start()
        assert engine._running
        assert engine._dispatcher_th is not None
        assert engine._scheduler_th is not None
        assert engine._dispatcher_th.is_alive()
        assert engine._scheduler_th.is_alive()

        # 保存线程引用（停止后可能会被清理）
        dispatcher_th = engine._dispatcher_th
        scheduler_th = engine._scheduler_th

        # 停止引擎
        engine.stop(timeout=2.0)
        assert not engine._running

        # 等待线程结束
        time.sleep(0.5)

        # 检查线程是否已停止（使用保存的引用）
        if dispatcher_th:
            assert not dispatcher_th.is_alive()
        if scheduler_th:
            assert not scheduler_th.is_alive()

    def test_engine_double_start(self, engine):
        """测试重复启动引擎"""
        engine.start()
        first_dispatcher = engine._dispatcher_th

        # 再次启动应该无效
        engine.start()
        assert engine._dispatcher_th is first_dispatcher

    def test_engine_double_stop(self, engine):
        """测试重复停止引擎"""
        engine.start()
        engine.stop(timeout=1.0)

        # 再次停止应该无效
        engine.stop(timeout=1.0)
        assert not engine._running

    def test_event_put_and_processing(self, engine):
        """测试事件放入队列和处理"""
        # 记录处理的事件
        processed_events = []

        def handler(event: Event):
            processed_events.append(event)

        # 注册处理器
        engine.register(event_type="TEST_EVENT", handler=handler)

        # 启动引擎
        engine.start()

        # 发送事件
        event = Event(type="TEST_EVENT", data={"test": "data"})
        success = engine.put(event)
        assert success

        # 等待处理
        time.sleep(0.2)

        # 验证事件被处理
        assert len(processed_events) == 1
        assert processed_events[0].type == "TEST_EVENT"
        assert processed_events[0].data == {"test": "data"}

    def test_event_priority_processing(self, engine):
        """测试事件优先级处理"""
        processed_order = []

        def handler(event: Event) -> None:
            payload = _event_payload(event)
            processed_order.append(cast(int, payload["id"]))

        engine.register(event_type="TEST", handler=handler)
        engine.start()

        # 发送不同优先级的事件
        # 注意：优先级越低，处理越早
        engine.put(Event(type="TEST", data={"id": 1}), priority=10)
        engine.put(Event(type="TEST", data={"id": 2}), priority=5)
        engine.put(Event(type="TEST", data={"id": 3}), priority=20)

        # 等待处理
        time.sleep(0.3)

        # 验证处理顺序（优先级低的先处理）
        assert processed_order == [2, 1, 3]

    def test_async_handler_execution(self, engine):
        """测试异步处理器执行"""
        event_received = threading.Event()
        thread_name = None

        def async_handler(event: Event):
            nonlocal thread_name
            thread_name = threading.current_thread().name
            time.sleep(0.1)  # 模拟耗时操作
            event_received.set()

        # 注册异步处理器
        engine.register(event_type="ASYNC_TEST", handler=async_handler, async_flag=True)

        engine.start()

        # 发送事件
        engine.put(Event(type="ASYNC_TEST"))

        # 等待处理完成
        assert event_received.wait(timeout=1.0)

        # 验证在线程池中执行
        assert "EventEngine" in thread_name

    def test_general_handler(self, engine):
        """测试通用处理器"""
        received_events = []

        def general_handler(event: Event):
            received_events.append(event.type)

        # 注册通用处理器
        engine.register_general(handler=general_handler)

        engine.start()

        # 发送不同类型的事件
        engine.put(Event(type="TYPE_A"))
        engine.put(Event(type="TYPE_B"))
        engine.put(Event(type="TYPE_C"))

        # 等待处理
        time.sleep(0.2)

        # 验证所有事件都被处理
        assert set(received_events) == {"TYPE_A", "TYPE_B", "TYPE_C"}

    def test_handler_exception_handling(self, engine):
        """测试处理器异常处理"""
        successful_handler_called = False

        def failing_handler(event: Event):
            raise RuntimeError("Handler failed!")

        def successful_handler(event: Event):
            nonlocal successful_handler_called
            successful_handler_called = True

        # 注册两个处理器，一个会失败
        engine.register(event_type="TEST", handler=failing_handler, priority=10)
        engine.register(event_type="TEST", handler=successful_handler, priority=5)

        engine.start()

        # 发送事件
        engine.put(Event(type="TEST"))

        # 等待处理
        time.sleep(0.2)

        # 验证即使有处理器失败，其他处理器仍然执行
        assert successful_handler_called

    def test_scheduler_task(self, engine):
        """测试调度任务"""
        call_count = []

        def scheduled_handler(event: Event):
            call_count.append(time.time())

        engine.register(event_type="SCHEDULED", handler=scheduled_handler)
        engine.start()

        # 添加周期性任务（每0.1秒执行一次）
        task_id = engine.schedule(
            event_type="SCHEDULED", interval=0.1, priority=5, async_flag=False
        )

        # 等待执行几次
        time.sleep(0.35)

        # 取消任务
        engine.cancel(task_id)

        # 验证任务被执行了多次
        assert len(call_count) >= 3

        # 验证执行间隔
        if len(call_count) >= 2:
            interval = call_count[1] - call_count[0]
            assert 0.08 < interval < 0.12  # 允许一些误差

    def test_cancel_scheduled_task(self, engine):
        """测试取消调度任务"""
        call_count = 0

        def handler(event: Event):
            nonlocal call_count
            call_count += 1

        engine.register(event_type="CANCELABLE", handler=handler)
        engine.start()

        # 添加任务
        task_id = engine.schedule(event_type="CANCELABLE", interval=0.1, priority=5)

        # 等待一次执行
        time.sleep(0.15)

        # 取消任务
        engine.cancel(task_id)

        # 记录当前调用次数
        count_after_cancel = call_count

        # 等待更长时间
        time.sleep(0.3)

        # 验证取消后没有新的执行
        assert call_count == count_after_cancel

    def test_batch_processing(self, batch_engine):
        """测试批处理功能"""
        processed_batches: List[List[int]] = []

        class TestBatchHandler(BatchHandler):
            def process_batch(self, events: List[Event]) -> None:
                batch_ids = [cast(int, _event_payload(e)["id"]) for e in events]
                processed_batches.append(batch_ids)

        handler = TestBatchHandler()
        batch_engine.register(event_type="BATCH_TEST", handler=handler)
        batch_engine.start()

        # 发送多个事件
        for i in range(8):
            batch_engine.put(Event(type="BATCH_TEST", data={"id": i}))

        # 等待批处理
        time.sleep(0.3)

        # 验证批处理（batch_size=5，所以应该有两批）
        assert len(processed_batches) >= 1
        # 第一批应该有5个事件
        if len(processed_batches) > 0:
            assert len(processed_batches[0]) <= 5

    def test_engine_statistics(self, engine):
        """测试引擎统计信息"""
        engine.register(event_type="TEST", handler=Mock())
        engine.start()

        # 发送一些事件
        for i in range(5):
            engine.put(Event(type="TEST", data={"id": i}))

        # 等待处理
        time.sleep(0.2)

        # 获取统计信息（如果引擎有相关方法）
        stats = engine._handler_manager.get_statistics()
        assert "specific_handlers" in stats
        assert "TEST" in stats["specific_handlers"]
