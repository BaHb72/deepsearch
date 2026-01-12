"""AmazingData 集成测试配置，默认设为手动避免误触发真实环境脚本。"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.manual(reason="需要接入 AmazingData 真实环境")

_AMAZINGDATA_DIR = Path(__file__).parent.resolve()


def pytest_collection_modifyitems(config, items):
    """默认跳过 AmazingData 集成测试，显式设置变量后才会运行。"""
    if os.getenv("RUN_MANUAL_TESTS"):
        return

    skip_marker = pytest.mark.skip(
        reason="AmazingData 集成测试默认手动执行，请设置 RUN_MANUAL_TESTS=1 后再运行。"
    )

    for item in items:
        item_path = Path(getattr(item, "fspath", "")).resolve()
        if _AMAZINGDATA_DIR in item_path.parents:
            item.add_marker(skip_marker)
