"""
Facade for the process-isolated AmazingData provider.

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Use ``deepsearch.domain.data_proxy.adapters.AmazingDataAdapter`` with Dask Actor instead.

    Migration guide:
    1. Import the new adapter: ``from deepsearch.domain.data_proxy import get_data_proxy``
    2. Use ``proxy = get_data_proxy()`` to get unified data access
    3. Use ``await proxy.get_kline(...)`` instead of direct SDK calls

This module serves as the primary entry point for the process-isolated implementation
of the AmazingData provider. It re-exports the necessary runtime classes and
configuration constants to ensure a unified import interface.
"""

from __future__ import annotations

import warnings

from .common import DEFAULT_HIST_CODE_LIST_START
from .process.runtime import (
    AmazingDataLoginManager,
    ProcessIsolatedAmazingDataProvider,
    SnapshotAlignPolicy,
)

# 导入时发出废弃警告
warnings.warn(
    "ProcessIsolatedAmazingDataProvider is deprecated. "
    "Use deepsearch.domain.data_proxy.adapters.AmazingDataAdapter instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "AmazingDataLoginManager",
    "DEFAULT_HIST_CODE_LIST_START",
    "ProcessIsolatedAmazingDataProvider",
    "SnapshotAlignPolicy",
]
