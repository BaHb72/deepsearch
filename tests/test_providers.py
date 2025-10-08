"""
数据提供者测试套件
测试所有数据提供者的功能和性能
"""

import asyncio
from datetime import datetime

import pytest

from deepsearch.core.utils.async_timeout import run_with_timeout, with_timeout
from deepsearch.infrastructure.providers.base.provider_base import BaseDataProvider
from deepsearch.infrastructure.providers.factory import (
    CircuitBreaker,
    CircuitBreakerState,
    DataProviderFactory,
    SelectionStrategy,
)
from deepsearch.infrastructure.providers.registry import (
    DataProviderRegistry,
    ProviderInfo,
    ProviderType,
)


class MockDataProvider(BaseDataProvider):
    """模拟数据提供者"""

    def __init__(self):
        super().__init__()
        self.fail_count = 0
        self.success_count = 0
        self.delay = 0.1

    async def initialize(self) -> bool:
        """初始化"""
        await asyncio.sleep(0.01)
        self.initialized = True
        return True

    async def get_realtime_quote(self, symbol: str):
        """获取实时行情"""
        if not self._check_initialization():
            return {"error": "not initialized"}

        self.success_count += 1
        await asyncio.sleep(self.delay)
        return {"symbol": symbol, "price": 100.0, "timestamp": datetime.now().isoformat()}

    async def get_historical_data(self, symbol: str, start_date=None, end_date=None):
        """获取历史数据"""
        if not self._check_initialization():
            return {"error": "not initialized"}

        self.success_count += 1
        await asyncio.sleep(self.delay)
        return {
            "symbol": symbol,
            "data": [{"date": "2024-01-01", "close": 99.0}, {"date": "2024-01-02", "close": 100.0}],
        }


class FailingDataProvider(BaseDataProvider):
    """会失败的数据提供者"""

    def __init__(self):
        super().__init__()
        self.fail_after = 2  # 第2次调用后开始失败

    async def initialize(self) -> bool:
        """初始化"""
        self.initialized = True
        return True

    async def get_realtime_quote(self, symbol: str):
        """获取实时行情（会失败）"""
        self.fail_after -= 1
        if self.fail_after <= 0:
            raise Exception("Provider failed")
        return {"symbol": symbol, "price": 50.0}

    async def get_historical_data(self, symbol: str, start_date=None, end_date=None):
        """获取历史数据"""
        raise NotImplementedError("Not implemented")


