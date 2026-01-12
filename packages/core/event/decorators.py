"""
Event System Decorators Module

This module provides decorators to enhance developer experience when working with
the event system, including automatic registration, validation, monitoring, and more.
"""

from __future__ import annotations

import functools
import threading
import time
from collections.abc import Mapping
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, cast

from core.event.engine.engine import Event, EventEngine, Handler
from core.event.schema import BaseEventSchema
from core.observability import get_logger
from core.observability.monitoring.event_monitor import MetricsCollector

# ==============================================================================
# Constants
# ==============================================================================

DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_TIMEOUT = 30.0
DEFAULT_RATE_LIMIT = 100  # Events per second

# ==============================================================================
# Type Variables and Logger
# ==============================================================================

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])

# Global registry for decorated handlers
_handler_registry: Dict[str, List[Handler]] = {}
_engine_registry: Optional[EventEngine] = None


# ==============================================================================
# Core Decorators
# ==============================================================================


def event_handler(
    event_type: str, *, priority: int = 0, async_flag: bool = False, auto_register: bool = True
) -> Callable[[F], F]:
    """
    Decorator to mark a function as an event handler.

    :param event_type: Type of event to handle
    :param priority: Handler priority
    :param async_flag: Whether to execute asynchronously
    :param auto_register: Whether to auto-register with engine

    Example:
        @event_handler("TICK", priority=10, async_flag=True)
        def handle_tick(event: Event):
            print(f"Tick: {event.data}")
    """

    def decorator(func: F) -> F:
        # Add metadata to function
        setattr(func, "_event_type", event_type)
        setattr(func, "_priority", priority)
        setattr(func, "_async_flag", async_flag)

        # Add to registry if auto-register is enabled
        if auto_register:
            if event_type not in _handler_registry:
                _handler_registry[event_type] = []
            _handler_registry[event_type].append(func)

            # Register immediately if engine is available
            if _engine_registry:
                _engine_registry.register(
                    event_type=event_type, handler=func, priority=priority, async_flag=async_flag
                )

        return func

    return decorator


