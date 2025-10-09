"""领域接口命名空间。"""

from .base import DomainEvent
from .repository import IStockRepository, IUnitOfWork, PageRequest, PageResult
from .services import IEventPublisher

__all__ = [
    "DomainEvent",
    "IStockRepository",
    "IUnitOfWork",
    "PageRequest",
    "PageResult",
    "IEventPublisher",
]
