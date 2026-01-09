"""Helpers to load bytecode-only modules shipped in ``__pycache__``."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable, List

__all__ = ["load_sourceless", "load_all_sourceless"]


def load_sourceless(package_file: str, package_name: str, module_name: str) -> ModuleType:
    """Load a sibling ``.pyc`` module for a package ``__init__``."""

    cache_dir = Path(package_file).with_name("__pycache__")
    pattern = f"{module_name}.cpython-*.pyc"
    candidates = sorted(cache_dir.glob(pattern))
    if not candidates:
        raise ImportError(f"No bytecode found for {module_name!r} in {cache_dir}")

    bytecode_path = candidates[-1]
    qualified_name = f"{package_name}.{module_name}"

    loader = importlib.machinery.SourcelessFileLoader(qualified_name, str(bytecode_path))
    spec = importlib.util.spec_from_loader(qualified_name, loader)
    if spec is None:
        raise ImportError(f"Cannot build spec for {qualified_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified_name] = module
    loader.exec_module(module)
    return module


def load_all_sourceless(
    package_file: str, package_name: str, module_names: Iterable[str]
) -> List[ModuleType]:
    """Convenience wrapper to load several compiled-only modules."""

    loaded: List[ModuleType] = []
    for name in module_names:
        loaded.append(load_sourceless(package_file, package_name, name))
    return loaded
