"""
Redis configuration models.
"""
from typing import Optional

from pydantic import BaseModel

from deepsearch.constants import (
    DEFAULT_KEY_PREFIX,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
)


class RedisConfig(BaseModel):
    """Redis connection and storage configuration."""
    host: str = DEFAULT_REDIS_HOST
    port: int = DEFAULT_REDIS_PORT
    db: int = DEFAULT_REDIS_DB
    password: Optional[str] = None
    key_prefix: str = DEFAULT_KEY_PREFIX + "ts:"
    retention_ms: int = 86400000  # 24 hours
    duplicate_policy: str = "LAST"
