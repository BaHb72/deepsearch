"""Unified loader for AmazingData SDK to avoid duplicate imports"""

from __future__ import annotations

import importlib
import os
from types import ModuleType
from typing import Optional

from loguru import logger

ad: Optional[ModuleType]
HAS_AMAZINGDATA: bool
IMPORT_ERROR: Optional[Exception]


def _load_stub(stub_path: str) -> tuple[Optional[ModuleType], bool, Optional[Exception]]:
    try:
        module = importlib.import_module(stub_path)
    except Exception as exc:  # pragma: no cover - stub load failure only for diagnostics
        logger.warning(f"Failed to load AmazingData stub: {exc}")
        return None, False, exc
    logger.info(f"Loaded AmazingData stub module: {stub_path}")
    return module, True, None


def _load_sdk() -> tuple[Optional[ModuleType], bool, Optional[Exception]]:
    try:
        import AmazingData as _ad
    except Exception as exc:  # pragma: no cover - executed when AmazingData is missing
        logger.warning(f"AmazingData SDK import failed, falling back to degraded mode: {exc}")
        return None, False, exc
    return _ad, True, None


stub_path = os.getenv("DEEPSEARCH_AMAZINGDATA_STUB")
if stub_path:
    ad, HAS_AMAZINGDATA, IMPORT_ERROR = _load_stub(stub_path)
    if not HAS_AMAZINGDATA:
        ad, HAS_AMAZINGDATA, IMPORT_ERROR = _load_sdk()
else:
    ad, HAS_AMAZINGDATA, IMPORT_ERROR = _load_sdk()

__all__ = ["ad", "HAS_AMAZINGDATA", "IMPORT_ERROR"]

