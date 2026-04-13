"""Integration test gating.

默认集成测试只运行不依赖真实外部服务的用例。AmazingData、MiniQMT 和
外部基础设施测试必须显式开启，避免本地一键检查挂在 SDK、Redis 或行情环境上。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_INTEGRATION_ROOT = Path(__file__).parent.resolve()
_AMAZINGDATA_DIR = _INTEGRATION_ROOT / "amazingdata"
_INFRASTRUCTURE_DIR = _INTEGRATION_ROOT / "infrastructure"
_MINIQMT_FILES = {
    "test_miniqmt_integration.py",
    "test_miniqmt_comprehensive.py",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--include-external",
        action="store_true",
        default=False,
        help="Run integration tests marked external.",
    )
    parser.addoption(
        "--include-manual",
        action="store_true",
        default=False,
        help="Run integration tests marked manual.",
    )


def _truthy_env(name: str) -> bool:
    value = os.getenv(name, "")
    return value.lower() in {"1", "true", "yes", "on"}


def _is_in_path(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def _include_external(config: pytest.Config) -> bool:
    return bool(config.getoption("--include-external")) or _truthy_env("RUN_EXTERNAL_TESTS")


def _include_manual(config: pytest.Config) -> bool:
    return bool(config.getoption("--include-manual")) or _truthy_env("RUN_MANUAL_TESTS")


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    path = Path(collection_path).resolve()
    include_external = _include_external(config)
    include_manual = _include_manual(config)

    if _is_in_path(path, _AMAZINGDATA_DIR) and not (include_external and include_manual):
        return True
    if path.name in _MINIQMT_FILES and not (include_external and include_manual):
        return True
    if _is_in_path(path, _INFRASTRUCTURE_DIR) and not include_external:
        return True
    return None


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    include_external = _include_external(config)
    include_manual = _include_manual(config)

    skip_external = pytest.mark.skip(
        reason=(
            "external 集成测试默认跳过；使用 --include-external "
            "或设置 RUN_EXTERNAL_TESTS=1 后运行。"
        )
    )
    skip_manual = pytest.mark.skip(
        reason=(
            "manual 集成测试默认跳过；使用 --include-manual " "或设置 RUN_MANUAL_TESTS=1 后运行。"
        )
    )

    for item in items:
        item_path = Path(str(getattr(item, "fspath", ""))).resolve()
        item.add_marker(pytest.mark.integration)

        is_external = False
        is_manual = False

        if _is_in_path(item_path, _AMAZINGDATA_DIR):
            item.add_marker(pytest.mark.amazingdata)
            item.add_marker(pytest.mark.external)
            item.add_marker(pytest.mark.manual)
            is_external = True
            is_manual = True

        if item_path.name in _MINIQMT_FILES:
            item.add_marker(pytest.mark.miniqmt)
            item.add_marker(pytest.mark.external)
            item.add_marker(pytest.mark.manual)
            is_external = True
            is_manual = True

        if _is_in_path(item_path, _INFRASTRUCTURE_DIR):
            item.add_marker(pytest.mark.external)
            is_external = True

        if is_manual and not include_manual:
            item.add_marker(skip_manual)
        if is_external and not include_external:
            item.add_marker(skip_external)
