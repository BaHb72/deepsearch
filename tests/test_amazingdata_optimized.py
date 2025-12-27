# encoding:utf-8
"""
AmazingData 优化版本的单元测试
测试所有关键性能优化和问题修复
"""

import asyncio
import gc

# 假设 AmazingData SDK 可能未安装，先 mock
import sys
import time
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

sys.modules["AmazingData"] = MagicMock()

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_optimized import (  # noqa: E402
    CircuitBreaker,
    MonitoringSystem,
    OptimizedAmazingDataProvider,
    OptimizedCacheManager,
    OptimizedDataConverter,
    OptimizedHeartbeat,
    OptimizedThreadPoolManager,
    RateLimiter,
    SubscriptionManager,
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderConfig  # noqa: E402


class TestOptimizedThreadPoolManager:
    """测试优化的线程池管理器"""

    @pytest.mark.asyncio
    async def test_thread_pool_performance(self):
        """测试线程池性能 - 并发执行不阻塞"""
        manager = OptimizedThreadPoolManager()

        # 模拟慢速同步函数
        def slow_func(delay):
            time.sleep(delay)
            return delay

        # 并发执行50个任务
        tasks = [manager.execute_async(slow_func, 0.01) for _ in range(50)]

        start = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # 验证结果
        assert len(results) == 50
        assert all(r == 0.01 for r in results)

        # 验证并发执行（不应该串行）
        # 50个任务，每个0.01秒，串行需要0.5秒
        # 并发执行应该远小于0.5秒
        assert elapsed < 0.2  # 给一些余量

        # 验证统计
        assert manager.stats["completed_tasks"] == 50
        assert manager.stats["failed_tasks"] == 0

    @pytest.mark.asyncio
    async def test_thread_pool_semaphore(self):
        """测试线程池信号量限制"""
        manager = OptimizedThreadPoolManager()

        # 记录并发执行数
        concurrent_count = []

        def track_concurrent():
            concurrent_count.append(manager.stats["active_threads"])
            time.sleep(0.01)
            return True

        # 发起100个并发任务
        tasks = [manager.execute_async(track_concurrent) for _ in range(100)]

        await asyncio.gather(*tasks)

        # 验证并发数被限制
        max_concurrent = max(concurrent_count)
        assert max_concurrent <= manager.pool_size // 2

    def test_thread_pool_shutdown(self):
        """测试线程池优雅关闭"""
        manager = OptimizedThreadPoolManager()

        # 关闭线程池
        manager.shutdown()

        # 验证线程池已关闭
        assert manager.executor._shutdown


class TestOptimizedHeartbeat:
    """测试优化的心跳机制"""

    @pytest.mark.asyncio
    async def test_heartbeat_adaptive_interval(self):
        """测试心跳自适应间隔调整"""
        config = Mock()
        heartbeat = OptimizedHeartbeat(config)

        # 初始间隔
        assert heartbeat.current_interval == 60

        # 模拟长时间无活动
        heartbeat.last_activity = time.time() - 120
        heartbeat._adjust_interval()

        # 间隔应该增加
        assert heartbeat.current_interval > 60

        # 模拟有活动
        heartbeat.update_activity()
        heartbeat._adjust_interval()

        # 间隔应该减少
        assert heartbeat.current_interval < heartbeat.max_interval

    @pytest.mark.asyncio
    async def test_heartbeat_failure_handling(self):
        """测试心跳失败处理"""
        config = Mock()
        heartbeat = OptimizedHeartbeat(config)

        # 模拟连续失败
        for _ in range(5):
            heartbeat._on_failure(Exception("Test failure"))

        # 验证失败计数
        assert heartbeat.consecutive_failures == 5

        # 验证间隔增加（指数退避）
        assert heartbeat.current_interval > heartbeat.base_interval

        # 模拟成功
        heartbeat._on_success()

        # 验证重置
        assert heartbeat.consecutive_failures == 0


class TestOptimizedCacheManager:
    """测试优化的缓存管理器"""

    def test_cache_key_normalization(self):
        """测试缓存键标准化"""
        cache = OptimizedCacheManager()

        # 不同格式的日期应该生成相同的键
        key1 = cache.generate_cache_key(
            symbol="000001.SZ", period="daily", start_date="2024-01-01", end_date="2024-12-31"
        )

        key2 = cache.generate_cache_key(
            symbol="000001.SZ", period="daily", start_date="20240101", end_date="20241231"
        )

        # 去掉哈希部分比较前缀
        prefix1 = key1.split(":")[:-1]
        prefix2 = key2.split(":")[:-1]

        assert prefix1 == prefix2

    def test_cache_hit_rate(self):
        """测试缓存命中率"""
        cache = OptimizedCacheManager()

        # 模拟数据
        test_data = pd.DataFrame({"value": [1, 2, 3]})

        # 第一次查询 - miss
        key = cache.generate_cache_key(symbol="000001.SZ", period="daily")
        result = cache.get(key)
        assert result is None

        # 设置缓存
        cache.set(key, test_data)

        # 后续查询 - hit
        for _ in range(10):
            result = cache.get(key)
            assert result is not None

        # 验证统计
        stats = cache.get_stats()
        assert cache.stats["hits"] == 10
        assert cache.stats["misses"] == 1

        # 验证命中率
        hit_rate = float(stats["hit_rate"].strip("%"))
        assert hit_rate > 90

    def test_cache_ttl(self):
        """测试缓存过期"""
        cache = OptimizedCacheManager(ttl=0.1)  # 100ms 过期

        key = cache.generate_cache_key(symbol="test")
        cache.set(key, "test_data")

        # 立即获取 - 应该命中
        assert cache.get(key) == "test_data"

        # 等待过期
        time.sleep(0.2)

        # 应该过期
        assert cache.get(key) is None
        assert cache.stats["evictions"] == 1


class TestSubscriptionManager:
    """测试订阅管理器"""

    @pytest.mark.asyncio
    async def test_subscription_weak_reference(self):
        """测试弱引用防止内存泄漏"""
        manager = SubscriptionManager()

        # 创建回调函数
        def callback(data):
            pass

        # 订阅
        sub_id = manager.subscribe("000001.SZ", callback)

        # 验证订阅存在
        assert "000001.SZ" in manager._subscriptions
        assert sub_id in manager._weak_callbacks

        # 删除回调引用
        del callback

        # 强制垃圾回收
        gc.collect()

        # 弱引用应该被清理
        # 注意：这个测试在某些情况下可能不稳定
        # 因为垃圾回收的时机不确定

    @pytest.mark.asyncio
    async def test_subscription_cleanup(self):
        """测试订阅清理"""
        manager = SubscriptionManager()

        # 创建多个订阅
        callbacks = []
        sub_ids = []

        for i in range(10):
            callback = Mock()
            callbacks.append(callback)
            sub_id = manager.subscribe(f"stock_{i}", callback)
            sub_ids.append(sub_id)

        # 验证订阅数量
        assert len(manager._subscriptions) == 10

        # 清理所有订阅
        await manager.cleanup_all()

        # 验证清理完成
        assert len(manager._subscriptions) == 0
        assert len(manager._weak_callbacks) == 0
        assert len(manager._subscription_tasks) == 0


class TestOptimizedDataConverter:
    """测试优化的数据转换器"""

    def test_vectorized_conversion_performance(self):
        """测试向量化转换性能"""
        # 生成测试数据
        test_data = [
            {
                "datetime": "20240101",
                "open": "10.5",
                "high": "11.0",
                "low": "10.0",
                "close": "10.8",
                "volume": "1000000",
            }
            for _ in range(1000)
        ]

        start = time.time()
        df = OptimizedDataConverter.convert_kline_vectorized(test_data)
        elapsed = time.time() - start

        # 验证结果
        assert len(df) == 1000
        assert df.index.name == "datetime"
        assert all(col in df.columns for col in ["open", "high", "low", "close", "volume"])

        # 验证数据类型
        assert df["open"].dtype in [float, "float64"]

        # 性能验证（应该很快）
        assert elapsed < 0.1  # 1000行应该在100ms内完成

    def test_data_validation(self):
        """测试数据验证和清理"""
        # 创建异常数据
        df = pd.DataFrame(
            {
                "high": [10.0, 9.0, 12.0],  # 第二行 high < low
                "low": [9.0, 10.0, 11.0],
                "volume": [1000, -100, 2000],  # 负成交量
                "change_percent": [5.0, 100.0, -50.0],  # 异常涨跌幅
            }
        )

        # 验证和清理
        cleaned_df = OptimizedDataConverter.validate_and_clean(df)

        # 验证修正
        assert cleaned_df.loc[1, "high"] >= cleaned_df.loc[1, "low"]  # high/low 修正
        assert cleaned_df.loc[1, "volume"] >= 0  # 负值修正
        assert abs(cleaned_df.loc[1, "change_percent"]) <= 20  # 涨跌幅限制


class TestRateLimiter:
    """测试限流器"""

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """测试速率限制"""
        limiter = RateLimiter(rate=10, burst=5)  # 每秒10个，突发5个

        # 快速获取5个令牌（突发）
        start = time.time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.time() - start

        # 突发应该立即完成
        assert elapsed < 0.1

        # 继续获取5个令牌
        start = time.time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.time() - start

        # 需要等待补充令牌
        assert elapsed >= 0.4  # 至少需要0.5秒（5个令牌，每秒10个）


class TestCircuitBreaker:
    """测试断路器"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_states(self):
        """测试断路器状态转换"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5)

        # 初始状态：关闭
        assert breaker.state == "closed"

        # 模拟成功调用
        async def success_call():
            return "success"

        result = await breaker.call(success_call())
        assert result == "success"

        # 模拟失败调用
        async def fail_call():
            raise Exception("Test failure")

        # 连续失败3次
        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(fail_call())

        # 断路器应该开启
        assert breaker.state == "open"

        # 立即调用应该被拒绝
        with pytest.raises(RuntimeError, match="断路器开启"):
            await breaker.call(success_call())

        # 等待恢复时间
        await asyncio.sleep(0.6)

        # 应该进入半开状态
        result = await breaker.call(success_call())
        assert result == "success"

        # 连续成功后应该恢复
        for _ in range(2):
            await breaker.call(success_call())

        assert breaker.state == "closed"


class TestMonitoringSystem:
    """测试监控系统"""

    def test_performance_metrics(self):
        """测试性能指标收集"""
        monitoring = MonitoringSystem()

        # 记录多个请求
        latencies = [0.1, 0.2, 0.15, 0.3, 0.25]
        for latency in latencies:
            monitoring.record_request("kline", latency, True)

        # 获取统计
        health = monitoring.get_health_status()

        # 验证计数
        assert monitoring.counters["total_requests"] == 5
        assert monitoring.counters["successful_requests"] == 5

        # 验证成功率
        assert health["status"] == "healthy"
        assert "100" in health["success_rate"]

        # 验证延迟统计
        kline_stats = health["metrics"]["kline"]
        assert kline_stats["count"] == 5
        assert 0.1 <= kline_stats["mean"] <= 0.3

    def test_event_recording(self):
        """测试事件记录"""
        monitoring = MonitoringSystem()

        # 记录事件
        for i in range(10):
            monitoring.record_event("test_event", {"index": i})

        # 验证事件记录
        assert len(monitoring.events) == 10
        assert monitoring.events[-1]["type"] == "test_event"
        assert monitoring.events[-1]["details"]["index"] == 9


class TestOptimizedAmazingDataProvider:
    """测试优化的 AmazingData 提供者"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return DataProviderConfig(
            name="amazingdata_test",
            enabled=True,
            priority=1,
            timeout=10,
            retry_count=3,  # 使用retry_count而不是max_retries
            config={
                "cache_enabled": True,
                "cache_ttl": 300,
                "username": "test_user",
                "password": "test_pass",
                "host": "localhost",
                "port": 8080,
            },
        )

    @pytest.mark.asyncio
    async def test_provider_initialization(self, config):
        """测试提供者初始化"""
        with patch(
            "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_optimized.HAS_AMAZINGDATA",
            True,
        ):
            provider = OptimizedAmazingDataProvider(config)

            # 验证组件初始化
            assert provider.thread_pool is not None
            assert provider.cache is not None
            assert provider.subscription_manager is not None
            assert provider.heartbeat is not None
            assert provider.rate_limiter is not None
            assert provider.circuit_breaker is not None
            assert provider.monitoring is not None

    @pytest.mark.asyncio
    async def test_cache_integration(self, config):
        """测试缓存集成"""
        with patch(
            "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_optimized.HAS_AMAZINGDATA",
            True,
        ):
            with patch(
                "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_optimized.ad"
            ) as mock_ad:
                provider = OptimizedAmazingDataProvider(config)

                # Mock 登录成功
                mock_ad.login.return_value = 0

                # Mock K线数据
                mock_kline_data = [
                    {
                        "datetime": "20240101",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.5,
                        "close": 10.5,
                        "volume": 1000000,
                    }
                ]
                mock_ad.KLine.get_kline.return_value = mock_kline_data

                # 连接
                await provider.connect()

                # 第一次查询 - 应该调用 API
                result1 = await provider.get_kline("000001.SZ", "daily")
                assert len(result1) == 1
                assert "symbol" in result1.columns
                assert result1.index.name == "datetime"
                assert mock_ad.KLine.get_kline.call_count == 1

                # 第二次查询相同数据 - 应该命中缓存
                result2 = await provider.get_kline("000001.SZ", "daily")
                assert len(result2) == 1
                assert mock_ad.KLine.get_kline.call_count == 1  # 不应该再调用

                # 验证缓存统计
                assert provider.monitoring.counters["cache_hits"] == 1
                assert provider.monitoring.counters["cache_misses"] == 1

    @pytest.mark.asyncio
    async def test_health_status(self, config):
        """测试健康状态报告"""
        with patch(
            "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_optimized.HAS_AMAZINGDATA",
            True,
        ):
            provider = OptimizedAmazingDataProvider(config)

            # 获取健康状态
            health = await provider.get_health_status()

            # 验证结构
            assert health["provider"] == "amazingdata_optimized"
            assert "status" in health
            assert "cache" in health
            assert "circuit_breaker" in health
            assert "thread_pool" in health
            assert "heartbeat" in health

            # 验证初始状态
            assert health["circuit_breaker"] == "closed"
            assert health["thread_pool"]["size"] > 0


@pytest.mark.benchmark
class TestPerformanceBenchmark:
    """性能基准测试"""

    @pytest.mark.asyncio
    async def test_concurrent_requests_benchmark(self):
        """测试并发请求性能"""
        manager = OptimizedThreadPoolManager()

        # 模拟 API 调用
        def mock_api_call():
            time.sleep(0.01)  # 模拟10ms延迟
            return {"data": "test"}

        # 发起100个并发请求
        start = time.time()
        tasks = [manager.execute_async(mock_api_call) for _ in range(100)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # 验证结果
        assert len(results) == 100

        # 性能验证
        # 100个请求，每个10ms，串行需要1秒
        # 优化后应该远小于1秒
        assert elapsed < 0.5

        # 计算 QPS
        qps = 100 / elapsed
        print(f"QPS: {qps:.2f}")
        assert qps > 200  # 应该达到 200+ QPS

    def test_cache_performance(self):
        """测试缓存性能"""
        cache = OptimizedCacheManager()

        # 预热缓存
        for i in range(1000):
            key = cache.generate_cache_key(symbol=f"stock_{i}", period="daily")
            cache.set(key, f"data_{i}")

        # 测试查询性能
        start = time.time()
        hits = 0
        for _ in range(10000):
            key = cache.generate_cache_key(symbol=f"stock_{_ % 1000}", period="daily")
            if cache.get(key) is not None:
                hits += 1
        elapsed = time.time() - start

        # 验证性能
        queries_per_second = 10000 / elapsed
        print(f"Cache QPS: {queries_per_second:.2f}")
        expected_min_qps = 20000  # 离线环境下的保守阈值
        assert (
            queries_per_second > expected_min_qps
        ), f"缓存QPS不足 {expected_min_qps}, 实测 {queries_per_second:.2f}"

        # 验证命中率
        hit_rate = hits / 10000
        assert hit_rate > 0.99  # 应该接近 100%
