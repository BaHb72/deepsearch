"""AmazingData 登录守护逻辑的核心回归测试。"""

import os
from unittest.mock import patch

import pytest

# 使用桩模块替代真实 SDK，确保测试可在离线环境执行
os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
    AmazingDataConfig,
    AmazingDataProvider,
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError


@pytest.mark.asyncio
async def test_safe_login_masks_system_exit():
    """验证 safe_login 能够吞掉 SystemExit 并转换为业务错误。"""

    provider = AmazingDataProvider(
        AmazingDataConfig(
            username="demo",
            password="demo",
            host="127.0.0.1",
            port=8600,
            timeout=3,
        )
    )

    # 打补丁的位置必须与 _login 实际调用的 ad.login 完全一致
    patch_target = (
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata.ad.login"
    )

    with patch(patch_target, side_effect=SystemExit(1)):
        with pytest.raises(DataProviderError) as error:
            await provider._login()

    # SystemExit 被捕获后会包装成 DataProviderError，其中包含明确提示
    assert "SDK尝试强制退出程序" in str(error.value)
