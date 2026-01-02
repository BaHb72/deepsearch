"""
Redis configuration models.
"""

from typing import Optional

from pydantic import BaseModel

# Default values (previously from deepsearch.constants)
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_KEY_PREFIX = "deepsearch:"


class RedisConfig(BaseModel):
    """Redis connection and storage configuration."""

    host: str = DEFAULT_REDIS_HOST
    port: int = DEFAULT_REDIS_PORT
    db: int = DEFAULT_REDIS_DB
    username: Optional[str] = None
    password: Optional[str] = None
    key_prefix: str = DEFAULT_KEY_PREFIX + "ts:"
    retention_ms: int = 86400000  # 24 hours
    duplicate_policy: str = "LAST"
