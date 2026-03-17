from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class BackendRuntime:
    """后端运行时真源，集中保存关键基础设施句柄。"""

    provider_container: Any = None
    dask_init_manager: Any = None
    db_component: Any = None
    db_service: Any = None
    notification_service: Any = None
    market_data_orchestrator: Any = None
    market_data_fallback_manager: Any = None
    market_data_service: Any = None
