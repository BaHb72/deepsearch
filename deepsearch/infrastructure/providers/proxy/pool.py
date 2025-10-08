"""
代理池实现

管理代理的生命周期、状态和统计信息。
"""

import asyncio
import random
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set

from loguru import logger


class ProxyStatus(Enum):
    """代理状态"""

    UNKNOWN = "unknown"  # 未知
    AVAILABLE = "available"  # 可用
    BUSY = "busy"  # 使用中
    FAILED = "failed"  # 失败
    BLACKLISTED = "blacklisted"  # 黑名单


@dataclass
class ProxyInfo:
    """代理信息"""

    url: str
    status: ProxyStatus = ProxyStatus.UNKNOWN
    success_count: int = 0
    failure_count: int = 0
    total_requests: int = 0
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_response_time: float = 0
    weight: float = 1.0  # 权重（用于加权轮询）
    blacklisted_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0
        return self.success_count / self.total_requests

    @property
    def is_available(self) -> bool:
        """是否可用"""
        if self.status == ProxyStatus.BLACKLISTED:
            if self.blacklisted_until and datetime.now() > self.blacklisted_until:
                self.status = ProxyStatus.UNKNOWN
                self.blacklisted_until = None
                return True
            return False
        return self.status in [ProxyStatus.AVAILABLE, ProxyStatus.UNKNOWN]

    def update_success(self, response_time: float = 0):
        """更新成功统计"""
        self.success_count += 1
        self.total_requests += 1
        self.last_used = datetime.now()
        self.last_success = datetime.now()
        self.status = ProxyStatus.AVAILABLE

        # 更新平均响应时间
        if response_time > 0:
            if self.avg_response_time == 0:
                self.avg_response_time = response_time
            else:
                # 指数移动平均
                alpha = 0.3
                self.avg_response_time = (
                    alpha * response_time + (1 - alpha) * self.avg_response_time
                )

        # 更新权重（基于成功率和响应时间）
        self._update_weight()

    def update_failure(self):
        """更新失败统计"""
        self.failure_count += 1
        self.total_requests += 1
        self.last_used = datetime.now()
        self.last_failure = datetime.now()
        self.status = ProxyStatus.FAILED

        # 更新权重
        self._update_weight()

    def _update_weight(self):
        """更新权重"""
        # 基于成功率和响应时间计算权重
        success_weight = self.success_rate

        # 响应时间权重（响应时间越短权重越高）
        if self.avg_response_time > 0:
            time_weight = 1.0 / (1.0 + self.avg_response_time)
        else:
            time_weight = 0.5

        # 综合权重
        self.weight = 0.7 * success_weight + 0.3 * time_weight

        # 确保权重在合理范围内
        self.weight = max(0.1, min(1.0, self.weight))


