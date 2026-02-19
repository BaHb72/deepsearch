"""Dask 初始化链路下 AmazingData 真实集成测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from core.compute.dask_cluster_manager import shutdown_dask_cluster
from core.compute.dask_init_state import DaskInitPhase, DaskInitStateManager
from core.infrastructure.providers.container import ProviderContainer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dask_init_registers_amazingdata_and_can_query_calendar(monkeypatch):
    """验证真实 Dask 初始化后 AmazingData 能注册并完成一次查询。"""
    try:
        import AmazingData  # noqa: F401
    except Exception as exc:
        pytest.skip(f"AmazingData SDK 依赖不完整，跳过真实 Dask 初始化测试: {exc}")

    monkeypatch.setenv("APP__ENV", "dev")

    # 真实环境下，Dask Plugin 初始化存在时序抖动；允许重试一次降低偶发失败。
    max_attempts = 2
    last_status: dict[str, object] | None = None

    for attempt in range(1, max_attempts + 1):
        manager = DaskInitStateManager()
        app = SimpleNamespace(state=SimpleNamespace(provider_container=ProviderContainer()))
        should_retry = False

        try:
            await manager.initialize_in_background(app)
            status = manager.get_status().to_dict()
            last_status = status

            if not app.state.provider_container.has("amazingdata"):
                should_retry = attempt < max_attempts
                if should_retry:
                    continue

                pytest.fail(
                    "Dask 初始化后未注册 amazingdata Provider；"
                    f"phase={status.get('phase')} components={status.get('components')}"
                )

            provider = await app.state.provider_container.get("amazingdata")
            calendar = await provider.get_calendar()

            assert manager.phase in {DaskInitPhase.READY, DaskInitPhase.PARTIAL}
            assert isinstance(calendar, list)
            assert len(calendar) > 0
            assert all(isinstance(item, int) for item in calendar[:5])
            return
        finally:
            await manager.shutdown()
            await app.state.provider_container.shutdown()
            await shutdown_dask_cluster()

        if not should_retry:
            break

    pytest.fail(f"AmazingData Dask 初始化与调用失败，最后状态: {last_status}")
