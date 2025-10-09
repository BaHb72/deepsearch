import asyncio

import pytest

from deepsearch.event.const import EVENT_TICK
from deepsearch.event.engine import Event, EventEngine
from deepsearch.event.schema import TickSchema, schema_validated


async def wait_for(predicate, timeout=0.5, interval=0.01):
    """Simple helper that waits until predicate returns True."""
    elapsed = 0.0
    while elapsed < timeout:
        if predicate():
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return predicate()


@pytest.mark.asyncio
async def test_schema_validated_handler_processes_valid_event():
    engine = EventEngine(max_workers=0)
    received = []

    @schema_validated(EVENT_TICK, TickSchema)
    def handler(event: Event) -> None:
        received.append((event.data, event.ts))

    engine.register(EVENT_TICK, handler)

    engine.start()
    try:
        payload = {
            "source": "integration-test",
            "symbol": "600000",
            "exchange": "SSE",
            "bid_price": 10.0,
            "ask_price": 10.2,
            "bid_volume": 1200.0,
            "ask_volume": 800.0,
        }
        event = Event(type=EVENT_TICK, data=payload)
        original_ts = event.ts

        assert engine.put(event, block=False)
        assert await wait_for(lambda: len(received) == 1)

        validated, ts_value = received[0]
        assert validated["symbol"] == "600000"
        assert validated["source"] == "integration-test"
        assert validated["bid_price"] == 10.0
        assert ts_value == original_ts
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_schema_validated_records_validation_failure():
    engine = EventEngine(max_workers=0)
    received = []

    @schema_validated(EVENT_TICK, TickSchema)
    def handler(event: Event) -> None:
        received.append(event.data)

    engine.register(EVENT_TICK, handler)

    engine.start()
    try:
        invalid_payload = {
            "source": "integration-test",
            "symbol": "600001",
            "exchange": "SSE",
            "bid_price": 10.5,
            "ask_price": 10.0,  # invalid spread to trigger schema violation
            "bid_volume": 500.0,
            "ask_volume": 400.0,
        }
        invalid_event = Event(type=EVENT_TICK, data=invalid_payload)

        assert engine.put(invalid_event, block=False)
        await asyncio.sleep(0.1)

        assert received == []
    finally:
        engine.stop()


def test_schema_registry_dynamic_registration_roundtrip():
    from deepsearch.event.schema import SchemaBuilder, schema_registry

    event_type = "CUSTOM_TEST_EVENT"
    builder = SchemaBuilder("CustomTestSchema")
    builder.add_field("value", int, description="payload value")
    schema_cls = builder.build()

    try:
        schema_registry.register(event_type, schema_cls)

        assert event_type in schema_registry.list_schemas()
        exported = schema_registry.export_schemas()
        assert event_type in exported

        payload = {"source": "integration-test", "value": 42}
        validated = schema_registry.validate(event_type, payload)
        assert validated.value == 42

        stats = schema_registry.get_stats()[event_type]
        assert stats["success"] == 1
        assert stats["failure"] == 0
    finally:
        schema_registry.unregister(event_type)
