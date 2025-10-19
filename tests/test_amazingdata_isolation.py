"""
AmazingData SDK 隔离机制测试用例

测试SDK退出保护、降级机制、错误处理等功能。
"""

import os
import asyncio
from unittest.mock import patch

import pytest

from deepsearch.infrastructure.monitoring.provider_health import (
    ProviderHealthMonitor,
    ProviderStatus,
)

# 确保加载测试桩模块，避免真实 SDK 依赖阻塞单测
os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")

# 在离线环境下跳过依赖外部数据源的测试
SKIP_NETWORK_PROVIDERS = os.environ.get("DEEPSEARCH_TEST_ENABLE_NETWORK_PROVIDERS") != "1"

# 测试导入
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (  # noqa: E402
    AmazingDataConfig,
    AmazingDataProvider,
)
from deepsearch.infrastructure.providers.mock.error_provider import MockErrorProvider  # noqa: E402
from deepsearch.webui.api.providers import DataProviderFactory  # noqa: E402


class TestSDKIsolation:
    """SDK隔离机制测试"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return AmazingDataConfig(
            username="test_user", password="test_pass", host="localhost", port=8600, timeout=5
        )

    @pytest.fixture
    def provider(self, config):
        """创建提供者实例"""
        return AmazingDataProvider(config)

    @pytest.mark.asyncio
    async def test_safe_login_catches_system_exit(self, provider):
        """
        测试: safe_login能够捕获SystemExit
        """
        # 模拟SDK调用exit(0)
        with patch(
            "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata.ad.login"
        ) as mock_login:
            mock_login.side_effect = SystemExit(0)

            # 调用_login应该捕获SystemExit并返回错误
            with pytest.raises(Exception) as exc_info:
                await provider._login()

            # 验证错误消息包含SDK退出信息
            assert "SDK尝试强制退出程序" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_safe_login_catches_system_exit_with_code_1(self, provider):
        """
        测试: safe_login能够捕获SystemExit(1)
        """
        with patch(
            "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata.ad.login"
        ) as mock_login:
            mock_login.side_effect = SystemExit(1)

            with pytest.raises(Exception) as exc_info:
                await provider._login()

            assert "SDK尝试强制退出程序" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_timeout_handling(self, provider):
        """
        测试: 登录超时处理
        """

        # 模拟超时的登录函数
        async def slow_login():
            await asyncio.sleep(10)  # 超过5秒超时

        with patch.object(provider, "_login", slow_login):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(provider._login(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_trigger_alert_functionality(self, provider):
        """
        测试: _trigger_alert方法功能
        """
        # 调用_trigger_alert
        await provider._trigger_alert("SDK_EXIT", "Test alert message")

        # 验证统计信息中记录了告警
        assert "SDK_EXIT" in provider._stats
        assert len(provider._stats["SDK_EXIT"]) > 0
        assert provider._stats["SDK_EXIT"][0]["message"] == "Test alert message"


class TestDataProviderFactory:
    """DataProviderFactory降级机制测试"""

    @pytest.mark.asyncio
    async def test_fallback_to_akshare_on_amazingdata_failure(self):
        """
        测试: AmazingData失败时降级到AkShare
        """
        # 清理现有实例
        DataProviderFactory.clear_all()

        # 模拟AmazingData初始化失败
        with patch(
            "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata.AmazingDataProvider.initialize"
        ) as mock_init:
            mock_init.side_effect = Exception("SDK尝试强制退出程序")

            # 获取提供者应该降级到AkShare
            await DataProviderFactory.get_provider_async("amazingdata")

            # 验证降级状态
            assert "amazingdata" in DataProviderFactory._fallback_status
            fallback_info = DataProviderFactory._fallback_status["amazingdata"]
            assert fallback_info["fallback"] == "akshare"
            assert "SDK" in fallback_info["reason"]

    @pytest.mark.requires_cloudflare
    @pytest.mark.skipif(
        SKIP_NETWORK_PROVIDERS,
        reason="当前运行环境未开启外部数据源（Cloudflare/Akshare），跳过依赖真实网络的降级链路测试",
    )
    @pytest.mark.asyncio
    async def test_fallback_to_error_provider_when_all_fail(self):
        """
        测试: 所有提供者都失败时降级到ErrorProvider
        """
        DataProviderFactory.clear_all()

        # 模拟所有提供者都失败
        with patch(
            "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata.AmazingDataProvider.initialize"
        ) as mock_ad_init:
            with patch(
                "deepsearch.infrastructure.providers.implementations.akshare.akshare.AkShareProxyProvider.initialize"
            ) as mock_ak_init:
                mock_ad_init.side_effect = Exception("AmazingData failed")
                mock_ak_init.side_effect = Exception("AkShare failed")

                # 获取提供者应该得到ErrorProvider或临时错误提供者
                await DataProviderFactory.get_provider_async("amazingdata")

                # 验证健康状态
                health = DataProviderFactory._provider_health.get("amazingdata", {})
                assert health.get("status") == "failed"
                assert health.get("provider") == "error"

    @pytest.mark.asyncio
    async def test_record_provider_failure(self):
        """
        测试: 记录提供者失败信息
        """
        DataProviderFactory._record_provider_failure(
            "test_provider", "SDK_EXIT", "Test error message"
        )

        # 验证失败记录
        assert "test_provider" in DataProviderFactory._provider_health
        health = DataProviderFactory._provider_health["test_provider"]
        assert health["status"] == "failed"
        assert health.get("critical_error") is True
        assert len(health["failures"]) > 0
        assert health["failures"][-1]["type"] == "SDK_EXIT"

    def test_get_health_status(self):
        """
        测试: 获取健康状态
        """
        # 添加一些测试数据
        DataProviderFactory._provider_health["test1"] = {"status": "healthy"}
        DataProviderFactory._fallback_status["test2"] = {"fallback": "akshare"}

        # 获取健康状态
        status = DataProviderFactory.get_health_status()

        assert "providers" in status
        assert "fallback_status" in status
        assert "timestamp" in status
        assert "test1" in status["providers"]
        assert "test2" in status["fallback_status"]


class TestMockErrorProvider:
    """MockErrorProvider测试"""

    @pytest.mark.asyncio
    async def test_error_provider_initialization(self):
        """
        测试: ErrorProvider初始化
        """
        provider = MockErrorProvider("Test failure reason")
        assert await provider.initialize() is True
        assert provider.failure_reason == "Test failure reason"

    @pytest.mark.asyncio
    async def test_error_provider_returns_error_info(self):
        """
        测试: ErrorProvider返回错误信息
        """
        provider = MockErrorProvider("All providers failed")

        # 测试get_data方法
        result = await provider.get_data("test_request", symbol="000001.SZ")
        assert "error" in result
        assert result["reason"] == "All providers failed"
        assert result["provider"] == "MockErrorProvider"

    @pytest.mark.asyncio
    async def test_error_provider_access_logging(self):
        """
        测试: ErrorProvider访问日志记录
        """
        provider = MockErrorProvider("Test")

        # 进行多次访问
        for i in range(5):
            await provider.get_kline("000001.SZ")

        # 验证访问计数
        assert provider.access_count == 5
        assert len(provider.access_log) == 5

        # 验证统计信息
        stats = provider.get_statistics()
        assert stats["total_access_count"] == 5
        assert "get_kline" in stats["method_counts"]


class TestProviderHealthMonitor:
    """健康监控系统测试"""

    @pytest.fixture
    def monitor(self):
        """创建监控器实例"""
        return ProviderHealthMonitor(check_interval=1, max_consecutive_errors=3)

    def test_record_request_success(self, monitor):
        """
        测试: 记录成功请求
        """
        monitor.record_request("test_provider", success=True, latency_ms=50)

        health = monitor.get_provider_health("test_provider")
        assert health is not None
        assert health.total_requests == 1
        assert health.consecutive_errors == 0
        assert health.success_rate == 1.0

    def test_record_request_failure(self, monitor):
        """
        测试: 记录失败请求
        """
        monitor.record_request("test_provider", success=False)

        health = monitor.get_provider_health("test_provider")
        assert health.total_requests == 1
        assert health.consecutive_errors == 1
        assert health.total_errors == 1
        assert health.success_rate == 0.0

    def test_status_evaluation(self, monitor):
        """
        测试: 状态评估逻辑
        """
        # 记录多次失败
        for i in range(4):
            monitor.record_request("test_provider", success=False)

        health = monitor.get_provider_health("test_provider")
        assert health.status == ProviderStatus.FAILED
        assert health.consecutive_errors == 4

    def test_sdk_exit_recording(self, monitor):
        """
        测试: SDK退出记录
        """
        monitor.record_error("test_provider", "SDK_EXIT", "SDK tried to exit")

        health = monitor.get_provider_health("test_provider")
        assert health.sdk_exit_count == 1
        assert health.status == ProviderStatus.FAILED

        # 验证触发了告警
        assert len(monitor._alerts) > 0
        alert_types = [alert["type"] for alert in monitor._alerts]
        assert "SDK_EXIT" in alert_types

    def test_health_summary(self, monitor):
        """
        测试: 健康状态摘要
        """
        # 添加一些测试数据
        monitor.record_request("provider1", success=True)
        monitor.record_request("provider2", success=False)
        monitor.record_request("provider2", success=False)
        monitor.record_request("provider2", success=False)

        summary = monitor.get_health_summary()

        assert summary["total_providers"] == 2
        assert "providers" in summary
        assert "provider1" in summary["providers"]
        assert "provider2" in summary["providers"]


@pytest.mark.requires_cloudflare
@pytest.mark.skipif(
    SKIP_NETWORK_PROVIDERS,
    reason="当前运行环境未开启外部数据源（Cloudflare/Akshare），跳过依赖真实网络的集成用例",
)
@pytest.mark.requires_cloudflare
@pytest.mark.skipif(
    SKIP_NETWORK_PROVIDERS,
    reason="当前运行环境未开启外部数据源（Cloudflare/Akshare），跳过依赖真实网络的集成用例",
)
@pytest.mark.asyncio
async def test_integration_sdk_exit_protection():
    """
    集成测试: SDK退出保护完整流程
    """
    # 清理状态
    DataProviderFactory.clear_all()

    # 创建监控器
    ProviderHealthMonitor()

    # 模拟SDK退出场景
    with patch("AmazingData.ad.login") as mock_login:
        mock_login.side_effect = SystemExit(0)

        # 尝试获取提供者
        provider = await DataProviderFactory.get_provider_async("amazingdata")

        # 验证降级成功
        assert provider is not None

        # 验证健康状态记录
        health_status = DataProviderFactory.get_health_status()
        assert "amazingdata" in health_status["providers"]

        # 如果降级成功，provider应该不是AmazingDataProvider
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (  # noqa: E402
            AmazingDataProvider,
        )

        assert not isinstance(provider, AmazingDataProvider)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
