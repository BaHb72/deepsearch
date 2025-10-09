"""
DeepSearch 应用程序的系统级常量。

本模块包含与系统配置、性能调优和基础设施设置相关的常量。
"""

# ==============================================================================
# 应用程序信息
# ==============================================================================

APP_NAME = "DeepSearch"
APP_AUTHOR = "BaHb"

# ==============================================================================
# 系统常量
# ==============================================================================

# 编码
DEFAULT_ENCODING = "utf-8"

# 超时时间（秒）
DEFAULT_TIMEOUT = 30.0
CONNECTION_TIMEOUT = 10.0
SHUTDOWN_TIMEOUT = 5.0

# 重试
MAX_RETRIES = 3
RETRY_DELAY = 1.0
RETRY_BACKOFF = 2.0

# ==============================================================================
# 性能常量
# ==============================================================================

# 队列大小
DEFAULT_QUEUE_SIZE = 10000
MAX_QUEUE_SIZE = 100000

# 线程池
DEFAULT_MAX_WORKERS = 32
MIN_WORKERS = 1
MAX_WORKERS = 128

# 批处理
DEFAULT_BATCH_SIZE = 100
MAX_BATCH_SIZE = 1000
DEFAULT_BATCH_TIMEOUT = 0.1  # 100毫秒

# 速率限制
DEFAULT_RATE_LIMIT = 1000  # 每秒请求数
MAX_RATE_LIMIT = 10000

# ==============================================================================
# 网络常量
# ==============================================================================

# 默认端口
DEFAULT_ZMQ_PUB_PORT = 5556
DEFAULT_ZMQ_SUB_PORT = 5557
DEFAULT_HTTP_PORT = 8080
DEFAULT_WEBSOCKET_PORT = 8081

# 缓冲区大小
DEFAULT_SEND_BUFFER = 1000
DEFAULT_RECV_BUFFER = 1000

# ==============================================================================
# 存储常量
# ==============================================================================

# Redis
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_KEY_PREFIX = "deepsearch:"

# 数据保留
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365

# ==============================================================================
# 监控常量
# ==============================================================================

# 指标
METRICS_WINDOW_SIZE = 300  # 5分钟
METRICS_EXPORT_INTERVAL = 60  # 1分钟

# 健康检查
HEALTH_CHECK_INTERVAL = 60  # 1分钟
HEALTH_CHECK_TIMEOUT = 5.0

# 慢事件阈值
SLOW_EVENT_THRESHOLD = 1.0  # 1秒

# ==============================================================================
# 文件系统常量
# ==============================================================================

# 文件扩展名
YAML_EXTENSION = ".yaml"
JSON_EXTENSION = ".json"
LOG_EXTENSION = ".log"

# 文件大小限制
MAX_CONFIG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# ==============================================================================
# 错误码
# ==============================================================================

# 系统错误 (1000-1999)
ERROR_SYSTEM_GENERAL = 1000
ERROR_SYSTEM_CONFIG = 1001
ERROR_SYSTEM_STARTUP = 1002
ERROR_SYSTEM_SHUTDOWN = 1003

# 事件错误 (2000-2999)
ERROR_EVENT_INVALID = 2000
ERROR_EVENT_HANDLER = 2001
ERROR_EVENT_QUEUE_FULL = 2002
ERROR_EVENT_TIMEOUT = 2003

# 存储错误 (3000-3999)
ERROR_STORAGE_CONNECTION = 3000
ERROR_STORAGE_READ = 3001
ERROR_STORAGE_WRITE = 3002
ERROR_STORAGE_DELETE = 3003

# 网关错误 (4000-4999)
ERROR_GATEWAY_CONNECTION = 4000
ERROR_GATEWAY_AUTH = 4001
ERROR_GATEWAY_ORDER = 4002
ERROR_GATEWAY_DATA = 4003

# 交易错误 (5000-5999)
ERROR_TRADE_INVALID_ORDER = 5000
ERROR_TRADE_INSUFFICIENT_BALANCE = 5001
ERROR_TRADE_POSITION_LIMIT = 5002
ERROR_TRADE_RISK_LIMIT = 5003
