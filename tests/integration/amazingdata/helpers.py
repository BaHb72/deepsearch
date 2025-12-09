"""Utility helpers for AmazingData integration tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_SECURITY_TYPE = "EXTRA_STOCK_A_SH_SZ"
DEFAULT_START_DATE = 20130101
DEFAULT_LOCAL_CACHE = "D://AmazingData_local_data//"


def _ensure_dataframe(payload: Any) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()
    if isinstance(payload, pd.DataFrame):
        return payload.copy()
    if isinstance(payload, dict):
        return pd.DataFrame([payload])
    try:
        return pd.DataFrame(payload)
    except Exception:
        return pd.DataFrame()


def fetch_code_list(ad_module: Any, security_type: str = DEFAULT_SECURITY_TYPE) -> pd.DataFrame:
    """Fetch stock code list from AmazingData BaseData with safe fallbacks."""

    base_instance = ad_module.BaseData()
    result: Any = None

    if hasattr(base_instance, "get_code_list"):
        try:
            result = base_instance.get_code_list(security_type=security_type)
        except Exception:
            result = None

    if result is None or getattr(result, "empty", False):
        if hasattr(base_instance, "get_hist_code_list"):
            today = int(datetime.now().strftime("%Y%m%d"))
            cache_path = Path(DEFAULT_LOCAL_CACHE)
            try:
                cache_path.mkdir(parents=True, exist_ok=True)
            except Exception:
                # 目录创建失败不应中断测试
                pass
            try:
                result = base_instance.get_hist_code_list(
                    security_type=security_type,
                    start_date=DEFAULT_START_DATE,
                    end_date=today,
                    local_path=str(cache_path),
                    is_local=False,
                )
            except TypeError:
                # 部分旧版本不接受 is_local 参数
                result = base_instance.get_hist_code_list(
                    security_type=security_type,
                    start_date=DEFAULT_START_DATE,
                    end_date=today,
                    local_path=str(cache_path),
                )

    return _ensure_dataframe(result)
