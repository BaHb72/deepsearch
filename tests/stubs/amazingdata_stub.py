"""测试环境下使用的 AmazingData SDK 占位实现。"""
from __future__ import annotations

import sys
from types import SimpleNamespace

__all__ = ["__deepsearch_stub__", "__getattr__"]

__deepsearch_stub__ = True

_module = sys.modules[__name__]
for alias in ("amazingdata", "AmazingData", "amazingdata_sdk", "tgw"):
    sys.modules.setdefault(alias, _module)

def __getattr__(name: str) -> object:
    return SimpleNamespace(__stub_name__=name)
