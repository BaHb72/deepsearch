"""
Event Schema Management Module

This module provides a comprehensive schema validation system for events in the DeepSearch platform.
It enables type safety, automatic validation, and clear documentation of event structures.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Mapping, Optional, Type, TypeVar, cast

from pydantic import BaseModel, Field, ValidationError, validator
from pydantic.json_schema import JsonSchemaValue

from deepsearch.observability import get_logger

from .const import EVENT_ACCOUNT, EVENT_ORDER, EVENT_POSITION, EVENT_TICK, EVENT_TRADE
from .engine import Event

# ==============================================================================
# Constants
# ==============================================================================

SCHEMA_VERSION = "1.0.0"
DEFAULT_SCHEMA_REGISTRY_SIZE = 1000
VALIDATION_ERROR_LIMIT = 10

# ==============================================================================
# Type Variables and Logger
# ==============================================================================

logger = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)
HandlerFunc = TypeVar("HandlerFunc", bound=Callable[["Event"], Any])


# ==============================================================================
# Schema Registry
# ==============================================================================


class SchemaRegistry:
    """
    Central registry for all event schemas.
    Provides schema registration, lookup, and validation capabilities.
    """

    def __init__(self, max_size: int = DEFAULT_SCHEMA_REGISTRY_SIZE):
        self._schemas: Dict[str, Type[BaseModel]] = {}
        self._max_size = max_size
        self._validation_stats: Dict[str, Dict[str, int]] = {}

    def register(self, event_type: str, schema: Type[BaseModel]) -> None:
        """Register a schema for an event type"""
        if len(self._schemas) >= self._max_size:
            raise ValueError(f"Schema registry full (max size: {self._max_size})")

        if not issubclass(schema, BaseModel):
            raise TypeError(f"Schema must be a Pydantic BaseModel, got {type(schema)}")

        self._schemas[event_type] = schema
        self._validation_stats[event_type] = {"success": 0, "failure": 0}
        logger.info(f"Registered schema for event type: {event_type}")

    def unregister(self, event_type: str) -> None:
        """Unregister a schema"""
        if event_type in self._schemas:
            del self._schemas[event_type]
            del self._validation_stats[event_type]
            logger.info(f"Unregistered schema for event type: {event_type}")

    def get_schema(self, event_type: str) -> Optional[Type[BaseModel]]:
        """Get schema for an event type"""
        return self._schemas.get(event_type)

    def validate(self, event_type: str, data: Dict[str, Any]) -> BaseModel:
        """Validate data against registered schema"""
        schema = self.get_schema(event_type)
        if not schema:
            raise ValueError(f"No schema registered for event type: {event_type}")

        try:
            validated = schema(**data)
            self._validation_stats[event_type]["success"] += 1
            return validated
        except ValidationError as e:
            self._validation_stats[event_type]["failure"] += 1
            logger.error(f"Validation failed for {event_type}: {e}")
            raise

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get validation statistics"""
        return self._validation_stats.copy()

    def list_schemas(self) -> List[str]:
        """List all registered event types"""
        return list(self._schemas.keys())

    def export_schemas(self) -> Dict[str, JsonSchemaValue]:
        """Export all schemas as JSON Schema"""
        exported: Dict[str, JsonSchemaValue] = {}
        for event_type, schema in self._schemas.items():
            schema_cls = cast("type[BaseModel]", schema)
            json_schema = cast(Callable[[], JsonSchemaValue], schema_cls.model_json_schema)
            exported[event_type] = json_schema()
        return exported


# ==============================================================================
# Base Event Schemas
# ==============================================================================


class BaseEventSchema(BaseModel):
    """Base schema for all events"""

    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    source: str = Field(..., description="Event source identifier")
    sequence: Optional[int] = Field(None, description="Event sequence number")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for event tracking")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MarketDataSchema(BaseEventSchema):
    """Base schema for market data events"""

    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")


class TradingSchema(BaseEventSchema):
    """Base schema for trading events"""

    account_id: str = Field(..., description="Trading account ID")
    strategy_id: Optional[str] = Field(None, description="Strategy identifier")


# ==============================================================================
# Specific Event Schemas
# ==============================================================================