class ProxyPool:
    """
    代理池

    管理所有代理，提供不同的选择策略。
    """

    def __init__(self, rotation_strategy: str = "round-robin"):
        """
        初始化代理池

        Args:
            rotation_strategy: 轮换策略 (round-robin, random, weighted, least-used)
        """
        self.rotation_strategy = rotation_strategy
        self._proxies: Dict[str, ProxyInfo] = {}
        self._available_queue: Deque[str] = deque()
        self._blacklist: Set[str] = set()
        self._lock = asyncio.Lock()
        self._round_robin_index = 0

    async def add_proxy(self, proxy_url: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        添加代理

        Args:
            proxy_url: 代理URL
            metadata: 代理元数据
        """
        async with self._lock:
            if proxy_url not in self._proxies:
                proxy_info = ProxyInfo(url=proxy_url, metadata=metadata or {})
                self._proxies[proxy_url] = proxy_info
                self._available_queue.append(proxy_url)
                logger.debug(f"添加代理: {proxy_url}")

    async def remove_proxy(self, proxy_url: str) -> None:
        """移除代理"""
        async with self._lock:
            if proxy_url in self._proxies:
                del self._proxies[proxy_url]
                if proxy_url in self._available_queue:
                    self._available_queue.remove(proxy_url)
                if proxy_url in self._blacklist:
                    self._blacklist.remove(proxy_url)
                logger.debug(f"移除代理: {proxy_url}")

    async def get_proxy(self) -> Optional[str]:
        """
        获取一个可用代理

        Returns:
            代理URL，如果没有可用代理返回None
        """
        async with self._lock:
            available_proxies = [url for url, info in self._proxies.items() if info.is_available]

            if not available_proxies:
                logger.warning("没有可用的代理")
                return None

            # 根据策略选择代理
            if self.rotation_strategy == "round-robin":
                proxy_url = self._round_robin_select(available_proxies)
            elif self.rotation_strategy == "random":
                proxy_url = random.choice(available_proxies)
            elif self.rotation_strategy == "weighted":
                proxy_url = self._weighted_select(available_proxies)
            elif self.rotation_strategy == "least-used":
                proxy_url = self._least_used_select(available_proxies)
            else:
                proxy_url = available_proxies[0]

            # 标记为使用中
            if proxy_url:
                self._proxies[proxy_url].status = ProxyStatus.BUSY
                self._proxies[proxy_url].last_used = datetime.now()

            return proxy_url

    def _round_robin_select(self, proxies: List[str]) -> Optional[str]:
        """轮询选择"""
        if not proxies:
            return None
        proxy = proxies[self._round_robin_index % len(proxies)]
        self._round_robin_index = (self._round_robin_index + 1) % len(proxies)
        return proxy

    def _weighted_select(self, proxies: List[str]) -> Optional[str]:
        """加权选择"""
        if not proxies:
            return None

        # 计算权重总和
        weights = [self._proxies[url].weight for url in proxies]
        total_weight = sum(weights)

        if total_weight == 0:
            return random.choice(proxies)

        # 加权随机选择
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        for proxy, weight in zip(proxies, weights):
            cumulative += weight
            if r <= cumulative:
                return proxy

        return proxies[-1]

    def _least_used_select(self, proxies: List[str]) -> Optional[str]:
        """选择使用次数最少的代理"""
        if not proxies:
            return None

        return min(proxies, key=lambda p: self._proxies[p].total_requests)

    async def mark_success(self, proxy_url: str, response_time: float = 0) -> None:
        """
        标记代理请求成功

        Args:
            proxy_url: 代理URL
            response_time: 响应时间（秒）
        """
        async with self._lock:
            if proxy_url in self._proxies:
                self._proxies[proxy_url].update_success(response_time)
                logger.debug(f"代理成功: {proxy_url}, 响应时间: {response_time:.2f}s")

    async def mark_failure(
        self, proxy_url: str, blacklist_threshold: int = 5, blacklist_duration: int = 300
    ) -> None:
        """
        标记代理请求失败

        Args:
            proxy_url: 代理URL
            blacklist_threshold: 黑名单阈值
            blacklist_duration: 黑名单持续时间（秒）
        """
        async with self._lock:
            if proxy_url not in self._proxies:
                return

            proxy_info = self._proxies[proxy_url]
            proxy_info.update_failure()

            # 检查是否需要加入黑名单
            recent_failures = 0
            if proxy_info.last_failure:
                # 统计最近的连续失败次数
                for i in range(proxy_info.failure_count):
                    if proxy_info.failure_count - i <= blacklist_threshold:
                        recent_failures += 1
                    else:
                        break

            if recent_failures >= blacklist_threshold:
                proxy_info.status = ProxyStatus.BLACKLISTED
                proxy_info.blacklisted_until = datetime.now() + timedelta(
                    seconds=blacklist_duration
                )
                self._blacklist.add(proxy_url)
                logger.warning(f"代理加入黑名单: {proxy_url}, " f"持续时间: {blacklist_duration}秒")
            else:
                logger.debug(f"代理失败: {proxy_url}, 失败次数: {proxy_info.failure_count}")

    async def release_proxy(self, proxy_url: str) -> None:
        """释放代理（标记为可用）"""
        async with self._lock:
            if proxy_url in self._proxies:
                proxy_info = self._proxies[proxy_url]
                if proxy_info.status == ProxyStatus.BUSY:
                    proxy_info.status = ProxyStatus.AVAILABLE

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_proxies = len(self._proxies)
        available_count = sum(1 for p in self._proxies.values() if p.is_available)
        blacklisted_count = len(self._blacklist)

        # 计算总体成功率
        total_success = sum(p.success_count for p in self._proxies.values())
        total_requests = sum(p.total_requests for p in self._proxies.values())
        overall_success_rate = total_success / total_requests if total_requests > 0 else 0

        # 找出最佳和最差代理
        best_proxy = None
        worst_proxy = None
        if self._proxies:
            sorted_proxies = sorted(
                self._proxies.values(), key=lambda p: p.success_rate, reverse=True
            )
            if sorted_proxies:
                best_proxy = {
                    "url": sorted_proxies[0].url,
                    "success_rate": sorted_proxies[0].success_rate,
                    "avg_response_time": sorted_proxies[0].avg_response_time,
                }
                worst_proxy = {
                    "url": sorted_proxies[-1].url,
                    "success_rate": sorted_proxies[-1].success_rate,
                    "avg_response_time": sorted_proxies[-1].avg_response_time,
                }

        return {
            "total_proxies": total_proxies,
            "available_proxies": available_count,
            "blacklisted_proxies": blacklisted_count,
            "total_requests": total_requests,
            "total_success": total_success,
            "overall_success_rate": overall_success_rate,
            "rotation_strategy": self.rotation_strategy,
            "best_proxy": best_proxy,
            "worst_proxy": worst_proxy,
        }

    def get_proxy_details(self) -> List[Dict[str, Any]]:
        """获取所有代理的详细信息"""
        return [
            {
                "url": info.url,
                "status": info.status.value,
                "success_rate": info.success_rate,
                "total_requests": info.total_requests,
                "avg_response_time": info.avg_response_time,
                "weight": info.weight,
                "last_used": info.last_used.isoformat() if info.last_used else None,
                "blacklisted_until": (
                    info.blacklisted_until.isoformat() if info.blacklisted_until else None
                ),
            }
            for info in self._proxies.values()
        ]

    async def cleanup_blacklist(self) -> None:
        """清理过期的黑名单"""
        async with self._lock:
            now = datetime.now()
            expired = []

            for proxy_url in self._blacklist:
                if proxy_url in self._proxies:
                    proxy_info = self._proxies[proxy_url]
                    if proxy_info.blacklisted_until and now > proxy_info.blacklisted_until:
                        proxy_info.status = ProxyStatus.UNKNOWN
                        proxy_info.blacklisted_until = None
                        expired.append(proxy_url)

            for proxy_url in expired:
                self._blacklist.remove(proxy_url)
                logger.info(f"代理移出黑名单: {proxy_url}")
