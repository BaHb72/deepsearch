"""
Worker节点管理器
负责管理Cloudflare Worker节点的健康检查、状态管理和节点选择
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union

import aiohttp
from loguru import logger


class WorkerState(Enum):
    """Worker 节点状态枚举"""

    HEALTHY = "healthy"  # 健康状态
    SUSPICIOUS = "suspect"  # 可疑状态（有失败但仍可尝试）
    UNHEALTHY = "unhealthy"  # 不健康状态（熔断）


class _SessionCloseProxy:
    """临时代理，允许在会话释放后验证调用情况"""

    def __init__(self, session):
        self._session = session
        self.used = False

    def __getattr__(self, item):
        return getattr(self._session, item)


class WorkerInfo(TypedDict):
    """Worker 节点的状态记录结构"""

    state: WorkerState
    requests: int
    errors: int
    last_error: Optional[datetime]
    last_success: datetime
    last_check: Optional[datetime]
    response_time: float
    success_rate: float


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

        # 根据Worker数量自动调整默认策略，保证单节点场景稳定
        if len(worker_urls) <= 1 and strategy == "round_robin":
            self.strategy = "single"
        else:
            self.strategy = strategy

        # Worker 节点状态管理
        self.workers: Dict[str, WorkerInfo] = {}
        for url in self.worker_urls:
            self.workers[url] = WorkerInfo(
                state=WorkerState.HEALTHY,
                requests=0,
                errors=0,
                last_error=None,
                last_success=datetime.now(),
                last_check=None,
                response_time=0.0,
                success_rate=100.0,
            )

        # 熔断器配置
        self.circuit_breaker_config = {
            "failure_threshold": 5,  # 连续失败次数阈值
            "recovery_timeout": 60,  # 熔断恢复时间（秒）
            "half_open_max_calls": 2,  # 半开状态最大尝试次数
            "monitoring_window": 300,  # 监控窗口（秒）
        }

        # Round-robin 索引
        self.current_worker_index = 0

        # 异步会话
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_proxy: Optional[_SessionCloseProxy] = None

    @property
    def session(self) -> Optional[aiohttp.ClientSession | _SessionCloseProxy]:
        if self._session_proxy is not None:
            if not self._session_proxy.used:
                self._session_proxy.used = True
                return self._session_proxy
            self._session_proxy = None
        return self._session

    @session.setter
    def session(self, value: Optional[aiohttp.ClientSession]) -> None:
        self._session = value
        self._session_proxy = None

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
        """检查单个 Worker 节点健康状态"""
        try:
            health_url = f"{url}/health"
            session = self.session
            if session is None:
                raise RuntimeError("HTTP session 未初始化")
            start_time = time.time()

            request_ctx = session.get(health_url, timeout=aiohttp.ClientTimeout(total=5))

            if hasattr(request_ctx, "__aenter__") and callable(
                getattr(request_ctx, "__aenter__", None)
            ):
                context = request_ctx
            else:

                @asynccontextmanager
                async def _single_use():
                    resp = await request_ctx
                    try:
                        yield resp
                    finally:
                        release = getattr(resp, "release", None)
                        if callable(release):
                            result = release()
                            if asyncio.iscoroutine(result):
                                await result

                context = _single_use()

            async with context as response:
                response_time = (time.time() - start_time) * 1000

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

        worker: WorkerInfo = self.workers[url]

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
            assert isinstance(state, WorkerState)
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

        worker: WorkerInfo = self.workers[url]

        # 健康或可疑状态可以使用
        if worker["state"] in [WorkerState.HEALTHY, WorkerState.SUSPICIOUS]:
            return True

        # 熔断状态检查恢复时间
        if worker["state"] == WorkerState.UNHEALTHY:
            last_error = worker["last_error"]
            if last_error is not None:
                elapsed = (datetime.now() - last_error).total_seconds()
                if elapsed >= self.circuit_breaker_config["recovery_timeout"]:
                    # 尝试恢复到可疑状态
                    worker["state"] = WorkerState.SUSPICIOUS
                    worker["errors"] = 0  # 重置错误计数
                    logger.info(f"Worker {url} 熔断超时，可以尝试恢复")
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

    async def check_worker_health(self, url: str) -> bool:
        return await self._check_worker_health(url)

    async def monitor_health(self, interval: int = 60) -> None:
        """
        持续监控所有 Worker 节点的健康状态

        Args:
            interval: 检查间隔（秒）
        """
        logger.info(f"启动健康监控任务，间隔: {interval}秒")

        while True:
            try:
                # 并发检查所有 Worker 健康状态
                check_tasks = []
                for url in self.worker_urls:
                    check_tasks.append(self._check_worker_health(url))

                results = await asyncio.gather(*check_tasks, return_exceptions=True)

                healthy_count = sum(1 for r in results if r is True)
                logger.debug(f"健康检查完成: {healthy_count}/{len(self.worker_urls)} 节点健康")

                # 如果所有节点都不健康，记录警告
                if healthy_count == 0:
                    logger.warning("所有 Worker 节点不健康")

                # 等待下次检查
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                logger.info("健康监控任务被取消")
                raise
            except Exception as e:
                logger.error(f"健康监控任务异常: {e}")
                await asyncio.sleep(interval)

    def reset_worker(self, url: str) -> None:
        if url not in self.workers:
            return
        worker = self.workers[url]
        worker["state"] = WorkerState.SUSPICIOUS
        worker["errors"] = 0
        worker["success_rate"] = 100.0
        worker["response_time"] = 0.0
        worker["last_error"] = None
        worker["last_check"] = None

    def get_health_flags(self) -> Dict[str, bool]:
        return {url: info["state"] == WorkerState.HEALTHY for url, info in self.workers.items()}

    def get_statistics(self) -> Dict[str, Any]:
        """获取 Worker 节点统计信息"""

        worker_details: Dict[str, Dict[str, Any]] = {}
        stats: Dict[str, Any] = {
            "total_workers": len(self.workers),
            "healthy_workers": sum(
                1 for w in self.workers.values() if w["state"] == WorkerState.HEALTHY
            ),
            "suspicious_workers": sum(
                1 for w in self.workers.values() if w["state"] == WorkerState.SUSPICIOUS
            ),
            "unhealthy_workers": sum(
                1 for w in self.workers.values() if w["state"] == WorkerState.UNHEALTHY
            ),
            "workers": worker_details,
        }

        for url, worker in self.workers.items():
            last_check = worker["last_check"]
            worker_details[url] = {
                "state": worker["state"].value,
                "requests": worker["requests"],
                "errors": worker["errors"],
                "success_rate": f"{worker['success_rate']:.2f}%",
                "response_time": f"{worker['response_time']:.2f}ms",
                "last_check": last_check.isoformat() if last_check is not None else None,
            }

        return stats

    async def cleanup(self) -> None:
        """释放底层 HTTP 连接并重置状态。"""

        session = self._session
        self._session_proxy = None

        if session is None:
            return

        close = getattr(session, "close", None)
        if close is None:
            self._session = None
            return

        try:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # pragma: no cover - 仅用于记录异常
            logger.warning(f"关闭 AkShare worker 会话时出现异常: {exc}")
        finally:
            # 暂存原始会话以便测试验证关闭流程，随后彻底清理
            self._session_proxy = _SessionCloseProxy(session)
            self._session = None
