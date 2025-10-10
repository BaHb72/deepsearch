"""
代理管理器

整合代理的拉取、验证、轮换与统计。
"""

import asyncio
import contextlib
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, cast

import aiohttp
from loguru import logger

from ..interfaces.base import ProxyConfig
from .pool import ProxyPool
from .validator import ProxyValidator, ProxyValidationResult


class ProxyManagerConfigSnapshot(TypedDict):
    rotation_strategy: str
    pool_size: int
    blacklist_threshold: int
    blacklist_duration: int


class ProxyManagerStats(TypedDict):
    enabled: bool
    total_requests: int
    total_success: int
    success_rate: float
    last_health_check: Optional[str]
    last_dynamic_fetch: Optional[str]
    pool: Dict[str, Any]
    config: ProxyManagerConfigSnapshot


class ProxyManager:
    """代理管理器，统一调度代理的获取、验证与健康度维护。"""

    def __init__(self, config: ProxyConfig) -> None:
        self.config = config
        self._pool = ProxyPool(rotation_strategy=config.rotation_strategy)
        self._health_check_task: Optional[asyncio.Task[None]] = None
        self._dynamic_fetch_task: Optional[asyncio.Task[None]] = None
        self._running = False

        self._total_requests = 0
        self._total_success = 0
        self._last_health_check: Optional[datetime] = None
        self._last_dynamic_fetch: Optional[datetime] = None

    async def initialize(self) -> None:
        logger.info("初始化代理管理器...")

        if self.config.proxy_list:
            await self._add_static_proxies()

        if self.config.proxy_api_url:
            await self._fetch_dynamic_proxies()

        await self._validate_all_proxies()
        available = len(await self._get_available_proxies())
        logger.info("代理管理器初始化完成，可用代理: %s", available)

    async def start(self) -> None:
        if self._running:
            return

        self._running = True

        if self.config.health_check_interval > 0:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        if self.config.proxy_api_url:
            self._dynamic_fetch_task = asyncio.create_task(self._dynamic_fetch_loop())

        logger.info("代理管理器已启动")

    async def stop(self) -> None:
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task
            self._health_check_task = None

        if self._dynamic_fetch_task:
            self._dynamic_fetch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._dynamic_fetch_task
            self._dynamic_fetch_task = None

        logger.info("代理管理器已停止")

    async def get_proxy(self) -> Optional[str]:
        self._total_requests += 1

        await self._pool.cleanup_blacklist()

        proxy: Optional[str] = await self._pool.get_proxy()

        if proxy is None and self.config.proxy_api_url:
            await self._fetch_dynamic_proxies()
            proxy = await self._pool.get_proxy()

        if proxy:
            logger.debug("分配代理: %s", proxy)
        else:
            logger.warning("暂无可用代理")

        return proxy

    async def report_success(self, proxy_url: str, response_time: float = 0.0) -> None:
        self._total_success += 1
        await self._pool.mark_success(proxy_url, response_time)

    async def mark_failure(self, proxy_url: str) -> None:
        await self._pool.mark_failure(
            proxy_url, self.config.blacklist_threshold, self.config.blacklist_duration
        )
        await self._pool.release_proxy(proxy_url)

    async def _add_static_proxies(self) -> None:
        for proxy_url in self.config.proxy_list:
            await self._pool.add_proxy(proxy_url, {"source": "static"})
        logger.info("已添加 %s 个静态代理", len(self.config.proxy_list))

    async def _fetch_dynamic_proxies(self) -> None:
        if not self.config.proxy_api_url:
            return

        try:
            async with aiohttp.ClientSession() as session:
                headers: Dict[str, str] = {}
                if self.config.proxy_api_key:
                    headers["Authorization"] = f"Bearer {self.config.proxy_api_key}"

                async with session.get(
                    self.config.proxy_api_url, headers=headers, timeout=30
                ) as response:
                    if response.status != 200:
                        logger.error("获取动态代理失败: HTTP %s", response.status)
                        return

                    data = await response.json()
                    proxies: List[str] = []

                    if isinstance(data, list):
                        proxies = [item for item in data if isinstance(item, str)]
                    elif isinstance(data, dict):
                        raw = data.get("proxies") or data.get("data") or []
                        if isinstance(raw, list):
                            proxies = [item for item in raw if isinstance(item, str)]
                        elif isinstance(raw, str):
                            proxies = [raw]

                    new_count = 0
                    for proxy in proxies:
                        await self._pool.add_proxy(proxy, {"source": "dynamic"})
                        new_count += 1

                    self._last_dynamic_fetch = datetime.now()
                    logger.info("获取到 %s 个动态代理", new_count)

        except Exception as exc:  # pragma: no cover - 网络异常
            logger.error("获取动态代理异常: %s", exc)

    async def _validate_all_proxies(self) -> None:
        proxies = list(self._pool._proxies.keys())
        if not proxies:
            return

        logger.info("开始验证 %s 个代理", len(proxies))

        async with ProxyValidator(timeout=self.config.timeout) as validator:
            results: Dict[str, ProxyValidationResult] = await validator.batch_validate(
                proxies, max_concurrent=10
            )

        for proxy_url, result in results.items():
            if result.get("valid"):
                await self._pool.mark_success(proxy_url, result.get("response_time", 0.0) or 0.0)
            else:
                await self._pool.mark_failure(
                    proxy_url,
                    self.config.blacklist_threshold,
                    self.config.blacklist_duration,
                )

    async def _get_available_proxies(self) -> List[str]:
        return [url for url, info in self._pool._proxies.items() if info.is_available]

    async def _health_check_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                proxies_to_check: List[str] = []
                now = datetime.now()

                for url, info in self._pool._proxies.items():
                    if info.status.value == "failed":
                        proxies_to_check.append(url)
                    elif info.last_used and (now - info.last_used).seconds > 300:
                        proxies_to_check.append(url)

                if proxies_to_check:
                    logger.debug("健康检查 %s 个代理", len(proxies_to_check))

                    async with ProxyValidator(timeout=self.config.timeout) as validator:
                        for proxy_url in proxies_to_check[:5]:
                            valid, result = await validator.validate_proxy(proxy_url)
                            if valid:
                                await self._pool.mark_success(
                                    proxy_url, result.get("response_time", 0.0) or 0.0
                                )
                            else:
                                await self._pool.mark_failure(
                                    proxy_url,
                                    self.config.blacklist_threshold,
                                    self.config.blacklist_duration,
                                )

                await self._pool.cleanup_blacklist()
                self._last_health_check = datetime.now()

            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - 健康检查异常
                logger.error("健康检查异常: %s", exc)

    async def _dynamic_fetch_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(300)

                available_count = len(await self._get_available_proxies())
                if available_count < self.config.pool_size:
                    logger.info(
                        "可用代理数量不足 (%s/%s)，尝试补充",
                        available_count,
                        self.config.pool_size,
                    )
                    await self._fetch_dynamic_proxies()
                    await self._validate_all_proxies()

            except asyncio.CancelledError:
                break
            except Exception as exc:  # pragma: no cover - API 异常
                logger.error("动态代理获取异常: %s", exc)

    def get_statistics(self) -> ProxyManagerStats:
        pool_stats = cast(Dict[str, Any], self._pool.get_statistics())
        config_snapshot: ProxyManagerConfigSnapshot = {
            "rotation_strategy": self.config.rotation_strategy,
            "pool_size": self.config.pool_size,
            "blacklist_threshold": self.config.blacklist_threshold,
            "blacklist_duration": self.config.blacklist_duration,
        }

        return ProxyManagerStats(
            enabled=self.config.enabled,
            total_requests=self._total_requests,
            total_success=self._total_success,
            success_rate=(
                self._total_success / self._total_requests if self._total_requests > 0 else 0.0
            ),
            last_health_check=(
                self._last_health_check.isoformat() if self._last_health_check else None
            ),
            last_dynamic_fetch=(
                self._last_dynamic_fetch.isoformat() if self._last_dynamic_fetch else None
            ),
            pool=pool_stats,
            config=config_snapshot,
        )

    def get_proxy_list(self) -> List[Dict[str, Any]]:
        return cast(List[Dict[str, Any]], self._pool.get_proxy_details())
