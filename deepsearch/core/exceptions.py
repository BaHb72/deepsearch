"""
Custom exceptions for DeepSearch application.

This module defines a hierarchy of exceptions for better error handling
and debugging throughout the application.
"""
from typing import Any, Dict, Optional


class DeepSearchError(Exception):
    """
    Base exception for all DeepSearch errors.
    
    All custom exceptions should inherit from this class to allow
    catching all DeepSearch-specific errors with a single except clause.
    """

    def __init__(
            self,
            message: str,
            error_code: Optional[int] = None,
            details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize DeepSearch error.
        
        Args:
            message: Error message
            error_code: Optional error code for programmatic handling
            details: Optional dictionary with additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


# ==============================================================================
# Configuration Errors
# ==============================================================================


class ConfigurationError(DeepSearchError):
    """Raised when there's an issue with configuration."""
    pass


class InvalidConfigError(ConfigurationError):
    """Raised when configuration values are invalid."""
    pass


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing."""
    pass


# ==============================================================================
# Validation Errors
# ==============================================================================


class ValidationError(DeepSearchError):
    """Raised when data validation fails."""
    pass


class SchemaValidationError(ValidationError):
    """Raised when event data doesn't match schema."""
    pass


class FieldValidationError(ValidationError):
    """Raised when a specific field fails validation."""

    def __init__(self, field: str, value: Any, reason: str, **kwargs):
        super().__init__(
            f"Field '{field}' validation failed: {reason}",
            details={"field": field, "value": value, "reason": reason},
            **kwargs
        )


# ==============================================================================
# Connection Errors
# ==============================================================================


class ConnectionError(DeepSearchError):
    """Raised when connection to external service fails."""
    pass


class NetworkError(ConnectionError):
    """Raised when network communication fails."""
    pass


class TimeoutError(ConnectionError):
    """Raised when operation times out."""
    pass


class AuthenticationError(ConnectionError):
    """Raised when authentication fails."""
    pass


# ==============================================================================
# Event System Errors
# ==============================================================================


class EventError(DeepSearchError):
    """Base class for event system errors."""
    pass


class EventQueueFullError(EventError):
    """Raised when event queue is full."""
    pass


class EventHandlerError(EventError):
    """Raised when event handler fails."""

    def __init__(self, handler_name: str, event_type: str, original_error: Exception, **kwargs):
        super().__init__(
            f"Handler '{handler_name}' failed for event '{event_type}': {original_error}",
            details={
                "handler": handler_name,
                "event_type": event_type,
                "original_error": str(original_error)
            },
            **kwargs
        )


class EventValidationError(EventError):
    """Raised when event validation fails."""
    pass


# ==============================================================================
# Storage Errors
# ==============================================================================


class StorageError(DeepSearchError):
    """Base class for storage-related errors."""
    pass


class StorageConnectionError(StorageError):
    """Raised when connection to storage fails."""
    pass


class StorageReadError(StorageError):
    """Raised when reading from storage fails."""
    pass


class StorageWriteError(StorageError):
    """Raised when writing to storage fails."""
    pass


class StorageNotFoundError(StorageError):
    """Raised when requested data is not found in storage."""
    pass


# ==============================================================================
# Gateway Errors
# ==============================================================================


class GatewayError(DeepSearchError):
    """Base class for gateway-related errors."""
    pass


class GatewayConnectionError(GatewayError):
    """Raised when gateway connection fails."""
    pass


class GatewayAuthError(GatewayError):
    """Raised when gateway authentication fails."""
    pass


class GatewayOrderError(GatewayError):
    """Raised when order submission fails."""

    def __init__(self, order_id: str, reason: str, **kwargs):
        super().__init__(
            f"Order '{order_id}' failed: {reason}",
            details={"order_id": order_id, "reason": reason},
            **kwargs
        )


class GatewayDataError(GatewayError):
    """Raised when market data reception fails."""
    pass


# ==============================================================================
# Trading Errors
# ==============================================================================


class TradingError(DeepSearchError):
    """Base class for trading-related errors."""
    pass


class InsufficientBalanceError(TradingError):
    """Raised when account has insufficient balance."""

    def __init__(self, required: float, available: float, currency: str, **kwargs):
        super().__init__(
            f"Insufficient {currency} balance: required {required}, available {available}",
            details={
                "required": required,
                "available": available,
                "currency": currency
            },
            **kwargs
        )


class PositionLimitError(TradingError):
    """Raised when position limit is exceeded."""
    pass


class RiskLimitError(TradingError):
    """Raised when risk limit is exceeded."""
    pass


class InvalidOrderError(TradingError):
    """Raised when order parameters are invalid."""
    pass


# ==============================================================================
# System Errors
# ==============================================================================


class SystemError(DeepSearchError):
    """Base class for system-level errors."""
    pass


class StartupError(SystemError):
    """Raised when system startup fails."""
    pass


class ShutdownError(SystemError):
    """Raised when system shutdown fails."""
    pass


class ResourceError(SystemError):
    """Raised when system resource is unavailable."""
    pass


# ==============================================================================
# Utility Functions
# ==============================================================================


def reraise_with_context(original_error: Exception, context: str, **details) -> None:
    """
    Re-raise an exception with additional context.
    
    Args:
        original_error: The original exception
        context: Additional context message
        **details: Additional details to include
    """
    error_class = type(original_error)

    # If it's already a DeepSearchError, preserve its details
    if isinstance(original_error, DeepSearchError):
        original_error.message = f"{context}: {original_error.message}"
        original_error.details.update(details)
        raise original_error

    # Otherwise, wrap it in a DeepSearchError
    raise DeepSearchError(
        f"{context}: {original_error}",
        details={
            "original_error": str(original_error),
            "original_type": error_class.__name__,
            **details
        }
    ) from original_error
