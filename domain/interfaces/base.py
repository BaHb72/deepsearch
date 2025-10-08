"""领域事件基础协议。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DomainEvent:
    """领域事件基类，占位以支撑 mypy 检查。"""

    event_name: str
    aggregate_id: str
    occurred_at: datetime
