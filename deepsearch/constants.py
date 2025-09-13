"""
Core constants for DeepSearch.
"""

# Application constants
APP_NAME = "DeepSearch"
APP_AUTHOR = "DeepSearch Team"
DEFAULT_ENCODING = "utf-8"
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

# Port constants
DEFAULT_WEBUI_PORT = 8000
DEFAULT_FRONTEND_PORT = 3000
DEFAULT_ZMQ_PUB_PORT = 5556
DEFAULT_ZMQ_SUB_PORT = 5557

# Environment constants
ENV_DEVELOPMENT = "development"
ENV_PRODUCTION = "production"
ENV_TEST = "test"

# Log levels
LOG_DEBUG = "DEBUG"
LOG_INFO = "INFO"
LOG_WARNING = "WARNING"
LOG_ERROR = "ERROR"
LOG_CRITICAL = "CRITICAL"

# Database constants
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 3600

# Cache constants
CACHE_TTL = 300  # 5 minutes
CACHE_MAX_SIZE = 1000

# API constants
API_VERSION = "v1"
API_PREFIX = "/api"

# Data source priorities
DATA_SOURCE_PRIORITY = {
    "amazingdata": 1,
    "cloudflare": 2,
    "qmt": 3,
    "akshare": 4
}