class TestDataProviderRegistry:
    """测试数据提供者注册表"""

    def setup_method(self):
        """设置测试环境"""
        # 清除全局注册表
        global _registry
        from deepsearch.infrastructure.providers import registry

        registry._registry = None
        self.registry = DataProviderRegistry()

    def test_register_provider(self):
        """测试注册提供者"""
        provider_info = ProviderInfo(
            name="test_provider",
            type=ProviderType.AMAZINGDATA,
            module_path="tests.test_providers",
            class_name="MockDataProvider",
            description="Test provider",
            priority=100,
        )

        self.registry.register(provider_info)
        assert "test_provider" in self.registry._providers
        assert self.registry.get_provider_info("test_provider") == provider_info

        disallowed = ProviderInfo(
            name="legacy_provider",
            type=ProviderType.QMT,
            module_path="tests.test_providers",
            class_name="MockDataProvider",
            description="Legacy provider",
        )
        self.registry.register(disallowed)
        assert "legacy_provider" not in self.registry._providers

    def test_get_providers_by_type(self):
        """测试按类型获取提供者"""
        # 注册多个提供者
        providers = [
            ProviderInfo(
                name="amazing_primary",
                type=ProviderType.AMAZINGDATA,
                module_path="test",
                class_name="Test1",
                description="Primary",
            ),
            ProviderInfo(
                name="amazing_secondary",
                type=ProviderType.AMAZINGDATA,
                module_path="test",
                class_name="Test2",
                description="Secondary",
            ),
        ]

        for provider in providers:
            self.registry.register(provider)

        amazing_providers = self.registry.get_providers_by_type(ProviderType.AMAZINGDATA)
        amazing_names = {p.name for p in amazing_providers}
        assert {"amazing_primary", "amazing_secondary"}.issubset(amazing_names)
        assert all(p.type == ProviderType.AMAZINGDATA for p in amazing_providers)

        legacy = self.registry.get_providers_by_type(ProviderType.AKSHARE)
        assert any(p.name == "akshare" for p in legacy)

    def test_default_providers_initialized(self):
        providers = self.registry.get_all_providers()
        assert "amazingdata" in providers
        assert "cloudflare" in providers
        assert "akshare" in providers

    def test_get_providers_by_priority(self):
        """测试按优先级排序获取提供者"""
        providers = [
            ProviderInfo(
                name="low",
                type=ProviderType.CUSTOM,
                module_path="test",
                class_name="Test1",
                description="Low priority",
                priority=10,
            ),
            ProviderInfo(
                name="high",
                type=ProviderType.CUSTOM,
                module_path="test",
                class_name="Test2",
                description="High priority",
                priority=100,
            ),
            ProviderInfo(
                name="medium",
                type=ProviderType.CUSTOM,
                module_path="test",
                class_name="Test3",
                description="Medium priority",
                priority=50,
            ),
        ]

        for provider in providers:
            self.registry.register(provider)

        sorted_providers = [
            p for p in self.registry.get_providers_by_priority() if p.type == ProviderType.CUSTOM
        ]
        priorities = [p.priority for p in sorted_providers[:3]]
        assert priorities == [100, 50, 10]

    def test_enable_disable_provider(self):
        """测试启用/禁用提供者"""
        provider_info = ProviderInfo(
            name="test",
            type=ProviderType.CUSTOM,
            module_path="test",
            class_name="Test",
            description="Test",
        )

        self.registry.register(provider_info)
        assert provider_info.enabled

        # 禁用
        self.registry.disable_provider("test")
        assert not self.registry.get_provider_info("test").enabled

        # 启用
        self.registry.enable_provider("test")
        assert self.registry.get_provider_info("test").enabled