class TickSchema(MarketDataSchema):
    """Schema for tick/price events"""

    bid_price: float = Field(..., description="Best bid price")
    ask_price: float = Field(..., description="Best ask price")
    bid_volume: float = Field(..., ge=0, description="Bid volume")
    ask_volume: float = Field(..., ge=0, description="Ask volume")
    last_price: Optional[float] = Field(None, description="Last traded price")
    last_volume: Optional[float] = Field(None, ge=0, description="Last traded volume")
    open_interest: Optional[float] = Field(None, ge=0, description="Open interest (for futures)")

    @validator("ask_price")
    def validate_spread(cls, v, values):
        """Ensure ask >= bid"""
        if "bid_price" in values and v < values["bid_price"]:
            raise ValueError("Ask price must be >= bid price")
        return v


class OrderStatus(str, Enum):
    """Order status enumeration"""

    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(str, Enum):
    """Order type enumeration"""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    """Order side enumeration"""

    BUY = "buy"
    SELL = "sell"


class OrderSchema(TradingSchema):
    """Schema for order events"""

    order_id: str = Field(..., description="Unique order identifier")
    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")
    order_type: OrderType = Field(..., description="Order type")
    side: OrderSide = Field(..., description="Order side")
    price: Optional[float] = Field(None, description="Order price (for limit orders)")
    quantity: float = Field(..., gt=0, description="Order quantity")
    filled_quantity: float = Field(0, ge=0, description="Filled quantity")
    status: OrderStatus = Field(..., description="Order status")
    time_in_force: str = Field("GTC", description="Time in force")
    stop_price: Optional[float] = Field(None, description="Stop price (for stop orders)")

    @validator("filled_quantity")
    def validate_filled(cls, v, values):
        """Ensure filled <= quantity"""
        if "quantity" in values and v > values["quantity"]:
            raise ValueError("Filled quantity cannot exceed order quantity")
        return v


class TradeSchema(TradingSchema):
    """Schema for trade/execution events"""

    trade_id: str = Field(..., description="Unique trade identifier")
    order_id: str = Field(..., description="Associated order ID")
    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")
    side: OrderSide = Field(..., description="Trade side")
    price: float = Field(..., gt=0, description="Execution price")
    quantity: float = Field(..., gt=0, description="Execution quantity")
    commission: float = Field(0, ge=0, description="Commission amount")
    commission_asset: Optional[str] = Field(None, description="Commission currency")


class PositionSchema(TradingSchema):
    """Schema for position events"""

    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")
    quantity: float = Field(..., description="Position quantity (negative for short)")
    average_price: float = Field(..., gt=0, description="Average entry price")
    market_price: float = Field(..., gt=0, description="Current market price")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")
    realized_pnl: float = Field(0, description="Realized P&L")
    margin_used: Optional[float] = Field(None, ge=0, description="Margin used")


class AccountSchema(TradingSchema):
    """Schema for account update events"""

    balance: float = Field(..., description="Account balance")
    available_balance: float = Field(..., description="Available balance")
    margin_used: float = Field(0, ge=0, description="Total margin used")
    unrealized_pnl: float = Field(0, description="Total unrealized P&L")
    realized_pnl: float = Field(0, description="Total realized P&L")
    positions: List[Dict[str, Any]] = Field(default_factory=list, description="Position summary")

    @validator("available_balance")
    def validate_available(cls, v, values):
        """Ensure available <= balance"""
        if "balance" in values and v > values["balance"]:
            raise ValueError("Available balance cannot exceed total balance")
        return v


# ==============================================================================
# Schema Validation Decorators
# ==============================================================================