def multi_event_handler(
    event_types: List[str],
    *,
    priority: int = 0,
    async_flag: bool = False,
    auto_register: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to handle multiple event types with one function.

    Example:
        @multi_event_handler(["TICK", "TRADE"], priority=5)
        def handle_market_data(event: Event):
            print(f"{event.type}: {event.data}")
    """

    def decorator(func: F) -> F:
        # Apply event_handler for each type
        for event_type in event_types:
            event_handler(
                event_type, priority=priority, async_flag=async_flag, auto_register=auto_register
            )(func)

        # Store all event types
        setattr(func, "_event_types", event_types)

        return func

    return decorator


# ==============================================================================
# Validation Decorators
# ==============================================================================


def validated_handler(
    event_type: str,
    schema: Type[BaseEventSchema],
    *,
    priority: int = 0,
    async_flag: bool = False,
    strict: bool = True,
) -> Callable[[F], F]:
    """
    Decorator that validates event data against a schema before processing.

    :param event_type: Event type to handle
    :param schema: Pydantic schema for validation
    :param strict: Whether to raise exception on validation failure

    Example:
        @validated_handler("ORDER", OrderSchema)
        def handle_order(event: Event):
            # event.data is guaranteed to match OrderSchema
            print(f"Order {event.data['order_id']} received")
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(event: Event) -> Any:
            try:
                # Validate event data
                raw_data = event.data
                if raw_data is None:
                    payload: Mapping[str, Any] = {}
                elif isinstance(raw_data, Mapping):
                    payload = raw_data
                else:
                    raise TypeError(
                        f"Event data for '{event_type}' must be mapping-like, got {type(raw_data)!r}"
                    )
                payload_dict = payload if isinstance(payload, dict) else dict(payload)
                validated_data = schema(**payload_dict)

                # Create new event with validated data
                validated_event = Event(
                    type=event.type, data=validated_data.model_dump(), ts=event.ts
                )

                return func(validated_event)

            except Exception as e:
                logger.error(f"Validation failed for {event_type}: {e}")
                if strict:
                    raise
                # Skip processing if not strict
                return None

        # Apply event_handler decorator
        return cast(F, event_handler(event_type, priority=priority, async_flag=async_flag)(wrapper))

    return decorator


# ==============================================================================
# Performance Decorators
# ==============================================================================


def monitored(
    metric_name: Optional[str] = None, collector: Optional[MetricsCollector] = None
) -> Callable[[F], F]:
    """
    Decorator to monitor handler performance.

    Example:
        @monitored(metric_name="tick_processing")
        @event_handler("TICK")
        def handle_tick(event: Event):
            process_tick(event.data)
    """

    def decorator(func: F) -> F:
        # Use function name as metric if not provided
        name = metric_name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(event: Event) -> Any:
            start_time = time.time()
            success = True

            try:
                result = func(event)
                return result
            except Exception:
                success = False
                raise
            finally:
                duration = time.time() - start_time

                # Record metrics if collector available
                if collector:
                    collector.record_event(
                        event_type=event.type,
                        processing_time=duration,
                        success=success,
                        handler_name=name,
                    )
                else:
                    # Just log if no collector
                    logger.debug(f"{name} took {duration:.3f}s (success={success})")

        return cast(F, wrapper)

    return decorator


def rate_limited(
    max_rate: float = DEFAULT_RATE_LIMIT, *, per_event_type: bool = False
) -> Callable[[F], F]:
    """
    Decorator to rate limit event processing.

    :param max_rate: Maximum events per second
    :param per_event_type: Whether to apply limit per event type

    Example:
        @rate_limited(10)  # Max 10 events per second
        @event_handler("TICK")
        def handle_tick(event: Event):
            process_tick(event.data)
    """

    def decorator(func: F) -> F:
        # Rate limiter state
        if per_event_type:
            last_times: Dict[str, float] = {}
            locks: Dict[str, threading.Lock] = {}
        else:
            last_time = 0.0
            lock = threading.Lock()

        min_interval = 1.0 / max_rate

        @functools.wraps(func)
        def wrapper(event: Event) -> Any:
            if per_event_type:
                # Get or create lock for event type
                if event.type not in locks:
                    locks[event.type] = threading.Lock()
                current_lock = locks[event.type]

                with current_lock:
                    current_time = time.time()
                    last = last_times.get(event.type, 0.0)

                    time_since_last = current_time - last
                    if time_since_last < min_interval:
                        sleep_time = min_interval - time_since_last
                        time.sleep(sleep_time)

                    last_times[event.type] = time.time()
            else:
                nonlocal last_time

                with lock:
                    current_time = time.time()
                    time_since_last = current_time - last_time

                    if time_since_last < min_interval:
                        sleep_time = min_interval - time_since_last
                        time.sleep(sleep_time)

                    last_time = time.time()

            return func(event)

        return cast(F, wrapper)

    return decorator


# ==============================================================================
# Resilience Decorators
# ==============================================================================


def retry_on_error(
    max_retries: int = DEFAULT_RETRY_COUNT,
    delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator to retry handler on failure.

    Example:
        @retry_on_error(max_retries=3, delay=1.0)
        @event_handler("ORDER")
        def handle_order(event: Event):
            submit_order(event.data)  # May fail
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(event: Event) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(event)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Handler {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Handler {func.__name__} failed after {max_retries + 1} attempts"
                        )

            # Re-raise last exception
            if last_exception:
                raise last_exception

        return cast(F, wrapper)

    return decorator


def timeout(seconds: float = DEFAULT_TIMEOUT) -> Callable[[F], F]:
    """
    Decorator to add timeout to handler execution.

    Example:
        @timeout(5.0)  # 5 second timeout
        @event_handler("TRADE")
        def handle_trade(event: Event):
            process_trade(event.data)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(event: Event) -> Any:
            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = func(event)
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                # Thread is still running, timeout occurred
                raise TimeoutError(f"Handler {func.__name__} timed out after {seconds}s")

            if exception[0]:
                raise exception[0]

            return result[0]

        return cast(F, wrapper)

    return decorator


# ==============================================================================
# Conditional Decorators
# ==============================================================================


def conditional_handler(
    condition: Callable[[Event], bool], event_type: str, **kwargs
) -> Callable[[F], F]:
    """
    Decorator to conditionally execute handler based on event data.

    Example:
        @conditional_handler(
            lambda e: e.data.get('price', 0) > 50000,
            "TICK"
        )
        def handle_high_price_tick(event: Event):
            alert_high_price(event.data)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(event: Event) -> Any:
            if condition(event):
                return func(event)
            # Skip if condition not met
            return None

        # Apply event_handler decorator
        return cast(F, event_handler(event_type, **kwargs)(wrapper))

    return decorator


def filter_by_field(
    field: str, values: Union[Any, List[Any]], event_type: str, **kwargs
) -> Callable[[F], F]:
    """
    Decorator to filter events by field value.

    Example:
        @filter_by_field("symbol", ["BTCUSDT", "ETHUSDT"], "TICK")
        def handle_major_pairs(event: Event):
            process_major_pair_tick(event.data)
    """
    # Convert single value to list
    if not isinstance(values, list):
        values = [values]
    values_set = set(values)

    def condition(event: Event) -> bool:
        if isinstance(event.data, dict):
            return event.data.get(field) in values_set
        return False

    return conditional_handler(condition, event_type, **kwargs)


# ==============================================================================
# Transformation Decorators
# ==============================================================================


def transform_event(transformer: Callable[[Event], Event]) -> Callable[[F], F]:
    """
    Decorator to transform event before processing.

    Example:
        def add_timestamp(event: Event) -> Event:
            event.data['processed_at'] = time.time()
            return event

        @transform_event(add_timestamp)
        @event_handler("TICK")
        def handle_tick(event: Event):
            # event.data now has 'processed_at' field
            process_tick(event.data)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(event: Event) -> Any:
            transformed = transformer(event)
            return func(transformed)

        return cast(F, wrapper)

    return decorator


def enrich_event(enricher: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Callable[[F], F]:
    """
    Decorator to enrich event data.

    Example:
        def add_spread(data: dict) -> dict:
            data['spread'] = data.get('ask', 0) - data.get('bid', 0)
            return data

        @enrich_event(add_spread)
        @event_handler("TICK")
        def handle_tick(event: Event):
            print(f"Spread: {event.data['spread']}")
    """

    def transformer(event: Event) -> Event:
        if isinstance(event.data, dict):
            enriched_data = enricher(event.data.copy())
            return Event(type=event.type, data=enriched_data, ts=event.ts)
        return event

    return transform_event(transformer)


# ==============================================================================
# Handler Registration Utilities
# ==============================================================================


def set_engine(engine: EventEngine) -> None:
    """
    Set the global event engine for auto-registration.

    Example:
        engine = EventEngine()
        set_engine(engine)

        # Now all @event_handler decorators will auto-register
    """
    global _engine_registry
    _engine_registry = engine

    # Register all pending handlers
    for event_type, handlers in _handler_registry.items():
        for handler in handlers:
            engine.register(
                event_type=event_type,
                handler=handler,
                priority=getattr(handler, "_priority", 0),
                async_flag=getattr(handler, "_async_flag", False),
            )

    logger.info(f"Registered {sum(len(h) for h in _handler_registry.values())} handlers")


def get_registered_handlers() -> Dict[str, List[Handler]]:
    """Get all registered handlers"""
    return _handler_registry.copy()


def clear_handlers() -> None:
    """Clear all registered handlers"""
    global _handler_registry
    _handler_registry.clear()


# ==============================================================================
# Combined Decorators
# ==============================================================================


def robust_handler(
    event_type: str,
    *,
    schema: Optional[Type[BaseEventSchema]] = None,
    max_retries: int = DEFAULT_RETRY_COUNT,
    timeout_seconds: float = DEFAULT_TIMEOUT,
    rate_limit: Optional[float] = None,
    monitor: bool = True,
    **kwargs,
) -> Callable[[F], F]:
    """
    Combined decorator for robust event handling.

    Applies multiple decorators in the correct order:
    1. Monitoring
    2. Timeout
    3. Retry
    4. Rate limiting
    5. Validation
    6. Event handler registration

    Example:
        @robust_handler(
            "ORDER",
            schema=OrderSchema,
            max_retries=3,
            timeout_seconds=10.0,
            rate_limit=50,
            priority=10
        )
        def handle_order(event: Event):
            submit_order(event.data)
    """

    def decorator(func: F) -> F:
        # Build decorator chain from inside out
        handler = func

        # Apply validation if schema provided
        if schema:
            handler = validated_handler(event_type, schema, strict=True)(handler)
        else:
            # Just register as event handler
            handler = cast(F, event_handler(event_type, **kwargs)(handler))

        # Apply rate limiting if specified
        if rate_limit:
            handler = rate_limited(rate_limit)(handler)

        # Apply retry logic
        handler = retry_on_error(max_retries=max_retries)(handler)

        # Apply timeout
        handler = timeout(timeout_seconds)(handler)

        # Apply monitoring if requested
        if monitor:
            handler = monitored()(handler)

        return handler

    return decorator


# ==============================================================================
# Module Summary
# ==============================================================================
"""
Event System Decorators Module

This module provides a rich set of decorators for enhanced developer experience:

1. Core Decorators:
   - @event_handler: Basic event handler registration
   - @multi_event_handler: Handle multiple event types
   - set_engine(): Set global engine for auto-registration

2. Validation:
   - @validated_handler: Schema validation with Pydantic
   - Automatic data validation and type checking

3. Performance:
   - @monitored: Track handler performance metrics
   - @rate_limited: Limit processing rate

4. Resilience:
   - @retry_on_error: Automatic retry with backoff
   - @timeout: Prevent handler hanging

5. Conditional:
   - @conditional_handler: Execute based on conditions
   - @filter_by_field: Filter by event field values

6. Transformation:
   - @transform_event: Transform events before processing
   - @enrich_event: Add computed fields to event data

7. Combined:
   - @robust_handler: All-in-one decorator for production use

Usage Example:
    from core.event.decorators import event_handler, set_engine, robust_handler
    from core.event.schema import TickSchema

    # Set global engine
    set_engine(event_engine)

    # Simple handler
    @event_handler("TICK", priority=10, async_flag=True)
    def handle_tick(event: Event):
        print(f"Price: {event.data['price']}")

    # Robust handler with all features
    @robust_handler(
        "TICK",
        schema=TickSchema,
        max_retries=3,
        timeout_seconds=5.0,
        rate_limit=100,
        priority=20
    )
    def handle_critical_tick(event: Event):
        process_critical_tick(event.data)
"""