class TestCircuitBreaker:
    """测试熔断器"""

    def test_circuit_breaker_states(self):
        """测试熔断器状态转换"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1, success_threshold=2)

        # 初始状态：关闭
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.can_attempt()

        # 失败3次后开启
        for _ in range(3):
            breaker.call_failed()
        assert breaker.state == CircuitBreakerState.OPEN
        assert not breaker.can_attempt()

        # 等待恢复时间后变为半开
        import time

        time.sleep(1.1)
        assert breaker.can_attempt()
        assert breaker.state == CircuitBreakerState.HALF_OPEN

        # 成功2次后关闭
        breaker.call_succeeded()
        assert breaker.state == CircuitBreakerState.HALF_OPEN
        breaker.call_succeeded()
        assert breaker.state == CircuitBreakerState.CLOSED


class TestDataProviderFactory:
    """测试数据提供者工厂"""

    def setup_method(self):
        """设置测试环境"""
        self.factory = DataProviderFactory(
            strategy=SelectionStrategy.PRIORITY, enable_circuit_breaker=True
        )

        # 注册测试提供者
        provider_info = ProviderInfo(
            name="mock_provider",
            type=ProviderType.CUSTOM,
            module_path="tests.test_providers",
            class_name="MockDataProvider",
            description="Mock provider",
            priority=100,
        )
        self.factory.registry.register(provider_info)

    @pytest.mark.asyncio
    async def test_get_specific_provider(self):
        """测试获取特定提供者"""
        provider = await self.factory._get_specific_provider("mock_provider")
        assert provider is not None
        assert isinstance(provider, MockDataProvider)
        assert provider.initialized

    @pytest.mark.asyncio
    async def test_get_by_priority(self):
        """测试按优先级获取提供者"""
        # 注册多个提供者
        providers = [
            ProviderInfo(
                name="low_priority",
                type=ProviderType.CUSTOM,
                module_path="tests.test_providers",
                class_name="MockDataProvider",
                description="Low",
                priority=10,
                enabled=True,
            ),
            ProviderInfo(
                name="high_priority",
                type=ProviderType.CUSTOM,
                module_path="tests.test_providers",
                class_name="MockDataProvider",
                description="High",
                priority=100,
                enabled=True,
            ),
        ]

        for p in providers:
            self.factory.registry.register(p)

        # 应该获取高优先级的
        provider = await self.factory._get_by_priority(ProviderType.CUSTOM)
        assert provider is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """测试熔断器集成"""
        # 注册会失败的提供者
        failing_info = ProviderInfo(
            name="failing",
            type=ProviderType.CUSTOM,
            module_path="tests.test_providers",
            class_name="FailingDataProvider",
            description="Failing",
            priority=100,
        )
        self.factory.registry.register(failing_info)

        # 获取提供者并让它失败多次
        provider = await self.factory._get_specific_provider("failing")
        assert provider is not None

        # 模拟多次失败
        self.factory._check_circuit_breaker("failing")
        for _ in range(5):
            self.factory.report_failure("failing")

        # 检查熔断器状态
        assert not self.factory._check_circuit_breaker("failing")

    def test_performance_statistics(self):
        """测试性能统计"""
        # 报告成功
        self.factory.report_success("test", 0.5)
        self.factory.report_success("test", 0.3)

        # 报告失败
        self.factory.report_failure("test")

        stats = self.factory.get_statistics()
        assert "performance" in stats
        assert "test" in stats["performance"]

        test_stats = stats["performance"]["test"]
        assert test_stats["total_requests"] == 3
        assert test_stats["failed_requests"] == 1
        assert test_stats["avg_latency"] == pytest.approx(0.4, rel=0.01)
        assert test_stats["success_rate"] == pytest.approx(66.67, rel=0.01)


class TestAsyncTimeout:
    """测试异步超时功能"""

    @pytest.mark.asyncio
    async def test_with_timeout_decorator(self):
        """测试超时装饰器"""

        @with_timeout(0.1, default={"error": "timeout"})
        async def slow_function():
            await asyncio.sleep(1)
            return {"data": "success"}

        result = await slow_function()
        assert result == {"error": "timeout"}

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """测试超时内完成"""

        @with_timeout(1.0)
        async def fast_function():
            await asyncio.sleep(0.01)
            return {"data": "success"}

        result = await fast_function()
        assert result == {"data": "success"}

    @pytest.mark.asyncio
    async def test_run_with_timeout(self):
        """测试run_with_timeout函数"""

        async def slow_coro():
            await asyncio.sleep(1)
            return "done"

        result = await run_with_timeout(
            slow_coro(), 0.1, default="timeout", operation_name="test_op"
        )
        assert result == "timeout"


class TestBaseDataProvider:
    """测试基础数据提供者"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """测试初始化"""
        provider = MockDataProvider()
        assert not provider.initialized
        assert provider.status == "inactive"
        assert provider.error_count == 0
        assert provider.success_count == 0

        success = await provider.initialize()
        assert success
        assert provider.initialized

    @pytest.mark.asyncio
    async def test_performance_tracking(self):
        """测试性能跟踪"""
        provider = MockDataProvider()
        await provider.initialize()

        # 执行一些操作
        await provider.get_realtime_quote("000001")
        await provider.get_historical_data("000001")

        # 更新统计
        provider._update_stats(True, 0.5)
        provider._update_stats(True, 0.3)
        provider._update_stats(False, 0.1)

        stats = provider.get_performance_stats()
        assert stats["total_requests"] == 3
        assert stats["failed_requests"] == 1
        assert stats["avg_latency"] == pytest.approx(0.3, rel=0.01)
        assert stats["success_rate"] == pytest.approx(66.67, rel=0.01)

    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        provider = MockDataProvider()
        await provider.initialize()

        health = await provider.health_check()
        assert health["provider"] == "MockDataProvider"
        assert health["initialized"]
        assert health["status"] == "inactive"
        assert "performance" in health


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
