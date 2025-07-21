"""
Global constants for DeepSearch application.

This module centralizes all application-wide constants to ensure
consistency and ease of maintenance.
"""

# ==============================================================================
# Application Information
# ==============================================================================

APP_NAME = "DeepSearch"
APP_AUTHOR = "BaHb"

# ==============================================================================
# System Constants
# ==============================================================================

# Encoding
DEFAULT_ENCODING = "utf-8"

# Timeouts (in seconds)
DEFAULT_TIMEOUT = 30.0
CONNECTION_TIMEOUT = 10.0
SHUTDOWN_TIMEOUT = 5.0

# Retries
MAX_RETRIES = 3
RETRY_DELAY = 1.0
RETRY_BACKOFF = 2.0

# ==============================================================================
# Performance Constants
# ==============================================================================

# Queue sizes
DEFAULT_QUEUE_SIZE = 10000
MAX_QUEUE_SIZE = 100000

# Thread pool
DEFAULT_MAX_WORKERS = 32
MIN_WORKERS = 1
MAX_WORKERS = 128

# Batch processing
DEFAULT_BATCH_SIZE = 100
MAX_BATCH_SIZE = 1000
DEFAULT_BATCH_TIMEOUT = 0.1  # 100ms

# Rate limiting
DEFAULT_RATE_LIMIT = 1000  # requests per second
MAX_RATE_LIMIT = 10000

# ==============================================================================
# Network Constants
# ==============================================================================

# Default ports
DEFAULT_ZMQ_PUB_PORT = 5556
DEFAULT_ZMQ_SUB_PORT = 5557
DEFAULT_HTTP_PORT = 8080
DEFAULT_WEBSOCKET_PORT = 8081

# Buffer sizes
DEFAULT_SEND_BUFFER = 1000
DEFAULT_RECV_BUFFER = 1000

# ==============================================================================
# Storage Constants
# ==============================================================================

# Redis
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_KEY_PREFIX = "deepsearch:"

# Data retention
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365

# ==============================================================================
# Monitoring Constants
# ==============================================================================

# Metrics
METRICS_WINDOW_SIZE = 300  # 5 minutes
METRICS_EXPORT_INTERVAL = 60  # 1 minute

# Health check
HEALTH_CHECK_INTERVAL = 60  # 1 minute
HEALTH_CHECK_TIMEOUT = 5.0

# Slow event threshold
SLOW_EVENT_THRESHOLD = 1.0  # 1 second

# ==============================================================================
# File System Constants
# ==============================================================================

# File extensions
YAML_EXTENSION = ".yaml"
JSON_EXTENSION = ".json"
LOG_EXTENSION = ".log"

# File size limits
MAX_CONFIG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# ==============================================================================
# Trading Constants
# ==============================================================================

# Order types
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_STOP = "STOP"
ORDER_TYPE_STOP_LIMIT = "STOP_LIMIT"

# Order sides
ORDER_SIDE_BUY = "BUY"
ORDER_SIDE_SELL = "SELL"

# Order status
ORDER_STATUS_PENDING = "PENDING"
ORDER_STATUS_SUBMITTED = "SUBMITTED"
ORDER_STATUS_PARTIAL = "PARTIAL"
ORDER_STATUS_FILLED = "FILLED"
ORDER_STATUS_CANCELLED = "CANCELLED"
ORDER_STATUS_REJECTED = "REJECTED"

# Position sides
POSITION_SIDE_LONG = "LONG"
POSITION_SIDE_SHORT = "SHORT"
POSITION_SIDE_FLAT = "FLAT"

# ==============================================================================
# Validation Constants
# ==============================================================================

# Field limits
MAX_SYMBOL_LENGTH = 20
MAX_ORDER_ID_LENGTH = 64
MAX_ACCOUNT_ID_LENGTH = 32

# Numeric limits
MIN_PRICE = 0.0000001
MAX_PRICE = 999999999.99999999
MIN_QUANTITY = 0.00000001
MAX_QUANTITY = 999999999.99999999

# ==============================================================================
# Error Codes
# ==============================================================================

# System errors (1000-1999)
ERROR_SYSTEM_GENERAL = 1000
ERROR_SYSTEM_CONFIG = 1001
ERROR_SYSTEM_STARTUP = 1002
ERROR_SYSTEM_SHUTDOWN = 1003

# Event errors (2000-2999)
ERROR_EVENT_INVALID = 2000
ERROR_EVENT_HANDLER = 2001
ERROR_EVENT_QUEUE_FULL = 2002
ERROR_EVENT_TIMEOUT = 2003

# Storage errors (3000-3999)
ERROR_STORAGE_CONNECTION = 3000
ERROR_STORAGE_READ = 3001
ERROR_STORAGE_WRITE = 3002
ERROR_STORAGE_DELETE = 3003

# Gateway errors (4000-4999)
ERROR_GATEWAY_CONNECTION = 4000
ERROR_GATEWAY_AUTH = 4001
ERROR_GATEWAY_ORDER = 4002
ERROR_GATEWAY_DATA = 4003

# Trading errors (5000-5999)
ERROR_TRADE_INVALID_ORDER = 5000
ERROR_TRADE_INSUFFICIENT_BALANCE = 5001
ERROR_TRADE_POSITION_LIMIT = 5002
ERROR_TRADE_RISK_LIMIT = 5003
