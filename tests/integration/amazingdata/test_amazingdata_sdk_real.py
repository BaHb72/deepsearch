import os

import pytest
from core.infrastructure.providers.managers.data_source_manager import get_data_source_manager
from core.ports.data_sources import DataSourceType


@pytest.mark.integration
@pytest.mark.asyncio
async def test_amazingdata_process_provider_real_login():
    """
    通过真实配置调用 AmazingData SDK，验证是否能成功返回数据。

    仅当设置环境变量 DEEPSEARCH_RUN_REAL_AMAZINGDATA_TESTS 时才执行，
    以免在 CI 中进行外部依赖调用。
    """

    if not os.getenv("DEEPSEARCH_RUN_REAL_AMAZINGDATA_TESTS"):
        pytest.skip("未设置 DEEPSEARCH_RUN_REAL_AMAZINGDATA_TESTS，跳过真实 AmazingData 测试。")

    manager = get_data_source_manager()
    await manager.initialize()

    if not manager.is_provider_enabled(DataSourceType.AMAZINGDATA):
        pytest.skip("当前配置禁用了 AmazingData，跳过真实 SDK 测试。")

    provider = manager.get_provider(DataSourceType.AMAZINGDATA)
    assert provider is not None, "DataSourceManager 未返回 AmazingData 提供者实例。"

    stocks = await provider.get_stock_list(limit=10)
    assert stocks, "AmazingData 未返回任何股票数据，可能是官方 SDK/账号异常。"
