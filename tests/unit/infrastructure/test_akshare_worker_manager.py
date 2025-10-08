"""
AkShare Worker管理器单元测试

测试WorkerManager的核心功能：
1. Worker健康检查
2. 负载均衡选择
3. 熔断器机制
4. 状态管理
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

from deepsearch.infrastructure.providers.implementations.akshare.worker_manager import (
    WorkerManager,
    WorkerState,
)


class TestWorkerManager:
    """WorkerManager单元测试"""

    @pytest.fixture
    def worker_urls(self):
        """测试用Worker URLs"""
        return [
            "https://worker1.example.com",
            "https://worker2.example.com",
            "https://worker3.example.com",
        ]

    @pytest.fixture
    def single_worker_url(self):
        """单个Worker URL"""
        return ["https://worker.example.com"]

    @pytest.fixture
    async def manager_multi(self, worker_urls):
        """多Worker管理器"""
        manager = WorkerManager(worker_urls, strategy="round_robin")
        manager.session = Mock(spec=aiohttp.ClientSession)
        return manager

    @pytest.fixture
    async def manager_single(self, single_worker_url):
        """单Worker管理器"""
        manager = WorkerManager(single_worker_url, strategy="single")
        manager.session = Mock(spec=aiohttp.ClientSession)
        return manager

    @pytest.mark.asyncio
    async def test_initialization(self, worker_urls):
        """测试初始化"""
        manager = WorkerManager(worker_urls)

        # 验证Worker初始化状态
        assert len(manager.workers) == 3
        for url in worker_urls:
            assert url in manager.workers
            assert manager.workers[url]["state"] == WorkerState.HEALTHY
            assert manager.workers[url]["errors"] == 0
            assert manager.workers[url]["requests"] == 0

        # 验证策略设置
        assert manager.strategy == "round_robin"

    @pytest.mark.asyncio
    async def test_single_worker_strategy(self, single_worker_url):
        """测试单Worker策略"""
        manager = WorkerManager(single_worker_url)
        assert manager.strategy == "single"

    @pytest.mark.asyncio
    async def test_health_check_success(self, manager_multi):
        """测试健康检查成功"""
        url = "https://worker1.example.com"

        # 模拟成功的健康检查响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "healthy"})

        mock_get = AsyncMock(return_value=mock_response)
        manager_multi.session.get = mock_get
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        # 执行健康检查
        result = await manager_multi._check_worker_health(url)

        # 验证结果
        assert result is True
        assert manager_multi.workers[url]["state"] == WorkerState.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_failure(self, manager_multi):
        """测试健康检查失败"""
        url = "https://worker1.example.com"

        # 模拟失败的健康检查响应
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_get = AsyncMock(return_value=mock_response)
        manager_multi.session.get = mock_get
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        # 执行健康检查
        result = await manager_multi._check_worker_health(url)

        # 验证结果
        assert result is False
        assert manager_multi.workers[url]["state"] == WorkerState.SUSPICIOUS

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, manager_multi):
        """测试健康检查超时"""
        url = "https://worker1.example.com"

        # 模拟超时
        manager_multi.session.get = AsyncMock(side_effect=asyncio.TimeoutError())

        # 执行健康检查
        result = await manager_multi._check_worker_health(url)

        # 验证结果
        assert result is False
        assert manager_multi.workers[url]["state"] == WorkerState.SUSPICIOUS

    def test_round_robin_selection(self, manager_multi):
        """测试Round-robin负载均衡"""
        # 第一次选择
        selected1 = manager_multi.select_worker()
        assert selected1 == "https://worker1.example.com"
        assert manager_multi.workers[selected1]["requests"] == 1

        # 第二次选择
        selected2 = manager_multi.select_worker()
        assert selected2 == "https://worker2.example.com"
        assert manager_multi.workers[selected2]["requests"] == 1

        # 第三次选择
        selected3 = manager_multi.select_worker()
        assert selected3 == "https://worker3.example.com"
        assert manager_multi.workers[selected3]["requests"] == 1

        # 第四次选择（循环回第一个）
        selected4 = manager_multi.select_worker()
        assert selected4 == "https://worker1.example.com"
        assert manager_multi.workers[selected4]["requests"] == 2

    def test_single_worker_selection(self, manager_single):
        """测试单Worker选择"""
        # 多次选择都应该返回同一个Worker
        for _ in range(5):
            selected = manager_single.select_worker()
            assert selected == "https://worker.example.com"

        assert manager_single.workers["https://worker.example.com"]["requests"] == 5

    def test_circuit_breaker_trigger(self, manager_multi):
        """测试熔断器触发"""
        url = "https://worker1.example.com"

        # 模拟连续失败
        for _ in range(5):
            manager_multi.record_failure(url)

        # 验证熔断状态
        assert manager_multi.workers[url]["state"] == WorkerState.UNHEALTHY
        assert manager_multi.workers[url]["errors"] == 5

        # 验证该Worker不能被选择
        assert not manager_multi._can_use_worker(url)

    def test_circuit_breaker_recovery(self, manager_multi):
        """测试熔断器恢复"""
        url = "https://worker1.example.com"

        # 触发熔断
        for _ in range(5):
            manager_multi.record_failure(url)
        assert manager_multi.workers[url]["state"] == WorkerState.UNHEALTHY

        # 模拟时间流逝（超过恢复时间）
        past_time = datetime.now() - timedelta(seconds=61)
        manager_multi.workers[url]["last_error"] = past_time

        # 验证可以重新使用
        assert manager_multi._can_use_worker(url)
        assert manager_multi.workers[url]["state"] == WorkerState.SUSPICIOUS

    def test_record_success(self, manager_multi):
        """测试记录成功请求"""
        url = "https://worker1.example.com"

        # 先设置为可疑状态
        manager_multi.workers[url]["state"] = WorkerState.SUSPICIOUS
        manager_multi.workers[url]["errors"] = 3

        # 记录成功
        manager_multi.record_success(url)

        # 验证状态恢复
        assert manager_multi.workers[url]["state"] == WorkerState.HEALTHY
        assert manager_multi.workers[url]["errors"] == 0

    def test_record_failure(self, manager_multi):
        """测试记录失败请求"""
        url = "https://worker1.example.com"

        # 记录第一次失败
        manager_multi.record_failure(url)
        assert manager_multi.workers[url]["errors"] == 1
        assert manager_multi.workers[url]["state"] == WorkerState.SUSPICIOUS

        # 记录更多失败直到熔断
        for _ in range(4):
            manager_multi.record_failure(url)

        assert manager_multi.workers[url]["errors"] == 5
        assert manager_multi.workers[url]["state"] == WorkerState.UNHEALTHY

    def test_get_statistics(self, manager_multi):
        """测试获取统计信息"""
        # 设置不同状态的Worker
        manager_multi.workers["https://worker1.example.com"]["state"] = WorkerState.HEALTHY
        manager_multi.workers["https://worker2.example.com"]["state"] = WorkerState.SUSPICIOUS
        manager_multi.workers["https://worker3.example.com"]["state"] = WorkerState.UNHEALTHY

        # 获取统计
        stats = manager_multi.get_statistics()

        # 验证统计信息
        assert stats["total_workers"] == 3
        assert stats["healthy_workers"] == 1
        assert stats["suspicious_workers"] == 1
        assert stats["unhealthy_workers"] == 1
        assert len(stats["workers"]) == 3

    def test_no_available_workers(self, manager_multi):
        """测试没有可用Worker的情况"""
        # 将所有Worker设置为不健康
        for url in manager_multi.workers:
            manager_multi.workers[url]["state"] = WorkerState.UNHEALTHY

        # 尝试选择Worker
        selected = manager_multi.select_worker()
        assert selected is None

    def test_partial_worker_failure(self, manager_multi):
        """测试部分Worker失败的情况"""
        # 将第一个Worker设置为不健康
        manager_multi.workers["https://worker1.example.com"]["state"] = WorkerState.UNHEALTHY

        # 应该能够选择其他健康的Worker
        available_workers = []
        for _ in range(4):
            worker = manager_multi.select_worker()
            if worker:
                available_workers.append(worker)

        # 验证不会选择不健康的Worker
        assert "https://worker1.example.com" not in available_workers
        assert "https://worker2.example.com" in available_workers
        assert "https://worker3.example.com" in available_workers

    @pytest.mark.asyncio
    async def test_cleanup(self, manager_multi):
        """测试资源清理"""
        # 创建真实的session
        manager_multi.session = AsyncMock(spec=aiohttp.ClientSession)
        manager_multi.session.close = AsyncMock()

        # 执行清理
        await manager_multi.cleanup()

        # 验证session被关闭
        manager_multi.session.close.assert_called_once()
        assert manager_multi.session is None

    @pytest.mark.asyncio
    async def test_initialize_with_all_unhealthy(self, manager_multi):
        """测试初始化时所有节点都不健康的情况"""

        # 模拟所有健康检查失败
        async def mock_check_health(url):
            manager_multi._update_worker_state(url, WorkerState.UNHEALTHY)
            return False

        manager_multi._check_worker_health = mock_check_health

        # 执行初始化
        await manager_multi.initialize()

        # 验证所有Worker被重置为可疑状态（允许重试）
        for worker in manager_multi.workers.values():
            assert worker["state"] == WorkerState.SUSPICIOUS

    def test_success_rate_calculation(self, manager_multi):
        """测试成功率计算"""
        url = "https://worker1.example.com"

        # 模拟10次请求，3次失败
        for _ in range(7):
            manager_multi.workers[url]["requests"] += 1
            manager_multi.record_success(url)

        for _ in range(3):
            manager_multi.workers[url]["requests"] += 1
            manager_multi.record_failure(url)

        # 成功率应该是70%
        assert manager_multi.workers[url]["success_rate"] == 70.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
