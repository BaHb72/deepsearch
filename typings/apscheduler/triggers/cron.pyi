from datetime import datetime
from typing import Any, Optional, Sequence, Union

class CronTrigger:
    def __init__(
        self,
        year: Optional[Union[int, str]] = None,
        month: Optional[Union[int, str]] = None,
        day: Optional[Union[int, str]] = None,
        week: Optional[Union[int, str]] = None,
        day_of_week: Optional[Union[int, str]] = None,
        hour: Optional[Union[int, str]] = None,
        minute: Optional[Union[int, str]] = None,
        second: Optional[Union[int, str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        timezone: Any = None,
        jitter: Optional[int] = None,
    ) -> None: ...
    def get_next_fire_time(
        self, previous_fire_time: Optional[datetime], now: datetime
    ) -> Optional[datetime]: ...
