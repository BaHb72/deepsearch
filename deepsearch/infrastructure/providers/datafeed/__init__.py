"""DataFeed abstractions for DeepSearch.

Provides a thin adapter layer between internal data model and various data sources
(similar to vn.py's datafeed concept). Start with AkShare-backed implementation.
"""

from .akshare import AkShareDataFeed
from .base import IDataFeed, KlineParams

__all__ = [
    "IDataFeed",
    "KlineParams",
    "AkShareDataFeed",
]
