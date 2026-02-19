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

    try:
        import AmazingData  # noqa: F401
    except Exception as exc:
        pytest.skip(f"AmazingData SDK 依赖不完整，跳过真实登录测试: {exc}")

    manager = get_data_source_manager()
    await manager.initialize()

    if not manager.is_provider_enabled(DataSourceType.AMAZINGDATA):
        pytest.skip("当前配置禁用了 AmazingData，跳过真实 SDK 测试。")

    provider = manager.get_provider(DataSourceType.AMAZINGDATA)
    assert provider is not None, "DataSourceManager 未返回 AmazingData 提供者实例。"

    is_connected = getattr(provider, "is_connected", None)
    if callable(is_connected) and not is_connected():
        pytest.skip("AmazingData Provider 未连接（Dask Worker/Actor 未就绪），跳过真实登录测试。")

    stocks = await provider.get_stock_list(limit=10)
    assert stocks, "AmazingData 未返回任何股票数据，可能是官方 SDK/账号异常。"
