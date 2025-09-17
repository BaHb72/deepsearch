"""
Worker节点管理器
负责管理Cloudflare Worker节点的健康检查、状态管理和节点选择
"""
import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any
import aiohttp
from loguru import logger


class WorkerState(Enum):
    """Worker 节点状态枚举"""
    HEALTHY = "healthy"         # 健康状态
    SUSPICIOUS = "suspect"       # 可疑状态（有失败但仍可尝试）
    UNHEALTHY = "unhealthy"     # 不健康状态（熔断）


class WorkerManager:
    """Worker节点管理器"""

    def __init__(self, worker_urls: List[str], strategy: str = "round_robin"):
        """
        初始化Worker管理器

        Args:
            worker_urls: Worker节点URL列表
            strategy: 负载均衡策略 ("round_robin", "single")
        """
        self.worker_urls = worker_urls
        self.strategy = strategy

        # Worker 节点状态管理
        self.workers = {}
        for url in self.worker_urls:
            self.workers[url] = {
                "state": WorkerState.HEALTHY,
                "requests": 0,
                "errors": 0,
                "last_error": None,
                "last_success": datetime.now(),
                "last_check": None,
                "response_time": 0,
                "success_rate": 100.0,
            }

        # 熔断器配置
        self.circuit_breaker_config = {
            "failure_threshold": 5,        # 连续失败次数阈值
            "recovery_timeout": 60,         # 熔断恢复时间（秒）
            "half_open_max_calls": 2,       # 半开状态最大尝试次数
            "monitoring_window": 300,       # 监控窗口（秒）
        }

        # Round-robin 索引
        self.current_worker_index = 0

        # 异步会话
        self.session = None

    async def initialize(self):
        """初始化异步会话和检查所有Worker健康状态"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        # 并发检查所有 Worker 健康状态
        check_tasks = []
        for url in self.worker_urls:
            check_tasks.append(self._check_worker_health(url))

        results = await asyncio.gather(*check_tasks, return_exceptions=True)

        healthy_count = sum(1 for r in results if r is True)
        logger.info(f"Worker 健康检查完成: {healthy_count}/{len(self.worker_urls)} 节点健康")

        # 如果所有节点都不健康，重置为可疑状态以允许重试
        if healthy_count == 0:
            logger.warning("所有 Worker 节点不健康，重置为可疑状态")
            for url in self.worker_urls:
                self.workers[url]["state"] = WorkerState.SUSPICIOUS

    async def _check_worker_health(self, url: str) -> bool:
        """
        检查单个 Worker 节点健康状态

        Args:
            url: Worker URL

        Returns:
            是否健康
        """
        try:
            health_url = f"{url}/health"
            start_time = time.time()

            async with self.session.get(
                health_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                response_time = (time.time() - start_time) * 1000  # 转换为毫秒

                if response.status == 200:
                    result = await response.json()
                    if result.get("status") == "healthy":
                        self._update_worker_state(url, WorkerState.HEALTHY)
                        self.workers[url]["response_time"] = response_time
                        self.workers[url]["last_check"] = datetime.now()
                        logger.debug(f"Worker {url} 健康检查通过，响应时间: {response_time:.2f}ms")
                        return True

                self._update_worker_state(url, WorkerState.SUSPICIOUS)
                logger.warning(f"Worker {url} 健康检查失败: 状态码 {response.status}")
                return False

        except asyncio.TimeoutError:
            self._update_worker_state(url, WorkerState.SUSPICIOUS)
            logger.warning(f"Worker {url} 健康检查超时")
            return False
        except Exception as e:
            self._update_worker_state(url, WorkerState.UNHEALTHY)
            logger.error(f"Worker {url} 健康检查异常: {e}")
            return False

    def _update_worker_state(self, url: str, state: Union[bool, WorkerState]) -> None:
        """
        更新 Worker 节点状态

        Args:
            url: Worker URL
            state: 新状态（布尔值或 WorkerState 枚举）
        """
        if url not in self.workers:
            return

        worker = self.workers[url]

        # 处理布尔值输入
        if isinstance(state, bool):
            if state:
                # 成功 - 重置错误计数
                worker["errors"] = 0
                worker["last_success"] = datetime.now()

                # 根据当前状态决定新状态
                if worker["state"] == WorkerState.UNHEALTHY:
                    # 从熔断恢复到可疑状态
                    worker["state"] = WorkerState.SUSPICIOUS
                    logger.info(f"Worker {url} 从熔断状态恢复到可疑状态")
                else:
                    worker["state"] = WorkerState.HEALTHY

            else:
                # 失败 - 增加错误计数
                worker["errors"] += 1
                worker["last_error"] = datetime.now()

                # 检查是否需要熔断
                if worker["errors"] >= self.circuit_breaker_config["failure_threshold"]:
                    worker["state"] = WorkerState.UNHEALTHY
                    logger.warning(f"Worker {url} 进入熔断状态，错误次数: {worker['errors']}")
                elif worker["state"] == WorkerState.HEALTHY:
                    worker["state"] = WorkerState.SUSPICIOUS

        else:
            # 直接设置状态
            old_state = worker["state"]
            worker["state"] = state
            if old_state != state:
                logger.info(f"Worker {url} 状态变更: {old_state.value} -> {state.value}")

        # 更新成功率
        total = worker["requests"]
        if total > 0:
            worker["success_rate"] = ((total - worker["errors"]) / total) * 100

    def _can_use_worker(self, url: str) -> bool:
        """
        判断 Worker 节点是否可用

        Args:
            url: Worker URL

        Returns:
            是否可用
        """
        if url not in self.workers:
            return False

        worker = self.workers[url]

        # 健康或可疑状态可以使用
        if worker["state"] in [WorkerState.HEALTHY, WorkerState.SUSPICIOUS]:
            return True

        # 熔断状态检查恢复时间
        if worker["state"] == WorkerState.UNHEALTHY:
            if worker["last_error"]:
                elapsed = (datetime.now() - worker["last_error"]).total_seconds()
                if elapsed >= self.circuit_breaker_config["recovery_timeout"]:
                    # 尝试恢复到可疑状态
                    worker["state"] = WorkerState.SUSPICIOUS
                    worker["errors"] = 0  # 重置错误计数
                    logger.info(f"Worker {url} 熔断超时，尝试恢复")
                    return True

        return False

    def select_worker(self) -> Optional[str]:
        """
        选择一个可用的 Worker 节点

        Returns:
            Worker URL 或 None
        """
        available_workers = [url for url in self.worker_urls if self._can_use_worker(url)]

        if not available_workers:
            logger.error("没有可用的 Worker 节点")
            return None

        if self.strategy == "round_robin" and len(available_workers) > 1:
            # Round-robin 策略
            selected = available_workers[self.current_worker_index % len(available_workers)]
            self.current_worker_index += 1
        else:
            # 单节点或回退到第一个可用节点
            selected = available_workers[0]

        # 更新请求计数
        if selected in self.workers:
            self.workers[selected]["requests"] += 1

        logger.debug(f"选择 Worker: {selected}")
        return selected

    def record_success(self, url: str):
        """记录成功请求"""
        self._update_worker_state(url, True)

    def record_failure(self, url: str):
        """记录失败请求"""
        self._update_worker_state(url, False)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 Worker 节点统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "total_workers": len(self.workers),
            "healthy_workers": sum(
                1 for w in self.workers.values()
                if w["state"] == WorkerState.HEALTHY
            ),
            "suspicious_workers": sum(
                1 for w in self.workers.values()
                if w["state"] == WorkerState.SUSPICIOUS
            ),
            "unhealthy_workers": sum(
                1 for w in self.workers.values()
                if w["state"] == WorkerState.UNHEALTHY
            ),
            "workers": {}
        }

        for url, worker in self.workers.items():
            stats["workers"][url] = {
                "state": worker["state"].value,
                "requests": worker["requests"],
                "errors": worker["errors"],
                "success_rate": f"{worker['success_rate']:.2f}%",
                "response_time": f"{worker['response_time']:.2f}ms",
                "last_check": worker["last_check"].isoformat() if worker["last_check"] else None,
            }

        return stats

    async def monitor_health(self, interval: int = 60):
        """
        定期监控 Worker 节点健康状态

        Args:
            interval: 检查间隔（秒）
        """
        while True:
            try:
                await asyncio.sleep(interval)

                # 并发检查所有 Worker
                check_tasks = []
                for url in self.worker_urls:
                    check_tasks.append(self._check_worker_health(url))

                await asyncio.gather(*check_tasks, return_exceptions=True)

                # 输出统计信息
                stats = self.get_statistics()
                logger.info(
                    f"Worker 健康监控 - "
                    f"健康: {stats['healthy_workers']}, "
                    f"可疑: {stats['suspicious_workers']}, "
                    f"熔断: {stats['unhealthy_workers']}"
                )

            except Exception as e:
                logger.error(f"Worker 健康监控异常: {e}")

    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None