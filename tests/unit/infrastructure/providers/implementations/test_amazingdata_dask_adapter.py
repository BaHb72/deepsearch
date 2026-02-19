"""AmazingData Dask Adapter 单元测试

测试 AmazingDataDaskAdapter 的核心功能：
- 初始化和 Worker 发现
- 远程调用机制
- 错误处理和重试
- DataProvider 接口方法
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """模拟 Redis Async 客户端（Worker 就绪）"""
    client = MagicMock()
    client.get = AsyncMock(return_value="ready:tcp://worker1:1234")
    client.rpush = AsyncMock(return_value=1)
    client.delete = AsyncMock(return_value=1)
    return client


@pytest.fixture
def mock_redis_client_no_windows() -> MagicMock:
    """模拟 Redis 中没有 Worker 就绪标记"""
    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.rpush = AsyncMock(return_value=1)
    client.delete = AsyncMock(return_value=1)
    return client


class TestAmazingDataDaskAdapterInit:
    """初始化测试"""

    def test_init_basic(self, mock_redis_client: MagicMock) -> None:
        """测试基本初始化"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)

        assert adapter.name == "amazingdata"
        assert adapter._timeout == 45.0
        assert adapter._retry_count == 3
        assert adapter._windows_worker is None
        assert adapter._actor_available is False
        assert adapter._initialized is False

    def test_init_custom_params(self, mock_redis_client: MagicMock) -> None:
        """测试自定义参数初始化"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(
            redis_client=mock_redis_client,
            timeout=60.0,
            retry_count=5,
        )

        assert adapter._timeout == 60.0
        assert adapter._retry_count == 5


class TestAmazingDataDaskAdapterInitialize:
    """initialize() 方法测试"""

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_redis_client: MagicMock) -> None:
        """测试初始化成功"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)

        # 模拟 _check_actor_available 返回 True
        with patch.object(adapter, "_check_actor_available", return_value=True):
            result = await adapter.initialize()

        assert result is True
        assert adapter._windows_worker == "tcp://worker1:1234"
        assert adapter._actor_available is True
        assert adapter._initialized is True
        assert adapter.is_connected() is True

    @pytest.mark.asyncio
    async def test_initialize_no_windows_worker(
        self, mock_redis_client_no_windows: MagicMock
    ) -> None:
        """测试无 Windows Worker"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client_no_windows)
        result = await adapter.initialize()

        assert result is False
        assert adapter._windows_worker is None
        assert adapter.is_connected() is False

    @pytest.mark.asyncio
    async def test_initialize_actor_not_available(self, mock_redis_client: MagicMock) -> None:
        """测试 Actor 不可用"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)

        # 模拟 _check_actor_available 返回 False
        with patch.object(adapter, "_check_actor_available", return_value=False):
            result = await adapter.initialize()

        assert result is False
        assert adapter._windows_worker == "tcp://worker1:1234"
        assert adapter._actor_available is False

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mock_redis_client: MagicMock) -> None:
        """测试重复初始化（幂等性）"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)

        with patch.object(adapter, "_check_actor_available", return_value=True):
            # 第一次初始化
            result1 = await adapter.initialize()
            # 第二次初始化应该直接返回 True
            result2 = await adapter.initialize()

        assert result1 is True
        assert result2 is True


class TestAmazingDataDaskAdapterCallActor:
    """_call_actor() 方法测试"""

    @pytest.mark.asyncio
    async def test_call_actor_not_initialized(self, mock_redis_client: MagicMock) -> None:
        """测试未初始化时调用"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )
        from core.infrastructure.providers.interfaces.base import DataProviderError

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)

        with pytest.raises(DataProviderError, match="Actor 不可用"):
            await adapter._call_actor("query_kline", code_list=["000001.SZ"])

    @pytest.mark.asyncio
    async def test_call_actor_success(self, mock_redis_client: MagicMock) -> None:
        """测试远程调用成功"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)
        adapter._actor_available = True
        adapter._windows_worker = "tcp://worker1:1234"

        # 模拟 Redis 轮询返回结果
        expected_result = [{"symbol": "000001.SZ", "close": 10.5}]
        mock_redis_client.get = AsyncMock(
            return_value=json.dumps(
                {
                    "status": "success",
                    "result": expected_result,
                }
            ).encode()
        )

        result = await adapter._call_actor(
            "query_kline",
            code_list=["000001.SZ"],
            begin_date=20240101,
            end_date=20240110,
        )

        assert result == expected_result
        mock_redis_client.rpush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_call_actor_timeout_retry(self, mock_redis_client: MagicMock) -> None:
        """测试超时重试"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )
        from core.infrastructure.providers.interfaces.base import DataProviderError

        adapter = AmazingDataDaskAdapter(
            redis_client=mock_redis_client, timeout=0.1, first_call_timeout=0.1, retry_count=2
        )
        adapter._actor_available = True
        adapter._windows_worker = "tcp://worker1:1234"

        async def _mock_get(key: str) -> Any:
            if key.startswith("dask_result:"):
                return None
            if key in ("dask_actor_heartbeat:amazingdata", "dask_actor_ready:amazingdata"):
                return "ready:tcp://worker1:1234"
            return None

        # 结果键始终无结果（模拟业务超时），但运行时标记存在（不应误判为崩溃）
        mock_redis_client.get = AsyncMock(side_effect=_mock_get)

        with pytest.raises(DataProviderError, match="超时"):
            await adapter._call_actor("query_kline")

        # 应该重试 2 次 + 初始调用 = 3 次
        assert mock_redis_client.rpush.await_count == 3

    @pytest.mark.asyncio
    async def test_call_actor_marks_unavailable_when_runtime_marker_missing(
        self, mock_redis_client: MagicMock
    ) -> None:
        """测试超时且运行时标记缺失时，标记为疑似 Worker 崩溃。"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )
        from core.infrastructure.providers.interfaces.base import DataProviderError

        adapter = AmazingDataDaskAdapter(
            redis_client=mock_redis_client,
            timeout=0.1,
            first_call_timeout=0.1,
            retry_count=0,
        )
        adapter._actor_available = True
        adapter._initialized = True
        adapter._windows_worker = "tcp://worker1:1234"

        # 所有 key 都不存在：结果无返回 + 心跳/就绪标记缺失
        mock_redis_client.get = AsyncMock(return_value=None)

        with pytest.raises(DataProviderError, match="运行时异常"):
            await adapter._call_actor("query_kline")

        assert adapter._actor_available is False
        assert adapter._initialized is False
        assert adapter._last_runtime_issue is not None
        assert "心跳/就绪标记" in adapter._last_runtime_issue


class TestAmazingDataDaskAdapterDataProviderMethods:
    """DataProvider 接口方法测试"""

    @pytest.fixture
    def initialized_adapter(self, mock_redis_client: MagicMock) -> Any:
        """已初始化的 Adapter"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)
        adapter._actor_available = True
        adapter._windows_worker = "tcp://worker1:1234"
        adapter._initialized = True
        return adapter

    @pytest.mark.asyncio
    async def test_query_kline(self, initialized_adapter: Any) -> None:
        """测试 query_kline 接口"""
        expected_result = {
            "000001.SZ": [{"date": 20240101, "close": 10.5}],
        }

        with patch.object(
            initialized_adapter, "_call_actor", return_value=expected_result
        ) as mock_call:
            result = await initialized_adapter.query_kline(
                code_list=["000001.SZ"],
                begin_date=20240101,
                end_date=20240110,
                period="day",
            )

        assert result is not None
        assert "000001.SZ" in result
        mock_call.assert_called_once_with(
            "query_kline",
            code_list=["000001.SZ"],
            begin_date=20240101,
            end_date=20240110,
            period=10008,
        )

    @pytest.mark.asyncio
    async def test_get_code_list(self, initialized_adapter: Any) -> None:
        """测试 get_code_list 接口"""
        expected_result = ["000001.SZ", "000002.SZ", "600000.SH"]

        with patch.object(
            initialized_adapter, "_call_actor", return_value=expected_result
        ) as mock_call:
            result = await initialized_adapter.get_code_list(security_type="EXTRA_STOCK_A")

        assert result == expected_result
        mock_call.assert_called_once_with("get_code_list", security_type="EXTRA_STOCK_A")

    @pytest.mark.asyncio
    async def test_get_calendar(self, initialized_adapter: Any) -> None:
        """测试 get_calendar 接口"""
        expected_result = [20240102, 20240103, 20240104]

        with patch.object(
            initialized_adapter, "_call_actor", return_value=expected_result
        ) as mock_call:
            result = await initialized_adapter.get_calendar(market="SH", data_type="int")

        assert result == expected_result
        # get_calendar 使用默认参数时不传递 kwargs 到 _call_actor
        mock_call.assert_called_once_with("get_calendar")

    @pytest.mark.asyncio
    async def test_get_stock_list_accepts_limit_keyword(self, initialized_adapter: Any) -> None:
        """测试 get_stock_list 支持 limit 关键字参数。"""
        expected_codes = ["600000.SH", "000001.SZ", "000002.SZ"]

        with patch.object(
            initialized_adapter, "_call_actor", return_value=expected_codes
        ) as mock_call:
            result = await initialized_adapter.get_stock_list(market="SZ", limit=1)

        assert result == [{"symbol": "000001.SZ", "name": ""}]
        mock_call.assert_called_once_with("get_code_list", security_type="EXTRA_STOCK_A")

    @pytest.mark.asyncio
    async def test_get_stock_list_accepts_positional_limit(self, initialized_adapter: Any) -> None:
        """测试 get_stock_list 兼容旧式位置参数 limit。"""
        expected_codes = ["600000.SH", "000001.SZ", "000002.SZ"]

        with patch.object(
            initialized_adapter, "_call_actor", return_value=expected_codes
        ) as mock_call:
            result = await initialized_adapter.get_stock_list(2)

        assert len(result) == 2
        assert result[0]["symbol"] == "600000.SH"
        assert result[1]["symbol"] == "000001.SZ"
        mock_call.assert_called_once_with("get_code_list", security_type="EXTRA_STOCK_A")

    @pytest.mark.asyncio
    async def test_get_balance_sheet(self, initialized_adapter: Any) -> None:
        """测试 get_balance_sheet 接口"""
        expected_result = [
            {"symbol": "000001.SZ", "total_assets": 1000000},
        ]

        with patch.object(
            initialized_adapter, "_call_actor", return_value=expected_result
        ) as mock_call:
            result = await initialized_adapter.get_balance_sheet(
                code_list=["000001.SZ"],
                local_path="D:/tmp/amazingdata",
                is_local=True,
            )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        mock_call.assert_called_once_with(
            "get_balance_sheet",
            code_list=["000001.SZ"],
            local_path="D:/tmp/amazingdata",
            is_local=True,
        )