def schema_validated(
    event_type: str, schema: Type[BaseModel]
) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to add schema validation to event handlers"""

    def decorator(func: HandlerFunc) -> HandlerFunc:
        @wraps(func)
        def wrapper(event: Event):
            # Validate event data against schema
            payload = event.data
            if isinstance(payload, BaseModel):
                payload_data: Mapping[str, Any] = payload.model_dump()
            elif isinstance(payload, Mapping):
                payload_data = dict(payload)
            elif payload is None:
                payload_data = {}
            else:
                error_message = (
                    f"事件数据必须为映射或 BaseModel，当前类型: {type(payload).__name__}"
                )
                logger.error(error_message)
                raise TypeError(error_message)

            try:
                validated_data = schema.model_validate(payload_data)
                validated_payload: Dict[str, Any] = validated_data.model_dump()
                # Create new event with validated data
                ts_value = getattr(event, "ts", None)
                if ts_value is None and hasattr(event, "timestamp"):
                    maybe_ts = getattr(event, "timestamp")
                    if isinstance(maybe_ts, (int, float)):
                        ts_value = maybe_ts
                if ts_value is None:
                    validated_event = Event(type=event.type, data=validated_payload)
                else:
                    validated_event = Event(type=event.type, data=validated_payload, ts=ts_value)
                return func(validated_event)
            except ValidationError as e:
                logger.error(f"Schema validation failed for {event_type}: {e}")
                raise

        setattr(wrapper, "_event_schema", schema)
        setattr(wrapper, "_event_type", event_type)
        return cast(HandlerFunc, wrapper)

    return decorator


# ==============================================================================
# Schema Builder for Dynamic Schemas
# ==============================================================================


class SchemaBuilder:
    """Builder for creating schemas dynamically"""

    def __init__(self, name: str, base: Type[BaseModel] = BaseEventSchema):
        self._name = name
        self._fields: Dict[str, tuple] = {}
        self._validators: Dict[str, Any] = {}
        self._base = base

    def add_field(
        self, name: str, type_: Type, default: Any = ..., description: str = "", **kwargs
    ) -> "SchemaBuilder":
        """Add a field to the schema"""
        field_info = Field(default, description=description, **kwargs)
        self._fields[name] = (type_, field_info)
        return self

    def add_validator(self, field: str, func: Callable[..., Any]) -> "SchemaBuilder":
        """Add a validator for a field"""
        self._validators[f"validate_{field}"] = validator(field)(func)
        return self

    def build(self) -> Type[BaseModel]:
        """Build the schema class"""
        # Create class attributes
        annotations = {name: type_ for name, (type_, _) in self._fields.items()}
        field_definitions = {name: field for name, (_, field) in self._fields.items()}
        attrs = {
            "__module__": __name__,
            "__annotations__": annotations,
            **field_definitions,
            **self._validators,
        }

        # Create the schema class
        schema_class = type(self._name, (self._base,), attrs)
        return schema_class


# ==============================================================================
# Global Schema Registry Instance
# ==============================================================================

# Create global registry
schema_registry = SchemaRegistry()

# Register default schemas
schema_registry.register(EVENT_TICK, TickSchema)
schema_registry.register(EVENT_ORDER, OrderSchema)
schema_registry.register(EVENT_TRADE, TradeSchema)
schema_registry.register(EVENT_POSITION, PositionSchema)
schema_registry.register(EVENT_ACCOUNT, AccountSchema)


# ==============================================================================
# Schema Migration Support
# ==============================================================================


class SchemaMigration(ABC):
    """Base class for schema migrations"""

    @property
    @abstractmethod
    def from_version(self) -> str:
        """Source schema version"""
        pass

    @property
    @abstractmethod
    def to_version(self) -> str:
        """Target schema version"""
        pass

    @abstractmethod
    def migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate data from old schema to new schema"""
        pass


class SchemaMigrationRegistry:
    """Registry for schema migrations"""

    def __init__(self):
        self._migrations: Dict[tuple[str, str], SchemaMigration] = {}

    def register(self, migration: SchemaMigration) -> None:
        """Register a migration"""
        key = (migration.from_version, migration.to_version)
        self._migrations[key] = migration

    def migrate(self, data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Apply migration to data"""
        key = (from_version, to_version)
        migration = self._migrations.get(key)

        if not migration:
            raise ValueError(f"No migration found from {from_version} to {to_version}")

        return migration.migrate(data)


# ==============================================================================
# Module Summary
# ==============================================================================
"""
Event Schema Management System

This module provides comprehensive schema validation for the event system:

1. Schema Registry:
   - Central registry for all event schemas
   - Schema registration and lookup
   - Validation statistics tracking
   - JSON Schema export

2. Base Schemas:
   - BaseEventSchema: Common fields for all events
   - MarketDataSchema: Base for market data events
   - TradingSchema: Base for trading events

3. Specific Event Schemas:
   - TickSchema: Price/quote data validation
   - OrderSchema: Order event validation
   - TradeSchema: Trade execution validation
   - PositionSchema: Position update validation
   - AccountSchema: Account state validation

4. Schema Validation:
   - Decorator for automatic validation
   - Type safety and data consistency
   - Custom validators for business rules

5. Dynamic Schema Building:
   - SchemaBuilder for runtime schema creation
   - Flexible field and validator addition

6. Schema Migration:
   - Support for schema versioning
   - Migration registry for upgrades

Usage Example:
    from deepsearch.event.schema import schema_registry, schema_validated, TickSchema

    # Validate event data
    tick_data = {"symbol": "BTCUSDT", "exchange": "Binance", ...}
    validated = schema_registry.validate(EVENT_TICK, tick_data)

    # Use decorator for automatic validation
    @schema_validated(EVENT_TICK, TickSchema)
    def handle_tick(event: Event):
        # Event data is already validated
        process_tick(event.data)
"""
