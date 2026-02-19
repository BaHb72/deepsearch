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
_REQUIRED_SDK_ATTRS = ("BaseData", "MarketData", "InfoData")


def _load_stub(stub_path: str) -> tuple[Optional[ModuleType], bool, Optional[Exception]]:
    try:
        module = importlib.import_module(stub_path)
    except Exception as exc:  # pragma: no cover - stub load failure only for diagnostics
        logger.warning(f"Failed to load AmazingData stub: {exc}")
        return None, False, exc
    logger.info(f"Loaded AmazingData stub module: {stub_path}")
    return module, True, None


def _load_sdk() -> tuple[Optional[ModuleType], bool, Optional[Exception]]:
    # 按优先级尝试不同的包名
    # 注意: AmazingData 和 tgw 的login函数签名不同！
    # AmazingData.login(username, password, host, port) -> 使用关键字参数
    # tgw.Login 有不同的签名
    sdk_candidates = ("AmazingData", "amazingdata", "tgw", "amazingdata_sdk")
    last_exc = None
    for name in sdk_candidates:
        try:
            _ad = __import__(name)

            has_login = callable(getattr(_ad, "login", None))
            has_login_legacy = callable(getattr(_ad, "Login", None))
            if not has_login and has_login_legacy:
                # 兼容旧接口：将 Login 对齐为 login
                setattr(_ad, "login", getattr(_ad, "Login"))
                has_login = True

            if not has_login:
                last_exc = RuntimeError(f"{name} missing callable login/Login")
                logger.debug(f"[SDK加载] 候选 {name} 不兼容: {last_exc}")
                continue

            missing_attrs = [
                attr for attr in _REQUIRED_SDK_ATTRS if not callable(getattr(_ad, attr, None))
            ]
            if missing_attrs:
                last_exc = RuntimeError(
                    f"{name} missing required SDK APIs: {', '.join(missing_attrs)}"
                )
                logger.debug(f"[SDK加载] 候选 {name} 不兼容: {last_exc}")
                continue

            logger.info(f"[SDK加载] AmazingData SDK加载成功 (包名: {name}): {_ad}")
            return _ad, True, None
        except Exception as exc:
            last_exc = exc
            logger.debug(f"[SDK加载] 导入候选 {name} 失败: {exc}")
            continue
    logger.warning(f"AmazingData SDK import failed, tried {sdk_candidates}. Last error: {last_exc}")
    return None, False, last_exc


stub_path = os.getenv("DEEPSEARCH_AMAZINGDATA_STUB")
if stub_path:
    ad, HAS_AMAZINGDATA, IMPORT_ERROR = _load_stub(stub_path)
    if not HAS_AMAZINGDATA:
        ad, HAS_AMAZINGDATA, IMPORT_ERROR = _load_sdk()
else:
    ad, HAS_AMAZINGDATA, IMPORT_ERROR = _load_sdk()

# SDK v1.0.4 bug 修复（字节码反编译验证后的 monkey-patch）
if HAS_AMAZINGDATA:
    try:
        from .sdk_patches import apply_sdk_patches

        apply_sdk_patches()
    except Exception as exc:
        logger.warning(f"[SDK补丁] 应用失败（不影响其他功能）: {exc}")

__all__ = ["ad", "HAS_AMAZINGDATA", "IMPORT_ERROR"]
