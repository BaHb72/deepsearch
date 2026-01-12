from datetime import datetime, timedelta
from typing import Any, Optional, Union

class IntervalTrigger:
    def __init__(
        self,
        weeks: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        timezone: Any = None,
        jitter: Optional[int] = None,
    ) -> None: ...
    def get_next_fire_time(
        self, previous_fire_time: Optional[datetime], now: datetime
    ) -> Optional[datetime]: ...