class TestAmazingDataDaskAdapterHealthCheck:
    """health_check() 方法测试"""

    @pytest.mark.asyncio
    async def test_health_check_runtime_marker_missing_marks_unhealthy(
        self, mock_redis_client: MagicMock
    ) -> None:
        """测试运行时标记丢失时 health_check 返回 UNHEALTHY 并降级。"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )
        from core.infrastructure.providers.protocols.lifecycle import HealthStatus

        async def _mock_get(key: str) -> Any:
            if key in ("dask_actor_heartbeat:amazingdata", "dask_actor_ready:amazingdata"):
                return None
            return "ready:tcp://worker1:1234"

        mock_redis_client.get = AsyncMock(side_effect=_mock_get)
        mock_redis_client.ping = AsyncMock(return_value=True)

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)
        adapter._actor_available = True
        adapter._initialized = True
        adapter._windows_worker = "tcp://worker1:1234"

        result = await adapter.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "运行时异常" in result.message
        assert adapter._actor_available is False


class TestAmazingDataDaskAdapterShutdown:
    """shutdown() 方法测试"""

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_redis_client: MagicMock) -> None:
        """测试关闭"""
        from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
            AmazingDataDaskAdapter,
        )

        adapter = AmazingDataDaskAdapter(redis_client=mock_redis_client)
        adapter._actor_available = True
        adapter._initialized = True

        await adapter.shutdown()

        assert adapter._actor_available is False
        assert adapter._initialized is False
        assert adapter.is_connected() is False


class TestAmazingDataActorCallSync:
    """AmazingDataActor.call_sync() 方法测试"""

    def test_call_sync_basic(self) -> None:
        """测试 call_sync 基本功能"""
        # 直接导入 amazingdata_actor 模块，避免触发 __init__.py 的导入
        import importlib.util
        import sys

        # 动态加载模块
        spec = importlib.util.spec_from_file_location(
            "amazingdata_actor",
            "packages/core/compute/actors/amazingdata_actor.py",
        )
        if spec is None or spec.loader is None:
            pytest.skip("Unable to load amazingdata_actor module")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules["amazingdata_actor_test"] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            pytest.skip(f"Unable to execute amazingdata_actor module: {e}")
            return

        AmazingDataActor = module.AmazingDataActor
        actor = AmazingDataActor()

        # 模拟 call 方法
        async def mock_call(method: str, **kwargs: Any) -> Any:
            return {"method": method, "kwargs": kwargs}

        with patch.object(actor, "call", side_effect=mock_call):
            # call_sync 是同步方法
            result = actor.call_sync("query_kline", code_list=["000001.SZ"])

        assert result["method"] == "query_kline"
        assert result["kwargs"]["code_list"] == ["000001.SZ"]


class TestConfigValidation:
    """配置验证测试"""

    def test_distributed_mode_requires_scheduler(self) -> None:
        """测试 distributed 模式需要 scheduler 地址"""
        from core.config.models.amazingdata import AmazingDataConfig

        # distributed 模式但没有 scheduler 地址应该报错
        with pytest.raises(ValueError, match="distributed 模式需要配置"):
            AmazingDataConfig(
                enabled=False,  # 禁用以跳过连接验证
                mode="distributed",
                dask_scheduler_address=None,
            )

    def test_distributed_mode_with_scheduler(self) -> None:
        """测试 distributed 模式配置正确"""
        from core.config.models.amazingdata import AmazingDataConfig

        # 正确配置应该通过
        config = AmazingDataConfig(
            enabled=False,
            mode="distributed",
            dask_scheduler_address="tcp://localhost:8786",
        )

        assert config.mode == "distributed"
        assert config.dask_scheduler_address == "tcp://localhost:8786"

    def test_local_mode_default(self) -> None:
        """测试 local 模式默认值"""
        from core.config.models.amazingdata import AmazingDataConfig

        config = AmazingDataConfig(enabled=False)

        assert config.mode == "local"
        assert config.dask_scheduler_address is None
