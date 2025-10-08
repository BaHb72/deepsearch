import asyncio
import time

import pytest

from deepsearch.core.interfaces.component import MonitoringHook
from deepsearch.event.engine.engine import BatchHandler, Event, EventEngine


async def wait_for_condition(condition, timeout=0.5, interval=0.01):
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    return condition()


class RecordingHook(MonitoringHook):
    def __init__(self) -> None:
        self.starts = []
        self.completes = []

    def on_handler_start(self, handler_name, event_type) -> None:
        self.starts.append((handler_name, event_type))

    def on_handler_complete(self, handler_name, event_type, duration, error) -> None:
        self.completes.append((handler_name, event_type, duration, error))


class CollectingBatchHandler(BatchHandler):
    def __init__(self) -> None:
        self.calls = []

    def process_batch(self, events):
        self.calls.append([event.data["id"] for event in events])


@pytest.mark.asyncio
async def test_monitoring_hook_tracks_handler_lifecycle():
    engine = EventEngine(max_workers=0)
    hook = RecordingHook()
    results = []

    def handler(event: Event) -> None:
        results.append(event.data["value"])

    engine.add_monitoring_hook(hook)
    engine.register("HOOK_EVENT", handler)
    engine.start()
    try:
        engine.put(Event(type="HOOK_EVENT", data={"value": 1}), block=False)
        await asyncio.sleep(0.1)

        assert results == [1]
        assert hook.starts == [(handler.__name__, "HOOK_EVENT")]
        assert len(hook.completes) == 1
        name, event_type, duration, error = hook.completes[0]
        assert name == handler.__name__
        assert event_type == "HOOK_EVENT"
        assert error is None
        assert duration >= 0
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_enable_and_disable_batch_processing_runtime():
    engine = EventEngine(
        enable_batch_processing=False, batch_size=3, batch_timeout=0.2, max_workers=0
    )
    handler = CollectingBatchHandler()
    engine.register("BATCH_FLIP", handler)
    engine.start()
    try:
        for idx in range(2):
            assert engine.put(Event(type="BATCH_FLIP", data={"id": idx}), block=False)
        await asyncio.sleep(0.1)

        assert handler.calls == [[0], [1]]

        handler.calls.clear()
        engine.enable_batch_processing(batch_size=3, batch_timeout=0.2)

        for idx in range(3):
            assert engine.put(Event(type="BATCH_FLIP", data={"id": idx}), block=False)
        await asyncio.sleep(0.2)

        assert handler.calls == [[0, 1, 2]]

        handler.calls.clear()
        engine.disable_batch_processing()
        assert engine.put(Event(type="BATCH_FLIP", data={"id": 99}), block=False)
        await asyncio.sleep(0.1)

        assert handler.calls == [[99]]
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_update_periodic_interval_runtime():
    engine = EventEngine(max_workers=0)
    timestamps = []

    def handler(event: Event) -> None:
        timestamps.append(time.perf_counter())

    engine.register("PERIODIC_UPDATE", handler)
    engine.start()
    try:
        task_id = engine.schedule(event_type="PERIODIC_UPDATE", interval=0.05)
        assert await wait_for_condition(lambda: len(timestamps) >= 1, timeout=0.3)
        first = timestamps[0]

        engine.update_periodic(task_id, new_interval=0.2)
        assert await wait_for_condition(lambda: len(timestamps) >= 2, timeout=0.5)
        second = timestamps[1]

        assert second - first >= 0.15
        engine.cancel_periodic(task_id)
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_general_handler_receives_events_and_can_unregister():
    engine = EventEngine(max_workers=0)
    specific_calls = []
    general_calls = []

    def specific_handler(event: Event) -> None:
        specific_calls.append(event.type)

    def general_handler(event: Event) -> None:
        general_calls.append(event.type)

    engine.register("SPECIFIC_EVENT", specific_handler)
    engine.register_general(general_handler)
    engine.start()
    try:
        assert engine.put(Event(type="SPECIFIC_EVENT", data={"value": 1}), block=False)
        assert engine.put(Event(type="SECOND_EVENT", data={"value": 2}), block=False)

        assert await wait_for_condition(lambda: len(specific_calls) == 1)
        assert await wait_for_condition(lambda: len(general_calls) == 2)

        type_counts = {etype: general_calls.count(etype) for etype in set(general_calls)}
        assert type_counts.get("SPECIFIC_EVENT") == 1
        assert type_counts.get("SECOND_EVENT") == 1

        engine.unregister_general(general_handler)
        general_calls.clear()

        assert engine.put(Event(type="SPECIFIC_EVENT", data={"value": 3}), block=False)
        assert await wait_for_condition(lambda: len(specific_calls) == 2)
        await asyncio.sleep(0.05)

        assert general_calls == []
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_snapshot_reflects_batch_and_schedule_state():
    engine = EventEngine(
        enable_batch_processing=True,
        batch_size=2,
        batch_timeout=0.2,
        max_workers=0,
    )
    handler = CollectingBatchHandler()
    engine.register("SNAPSHOT_EVENT", handler)
    engine.start()
    try:
        snapshot = engine.snapshot()
        batch_info = snapshot["batch_processing"]
        assert batch_info["enabled"] is True
        assert batch_info["batch_size"] == 2
        assert batch_info["batch_timeout"] == pytest.approx(0.2, rel=1e-3)

        engine.set_batch_size(3)
        engine.set_batch_timeout(0.15)
        snapshot = engine.snapshot()
        batch_info = snapshot["batch_processing"]
        assert batch_info["batch_size"] == 3
        assert batch_info["batch_timeout"] == pytest.approx(0.15, rel=1e-3)

        task_id = engine.schedule(event_type="SNAPSHOT_EVENT", interval=0.5)
        assert await wait_for_condition(lambda: engine.snapshot()["scheduled"] >= 1, timeout=0.3)

        assert engine.put(Event(type="SNAPSHOT_EVENT", data={"id": 1}), block=False)
        assert await wait_for_condition(lambda: bool(handler.calls), timeout=0.3)

        engine.disable_batch_processing()
        snapshot = engine.snapshot()
        assert snapshot["batch_processing"]["enabled"] is False

        engine.cancel_periodic(task_id)
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_remove_monitoring_hook_stops_tracking():
    engine = EventEngine(max_workers=0)
    hook = RecordingHook()
    observed = []

    def handler(event: Event) -> None:
        observed.append(event.data["value"])

    engine.add_monitoring_hook(hook)
    engine.register("MONITOR_EVENT", handler)
    engine.start()
    try:
        assert engine.put(Event(type="MONITOR_EVENT", data={"value": 1}), block=False)
        assert await wait_for_condition(lambda: len(observed) == 1)
        assert await wait_for_condition(lambda: len(hook.starts) == 1)
        assert await wait_for_condition(lambda: len(hook.completes) == 1)

        hook.starts.clear()
        hook.completes.clear()
        engine.remove_monitoring_hook(hook)

        assert engine.put(Event(type="MONITOR_EVENT", data={"value": 2}), block=False)
        assert await wait_for_condition(lambda: len(observed) == 2)

        await asyncio.sleep(0.05)
        assert hook.starts == []
        assert hook.completes == []
    finally:
        engine.stop()
