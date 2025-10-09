"""
超时配置管理器单元测试

测试TimeoutManager的核心功能：
1. 超时配置管理
2. 动态超时计算
3. API智能超时
4. 指数退避策略
"""

import pytest

from deepsearch.core.utils.timeout_config import (
    TimeoutCategory,
    TimeoutConfig,
    TimeoutManager,
    configure_timeouts,
    get_timeout_manager,
)


class TestTimeoutConfig:
    """TimeoutConfig测试"""

    def test_default_timeout(self):
        """测试默认超时"""
        config = TimeoutConfig(default=10.0, min=5.0, max=30.0)
        assert config.get_timeout(0) == 10.0

    def test_retry_timeout_with_multiplier(self):
        """测试重试超时倍数"""
        config = TimeoutConfig(default=10.0, min=5.0, max=60.0, retry_multiplier=2.0)

        # 第一次尝试
        assert config.get_timeout(0) == 10.0

        # 第一次重试 (10 * 2^1 = 20)
        assert config.get_timeout(1) == 20.0

        # 第二次重试 (10 * 2^2 = 40)
        assert config.get_timeout(2) == 40.0

        # 第三次重试 (10 * 2^3 = 80, 但限制在max=60)
        assert config.get_timeout(3) == 60.0

    def test_retry_timeout_default_multiplier(self):
        """测试默认重试倍数（1.5）"""
        config = TimeoutConfig(default=10.0, min=5.0, max=30.0)

        # 第一次尝试
        assert config.get_timeout(0) == 10.0

        # 第一次重试 (10 * 1.5^1 = 15)
        assert config.get_timeout(1) == 15.0

        # 第二次重试 (10 * 1.5^2 = 22.5)
        assert config.get_timeout(2) == 22.5

        # 第三次重试 (10 * 1.5^3 = 33.75, 但限制在max=30)
        assert config.get_timeout(3) == 30.0


class TestTimeoutManager:
    """TimeoutManager测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用管理器"""
        return TimeoutManager()

    @pytest.fixture
    def custom_manager(self):
        """创建自定义配置的管理器"""
        custom_configs = {
            TimeoutCategory.NETWORK_REALTIME: TimeoutConfig(default=5.0, min=2.0, max=15.0),
            TimeoutCategory.DB_QUERY: TimeoutConfig(default=60.0, min=10.0, max=180.0),
        }
        return TimeoutManager(custom_configs)

    def test_default_configurations(self, manager):
        """测试默认配置是否正确加载"""
        # 验证所有类别都有配置
        for category in TimeoutCategory:
            config = manager.get_config(category)
            assert config is not None
            assert isinstance(config, TimeoutConfig)

    def test_get_timeout_network_realtime(self, manager):
        """测试实时网络请求超时"""
        timeout = manager.get_timeout(TimeoutCategory.NETWORK_REALTIME)
        assert timeout == 10.0  # 默认配置

    def test_get_timeout_with_retry(self, manager):
        """测试带重试的超时获取"""
        # 第一次尝试
        timeout0 = manager.get_timeout(TimeoutCategory.NETWORK_HISTORICAL, 0)
        assert timeout0 == 30.0

        # 第一次重试
        timeout1 = manager.get_timeout(TimeoutCategory.NETWORK_HISTORICAL, 1)
        assert timeout1 == 45.0  # 30 * 1.5

        # 第二次重试
        timeout2 = manager.get_timeout(TimeoutCategory.NETWORK_HISTORICAL, 2)
        assert timeout2 == 67.5  # 30 * 1.5^2

    def test_custom_configuration(self, custom_manager):
        """测试自定义配置覆盖"""
        # 自定义的配置应该被使用
        timeout = custom_manager.get_timeout(TimeoutCategory.NETWORK_REALTIME)
        assert timeout == 5.0  # 自定义值

        # 未自定义的应该使用默认值
        timeout = custom_manager.get_timeout(TimeoutCategory.CACHE_GET)
        assert timeout == 5.0  # 默认值

    def test_update_config(self, manager):
        """测试更新配置"""
        new_config = TimeoutConfig(default=100.0, min=50.0, max=200.0)
        manager.update_config(TimeoutCategory.DB_TRANSACTION, new_config)

        timeout = manager.get_timeout(TimeoutCategory.DB_TRANSACTION)
        assert timeout == 100.0

    def test_get_timeout_for_api_realtime(self, manager):
        """测试API智能超时 - 实时数据"""
        realtime_apis = [
            "realtime_quotes",
            "stock_spot_em",
            "tick_data",
            "orderbook_depth",
            "quote_snapshot",
        ]

        for api_name in realtime_apis:
            timeout = manager.get_timeout_for_api(api_name)
            assert timeout == 10.0  # 实时数据默认10秒

    def test_get_timeout_for_api_historical(self, manager):
        """测试API智能超时 - 历史数据"""
        historical_apis = [
            "stock_hist_data",
            "daily_kline",
            "weekly_data",
            "monthly_stats",
            "kline_min",
        ]

        for api_name in historical_apis:
            timeout = manager.get_timeout_for_api(api_name)
            assert timeout == 30.0  # 历史数据默认30秒

    def test_get_timeout_for_api_batch(self, manager):
        """测试API智能超时 - 批量请求"""
        # 批量请求应该使用更长的超时
        timeout = manager.get_timeout_for_api("any_api", is_batch=True)
        assert timeout == 60.0  # 批量请求默认60秒

        # 即使是实时API，批量请求也应该使用批量超时
        timeout = manager.get_timeout_for_api("realtime_quotes", is_batch=True)
        assert timeout == 60.0

    def test_get_timeout_for_api_default(self, manager):
        """测试API智能超时 - 默认情况"""
        # 不匹配任何关键词的API应该使用历史数据超时
        timeout = manager.get_timeout_for_api("unknown_api")
        assert timeout == 30.0

    def test_all_categories_have_config(self, manager):
        """测试所有类别都有配置"""
        for category in TimeoutCategory:
            config = manager.get_config(category)
            assert config is not None
            assert config.default > 0
            assert config.min > 0
            assert config.max >= config.default
            assert config.max >= config.min

    def test_timeout_hierarchy(self, manager):
        """测试超时时间的层次关系"""
        # 缓存操作应该最快
        cache_timeout = manager.get_timeout(TimeoutCategory.CACHE_GET)

        # 网络健康检查应该很快
        health_timeout = manager.get_timeout(TimeoutCategory.NETWORK_HEALTH)

        # 实时数据比历史数据快
        realtime_timeout = manager.get_timeout(TimeoutCategory.NETWORK_REALTIME)
        historical_timeout = manager.get_timeout(TimeoutCategory.NETWORK_HISTORICAL)

        # 批量操作最慢
        batch_timeout = manager.get_timeout(TimeoutCategory.NETWORK_BATCH)

        # 验证层次关系
        assert cache_timeout <= health_timeout
        assert health_timeout <= realtime_timeout
        assert realtime_timeout < historical_timeout
        assert historical_timeout < batch_timeout


