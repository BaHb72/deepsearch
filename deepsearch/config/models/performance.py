"""
Performance configuration models.
"""
from pydantic import BaseModel

from deepsearch.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_WORKERS,
    DEFAULT_QUEUE_SIZE,
)


class PerformanceConfig(BaseModel):
    """Performance configuration."""
    max_workers: int = DEFAULT_MAX_WORKERS
    queue_size: int = DEFAULT_QUEUE_SIZE
    batch_size: int = DEFAULT_BATCH_SIZE