class TestTimeoutManagerSingleton:
    """测试全局超时管理器单例"""

    def test_get_timeout_manager_singleton(self):
        """测试获取单例管理器"""
        manager1 = get_timeout_manager()
        manager2 = get_timeout_manager()

        # 应该是同一个实例
        assert manager1 is manager2

    def test_configure_timeouts(self):
        """测试配置全局超时"""
        # 配置自定义超时
        custom_configs = {
            TimeoutCategory.NETWORK_REALTIME: TimeoutConfig(default=3.0, min=1.0, max=10.0)
        }
        configure_timeouts(custom_configs)

        # 获取管理器应该使用新配置
        manager = get_timeout_manager()
        timeout = manager.get_timeout(TimeoutCategory.NETWORK_REALTIME)
        assert timeout == 3.0

        # 重置为默认配置
        configure_timeouts({})


class TestTimeoutCategories:
    """测试超时类别枚举"""

    def test_category_names(self):
        """测试类别名称"""
        assert TimeoutCategory.NETWORK_REALTIME.value == "network_realtime"
        assert TimeoutCategory.DB_CONNECT.value == "db_connect"
        assert TimeoutCategory.CACHE_GET.value == "cache_get"
        assert TimeoutCategory.COMPONENT_INIT.value == "component_init"

    def test_all_categories_unique(self):
        """测试所有类别值唯一"""
        values = [cat.value for cat in TimeoutCategory]
        assert len(values) == len(set(values))


class TestEdgeCases:
    """边界情况测试"""

    def test_zero_attempt_always_returns_default(self):
        """测试0次尝试总是返回默认值"""
        config = TimeoutConfig(default=20.0, min=10.0, max=100.0)
        for _ in range(10):
            assert config.get_timeout(0) == 20.0

    def test_very_large_retry_count(self):
        """测试大量重试不会超过最大值"""
        config = TimeoutConfig(default=1.0, min=0.5, max=10.0, retry_multiplier=2.0)

        # 即使重试100次，也不应该超过最大值
        for attempt in range(100):
            timeout = config.get_timeout(attempt)
            assert timeout <= 10.0

    def test_min_greater_than_default(self):
        """测试最小值大于默认值的情况"""
        # 这种配置虽然不合理，但不应该崩溃
        config = TimeoutConfig(default=5.0, min=10.0, max=20.0)
        assert config.get_timeout(0) == 5.0  # 仍然返回默认值

    def test_negative_attempt(self):
        """测试负数尝试次数"""
        config = TimeoutConfig(default=10.0, min=5.0, max=30.0)
        # 负数应该当作0处理
        assert config.get_timeout(-1) == 10.0

    def test_none_category(self):
        """测试不存在的类别"""
        manager = TimeoutManager()
        # 返回默认的30秒
        timeout = manager.get_timeout(None, 0)
        assert timeout == 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
